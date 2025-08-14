#!/usr/bin/env python3
"""
Base Script of the Array Viewer
"""
# View arrays from different sources in the viewer. Reshape them etc.
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>

import sys
from itertools import zip_longest
from functools import reduce
from operator import getitem
from configparser import ConfigParser, MissingSectionHeaderError
from importlib import resources

import os.path
from natsort import realsorted, ns
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication, QCheckBox,
                             QFileDialog, QGridLayout, QLabel, QLineEdit,
                             QMainWindow, QMenu, QToolBar, QMessageBox,
                             QPushButton, QWidget)
from PyQt5.QtWidgets import QSizePolicy as QSP
from PyQt5.QtCore import pyqtSlot, Qt, QTimer
import numpy as np
from ArrayViewer.Charts import GraphWidget
from ArrayViewer.Dialogs import ReshapeDialog, NewDataDialog, show_aview_about
from ArrayViewer.Slider import rangeSlider
from ArrayViewer.Data import Loader, h5py
from ArrayViewer.Style import dark_qpalette
from ArrayViewer.DataTree import DataTree
from ArrayViewer.Shape import ShapeSelector
from ArrayViewer.Options import OptionsDialog
from ArrayViewer.Editor import EditorDialog

ICONPATH = resources.files("ArrayViewer") / 'icons'

