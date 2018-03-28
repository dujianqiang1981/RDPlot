
from os import path
from os.path import sep, isfile, isdir
import csv

import pkg_resources
import jsonpickle
from PyQt5 import QtWidgets, QtGui
from PyQt5.Qt import Qt, QModelIndex, QItemSelectionModel
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.uic import loadUiType


#from rdplot.SimulationDataItem import dict_tree_from_sim_data_items
from rdplot.Widgets.PlotWidget import PlotWidget
from rdplot.model import OrderedDictModel
#from rdplot.Widgets.MainWindow import Ui_MainWindow, QMainWindow
from rdplot.view import NewCurveThread

Ui_curve_name = pkg_resources.resource_filename('rdplot', 'ui' + sep + 'curveWindow.ui')
Ui_CurveWindow, QMainWindow = loadUiType(Ui_curve_name)

here = pkg_resources.resource_filename('rdplot','')

# separate window for generated curves
class CurveWindow(QMainWindow, Ui_CurveWindow):
    def __init__(self):
        super(CurveWindow, self).__init__()
        self.setupUi(self)
        self.fig_dict = {}

        # PlotWidget as plotting device
        self.plotAreaVerticalLayout = QtWidgets.QVBoxLayout()
        self.plot.setLayout(self.plotAreaVerticalLayout)

        self.plotPreview = PlotWidget()
        self.plotAreaVerticalLayout.addWidget(self.plotPreview)

        # Create list model to store plot data for generated curves and connect it to view
        self.curveDataItemListModel = CurveListModel()
        self.curveListView.setModel(self.curveDataItemListModel)

        self.actionClose.triggered.connect(self.closeWindow)
        self._selection_model = QItemSelectionModel(self.curveListView.model())
        self.curveListView.setSelectionModel(self._selection_model)
        self._selection_model.selectionChanged.connect(self.update)
        #self.curveDataItemListModel.items_changed.connect(self.update)

    def update(self):
        self.plotPreview.ax.clear()
        #selected_data = self.get_selected_curve_data()
        select_data = self.get_plot_data_from_selection()
        plot_data, legend = [],[]
        for data in select_data:
            plot_data.append(data[0])
            legend.append(data[1])
        self.plotPreview.change_plot(plot_data, legend)


    #def get_selected_curve_data(self):
    #   return [[self.curveDataItemListModel[key], key] for key in self.curveDataItemListModel]

    def get_plot_data_from_selection(self):

        plot_data_collection = []
        for q_index in self.curveListView.selectedIndexes():
            key = q_index.data()
            plot_data_collection.append([self.curveDataItemListModel[key], key])

        return plot_data_collection

    def closeWindow(self):
        self.close()


class CurveListModel(OrderedDictModel): #aus model.py
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self._data = []

    #def rowCount(self, parent):
    #    return len(self._data)

    #def data(self, index, role): # in this the data for model view is stored
    #    if index.isValid() and role == Qt.DisplayRole:
    #        return QVariant(self._data[index.row()])
    #    else:
    #        return QVariant()

    def headerData(self, p_int, Qt_Orientation, int_role=None):
        pass

    def setData(self, data, int_role=None):
        self._data.append(data)

    def update_from_plot_data(self, curve_name, plot_data):

        key = curve_name
        item = plot_data
        #for key, item in plot_data:
        # If the key is already present, just update its item and continue
        if key in self:
                self._items[self._keys.index(key)] = item

        # Else search the insertion position by comparision
        else:
                index_insert = len(self)
                self.beginInsertRows(QModelIndex(), index_insert, index_insert + 1)
                self._keys.insert(index_insert, key)
                self._items.insert(index_insert, item)
                self.endInsertRows()

        self.items_changed.emit()
        # for index, key_other in enumerate(self):
        # If the key is bigger, then insert key/item here
        #    if self._compare_keys_function(key_other, key):
        #        index_insert = index
        #        break
