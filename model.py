import re
from glob import glob
from os.path import (basename, dirname, abspath, join, sep, normpath, isdir,
                     isfile)
from collections import OrderedDict
from PyQt5.QtCore import QAbstractListModel, QAbstractItemModel
from PyQt5.Qt import Qt, QVariant, QModelIndex


class ModelError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class Model:
    def __init__(self, views=None):
        self._views = []
        if views is not None:
            for view in views:
                self._add_view(view)

    def _update_views(self, *args, **kwargs):
        for view in self._views:
            view._update_view(*args, **kwargs)

    def _add_view(self, view):
        if view in self._views:
            raise ModelError((
                "View {} is already observing model {} and thus,"
                " can not be added as view"
            ).format(view, model))
        self._views.append(view)

    def _remove_view(self, view):
        if view not in self._views:
            raise ModelError((
                "View {} is not observing model {} and thus,"
                " can not be removed as view"
            ).format(view, model))
        self._views.remove(view)


def summary_data_from_enc_logs(encLogs):
    """Create a dictionary containing the summary data by combining
       different encLogs."""
    #{'Summary' : {'Y-PSNR' : [...], 'PSNR' : ...}, 'I' : ...}
    output = {}
    for encLog in encLogs:
        seqconf = encLog.sequence + ' ' + encLog.config
        if seqconf not in output:
            output[seqconf] = {}
        for (name1, dict1) in encLog.summary_data.items():
            if name1 not in output[seqconf]:
                output[seqconf][name1] = {}
            for (name2, list2) in dict1.items():
                if name2 not in output[seqconf][name1]:
                    output[seqconf][name1][name2] = []
                output[seqconf][name1][name2].extend(list2)
    return output

def sort_dict_of_lists_by_key(dictionary, sorting_key):
    """Take a dictionary with equal length lists as items and sort all list
       according to one list identified by sorting_key"""
    sorting_list = dictionary[sorting_key]
    sorted_dictionary = {sorting_key : sorted(sorting_list)}
    for (key, item) in dictionary.items():
        if key != sorting_key:
            sorted_pairs = sorted(zip(sorting_list, item),
                                  key=lambda zipped: zipped[0])
            sorted_dictionary[key] = list(zip(*sorted_pairs))[1]
    return sorted_dictionary


