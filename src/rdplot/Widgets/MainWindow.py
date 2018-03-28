from os import path
from os.path import sep, isfile, isdir
import csv

import pkg_resources
import jsonpickle
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import QItemSelectionModel
from PyQt5.uic import loadUiType

from rdplot.Widgets.CurveWindow import CurveWindow
from rdplot.SimulationDataItem import dict_tree_from_sim_data_items, PlotData
from rdplot.Widgets.PlotWidget import PlotWidget
from rdplot.model import SimDataItemTreeModel, OrderedDictModel, VariableTreeModel, BdTableModel
from rdplot.view import QRecursiveSelectionModel

Ui_name = pkg_resources.resource_filename('rdplot', 'ui' + sep + 'mainWindow.ui')
Ui_MainWindow, QMainWindow = loadUiType(Ui_name)

here = pkg_resources.resource_filename('rdplot','')
#here = path.abspath(path.dirname(__file__) + '/../')

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, ):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        self.fig_dict = {}

        self.tabWidget.setCurrentIndex(0)

        self.plotAreaVerticalLayout = QtWidgets.QVBoxLayout()
        self.plotsFrame.setLayout(self.plotAreaVerticalLayout)

        #initialize Table
        self.headerV = self.tableWidget.verticalHeader()
        self.headerV.show()

        # add a widget for previewing plots, they can then be added to the actual plot
        self.plotPreview = PlotWidget()
        self.plotAreaVerticalLayout.addWidget(self.plotPreview)

        # Create tree model to store sim data items and connect it to views
        self.simDataItemTreeModel = SimDataItemTreeModel()
        self.bdTableModel = BdTableModel()
        self.simDataItemTreeView.setModel(self.simDataItemTreeModel)
        self.plotPreview.tableView.setModel(self.bdTableModel)

        # connect a double clicked section of the bd table to a change of the anchor
        self.plotPreview.tableView.horizontalHeader().sectionDoubleClicked.connect(self.update_bd_table)

        # Set custom selection model, so that sub items are automatically
        # selected if parent is selected
        self._selection_model = QRecursiveSelectionModel(self.simDataItemTreeView.model())
        self.simDataItemTreeView.setSelectionModel(self._selection_model)

        # Connect list view with model for the selected values of tree view
        self.selectedSimulationDataItemListModel = OrderedDictModel()
        self.simDataItemListView.setModel(self.selectedSimulationDataItemListModel)
        self._selection_model.selectionChanged.connect(self.change_list)

        # set up signals and slots
        self.selectedSimulationDataItemListModel.items_changed.connect(
            self.update_variable_tree
        )

        # Connect signals of menus
        self.actionOpen_File.triggered.connect(
            self.simDataItemTreeView.add_file
        )
        self.actionOpen_Directory.triggered.connect(
            self.simDataItemTreeView.add_folder
        )
        self.actionOpen_Directory_List.triggered.connect(
            self.simDataItemTreeView.add_folder_list
        )
        self.actionHide_PlotSettings.triggered.connect(
            self.set_plot_settings_visibility
        )
        self.actionHide_Sequence.triggered.connect(
            self.set_sequence_widget_visibility
        )
        self.actionHide_Status.triggered.connect(
            self.set_status_widget_visibility
        )

        self.actionSave_Table.triggered.connect(
            self.save_bd_table
        )

        self.actionExport_TableWidget.triggered.connect(
            self.export_table_to_csv
        )

        self.actionSave_Data.triggered.connect(
            self.save_current_selection
        )

        self.action_About.triggered.connect(
            self.open_about_page
        )

        self.variableTreeModel = VariableTreeModel()
        self.variableTreeView.setModel(self.variableTreeModel)
        self.plotsettings.visibilityChanged.connect(self.plot_settings_visibility_changed)
        self.sequenceWidget.visibilityChanged.connect(self.sequence_widget_visibility_changed)
        self.statusWidget.visibilityChanged.connect(self.status_widget_visibility_changed)

        # Set recursive selection model for variable view
        self._variable_tree_selection_model = QRecursiveSelectionModel(
            self.variableTreeView.model()
        )
        self.variableTreeView.setSelectionModel(
            self._variable_tree_selection_model
        )

        # set up combo boxes for rate/psnr and interpolation options
        self.combo_interp.addItems(["pchip", "pol"])
        self.combo_rate_psnr.addItems(["drate", "dsnr"])
        self.combo_interp.currentIndexChanged.connect(self.on_combo_box)
        self.combo_rate_psnr.currentIndexChanged.connect(self.on_combo_box)

        # set up button to generate new curve
        self.pushButton_newcurve.clicked.connect(self.generate_new_curve)

        self.curve_window = CurveWindow()

    # sets Visibility for the Plotsettings Widget
    def set_plot_settings_visibility(self):
        self.plotsettings.visibilityChanged.disconnect(self.plot_settings_visibility_changed)
        if self.plotsettings.isHidden():
            self.plotsettings.setVisible(True)
        else:
            self.plotsettings.setHidden(True)
        self.plotsettings.visibilityChanged.connect(self.plot_settings_visibility_changed)

    # updates the QAction if Visibility is changed
    def plot_settings_visibility_changed(self):
        if self.plotsettings.isHidden():
            self.actionHide_PlotSettings.setChecked(True)
        else:
            self.actionHide_PlotSettings.setChecked(False)
        self._variable_tree_selection_model.selectionChanged.connect(self.update_plot)

        self.simDataItemTreeView.deleteKey.connect(self.remove)

    # sets Visibility for the Sequence Widget
    def set_sequence_widget_visibility(self):
        self.sequenceWidget.visibilityChanged.disconnect(self.sequence_widget_visibility_changed)
        if self.sequenceWidget.isHidden():
            self.sequenceWidget.setVisible(True)
        else:
            self.sequenceWidget.setHidden(True)
        self.sequenceWidget.visibilityChanged.connect(self.sequence_widget_visibility_changed)

    def sequence_widget_visibility_changed(self):
        if self.sequenceWidget.isHidden():
            self.actionHide_Sequence.setChecked(True)
        else:
            self.actionHide_Sequence.setChecked(False)

    # Sets Visibility for the Status Widget
    def set_status_widget_visibility(self):
        self.statusWidget.visibilityChanged.disconnect(self.status_widget_visibility_changed)
        if self.statusWidget.isHidden():
            self.statusWidget.setVisible(True)
        else:
            self.statusWidget.setHidden(True)
        self.statusWidget.visibilityChanged.connect(self.status_widget_visibility_changed)

    def status_widget_visibility_changed(self):
        if self.statusWidget.isHidden():
            self.actionHide_Status.setChecked(True)
        else:
            self.actionHide_Status.setChecked(False)

    def remove(self):
        values = self.selectedSimulationDataItemListModel.values()
        # List call necessary to avoid runtime error because of elements changing
        # during iteration
        self._variable_tree_selection_model.selectionChanged.disconnect()
        self.simDataItemTreeModel.remove(list(values))
        self._variable_tree_selection_model.selectionChanged.connect(self.update_plot)

    def change_list(self, q_selected, q_deselected):
        """Extend superclass behavior by automatically adding the values of
           all selected items in :param: `q_selected` to value list model. """

        selected_q_indexes = q_deselected.indexes()

        q_reselect_indexes = []
        for q_index in self.simDataItemTreeView.selectedIndexes():
            if q_index not in selected_q_indexes:
                q_reselect_indexes.append(q_index)

        # Find all all values that are contained by selected tree items
        tuples = []
        for q_index in q_selected.indexes() + q_reselect_indexes:
            # Add values, ie. sim data items stored at the item, to the list
            # model.
            sim_data_items = q_index.internalPointer().values
            tuples.extend((e.path, e) for e in sim_data_items)

        # Overwrite all elements in dictionary by selected values
        # Note, that overwriting only issues one `updated` signal, and thus,
        # only rerenders the plots one time. Therefore, simply overwriting
        # is much more efficient, despite it would seem, that selectively
        # overwriting keys is.
        self.selectedSimulationDataItemListModel.clear_and_update_from_tuples(tuples)

    def get_selected_simulation_data_items(self):
        return [self.selectedSimulationDataItemListModel[key] for key in self.selectedSimulationDataItemListModel]

    def get_plot_data_collection_from_selected_variables(self):
        """Get a :class: `dict` with y-variable as key and values as items
        from the current selection of the variable tree.

        :rtype: :class: `dict` of :class: `string` and :class: `list`
        """

        plot_data_collection = []
        for q_index in self.variableTreeView.selectedIndexes():
            item = q_index.internalPointer()
            if len(item.values) > 0:
                plot_data_collection.extend(item.values)

        return plot_data_collection

    def update_variable_tree(self):
        """Collect all SimDataItems currently selected, and create variable
        tree and corresponding data from it. Additionaly reselect all prevously
        selected variables.
        """

        # Create a list of all currently selected paths
        # Note, that *q_index* can not be used directly, because it might
        # change if the variable tree is recreated
        selected_path_collection = []
        for q_index in self.variableTreeView.selectedIndexes():
            selected_path_collection.append(
                # Create list of identifiers from path
                # Note, that the root node is excluded from the path
                [item.identifier for item in q_index.internalPointer().path[1:]]
            )

        # Join the data of all currently selected items to a dictionary
        # tree
        sim_data_items = self.get_selected_simulation_data_items()
        dict_tree = dict_tree_from_sim_data_items(sim_data_items)
        # Reset variable tree and update it with *dict_tree*
        self.variableTreeModel.clear_and_update_from_dict_tree(dict_tree)

        # Auto expand variable tree
        self.variableTreeView.expandToDepth(1)

        # Reselect all variables, which also exist on the new tree
        for path in selected_path_collection:
            # Try to reselect, and do nothing, if path does not exist anymore
            try:
                # Reselect new item corresponding to the previously selected
                # path
                item = self.variableTreeModel.get_item_from_path(*path)
                self.variableTreeView.selectionModel().select(
                    self.variableTreeModel._get_index_from_item(item),
                    QItemSelectionModel.Select,
                )
            except KeyError:
                pass

    def check_labels(self):
        selectionmodel = self.variableTreeView.selectionModel()
        selected = self.variableTreeView.selectedIndexes()
        # return if no comparison needed
        if len(selected) < 2:
            return
        labelx = []
        labely = []
        for index in selected:
            x = index.internalPointer()
            if len(x.values) > 0:
                labelx.append(x.values[0].label[0])
                labely.append(x.values[0].label[1])

        if all(x == labelx[0] for x in labelx) and all(x == labely[0] for x in labely):
            return

        else:
            QtWidgets.QMessageBox.information(self, "Error!",
                                              "You should not choose curves with different units.")
            selectionmodel.clearSelection()

    # updates the plot if the plot variable is changed
    def update_plot(self):
        self.check_labels()
        plot_data_collection = self.get_plot_data_collection_from_selected_variables()

        self.plotPreview.change_plot(plot_data_collection)
        self.update_table(plot_data_collection)

        # update the model for the bd table, note the anchor is always
        # the first config if new simDataItems are selected
        self.bdTableModel.update(plot_data_collection, self.combo_rate_psnr.currentText(),
                                 self.combo_interp.currentText())

    def get_table_header(self, plot_data_collection):
        tmp_legend = []
        tmp_config = []

        # make legend
        for plot_data in plot_data_collection:
            tmp = []
            for identifiers in plot_data.identifiers[1:]:
                tmp += identifiers.split(sep)
            tmp2 = tmp + plot_data.path
            tmp_legend.append(tmp2)
            tmp_config.append(tmp)

        legend = []
        config = []
        for c in tmp_legend:
            result = list(filter(lambda x: all(x in l for l in tmp_legend) == False, c))
            if result == []: result = [plot_data.path[-1]]
            legend.append(" ".join(result))
        if len(tmp_legend) == 1:
            legend = [plot_data.path[-1]]

        #make config
        for c in tmp_config:
            result = list(filter(lambda x: all(x in l for l in tmp_config) == False, c))
            if ((set([" ".join(result)]) - set(config) != set()) & (result != [])): config.append(" ".join(result))

        result = (legend, config)
        return result

    #updates the table
    def update_table(self,plot_data_collection):

        self.tableWidget.clear()
        self.tableWidget.setColumnCount(0)
        self.tableWidget.setRowCount(0)

        if plot_data_collection != []:
            if 'Temporal' in plot_data_collection[0].path: self.change_table_temporal(plot_data_collection)
            else: self.change_table_summary(plot_data_collection)

        self.tableWidget.resizeColumnsToContents()

    def change_table_temporal(self, plot_data_collect):

        plot_data_collection = plot_data_collect
        self.tableWidget.setRowCount(len(plot_data_collection))
        plot_count = data_count = 0
        data_names = []
        plot_data_collection.sort(key=lambda plot_data: (plot_data.identifiers))
        legend = self.get_table_header(plot_data_collection)
        header = legend[0]

        for plot_data in plot_data_collection:
            values = ((float(x), float(y)) for (x, y) in plot_data.values)

            sorted_value_pairs = sorted(values, key=lambda pair: pair[0])
            [xs, ys] = list(zip(*sorted_value_pairs))

            # make header
            if plot_data.identifiers[0] not in data_names:
                self.tableWidget.insertRow(plot_count)
                v_item = QtWidgets.QTableWidgetItem(str(plot_data.identifiers[0]))
                font = self.tableWidget.font()
                v_item.setData(6, QtGui.QFont(self.tableWidget.font().setBold(True)))
                v_item.setData(6, QtGui.QFont("Ubuntu", 11, QtGui.QFont.Bold))
                self.tableWidget.setVerticalHeaderItem(plot_count, v_item)
                header_count = plot_count
                data_names.append(plot_data.identifiers[0])
                plot_count += 1

            # round data
            if plot_data.label[1] == 'dB':
                ys = tuple(map(lambda i: round(i, 1), ys))

            self.tableWidget.horizontalHeader().setVisible(False)
            # fill up column per column
            for column_count in range(0, len(xs)):

                self.tableWidget.setCurrentCell(plot_count, column_count)
                if column_count > self.tableWidget.currentColumn():   self.tableWidget.insertColumn(column_count)
                self.tableWidget.setItem(plot_count, column_count, QtWidgets.QTableWidgetItem(str(ys[column_count])))
                self.tableWidget.setVerticalHeaderItem(plot_count, QtWidgets.QTableWidgetItem(str(header[data_count])+ " [" + str(plot_data.label[1]) + "] "))
                new_item = QtWidgets.QTableWidgetItem(str(xs[column_count]))
                new_item.setData(6, QtGui.QFont("Ubuntu", 11, QtGui.QFont.Bold))
                self.tableWidget.setItem(header_count, column_count, new_item)

                column_count += 1

            plot_count += 1
            data_count += 1

    def change_table_summary(self, plot_data_collect):

        plot_data_collection = plot_data_collect
        header_count = plot_count = data_count = config_count = column_saver = 0
        data_names = []
        plot_data_collection.sort(key=lambda plot_data: plot_data.path[-1])
        plot_data_collection.sort(key=lambda plot_data: plot_data.identifiers[0])
        legend = self.get_table_header(plot_data_collection)
        header = legend[0]
        config = legend[1]

        if ((config == []) | (len(config) == 1)):
            self.change_table_temporal(plot_data_collection)
            return

        self.tableWidget.setRowCount(len(plot_data_collection)/len(config))

        for plot_data in plot_data_collection:

            values = ((float(x), float(y)) for (x, y) in plot_data.values)

            sorted_value_pairs = sorted(values, key=lambda pair: pair[0])
            [xs, ys] = list(zip(*sorted_value_pairs))

            # make header, important if more than one plot
            if plot_data.identifiers[0] not in data_names:
                self.tableWidget.insertRow(plot_count)
                v_item = QtWidgets.QTableWidgetItem(str(plot_data.identifiers[0]))
                v_item.setData(6, QtGui.QFont("Ubuntu", 11, QtGui.QFont.Bold))
                self.tableWidget.setVerticalHeaderItem(plot_count, v_item)
                header_count = plot_count
                data_names.append(plot_data.identifiers[0])
                plot_count += 1

            # round data
            if plot_data.label[1] == 'dB':
                ys = tuple(map(lambda i: round(i, 1), ys))

            #horizontal header if more than one config
            if len(config) > 1: self.tableWidget.horizontalHeader().setVisible(True)
            else: self.tableWidget.horizontalHeader().setVisible(False)

            for column_count in range(0, len(xs)):

                columns = column_saver + column_count
                if (((column_saver+column_count) >= self.tableWidget.columnCount()) | (self.tableWidget.columnCount()==0) ):
                    self.tableWidget.insertColumn(column_saver + column_count)
                if plot_count >= self.tableWidget.rowCount():
                    self.tableWidget.insertRow(plot_count)
                # units in first row of table
                new_item = QtWidgets.QTableWidgetItem(plot_data.label[0] + ' | ' + plot_data.label[1])
                new_item.setData(6, QtGui.QFont("Ubuntu", 11, QtGui.QFont.Bold))
                self.tableWidget.setItem(header_count, column_saver + column_count, new_item)
                #self.tableWidget.setItem(header_count, column_saver + column_count, QtWidgets.QTableWidgetItem(plot_data.label[0] + ' | ' + plot_data.label[1]))
                # x and y-value in one cell
                self.tableWidget.setItem(plot_count, columns, QtWidgets.QTableWidgetItem(str(xs[column_count]) + ' | ' + str(ys[column_count])))
                # header
                self.tableWidget.setHorizontalHeaderItem(column_saver+column_count, QtWidgets.QTableWidgetItem(str(config[config_count])))
                column_count += 1

            if config[config_count] == header[data_count]: header[data_count] =  header[data_count].replace(config[config_count], plot_data.path[-1])
            elif config[config_count] in header[data_count]: header[data_count] = header[data_count].replace(config[config_count], '')

            self.tableWidget.setVerticalHeaderItem(plot_count, QtWidgets.QTableWidgetItem(str(header[data_count])))
            column_saver = column_saver + column_count
            config_count += 1

            plot_data_collection = plot_data_collection[1:]
            if plot_data.identifiers[0] not in list(map(lambda x: x.identifiers[0], plot_data_collection)):
                plot_count += 1
                column_saver = config_count = 0
            data_count += 1


    def update_bd_table(self, index):
        # update bd table, the index determines the anchor,
        # if it is non integer per default the first config is regarded as
        # anchor
        self.bdTableModel.update_table(self.combo_rate_psnr.currentText(),
                                       self.combo_interp.currentText(), index)

    def generate_new_curve(self):

        plot_data_collection = self.get_plot_data_collection_from_selected_variables()
        #plot_data = self.fuse_plot_data_collection(plot_data_collection)

        try: plot_data = self.fuse_plot_data_collection(plot_data_collection)
        except ValueError:
            return QtWidgets.QMessageBox.warning(self, "Warning!", "You didn't select at least 4 points.")

        if(len(plot_data.values) < 4):
                QtWidgets.QMessageBox.warning(self, "Warning!", "You didn't select at least 4 points.")

        else:
            curve_name, ok = QtWidgets.QInputDialog.getText(self, "New curve", "Please enter name of new curve. "
                                        "If you enter a name that is already existing, its data will be overwritten.")
            # curvelistview , thread needs to start here
            self.curve_window.show()
            self.curve_window.activateWindow()
            self.curve_window.curveListView.curveThread.add_items(curve_name, plot_data)
            self.curve_window.curveListView.curveThread.start()
            #self.curve_window.update(curve_name, plot_data)





    def fuse_plot_data_collection(self, plot_data_collection):

        if plot_data_collection:
            fused = plot_data_collection[0]

            for plot_data in plot_data_collection[1:]:
                fused.identifiers.extend(plot_data.identifiers)
                fused.values.extend(plot_data.values)
                fused.path.extend(plot_data.path)
                # todo label
            return fused

        else: raise ValueError


    def export_table_to_csv(self):
        # remember that the decimal mark is '.'
        if self.tableWidget.rowCount() > 0:
            path = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Table View as', '.', '*.csv')
            path = path[0] + path[1][1:]
            if len(path) > 0:
                with open(str(path), 'w', newline='') as stream:
                    writer = csv.writer(stream)
                    for row in range(self.tableWidget.rowCount()):
                        rowdata = []
                        rowdata.append(str(self.tableWidget.verticalHeaderItem(row).data(0))) #data(0) = data(Qt.displayRole)
                        for column in range(self.tableWidget.columnCount()):
                            item = self.tableWidget.item(row, column)
                            if item is not None:
                                rowdata.append(str(item.text()))
                            else:
                                rowdata.append('')
                        writer.writerow(rowdata)

    def save_bd_table(self):
        if self.bdTableModel.rowCount(self) == 0:
            return
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Table as', '.', 'tex')
        filename = '.'.join(filename)
        if not len(filename) == 0:
            self.bdTableModel.export_to_latex(filename)

    def on_combo_box(self):
        # just update the bd table but do not change the anchor
        self.update_bd_table(-1)

    def save_current_selection(self):
        """Saves the current selected sim data item collection"""
        if not self.get_selected_simulation_data_items():
            msg = QtWidgets.QMessageBox(self)  # use self as parent here
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setText("You did not select any simulation data item to store\n"
                        "Please make a selection and try again.")
            msg.setWindowTitle("Info")
            msg.show()
            return
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save RD data as', '.', '*.rd')
        filename = filename[0] + filename[1][1:]
        if not len(filename) == 0:
            f = open(filename, 'w')
            f.write(jsonpickle.encode(self.get_selected_simulation_data_items()))
            f.close()

    def process_cmd_line_args(self, args):
        """Processes cmd line arguments. Those are only pathes or files."""
        for path in args[1:]:
            if not isdir(path) and not isfile(path):
                continue
            if path.endswith('.rd'):
                f = open(path, 'r')
                json_str = f.read()
                sim_data_items = jsonpickle.decode(json_str)
                self.simDataItemTreeModel.update(sim_data_items)
                f.close()
                continue

            self.simDataItemTreeView.msg.show()
            self.simDataItemTreeView.parserThread.addPath(path)
            self.simDataItemTreeView.parserThread.start()

    def open_about_page(self):
        """Opens and displays an Html About file"""
        try:
            html_path = path.abspath(here + '/docs/about.html')
            html_file = open(html_path, 'r', encoding='utf-8', errors='ignore')
            source_code = html_file.read()
            app_version = '0.1.0'
            source_code = source_code.replace("##VERSION##", app_version)
            source_code = source_code.replace("##here##", here)
            about_dialog = QtWidgets.QDialog(self)
            about_dialog.setWindowTitle("About RDPlot")
            about_dialog.setMaximumSize(950, 800)
            about_text = QtWidgets.QTextBrowser(about_dialog)
            about_text.setMinimumWidth(950)
            about_text.setMinimumHeight(800)
            about_text.setHtml(source_code)
            about_text.setOpenExternalLinks(True)
            about_text.show()
            about_dialog.exec_()
            about_dialog.close()
            about_text.close()
        except IOError:
            html_error = QtWidgets.QMessageBox()
            html_error.setIcon(QtWidgets.QMessageBox.Critical)
            html_error.setText("Error opening about or help")
            html_error.setInformativeText("The html file from the resource could not be loaded.")
            html_error.exec_()
