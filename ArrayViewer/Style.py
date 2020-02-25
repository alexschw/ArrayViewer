"""
Color Palette for the ArrayViewer
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>

from PyQt5.QtGui import QColor, QPalette

def dark_pal():
    """ Create a dark palette for a dark mode. """
    dark = QColor(21, 29, 45)
    base = QColor(29, 40, 62)
    high = QColor(42, 130, 218)
    white = QColor(255, 255, 255)
    black = QColor(0, 0, 0)
    red = QColor(255, 0, 0)

    pal = QPalette()
    pal.setColor(QPalette.Window, dark)
    pal.setColor(QPalette.WindowText, white)
    pal.setColor(QPalette.Base, base)
    pal.setColor(QPalette.AlternateBase, dark)
    pal.setColor(QPalette.Text, white)
    pal.setColor(QPalette.Button, dark)
    pal.setColor(QPalette.ButtonText, white)
    pal.setColor(QPalette.BrightText, red)
    pal.setColor(QPalette.Highlight, high)
    pal.setColor(QPalette.HighlightedText, black)
    pal.setColor(QPalette.Link, high)
    return pal

def set_darkmode(app, darkmode=True):
    """ Set a dark mode for the Viewer Window. """
    if darkmode:
        app.setPalette(dark_pal())
    else:
        app.setPalette(app.style().standardPalette())
