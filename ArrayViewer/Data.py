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
from PIL import Image
import numpy as np


class Loader(QObject):
    """ Seperate Loader to simultaneously load data. """
    doneLoading = pyqtSignal(dict, str)
    load = pyqtSignal(str, str, bool)
    infoMsg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        """ Initialize the Loader. """
        super(Loader, self).__init__(parent)
        self.fname = ''
        self.switch_to_last = False
        self.load.connect(self._add_data)

    def _validate(self, data):
        """ Data validation. Replace lists of numbers with np.ndarray."""
        if isinstance(data, dict) or isinstance(data, np.lib.npyio.NpzFile):
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
                        data = self._validate(
                            {str(k): v for k, v in enumerate(data)})
                    else:
                        data = dat
                except ValueError:
                    data = self._validate(
                        {str(k): v for k, v in enumerate(data)})
        elif isinstance(data, scipy.io.matlab.mio5_params.mat_struct):
            # Create a dictionary from matlab structs
            dct = {}
            for key in data._fieldnames:
                exec("dct[key] = self._validate(data.%s)"%key)
            data = dct
        elif isinstance(data, np.ndarray) and data.dtype == "O" :
            # Create numpy arrays from matlab cell types
            if not data.shape:
                data = self._validate(data[()])
            else:
                data = self._validate([self._validate(sd) for sd in data])
        elif isinstance(data, np.ndarray) and not data.shape:
            data = data[()]
        elif isinstance(data, (h5py.File, h5py.Group)):
            data = {key: self._validate(data[key])
                    for key in data if key != "#refs#"}
        elif isinstance(data, h5py.Dataset):
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
                except TypeError:
                    data = self._validate(data[()])
            else:
                data = np.array(data)
        elif not isinstance(data, (np.ndarray, h5py.Dataset, int,
                                   float, str, type(u''), tuple)):
            self.infoMsg.emit("DataType (" + str(type(data))
                              + ") not recognized. Skipping", 0)
            data = None
        if isinstance(data, (np.ndarray, h5py.Dataset)) and \
           self.switch_to_last and len(data.shape) > 1:
            data = np.moveaxis(data, 0, -1)
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
        if fname[-5:] == '.hdf5':
            data = self._validate(h5py.File(str(fname), 'r'))
        elif fname[-4:] == '.mat':
            try:
                # old matlab versions
                data = self._validate(scipy.io.loadmat(str(fname),
                                                       squeeze_me=True,
                                                       struct_as_record=False))
            except NotImplementedError:
                # v7.3
                data = self._validate(h5py.File(str(fname), "r"))
        elif fname[-4:] == '.npy' or fname[-4:] == '.npz':
            try:
                data = self._validate(np.load(str(fname), allow_pickle=True))
            except UnicodeDecodeError:
                data = self._validate(np.load(str(fname), allow_pickle=True,
                                              encoding='latin1'))
        elif fname[-5:] == '.data' or fname[-4:] == '.bin':
            try:
                f = pickle.load(open(str(fname)))
            except UnicodeDecodeError:
                f = pickle.load(open(str(fname), 'rb'), encoding='latin1')
            data = self._validate(f)
        elif fname[-4:] == '.txt':
            lines = open(fname).readlines()
            numberRegEx = r'([-+]?\d+\.?\d*(?:[eE][-+]\d+)?)'
            lil = [re.findall(numberRegEx, line) for line in lines]
            data = {'Value': np.array(lil, dtype=float)}
        else:
            try:
                img = Image.open(fname)
                data = {'Value': np.swapaxes(np.array(img), 0, 1)}
            except (OSError, FileNotFoundError):
                print('File type not recognized!')
                return False
        if not isinstance(data, dict):
            data = {'Value': data}
        self.doneLoading.emit(data, key)
        return True
