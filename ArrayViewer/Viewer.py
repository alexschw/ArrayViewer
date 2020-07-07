#!/usr/bin/env python3
"""
Base Script of the Array Viewer
"""
# View arrays from different sources in the viewer. Reshape them etc.
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>

import sys
from functools import reduce
from operator import getitem
from configparser import ConfigParser, MissingSectionHeaderError

import os.path
from natsort import realsorted
from PyQt5.QtGui import QColor, QCursor, QIcon
from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication, QCheckBox,
                             QFileDialog, QGridLayout, QLabel, QLineEdit,
                             QMainWindow, QMenu, QMenuBar, QMessageBox,
                             QPushButton, QTreeWidgetItem, QWidget)
from PyQt5.QtWidgets import QSizePolicy as QSP
from PyQt5.QtCore import pyqtSlot, Qt, QThread, QTimer
import numpy as np
from ArrayViewer.Charts import GraphWidget, ReshapeDialog, NewDataDialog
from ArrayViewer.Slider import rangeSlider
from ArrayViewer.Data import Loader, h5py
from ArrayViewer.Style import dark_qpalette
from ArrayViewer.DataTree import DataTree
from ArrayViewer.Shape import ShapeSelector

def _menu_opt(menu, text, function, shortcut=None, act_grp=None):
    """ Build a new menu option. """
    btn = QAction(menu)
    btn.setText(text)
    btn.triggered.connect(function)
    if shortcut:
        btn.setShortcut(shortcut)
    if act_grp:
        btn.setActionGroup(act_grp)
        btn.setCheckable(True)
    menu.addAction(btn)
    return btn


