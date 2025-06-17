"""
InfoBoxes and Dialogs for the ArrayViewer
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
import re
import json
import subprocess
from packaging.version import parse as parse_version
from itertools import combinations
import numpy as np
from PyQt5 import QtCore
from PyQt5.QtWidgets import QCompleter, QDialog, QGridLayout, QLabel, QLineEdit, QMessageBox, QTextEdit, QVBoxLayout
from PyQt5.QtWidgets import QDialogButtonBox as DBB

from ArrayViewer import __version__


def _get_shape_from_str(string):
    """
    Returns an array with the elements of the string. All brackets are
    removed as well as empty elements in the array.
    """
    return np.array([_f for _f in string.strip("()[]").split(",") if _f],
                    dtype=int)


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
    return [previous_val + f"{i}," for i in factors]


def show_aview_about():
    """Show the version of the ArrayViewer."""
    proc = subprocess.run(
        ["curl", "https://pypi.org/pypi/arrayviewer/json"],
        capture_output=True,
        check=False,
    )
    txt = f"ArrayViewer version {__version__}"
    if proc.returncode == 0:
        current_vers = parse_version(json.loads(proc.stdout).get("info", {}).get("version", "0"))
        if current_vers > parse_version(__version__):
            txt += f"\n\nA new version of ArrayViewer is available ({current_vers})!"
            txt += "\n\nYou can update it using:\n\npip install --upgrade arrayviewer"
    infoBox = QMessageBox(QMessageBox.Information, "Info", txt, QMessageBox.Ok)
    infoBox.exec_()


class ReshapeDialog(QDialog):
    """ A Dialog for Reshaping the Array. """
    def __init__(self, parent=None):
        """ Initialize. """
        super().__init__(parent)

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
                return data, _get_shape_from_str(sStr)
            # If "CANCEL" is pressed
            return data, None


class NewDataDialog(QDialog):
    """ A Dialog for Creating new Data. """
    def __init__(self, parent=None):
        """ Initialize. """
        super().__init__(parent)

        # Setup the basic window
        self.resize(400, 150)
        self.setWindowTitle("Create new data or change the current one")
        Layout = QVBoxLayout(self)
        self.data = {}
        self.lastText = ""
        self.returnVal = None

        # Add the current and new shape boxes and their labels
        label = QLabel(self)
        label.setText(("Use 'this' to reference the current data and 'cutout' "
                       + "for the current view.\nBefore saving enter the "
                       + "variable you want to save.\n"
                       + "Otherwise the original data will be overwritten."))
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
            methods = {'np': np, 'self': self}
            self.data[var] = eval(value, {'__buildins__': None}, methods)
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
        except ValueError as e:
            raise ValueError("No '=' in expression") from e
        for op in ['(', ')', '[', ']', '{', '}', ',',
                   '+', '-', '*', '/', '%', '^']:
            expr = expr.replace(op, f" {op} ")
        expr = " " + expr + " "
        for datum in self.data:
            expr = expr.replace(f" {datum} ", f"self.data['{datum}']")
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
