"""
# GraphWidget and ReshapeDialog for the ArrayViewer
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
"""
import re
import numpy as np
from PyQt4.QtGui import QSizePolicy as QSP
from PyQt4.QtGui import QDialogButtonBox as DBB
from PyQt4 import QtGui, QtCore
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator as TickMultLoc

def flatPad(Arr, padding=1, fill=np.nan):
    """ Flatten ND array into a 2D array and add a padding with given fill """
    # Reshape the array to 3D
    Arr = np.reshape(Arr, Arr.shape[:2]+(-1, ))
    # Get the most equal division of the last dimension
    for n in xrange(int(np.sqrt(Arr.shape[2])), Arr.shape[2]+1):
        if Arr.shape[2]%n == 0:
            rows = Arr.shape[2]/n
            break
    # Add the padding to the right and bottom of the arrays
    A0 = np.ones([padding, Arr.shape[1], Arr.shape[2]])*fill
    A1 = np.ones([Arr.shape[0]+padding, padding, Arr.shape[2]])*fill
    pArr = np.append(np.append(Arr, A0, axis=0), A1, axis=1)
    # Stack the arrays according to the precalculated number of rows
    pA2D = np.hstack(np.split(np.hstack(pArr.T).T, rows)).T
    # Add the padding to the left and top of the arrays
    A0 = np.ones([padding, pA2D.shape[1]])*fill
    A1 = np.ones([pA2D.shape[0]+padding, padding])*fill
    pA2D = np.append(A1, np.append(A0, pA2D, axis=0), axis=1)
    return pA2D

def getShapeFromStr(string):
    """
    Returns an array with the elements of the string. All brackets are
    removed as well as empty elements in the array.
    """
    return np.array(filter(None, string.strip("()[]").split(",")), dtype=int)

class GraphWidget(QtGui.QWidget):
    """ Draws the data graph """
    def __init__(self, parent=None):
        """Initialize the figure. """
        super(GraphWidget, self).__init__(parent)

        # Setup the canvas, figure and axes
        self._figure = Figure(facecolor='white')
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.ax = self._figure.add_axes([.15, .15, .75, .75])
        self._canvas.canvas = self._canvas.ax.figure.canvas
        self._canvas.setSizePolicy(QSP.Expanding, QSP.Expanding)
        self._clim = (0, 1)
        self._img = None
        self._cb = None

        # Add a label Text that may be changed in later Versions to display the
        # position and value below the mouse pointer
        self._layout = QtGui.QVBoxLayout(self)
        self._layout.addWidget(self._canvas)
        self._txt = QtGui.QLabel(self)
        self._txt.setText('')
        self._layout.addWidget(self._txt)

    def clear(self):
        """ Clear the figure """
        if self._cb is not None:
            self._cb.remove()
            self._cb = None
        self._figure.clf()

    def figure(self):
        """ Return the local figure variable """
        return self._figure

    def colorbar(self, minmax=None):
        """ Add a colorbar to the graph or remove it, if it is existing """
        if self._img is None:
            return
        if self._cb is None:
            self._cb = self._figure.colorbar(self._img)
        else:
            if minmax != None:
                self._cb.set_clim(vmin=minmax[0]*(self._clim[1]-self._clim[0])+self._clim[0],
                                  vmax=minmax[1]*self._clim[1])
                self._cb.draw_all()
            else:
                self._cb.remove()
                self._cb = None
        self._canvas.draw()

    def renewPlot(self, data, shape_str, ui):
        """ Draw given data. """
        ax = self._figure.gca()
        ax.clear()
        # Reset the minimum and maximum text
        ui.txtMin.setText('min :')
        ui.txtMax.setText('max :')
        if isinstance(data, (str, unicode, list, float, int)):
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
            exec("cutout = data%s"%shape_str)
            # Transpose the first two dimensions if it is chosen
            if ui.Transp.checkState():
                cutout = np.swapaxes(cutout, 0, 1)
            # Graph an 1D-cutout
            if cutout.squeeze().ndim == 0:
                ax.set_ylim([0, 1])
                ax.text(0, 1.0, cutout)
                ax.axis('off')
            if cutout.squeeze().ndim == 1:
                ax.plot(cutout)
                alim = ax.get_ylim()
                if alim[0] > alim[1]:
                    ax.invert_yaxis()
            # 2D-cutout will be shown using imshow
            elif cutout.squeeze().ndim == 2:
                self._img = ax.imshow(cutout, interpolation='none', aspect='auto')
            # higher-dimensional cutouts will first be flattened
            elif cutout.squeeze().ndim >= 3:
                nPad = cutout.shape[0] // 100 + 1
                dat = flatPad(cutout, nPad)
                self._img = ax.imshow(dat, interpolation='none', aspect='auto')
                ax.xaxis.set_major_locator(TickMultLoc(cutout.shape[0]+nPad))
                ax.yaxis.set_major_locator(TickMultLoc(cutout.shape[1]+nPad))
            # Reset the colorbar. A better solution would be possible, if the
            # axes were not cleared everytime.
            self.colorbar()
            self.colorbar()
            self._clim = (cutout.min(), cutout.max())
            # Set the minimum and maximum values from the data
            ui.txtMin.setText('min :' + "%0.5f"%cutout.min())
            ui.txtMax.setText('max :' + "%0.5f"%cutout.max())
        self._canvas.draw()

