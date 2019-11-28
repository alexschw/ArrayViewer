"""
# GraphWidget and ReshapeDialog for the ArrayViewer
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
"""
import re
from itertools import combinations
from PyQt5.QtWidgets import (QCompleter, QDialog, QGridLayout, QLabel,
                             QLineEdit, QSizePolicy, QTextEdit, QVBoxLayout,
                             QWidget)
from PyQt5.QtWidgets import QDialogButtonBox as DBB
from PyQt5 import QtCore
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator as TickMultLoc
import numpy as np
from h5py._hl.dataset import Dataset

def _flat_with_padding(Array, padding=1, fill=np.nan):
    """ Flatten ND array into a 2D array and add a padding with given fill """
    # Reshape the array to 3D
    Arr = np.reshape(Array, Array.shape[:2] + (-1, ))
    if (Array.ndim == 4 and .18 < 1.0 * Array.shape[2] / Array.shape[3] < 5.5):
        # If the Array is 4D and has reasonable ratio, keep that ratio.
        rows = Array.shape[2]
    else:
        # Get the most equal division of the last dimension
        for n in range(int(np.sqrt(Arr.shape[2])), Arr.shape[2] + 1):
            if Arr.shape[2]%n == 0:
                rows = Arr.shape[2] / n
                break
    # Add the padding to the right and bottom of the arrays
    A0 = np.ones([padding, Arr.shape[1], Arr.shape[2]]) * fill
    A1 = np.ones([Arr.shape[0] + padding, padding, Arr.shape[2]]) * fill
    pArr = np.append(np.append(Arr, A0, axis=0), A1, axis=1)
    # Stack the arrays according to the precalculated number of rows
    pA2D = np.hstack(np.split(np.hstack(pArr.T).T, rows)).T
    # Add the padding to the left and top of the arrays
    A0 = np.ones([padding, pA2D.shape[1]]) * fill
    A1 = np.ones([pA2D.shape[0] + padding, padding]) * fill
    pA2D = np.append(A1, np.append(A0, pA2D, axis=0), axis=1)
    return pA2D


def _get_shape_from_str(string):
    """
    Returns an array with the elements of the string. All brackets are
    removed as well as empty elements in the array.
    """
    return np.array([_f for _f in string.strip("()[]").split(",") if _f],
                    dtype=int)

def _set_ticks(ax, s, transp, is1DPlot=False):
    """ Set the ticks of plots according to the selected slices. """
    # Calculate the ticks for the plot by checking the limits
    limits = [l.split(':') for l in s[1:-1].split(',') if ':' in l]
    lim = np.array([l if len(l) == 3 else l+['1'] for l in limits])
    lim[lim == ''] = '0'
    lim = lim.astype(float)
    if lim.shape[0] == 1:
        lim = np.append([[0, 0, 1]], lim, axis=0)
    if not transp:
        lim = lim[(1, 0), :]
    # Set the x-ticks
    loc = ax.xaxis.get_major_locator()()
    d = (np.arange(len(loc))-1)*(loc[2] - loc[1])*lim[0, 2]+lim[0, 0]
    if all(d.astype(int) == d.astype(float)):
        ax.set_xticklabels(d.astype(int))
    else:
        ax.set_xticklabels(d.astype(float))
    if is1DPlot:
        return
    # Set the y-ticks
    loc = ax.yaxis.get_major_locator()()
    d = (np.arange(len(loc))-1)*(loc[2] - loc[1])*lim[1, 2]+lim[1, 0]
    if all(d.astype(int) == d.astype(float)):
        ax.set_yticklabels(d.astype(int))
    else:
        ax.set_yticklabels(d.astype(float))

def _suggestion(previous_val, value):
    """ Returns all possible factors """
    pfactors = []
    divisor = 2
    while value > 1:
        while value % divisor == 0:
            pfactors.append(divisor)
            value /= divisor
        divisor += 1
        if divisor * divisor > value:
            if value > 1:
                pfactors.append(value)
            break
    factors = []
    for n in range(1, len(pfactors) + 1):
        for x in combinations(pfactors, n):
            y = 1
            for a in x:
                y = y * a
            factors.append(int(y))
    factors = list(set(factors))
    factors.sort(reverse=True)
    return [previous_val + "{0},".format(i) for i in factors]

