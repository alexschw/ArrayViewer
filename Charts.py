"""
# GraphWidget and ReshapeDialog for the ArrayViewer
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
"""
from PyQt4.QtCore import Qt, QObject, SIGNAL
from PyQt4.QtGui import QSizePolicy as QSP
from PyQt4.QtGui import QDialogButtonBox as QDBB
from PyQt4.QtGui import QWidget, QVBoxLayout, QLabel, QDialog, QGridLayout, QLineEdit
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np

def flat_with_padding(Arr, padding=1, fill=np.nan):
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

class GraphWidget(QWidget):
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

        # Add a label Text that may be changed in later Versions to display the
        # position and value below the mouse pointer
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._canvas)
        self._txt = QLabel(self)
        self._txt.setText('')
        self._layout.addWidget(self._txt)

    def clear(self):
        """ Clear the figure """
        self._figure.clf()

    def figure(self):
        """ Return the local figure variable """
        return self._figure

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
                ax.imshow(cutout, interpolation='none', aspect='auto')
            # higher-dimensional cutouts will first be flattened
            elif cutout.squeeze().ndim >= 3:
                ax.imshow(flat_with_padding(cutout), interpolation='none', aspect='auto')
            # Set the minimum and maximum values from the data
            ui.txtMin.setText('min :' + "%0.5f"%cutout.min())
            ui.txtMax.setText('max :' + "%0.5f"%cutout.max())
        self._canvas.draw()

class ReshapeDialog(QDialog):
    """ A Dialog for Reshaping the Array """
    def __init__(self, parent=None):
        super(ReshapeDialog, self).__init__(parent)

        # Setup the basic window
        self.resize(400, 150)
        self.setWindowTitle("Reshape the current array")
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
        gridLayout.addWidget(self.txtNew, 1, 1, 1, 1)

        # Add a button Box with "OK" and "Cancel"-Buttons
        self.buttonBox = QDBB(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDBB.Cancel|QDBB.Ok)
        gridLayout.addWidget(self.buttonBox, 3, 1, 1, 1)
        QObject.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
        QObject.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)

    def reshape_array(self, data):
        """ Reshape the currently selected array """
        while True:
            # Open a dialog to reshape
            self.txtCurrent.setText(str(data.shape))
            self.txtNew.setText("")
            # If "OK" is pressed
            if data.shape and self.exec_():
                # Get the shape sting and split it
                sStr = str(self.txtNew.text())
                shape = np.array(sStr.strip("()[]").split(","), dtype=int)
                # Try if the array could be reshaped that way
                try:
                    data = np.reshape(data, shape)
                # If it could not be reshaped, get another user input
                except ValueError:
                    continue
                return data
            # If "CANCEL" is pressed
            else:
                return data