class EncLogParserError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class EncLog():
    def __init__(self, path):
        #Path is unique identifier
        self.path = abspath(path)

        #Parse file path and set additional identifiers
        self.sequence, self.config, self.qp = self._parse_path(self.path)

        #Dictionaries holding the parsed values
        #TODO select parsing functions depending on codec type,
        self.summary_data  = self._parse_summary_data(self.path)
        self.temporal_data = {self.qp : self._parse_temporal_data(self.path)}

    @classmethod
    def parse_url(cls, url):
        """Parse a url and return either all encoder logs in the folder, all
           logs in a subfolder log or all encoder logs with the same sequence as
           the file."""
        # Parse url as directory. Check for encoder log files in directory and
        # in a possible 'log' subdirectory
        if isdir(url) == True:
            enc_logs = list( cls.parse_directory(url) )
            if len(enc_logs) != 0:
                return enc_logs

            url_log = join(url, 'log')
            if isdir( url_log ) == True:
                enc_logs = list( cls.parse_directory(url_log) )
                if len(enc_logs) != 0:
                    return enc_logs

        # Parse url as encoder log path. Search in same directory for encoder
        # logs with same sequence
        if isfile(url) == True:
            enc_logs = list( cls.parse_directory_for_sequence(url) )
            if len(enc_logs) != 0:
                return enc_logs

        # No parsing scheme succeeded
        raise EncLogParserError( "Could not parse url {} for encoder logs"
                                .format(url) )

    @classmethod
    def parse_directory(cls, directory_path):
        """Parse a directory for all encoder log files and return generator
           yielding :class: `EncLog`s"""
        #TODO join vs sep and glob pattern?
        paths = glob(join(directory_path, '*_enc.log'))

        return (EncLog(p) for p in paths)

    @classmethod
    def parse_directory_for_sequence(cls, sequence_file_path):
        """Parse a directory for encoder logs of a specific sequence given one
           encoder log of this sequence returning a generator yielding parsed
           encoder :class: `EncLog`s"""
        filename = basename(sequence_file_path)
        directory = dirname(sequence_file_path)
        sequence = filename.rsplit('_QP', 1)[0]

        #Search for other encoder logs in directory and parse them
        #TODO hardcoded file ending, needed to prevent ambiguous occurence
        #exceptions due to *.csv or other files being parsed
        paths = glob(directory + sep + sequence + '*_enc.log')

        return (EncLog(p) for p in paths)

    @staticmethod
    def _parse_path(path):
        try:
            # Assumes structure of .../<simulation_directory>/log/<basename>
            directories = normpath(path).split(sep)[0 : -2]
            filename    = basename(path)
        except IndexError:
            raise EncLogParserError(
                "Path {} can not be splitted into directories and filename"
                .format(filename, path)
            )

        try:
            seperator = '-'
            filename_splitted = filename.split('_QP')[0].split(seperator)
            sequence = filename_splitted[-1]
            config = seperator.join(filename_splitted[0 : -2])
        except IndexError:
            raise EncLogParserError((
                "Filename {} can not be splitted into config until '{}' and"
                " sequence between last '{}' and '_QP'"
            ).format(filename, seperator, seperator))

        # prepend simulation directory to config
        config = directories[-1] + ' ' + config

        m = re.search(r'_QP(\d*)_', filename)
        if m:
            qp = m.group(1)
        else:
            raise EncLogParserError(
                "Basename {} of path {} does not contain a valid qp value"
                .format(filename, path)
            )
        return (sequence, config, qp)

    @staticmethod
    def _parse_temporal_data(path):
        #this function extracts temporal values
        with open(path, 'r') as log_file:
            log_text = log_file.read()  # reads the whole text file
            tempData = re.findall(r"""
                POC \s+ (\d+) \s+ .+ \s+ \d+ \s+ . \s+ (.-\D+) ,  #Slice
                \s .+ \) \s+ (\d+) \s+ (.+) \s+ \[ (\D+) \s+ (\d+.\d+) \s+ #Y PSNR
                \D+ \s+ (\D+) \s+ (\d+.\d+) \s+ # U PSNR
                \D+ \s+ (\D+) \s+ (\d+.\d+) \s+ # v PSNR
                """, log_text, re.M + re.X)

            #Association between index of data in tempData and corresponding
            #output key. Output shape definition is in one place.
            names = {0 : 'Frames', 2 : 'Bits', 5 : 'Y-PSNR', 7 : 'U-PSNR',
                     9 : 'V-PSNR'}

            #Define output data dict and fill it with parsed values
            data = {name : [] for (index, name) in names.items()}
            for i in range(0, len(tempData)):
                #TODO slices and frames?
                for (index, name) in names.items():
                    data[name].append(tempData[i][index])
            return data

    @staticmethod
    def _parse_summary_data(path):
        with open(path, 'r') as log_file:
            log_text = log_file.read()  # reads the whole text file
            summaries = re.findall(r"""  ^(\w*)-*.*$ # catch summary line
                           \s* # catch newline and space
                           (.*)\| # catch phrase Total Frames / I / P / B
                           (\s*\S*)(\s*\S*)(\s*\S*)(\s*\S*)(\s*\S*)# catch rest of the line
                           \s* # catch newline and space
                           (\d*\s*)\w # catch frame number
                           (\s*\d*\.\d*)(\s*\d*\.\d*)(\s*\d*\.\d*)(\s*\d*\.\d*)(\s*\d*\.\d*) # catch the fractional number (rate, PSNRs)
                      """, log_text, re.M + re.X)

            data = {}
            for summary in summaries:
                summary_type = summary[0]
                # Create upon first access
                if summary_type not in data:
                    data[summary_type] = {}
                names = summary[1:7]
                vals = summary[7:]

                names = [name.strip() for name in names]  # remove leading and trailing space
                vals = [float(val) for val in vals]  # convert to numbers

                name_val_dict = dict(zip(names, vals))  # pack both together in a dict
                # print(summary_type)

                # now pack everything together
                for name in names:
                    if name not in data[summary_type]: # create upon first access
                        data[summary_type][name] = []
                    data[summary_type][name].append(name_val_dict[name])
            return data

    def __eq__(self, enc_log):
        return self.path == enc_log.path

    def __str__(self):
        return str((
            "Encoder Log of sequence '{}' from config '{}' with qp '{}'"
            " at path {}"
       ).format(self.sequence, self.config, self.qp, self.path))

    def __repr__(self):
        return str(self)

