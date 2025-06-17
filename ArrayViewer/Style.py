"""
Color Palette for the ArrayViewer
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>

from PyQt5.QtGui import QColor, QPalette

def dark_qpalette():
    """ Create a dark palette for a dark mode. """
    dark = QColor(25, 35, 45)
    base = QColor(40, 50, 60)
    high = QColor(42, 130, 200)
    button = QColor(65, 65, 65)
    white = QColor(255, 255, 255)
    black = QColor(0, 0, 0)
    red = QColor(255, 0, 0)

    pal = QPalette()
    pal.setColor(QPalette.Window, dark)
    pal.setColor(QPalette.WindowText, white)
    pal.setColor(QPalette.Base, base)
    pal.setColor(QPalette.AlternateBase, dark)
    pal.setColor(QPalette.Text, white)
    pal.setColor(QPalette.Button, button)
    pal.setColor(QPalette.ButtonText, white)
    pal.setColor(QPalette.BrightText, red)
    pal.setColor(QPalette.Highlight, high)
    pal.setColor(QPalette.HighlightedText, black)
    pal.setColor(QPalette.Link, high)
    pal.setColor(QPalette.Disabled, QPalette.Button, base)
    pal.setColor(QPalette.Disabled, QPalette.Highlight, base)
    return pal
