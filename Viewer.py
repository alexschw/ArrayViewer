"""
# Array Viewer
# View arrays from different sources in the viewer. Reshape them etc.
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
"""
import sys
import cPickle
from operator import getitem

import os.path
import re
import h5py
import scipy.io
import numpy as np
from PyQt4 import QtGui
from PyQt4.QtGui import QSizePolicy as QSP
from PyQt4.QtCore import QRect
from Charts import GraphWidget, ReshapeDialog, NewDataDialog

def filltoequal(lil):
    """ Fill a list of lists. Append smaller lists with nan """
    maxlen = max(map(len, lil))
    [[xi.append(np.nan) for _ in xrange(maxlen-len(xi))] for xi in lil]

def validate(data):
    """ Data validation. Replace lists of numbers with np.ndarray."""
    if isinstance(data, dict):
        # List of global variables (that should not be shown)
        glob = []
        for subdat in data:
            # global variables start with two underscores
            if subdat[:2] == "__":
                glob.append(subdat)
                continue
            # Run the validation again for each subelement in the dict
            data[subdat] = validate(data[subdat])
        # Remove global variables
        for g in glob:
            data.pop(g)
    elif isinstance(data, list):
        if data != [] and not isinstance(data[0], str):
            # not all elements in the list have the same length
            if isinstance(data[0], list) and len(set(map(len, data))) != 1:
                filltoequal(data)
            data = np.array(data)
    elif isinstance(data, scipy.io.matlab.mio5_params.mat_struct):
        # Create a dictionary from matlab structs
        dct = {}
        for key in data._fieldnames:
            exec("dct[key] = validate(data.%s)"%key)
        data = dct
    elif isinstance(data, np.ndarray) and data.dtype == "O":
        # Create numpy arrays from matlab cell types
        ndata = []
        for subdat in data:
            ndata.append(validate(subdat))
        data = np.array(ndata)
    elif not isinstance(data, (np.ndarray, int, float, str, unicode, tuple)):
        print "DataType ("+type(data)+") not recognized. Skipping"
        return None
    return data

class ViewerWindow(QtGui.QMainWindow):
    """ The main window of the array viewer """
    def __init__(self, parent=None):
        """ Initialize the window """
        super(self.__class__, self).__init__(parent)
            # set class variables
        self.keys = []
        self._data = {}
        self.cText = []
        self.reshapeBox = ReshapeDialog(self)
        self.newDataBox = NewDataDialog()

        # General Options
