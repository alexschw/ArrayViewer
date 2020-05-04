"""
Slice Selectors for the ArrayViewer
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
from PyQt5.QtGui import QDrag, QRegExpValidator
from PyQt5.QtWidgets import (QApplication, QLabel, QLineEdit, QHBoxLayout, 
                             QVBoxLayout, QWidget)
from PyQt5.QtCore import QRegExp, Qt, QMimeData, QPoint, QSize
import numpy as np

class singleShape(QWidget):
    """ A single Shape widget with one label and one lineedit. """
    def __init__(self, validator, parent, index):
        super(singleShape, self).__init__()
        self.index = index
        self.parent = parent
        self.dock = QWidget()
        self.start = QPoint(0, 0)
        self.setAcceptDrops(True)

        layout = QVBoxLayout()
        self.label = QLabel("0", self.dock)
        layout.addWidget(self.label)
        clayout = QVBoxLayout()
        clayout.addWidget(self.dock)
        self.setLayout(clayout)
        self.dragging = True
        self.dragSty = "singleShape > QWidget { border: 1px solid #0F0; }"
        self.noDragSty = "singleShape > QWidget { border: 0px solid #000; }"

        self.lineedit = QLineEdit(self)
        self.lineedit.setValidator(validator)
        self.lineedit.editingFinished.connect(parent._set_slice)  # TODO
        layout.addWidget(self.lineedit)

        self.dock.setLayout(layout)

    def _perform_operation(self, event):
        """ Perform the chosen Operation on the graph.
        If the field is clicked again the operation will be undone.
        """
        if self.index in self.parent.Graph.set_oprdim(self.index):
            self.label.setStyleSheet("background-color:lightgreen;")
        else:
            self.label.setStyleSheet("")
        self.parent._draw_data()

    def mousePressEvent(self, event):
        """ Catch mousePressEvent for the dragging action. """
        if event.button() == Qt.LeftButton:
            self.start = event.pos()
            self.dragging = False
            event.accept()

    def mouseReleaseEvent(self, event):
        """ Chatch mouseReleaseEvent and perform operation if not dragged. """
        if not self.dragging:
            self._perform_operation(event)
        event.accept()

    def mouseMoveEvent(self, event):
        """ Catch mouseMoveEvent and start dragging when needed. """
        if not self.dragging:
            diff = (event.pos() - self.start).manhattanLength()
            if diff > QApplication.startDragDistance():
                self.dock.setStyleSheet(self.dragSty)
                self.drag = QDrag(self)
                self.drag.setMimeData(QMimeData())
                pixmap = self.dock.grab()
                x, y = (pixmap.width() * 0.8, pixmap.height() * 0.8)
                self.drag.setPixmap(pixmap.scaled(QSize(x, y)))
                self.drag.setHotSpot(QPoint(x/2, y/2))
                self.update()
                self.drag.exec_()
                self.dock.setStyleSheet(self.noDragSty)
                self.dragging = True
        event.accept()

    def dragEnterEvent(self, event):
        """ Catch dragEnterEvents only for other widgets. """
        if not event.source() == self:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """ Catch dropEvents to permute the dimensions. """
        id_from, id_to = event.source().index, self.index
        new_order = np.arange(self.parent[0].ndim)
        new_order[id_from], new_order[id_to] = id_to, id_from
        self.parent.transpose_data(new_order)

class ShapeSelector(QWidget):
    """ Array Shape selectors"""
    def __init__(self, parent=None):
        super(ShapeSelector, self).__init__()
        self.parent = parent
        layout = QHBoxLayout()

        self.maxDims = 6
        self.fixate_view = False

        validator = QRegExpValidator(self)
        rex = r"[+-]?\d*(?::|:\+|:-|)\d*(?::|:\+|:-|)\d*"
        validator.setRegExp(QRegExp(rex))
        for i in range(self.maxDims):
            shape = singleShape(validator, self.parent, i)
            layout.addWidget(shape)
            shape.hide()

        self.setLayout(layout)

    def _get(self, index):
        return self.layout().itemAt(index).widget()

    def current_slice(self):
        """ Return the current slice, """
        curr_slice = []
        # For all (non-hidden) widgets
        for n in range(self.maxDims):
            if self._get(n).isHidden():
                break
            # Get the text and the maximum value within the dimension
            curr_slice.append(self._get(n).label.text())
        return curr_slice

    def get_index(self, widget):
        """ Get the index of one of the subwidgets. """
        for n in range(self.maxDims):
            if self._get(n).layout().indexOf(widget) != -1:
                return n
        return -1

    def get_shape(self):
        """ Get the values of all non-hidden widgets."""
        shapeStr = "["
        scalarDims = []  # scalar Dimensions
        # For all (non-hidden) widgets
        for n in range(self.maxDims):
            if self._get(n).isHidden():
                break
            # Get the text and the maximum value within the dimension
            txt = self._get(n).lineedit.text()
            maxt = int(self._get(n).label.text())
            if txt == "":
                shapeStr += ":,"
            elif ":" in txt:
                shapeStr += txt + ','
            else:
                scalarDims.append(n)
                try:
                    int(txt)
                except ValueError:
                    self.info_msg("Could not convert value to int.", -1)
                    shapeStr += ':,'
                    continue
                if int(txt) >= maxt:
                    txt = str(maxt - 1)
                    self._get(n).lineedit.setText(txt)
                elif int(txt) < -maxt:
                    txt = str(-maxt)
                    self._get(n).lineedit.setText(txt)
                shapeStr += txt + ','
        shapeStr = str(shapeStr[:-1] + "]")
        return shapeStr, scalarDims

    def update_shape(self, shape, load_slice=True):
        """ Update the shape widgets in the window based on the new data. """
        # Show a number of widgets equal to the dimension, hide the others
        for n in range(self.maxDims):
            if n < len(shape):
                self._get(n).show()
            else:
                self._get(n).hide()
            self._get(n).label.setStyleSheet("")
        # Initialize the Values of those widgets. Could not be done previously
        if load_slice:
            curr_slice = self.parent._load_slice()
            self.parent.Prmt.setText(str(list(range(self.parent[0].ndim))))
        else:
            self.parent.Prmt.setText("")
        for n, value in enumerate(shape):
            self._get(n).label.setText(str(value))
            if self.fixate_view:
                pass
            elif load_slice and curr_slice:
                self._get(n).lineedit.setText(curr_slice[n])
            else:
                # Just show the first two dimensions in the beginning
                if n > 1:
                    self._get(n).lineedit.setText("0")
                else:
                    self._get(n).lineedit.clear()
        # Redraw the graph
        self.parent._draw_data()


    def set_operation(self, operation="None"):
        """ Make Dimension-titles (not) clickable and pass the operation. """
        for n in range(self.maxDims):
            self._get(n).label.setStyleSheet("")
        for i in self.parent.Graph.set_operation(operation):
            self._get(i).label.setStyleSheet("background-color:lightgreen;")
        self.parent._draw_data()

    def wheelEvent(self, event):
        """ Catch wheelEvents on the Shape widgets making them scrollable. """
        onField = -1
        for n in range(self.maxDims):
            if self._get(n).lineedit.underMouse():
                onField = n
                break
        if onField < 0:
            return
        from_wgt = self._get(onField).lineedit
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
            try:
                for t in txt:
                    if t != "":
                        int(t)
            except ValueError:
                self.parent.info_msg("Could not convert value to int.", -1)
                return
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
        self.parent._set_slice()