class OrderedDictModel(QAbstractListModel):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self._dict = OrderedDict(*args, **kwargs)

    def rowCount(self, parent):
        return len(self._dict)

    def data(self, qIndex, role):
        if qIndex.isValid() and role == Qt.DisplayRole:
            for index, (key, item) in enumerate(self._dict.items()):
                if index == qIndex.row():
                    return QVariant( key )
        return QVariant()

    def __setitem__(self, key, item):
        length = len(self._dict)
        for index, oldkey in enumerate(self._dict):
            if oldkey == key:
                length = index

        self.beginInsertRows(QModelIndex(), length, length + 1)
        self._dict[key] = item
        self.endInsertRows()

    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __contains__(self, key):
        return key in self._dict

    def __len__(self):
        return len(self._dict)

    def __str__(self):
        return str(list(self._dict))

    def __repr__(self):
        return str(self)


class OrderedDictTreeItem():
    """Item of tree model. The item imitates the behavior of a dictionary, thus,
       each item has an identifier, and the children of an item can be accessed
       by `DictTreeItem`[ìdentifier]."""
    def __init__(self, identifier=None,  parent=None, children=None, value=None):
        self.identifier = identifier
        self.parent     = parent

        self._children  = []
        if children is not None:
            self.extend(children)

        self.value      = value

    @property
    def children(self):
        #TODO as this is copy by reference it is not really safer
        return self._children

    @property
    def dict_tree(self):
        # Create tree of ordinary dicts from item
        if len(self) == 0:
            return self.value
        return { child.identifier : child.dict_tree }

    def add(self, child):
        child.parent = self

        # If a child with the identifier is already present it is replaced, else
        # the child is inserted at the end
        if child in self:
            index = self._children.index(child.identifier)
            self._children[index] = child
        else:
            self._children.append( child )

    def update(self, children):
        for child in children:
            self.add(child)

    def __getitem__(self, identifier):
        for child in self._children:
            if child.identifier == identifier:
                return child

        raise KeyError("Key {key} not found in item {item}".format(
            key     = identifier,
            item    = str(self)
        ))

    def __len__(self):
        return len(self._children)

    def __iter__(self):
        for child in self._children:
            yield child.identifier

    def __contains(self, identifier):
        for identifier_child in self:
            if identifier_child == identifier:
                return True
        return False

    def __str__(self):
        return str(self.identifier)

    def __repr__(self):
        return str(self.dict_tree)