#        self.resize(800, 600)
        self.setWindowTitle("Array Viewer")

        CWgt = QtGui.QWidget(self)
        self.setCentralWidget(CWgt)
        vLayout = QtGui.QVBoxLayout(CWgt)

        # Get the general Frame/Box Structure
        QFra = QtGui.QFrame(CWgt)
        vLayout.addWidget(QFra)
        hLayout2 = QtGui.QHBoxLayout()
        hLayout3 = QtGui.QHBoxLayout()
        vLayout2 = QtGui.QVBoxLayout()
        hLayout = QtGui.QHBoxLayout(QFra)
        hLayout.addLayout(vLayout2)

        # Add the Tree Widget
        self.Tree = QtGui.QTreeWidget(QFra)
        self.Tree.setSizePolicy(QSP(QSP.Fixed, QSP.Expanding))
        self.Tree.headerItem().setText(0, "1")
        self.Tree.header().setVisible(False)
        self.Tree.currentItemChanged.connect(self.change_tree)
        vLayout2.addWidget(self.Tree)

        # Add the min and max labels
        self.txtMin = QtGui.QLabel(QFra)
        self.txtMin.setText("min : ")
        hLayout2.addWidget(self.txtMin)
        self.txtMax = QtGui.QLabel(QFra)
        self.txtMax.setText("max : ")
        hLayout2.addWidget(self.txtMax)
        vLayout2.addLayout(hLayout2)

        # Add the "Transpose"-Checkbox
        self.Transp = QtGui.QCheckBox(QFra)
        self.Transp.setText("Transpose")
        self.Transp.stateChanged.connect(self.draw_data)
        vLayout2.addWidget(self.Transp)

        # Add the Permute Field
        self.Prmt = QtGui.QLineEdit(QFra)
        self.Prmt.setText("")
        self.Prmt.setSizePolicy(QSP(QSP.Fixed, QSP.Fixed))
        hLayout3.addWidget(self.Prmt)
        self.PrmtBtn = QtGui.QPushButton(QFra)
        self.PrmtBtn.setText("Permute")
        self.PrmtBtn.released.connect(self.permute_data)
        hLayout3.addWidget(self.PrmtBtn)
        vLayout2.addLayout(hLayout3)

        # Add the Basic Graph Widget
        self.Graph = GraphWidget(QFra)
        self.Graph.setSizePolicy(QSP.Expanding, QSP.Expanding)
        hLayout.addWidget(self.Graph)

        self._initMenu()

        # Shape Widget
        self.Shape = QtGui.QGridLayout()
        for n in xrange(6):
            label = QtGui.QLabel()
            label.setText("0")
            label.hide()
            self.Shape.addWidget(label, 0, n, 1, 1)
            lineedit = QtGui.QLineEdit()
            lineedit.editingFinished.connect(self.draw_data)
            lineedit.hide()
            self.Shape.addWidget(lineedit, 1, n, 1, 1)
        vLayout.addLayout(self.Shape)

    def _initMenu(self):
        """ Setup the menu bar """
        menubar = QtGui.QMenuBar(self)
        menubar.setGeometry(QRect(0, 0, 800, 10))
        menuStart = QtGui.QMenu(menubar)
        menuStart.setTitle("Start")
        menubar.addAction(menuStart.menuAction())

        btnLoadData = QtGui.QAction(menubar)
        menuStart.addAction(btnLoadData)
        btnLoadData.setText("Load data")
        btnLoadData.setShortcut("Ctrl+O")
        btnLoadData.activated.connect(self.load_data_dialog)

        btnSave = QtGui.QAction(menubar)
        menuStart.addAction(btnSave)
        btnSave.setText("Save")
        btnSave.setShortcut("Ctrl+S")
        btnSave.activated.connect(self.save_chart)

        btnReshape = QtGui.QAction(menubar)
        menuStart.addAction(btnReshape)
        btnReshape.setText("Reshape")
        btnReshape.setShortcut("Ctrl+R")
        btnReshape.activated.connect(self.reshape_dialog)

        btnNewData = QtGui.QAction(menubar)
        menuStart.addAction(btnNewData)
        btnNewData.setText("New Data")
        btnNewData.setShortcut("Ctrl+N")
        btnNewData.activated.connect(self.new_data_dialog)

        menuGraph = QtGui.QMenu(menubar)
        menuGraph.setTitle("Graph")
        menubar.addAction(menuGraph.menuAction())
        self.setMenuBar(menubar)

        btnNewData = QtGui.QAction(menubar)
        menuGraph.addAction(btnNewData)
        btnNewData.setText("Colorbar")
        btnNewData.activated.connect(self.Graph.colorbar)

    def __getitem__(self, item):
        """ Gets the current data """
        if self._data == {}:
            return np.array(0)
        if item in [0, "data", ""]:
            return reduce(getitem, self.cText[:-1], self._data)[self.cText[-1]]
        else:
            return np.array(0)

    def __setitem__(self, _, newData):
        """ Sets the current data to the new data """
        if self._data == {}:
            return 0
        reduce(getitem, self.cText[:-1], self._data)[self.cText[-1]] = newData

    def add_data(self, fname):
        """ Add a new data to the dataset. Ask if the data already exists. """
        splitted = fname.split("/")
        folder = splitted[-2]
        filename = splitted[-1]
        key = str(folder + " - " + filename)
        # Show warning if data exists
        if self._data.has_key(key):
            msg = QtGui.QMessageBox()
            msg.setText("Data(%s) exists. Do you want to overwrite it?"%key)
            msg.setIcon(QtGui.QMessageBox.Warning)
            msg.setStandardButtons(QtGui.QMessageBox.No|QtGui.QMessageBox.Yes)
            msg.setDefaultButton(QtGui.QMessageBox.Yes)
            if msg.exec_() != QtGui.QMessageBox.Yes:
                return
            else:
                self.keys.remove(key)
        # Check if the File is bigger than 1 GB, than it will not be loaded
        if os.path.getsize(fname) > 4e9:
            print "File bigger than 4GB. Not loading!"
            return False
        # Load the different data types
        if fname[-5:] == '.hdf5':
            f = h5py.File(str(fname))
            data = dict([(n, np.array(f[n])) for n in f])
        elif fname[-4:] == '.mat':
            data = validate(scipy.io.loadmat(str(fname), squeeze_me=True,
                                             struct_as_record=False))
        elif fname[-4:] == '.npy':
            data = {'Value':np.load(open(str(fname)))}
        elif fname[-5:] == '.data':
            data = validate(cPickle.load(open(str(fname))))
        elif fname[-4:] == '.txt':
            lines = open(fname).readlines()
            numberRegEx = r'([-+]?\d+\.?\d*(?:[eE][-+]\d+)?)'
            lil = [re.findall(numberRegEx, line) for line in lines]
            data = {'Value':np.array(lil, dtype=float)}
        else:
            print 'File type not recognized!'
            return False

        self._data[key] = data
        self.keys.append(key)
        self.update_tree()

    def permute_data(self):
        """ Check the input in the permute box and reshape the array """
        content = str(self.Prmt.text()).strip("([])").replace(" ", "")
        chkstr = content.split(",")
        chkstr.sort()
        if chkstr != [str(_a) for _a in xrange(self[0].ndim)]:
            print "Shape is not matching dimensions. Aborting!"
            return
        new_order = tuple(np.array(content.split(","), dtype="i"))
        self[0] = np.transpose(self[0], new_order)
        self.update_shape(self[0].shape)
        print "Permuted to", self[0].shape

    def reshape_dialog(self):
        """ Open the reshape box to reshape the current data """
        self[0] = self.reshapeBox.reshape_array(self[0])
        self.update_shape(self[0].shape)

    def new_data_dialog(self):
        """ Open the new data dialog box to construct new data """
        key, _data = self.newDataBox.newData(self[0])
        if key == 1:
            self[0] = _data
            self.update_shape(self[0].shape)
        elif key != 0:
            self._data[key] = {"Value":_data}
            self.keys.append(key)
            self.update_tree()

    def load_data_dialog(self):
        """ Open file-dialog to choose one or multiple files. """
        ftypes = "(*.data *.hdf5 *.mat *.npy *.txt)"
        title = 'Open data file'
        fnames = QtGui.QFileDialog.getOpenFileNames(self, title, '.', ftypes)
        # For all files
        for fname in fnames:
            self.add_data(fname)

    def save_chart(self):
        """ Saves the currently shown chart as a file. """
        figure = self.Graph.figure()
        ftypes = 'Image file (*.png *.jpg);;PDF file (*.pdf)'
        if figure:
            fname = QtGui.QFileDialog.getSaveFileName(self, 'Save Image',
                                                      './figure.png', ftypes)
            if fname:
                figure.savefig(str(fname))

    def draw_data(self):
        """ Draw the selected data """
        shape = self.get_shape_str()
        if shape or self[0].shape == (1,):
            self.Graph.renewPlot(self[0], shape, self)

    def change_tree(self, current, previous):
        """ Draw chart, if the selection has changed """
        if current and current != previous and previous:
            self.Graph.clear()
            # Only bottom level nodes contain data -> skip if node has children
            if current.childCount() != 0:
                return 0
            # Get the currently selected FigureCanvasQTAggd data recursively
            self.cText = [str(current.text(0))]
            while current.parent() != None:
                current = current.parent()
                self.cText.insert(0, str(current.text(0)))
            # Update the shape widgets based on the datatype
            if isinstance(self[0], (int, float, str, unicode, list)):
                self.update_shape([0])
                self.Prmt.setText("")
            else:
                self.update_shape(self[0].shape)
                self.Prmt.setText(str(range(self[0].ndim)))
            self.draw_data()


    def get_shape_str(self):
        """ Get a shape string from the QLineEditWidgets """
        shapeStr = "["
        nNonScalar = 0 # number of non scalar values
        # For all (non-hidden) widgets
        for n in xrange(self.Shape.columnCount()):
            if self.Shape.itemAtPosition(1, n).widget().isHidden():
                break
            # Get the text and the maximum value within the dimension
            txt = self.Shape.itemAtPosition(1, n).widget().text()
            maxt = int(self.Shape.itemAtPosition(0, n).widget().text())
            if txt != "":
                if ":" in txt:
                    nNonScalar += 1
                elif int(txt) >= maxt:
                    txt = str(maxt - 1)
                    self.Shape.itemAtPosition(1, n).widget().setText(txt)
                elif int(txt) < -maxt:
                    txt = str(-maxt)
                    self.Shape.itemAtPosition(1, n).widget().setText(txt)
                shapeStr += txt+','
            else:
                shapeStr += ":,"
                nNonScalar += 1
        shapeStr = shapeStr[:-1]+"]"
        return shapeStr

    def update_shape(self, shape):
        """ Update the shape widgets in the window based on the new data """
        # Show a number of widgets equal to the dimension, hide the others
        for n in xrange(self.Shape.columnCount()):
            for m in xrange(self.Shape.rowCount()):
                wgt = self.Shape.itemAtPosition(m, n)
                if n < len(shape):
                    wgt.widget().show()
                else:
                    wgt.widget().hide()
        # Initialize the Values of those widgets. Could not be done previously
        for n in xrange(len(shape)):
            self.Shape.itemAtPosition(0, n).widget().setText(str(shape[n]))
            # Just show the first two dimensions in the beginning
            if n > 1:
                self.Shape.itemAtPosition(1, n).widget().setText("0")
            else:
                self.Shape.itemAtPosition(1, n).widget().clear()

    def update_tree(self):
        """ Add new data to TreeWidget """
        itemList = []
        for i in self.keys:
            item = QtGui.QTreeWidgetItem([i])
            for j in self._data[i].keys():
                item.addChild(QtGui.QTreeWidgetItem([j]))
            for j in xrange(item.childCount()):
                data = self._data[i][str(item.child(j).text(0))]
                if isinstance(data, dict):
                    for k in data.keys():
                        item.child(j).addChild(QtGui.QTreeWidgetItem([k]))
            itemList.append(item)
        self.Tree.clear()
        self.Tree.addTopLevelItems(itemList)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = ViewerWindow()
    window.show()
    app.exec_()
