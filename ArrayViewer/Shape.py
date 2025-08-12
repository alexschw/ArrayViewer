"""
Slice Selectors for the ArrayViewer
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
from PyQt5.QtGui import QDrag, QRegExpValidator
from PyQt5.QtWidgets import (QApplication, QLabel, QLineEdit, QHBoxLayout,
                             QVBoxLayout, QWidget)
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QMimeData, QPoint, QRegExp,
                          QSize, Qt)
import numpy as np


class singleShape(QWidget):
    """ A single Shape widget with one label and one lineedit. """
    change_animation = pyqtSignal(int)
    change_operation = pyqtSignal(int)

    def __init__(self, validator, parent, index):
        super().__init__()
        self.index = index
        self.parent = parent.parent
        self.dock = QWidget()
        self.start = QPoint(0, 0)
        self.setAcceptDrops(True)

        layout = QVBoxLayout()
        self.label = QLabel()
        layout.addWidget(self.label)
        clayout = QVBoxLayout()
        clayout.addWidget(self.dock)
        clayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(clayout)
        self.dragging = True
        self.dragSty = "singleShape > QWidget { border: 1px solid #0F0; }"
        self.noDragSty = "singleShape > QWidget { border: 0px solid #000; }"

        self.lineedit = QLineEdit(self)
        self.lineedit.setValidator(validator)
        self.lineedit.editingFinished.connect(self.parent._set_slice)
        layout.addWidget(self.lineedit)

        self.dock.setLayout(layout)

    @pyqtSlot(np.ndarray, int)
    def style(self, operations, animation):
        """ Set the style of the label based on the operation or animation. """
        if self.index == animation:
            self.label.setStyleSheet("background-color:orange;")
        elif self.index in operations:
            self.label.setStyleSheet("background-color:lightgreen;")
        else:
            self.label.setStyleSheet("")

    def get_value(self):
        """ Return the values of this single Shape. """
        def clipint(x):
            """ The integer value of a string clipped to the dimensions """
            return min(max(-maxt, int(x)), maxt - 1)
        # Get the text and the maximum value within the dimension
        txt = self.lineedit.text()
        maxt = int(self.label.text())

        try:
            # Clip the value of the given text if it is an integer
            txt = str(clipint(txt))
            self.lineedit.setText(txt)
            return int(txt), True
        except ValueError:
            if "," in txt:
                tpl = tuple(dict.fromkeys(clipint(x) for x in txt.split(',') if x))
                self.lineedit.setText(str(tpl)[1:-1].replace(" ", ""))
                return tpl, False
            return slice(*(int(x) if x else None for x in txt.split(':'))), False

    def _perform_operation(self, _):
        """
        Perform the chosen Operation on the graph. If the field is clicked
        again the operation will be undone.
        """
        self.change_operation.emit(self.index)
        self.parent._set_slice()

    def mousePressEvent(self, event):
        """ Catch mousePressEvent for the dragging action. """
        if event.button() == Qt.LeftButton:
            self.start = event.pos()
            self.dragging = False
            event.accept()

    def mouseReleaseEvent(self, event):
        """ Chatch mouseReleaseEvent and perform operation if not dragged. """
        if event.button() == Qt.RightButton:
            self.change_animation.emit(self.index)
        elif not self.dragging:
            self._perform_operation(event)
        event.accept()

    def mouseMoveEvent(self, event):
        """ Catch mouseMoveEvent and start dragging when needed. """
        if not self.dragging:
            diff = (event.pos() - self.start).manhattanLength()
            if diff > QApplication.startDragDistance():
                self.dock.setStyleSheet(self.dragSty)
                drag = QDrag(self)
                drag.setMimeData(QMimeData())
                pixmap = self.dock.grab()
                x, y = (int(pixmap.width() * 0.8), int(pixmap.height() * 0.8))
                drag.setPixmap(pixmap.scaled(QSize(x, y)))
                drag.setHotSpot(QPoint(x // 2, y // 2))
                self.update()
                drag.exec_()
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
        new_order = np.arange(self.parent.get(0).ndim)
        new_order[id_from], new_order[id_to] = id_to, id_from
        self.parent.transpose_data(new_order)


class ShapeSelector(QWidget):
    """ Array Shape selectors"""
    state_changed = pyqtSignal(np.ndarray, int)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.max_dims = 8
        self.active_dims = 0
        self.fixate_view = False
        self.operation_state = np.array([], dtype=int)
        self.animation_state = -1

        validator = QRegExpValidator(self)
        rex = r"(?:[+-]?\d+,)+\d*|([+-]?\d*(?::|:\+|:-|)\d*(?::|:\+|:-|)\d*)"
        validator.setRegExp(QRegExp(rex))
        for i in range(self.max_dims):
            shape = singleShape(validator, self, i)
            layout.addWidget(shape)
            self.state_changed.connect(shape.style)
            shape.change_animation.connect(self.change_animation_state)
            shape.change_operation.connect(self.change_operation_state)
            shape.hide()

        self.setLayout(layout)

    def _get(self, index):
        return self.layout().itemAt(index).widget()

    @pyqtSlot(int)
    def change_animation_state(self, index):
        """ Change the animation_state of indexed Shape. """
        if self.animation_state != -1:  # Was already animated. Turn off.
            self.parent.Graph.stop_animation()
        if self.animation_state == index:  # same dimension clicked twice
            self.animation_state = -1
            self.parent._draw_data()
        else:  # new dimension to be animated
            self.animation_state = index
            self.parent.Graph.start_animation(index)
        self.state_changed.emit(self.operation_state, self.animation_state)

    @pyqtSlot(int)
    def change_operation_state(self, index):
        """ Change the operation_state of the indexed Shape. """
        self.operation_state = self.parent.Graph.set_oprdim(index)
        self.animation_state = -1
        self.state_changed.emit(self.operation_state, self.animation_state)

    def current_slice(self):
        """ Return the current slice, """
        return [self._get(n).lineedit.text() for n in range(self.active_dims)]

    def get_index(self, widget):
        """ Get the index of one of the subwidgets. """
        for n in range(self.max_dims):
            if self._get(n).layout().indexOf(widget) != -1:
                return n
        return -1

    def get_shape(self):
        """ Get the values of all non-hidden widgets."""
        shapeStr = []
        scalarDims = []  # scalar Dimensions
        # For all (non-hidden) widgets
        for n in range(self.active_dims):
            val, isScalar = self._get(n).get_value()
            if isScalar:
                scalarDims.append(n)
            shapeStr.append(val)
        return tuple(shapeStr), np.array(scalarDims, dtype=int)

    def update_shape(self, shape, load_slice=True):
        """ Update the shape widgets in the window based on the new data. """
        # Show a number of widgets equal to the dimension, hide the others
        self.active_dims = len(shape)
        for n in range(self.max_dims):
            if n < self.active_dims:
                self._get(n).show()
            else:
                self._get(n).hide()
            self._get(n).label.setStyleSheet("")
        # Initialize the Values of those widgets. Could not be done previously
        if load_slice:
            curr_slice, curr_operations = self.parent._load_slice()
            if not self.fixate_view:
                if not curr_operations is None and len(curr_operations) > 0:
                    self.operation_state = curr_operations
                    self.parent.Graph.set_oprdim(curr_operations)
                else:
                    self.operation_state = np.empty(0)
            self.parent.Prmt.setText(str(list(range(self.parent.get(0).ndim))))
        else:
            self.parent.Prmt.setText("")
        for n, value in enumerate(shape):
            self._get(n).label.setText(str(value))
            if self.fixate_view:
                pass
            elif load_slice and not curr_slice is None:
                self._get(n).lineedit.setText(curr_slice[n])
            else:
                # Just show the first two dimensions in the beginning
                if n > 1:
                    self._get(n).lineedit.setText("0")
                else:
                    self._get(n).lineedit.clear()
        # Redraw the graph
        self.state_changed.emit(self.operation_state, -1)
        self.parent._draw_data()

    def set_all_values(self, new_values):
        """ Set all selected values """
        for n, value in enumerate(new_values):
            self._get(n).lineedit.setText(f"{value}")
        self.parent._draw_data()

    def set_non_scalar_values(self, new_values):
        """ Set the values of the non-scalar dimensions. """
        sh, scalar_dims = self.get_shape()
        scalar_dims = np.concatenate((scalar_dims, self.operation_state))
        if len(sh) - len(scalar_dims) != len(new_values):
            return
        i = 0
        for n, _ in enumerate(sh):
            if n not in scalar_dims:
                self._get(n).lineedit.setText(f"{new_values[i]}")
                i += 1
        self.parent._draw_data()

    def set_operation(self, operation="None"):
        """ Make Dimension-titles (not) clickable and pass the operation. """
        for n in range(self.max_dims):
            self._get(n).label.setStyleSheet("")
        self.operation_state = self.parent.Graph.set_operation(operation)
        for i in self.operation_state:
            self._get(i).label.setStyleSheet("background-color:lightgreen;")
        self.parent._draw_data()

    def wheelEvent(self, event):
        """ Catch wheelEvents on the Shape widgets making them scrollable. """
        onField = -1
        for n in range(self.active_dims):
            if self._get(n).lineedit.underMouse():
                onField = n
                break
        if onField < 0:
            return
        from_wgt = self._get(onField).lineedit
        txt = from_wgt.text()
        if "," in txt:
            return
        modifiers = QApplication.keyboardModifiers()
        mod = np.sign(event.angleDelta().y())
        if modifiers & Qt.ControlModifier:
            mod *= 10
        elif modifiers & Qt.ShiftModifier:
            mod *= 100
        try:
            from_wgt.setText(str(int(txt) + mod))
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
            if (len(txt) == 2 and txt[1] != "" and modifiers & Qt.ShiftModifier
                and modifiers & Qt.ControlModifier):
                mod //= 10
                mod *= int(txt[1]) - int(txt[0])
            if (len(txt) == 3 and txt[2] != "" and modifiers & Qt.ShiftModifier
                and modifiers & Qt.ControlModifier):
                mod //= 100
                mod *= int(txt[2])
            if txt[0] != "":
                txt[0] = str(int(txt[0]) + mod)
            if txt[1] != "":
                txt[1] = str(int(txt[1]) + mod)
            from_wgt.setText(':'.join(txt))
        self.parent._set_slice()