class GraphWidget(QWidget):
    """ Draws the data graph. """
    def __init__(self, parent=None):
        """ Initialize the figure. """
        super(GraphWidget, self).__init__(parent)

        # Setup the canvas, figure and axes
        self._figure = Figure(facecolor='white')
        self._canv = FigureCanvasQTAgg(self._figure)
        self._canv.ax = self._figure.add_axes([.15, .15, .75, .75])
        self._canv.canvas = self._canv.ax.figure.canvas
        self._canv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.noPrintTypes = parent.parent().parent().noPrintTypes
        self._clim = (0, 1)
        self._img = None
        self._cb = None
        self.has_cb = False
        self.has_operation = False
        self._colormap = 'viridis'
        self._operation = 'None'
        self._opr = (lambda x: x)
        self._oprdim = -1
        self._oprcorr = -1
        self.cutout = np.array([])

        # Add a label Text that may be changed in later Versions to display the
        # position and value below the mouse pointer
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._canv)
        self._txt = QLabel(self)
        self._txt.setText('')
        self._layout.addWidget(self._txt)

    def _n_D_plot(self, ax, ui):
        """ Plot multi-dimensional data. """
        sh = self.cutout.shape
        nPad = sh[0] // 100 + 1
        if ui.Plot3D.isChecked() and self.cutout.ndim == 3 and sh[2] == 3:
            nPad = -1
            mm = [np.min(self.cutout), np.max(self.cutout)]
            dat = np.swapaxes((self.cutout - mm[0]) / (mm[1] - mm[0]), 0, 1)
        else:
            dat = _flat_with_padding(self.cutout, nPad)
        self._img = ax.imshow(dat, interpolation='none', aspect='auto')
        locx = TickMultLoc(sh[0] + nPad)
        ax.xaxis.set_major_locator(locx)
        ax.xaxis.set_ticklabels(np.arange(-sh[0], int(locx().max()), sh[0]))
        locy = TickMultLoc(sh[1] + nPad)
        ax.yaxis.set_major_locator(locy)
        ax.yaxis.set_ticklabels(np.arange(-sh[1], int(locy().max()), sh[1]))

    def _two_D_plot(self, ui, ax, s):
        """ Plot 2-dimensional data. """
        if ui.MMM.isChecked():
            ax.plot(self.cutout.max(axis=0), 'r')
            ax.plot(self.cutout.mean(axis=0), 'k')
            ax.plot(self.cutout.min(axis=0), 'b')
            ax.legend(["Max", "Mean", "Min"])
        else:
            self._img = ax.imshow(self.cutout.T, interpolation='none',
                                  aspect='auto')
        _set_ticks(ax, s, ui.Transp.isChecked())

    def clear(self):
        """ Clear the figure. """
        self._cb = None
        self._figure.clf()

    def colorbar(self, minmax=None):
        """ Add a colorbar to the graph or remove it, if it is existing. """
        if self._img is None:
            return
        if minmax is not None:
            self._img.set_clim(
                vmin=minmax[0] * (self._clim[1] - self._clim[0])
                + self._clim[0], vmax=minmax[1] * self._clim[1]
            )
        if not self.has_cb:
            if self._cb:
                self._cb.remove()
                self._cb = None
        elif self._cb is None:
            self._cb = self._figure.colorbar(self._img)
        self._canv.draw()

    def colormap(self, mapname=None):
        """ Replace colormap with the given one. """
        if mapname:
            self._colormap = mapname
        if self._img is None:
            return
        self._img.set_cmap(self._colormap)
        self._canv.draw()

    def figure(self):
        """ Return the local figure variable. """
        return self._figure

    def has_opr(self):
        """ Check if the operation is None. """
        return self.has_operation

    def renewPlot(self, data, s, scalDims, ui):
        """ Draw given data. """
        ax = self._figure.gca()
        ax.clear()
        # Reset the minimum and maximum text
        ui.txtMin.setText('min : ')
        ui.txtMax.setText('max : ')
        if data is None:
            return
        if isinstance(data, self.noPrintTypes):
            # Print strings or lists of strings to the graph directly
            ax.text(-0.1, 1.1, data, va='top', wrap=True)
            ax.axis('off')
        elif isinstance(data, Dataset) and data.shape == ():
            # Print single values of h5py arrays to the graph directly
            ax.text(-0.1, 1.1, data[()], va='top', wrap=True)
            ax.axis('off')
        elif isinstance(data[0], list):
            # If there is an array of lists plot each element as a graph
            for lst in data:
                ax.plot(lst)
        else:
            # Cut out the chosen piece of the array and plot it
            self.cutout = np.array([])
            self.cutout = eval("data%s.squeeze()"%s)
            if self._oprdim != -1 and self._oprdim not in scalDims:
                self._oprcorr = self._oprdim - (scalDims <= self._oprdim).sum()
                self.cutout = self._opr(self.cutout)
            # Transpose the first two dimensions if it is chosen
            if ui.Transp.isChecked() and self.cutout.ndim > 1:
                self.cutout = np.swapaxes(self.cutout, 0, 1)
            # Print the Value(s) directly
            if self.cutout.ndim == 0 or ui.PrintFlat.isChecked():
                ax.set_ylim([0, 1])
                ax.text(-0.1, 1.1, self.cutout, va='top', wrap=True)
                ax.axis('off')
            # Graph an 1D-cutout
            elif self.cutout.ndim == 1:
                ax.plot(self.cutout)
                _set_ticks(ax, s, False, True)
                alim = ax.get_ylim()
                if alim[0] > alim[1]:
                    ax.invert_yaxis()
            # 2D-cutout will be shown using imshow or plot
            elif self.cutout.ndim == 2:
                if ui.Plot2D.isChecked():
                    if self.cutout.shape[1] > 500:
                        msg = "You are trying to plot more than 500 lines!"
                        ui.info_msg(msg, -1)
                        return
                    ax.plot(self.cutout)
                    _set_ticks(ax, s, not ui.Transp.isChecked(), True)
                else:
                    self._two_D_plot(ui, ax, s)
            # higher-dimensional cutouts will first be flattened
            elif self.cutout.ndim >= 3:
                self._n_D_plot(ax, ui)
            # Reset the colorbar. A better solution would be possible, if the
            # axes were not cleared everytime.
            self.colorbar()
            self.colormap()
            if self.cutout.size > 0:
                self._clim = (self.cutout.min(), self.cutout.max())
                # Set the minimum and maximum values from the data
                ui.txtMin.setText('min : ' + "%0.5f"%self._clim[0])
                ui.txtMax.setText('max : ' + "%0.5f"%self._clim[1])
        self._canv.draw()

    def set_operation(self, operation="None"):
        """ Set an operation to be performed on click on a dimension. """
        self.has_operation = (operation != "None")
        if not self.has_operation:
            self._oprdim = -1
            self._opr = (lambda x: x)
        else:
            self._opr = (lambda x: eval("np." + operation + "(x, axis="
                                        + str(self._oprcorr) + ")"))
        return self._oprdim

    def set_oprdim(self, value):
        """ Set the operation dimension. """
        self._oprdim = value

    def toggle_colorbar(self):
        """ Toggle the state of the colorbar """
        self.has_cb = not self.has_cb
        self.colorbar()