class OrderedDictTreeModel(QAbstractItemModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.root = OrderedDictTreeItem()

    def __getitem__(self, *keys):
        """Access elements of the tree by identifiers seperated by commas. The
           last element can be a slice. which automatically select all
           subitems, not only the children, but also their children, and so on.
           """
        item = self.root
        for index, key in enumerate(keys):
            if isinstance(key, slice) == True:
                # TODO implement slice not only as last identifier
                if index != len(keys) - 1:
                    raise KeyError("Slice has to be last identifier")
                return item.get_all_subitems()
            item = item[key]
        return item

    def __setitem__(self, *args):
        """"""
        keys, value = args

        item = self.root
        for index, key in enumerate(keys):
            if isinstance(key, slice) == True:
                # TODO implement slice not only as last identifier
                if index != len(keys) - 1:
                    raise KeyError("Slice has to be last identifier")
                return item.get_all_subitems()
            if key not in item:
                item.add( OrderedDictTreeItem(identifier=key) )
            item = item[key]
        item.value = value

    def __repr__(self):
        return str( self.root.dict_tree )

    # Implement abstract methods from Qt superclass

    def index(self, row, column, q_parent_index):
        if column == 1 and q_parent_index.isValid() == True:
            child = q_parent_index.internalPointer().children[ row ]
            return self.createIndex(row, 1, child)
        # TODO empty index?
        return QModelIndex()

    def parent(self, q_parent_index):
        if q_parent_index.isValid() == True:
            return QModelIndex()
            # TODO q_parent_index.internalPointer().parent
        return QModelIndex()

    def rowCount(self, q_parent_index):
        # TODO Sufficient?
        if q_parent_index.isValid() == True:
            return len( parent_q_index.internalPointer() )
        return len(self.root)

    def columnCount(self, q_parent_index):
        # All items only hold their own identifier as data to be displayed,
        # thus, the agument is irrelevant
        return 1

    def data(self, q_parent_index, q_role):
        if q_role == Qt.DisplayRole:
            if q_parent_index.isValid() == True:
                return QVariant( str( q_parent_index.internalPointer() ) )
            return QVariant( str( self.root ) )
        return QVariant()

class EncLogCollectionModelContainer():
    _max_tree_depth = 3

    """Collection of :class: `model.EncLog`s. The class implements different
       access/iteration/etc. methods. Additionally it implements parsing the
       file system for certain encoder logs eg. all encoder logs of one sequence
       in different folders."""
    def __init__(self, enc_logs=None):
        #References to the encoder logs are stored in a flat dictionary using
        #the path/unique identifier as key and a tree using sequence, config and
        #qp as key
        self.list_model = OrderedDictModel()
        self.tree_model = OrderedDictTreeModel()
        if enc_logs is not None:
            self.update(enc_logs)

    def add(self, enc_log):
        """Adds :param: `enc_log` to the collection or replaces it if it is
           already in the collection."""

        #TODO Tree access is not unique in
        #filesystem. This prevents an encoder log overwriting another one with
        #same sequence, config and qp but on a different location. The question
        #is, if this should be the case?
        if enc_log.qp in self.tree_model[enc_log.sequence][enc_log.config]:
            old_enc_log = self.tree_model[enc_log.sequence][enc_log.config][enc_log.qp]
            if old_enc_log != enc_log:
                raise Exception((
                    "Ambigious encoder logs: Encoder log at {} and {} have the"
                    " same sequence '{}', dir '{}' and qp '{}', but different"
                    " absolute paths."
                ).format(old_enc_log.path, enc_log.path, enc_log.sequence,
                         enc_log.config, enc_log.qp))

        self.tree_model[enc_log.sequence, enc_log.config, enc_log.qp] = enc_log
        self.list_model[enc_log.path] = enc_log

        self._update_views(self.tree_model)

    def update(self, enc_logs):
        """Adds all elements in the iterable :param: `enc_logs` to the
           collection"""
        for enc_log in enc_logs:
            self.add(enc_log)

    @classmethod
    def _flatten_dict_tree(cls, parent, depth=0):
        """Helper function to create a flatted list from a dictionary tree."""
        if depth >= cls._max_tree_depth:
            raise Exception("Maximal tree depth exceeded")
        if isinstance(parent, EncLog):
            return [parent]

        enc_logs = []
        for child in parent.values():
            enc_logs.extend( cls._flatten_dict_tree(child, depth = depth + 1) )
        return enc_logs

    def get_by_sequence(self, sequence):
        #Access a sequence in the EncLog tree and flatten the remaining tree
        return self._flatten_dict_tree( self.tree_model[sequence] )

    def get_by_tree_keys(self, sequence, config, qp):
        return self.tree_model[sequence][config][qp]

    def __getitem__(self, path):
        """Access element by path ie. unique identifier"""
        return self.list_model[path]

    def __iter__(self):
        return iter(self.list_model)

    def __contains__(self, enc_log):
        return enc_log.path in self.list_model

    def __len__(self):
        return len(self.list_model)

    def __str__(self):
        return str(list(self))

    def __repr__(self):
        return str(self)

