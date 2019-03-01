#!/usr/bin/env python3
"""
# Array Viewer
# View arrays from different sources in the viewer. Reshape them etc.
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
"""
import sys
from operator import getitem

import os.path
import numpy as np
from PyQt4 import QtGui
from PyQt4.QtGui import QSizePolicy as QSP
from PyQt4.QtCore import QRect, QThread, pyqtSlot
from Charts import GraphWidget, ReshapeDialog, NewDataDialog
from Slider import rangeSlider
from Data import Loader

class ViewerWindow(QtGui.QMainWindow):
    """ The main window of the array viewer """
    def __init__(self, parent=None):
        """ Initialize the window """
        super(self.__class__, self).__init__(parent)
        # set class variables
        self.keys = []
        self._data = {}
        self.cText = []
        self.slices = {}
        self.reshapeBox = ReshapeDialog(self)
        self.newDataBox = NewDataDialog()

        # set the loader from a separate class
        self.loader = Loader()
        self.loadThread = QThread()
        self.loader.doneLoading.connect(self.on_done_loading)
        self.loader.moveToThread(self.loadThread)
        self.loadThread.start()
        self.lMsg = 'loading...'

        # General Options
        self.setWindowTitle("Array Viewer")

        CWgt = QtGui.QWidget(self)
        self.setCentralWidget(CWgt)
        vLayout = QtGui.QVBoxLayout(CWgt)

        # Get the general Frame/Box Structure
        QFra = QtGui.QFrame(CWgt)
        vLayout.addWidget(QFra)
        grLayout = QtGui.QGridLayout()
        hLayout = QtGui.QHBoxLayout(QFra)
        hLayout.addLayout(grLayout)

        # Add the Tree Widget
        self.Tree = QtGui.QTreeWidget(QFra)
        self.Tree.setSizePolicy(QSP(QSP.Fixed, QSP.Expanding))
        self.Tree.headerItem().setText(0, "1")
        self.Tree.header().setVisible(False)
        self.Tree.currentItemChanged.connect(self.change_tree)
        grLayout.addWidget(self.Tree, 0, 0, 1, -1)

        # Add the min and max labels
        self.txtMin = QtGui.QLabel(QFra)
        self.txtMin.setText("min : ")
        grLayout.addWidget(self.txtMin, 1, 0)
        self.txtMax = QtGui.QLabel(QFra)
        self.txtMax.setText("max : ")
        grLayout.addWidget(self.txtMax, 1, 1)

        # Add the "Transpose"-Checkbox
        self.Transp = QtGui.QCheckBox(QFra)
        self.Transp.setText("Transpose")
        self.Transp.stateChanged.connect(self.draw_data)
        grLayout.addWidget(self.Transp, 2, 0)

        # Add the "Plot2D"-Checkbox
        self.Plot2D = QtGui.QCheckBox(QFra)
        self.Plot2D.setText("Use plot for 2D graphs")
        self.Plot2D.stateChanged.connect(self.draw_data)
        grLayout.addWidget(self.Plot2D, 2, 1)

        # Add the Permute Field
        self.Prmt = QtGui.QLineEdit(QFra)
        self.Prmt.setText("")
        self.Prmt.setSizePolicy(QSP(QSP.Fixed, QSP.Fixed))
        grLayout.addWidget(self.Prmt, 3, 0)
        self.PrmtBtn = QtGui.QPushButton(QFra)
        self.PrmtBtn.setText("Permute")
        self.PrmtBtn.released.connect(self.permute_data)
        grLayout.addWidget(self.PrmtBtn, 3, 1)

        # Add the Basic Graph Widget
        self.Graph = GraphWidget(QFra)
        self.Graph.setSizePolicy(QSP.Expanding, QSP.Expanding)
        hLayout.addWidget(self.Graph)

        # Add the Color Slider
        self.Sldr = rangeSlider(QFra)
        self.Sldr.setSizePolicy(QSP.Fixed, QSP.Expanding)
        self.Sldr.sliderReleased.connect(self.update_colorbar)
        hLayout.addWidget(self.Sldr)

        self._initMenu()

        # Shape Widget
        self.Shape = QtGui.QGridLayout()
        for n in range(6):
            label = QtGui.QLabel()
            label.setText("0")
            label.hide()
            self.Shape.addWidget(label, 0, n, 1, 1)
            lineedit = QtGui.QLineEdit()
            lineedit.editingFinished.connect(self.set_slice)
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

        btnColorbar = QtGui.QAction(menubar)
        menuGraph.addAction(btnColorbar)
        btnColorbar.setText("Colorbar")
        btnColorbar.activated.connect(self.Graph.colorbar)

        menuGraph.addSeparator()

        btnCmJet = QtGui.QAction(menubar)
        menuGraph.addAction(btnCmJet)
        btnCmJet.setText("Colormap 'jet'")
        btnCmJet.activated.connect(lambda: self.Graph.colormap('jet'))

        btnCmGray = QtGui.QAction(menubar)
        menuGraph.addAction(btnCmGray)
        btnCmGray.setText("Colormap 'gray'")
        btnCmGray.activated.connect(lambda: self.Graph.colormap('gray'))

        btnCmHot = QtGui.QAction(menubar)
        menuGraph.addAction(btnCmHot)
        btnCmHot.setText("Colormap 'hot'")
        btnCmHot.activated.connect(lambda: self.Graph.colormap('hot'))

        btnCmBwr = QtGui.QAction(menubar)
        menuGraph.addAction(btnCmBwr)
        btnCmBwr.setText("Colormap 'bwr'")
        btnCmBwr.activated.connect(lambda: self.Graph.colormap('bwr'))

        btnCmViridis = QtGui.QAction(menubar)
        menuGraph.addAction(btnCmViridis)
        btnCmViridis.setText("Colormap 'viridis'")
        btnCmViridis.activated.connect(lambda: self.Graph.colormap('viridis'))

    def __getitem__(self, item):
        """ Gets the current data """
        if not self._data or not self.cText:
            return None
        if item in [0, "data", ""]:
            return reduce(getitem, self.cText[:-1], self._data)[self.cText[-1]]
        else:
            return None

    def __setitem__(self, _, newData):
        """ Sets the current data to the new data """
        if not self._data:
            return 0
        reduce(getitem, self.cText[:-1], self._data)[self.cText[-1]] = newData

    def slice_key(self):
        """ Return the slice key for the current dataset """
        return '/'.join(self.cText)

    def load_slice(self):
        """ Returns the perviously seleced slice for the current array """
        if not self._data:
            return None
        if self.slice_key() in self.slices:
            return self.slices[self.slice_key()]
        else:
            return None

    def set_slice(self):
        """ Get the current slice in the window and save it in a dict. """
        if isinstance(self[0], (int, float, str, unicode, list)):
            return
        curr_slice = []
        # For all (non-hidden) widgets
        for n in range(self.Shape.columnCount()):
            if self.Shape.itemAtPosition(1, n).widget().isHidden():
                break
            # Get the text and the maximum value within the dimension
            curr_slice.append(self.Shape.itemAtPosition(1, n).widget().text())
        self.slices[self.slice_key()] = curr_slice

    @pyqtSlot(dict, str)
    def on_done_loading(self, data, key):
        """ Set the data into the global _data list once loaded. """
        key = str(key)
        if key != "":
            self._data[key] = data
            self.keys.append(key)
        self.update_tree()

    def permute_data(self):
        """ Check the input in the permute box and reshape the array """
        content = str(self.Prmt.text()).strip("([])").replace(" ", "")
        chkstr = content.split(",")
        chkstr.sort()
        if chkstr != [str(_a) for _a in range(self[0].ndim)]:
            print("Shape is not matching dimensions. Aborting!")
            return
        new_order = tuple(np.array(content.split(","), dtype="i"))
        self[0] = np.transpose(self[0], new_order)
        if self.slice_key() in self.slices:
           self.slices[self.slice_key()] = [
                   self.slices[self.slice_key()][i] for i in new_order]
        self.update_shape(self[0].shape)
        print("Permuted to", self[0].shape)

    def reshape_dialog(self):
        """ Open the reshape box to reshape the current data """
        self[0] = self.reshapeBox.reshape_array(self[0])
        if self.slice_key() in self.slices:
           del self.slices[self.slice_key()]
        self.update_shape(self[0].shape)

    def new_data_dialog(self):
        """ Open the new data dialog box to construct new data """
        key, _data = self.newDataBox.newData(self[0])
        if key == 1:
            self[0] = _data
            self.update_shape(self[0].shape)
        elif key != 0:
            self._data[key] = {"Value": _data}
            self.keys.append(key)
            self.update_tree()

    def load_data_dialog(self):
        """ Open file-dialog to choose one or multiple files. """
        ftypes = "(*.data *.hdf5 *.mat *.npy *.txt)"
        title = 'Open data file'
        fnames = QtGui.QFileDialog.getOpenFileNames(self, title, '.', ftypes)
        if fnames:
            loadItem = QtGui.QTreeWidgetItem([self.lMsg])
            loadItem.setForeground(0, QtGui.QColor("grey"))
            self.Tree.addTopLevelItem(loadItem)
            # For all files
            for fname in fnames:
                self.loader.load.emit(fname)

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

    def update_colorbar(self):
        """ Update the values of the colorbar according to the slider value """
        self.Graph.colorbar(self.Sldr.value())

    def change_tree(self, current, previous):
        """ Draw chart, if the selection has changed """
        if (current and current != previous and previous and
            current.text(0) != self.lMsg):
            self.Graph.clear()
            # Only bottom level nodes contain data -> skip if node has children
            if current.childCount() != 0:
                return 0
            # Get the currently selected FigureCanvasQTAggd data recursively
            self.cText = [str(current.text(0))]
            while current.parent() is not None:
                current = current.parent()
                self.cText.insert(0, str(current.text(0)))
            # Update the shape widgets based on the datatype
            if isinstance(self[0], (int, float, str, unicode, list)):
                self.update_shape([0], False)
                self.PrmtBtn.setEnabled(False)
            else:
                self.update_shape(self[0].shape)
                self.PrmtBtn.setEnabled(True)
            self.draw_data()

    def get_shape_str(self):
        """ Get a shape string from the QLineEditWidgets """
        shapeStr = "["
        nNonScalar = 0  # number of non scalar values
        # For all (non-hidden) widgets
        for n in range(self.Shape.columnCount()):
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
                shapeStr += txt + ','
            else:
                shapeStr += ":,"
                nNonScalar += 1
        shapeStr = shapeStr[:-1] + "]"
        return shapeStr

    def update_shape(self, shape, load_slice=True):
        """ Update the shape widgets in the window based on the new data """
        # Show a number of widgets equal to the dimension, hide the others
        for n in range(self.Shape.columnCount()):
            for m in range(self.Shape.rowCount()):
                wgt = self.Shape.itemAtPosition(m, n)
                if n < len(shape):
                    wgt.widget().show()
                else:
                    wgt.widget().hide()
        # Initialize the Values of those widgets. Could not be done previously
        if load_slice:
            curr_slice=self.load_slice()
            self.Prmt.setText(str(list(range(self[0].ndim))))
        else:
            self.Prmt.setText("")
        for n in range(len(shape)):
            self.Shape.itemAtPosition(0, n).widget().setText(str(shape[n]))
            if load_slice and curr_slice:
                self.Shape.itemAtPosition(1, n).widget().setText(curr_slice[n])
            else:
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
            for j in sorted(self._data[i].keys()):
                item.addChild(QtGui.QTreeWidgetItem([j]))
            for j in range(item.childCount()):
                data = self._data[i][str(item.child(j).text(0))]
                if isinstance(data, dict):
                    for k in list(data.keys()):
                        item.child(j).addChild(QtGui.QTreeWidgetItem([k]))
            itemList.append(item)
        self.Tree.clear()
        self.Tree.addTopLevelItems(itemList)


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = ViewerWindow()
    for new_file in sys.argv[1:]:
        window.loader.load.emit(os.path.abspath(new_file))
    window.show()
    sys.exit(app.exec_())
