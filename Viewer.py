#!/usr/bin/env python3
"""
# Array Viewer
# View arrays from different sources in the viewer. Reshape them etc.
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
"""
import sys
from functools import reduce
from operator import getitem

import os.path
from PyQt5.QtGui import QColor, QCursor, QIcon, QRegExpValidator
from PyQt5.QtWidgets import (QAction, QApplication, QCheckBox, QFileDialog,
                             QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QMainWindow, QMenu, QMenuBar,
                             QMessageBox, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)
from PyQt5.QtWidgets import QSizePolicy as QSP
from PyQt5.QtCore import pyqtSlot, QRect, QRegExp, Qt, QThread, QTimer
import numpy as np
from Charts import GraphWidget, ReshapeDialog, NewDataDialog
from Slider import rangeSlider
from Data import Loader


class ViewerWindow(QMainWindow):
    """ The main window of the array viewer. """
    def __init__(self, application=None, parent=None):
        """ Initialize the window. """
        super(self.__class__, self).__init__(parent)
        # set class variables
        self.app = application
        self.keys = []
        self._data = {}
        self.cText = []
        self.slices = {}
        self.checkableItems = []
        self.diffNo = 0
        self.maxDims = 6
        self.noPrintTypes = (int, float, str, type(u''), list, tuple)
        self.reshapeBox = ReshapeDialog(self)
        self.newDataBox = NewDataDialog()

        # set the loader from a separate class
        self.loader = Loader()
        self.loadThread = QThread()
        self.loader.doneLoading.connect(self.on_done_loading)
        self.loader.infoMsg.connect(self.infoMsg)
        self.loader.moveToThread(self.loadThread)
        self.loadThread.start()
        self.lMsg = 'loading...'
        self.emptylabel = QLabel()
        self.previous_opr_widget = self.emptylabel

        # General Options
        self.setWindowTitle("Array Viewer")

        CWgt = QWidget(self)
        self.setCentralWidget(CWgt)
        vLayout = QVBoxLayout(CWgt)

        # Get the general Frame/Box Structure
        QFra = QFrame(CWgt)
        vLayout.addWidget(QFra)
        grLayout = QGridLayout()
        hLayout = QHBoxLayout(QFra)
        hLayout.addLayout(grLayout)

        # Add the Tree Widget
        self.Tree = QTreeWidget(QFra)
        self.Tree.setSizePolicy(QSP(QSP.Fixed, QSP.Expanding))
        self.Tree.headerItem().setText(0, "")
        self.Tree.headerItem().setText(1, "")
        self.Tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.Tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.Tree.header().setStretchLastSection(False)
        self.Tree.header().setVisible(False)
        self.Tree.setColumnWidth(1, 10)
        self.Tree.setColumnHidden(1, True)
        self.Tree.currentItemChanged.connect(self.change_tree)
        grLayout.addWidget(self.Tree, 0, 0, 1, -1)
        self.Tree.contextMenuEvent = self.dropdown

        # Add a hidden Diff Button
        self.diffBtn = QPushButton(QFra)
        self.diffBtn.setText("Calculate the difference")
        self.diffBtn.released.connect(self.calc_diff)
        self.diffBtn.hide()
        grLayout.addWidget(self.diffBtn, 1, 0, 1, 2)

        # Add the min and max labels
        self.txtMin = QLabel(QFra)
        self.txtMin.setText("min : ")
        grLayout.addWidget(self.txtMin, 2, 0)
        self.txtMax = QLabel(QFra)
        self.txtMax.setText("max : ")
        grLayout.addWidget(self.txtMax, 2, 1)

        # Add the "Transpose"-Checkbox
        self.Transp = QCheckBox(QFra)
        self.Transp.setText("Transpose")
        self.Transp.stateChanged.connect(self.draw_data)
        grLayout.addWidget(self.Transp, 3, 0)

        # Add the "Plot2D"-Checkbox
        self.Plot2D = QCheckBox(QFra)
        self.Plot2D.setText("2D as plot")
        self.Plot2D.clicked.connect(lambda: self.checkboxes(True))
        self.Plot2D.stateChanged.connect(self.draw_data)
        grLayout.addWidget(self.Plot2D, 4, 0)

        # Add the "Min Mean Max"-Checkbox
        self.MMM = QCheckBox(QFra)
        self.MMM.setText("min-mean-max plot")
        self.MMM.clicked.connect(lambda: self.checkboxes(False))
        self.MMM.stateChanged.connect(self.draw_data)
        grLayout.addWidget(self.MMM, 4, 1)

        # Add the Permute Field
        self.Prmt = QLineEdit(QFra)
        self.Prmt.setText("")
        self.Prmt.setSizePolicy(QSP(QSP.Fixed, QSP.Fixed))
        self.Prmt.returnPressed.connect(self.permute_data)
        grLayout.addWidget(self.Prmt, 5, 0)
        self.PrmtBtn = QPushButton(QFra)
        self.PrmtBtn.setText("Permute")
        self.PrmtBtn.released.connect(self.permute_data)
        grLayout.addWidget(self.PrmtBtn, 5, 1)

        # Add the Basic Graph Widget
        self.Graph = GraphWidget(QFra)
        self.Graph.setSizePolicy(QSP.Expanding, QSP.Expanding)
        grLayout.addWidget(self.Graph, 0, 2, 0, 1)

        # Add the Color Slider
        self.Sldr = rangeSlider(QFra)
        self.Sldr.setSizePolicy(QSP.Fixed, QSP.Expanding)
        self.Sldr.sliderReleased.connect(self.update_colorbar)
        grLayout.addWidget(self.Sldr, 0, 3, 0, 1)

        # Add a context menu
        self.contextMenu = QMenu(self)
        delData = QAction(self.contextMenu)
        delData.setText("Delete Data")
        delData.triggered.connect(self.delete_data)
        self.contextMenu.addAction(delData)

        self._initMenu()

        # Shape Widget
        self.Shape = QGridLayout()
        self.Validator = QRegExpValidator(self)
        self.Validator.setRegExp(QRegExp("[+-]?\\d*(?::|:\+|:-|)\\d*(?::|:\+|:-|)\\d*"))
        for n in range(self.maxDims):
            label = QLabel()
            label.setText("0")
            label.hide()
            self.Shape.addWidget(label, 0, n, 1, 1)
            lineedit = QLineEdit()
            lineedit.setValidator(self.Validator)
            lineedit.editingFinished.connect(self.set_slice)
            lineedit.hide()
            self.Shape.addWidget(lineedit, 1, n, 1, 1)
        vLayout.addLayout(self.Shape)

        # Message Field
        self.errMsgTimer = QTimer(self)
        self.errMsg = QLabel("")
        grLayout.addWidget(self.errMsg, 5, 2)

    def _initMenu(self):
        """ Setup the menu bar. """
        menubar = QMenuBar(self)
        menubar.setGeometry(QRect(0, 0, 800, 10))
        menuStart = QMenu(menubar)
        menuStart.setTitle("Start")
        menubar.addAction(menuStart.menuAction())

        btnLoadData = QAction(menubar)
        menuStart.addAction(btnLoadData)
        btnLoadData.setText("Load data")
        btnLoadData.setShortcut("Ctrl+O")
        btnLoadData.triggered.connect(self.load_data_dialog)

        btnSave = QAction(menubar)
        menuStart.addAction(btnSave)
        btnSave.setText("Save")
        btnSave.setShortcut("Ctrl+S")
        btnSave.triggered.connect(self.save_chart)

        btnReshape = QAction(menubar)
        menuStart.addAction(btnReshape)
        btnReshape.setText("Reshape")
        btnReshape.setShortcut("Ctrl+R")
        btnReshape.triggered.connect(self.reshape_dialog)

        btnNewData = QAction(menubar)
        menuStart.addAction(btnNewData)
        btnNewData.setText("New Data")
        btnNewData.setShortcut("Ctrl+N")
        btnNewData.triggered.connect(self.new_data_dialog)

        btnNewData = QAction(menubar)
        menuStart.addAction(btnNewData)
        btnNewData.setText("Difference")
        btnNewData.setShortcut("Ctrl+D")
        btnNewData.triggered.connect(self.start_diff)

        btnDelAll = QAction(menubar)
        menuStart.addAction(btnDelAll)
        btnDelAll.setText("Delete All Data")
        btnDelAll.setShortcut("Ctrl+X")
        btnDelAll.triggered.connect(self.delete_all_data)

        # Graph menu
        menuGraph = QMenu(menubar)
        menuGraph.setTitle("Graph")
        menubar.addAction(menuGraph.menuAction())

        btnColorbar = QAction(menubar)
        menuGraph.addAction(btnColorbar)
        btnColorbar.setText("Colorbar")
        btnColorbar.triggered.connect(self.Graph.toggle_colorbar)

        menuGraph.addSeparator()

        btnCmJet = QAction(menubar)
        menuGraph.addAction(btnCmJet)
        btnCmJet.setText("Colormap 'jet'")
        btnCmJet.triggered.connect(lambda: self.Graph.colormap('jet'))

        btnCmGray = QAction(menubar)
        menuGraph.addAction(btnCmGray)
        btnCmGray.setText("Colormap 'gray'")
        btnCmGray.triggered.connect(lambda: self.Graph.colormap('gray'))

        btnCmHot = QAction(menubar)
        menuGraph.addAction(btnCmHot)
        btnCmHot.setText("Colormap 'hot'")
        btnCmHot.triggered.connect(lambda: self.Graph.colormap('hot'))

        btnCmBwr = QAction(menubar)
        menuGraph.addAction(btnCmBwr)
        btnCmBwr.setText("Colormap 'bwr'")
        btnCmBwr.triggered.connect(lambda: self.Graph.colormap('bwr'))

        btnCmViridis = QAction(menubar)
        menuGraph.addAction(btnCmViridis)
        btnCmViridis.setText("Colormap 'viridis'")
        btnCmViridis.triggered.connect(lambda: self.Graph.colormap('viridis'))

        # Operations menu
        menuOprs = QMenu(menubar)
        menuOprs.setTitle("Operations")
        menubar.addAction(menuOprs.menuAction())

        btnOpNone = QAction(menubar)
        menuOprs.addAction(btnOpNone)
        btnOpNone.setText("None")
        btnOpNone.triggered.connect(lambda: self.set_operation())

        btnOpMin = QAction(menubar)
        menuOprs.addAction(btnOpMin)
        btnOpMin.setText("Min")
        btnOpMin.triggered.connect(lambda: self.set_operation('min'))

        btnOpMean = QAction(menubar)
        menuOprs.addAction(btnOpMean)
        btnOpMean.setText("Mean")
        btnOpMean.triggered.connect(lambda: self.set_operation('mean'))

        btnOpMed = QAction(menubar)
        menuOprs.addAction(btnOpMed)
        btnOpMed.setText("Median")
        btnOpMed.triggered.connect(lambda: self.set_operation('median'))

        btnOpMax = QAction(menubar)
        menuOprs.addAction(btnOpMax)
        btnOpMax.setText("Max")
        btnOpMax.triggered.connect(lambda: self.set_operation('max'))

        self.setMenuBar(menubar)

    def __getitem__(self, item):
        """ Gets the current data. """
        if not self._data or not self.cText:
            return None
        if item in [0, "data", ""]:
            return reduce(getitem, self.cText[:-1], self._data)[self.cText[-1]]
        else:
            return reduce(getitem, item[:-1], self._data)[item[-1]]

    def __setitem__(self, _, newData):
        """ Sets the current data to the new data. """
        if not self._data:
            return 0
        reduce(getitem, self.cText[:-1], self._data)[self.cText[-1]] = newData

    def checkboxes(self, fromP2D):
        if self.Plot2D.checkState() and not fromP2D:
            self.Plot2D.setCheckState(0)
        elif self.MMM.checkState() and fromP2D:
            self.MMM.setCheckState(0)

    def get_obj_trace(self, item):
        """ Returns the trace to a given item in the TreeView. """
        dText = [str(item.text(0))]
        while item.parent() is not None:
            item = item.parent()
            dText.insert(0, str(item.text(0)))
        return dText

    def dropdown(self, _):
        """ Add a context menu. """
        if self.Tree.currentItem():
            self.contextMenu.popup(QCursor.pos())

    def set_operation(self, operation="None"):
        """ Make Dimension-titles (not) clickable and pass the operation. """
        for n in range(self.Shape.columnCount()):
            self.Shape.itemAtPosition(0, n).widget().setStyleSheet("")
            if operation == "None":
                self.Shape.itemAtPosition(0, n).widget().mousePressEvent \
                    = None
            else:
                self.Shape.itemAtPosition(0, n).widget().mousePressEvent \
                    = self.perform_operation
        self.previous_opr_widget = self.emptylabel
        oprdim = self.Graph.set_operation(operation)
        if oprdim != -1:
            prev_wid = self.Shape.itemAtPosition(0, oprdim).widget()
            prev_wid.setStyleSheet("background-color:lightgreen;")
        self.draw_data()

    def perform_operation(self, event):
        """ Perform the chosen Operation on the graph.
        If the field is clicked again the operation will be undone.
        """
        this_wgt = self.app.widgetAt(event.globalPos())
        self.previous_opr_widget.setStyleSheet("")
        if this_wgt == self.previous_opr_widget:
            self.Graph._oprdim = -1
            self.draw_data()
            self.previous_opr_widget = self.emptylabel
        else:
            this_wgt.setStyleSheet("background-color:lightgreen;")
            index = self.Shape.indexOf(this_wgt) // self.Shape.rowCount()
            self.Graph._oprdim = index
            self.draw_data()
            self.previous_opr_widget = this_wgt

    def delete_data(self):
        """ Delete the selected data. """
        citem = self.Tree.currentItem()
        if str(citem.text(0)) == self.lMsg:
            return
        dText = self.get_obj_trace(citem)
        citem = self.Tree.currentItem()
        del reduce(getitem, dText[:-1], self._data)[dText[-1]]
        if len(dText) == 1:
            self.keys.remove(dText[0])
        (citem.parent() or self.Tree.invisibleRootItem()).removeChild(citem)

    def delete_all_data(self):
        """ Delete all data from the Treeview. """
        txt = "Delete all data in the Array Viewer?"
        btns = (QMessageBox.Yes|QMessageBox.No)
        msg = QMessageBox(QMessageBox.Warning,
                                    "Warning", txt, buttons=btns)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec_() != QMessageBox.Yes:
            return
        else:
            del self._data
            del self.keys
            self._data = {}
            self.keys = []
            self.cText = []
            self.slices = {}
            self.update_tree()
            self.Graph.clear()

    @pyqtSlot(str, int)
    def infoMsg(self, text, wLevel):
        """ Show an info Message """
        if wLevel == -1:
            self.errMsg.setText(text)
            self.errMsg.setStyleSheet("QLabel { color : red; }")
        elif wLevel == 0:
            self.errMsg.setText(text)
            self.errMsg.setStyleSheet("QLabel { color : green; }")
        elif wLevel == 1:
            print(text)
        self.errMsgTimer.singleShot(2000, lambda: self.errMsg.setText(""))

    def start_diff(self):
        """ Start the diff view. """
        self.diffBtn.show()
        self.Tree.setColumnHidden(1, False)
        for item in self.checkableItems:
            item.setCheckState(1, Qt.Unchecked)

    def calc_diff(self):
        """ Calculate the difference and end the diff view. """
        checkedItems = 0
        for item in self.checkableItems:
            if item.checkState(1) == Qt.Checked:
                text = self.get_obj_trace(item)
                if checkedItems == 0:
                    text0 = '[0] ' + '/'.join(text)
                    item0 = self[text]
                else:
                    text1 = '[1] ' + '/'.join(text)
                    item1 = self[text]
                checkedItems += 1
        if checkedItems == 2 and item0.shape == item1.shape:
            self._data["Diff " + str(self.diffNo)] = {text0: item0,
                                                      text1: item1,
                                                      "~> Diff [0]-[1]":
                                                      item0 - item1}
            self.keys.append("Diff " + str(self.diffNo))
            self.diffNo += 1
            self.Tree.setColumnHidden(1, True)
            self.diffBtn.hide()
            self.update_tree()

    def slice_key(self):
        """ Return the slice key for the current dataset. """
        return '/'.join(self.cText)

    def load_slice(self):
        """ Returns the perviously seleced slice for the current array. """
        if not self._data:
            return None
        if self.slice_key() in self.slices:
            return self.slices[self.slice_key()]
        else:
            return None

    def set_slice(self):
        """ Get the current slice in the window and save it in a dict. """
        if isinstance(self[0], self.noPrintTypes):
            return
        curr_slice = []
        # For all (non-hidden) widgets
        for n in range(self.Shape.columnCount()):
            if self.Shape.itemAtPosition(1, n).widget().isHidden():
                break
            # Get the text and the maximum value within the dimension
            curr_slice.append(self.Shape.itemAtPosition(1, n).widget().text())
        self.slices[self.slice_key()] = curr_slice
        self.draw_data()

    @pyqtSlot(dict, str)
    def on_done_loading(self, data, key):
        """ Set the data into the global _data list once loaded. """
        key = str(key)
        if key != "":
            self._data[key] = data
            self.keys.append(key)
        self.update_tree()

    def permute_data(self):
        """ Check the input in the permute box and reshape the array. """
        content = str(self.Prmt.text()).strip("([])").replace(" ", "")
        chkstr = content.split(",")
        chkstr.sort()
        if chkstr != [str(_a) for _a in range(self[0].ndim)]:
            self.infoMsg("Shape is not matching dimensions. Aborting!", -1)
            return
        new_order = tuple(np.array(content.split(","), dtype="i"))
        self[0] = np.transpose(self[0], new_order)
        if self.slice_key() in self.slices:
            self.slices[self.slice_key()] = [
                self.slices[self.slice_key()][i] for i in new_order]
        self.update_shape(self[0].shape)
        self.infoMsg("Permuted to " + str(self[0].shape), 1)

    def reshape_dialog(self):
        """ Open the reshape box to reshape the current data. """
        self[0] = self.reshapeBox.reshape_array(self[0])
        if self.slice_key() in self.slices:
            del self.slices[self.slice_key()]
        self.update_shape(self[0].shape)

    def new_data_dialog(self):
        """ Open the new data dialog box to construct new data. """
        key, _data = self.newDataBox.newData(self[0], self.Graph.cutout)
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
        fnames = QFileDialog.getOpenFileNames(self, title, '.', ftypes)
        if fnames:
            # For all files
            if isinstance(fnames[0], list):
                fnames = fnames[0]
            for fname in fnames:
                # Check if the data already exists
                splitted = fname.split("/")
                key = str(splitted[-2] + " - " + splitted[-1])
                # Show warning if data exists
                if key in self.keys:
                    txt = "Data(%s) exists.\nDo you want to overwrite it?"%key
                    replaceBtn = QPushButton(QIcon.fromTheme("list-add"),
                                             "Add new Dataset")
                    msg = QMessageBox(QMessageBox.Warning, "Warning", txt)
                    yesBtn = msg.addButton(QMessageBox.Yes)
                    msg.addButton(QMessageBox.No)
                    msg.addButton(replaceBtn, QMessageBox.AcceptRole)
                    msg.setDefaultButton(QMessageBox.Yes)
                    msg.exec_()
                    cBtn = msg.clickedButton()
                    if cBtn == replaceBtn:
                        n = 1
                        while True:
                            if key + "_" + str(n) not in self.keys:
                                key =  key + "_" + str(n)
                                break
                            n += 1
                    elif cBtn != yesBtn:
                        return
                    else :
                        self.keys.remove(key)
                loadItem = QTreeWidgetItem([self.lMsg])
                loadItem.setForeground(0, QColor("grey"))
                self.Tree.addTopLevelItem(loadItem)
                self.loader.load.emit(fname, key)

    def save_chart(self):
        """ Saves the currently shown chart as a file. """
        figure = self.Graph.figure()
        ftyp = 'Image file (*.png *.jpg);;PDF file (*.pdf)'
        if figure:
            fname = QFileDialog.getSaveFileName(self, 'Save Image',
                                                          './figure.png', ftyp)
            if fname:
                figure.savefig(str(fname))

    def draw_data(self):
        """ Draw the selected data. """
        shape, scalarDims = self.get_shape_str()
        if shape or self[0].shape == (1,):
            self.Graph.renewPlot(self[0], shape, scalarDims, self)
            self.update_colorbar()

    def update_colorbar(self):
        """ Update the values of the colorbar according to the slider value."""
        self.Graph.colorbar(self.Sldr.value())

    def change_tree(self, current, previous):
        """ Draw chart, if the selection has changed. """
        if (current and current != previous and current.text(0) != self.lMsg):
            self.Graph._oprdim = -1
            self.Graph.clear()
            # Only bottom level nodes contain data -> skip if node has children
            if current.childCount() != 0:
                return 0
            # Get the currently selected FigureCanvasQTAggd data recursively
            self.cText = self.get_obj_trace(current)
            # Update the shape widgets based on the datatype
            if isinstance(self[0], self.noPrintTypes):
                self.update_shape([0], False)
                self.PrmtBtn.setEnabled(False)
            else:
                self.update_shape(self[0].shape)
                self.PrmtBtn.setEnabled(True)

    def get_shape_str(self):
        """ Get a shape string from the QLineEditWidgets. """
        shapeStr = "["
        scalarDims = []  # scalar Dimensions
        # For all (non-hidden) widgets
        for n in range(self.Shape.columnCount()):
            if self.Shape.itemAtPosition(1, n).widget().isHidden():
                break
            # Get the text and the maximum value within the dimension
            txt = self.Shape.itemAtPosition(1, n).widget().text()
            maxt = int(self.Shape.itemAtPosition(0, n).widget().text())
            if txt == "":
                shapeStr += ":,"
            elif ":" in txt:
                shapeStr += txt + ','
            else:
                scalarDims.append(n)
                if int(txt) >= maxt:
                    txt = str(maxt - 1)
                    self.Shape.itemAtPosition(1, n).widget().setText(txt)
                elif int(txt) < -maxt:
                    txt = str(-maxt)
                    self.Shape.itemAtPosition(1, n).widget().setText(txt)
                shapeStr += txt + ','

        shapeStr = shapeStr[:-1] + "]"
        return str(shapeStr), np.array(scalarDims)

    def update_shape(self, shape, load_slice=True):
        """ Update the shape widgets in the window based on the new data. """
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
            curr_slice = self.load_slice()
            self.Prmt.setText(str(list(range(self[0].ndim))))
        else:
            self.Prmt.setText("")
        for n, value in enumerate(shape):
            self.Shape.itemAtPosition(0, n).widget().setText(str(value))
            if load_slice and curr_slice:
                self.Shape.itemAtPosition(1, n).widget().setText(curr_slice[n])
            else:
                # Just show the first two dimensions in the beginning
                if n > 1:
                    self.Shape.itemAtPosition(1, n).widget().setText("0")
                else:
                    self.Shape.itemAtPosition(1, n).widget().clear()
        # Redraw the graph
        self.draw_data()

    def update_tree(self):
        """ Add new data to TreeWidget. """
        itemList = []
        self.checkableItems = []
        for i in self.keys:
            item = QTreeWidgetItem([i])
            for j in sorted(self._data[i].keys()):
                item.addChild(QTreeWidgetItem([j]))
            for j in range(item.childCount()):
                data = self._data[i][str(item.child(j).text(0))]
                if isinstance(data, dict):
                    for n, k in enumerate(list(data.keys())):
                        item.child(j).addChild(QTreeWidgetItem([k]))
                        if not isinstance(data[k], self.noPrintTypes):
                            cItem = item.child(j).child(n)
                            cItem.setCheckState(1, Qt.Unchecked)
                            self.checkableItems.append(cItem)
                elif not isinstance(data, self.noPrintTypes):
                    item.child(j).setCheckState(1, Qt.Unchecked)
                    self.checkableItems.append(item.child(j))
            itemList.append(item)
        self.Tree.clear()
        self.Tree.addTopLevelItems(itemList)

    def wheelEvent(self, event):
        onField = False
        from_wgt = self.app.widgetAt(event.globalPos())
        for n in range(self.maxDims):
            if self.Shape.itemAtPosition(1, n).widget() == from_wgt:
                onField = True
                break
        if onField:
            txt = from_wgt.text()
            modifiers = QApplication.keyboardModifiers()
            mod = np.sign(event.angleDelta().y())
            if modifiers == Qt.ControlModifier:
                mod *= 10
            elif modifiers == Qt.ShiftModifier:
                mod *= 100
            try:
                from_wgt.setText(str(int(txt)+mod))
            except ValueError:
                txt = txt.split(':')
                if len(txt) == 1:
                    return
                if len(txt) == 3 and txt[2] != "":
                    if modifiers == Qt.ControlModifier:
                        mod //= 10
                        mod *= int(txt[2])
                if txt[0] != "":
                    txt[0] = str(int(txt[0])+mod)
                if txt[1] != "":
                    txt[1] = str(int(txt[1])+mod)
                if "0" in txt:
                    txt = np.array(txt)
                    txt[txt == "0"] = ""
                from_wgt.setText(':'.join(txt))
            self.set_slice()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ViewerWindow(app)
    for new_file in sys.argv[1:]:
        window.loader.load.emit(os.path.abspath(new_file), "")
    window.show()
    sys.exit(app.exec_())
