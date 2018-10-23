import sys
from PyQt4 import QtGui, QtCore


class rangeSlider(QtGui.QWidget):
    """ Combination of two sliders that return a range tuple """
    sliderReleased = QtCore.pyqtSignal()

    def __init__(self, parent=None, minmax=[0, 1]):
        """ Initialize the Slider """
        super(rangeSlider, self).__init__(parent)
        # Set internal variables
        self._nSteps = 100
        self._minVal = minmax[0]
        self._scaling = 1.0 * (minmax[1] - minmax[0]) / self._nSteps
        # Setup the (sub-)widgets
        self.minSlide = QtGui.QSlider(self)
        self.maxSlide = QtGui.QSlider(self)
        self.minSlide.setRange(0, self._nSteps)
        self.maxSlide.setRange(0, self._nSteps)
        self.minSlide.setTickPosition(self.minSlide.TicksRight)
        self.maxSlide.setTickPosition(self.maxSlide.TicksLeft)
        self.minSlide.setSliderPosition(0)
        self.maxSlide.setSliderPosition(self._nSteps)
        self.minSlide.setSingleStep(1)
        self.maxSlide.setSingleStep(1)
        self.minSlide.setTickInterval(self._nSteps / 10)
        self.maxSlide.setTickInterval(self._nSteps / 10)
        self.minSlide.valueChanged.connect(self.minRestict)
        self.maxSlide.valueChanged.connect(self.maxRestict)
        self.Layout = QtGui.QHBoxLayout(self)
        self.Layout.setSpacing(0)
        self.Layout.addWidget(self.minSlide)
        self.Layout.addWidget(self.maxSlide)
        # Signals
        self.minSlide.sliderReleased.connect(self.sliderReleased.emit)
        self.maxSlide.sliderReleased.connect(self.sliderReleased.emit)

    @QtCore.pyqtSlot()
    def value(self):
        """ Returns a tuple of the current value of both sliders """
        return (self.minSlide.value() * self._scaling + self._minVal,
                self.maxSlide.value() * self._scaling + self._minVal)

    def print_val(self):
        """ Prints the tuple of the current value of both sliders """
        print self.value()

    def maxRestict(self, value):
        """ Restricts the maximum slider to be more than the minimum slider """
        if value < self.minSlide.value() + 1:
            self.maxSlide.setSliderPosition(self.minSlide.value() + 1)

    def minRestict(self, value):
        """ Restricts the minimum slider to be less than the maximum slider """
        if value > self.maxSlide.value() - 1:
            self.minSlide.setSliderPosition(self.maxSlide.value() - 1)


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = QtGui.QMainWindow()
    window.resize(100, 600)
    window.setWindowTitle("")
    CWgt = QtGui.QWidget(window)
    window.setCentralWidget(CWgt)
    QFra = QtGui.QVBoxLayout(CWgt)
    rangeSld = rangeSlider(window, [-1, 1])
    QFra.addWidget(rangeSld)
    pushBtn = QtGui.QPushButton()
    rangeSld.sliderReleased.connect(rangeSld.print_val)
    QFra.addWidget(pushBtn)
    window.show()
    app.exec_()
