"""
Data Loader for the ArrayViewer.
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
try:
    import cPickle as pickle
except ImportError:
    import pickle

import os
import re
import scipy.io
import h5py
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PIL import Image, ImageSequence
import numpy as np


def _open_image_file(fname):
    """ Open a file as an image. """
    img = Image.open(fname)
    if img.format == 'GIF':
        image_seq = np.array([f.copy().convert('RGB') for f in ImageSequence.Iterator(img)])
        return {'Value': np.moveaxis(image_seq, [2, 3, 0], [0, 2, 3])}
    return {'Value': np.swapaxes(np.array(img), 0, 1)}


class Loader(QObject):
    """ Seperate Loader to simultaneously load data. """
    doneLoading = pyqtSignal(dict, str)
    load = pyqtSignal(str, str, bool)
    infoMsg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        """ Initialize the Loader. """
        super().__init__(parent)
        self.fname = ''
        self.switch_to_last = False
        self.load.connect(self._add_data)

    def _validate(self, data, origin=None):
        """ Data validation. Replace lists of numbers with np.ndarray."""
        if isinstance(data, (dict, np.lib.npyio.NpzFile)):
            # Run the validation again for each subelement in the dict
            data = {str(key): self._validate(data[key]) for key in data.keys()
                    if str(key)[:2] != "__"}
        elif isinstance(data, list):
            if data != [] and not isinstance(data[0], str):
                # not all elements in the list have the same length
                if isinstance(data[0], list) and len(set(map(len, data))) != 1:
                    maxlen = len(sorted(data, key=len, reverse=True)[0])
                    data = [[xi + [np.nan] * (maxlen - len(xi))] for xi in data]
                try:
                    dat = np.array(data)
                    if dat.dtype == "O":
                        data = self._validate({str(k): v for k, v in enumerate(data)})
                    else:
                        data = dat
                except ValueError:
                    data = self._validate({str(k): v for k, v in enumerate(data)})
        elif isinstance(data, scipy.io.matlab.mio5_params.mat_struct):
            # Create a dictionary from matlab structs
            data = data.__dict__
            data.pop('_fieldnames', None)
        elif isinstance(data, np.ndarray) and data.dtype == "O":
            # Create numpy arrays from matlab cell types
            if not data.shape:
                data = self._validate(data[()])
            else:
                data = self._validate([self._validate(sd) for sd in data])
        elif isinstance(data, np.ndarray) and not data.shape:
            data = data[()]
        elif isinstance(data, h5py.File):
            data = self._get_h5py_dict_data(data)
        elif not isinstance(data, (np.ndarray, h5py.Dataset, int, float, str, tuple, type(None))):
            self.infoMsg.emit(f"DataType ({type(data)}) not recognized. Skipping", 0)
            data = None
        if isinstance(data, (np.ndarray, h5py.Dataset)) and \
           self.switch_to_last and len(data.shape) > 1:
            data = np.moveaxis(data, 0, -1)
        return data

    def _get_h5py_dict_data(self, file):
        """ Validate all values of a h5py file and dereference references. """
        data = {}
        for key in file:
            if key == "#refs#":
                continue
            datum = self._h5py_val(file[key])
            if isinstance(datum, (h5py.Reference, h5py.RegionReference)):
                data[key] = file[datum]
            else:
                data[key] = datum
        return data

    def _h5py_val(self, data):
        """ Validate one datum from the h5py file. """
        if isinstance(data, h5py.Dataset):
            if data.dtype == "O":
                dat = np.empty_like(data)
                try:
                    for x, d in enumerate(data[()]):
                        names = [h5py.h5r.get_name(s, data.file.id) for s in d]
                        dat[x, :] = [np.array(data.file[name]).tobytes()
                                     .decode(encoding="utf-16")
                                     if data.file[name].dtype == "uint16"
                                     else data.file[name] for name in names]
                    data = dat.astype(str).squeeze().tolist()
                except ValueError:
                    data = np.array([data.file.get(d[0]) for d in data[()]][0])
                except (OSError, TypeError):
                    data = self._h5py_val(data[()])
            else:
                data = np.array(data)
        elif isinstance(data, h5py.Group):
            data = self._get_h5py_dict_data(data)
        elif isinstance(data, np.ndarray):
            # References are stored in np.ndarray -> return their value
            if isinstance(data.flatten()[0], (h5py.Reference, h5py.RegionReference)):
                return data.flatten()[0]
        return data

    @pyqtSlot(str, str, bool)
    def _add_data(self, fname, key, switch_to_last=False):
        """ Add a new data to the dataset. Ask if the data already exists. """
        self.switch_to_last = switch_to_last
        # Check if the File is bigger than 15 GB, than it will not be loaded
        if os.path.getsize(fname) > 15e9:
            self.infoMsg.emit("File bigger than 15GB. Not loading!", -1)
            self.doneLoading.emit({}, '')
            return False
        # Load the different data types
        if fname.endswith('.hdf5'):
            data = self._validate(h5py.File(str(fname), 'r'))
        elif fname.endswith('.mat'):
            try:
                # old matlab versions
                data = self._validate(scipy.io.loadmat(str(fname),
                                                       squeeze_me=True,
                                                       struct_as_record=False))
            except NotImplementedError:
                # v7.3
                data = self._validate(h5py.File(str(fname), "r"))
        elif fname.endswith(('.npy', '.npz')):
            try:
                data = self._validate(np.load(str(fname), allow_pickle=True))
            except UnicodeDecodeError:
                data = self._validate(np.load(str(fname), allow_pickle=True,
                                              encoding='latin1'))
        elif fname.endswith(('.data', '.bin')):
            try:
                with open(str(fname), encoding='utf-8') as file:
                    data = self._validate(pickle.load(file))
            except UnicodeDecodeError:
                with open(str(fname), 'rb') as file:
                    data = self._validate(pickle.load(file, encoding='latin1'))
        elif fname.endswith(('.txt', '.csv')):
            with open(fname, encoding="utf-8") as f:
                numberRegEx = r'([-+]?\d+\.?\d*(?:[eE][-+]\d+)?)'
                lil = [re.findall(numberRegEx, line) for line in f.readlines()]
                data = {'Value': np.array(lil, dtype=float)}
        else:
            try:
                _open_image_file(fname)
            except (OSError, FileNotFoundError):
                self.infoMsg('File type not recognized!', 1)
                return False
        if not isinstance(data, dict):
            data = {'Value': data}
        self.doneLoading.emit(data, key)
        return True
