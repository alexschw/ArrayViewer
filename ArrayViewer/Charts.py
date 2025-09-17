"""
GraphWidget for the ArrayViewer
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
from contextlib import suppress
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QSizePolicy, QVBoxLayout, QWidget
from PyQt5 import QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FixedLocator
from matplotlib.widgets import Cursor
from matplotlib.lines import Line2D
from matplotlib.image import AxesImage
from matplotlib.collections import PathCollection
import numpy as np
from h5py._hl.dataset import Dataset


def _flat_with_padding(Array, padding=1, fill=np.nan):
    """ Flatten ND array into a 2D array and add a padding with given fill """
    # Reshape the array to 3D
    Arr = np.reshape(Array, Array.shape[:2] + (-1, ))
    rows = _rows_from_dim(Array.shape)
    # Add the padding to the right and bottom of the arrays
    A0 = np.ones([padding, Arr.shape[1], Arr.shape[2]]) * fill
    A1 = np.ones([Arr.shape[0] + padding, padding, Arr.shape[2]]) * fill
    pArr = np.append(np.append(Arr, A0, axis=0), A1, axis=1)
    # Stack the arrays according to the precalculated number of rows
    pA2D = np.hstack(np.split(np.hstack(pArr.T).T, rows)).T
    # Add the padding to the left and top of the arrays
    A0 = np.ones([padding, pA2D.shape[1]]) * fill
    A1 = np.ones([pA2D.shape[0] + padding, padding]) * fill
    pA2D = np.append(A1, np.append(A0, pA2D, axis=0), axis=1)
    return pA2D


def _rows_from_dim(dim):
    """ Returns a reasonable row count for the given dimensionality """
    if (len(dim) == 4 and .18 < 1.0 * dim[2] / dim[3] < 5.5):
        # If the Array is 4D and has reasonable ratio, keep that ratio.
        rows = dim[2]
    else:
        # Get the most equal division of the last dimension
        last_dim = int(np.prod(dim[2:]))
        for n in range(int(np.sqrt(last_dim)), last_dim + 1):
            if last_dim%n == 0:
                rows = last_dim // n
                break
    return rows


def _unravel_flat_with_padding(ind, sh, pad=1):
    """ Unravel a clicked index onto its corresponding n-D-index """
    ind = [i - pad if i > pad else 0 for i in ind]
    cols = int(np.prod(sh[2:])) // _rows_from_dim(sh)
    box_index = [ind[0] // (sh[0] + pad), ind[1] // (sh[1] + pad)]
    ind.extend(map(int, np.unravel_index(box_index[1] * cols + box_index[0], sh[2:])))
    ind[0] = ind[0] % (sh[0] + pad)
    ind[1] = ind[1] % (sh[1] + pad)
    return ind


def _setlocator(axis, lim, nPad=None):
    """ Set the locator of an axis with the given limits and set the ticks """
    if isinstance(lim, list):
        loc = axis.get_major_locator()()
        axis.set_major_locator(FixedLocator(loc))
        d = (np.arange(len(loc)) - 1) * (loc[2] - loc[1]) * lim[2] + lim[0]
    elif isinstance(lim, tuple):
        loc = np.arange(-lim[0] - nPad, lim[-1], lim[0] + nPad)
        axis.set_major_locator(FixedLocator(loc))
        d = loc - (np.arange(0, len(loc)) * nPad - nPad)
    else:
        axis.set_major_locator(FixedLocator(np.arange(len(lim))))
        d = lim

    if all(d.astype(int) == d.astype(float)):
        axis.set_ticklabels(d.astype(int))
    else:
        d = np.vectorize(reformat)(d)
        axis.set_ticklabels(d.astype(float))


def reformat(dat):
    """ Format the numberstrings correctly. """
    if dat is None or isinstance(dat, np.ma.core.MaskedConstant):
        return ""
    try:
        # Check if data is iterable
        _ = iter(dat)
    except TypeError:
        if not 1e-5 < np.abs(dat) < 1e5:
            return f"{dat:.5e}"
        return f"{dat:.5f}"
    else:
        return [reformat(d) for d in dat]


class GraphWidget(QWidget):
    """ Draws the data graph. """
    def __init__(self, parent=None):
        """ Initialize the figure. """
        super().__init__(parent)

        # Setup the canvas, figure and axes
        self._figure = Figure(facecolor='white')
        self._axes = self._figure.add_subplot(111)
        self._canv = FigureCanvasQTAgg(self._figure)
        self._canv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._ui = parent
        self.noPrintTypes = parent.noPrintTypes
        self._clim = (0, 1)
        self._fix_limits = [None, None]
        self._img = None
        self._cb = None
        self.has_cb = False
        self.has_operation = False
        self._colormap = 'viridis'
        self._opr = (lambda x: x)
        self._oprdim = np.array([], dtype=int)
        self._oprcorr = None
        self.cutout = np.array([])
        self.ticks = [[0, -1, 1]]
        self._tick_str = [0, 0]

        # Add a cursor
        self._cursor = Cursor(self._axes, color='red', linewidth=1)
        if self._ui.config.getboolean('opt', 'cursor', fallback=False):
            self._cursor.visible = False
        self.last_clicked = (None, None)
        self.annotation = self._figure.text(0.3, 0.95, "0, 0", visible=False)
        self._canv.mpl_connect('pick_event', self.onclick)

        # Animation
        self._anim_timer = QtCore.QTimer()
        self._anim_timer.setInterval(parent.config.getint('opt', 'anim_speed',
                                                          fallback=300))
        self._anim_timer.timeout.connect(self._animate)
        self._anim_step = 0
        self._anim_dim = None
        self._anim_cutout = np.array([])

        self._canv.draw()

        # Add a label Text that may be changed in later Versions to display the
        # position and value below the mouse pointer
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._canv)
        self._txt = QLabel(self)
        self._txt.setText('')
        self._layout.addWidget(self._txt)

    def onclick(self, event):
        """ Override the existing onclick function to display value under cursor. """
        # Only react to clicks if not in Animation mode
        if self._anim_dim is not None:
            return
        # Get the x and y indices of the data based on the plot type
        xyz = []
        if isinstance(event.artist, Line2D):
            idx = event.ind[0]
            dat = event.artist.get_data()
            xyz = [int(dat[0][idx])]
            dat = reformat(dat[1][idx])
            fstr = "x: {xyz[0]}, y: {dat}"
        elif isinstance(event.artist, AxesImage):
            xyz.append(int(np.round(event.mouseevent.xdata)))
            xyz.append(int(np.round(event.mouseevent.ydata)))
            dat = reformat(event.artist.get_array()[xyz[1], xyz[0]])
            fstr = "x: {xyz[0]}, y: {xyz[1]}, z: {dat}"
        elif isinstance(event.artist, PathCollection):
            xyz.append(event.mouseevent.xdata)
            xyz.append(event.mouseevent.ydata)
            idx = event.ind[0]
            dat = [reformat(v) for v in self.cutout[idx]]
            fstr = str([float(d) for d in dat])[1:-2]
        # Adjust x and y value for reshaped data
        if self.has_operation:
            skipdims = [o - sum(self._tick_str[0] < o) for o in self._oprdim]
            ticks = [v for n, v in enumerate(self.ticks) if n not in skipdims]
        else:
            ticks = self.ticks
        if len(ticks) > 2:
            xyz = _unravel_flat_with_padding(xyz, self.cutout.shape)
            fstr = "index: {xyz}, value: {dat}"
        # Replace index for picked values
        for i, tick in enumerate(ticks):
            with suppress(IndexError):
                if isinstance(tick, list):
                    xyz[i] = tick[2] * xyz[i] + tick[0]
                else:
                    xyz[i] = tick[xyz[i]]

        if QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
            # Set Values in shape if clicked with shift
            self._ui.Shape.set_non_scalar_values(xyz)
        elif QApplication.keyboardModifiers() & QtCore.Qt.ControlModifier:
            # Set Values in shape to 2d if clicked with control
            self._ui.Shape.set_non_scalar_values(['', ''] + xyz[2:])
        elif QApplication.keyboardModifiers() & QtCore.Qt.AltModifier and len(xyz) > 1:
            self.spawn_micro_plot(xyz)
        else:
            # Hide or show information about the clicked location
            if xyz == self.last_clicked:
                self.annotation.set_visible(False)
                self.last_clicked = (None, None)
            else:
                self.annotation.set_visible(True)
                self.annotation.set_text(fstr.format(xyz=xyz, dat=dat))
                self.last_clicked = xyz
        # Refresh the canvas to show the changes
        self._canv.draw()

    def fix_limit(self, idx):
        """ Fix the current value of the minimum(idx 0) or maximum(idx 1). """
        if self._fix_limits[idx] is None:
            self._fix_limits[idx] = self._clim[idx]
            return 1
        self._fix_limits[idx] = None
        return 0

    def start_animation(self, dim=None):
        """ Start the animation over the given dimension. """
        if dim in self._tick_str[0]:
            return False
        if dim in self._oprdim:
            # remove from operation dimensions
            self._oprdim = np.setxor1d(self._oprdim, dim)
            data = self._ui.get(0)
            if isinstance(data, np.ndarray):
                self.cutout = data

        self._anim_dim = dim - (self._tick_str[0] < dim).sum()
        self._anim_step = 0
        self._anim_cutout = self.cutout
        self._anim_timer.start()
        self._axes.clear()
        self.plot()
        self._animate()
        return True

    def stop_animation(self):
        """ Stop the animation and set the cutout back to its original form. """
        self._anim_dim = None
        if self._anim_timer.isActive():
            self._anim_timer.stop()
            self.cutout = self._anim_cutout

    def set_anim_speed(self):
        """ Set the timeout time of the animation timer. """
        anim_speed = self._ui.config.getint('opt', 'anim_speed', fallback=300)
        self._anim_timer.setInterval(anim_speed)

    def spawn_micro_plot(self, location):
        """ Show a small window with the timecourse of selected location. """
        key = self._ui._slice_key()
        data = self._ui.get(0)
        if key in self._ui.slices:
            sl = list(int(s) if s.isdigit() else None for s in self._ui.slices[key])
        else:
            sl = [None for _ in data.shape]

        if sl.count(None) > len(location):
            return

        fill_iter = iter(location)
        sl = [next(fill_iter) if item is None else item for item in sl]
        plot_data = data[(*sl[:-1],)]

        micro_plot = MicroPlot(self, plot_data, sl[:-1], key)
        micro_plot.show()

    def _animate(self):
        """ Perform one animation step. """
        if self._anim_dim >= self._anim_cutout.ndim:
            self.stop_animation()
            return
        self._anim_step = (self._anim_step + 1) % self._anim_cutout.shape[self._anim_dim]
        self.cutout = self._anim_cutout.take(self._anim_step, self._anim_dim)
        self._axes.clear()
        self._axes.set_title(f"Animation on timestep: {self._anim_step}")
        self.plot()
        self._canv.draw()

    def _n_D_plot(self):
        """ Plot multi-dimensional data. """
        sh = self.cutout.shape
        nPad = sh[0] // 100 + 1
        if self._ui.Plot3D.isChecked() and self.cutout.ndim == 3 and sh[2] in (3, 4):
            nPad = -1
            mm = [np.nanmin(self.cutout), np.nanmax(self.cutout)]
            if mm[1] - mm[0] != 0:
                dat = np.swapaxes((self.cutout - mm[0]) / (mm[1] - mm[0]), 0, 1)
            else:
                dat = np.swapaxes(self.cutout, 0, 1)
        else:
            dat = _flat_with_padding(self.cutout, nPad)
        if self.cutout.dtype == np.float16:
            dat = dat.astype(np.float32)
        self._img = self._axes.imshow(dat, interpolation='none', aspect='auto')
        self._set_ticks()
        _setlocator(self._axes.xaxis, sh + (dat.shape[1],), nPad)
        sh = (sh[1], sh[0]) + sh[2:]
        _setlocator(self._axes.yaxis, sh + (dat.shape[0],), nPad)

    def _two_D_plot(self):
        """ Plot 2-dimensional data. """
        if self._ui.MMM.isChecked():
            self._img = []
            self._img += self._axes.plot(np.nanmax(self.cutout, axis=0), 'r')
            self._img += self._axes.plot(np.nanmean(self.cutout, axis=0), 'k')
            self._img += self._axes.plot(np.nanmin(self.cutout, axis=0), 'b')
            self._axes.legend(["Max", "Mean", "Min"])
        else:
            dat = self.cutout.T
            if self.cutout.dtype == np.float16:
                dat = dat.astype(np.float32)
            self._img = self._axes.imshow(dat, interpolation='none', aspect='auto')
        self._set_ticks()
        _setlocator(self._axes.xaxis, self.ticks[0])
        _setlocator(self._axes.yaxis, self.ticks[1])

    def _n_D_scatter(self):
        """ Plot up to four rows as a scatter (x, y, size, color)"""
        if self.cutout.shape[1] < 4:
            col = 'b'
        else:
            col = self.cutout[:, 3] - np.nanmin(self.cutout[:, 3])
            col /= np.nanmax(col)
        if self.cutout.shape[1] < 3:
            siz = 25
        else:
            siz = self.cutout[:, 2] - np.nanmin(self.cutout[:, 2])
            siz = 1 + 100 * siz / np.nanmax(siz)
        self._img = self._axes.scatter(self.cutout[:, 0], self.cutout[:, 1],
                                       c=col, s=siz, cmap=self._colormap)

    def _set_ticks(self, transp=True):
        """ Calculate the ticks for the plot by checking the limits """
        slices = (slice(n, n+1) if isinstance(n, int) else n for n in self._tick_str[1])
        self.ticks = []
        for n in slices:
            if isinstance(n, slice):
                self.ticks.append([n.start or 0, n.stop or -1, n.step or 1])
            else:
                self.ticks.append(np.array(n))
        if transp and self._ui.Transp.isChecked():
            self.ticks[0], self.ticks[1] = self.ticks[1], self.ticks[0]

    def clear(self):
        """ Clear the figure. """
        self._cb = None
        self._figure.clear()
        self._axes = self._figure.gca()

    def colorbar(self, minmax=None):
        """ Add a colorbar to the graph or remove it, if it is existing. """
        if not isinstance(self._img, AxesImage):
            return
        if minmax is not None and not isinstance(self._clim[0], bool):
            _vmin = minmax[0] * (self._clim[1] - self._clim[0]) + self._clim[0]
            _vmax = minmax[1] * self._clim[1]
            self._img.set_clim(
                vmin=_vmin if self._fix_limits[0] is None else self._fix_limits[0],
                vmax=_vmax if self._fix_limits[1] is None else self._fix_limits[1]
            )
        if not self.has_cb:
            if self._cb:
                self._cb.remove()
                self._cb = None
        elif self._cb is None:
            self._cb = self._figure.colorbar(self._img)
        self._canv.draw()

    def colormap(self, mapname=None):
        """ Replace colormap with the given one. """
        if mapname:
            self._colormap = mapname
        if not isinstance(self._img, AxesImage):
            return
        if self._cb:
            self._cb.mappable.set_cmap(mapname)
        self._img.set_cmap(self._colormap)
        self._canv.draw()

    def figure(self):
        """ Return the local figure variable. """
        return self._figure

    def has_opr(self):
        """ Check if the operation is None. """
        return self.has_operation

    def renew_cutout(self, data, slices):
        """ Renew the value of self.cutout with the given data and slices """
        newslice = []
        for i, sli in enumerate(slices):
            if isinstance(sli, tuple):
                data = data.take(sli, axis=i)
                newslice.append(slice(None))
            else:
                newslice.append(sli)
        self.cutout = data[tuple(newslice)].squeeze()

    def renewPlot(self, s, scalDims):
        """ Draw given data. """
        self._axes.clear()
        data = self._ui.get(0)
        self._anim_timer.stop()
        if data.size == 0:
            self._ui.info_msg("Empty dataset!", -1)
            return
        if isinstance(data, self.noPrintTypes):
            # Print strings or lists of strings to the graph directly
            self._axes.text(-0.1, 1.1, str(data), va='top', wrap=True)
            self._axes.axis('off')
        elif isinstance(data, Dataset) and data.shape == ():
            # Print single values of h5py arrays to the graph directly
            self._axes.text(-0.1, 1.1, data[()], va='top', wrap=True)
            self._axes.axis('off')
        elif isinstance(data[0], list):
            # If there is an array of lists plot each element as a graph
            self._img = [self._axes.plot(lst) for lst in data]
        else:
            non_scalar_idx = list(set(range(data.ndim)) - set(scalDims))
            s_mod = tuple(s[i] for i in non_scalar_idx)
            self._tick_str = [scalDims, s_mod]
            # Cut out the chosen piece of the array and plot it
            self.renew_cutout(data, s)
            if len(self._oprdim) and not all(np.isin(self._oprdim, scalDims)):
                a = np.setdiff1d(self._oprdim, scalDims)
                self._oprcorr = tuple(b - (scalDims <= b).sum() for b in a)
                self.cutout = self._opr(self.cutout)
            else:
                self._oprcorr = None
            # Transpose the first two dimensions if it is chosen
            if self._ui.Transp.isChecked() and self.cutout.ndim > 1:
                self.cutout = np.swapaxes(self.cutout, 0, 1)
            self.plot()
            self.reapply_setup()

    def plot(self):
        """ Draw one plot step """
        # Check for empty dimensions
        if 0 in self.cutout.shape:
            self._axes.clear()
            self._img = None
            return
        # Print the Value(s) directly
        if self.cutout.ndim == 0 or self._ui.PrintFlat.isChecked():
            self._axes.set_ylim([0, 1])
            self._axes.text(-0.1, 1.1, str(self.cutout), va='top', wrap=True)
            self._axes.axis('off')
        # Graph an 1D-cutout
        elif self.cutout.ndim == 1:
            self._img = self._axes.plot(self.cutout)
            self._set_ticks(False)
            _setlocator(self._axes.xaxis, self.ticks[0])
            alim = self._axes.get_ylim()
            if alim[0] > alim[1]:
                self._axes.invert_yaxis()
        # 2D-cutout will be shown using imshow, scatter or plot
        elif self.cutout.ndim == 2:
            if self._ui.Plot2D.isChecked():
                unsave = self._ui.config.getboolean('opt', 'unsave', fallback=False)
                if self.cutout.shape[1] > 500 and not unsave:
                    msg = "You are trying to plot more than 500 lines!"
                    msg += " (change to 'unsave' mode in options to plot them anyway)"
                    self._ui.info_msg(msg, -1)
                    return
                self._img = self._axes.plot(self.cutout)
                self._set_ticks()
                _setlocator(self._axes.xaxis, self.ticks[0])
            elif self._ui.PlotScat.isChecked() and self.cutout.shape[1] <= 4:
                self._n_D_scatter()
            else:
                self._two_D_plot()
        # higher-dimensional cutouts will first be flattened
        elif self.cutout.ndim >= 3:
            self._n_D_plot()
        self._canv.draw()

    def reapply_setup(self):
        """
            Reapply the basic setup such that the colorbar, colormap,
            limits, cursor and annotations are in the usual position.
        """
        # Reset the colorbar. A better solution would be possible, if the
        # axes were not cleared everytime.
        self.colorbar()
        self.colormap()
        if self.cutout.size > 0:
            self._clim = (np.nanmin(self.cutout), np.nanmax(self.cutout))
            # Set the minimum and maximum values from the data
            if self._ui.txtMin.text()[-1] != "\U0001F512":
                self._ui.txtMin.setText(f"min : {reformat(self._clim[0])}")
            if self._ui.txtMax.text()[-1] != "\U0001F512":
                self._ui.txtMax.setText(f"max : {reformat(self._clim[1])}")
        else:
            # Reset the minimum and maximum text
            self._ui.txtMin.setText('min : ')
            self._ui.txtMax.setText('max : ')

        if isinstance(self._img, list):
            for i in self._img:
                i.set_picker(5.)
        elif self._img is not None:
            self._img.set_picker(True)
        self._cursor = Cursor(self._axes, useblit=False, color='red', linewidth=1)
        if self._ui.config.getboolean('opt', 'cursor', fallback=False):
            self._cursor.visible = False
        self.annotation.remove()
        self.annotation = self._figure.text(0.3, 0.95, "0, 0", visible=False,
                                            backgroundcolor="silver")
        self._canv.mpl_connect('pick_event', self.onclick)

    def set_operation(self, operation="None"):
        """ Set an operation to be performed on click on a dimension. """
        self.has_operation = (operation != "None")
        if not self.has_operation:
            self._oprdim = np.array([], dtype=int)
            self._opr = (lambda x: x)
        else:
            operations = {'nanmin': np.nanmin, 'nanmax': np.nanmax,
                          'nanmean': np.nanmean, 'nanmedian': np.nanmedian}
            self._opr = lambda x: operations[operation](x, axis=self._oprcorr)
        return self._oprdim

    def set_oprdim(self, value=None):
        """ Set the operation dimension. """
        if value is None:
            self._oprdim = np.array([], dtype=int)
        else:
            self._oprdim = np.setxor1d(self._oprdim, value)
        if self.has_operation:
            return self._oprdim
        return np.empty(0)

    def toggle_colorbar(self):
        """ Toggle the state of the colorbar """
        self.has_cb = not self.has_cb
        self.colorbar()


class MicroPlot(QDialog):
    def __init__(self, parent, data, local_slice, key):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setWindowTitle(f"Timecourse of {key} {local_slice}")
        fig = Figure()
        canv = FigureCanvasQTAgg(fig)
        canv.axes = fig.add_subplot(111)
        canv.axes.plot(data)
        layout.addWidget(canv)
        self.setLayout(layout)
