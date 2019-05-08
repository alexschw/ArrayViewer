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


def flatPad(Arr, padding=1, fill=np.nan):
    """ Flatten ND array into a 2D array and add a padding with given fill """
    # Reshape the array to 3D
    Arr = np.reshape(Arr, Arr.shape[:2] + (-1, ))
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


def getShapeFromStr(string):
    """
    Returns an array with the elements of the string. All brackets are
    removed as well as empty elements in the array.
    """
    return np.array([_f for _f in string.strip("()[]").split(",") if _f], dtype=int)


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
        self._has_cb = False
        self._colormap = 'viridis'
        self._operation = 'None'
        self._opr = (lambda x: x)
        self._oprdim = -1
        self._oprcorr = -1

        # Add a label Text that may be changed in later Versions to display the
        # position and value below the mouse pointer
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._canv)
        self._txt = QLabel(self)
        self._txt.setText('')
        self._layout.addWidget(self._txt)

    def clear(self):
        """ Clear the figure. """
        self._cb = None
        self._figure.clf()

    def figure(self):
        """ Return the local figure variable. """
        return self._figure

    def toggle_colorbar(self):
        """ Toggle the state of the colorbar """
        self._has_cb = not self._has_cb
        self.colorbar()

    def colorbar(self, minmax=None):
        """ Add a colorbar to the graph or remove it, if it is existing. """
        if self._img is None:
            return
        if minmax is not None:
            self._img.set_clim(
                vmin=minmax[0] * (self._clim[1] - self._clim[0])
                + self._clim[0], vmax=minmax[1] * self._clim[1]
            )
        if not self._has_cb:
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

    def set_operation(self, operation="None"):
        """ Set an operation to be performed on click on a dimension. """
        if operation == "None":
            self._oprdim = -1
            self._opr = (lambda x: x)
        else:
            self._opr = (lambda x: eval("np." + operation + "(x, axis="
                                        + str(self._oprcorr) + ")"))
        return self._oprdim

    def renewPlot(self, data, s, scalDims, ui):
        """ Draw given data. """
        ax = self._figure.gca()
        ax.clear()
        # Reset the minimum and maximum text
        ui.txtMin.setText('min :')
        ui.txtMax.setText('max :')
        if data is None:
            return
        elif isinstance(data, self.noPrintTypes):
            # Print strings or lists of strings to the graph directly
            ax.text(0.0, 1.0, data)
            ax.axis('off')
        elif isinstance(data[0], list):
            # If there is an array of lists print each element as a graph
            for lst in data:
                ax.plot(lst)
        else:
            # Cut out the chosen piece of the array and plot it
            cutout = np.array([])
            cutout = eval("data%s.squeeze()"%s)
            if self._oprdim != -1 and self._oprdim not in scalDims:
                self._oprcorr = self._oprdim - (scalDims<=self._oprdim).sum()
                cutout = self._opr(cutout)
            # Transpose the first two dimensions if it is chosen
            if ui.Transp.checkState() and cutout.ndim > 1:
                cutout = np.swapaxes(cutout, 0, 1)
            # Graph an 1D-cutout
            if cutout.ndim == 0:
                ax.set_ylim([0, 1])
                ax.text(0, 1.0, cutout)
                ax.axis('off')
            if cutout.ndim == 1:
                ax.plot(cutout)
                alim = ax.get_ylim()
                if alim[0] > alim[1]:
                    ax.invert_yaxis()
            # 2D-cutout will be shown using imshow or plot
            elif cutout.ndim == 2:
                if ui.Plot2D.checkState():
                    ax.plot(cutout)
                else:
                    self._img = ax.imshow(cutout, interpolation='none',
                                          aspect='auto')
                # Calculate the ticks for the plot by checking the limits
                limits = [l.split(':') for l in s[1:-1].split(',') if ':' in l]
                lim = np.array([l if len(l)==3 else l+['1'] for l in limits])
                lim[lim == ''] = '0'
                lim = lim.astype(float)
                if not ui.Transp.checkState():
                    lim = lim[(1,0),:]
                # Set the x-ticks
                loc = ax.xaxis.get_major_locator()()
                d = (np.arange(len(loc))-1)*(loc[2] - loc[1])*lim[0,2]+lim[0,0]
                if all(d.astype(int) == d.astype(float)):
                    ax.set_xticklabels(d.astype(int))
                else:
                    ax.set_xticklabels(d.astype(float))
                # Set the y-ticks
                loc = ax.yaxis.get_major_locator()()
                d = (np.arange(len(loc))-1)*(loc[2] - loc[1])*lim[1,2]+lim[1,0]
                if all(d.astype(int) == d.astype(float)):
                    ax.set_yticklabels(d.astype(int))
                else:
                    ax.set_yticklabels(d.astype(float))
            # higher-dimensional cutouts will first be flattened
            elif cutout.ndim >= 3:
                nPad = cutout.shape[0] // 100 + 1
                dat = flatPad(cutout, nPad)
                self._img = ax.imshow(dat, interpolation='none', aspect='auto')
                ax.xaxis.set_major_locator(TickMultLoc(cutout.shape[0] + nPad))
                ax.yaxis.set_major_locator(TickMultLoc(cutout.shape[1] + nPad))
            # Reset the colorbar. A better solution would be possible, if the
            # axes were not cleared everytime.
            self.colorbar()
            self.colormap()
            if cutout.size > 0:
                self._clim = (cutout.min(), cutout.max())
                # Set the minimum and maximum values from the data
                ui.txtMin.setText('min :' + "%0.5f"%cutout.min())
                ui.txtMax.setText('max :' + "%0.5f"%cutout.max())
        self._canv.draw()