def _menu_opt(menu, text, function, shortcut=None, act_grp=None):
    """ Build a new menu option. """
    btn = QAction(menu)
    btn.setText(text)
    btn.triggered.connect(function)
    if shortcut:
        if isinstance(shortcut, list):
            btn.setShortcuts(shortcut)
        else:
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
        super().__init__(parent)
        # set class variables
        if os.path.isfile(str(ICONPATH / 'aview_logo.svg')):
            self.setWindowIcon(QIcon(str(ICONPATH / 'aview_logo.svg')))
        self.app = application
        self.config = config
        self._data = {}
        self._metadata = {}
        self.slices = {}
        self.operations = {}
        self.cText = []
        self.files = {}
        self.diffNo = 0
        self.noPrintTypes = (int, float, str, list, tuple, type(None))
        self.reload_unchanged_file = ("", "")
        self.reshapeBox = ReshapeDialog(self)
        self.newDataBox = NewDataDialog()
        self.optionsBox = OptionsDialog(self)
        self.editorBox = EditorDialog(self)

        # set the loader from a separate class
        self.loader = Loader()
        self.loader.doneLoading.connect(self.on_done_loading)
        self.loader.infoMsg.connect(self.info_msg)
        self.emptylabel = QLabel()
        self.previous_opr_widget = self.emptylabel

        # General Options
        self.setWindowTitle("Array Viewer")
        self.app.setStyle("Fusion")

        self.__addWidgets()

        # Initialize the menu
        self.__initMenu()

        if self.config.getboolean('opt', 'darkmode', fallback=False):
            self._set_dark_mode(True)

    def __addWidgets(self):
        """ Add the widgets in the main Window. """
        # Create the general Structure
        CWgt = QWidget(self)
        self.setCentralWidget(CWgt)
        grLayout = QGridLayout(CWgt)

        # Add PlotMenu
        grLayout.addWidget(self.__init_toolbar(), 0, 0, 1, 4)

        # Add the Tree Widgets
        self.datatree = DataTree(self, CWgt)
        grLayout.addWidget(self.datatree, 1, 0, 1, 2)

        # Add a hidden Diff Button
        self.diffBtn = QPushButton("Calculate the difference", CWgt)
        self.diffBtn.released.connect(self._calc_diff)
        self.diffBtn.hide()
        grLayout.addWidget(self.diffBtn, 2, 0, 1, 2)

        # Add the min and max labels
        self.txtMin = QLabel("min : ", CWgt)
        self.txtMin.mousePressEvent = self._fixMin
        grLayout.addWidget(self.txtMin, 3, 0)
        self.txtMax = QLabel("max : ", CWgt)
        self.txtMax.mousePressEvent = self._fixMax
        grLayout.addWidget(self.txtMax, 3, 1)

        # Add the "Transpose"-Checkbox
        self.Transp = QCheckBox("Transpose", CWgt)
        self.Transp.stateChanged.connect(self._draw_data)
        grLayout.addWidget(self.Transp, 4, 0, 1, 2)

        # Add the Permute Field
        self.Prmt = QLineEdit("", CWgt)
        self.Prmt.setSizePolicy(QSP(QSP.Fixed, QSP.Fixed))
        self.Prmt.returnPressed.connect(self._permute_data)
        grLayout.addWidget(self.Prmt, 5, 0)
        self.PrmtBtn = QPushButton("Permute", CWgt)
        self.PrmtBtn.released.connect(self._permute_data)
        grLayout.addWidget(self.PrmtBtn, 5, 1)

        # Add the Basic Graph Widget
        self.Graph = GraphWidget(self)
        self.Graph.setSizePolicy(QSP.Expanding, QSP.Expanding)
        grLayout.addWidget(self.Graph, 1, 2, 4, 1)

        # Message Field
        self.errMsgTimer = QTimer(self)
        self.errMsg = QLabel("", CWgt)
        grLayout.addWidget(self.errMsg, 5, 2)

        # Add the Color Slider
        self.Sldr = rangeSlider(CWgt)
        self.Sldr.setSizePolicy(QSP.Fixed, QSP.Expanding)
        self.Sldr.sliderReleased.connect(self._update_colorbar)
        grLayout.addWidget(self.Sldr, 1, 3, 5, 1)

        # Add operations tools
        ag_op = QActionGroup(self)
        ag_op.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        tool = QToolBar()
        tool.setStyleSheet("QToolButton { width: 20px; height 20px; }")
        self._menu_btn(tool, "Min", "min", act_grp=ag_op).triggered.connect(lambda: self.Shape.set_operation('nanmin'))
        self._menu_btn(tool, "Mean", "mean", act_grp=ag_op).triggered.connect(lambda: self.Shape.set_operation('nanmean'))
        self._menu_btn(tool, "Median", "median", act_grp=ag_op).triggered.connect(lambda: self.Shape.set_operation('nanmedian'))
        self._menu_btn(tool, "Max", "max", act_grp=ag_op).triggered.connect(lambda: self.Shape.set_operation('nanmax'))
        grLayout.addWidget(tool, 6, 0)

        # Shape Widget
        self.Shape = ShapeSelector(self)
        grLayout.addWidget(self.Shape, 6, 1, 1, 3)

    def __initMenu(self):
        """ Setup the menu bar. """
        menu = self.menuBar()
        menuStart = QMenu("Start", menu)
        menu.addAction(menuStart.menuAction())

        _menu_opt(menuStart, "Load data", self._dlg_load_data, "Ctrl+O")
        _menu_opt(menuStart, "Save", self._save_chart, "Ctrl+S")
        _menu_opt(menuStart, "New Data", self._dlg_new_data, "Ctrl+N")
        _menu_opt(menuStart, "Reshape", self._dlg_reshape, "Ctrl+R")
        _menu_opt(menuStart, "Difference", self._start_diff, "Ctrl+D")
        _menu_opt(menuStart, "Delete All Data", self._delete_all_data,
                  "Ctrl+X")
        _menu_opt(menuStart, "Options", self.optionsBox.adapt_options)

        # Operations menu
        menuOpr = QMenu("Operations", menu)
        menu.addAction(menuOpr.menuAction())

        _menu_opt(menuOpr, "Find Max", self._data_max_min, ["Ctrl+M", "Ctrl+Shift+M"])
        _menu_opt(menuOpr, "Find Min", self._data_max_min, ["Alt+M", "Alt+Shift+M"])
        _menu_opt(menuOpr, "Colorbar", self._add_colorbar).setCheckable(True)
        _menu_opt(menuOpr, "Keep Slice on data change", self._set_fixate_view).setCheckable(True)

        _menu_opt(menu, "?", show_aview_about)

        # Add a context menu
        self.contextMenu = QMenu(self)
        _menu_opt(self.contextMenu, "Rename", self.datatree.rename_key)
        _menu_opt(self.contextMenu, "Reshape", self._dlg_reshape)
        self.edit_opt = _menu_opt(self.contextMenu, "Edit", self._dlg_edit)
        self.combine_opt = _menu_opt(self.contextMenu, "Combine Dataset",
                                     self._dlg_combine)
        _menu_opt(self.contextMenu, "Delete Data", self._delete_data)

    def _menu_btn(self, menu, text, icon, act_grp):
        """ Build a new menu Icon Button. """
        btn = QAction(menu)
        btn.setToolTip(text)
        btn.setCheckable(True)
        btn.triggered.connect(self._draw_data)
        btn.setIcon(QIcon(str(ICONPATH / f"{icon}.svg")))
        btn.setActionGroup(act_grp)
        menu.addAction(btn)
        return btn

    def __init_toolbar(self):
        """ Setup the toolbar beneath the main menu bar. """
        bar = QToolBar()
        ag_plt = QActionGroup(self)
        self._menu_btn(bar, "Standard", "std", ag_plt).setChecked(True)
        self.Plot2D = self._menu_btn(bar, "2D as plot", "plot", ag_plt)
        self.PlotScat = self._menu_btn(bar, "2D as Scatter", "scatter", ag_plt)
        self.MMM = self._menu_btn(bar, "min-mean-max plot", "mmm", ag_plt)
        self.Plot3D = self._menu_btn(bar, "3D as RGB(A)", "rgb", ag_plt)
        self.PrintFlat = self._menu_btn(bar, "Print Values as text", "text", ag_plt)

        bar.addSeparator()
        ag_cm = QActionGroup(self)
        self._menu_btn(bar, "Colormap 'jet'", 'jet', ag_cm).triggered.connect(lambda: self.Graph.colormap('jet'))
        self._menu_btn(bar, "Colormap 'gray'", 'gray', ag_cm).triggered.connect(lambda: self.Graph.colormap('gray'))
        self._menu_btn(bar, "Colormap 'hot'", 'hot', ag_cm).triggered.connect(lambda: self.Graph.colormap('hot'))
        self._menu_btn(bar, "Colormap 'bwr'", 'bwr', ag_cm).triggered.connect(lambda: self.Graph.colormap('bwr'))
        vir = self._menu_btn(bar, "Colormap 'viridis'", 'viridis', ag_cm)
        vir.triggered.connect(lambda: self.Graph.colormap('viridis'))
        vir.setChecked(True)

        return bar

    def get(self, item):
        """ Gets the current data. """
        if item in [0, "data", ""]:
            item = self.cText
        if not self._data or not item:
            return np.empty(0)
        try:
            return reduce(getitem, item[:-1], self._data)[item[-1]]
        except KeyError:
            # Diff views in the DataTree
            if not self.datatree.is_files_tree() and item[1][:4] == "Diff":
                return self._data[item[1]][item[0]]
            return np.empty(0)

    def get_all_keys(self):
        """ Return all keys from the data. """
        def dict_keys(d):
            """ Get all keys from a dictionary. """
            for k, v in d.items():
                if isinstance(v, dict):
                    yield k, tuple(sk for sk in dict_keys(v))
                else:
                    yield k, isinstance(v, self.noPrintTypes)
        self.files = dict(dict_keys(self._data))

    def set_data(self, newkey, newData, *_):
        """ Sets the current data to the new data. """
        if not self._data:
            self._data = {}
        if newkey in [0, "data", ""]:
            newkey = self.cText
        reduce(getitem, newkey[:-1], self._data)[newkey[-1]] = newData
        self.get_all_keys()

    def _add_colorbar(self):
        """ Add a colorbar to the Graph Widget. """
        self.Graph.toggle_colorbar()
        self.Sldr.set_enabled(self.Graph.has_cb)
        self._update_colorbar()

    def _calc_diff(self):
        """ Calculate the difference and end the diff view. """
        checkedItems = 0
        for item in self.datatree.checkableItems:
            if item.checkState(0) == Qt.Checked:
                text = self.get_obj_trace(item)
                if checkedItems == 0:
                    text0 = '[0] ' + '/'.join(text)
                    item0 = self.get(text)
                else:
                    text1 = '[1] ' + '/'.join(text)
                    item1 = self.get(text)
                checkedItems += 1
        if checkedItems != 2:
            self.info_msg(f"Checked {checkedItems} items. Should be 2!", -1)
        elif item0.shape == item1.shape:
            textcomb = "~> Diff [0]-[1]"
            self._data[f"Diff {self.diffNo}"] = {text0: item0, text1: item1,
                                                 textcomb: item0 - item1}
            isnpt = isinstance(item0, self.noPrintTypes)
            self.files[f"Diff {self.diffNo}"] = ((text0, isnpt), (text1, isnpt), (textcomb, isnpt))
            self.diffNo += 1
            self.datatree.currentWidget().setColumnHidden(0, True)
            self.diffBtn.hide()
            self.datatree.update_tree()

    def _change_tree(self, current, previous):
        """ Draw chart, if the selection has changed. """
        if (current and current != previous):
            # Control uses the same slice as before
            old_fix_state = self.Shape.fixate_view
            if QApplication.keyboardModifiers() & Qt.ControlModifier:
                self.Shape.fixate_view = True
            else:
                self.Graph.set_oprdim()
            self.Graph.clear()
            # Only bottom level nodes contain data -> skip if node has children
            if current.childCount() == 0:
                # Get the currently selected FigureCanvasQTAggd data recursively
                self.cText = self.get_obj_trace(current)
                # Update the shape widgets based on the datatype
                if isinstance(self.get(0), self.noPrintTypes):
                    self.Shape.update_shape([0], False)
                    self.PrmtBtn.setEnabled(False)
                    self.edit_opt.setEnabled(False)
                else:
                    self.Shape.update_shape(self.get(0).shape)
                    self.PrmtBtn.setEnabled(True)
                    self.edit_opt.setEnabled(True)
            self.Shape.fixate_view = old_fix_state

    def _data_max_min(self, _):
        """
            Get the maximum or minimum of the selected data and set the
            shape accordingly
        """
        modifiers = QApplication.keyboardModifiers()
        # Shift uses the full array instead of the current cutout
        if modifiers & Qt.ShiftModifier:
            data = self.get(0)
        else:
            data = self.Graph.cutout
        if not isinstance(data, (np.ndarray, h5py.Dataset)) or data.size == 0:
            return
        # Alt uses minimum Ctrl uses maximum
        if modifiers & Qt.AltModifier:
            idx = np.argmin(data)
        else:
            idx = np.argmax(data)
        # Get the unraveled index of the maximum/minum and set it in the shape
        unraveled_idx = np.unravel_index(idx, data.shape)
        if modifiers & Qt.ShiftModifier:
            self.Shape.set_all_values(unraveled_idx)
        else:
            self.Shape.set_non_scalar_values(unraveled_idx)

    def _delete_all_data(self):
        """ Delete all data from the Treeview. """
        txt = "Delete all data in the Array Viewer?"
        btns = (QMessageBox.Yes|QMessageBox.No)
        msg = QMessageBox(QMessageBox.Warning, "Warning", txt, buttons=btns)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec_() != QMessageBox.Yes:
            return
        del self._data
        del self._metadata
        del self.files
        self._data = {}
        self._metadata = {}
        self.diffNo = 0
        self.files = {}
        self.cText = []
        self.slices = {}
        self.datatree.clear_tree()
        self.Graph.clear()

    def _dropdown(self, _):
        """ Add a context menu. """
        if self.datatree.current_item():
            self.combine_opt.setVisible(
                self.datatree.current_item().childCount() != 0)
            self.contextMenu.popup(QCursor.pos())

    def _delete_data(self):
        """ Delete the selected data. """
        citem = self.datatree.current_item()
        dText = self.get_obj_trace(citem)
        citem = self.datatree.current_item()
        del reduce(getitem, dText[:-1], self._data)[dText[-1]]
        if len(dText) == 1:
            self._metadata.pop(dText[0], None)
        self.get_all_keys()
        self.datatree.remove_from_checkables(citem.takeChildren())
        (citem.parent() or self.datatree.root).removeChild(citem)

    def _dlg_combine(self):
        """ Open a dialog to combine the dataset. """
        trace = self.get_obj_trace(self.datatree.current_item())
        data = self.get(trace)
        keys = realsorted(data, alg=ns.IGNORECASE|ns.NUMAFTER)
        skipkeys = []

        # Find the biggest shape in the dataset and drop unusable keys
        dshape = set()
        for k in keys:
            try:
                dshape.add(data[k].shape)
            except ValueError:
                # For h5py dictionaries
                dshape.add(data.get(k)[()].shape)
            except AttributeError:
                # uncombinable types
                skipkeys.append(k)
        keys = [k for k in keys if k not in skipkeys]
        mshape = tuple(np.max(list(set(dshape)), axis=0)) + (len(keys),)

        # Show a dialog asking if the combination should be done.
        txt = f"Combine {len(keys)} elements into {mshape} shape?"
        msg = QMessageBox(QMessageBox.Information, "Info", txt)
        msg.addButton(QMessageBox.Yes)
        keepBtn = msg.addButton("Yes but keep Elements", QMessageBox.YesRole)
        msg.addButton(QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        result = msg.exec_()
        if result == QMessageBox.No:
            return

        # Perform the combination
        try:
            newd = [data[k].flatten() for k in keys]
        except ValueError:
            # For h5py dictionaries
            newd = [data.get(k)[()].flatten() for k in keys]
        combined = np.array(list(zip_longest(*newd)), dtype=float)
        try:
            combined = np.reshape(combined, mshape)
        except ValueError:
            pass
        # Add 'combined'-key if it is a topLevelItem
        if len(trace) == 1 or len(skipkeys) > 0 or result == keepBtn:
            trace.append('combined')
            # Remove the combined data
            if result != keepBtn:
                _ = [self.get(trace[:-1]).pop(key) for key in keys]
        self.set_data(trace, combined)
        self.datatree.update_tree()

    def _dlg_load_data(self):
        """ Open file-dialog to choose one or multiple files. """
        FD = QFileDialog(self, 'Open data file', '.',
                         """Raw data (*.data *.hdf5 *.mat *.npy *.txt *.csv *.bin);;
                          Images (*.jpg *.bmp *.png *.tiff *.gif);;
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
            self.files[key] = ("Value", isinstance(_data, self.noPrintTypes))
            self.datatree.update_tree()

    def _dlg_reshape(self):
        """ Open the reshape box to reshape the current data. """
        cTree = self.datatree.currentWidget()  # The current Tree
        if not cTree.currentItem():
            return
        if cTree.currentItem().childCount() != 0:
            # If the current item has children try to reshape all of them
            tr = self.get_obj_trace(cTree.currentItem())
            if self.datatree.is_files_tree():
                keys = [tr + [k] for k in self.datatree.similar_items
                        if isinstance(self.get(tr + [k]),
                                      (np.ndarray, h5py.Dataset))]
            else:
                keys = [[k] + tr for k in self.datatree.similar_items
                        if isinstance(self.get([k] + tr),
                                      (np.ndarray, h5py.Dataset))]
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
        elif isinstance(self.get(0), (np.ndarray, h5py.Dataset)):
            # If just one is chosen and has a numpy compatible type, reshape it
            self.set_data(0, *self.reshapeBox.reshape_array(self.get(0)))
            if self._slice_key() in self.slices:
                del self.slices[self._slice_key()]
            if self._slice_key() in self.operations:
                del self.operations[self._slice_key()]
        else:
            return
        self.Shape.update_shape(self.get(0).shape)

    def _dlg_edit(self):
        """ Open the editor window. """
        self.editorBox.open_editor(self.get(0))

    def _draw_data(self):
        """ Draw the selected data. """
        shapeStr, scalarDims = self.Shape.get_shape()
        if shapeStr or self.get(0).shape == (1,):
            self.Graph.renewPlot(shapeStr, scalarDims)
            self._update_colorbar()

    def _fixMin(self, _):
        is_fixed = self.Graph.fix_limit(0)
        if is_fixed:
            self.txtMin.setText(self.txtMin.text() + "\U0001F512")
            self.txtMin.setStyleSheet("color:lightgrey;")
        else:
            self.txtMin.setText(self.txtMin.text()[:-1])
            self.txtMin.setStyleSheet("")

    def _fixMax(self, _):
        is_fixed = self.Graph.fix_limit(1)
        if is_fixed:
            self.txtMax.setText(self.txtMax.text() + "\U0001F512")
            self.txtMax.setStyleSheet("color:lightgrey;")
        else:
            self.txtMax.setText(self.txtMax.text()[:-1])
            self.txtMax.setStyleSheet("")

    def get_obj_trace(self, item):
        """ Returns the trace to a given item in the TreeView. """
        dText = [str(item.text(1))]
        while item.parent() is not None:
            item = item.parent()
            dText.insert(0, str(item.text(1)))
        # If in secondary tree revert the order
        if not self.datatree.is_files_tree():
            tli = self.datatree.current_item()
            if tli is None:
                tli = self.datatree.root
            else:
                while tli.parent() is not None:
                    tli = tli.parent()
            if tli.text(1)[:4] != "Diff":
                dText = [dText[i - 1] for i in range(len(dText))]
        return dText

    def _load_slice(self):
        """ Returns the perviously seleced slice for the current array. """
        if not self._data:
            return None, None
        k = self._slice_key()
        return (self.slices[k] if k in self.slices else None,
                self.operations[k] if k in self.operations else None)

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
        if self._slice_key() in self.operations:
            self.operations[self._slice_key()] = [
                new_order[i] for i in self.operations[self._slice_key()]]
        self.Shape.update_shape(self.get(0).shape)
        sh = self.get(0).shape
        self.info_msg(f"Permuted from {tuple(sh[o] for o in new_order)} to {sh}", 0)

    def pop(self, key):
        """ Returns the current data and removes it from the dict. """
        return reduce(getitem, key[:-1], self._data).pop(key[-1])

    def _save_chart(self):
        """ Saves the currently shown chart as a file. """
        figure = self.Graph.figure()
        ftype = 'Image file (*.png *.jpg);;Vector graphic (*.svg);;PDF file (*.pdf)'
        if figure:
            fname = QFileDialog.getSaveFileName(self, 'Save Image',
                                                './figure.png', ftype)
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
        self.operations[self._slice_key()] = self.Shape.operation_state
        self._draw_data()

    def _slice_key(self):
        """ Return the slice key for the current dataset. """
        return '/'.join(self.cText)

    def _start_diff(self):
        """ Start the diff view. """
        if self.diffBtn.isVisible():
            self.diffBtn.hide()
            self.datatree.currentWidget().setColumnHidden(0, True)
        else:
            self.diffBtn.show()
            self.datatree.currentWidget().setColumnHidden(0, False)
            for item in self.datatree.checkableItems:
                item.setCheckState(0, Qt.Unchecked)

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
            key = f"{os.path.split(splitted[0])[1]} - {splitted[1]}"
            # Show warning if data exists
            if key in self.files or key in new_keys:
                txt = f"Data({key}) exists.\nDo you want to overwrite it?"
                replaceBtn = QPushButton(QIcon.fromTheme("list-add"),
                                         "Add new Dataset")
                msg = QMessageBox(QMessageBox.Warning, "Warning", txt)
                msg.addButton(QMessageBox.Yes)
                msg.addButton(QMessageBox.No)
                msg.addButton(replaceBtn, QMessageBox.AcceptRole)
                msg.setDefaultButton(QMessageBox.Yes)
                result = msg.exec_()
                if result == QMessageBox.AcceptRole:
                    n = 1
                    while f"{key}_{n}" in self.files:
                        n += 1
                    key = f"{key}_{n}"
                elif result != QMessageBox.Yes:
                    continue
                else:
                    self.files.remove(key)
            new_keys.append(key)
            self.info_msg(f"Loading {fname} ...", 0)
            self.loader.load.emit(fname, key,
                                  self.config.getboolean('opt', 'first_to_last', fallback=False),
                                  self.config.getint('opt', 'max_file_size', fallback=15))

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

    @pyqtSlot(dict, str, str)
    def on_done_loading(self, data, key, fname):
        """ Set the data into the global _data list once loaded. """
        key = str(key)
        if key != "":
            self._data[key] = data
            self.get_all_keys()
            self._metadata[key] = fname, os.path.getmtime(fname)
        self.datatree.update_tree(self.cText)
        self.info_msg(f"Done loading {fname}", 0)

    ## Overloaded PyQt Methods
    def keyPressEvent(self, ev):
        """ Catch keyPressEvents for [Delete] and [Ctrl]+[C]. """
        if ev.key() == Qt.Key_Delete:
            self._delete_data()
        elif ev.key() == Qt.Key_C:
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ControlModifier:
                sys.exit()
        elif ev.key() == Qt.Key_F5:
            key = self.get_obj_trace(self.datatree.current_item())[0]
            fname, timestamp = self._metadata.get(key)
            if os.path.getmtime(fname) == timestamp and self.reload_unchanged_file != (fname, timestamp):
                self.info_msg("File has not changed since last load. Press F5 again to load anyway.", 0)
                self.reload_unchanged_file = (fname, timestamp)
                return
            self.reload_unchanged_file = ("", "")
            msg = QMessageBox(QMessageBox.Question, "Reload",
                              f"Do you want to reload the file {key}?",
                              QMessageBox.Yes | QMessageBox.No)
            if msg.exec_() == QMessageBox.Yes:
                self.files.pop(key, None)
                self.loader.load.emit(
                    fname, key,
                    self.config.getboolean("opt", "first_to_last", fallback=False),
                    self.config.getint("opt", "max_file_size", fallback=15))


def main():
    """ Main Function. """
    app = QApplication(sys.argv)
    config = ConfigParser()
    conf_file_name = os.path.expanduser("~/.arrayviewer")
    try:
        assert config.read(conf_file_name)
    except (AssertionError, MissingSectionHeaderError) as _:
        config.add_section('opt')
        config.set('opt', 'first_to_last', 'False')
        config.set('opt', 'darkmode', 'False')
        config.set('opt', 'anim_speed', '300')
        config.set('opt', 'cursor', 'False')
        config.set('opt', 'unsave', 'False')
        config.set('opt', 'max_file_size', '15')
    window = ViewerWindow(app, config)
    fnames = [os.path.abspath(new_file) for new_file in sys.argv[1:]]
    window.load_files(fnames)
    window.show()
    app.exec_()
    with open(conf_file_name, "w", encoding="utf-8") as conf_file:
        config.write(conf_file)
    sys.exit()


if __name__ == '__main__':
    main()
