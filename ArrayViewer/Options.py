"""
Options Window for the ArrayViewer.
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>

from PyQt5.QtWidgets import QCheckBox, QDialog, QFormLayout, QFrame, QLabel, QLineEdit
from PyQt5.QtWidgets import QDialogButtonBox as DBB
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import Qt


class OptionsDialog(QDialog):
    """ A Dialog for setting the options of the ArrayViewer. """
    def __init__(self, parent=None):
        """ Initialize. """
        super().__init__(parent)
        self.parent = parent

        # Setup the basic window
        self.setWindowTitle("Options of the ArrayViewer")
        self.info_msg = parent.info_msg
        formLayout = QFormLayout(self)

        self.options = {}

        ftl = QCheckBox("Put first dimension to the end", self)
        formLayout.addRow(self.tr("First to last"), ftl)
        self.options['first_to_last'] = ftl
        darkmode = QCheckBox("", self)
        self.options['darkmode'] = darkmode
        formLayout.addRow(self.tr("Enable Dark Mode"), darkmode)
        anim_speed = QLineEdit(self)
        anim_speed.setValidator(QIntValidator())
        self.options['anim_speed'] = anim_speed
        formLayout.addRow(self.tr("Animation Speed [ms]"), anim_speed)
        cursor = QCheckBox("", self)
        self.options['cursor'] = cursor
        formLayout.addRow(self.tr("Disable red cursor"), cursor)

        hline = QFrame()
        hline.setFrameStyle(QFrame.HLine)
        formLayout.addRow(hline)
        label = QLabel("The following options may slow down the ArrayViewer. Proceed with caution.")
        label.setStyleSheet("background-color:orange;")
        label.setFrameStyle(QFrame.Panel|QFrame.Raised)
        label.setLineWidth(2)
        formLayout.addRow(label)
        unsave = QCheckBox("I know what I'm doing. Let me plot more.", self)
        self.options['unsave'] = unsave
        formLayout.addRow(self.tr("Unsave Plotting Mode"), unsave)

        max_file_size = QLineEdit(self)
        max_file_size.setValidator(QIntValidator())
        self.options['max_file_size'] = max_file_size
        formLayout.addRow(self.tr("Maximum File Size [GB]"), max_file_size)

        # Add a button Box with "OK" and "Cancel"-Buttons
        self.buttonBox = DBB(DBB.Cancel|DBB.Ok, Qt.Horizontal)
        self.buttonBox.button(DBB.Cancel).clicked.connect(self.reject)
        self.buttonBox.button(DBB.Ok).clicked.connect(self.change_options)
        self.buttonBox.setCenterButtons(True)
        formLayout.addRow(self.buttonBox)
        self.setLayout(formLayout)

    def adapt_options(self):
        """ Set the values in the window to ConfigParser Data and start. """
        for key, option in self.options.items():
            if isinstance(option, QCheckBox):
                value = self.parent.config.getboolean('opt', key, fallback=False)
                option.setChecked(value)
        self.options['anim_speed'].setText(str(self.parent.config.getint('opt', 'anim_speed', fallback=300)))
        self.options['max_file_size'].setText(str(self.parent.config.getint('opt', 'max_file_size', fallback=15)))
        self.exec_()

    def change_options(self):
        """ Change the options in the ConfigParser and perform their actions. """
        for key, option in self.options.items():
            if isinstance(option, QCheckBox):
                self.parent.config.set('opt', key, str(option.isChecked()))
            elif isinstance(option, QLineEdit):
                self.parent.config.set('opt', key, option.text())
        # Perform actions based on new options.
        self.parent._set_dark_mode(self.options['darkmode'].isChecked())
        self.parent.Graph.set_anim_speed()
        self.accept()
