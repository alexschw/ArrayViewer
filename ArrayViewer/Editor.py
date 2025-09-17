"""
Editor for the ArrayViewer
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
import sys
import numpy as np
from PyQt5.QtWidgets import (QDialog, QMainWindow, QApplication, QPushButton,
                             QSpinBox, QTableView, QVBoxLayout, QHBoxLayout)
from PyQt5.QtCore import Qt, QAbstractTableModel, QRegExp, QVariant, pyqtSlot
from PyQt5.QtGui import QRegExpValidator


class dataModel(QAbstractTableModel):
    """ Custom Data Model for the Editor Table. """
    def __init__(self, _data, parent=None):
        QAbstractTableModel.__init__(self, parent.table)
        self._data = _data
        self.dataChanged.connect(parent.data_changed)

    def flags(self, index):
        """ Set the enabled and editable flags at the given index. """
        if not index.isValid():
            return Qt.ItemIsEnabled
        return QAbstractTableModel.flags(self, index) | Qt.ItemIsEditable

    def rowCount(self, _):
        """ Returns the number of rows. """
        return self._data.shape[0]

    def columnCount(self, _):
        """ Returns the number of columns. """
        if len(self._data.shape) < 2:
            return 1
        return self._data.shape[1]

    def setData(self, index, value, role=Qt.EditRole):
        """ Change the value of a single datum at the given index. """
        if role != Qt.EditRole:
            return False
        try:
            if self._data.dtype == int:
                self._data[index.row(), index.column()] = int(float(value))
            else:
                self._data[index.row(), index.column()] = value
            self.dataChanged.emit(index, index)
            return True
        except ValueError:
            return False

    def set_full_data(self, data, changes):
        """ Reset the full data of the dataModel. """
        self.beginResetModel()
        self._data = np.array(data, ndmin=2)
        for key, value in changes.items():
            if len(key) == 1:
                key = (0,) + key
            self._data[key] = value
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        """ Returns a datum at the given index. """
        # Precise values for editing
        if index.isValid() and role == Qt.EditRole:
            return QVariant(str(self._data[index.row()][index.column()]))
        # Shortened values for general display
        if index.isValid() and role == Qt.DisplayRole:
            return QVariant(f"{self._data[index.row()][index.column()]:.5g}")
        # Empty Field otherwise
        return QVariant()


class SpinBox(QSpinBox):
    """ Spinner Box with empty value. """
    def __init__(self, parent, index):
        super().__init__()
        self.validator = QRegExpValidator(QRegExp(r"^[0-9]*|\s?"))
        self.setMinimum(-1)
        self.setSpecialValueText(" ")
        self.index = index
        if index < 2:
            self.setValue(-1)
        self.valueChanged.connect(lambda x: parent.spin_box_change(self, x))

    def validate(self, text, pos):
        """ Overload the internal validator to allow empty strings as input """
        return self.validator.validate(text, pos)

    def valueFromText(self, txt):
        """ Overload to return -1 on empty string """
        if not txt.strip():
            return -1
        return int(txt)


class EditorDialog(QDialog):
    """ A dialog to edit data. """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.original_data = None
        self.changed_data = {}
        self.resize(600, 400)
        QFra = QVBoxLayout(self)

        self.table = QTableView()
        self.model = dataModel(np.empty((1, 1)), self)
        self.table.setModel(self.model)
        QFra.addWidget(self.table)

        self.dims = QHBoxLayout()
        self.max_dims = 8
        self.slice = []
        for n in range(self.max_dims):
            self.dims.addWidget(SpinBox(self, n))
        QFra.addLayout(self.dims)

        pushBtn = QPushButton("Save changes")
        pushBtn.clicked.connect(self.save_data)
        QFra.addWidget(pushBtn)

    def open_editor(self, data):
        """ Open the window to edit the currently selected data object """
        if type(data) in self.parent.noPrintTypes:
            return
        for s in range(self.max_dims):
            if self.dims.itemAt(s) is None or self.dims.itemAt(s).widget() is None:
                continue
            if s < data.ndim:
                self.dims.itemAt(s).widget().setValue(-1 * int(s < 2))
                self.dims.itemAt(s).widget().setVisible(True)
                self.dims.itemAt(s).widget().setMaximum(data.shape[s]-1)
            else:
                self.dims.itemAt(s).widget().setVisible(False)
        self.original_data = data
        self.changed_data = {}
        if data.ndim == 1:
            self.slice = [slice(None)]
        else:
            self.slice = [slice(None)]*2 + [0]*(data.ndim-2)
        self.model.set_full_data(data[(*self.slice,)], self.local_changes())
        self.table.resizeColumnsToContents()

        self.exec_()

    def save_data(self):
        """ Save the changed dataset to the original data object """
        # Only set data if it has changed.
        if not self.changed_data:
            return
        for location, value in self.changed_data.items():
            self.original_data[location] = value
        if self.original_data.ndim == 2 and self.original_data.shape[0] == 1:
            # Squeeze dimension 0 if it was generated from 1d array
            self.original_data = self.original_data.squeeze(0)
        self.parent.set_data(0, self.original_data)
        self.parent._draw_data()
        self.original_data = None
        # Close the window
        self.accept()

    def local_changes(self):
        """ Returns only localized changes of the current slice """
        loc_changes = {}
        for key, value in self.changed_data.items():
            if all(x == y or isinstance(y, slice) for x, y in zip(key, self.slice)):
                l_key = tuple(x for x, y in zip(key, self.slice) if isinstance(y, slice))
                loc_changes[l_key] = value
        return loc_changes

    @pyqtSlot(SpinBox, int)
    def spin_box_change(self, box, val):
        """ Change the Matrix on spin box change """
        if self.slice[box.index] == val:
            return
        if val == -1 and not isinstance(self.slice[box.index], slice):
            # Trying to set an empty dimension
            if sum(isinstance(a, slice) for a in self.slice) > 1:
                # Two dimensions are reached more could not be displayed
                box.setValue(self.slice[box.index])
                return
            val = slice(None)
        self.slice[box.index] = val
        curr_data = self.original_data[(*self.slice,)]
        self.model.set_full_data(curr_data, self.local_changes())

    def data_changed(self, index, index2):
        """ Function is called on data_changed """
        if index != index2:
            return
        if self.model.rowCount(None) == 1:
            idx_values = (index.column(),)
        else:
            idx_values = (index.row(), index.column())
        full_idx = self.slice[:]
        n = 0
        for i, v in enumerate(self.slice):
            if isinstance(v, slice):
                if n > 2:
                    return
                full_idx[i] = idx_values[n]
                n += 1
        data = float(self.model.itemData(index)[2])
        if self.original_data[(*full_idx,)] != data:
            self.changed_data[tuple(full_idx)] = data


if __name__ == '__main__':
    from PyQt5.QtCore import pyqtRemoveInputHook
    pyqtRemoveInputHook()
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.noPrintTypes = []
    window.setWindowTitle("")
    CWgt = EditorDialog(window)
    the_data = np.random.rand(5, 4, 3)
    CWgt.open_editor(the_data)