class ReshapeDialog(QDialog):
    """ A Dialog for Reshaping the Array. """
    def __init__(self, parent=None):
        """ Initialize. """
        super(ReshapeDialog, self).__init__(parent)

        # Setup the basic window
        self.resize(400, 150)
        self.setWindowTitle("Reshape the current array")
        self.prodShape = 0
        self.info_msg = parent.info_msg
        gridLayout = QGridLayout(self)

        # Add the current and new shape boxes and their labels
        curShape = QLabel(self)
        curShape.setText("current shape")
        gridLayout.addWidget(curShape, 0, 0, 1, 1)
        self.txtCurrent = QLineEdit(self)
        self.txtCurrent.setEnabled(False)
        gridLayout.addWidget(self.txtCurrent, 0, 1, 1, 1)
        newShape = QLabel(self)
        newShape.setText("new shape")

        gridLayout.addWidget(newShape, 1, 0, 1, 1)
        self.txtNew = QLineEdit(self)
        self.txtNew.textEdited.connect(self._key_press)
        self.cmpl = QCompleter([])
        self.cmpl.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.txtNew.setCompleter(self.cmpl)
        gridLayout.addWidget(self.txtNew, 1, 1, 1, 1)

        # Add a button Box with "OK" and "Cancel"-Buttons
        self.buttonBox = DBB(DBB.Cancel|DBB.Ok, QtCore.Qt.Horizontal)
        gridLayout.addWidget(self.buttonBox, 3, 1, 1, 1)
        self.buttonBox.button(DBB.Cancel).clicked.connect(self.reject)
        self.buttonBox.button(DBB.Ok).clicked.connect(self.accept)

    def _key_press(self, keyEv):
        """ Whenever a key is pressed check for comma and set autofill data."""
        if keyEv and keyEv[-1] == ',':
            shape = _get_shape_from_str(str(keyEv))
            if self.prodShape%shape.prod() == 0:
                rest = self.prodShape // shape.prod()
                self.cmpl.model().setStringList(_suggestion(keyEv, rest))
            else:
                self.cmpl.model().setStringList([keyEv + " Not fitting"])
        return keyEv

    def reshape_array(self, data):
        """ Reshape the currently selected array. """
        while True:
            # Open a dialog to reshape
            self.txtCurrent.setText(str(data.shape))
            self.prodShape = np.array(data.shape).prod()
            self.txtNew.setText("")
            # If "OK" is pressed
            if data.shape and self.exec_():
                # Get the shape sting and split it
                sStr = str(self.txtNew.text())
                if sStr == "":
                    continue
                # Try if the array could be reshaped that way
                try:
                    data = np.reshape(data, _get_shape_from_str(sStr))
                # If it could not be reshaped, get another user input
                except ValueError:
                    self.info_msg("Data could not be reshaped!", -1)
                    continue
                return data
            # If "CANCEL" is pressed
            return data