class ReshapeDialog(QDialog):
    """ A Dialog for Reshaping the Array. """
    def __init__(self, parent=None):
        """ Initialize. """
        super(ReshapeDialog, self).__init__(parent)

        # Setup the basic window
        self.resize(400, 150)
        self.setWindowTitle("Reshape the current array")
        self.prodShape = 0
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
        self.txtNew.textEdited.connect(self.keyPress)
        self.shCmpl = QCompleter([])
        self.shCmpl.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.txtNew.setCompleter(self.shCmpl)
        gridLayout.addWidget(self.txtNew, 1, 1, 1, 1)

        # Add a button Box with "OK" and "Cancel"-Buttons
        self.buttonBox = DBB(DBB.Cancel|DBB.Ok, QtCore.Qt.Horizontal)
        gridLayout.addWidget(self.buttonBox, 3, 1, 1, 1)
        self.buttonBox.button(DBB.Cancel).clicked.connect(self.reject)
        self.buttonBox.button(DBB.Ok).clicked.connect(self.accept)

    def keyPress(self, keyEv):
        """ Whenever a key is pressed check for comma and set autofill data."""
        if keyEv and keyEv[-1] == ',':
            shape = getShapeFromStr(str(keyEv))
            if self.prodShape%shape.prod() == 0:
                rest = self.prodShape // shape.prod()
                self.shCmpl.model().setStringList(self.suggestion(keyEv, rest))
            else:
                self.shCmpl.model().setStringList([keyEv + " Not fitting"])
        return keyEv

    def suggestion(self, previous_val, value):
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
                    data = np.reshape(data, getShapeFromStr(sStr))
                # If it could not be reshaped, get another user input
                except ValueError:
                    print("Data could not be reshaped!")
                    continue
                return data
            # If "CANCEL" is pressed
            else:
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
        label.setText("Use 'this' to reference the current data\nBefore saving enter the variable you want to save. \nOtherwise the original data will be overwritten.")
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
        self.buttonBox.button(DBB.Ok).clicked.connect(self.on_accept)
        self.buttonBox.button(DBB.Save).clicked.connect(self.on_save)

    def parsecmd(self, cmd):
        """ Parse the command given by the user. """
        try:
            var, expr = cmd.split("=")
        except ValueError:
            raise(ValueError("No '=' in expression"))
        for op in ['(', ')', '[', ']', '{', '}', ',',
                   '+', '-', '*', '/', '%', '^']:
            expr = expr.replace(op, " " + op + " ")
        expr = " " + expr + " "
        for datum in self.data:
            expr = expr.replace(" " + datum + " ",
                                "self.data['" + datum + "']")
        return var.strip(), expr.replace(" ", "")

    def on_accept(self):
        """ Try to run the command and append the history on pressing 'OK'. """
        try:
            var, value = self.parsecmd(str(self.cmd.text()))
            self.data[var] = eval(value)
        except Exception as err:
            self.err.setText(str(err))
            return -1
        self.history.append(self.cmd.text())
        self.lastText = str(self.cmd.text())
        self.cmd.setText("")

    def on_save(self):
        """ Return the object currently in the textBox to the Viewer. """
        if re.findall(r"\=", self.cmd.text()):
            return -1
        elif self.cmd.text() == "":
            self.returnVal = re.split(r"\=", self.lastText)[0].strip()
            self.accept()
        else:
            self.returnVal = self.cmd.text().strip()
            if self.returnVal is not None:
                self.accept()
            else:
                return -1

    def newData(self, data):
        """ Generate New Data (maybe using the currently selected array). """
        self.data = {'this': data}
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
                elif self.cmd.text() == "":
                    return 1, self.data[self.returnVal]
                else:
                    return str(self.cmd.text()), self.data[self.returnVal]
            else:
                return 0, []