class ReshapeDialog(QtGui.QDialog):
    """ A Dialog for Reshaping the Array """
    def __init__(self, parent=None):
        super(ReshapeDialog, self).__init__(parent)

        # Setup the basic window
        self.resize(400, 150)
        self.setWindowTitle("Reshape the current array")
        self.prodShape = 0
        gridLayout = QtGui.QGridLayout(self)

        # Add the current and new shape boxes and their labels
        curShape = QtGui.QLabel(self)
        curShape.setText("current shape")
        gridLayout.addWidget(curShape, 0, 0, 1, 1)
        self.txtCurrent = QtGui.QLineEdit(self)
        self.txtCurrent.setEnabled(False)
        gridLayout.addWidget(self.txtCurrent, 0, 1, 1, 1)
        newShape = QtGui.QLabel(self)
        newShape.setText("new shape")

        gridLayout.addWidget(newShape, 1, 0, 1, 1)
        self.txtNew = QtGui.QLineEdit(self)
        self.txtNew.textEdited.connect(self.keyPress)
        self.shCmpl = QtGui.QCompleter([])
        self.shCmpl.setCompletionMode(QtGui.QCompleter.InlineCompletion)
        self.txtNew.setCompleter(self.shCmpl)
        gridLayout.addWidget(self.txtNew, 1, 1, 1, 1)

        # Add a button Box with "OK" and "Cancel"-Buttons
        self.buttonBox = DBB(DBB.Cancel|DBB.Ok, QtCore.Qt.Horizontal)
        gridLayout.addWidget(self.buttonBox, 3, 1, 1, 1)
        self.buttonBox.button(DBB.Cancel).clicked.connect(self.reject)
        self.buttonBox.button(DBB.Ok).clicked.connect(self.accept)

    def keyPress(self, keyEv):
        """ Whenever a key is pressed check for comma and set autofill data"""
        if keyEv and keyEv[-1] == ',':
            shape = getShapeFromStr(str(keyEv))
            if self.prodShape%shape.prod() == 0:
                rest = self.prodShape/shape.prod()
                self.shCmpl.model().setStringList([keyEv+str(rest)])
            else:
                self.shCmpl.model().setStringList([keyEv+" Not fitting"])
        return keyEv

    def reshape_array(self, data):
        """ Reshape the currently selected array """
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
                    print "Data could not be reshaped!"
                    continue
                return data
            # If "CANCEL" is pressed
            else:
                return data

class NewDataDialog(QtGui.QDialog):
    """ A Dialog for Creating new Data """
    def __init__(self, parent=None):
        super(NewDataDialog, self).__init__(parent)

        # Setup the basic window
        self.resize(400, 150)
        self.setWindowTitle("Create new data or change the current one")
        Layout = QtGui.QVBoxLayout(self)
        self.data = []
        self.lastText = ""

        # Add the current and new shape boxes and their labels
        label = QtGui.QLabel(self)
        label.setText("Use self.data to reference the current data")
        Layout.addWidget(label)
        self.history = QtGui.QTextEdit(self)
        self.history.setEnabled(False)
        Layout.addWidget(self.history)
        self.cmd = QtGui.QLineEdit(self)
        Layout.addWidget(self.cmd)
        self.err = QtGui.QLineEdit(self)
        self.err.setEnabled(False)
        self.err.setStyleSheet("color: rgb(255, 0, 0);")
        Layout.addWidget(self.err)

        # Add a button Box with "OK" and "Cancel"-Buttons
        self.buttonBox = DBB(DBB.Cancel|DBB.Ok|DBB.Save, QtCore.Qt.Horizontal)
        Layout.addWidget(self.buttonBox)
        self.buttonBox.button(DBB.Cancel).clicked.connect(self.reject)
        self.buttonBox.button(DBB.Ok).clicked.connect(self.on_accept)
        self.buttonBox.button(DBB.Save).clicked.connect(self.on_save)

    def on_accept(self):
        """ Try to run the command and append the history on pressing 'OK' """
        try:
            exec("self."+str(self.cmd.text()))
        except Exception as err:
            self.err.setText(err.message)
            self.cmd.setText("")
            return -1
        self.history.append(self.cmd.text())
        self.lastText = str(self.cmd.text())
        self.cmd.setText("")

    def on_save(self):
        """ Return the object currently in the textBox to the Viewer """
        if re.findall(r"\=", self.cmd.text()):
            return -1
        elif self.cmd.text() == "":
            exec("self.returnVal = self.%s"%re.split(r"\=", self.lastText)[0])
            self.accept()
        else:
            exec("self.returnVal = self.%s"%self.cmd.text())
            self.accept()

    def newData(self, data):
        """ Generate New Data (maybe using the currently selected array) """
        self.data = data
        self.history.clear()
        while True:
            # Open a dialog to reshape
            self.cmd.setText("")
            # If "Save" is pressed
            if self.exec_():
                if self.cmd.text() == "":
                    return 1, self.returnVal
                else:
                    return str(self.cmd.text()), self.returnVal
            else:
                return 0, []