class NewDataDialog(QDialog):
    """ A Dialog for Creating new Data. """
    def __init__(self, parent=None):
        """ Initialize. """
        super(NewDataDialog, self).__init__(parent)

        # Setup the basic window
        self.resize(400, 150)
        self.setWindowTitle("Create new data or change the current one")
        Layout = QVBoxLayout(self)
        self.data = {}
        self.lastText = ""
        self.returnVal = None

        # Add the current and new shape boxes and their labels
        label = QLabel(self)
        label.setText(("Use 'this' to reference the current data and 'cutout'"+
                       " for the current view.\n"+
                       "Before saving enter the variable you want to save. \n"+
                       "Otherwise the original data will be overwritten."))
        Layout.addWidget(label)
        self.history = QTextEdit(self)
        self.history.setEnabled(False)
        Layout.addWidget(self.history)
        self.cmd = QLineEdit(self)
        Layout.addWidget(self.cmd)
        self.err = QLineEdit(self)
        self.err.setEnabled(False)
        self.err.setStyleSheet("color: rgb(255, 0, 0);")
        Layout.addWidget(self.err)

        # Add a button Box with "OK" and "Cancel"-Buttons
        self.buttonBox = DBB(DBB.Cancel|DBB.Ok|DBB.Save, QtCore.Qt.Horizontal)
        Layout.addWidget(self.buttonBox)
        self.buttonBox.button(DBB.Cancel).clicked.connect(self.reject)
        self.buttonBox.button(DBB.Ok).clicked.connect(self._on_accept)
        self.buttonBox.button(DBB.Save).clicked.connect(self._on_save)

    def _on_accept(self):
        """ Try to run the command and append the history on pressing 'OK'. """
        try:
            var, value = self._parsecmd(str(self.cmd.text()))
            self.data[var] = eval(value)
        except Exception as err:
            self.err.setText(str(err))
            return
        self.history.append(self.cmd.text())
        self.lastText = str(self.cmd.text())
        self.cmd.setText("")

    def _on_save(self):
        """ Return the object currently in the textBox to the Viewer. """
        if re.findall(r"\=", self.cmd.text()):
            return
        if self.cmd.text() == "":
            self.returnVal = re.split(r"\=", self.lastText)[0].strip()
            self.accept()
        else:
            self.returnVal = self.cmd.text().strip()
            if self.returnVal is not None:
                self.accept()
            else:
                return

    def _parsecmd(self, cmd):
        """ Parse the command given by the user. """
        try:
            var, expr = cmd.split("=", 1)
        except ValueError:
            raise ValueError("No '=' in expression")
        for op in ['(', ')', '[', ']', '{', '}', ',',
                   '+', '-', '*', '/', '%', '^']:
            expr = expr.replace(op, " " + op + " ")
        expr = " " + expr + " "
        for datum in self.data:
            expr = expr.replace(" " + datum + " ",
                                "self.data['" + datum + "']")
        return var.strip(), expr.replace(" ", "")

    def new_data(self, data, cutout):
        """ Generate New Data (maybe using the currently selected array). """
        self.data = {'this': data, 'cutout': cutout}
        self.history.clear()
        while True:
            # Open a dialog to reshape
            self.cmd.setText("")
            self.cmd.setFocus()
            # If "Save" is pressed
            if self.exec_() or self.returnVal is not None:
                if self.data['this'] is None:
                    return (re.split(r"\=", self.lastText)[0].strip(),
                            self.data[self.returnVal])
                if self.cmd.text() == "":
                    return 1, self.data[self.returnVal]
                return str(self.cmd.text()), self.data[self.returnVal]
            return 0, []