class ViewerWindow(QMainWindow):
    """ The main window of the array viewer. """
    def __init__(self, application=None, config=None, parent=None):
        """ Initialize the window. """
        super(ViewerWindow, self).__init__(parent)
        # set class variables
        if sys.platform.startswith('linux') or \
           sys.platform.startswith('darwin'): # TODO Windows Icon Location
            folder = os.path.expanduser("~/.local/share/icons/")
            self.setWindowIcon(QIcon(os.path.join(folder, 'aview_logo.svg')))
        self.app = application
        self.config = config
        self._data = {}
        self.slices = {}
        self.cText = []
        self.keys = []
        self.diffNo = 0
        self.noPrintTypes = (int, float, str, type(u''), list, tuple)
        self.reshapeBox = ReshapeDialog(self)
        self.newDataBox = NewDataDialog()

        # set the loader from a separate class
        self.loader = Loader()
        self.loadThread = QThread()
        self.loader.doneLoading.connect(self.on_done_loading)
        self.loader.infoMsg.connect(self.info_msg)
        self.loader.moveToThread(self.loadThread)
        self.loadThread.start()
        self.lMsg = 'loading...'
        self.emptylabel = QLabel()
        self.previous_opr_widget = self.emptylabel

        # General Options
        self.setWindowTitle("Array Viewer")
        self.app.setStyle("Fusion")

        self.__addWidgets()

        # Initialize the menu
        self.__initMenu()

    def __addWidgets(self):
        """ Add the widgets in the main Window. """
        # Create the general Structure
        CWgt = QWidget(self)
        self.setCentralWidget(CWgt)
        grLayout = QGridLayout(CWgt)

        # Add the Tree Widgets
        self.datatree = DataTree(self, CWgt)
        grLayout.addWidget(self.datatree, 0, 0, 1, 2)

        # Add a hidden Diff Button
        self.diffBtn = QPushButton("Calculate the difference", CWgt)
        self.diffBtn.released.connect(self._calc_diff)
        self.diffBtn.hide()
        grLayout.addWidget(self.diffBtn, 1, 0, 1, 2)

        # Add the min and max labels
        self.txtMin = QLabel("min : ", CWgt)
        grLayout.addWidget(self.txtMin, 2, 0)
        self.txtMax = QLabel("max : ", CWgt)
        grLayout.addWidget(self.txtMax, 2, 1)

        # Add the "Transpose"-Checkbox
        self.Transp = QCheckBox("Transpose", CWgt)
        self.Transp.stateChanged.connect(self._draw_data)
        grLayout.addWidget(self.Transp, 3, 0, 1, 2)

        # Add the Permute Field
        self.Prmt = QLineEdit("", CWgt)
        self.Prmt.setSizePolicy(QSP(QSP.Fixed, QSP.Fixed))
        self.Prmt.returnPressed.connect(self._permute_data)
        grLayout.addWidget(self.Prmt, 4, 0)
        self.PrmtBtn = QPushButton("Permute", CWgt)
        self.PrmtBtn.released.connect(self._permute_data)
        grLayout.addWidget(self.PrmtBtn, 4, 1)

        # Add the Basic Graph Widget
        self.Graph = GraphWidget(self)
        self.Graph.setSizePolicy(QSP.Expanding, QSP.Expanding)
        grLayout.addWidget(self.Graph, 0, 2, 4, 1)

        # Message Field
        self.errMsgTimer = QTimer(self)
        self.errMsg = QLabel("", CWgt)
        grLayout.addWidget(self.errMsg, 4, 2)

        # Add the Color Slider
        self.Sldr = rangeSlider(CWgt)
        self.Sldr.setSizePolicy(QSP.Fixed, QSP.Expanding)
        self.Sldr.sliderReleased.connect(self._update_colorbar)
        grLayout.addWidget(self.Sldr, 0, 3, 5, 1)

        # Shape Widget
        self.Shape = ShapeSelector(self)
        grLayout.addWidget(self.Shape, 5, 0, 1, 4)


    def __initMenu(self):
        """ Setup the menu bar. """
        menu = QMenuBar(self)
        menuStart = QMenu("Start", menu)
        menu.addAction(menuStart.menuAction())

        _menu_opt(menuStart, "Load data", self._dlg_load_data, "Ctrl+O")
        _menu_opt(menuStart, "Save", self._save_chart, "Ctrl+S")
        _menu_opt(menuStart, "New Data", self._dlg_new_data, "Ctrl+N")
        _menu_opt(menuStart, "Reshape", self._dlg_reshape, "Ctrl+R")
        _menu_opt(menuStart, "Difference", self._start_diff, "Ctrl+D")
        _menu_opt(menuStart, "Delete All Data", self._delete_all_data,
                  "Ctrl+X")

        # Graph menu
        menuGraph = QMenu("Graph", menu)
        menu.addAction(menuGraph.menuAction())

        _menu_opt(menuGraph, "Colorbar", self._add_colorbar).setCheckable(True)
        menuGraph.addSeparator()

        ag_cm = QActionGroup(self)
        _menu_opt(menuGraph, "Colormap 'jet'",
                  lambda: self.Graph.colormap('jet'), act_grp=ag_cm)
        _menu_opt(menuGraph, "Colormap 'gray'",
                  lambda: self.Graph.colormap('gray'), act_grp=ag_cm)
        _menu_opt(menuGraph, "Colormap 'hot'",
                  lambda: self.Graph.colormap('hot'), act_grp=ag_cm)
        _menu_opt(menuGraph, "Colormap 'bwr'",
                  lambda: self.Graph.colormap('bwr'), act_grp=ag_cm)
        _menu_opt(menuGraph, "Colormap 'viridis'",
                  lambda: self.Graph.colormap('viridis'),
                  act_grp=ag_cm).setChecked(True)

        # Operations menu
        menuOpr = QMenu("Operations", menu)
        menu.addAction(menuOpr.menuAction())

        ag_op = QActionGroup(self)
        _menu_opt(menuOpr, "None", lambda: self.Shape.set_operation('None'),
                  act_grp=ag_op).setChecked(True)
        _menu_opt(menuOpr, "Min", lambda: self.Shape.set_operation('min'),
                  act_grp=ag_op)
        _menu_opt(menuOpr, "Mean", lambda: self.Shape.set_operation('mean'),
                  act_grp=ag_op)
        _menu_opt(menuOpr, "Median",
                  lambda: self.Shape.set_operation('median'), act_grp=ag_op)
        _menu_opt(menuOpr, "Max", lambda: self.Shape.set_operation('max'),
                  act_grp=ag_op)


        # Plot menu
        menuPlot = QMenu("Plot", menu)
        menu.addAction(menuPlot.menuAction())
        ag_plt = QActionGroup(self)
        ag_plt.setExclusive(False)
        self.MMM = _menu_opt(menuPlot, "min-mean-max plot",
                             lambda: self._checkboxes(0), act_grp=ag_plt)
        self.MMM.triggered.connect(self._draw_data)
        self.Plot2D = _menu_opt(menuPlot, "2D as plot",
                                lambda: self._checkboxes(1), act_grp=ag_plt)
        self.Plot2D.triggered.connect(self._draw_data)
        self.PlotScat = _menu_opt(menuPlot, "2D as Scatter",
                                  lambda: self._checkboxes(2), act_grp=ag_plt)
        self.PlotScat.triggered.connect(self._draw_data)
        self.Plot3D = _menu_opt(menuPlot, "3D as RGB", self._draw_data,
                                act_grp=ag_plt)
        self.PrintFlat = _menu_opt(menuPlot, "Print Values as text",
                                   self._draw_data, act_grp=ag_plt)
        menuPlot.addSeparator()
        _menu_opt(menuPlot, "Keep Slice on data change", self._set_fixate_view,
                  act_grp=ag_plt)
        dm = _menu_opt(menuPlot, "Dark Window mode", self._set_dark_mode,
                       act_grp=ag_plt)
        if self.config.getboolean('opt', 'darkmode'):
            dm.setChecked(True)
            self._set_dark_mode(True)
        self.setMenuBar(menu)

        # Add a context menu
        self.contextMenu = QMenu(self)
        _menu_opt(self.contextMenu, "Rename", self.datatree.rename_key)
        _menu_opt(self.contextMenu, "Reshape", self._dlg_reshape)
        self.combine_opt = _menu_opt(self.contextMenu, "Combine Dataset",
                                     self._dlg_combine)
        _menu_opt(self.contextMenu, "Delete Data", self._delete_data)

    def get(self, item):
        """ Gets the current data. """
        if item in [0, "data", ""]:
            item = self.cText
        if not self._data or not item:
            return []
        try:
            return reduce(getitem, item[:-1], self._data)[item[-1]]
        except KeyError:
            return []

    def set_data(self, newkey, newData, *_):
        """ Sets the current data to the new data. """
        if not self._data:
            return
        if newkey in [0, "data", ""]:
            newkey = self.cText
        reduce(getitem, newkey[:-1], self._data)[newkey[-1]] = newData

    def _add_colorbar(self):
        """ Add a colorbar to the Graph Widget. """
        self.Graph.toggle_colorbar()
        self.Sldr.set_enabled(self.Graph.has_cb)
        self._update_colorbar()

    def _calc_diff(self):
        """ Calculate the difference and end the diff view. """
        checkedItems = 0
        for item in self.datatree.checkableItems:
            if item.checkState(1) == Qt.Checked:
                text = self._get_obj_trace(item)
                if checkedItems == 0:
                    text0 = '[0] ' + '/'.join(text)
                    item0 = self.get(text)
                else:
                    text1 = '[1] ' + '/'.join(text)
                    item1 = self.get(text)
                checkedItems += 1
        if checkedItems == 2 and item0.shape == item1.shape:
            self._data["Diff " + str(self.diffNo)] = {text0: item0,
                                                      text1: item1,
                                                      "~> Diff [0]-[1]":
                                                      item0 - item1}
            self.keys.append("Diff " + str(self.diffNo))
            self.diffNo += 1
            self.datatree.currentWidget().setColumnHidden(1, True)
            self.diffBtn.hide()
            self.datatree.update_tree()

    def _change_tree(self, current, previous):
        """ Draw chart, if the selection has changed. """
        if (current and current != previous and current.text(0) != self.lMsg):
            self.Graph.set_oprdim(-1)
            self.Graph.clear()
            # Only bottom level nodes contain data -> skip if node has children
            if current.childCount() != 0:
                return
            # Get the currently selected FigureCanvasQTAggd data recursively
            self.cText = self._get_obj_trace(current)
            # Update the shape widgets based on the datatype
            if isinstance(self.get(0), self.noPrintTypes):
                self.Shape.update_shape([0], False)
                self.PrmtBtn.setEnabled(False)
            else:
                self.Shape.update_shape(self.get(0).shape)
                self.PrmtBtn.setEnabled(True)

    def _checkboxes(self, fromCheckbox):
        """ Validate the value of the checkboxes and toggle their values. """
        if fromCheckbox == 0:
            self.Plot2D.setChecked(False)
            self.PlotScat.setChecked(False)
        elif fromCheckbox == 1:
            self.MMM.setChecked(False)
            self.PlotScat.setChecked(False)
        elif fromCheckbox == 2:
            self.MMM.setChecked(False)
            self.Plot2D.setChecked(False)

    def _delete_all_data(self):
        """ Delete all data from the Treeview. """
        txt = "Delete all data in the Array Viewer?"
        btns = (QMessageBox.Yes|QMessageBox.No)
        msg = QMessageBox(QMessageBox.Warning, "Warning", txt, buttons=btns)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec_() != QMessageBox.Yes:
            return
        del self._data
        del self.keys
        self._data = {}
        self.diffNo = 0
        self.keys = []
        self.cText = []
        self.slices = {}
        self.datatree.clear_tree()
        self.Graph.clear()

    def _dropdown(self, _):
        """ Add a context menu. """
        if self.datatree.current_item():
            if str(self.datatree.current_item().text(0)) == self.lMsg:
                return
            self.combine_opt.setVisible(
                self.datatree.current_item().childCount() != 0)
            self.contextMenu.popup(QCursor.pos())

    def _delete_data(self):
        """ Delete the selected data. """
        citem = self.datatree.current_item()
        if str(citem.text(0)) == self.lMsg:
            return
        dText = self._get_obj_trace(citem)
        citem = self.datatree.current_item()
        del reduce(getitem, dText[:-1], self._data)[dText[-1]]
        if len(dText) == 1:
            self.keys.remove(dText[0])
        self.datatree.remove_from_checkables(citem.takeChildren())
        (citem.parent() or self.datatree.root).removeChild(citem)

    def _dlg_combine(self):
        """ Open a dialog to combine the dataset. """
        trace = self._get_obj_trace(self.datatree.current_item())
        data = self.get(trace)
        keys = realsorted(data, key=lambda x: x.lower())
        d0 = data.get(keys[0])
        npt = self.noPrintTypes + (dict,)
        # Search for occurences of arrays with the same shape as the first one
        if isinstance(d0, npt):
            n_keys = [k for k in keys if isinstance(data.get(k), type(d0))]
            data_shape = ()
        else:
            n_keys = []
            for k in keys:
                if not isinstance(data.get(k), npt):
                    if data.get(k).shape == d0.shape:
                        n_keys.append(k)
            data_shape = data.get(n_keys[0]).shape
        # Show a dialog asking if the conversion should be done.
        if len(data_shape) > 1:
            txt = "Combine the first {} datasets of {} element(s) into one?"
            txt = txt.format(len(n_keys), data_shape)
        else:
            txt = "Combine {} elements into 1D vector?".format(len(n_keys))
        btns = (QMessageBox.Yes|QMessageBox.No)
        msg = QMessageBox(QMessageBox.Information, "Info", txt, buttons=btns)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec_() != QMessageBox.Yes:
            return
        # Add 'combined' if not all values are combined or it is a topLevelItem
        if len(n_keys) != len(keys) or len(trace) == 1:
            trace.append('combined')
        # Perform the combination
        try:
            self.set_data(trace, np.array([data.get(k) for k in n_keys]))
        except ValueError:
            # For h5py dictionaries
            self.set_data(trace, np.array([data.get(k)[()] for k in n_keys]))
        # Remove the combined data
        if len(n_keys) != len(keys) and len(data_shape) > 1:
            _ = [self.get(trace[:-1]).pop(key) for key in n_keys]
        # Put new dimension at the end and remove singleton dimensions.
        self.set_data(trace, np.moveaxis(self.get(trace), 0, -1).squeeze())
        self.datatree.update_tree()

    def _dlg_load_data(self):
        """ Open file-dialog to choose one or multiple files. """
        FD = QFileDialog(self, 'Open data file', '.',
                         """Raw data (*.data *.hdf5 *.mat *.npy *.txt);;
                          Images (*.jpg *.bmp *.png *.tiff);;
                          All (*)""")
        FD.setOptions(QFileDialog.DontUseNativeDialog)
        FD.setFileMode(QFileDialog.ExistingFiles)
        checkbox = QCheckBox("Put first dimension to the end", FD)
        checkbox.setChecked(self.config.getboolean('opt', 'first_to_last'))
        FD.layout().addWidget(checkbox, 4, 1, 1, 1)
        if FD.exec_():
            fnames = FD.selectedFiles()
            self.config.set('opt', 'first_to_last',
                            str(checkbox.checkState() != 0))
            # For all files
            if isinstance(fnames[0], list):
                fnames = fnames[0]
            self.load_files(fnames)

    def _dlg_new_data(self):
        """ Open the new data dialog box to construct new data. """
        key, _data = self.newDataBox.new_data(self.get(0), self.Graph.cutout)
        if key == 1:
            self.set_data(0, _data)
            self.Shape.update_shape(self.get(0).shape)
        elif key != 0:
            self._data[key] = {"Value": _data}
            self.keys.append(key)
            self.datatree.update_tree()

    def _dlg_reshape(self):
        """ Open the reshape box to reshape the current data. """
        cTree = self.datatree.currentWidget()  # The current Tree
        if cTree.currentItem().childCount() != 0:
            # If the current item has children try to reshape all of them
            tr = self._get_obj_trace(cTree.currentItem())
            if self.datatree.is_files_tree():
                keys = [tr + [k] for k in self.datatree.similar_items
                        if isinstance(self.get(tr + [k]),
                                      (np.ndarray, h5py._hl.dataset.Dataset))]
            else:
                keys = [[k] + tr for k in self.datatree.similar_items
                        if isinstance(self.get([k] + tr),
                                      (np.ndarray, h5py._hl.dataset.Dataset))]
            if len(keys) == 0:
                return
            # All data must have the same number of elements
            datalen = [np.prod(self.get(k).shape) for k in keys]
            if np.any(datalen - datalen[0]):
                self.info_msg("Shape is not equal in data. Aborting!", -1)
                return
            # Reshape the first using the dialog
            newdata, s = self.reshapeBox.reshape_array(self.get(keys[0]))
            self.set_data(keys[0], newdata)
            # All further data will be reshaped accordingly
            if s is not None:
                for k in keys[1:]:
                    self.set_data(k, np.reshape(self.get(k), s))
        elif isinstance(self.get(0), (np.ndarray, h5py._hl.dataset.Dataset)):
            # If just one is chosen and has a numpy compatible type, reshape it
            self.set_data(0, *self.reshapeBox.reshape_array(self.get(0)))
            if self._slice_key() in self.slices:
                del self.slices[self._slice_key()]
        else:
            return
        self.Shape.update_shape(self.get(0).shape)

    def _draw_data(self):
        """ Draw the selected data. """
        shapeStr, scalarDims = self.Shape.get_shape()
        if shapeStr or self.get(0).shape == (1,):
            self.Graph.renewPlot(shapeStr, np.array(scalarDims), self)
            self._update_colorbar()

    def _get_obj_trace(self, item):
        """ Returns the trace to a given item in the TreeView. """
        dText = [str(item.text(0))]
        while item.parent() is not None:
            item = item.parent()
            dText.insert(0, str(item.text(0)))
        # If in secondary tree revert the order
        if not self.datatree.is_files_tree():
            tli = self.datatree.current_item()
            while tli.parent() is not None:
                tli = tli.parent()
            if tli.text(0)[:4] != "Diff":
                dText = [dText[i-1] for i in range(len(dText))]
        return dText

    def _load_slice(self):
        """ Returns the perviously seleced slice for the current array. """
        if not self._data:
            return None
        if self._slice_key() in self.slices:
            return self.slices[self._slice_key()]
        return None

    def _permute_data(self):
        """ Check the input in the permute box and reshape the array. """
        content = str(self.Prmt.text()).strip("([])").replace(" ", "")
        chkstr = content.split(",")
        chkstr.sort()
        if chkstr != [str(_a) for _a in range(self.get(0).ndim)]:
            self.info_msg("Shape is not matching dimensions. Aborting!", -1)
            return
        new_order = tuple(np.array(content.split(","), dtype="i"))
        if new_order == tuple(sorted(new_order)):
            return
        self.transpose_data(new_order)

    def transpose_data(self, new_order):
        """ Transpose dimensions of the data. """
        self.set_data(0, np.transpose(self.get(0), new_order))
        if self._slice_key() in self.slices:
            self.slices[self._slice_key()] = [
                self.slices[self._slice_key()][i] for i in new_order]
        self.Shape.update_shape(self.get(0).shape)
        sh = self.get(0).shape
        self.info_msg("Permuted from " + str(tuple(sh[o] for o in new_order)) +
                      " to " + str(sh), 0)


    def pop(self, key):
        """ Returns the current data and removes it from the dict. """
        return reduce(getitem, key[:-1], self._data).pop(key[-1])

    def _save_chart(self):
        """ Saves the currently shown chart as a file. """
        figure = self.Graph.figure()
        ftyp = 'Image file (*.png *.jpg);;PDF file (*.pdf)'
        if figure:
            fname = QFileDialog.getSaveFileName(self, 'Save Image',
                                                './figure.png', ftyp)
            if fname:
                figure.savefig(fname[0])

    def _set_dark_mode(self, dm=True):
        """ Set a dark mode for the Application. """
        self.config.set('opt', 'darkmode', str(dm))
        if dm:
            self.app.setPalette(dark_qpalette())
        else:
            self.app.setPalette(self.app.style().standardPalette())

    def _set_fixate_view(self, new_val):
        self.Shape.fixate_view = new_val

    def _set_slice(self):
        """ Get the current slice in the window and save it in a dict. """
        if isinstance(self.get(0), self.noPrintTypes):
            return
        curr_slice = self.Shape.current_slice()
        # Check if the dimensions match and return silently otherwise
        if len(self.get(0).shape) != len(curr_slice):
            return
        self.slices[self._slice_key()] = curr_slice
        self._draw_data()

    def _slice_key(self):
        """ Return the slice key for the current dataset. """
        return '/'.join(self.cText)

    def _start_diff(self):
        """ Start the diff view. """
        if self.diffBtn.isVisible():
            self.diffBtn.hide()
            self.datatree.currentWidget().setColumnHidden(1, True)
        else:
            self.diffBtn.show()
            self.datatree.currentWidget().setColumnHidden(1, False)
            for item in self.datatree.checkableItems:
                item.setCheckState(1, Qt.Unchecked)

    def _update_colorbar(self):
        """ Update the values of the colorbar according to the slider value."""
        self.Graph.colorbar(self.Sldr.value())


    ## Public Methods
    def load_files(self, fnames):
        """ Load files to the tree. If key already exists, show a Warning. """
        # Remove duplicates
        fnames = list(dict.fromkeys(fnames))
        new_keys = []
        for fname in fnames:
            # Check if the data already exists
            splitted = os.path.split(fname)
            key = str(os.path.split(splitted[0])[1] + " - " + splitted[1])
            # Show warning if data exists
            if key in self.keys or key in new_keys:
                txt = "Data(%s) exists.\nDo you want to overwrite it?"%key
                replaceBtn = QPushButton(QIcon.fromTheme("list-add"),
                                         "Add new Dataset")
                msg = QMessageBox(QMessageBox.Warning, "Warning", txt)
                yesBtn = msg.addButton(QMessageBox.Yes)
                msg.addButton(QMessageBox.No)
                msg.addButton(replaceBtn, QMessageBox.AcceptRole)
                msg.setDefaultButton(QMessageBox.Yes)
                msg.exec_()
                if msg.clickedButton() == replaceBtn:
                    n = 1
                    while key + "_" + str(n) in self.keys:
                        n += 1
                    key = key + "_" + str(n)
                elif msg.clickedButton() != yesBtn:
                    continue
                else:
                    self.keys.remove(key)
            new_keys.append(key)
            loadItem = QTreeWidgetItem([self.lMsg])
            loadItem.setForeground(0, QColor("grey"))
            self.datatree.Tree.addTopLevelItem(loadItem)
            self.loader.load.emit(fname, key, self.config.getboolean(
                'opt', 'first_to_last'))

    ## PyQt Slots
    @pyqtSlot(str, int)
    def info_msg(self, text, warn_level):
        """ Show an info Message. """
        if warn_level == -1:
            self.errMsg.setText(text)
            self.errMsg.setStyleSheet("QLabel { color : red; }")
        elif warn_level == 0:
            self.errMsg.setText(text)
            self.errMsg.setStyleSheet("QLabel { color : green; }")
        elif warn_level == 1:
            print(text)
        self.errMsgTimer.singleShot(2000, lambda: self.errMsg.setText(""))

    @pyqtSlot(dict, str)
    def on_done_loading(self, data, key):
        """ Set the data into the global _data list once loaded. """
        key = str(key)
        if key != "":
            self._data[key] = data
            self.keys.append(key)
        self.datatree.update_tree()

    ## Overloaded PyQt Methods
    def keyPressEvent(self, ev):
        """ Catch keyPressEvents for [Delete] and [Ctrl]+[C]. """
        if ev.key() == Qt.Key_Delete:
            self._delete_data()
        elif ev.key() == Qt.Key_C:
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ControlModifier:
                sys.exit()


def main():
    """ Main Function. """
    app = QApplication(sys.argv)
    config = ConfigParser()
    try:
        assert config.read(os.path.expanduser("~/.arrayviewer"))
    except (AssertionError, MissingSectionHeaderError) as _:
        config.add_section('opt')
        config.set('opt', 'first_to_last', 'False')
        config.set('opt', 'darkmode', 'False')
    window = ViewerWindow(app, config)
    fnames = [os.path.abspath(new_file) for new_file in sys.argv[1:]]
    window.load_files(fnames)
    window.show()
    app.exec_()
    with open(os.path.expanduser("~/.arrayviewer"), "w") as conf_file:
        config.write(conf_file)
    sys.exit()

if __name__ == '__main__':
    main()
