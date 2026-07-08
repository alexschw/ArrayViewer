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
from concurrent.futures import ThreadPoolExecutor, Future
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from PIL import Image, ImageSequence
import numpy as np


def _open_image_file(fname):
    """Open a file as an image."""
    img = Image.open(fname)
    if img.format == "GIF":
        image_seq = np.array([f.copy().convert("RGB") for f in ImageSequence.Iterator(img)])
        return {"Value": np.moveaxis(image_seq, [2, 3, 0], [0, 2, 3])}
    return {"Value": np.swapaxes(np.array(img), 0, 1)}


class Loader(QObject):
    """Separate Loader to simultaneously load data."""
    doneLoading = pyqtSignal(dict, str, str)
    keyValidated = pyqtSignal(tuple, object)
    validateThis = pyqtSignal(object, str)
    load = pyqtSignal(str, str, bool, int)
    infoMsg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        """Initialize the Loader."""
        super().__init__(parent)
        self.fname = ""
        self.switch_to_last = False
        self.load.connect(self._add_data)
        self.loadThread = QThread()
        self.moveToThread(self.loadThread)
        self.loadThread.start()

        self._futures = {}
        self.validateThis.connect(self._bg_validate)
        self._executor = ThreadPoolExecutor()

    def _validate(self, data):
        """Data validation. Replace lists of numbers with np.ndarray."""
        if isinstance(data, (dict, np.lib.npyio.NpzFile)):
            # Run the validation again for each subelement in the dict
            data = {str(key): self._validate(data[key]) for key in data.keys() if str(key)[:2] != "__"}
        elif isinstance(data, (set, list)):
            data = self._validate_list(data)
        elif isinstance(data, scipy.io.matlab.mat_struct):
            # Create a dictionary from matlab structs
            data = data.__dict__
            data.pop("_fieldnames", None)
        elif isinstance(data, np.ndarray) and data.dtype == object:
            # Create numpy arrays from matlab cell types
            if not data.shape:
                data = self._validate(data[()])
            else:
                data = self._validate([self._validate(sd) for sd in data])
        elif isinstance(data, np.ndarray) and not data.shape:
            data = data[()]
        elif not isinstance(data, (np.ndarray, h5py.Dataset, int, float, str, tuple, type(None))):
            self.infoMsg.emit(f"DataType ({type(data)}) not recognized. Skipping", 0)
            data = None
        if isinstance(data, (np.ndarray, h5py.Dataset)) and self.switch_to_last and len(data.shape) > 1:
            data = np.moveaxis(data, 0, -1)
        return data

    def _validate_list(self, data):
        """Validate the elements of a list. Reformating uneven lists."""
        if isinstance(data, set):
            data = list(data)
        if data != [] and not isinstance(data[0], str):
            # not all elements in the list have the same length
            if isinstance(data[0], list) and len(set(map(len, data))) != 1:
                maxlen = len(sorted(data, key=len, reverse=True)[0])
                data = [[xi + [np.nan] * (maxlen - len(xi))] for xi in data]
            try:
                dat = np.array(data)
                if dat.dtype == object:
                    return self._validate({str(k): v for k, v in enumerate(data)})
                return dat
            except ValueError:
                return self._validate({str(k): v for k, v in enumerate(data)})
        return data

    def _get_h5py_dict(self, file, pre_key, empty=True):
        """Generate a dictionary of dictionaries from a h5py file."""
        futures = {}
        data = {}
        for key in file:
            if key == "#refs#":
                continue
            if isinstance(file[key], (dict, h5py.Group)):
                data[key] = self._get_h5py_dict(file[key], pre_key + (key,), empty)
            elif empty:
                self._futures.update({pre_key + (key,): (None, file[key])})
                data[key] = None
            else:
                future = self._executor.submit(self._h5py_val, file[key])
                futures[pre_key + (key,)] = (future, file[key])
                data[key] = future
        self._futures.update(futures)
        return data

    def _get_h5py_dict_data(self, file):
        """Validate all values of a h5py file and dereference references."""
        futures = dict(self._futures)
        for key, (future, _) in futures.items():
            datum = future.result()
            #Dereference Keys
            if isinstance(datum, (h5py.Reference, h5py.RegionReference)):
                datum = self._h5py_val(file[datum])
            self.keyValidated.emit(key, datum)
            del self._futures[key]

    def _h5py_val(self, data):
        """Validate one datum from the h5py file."""
        if isinstance(data, h5py.Dataset):
            if data.dtype == object:
                dat = np.empty_like(data)
                try:
                    for x, d in enumerate(data[()]):
                        names = [h5py.h5r.get_name(s, data.file.id) for s in d]
                        dat[x, :] = [
                            (
                                np.array(data.file[name]).tobytes().decode(encoding="utf-16")
                                if data.file[name].dtype == "uint16"
                                else data.file[name]
                            )
                            for name in names
                        ]
                    data = dat.astype(str).squeeze().tolist()
                except ValueError:
                    data = np.array([data.file.get(d[0]) for d in data[()]][0])
                except (OSError, TypeError):
                    data = self._h5py_val(data[()])
            else:
                data = data[()] if not data.shape else np.array(data)
        elif isinstance(data, np.ndarray):
            # References are stored in np.ndarray -> return their value
            flat = data.flatten()
            if flat.size == 0:
                self.infoMsg.emit("Empty object array encountered, skipping.", 0)
                return None
            if isinstance(flat[0], (h5py.Reference, h5py.RegionReference)):
                return flat[0]
        if isinstance(data, (np.ndarray, h5py.Dataset)) and self.switch_to_last and len(data.shape) > 1:
            data = np.moveaxis(data, 0, -1)
        return data

    def validate_key_now(self, data_key):
        """On-demand validation."""
        future, data = self._futures.get(tuple(data_key), (None, None))
        if data is None:
            return None
        if not isinstance(future, Future):
            # Skip the line and validate now
            return self._h5py_val(data)
        # Validation is already running. Wait for the running process to finish
        return future.result()

    @pyqtSlot(str, str, bool, int)
    def _add_data(self, fname, key, switch_to_last=False, max_file_size=15):
        """Add a new data to the dataset. Ask if the data already exists."""
        self.switch_to_last = switch_to_last
        if not os.path.exists(fname):
            self.doneLoading.emit({}, "", "")
            self.infoMsg.emit(f"File not found: {fname}.", -1)
            return False
        # Check if the File is bigger than max_file_size in GB, than it will not be loaded
        if os.path.getsize(fname) > max_file_size * 1e9:
            self.infoMsg.emit(f"File bigger than {max_file_size}GB. Not loading!", -1)
            self.doneLoading.emit({}, "", "")
            return False
        # Load the different data types
        h5file = None
        if h5py.is_hdf5(fname):
            h5file = h5py.File(str(fname), "r")
            data = self._get_h5py_dict(h5file, (key,))  # keep file open and validate later
        elif fname.endswith(".mat"):
            try:
                # old matlab versions
                data = self._validate(scipy.io.loadmat(str(fname), squeeze_me=True, struct_as_record=False))
            except NotImplementedError:
                # v7.3
                h5file = h5py.File(str(fname), "r")
                data = self._get_h5py_dict(h5file, (key,))  # keep file open and validate later
        elif fname.endswith((".npy", ".npz")):
            try:
                data = self._validate(np.load(str(fname), allow_pickle=True))
            except UnicodeDecodeError:
                data = self._validate(np.load(str(fname), allow_pickle=True, encoding="latin1"))
        elif fname.endswith((".data", ".bin")):
            try:
                with open(str(fname), encoding="utf-8") as file:
                    data = self._validate(pickle.load(file))
            except UnicodeDecodeError:
                with open(str(fname), "rb") as file:
                    data = self._validate(pickle.load(file, encoding="latin1"))
        elif fname.endswith((".txt", ".csv")):
            with open(fname, encoding="utf-8") as f:
                numberRegEx = r"([-+]?\d+\.?\d*(?:[eE][-+]\d+)?)"
                lil = [re.findall(numberRegEx, line) for line in f.readlines()]
                data = {"Value": np.array(lil, dtype=float)}
        else:
            try:
                data = _open_image_file(fname)
            except (OSError, FileNotFoundError):
                self.infoMsg.emit(f"File type .{fname.split('.')[-1]} not recognized!", 1)
                return False
        if not isinstance(data, dict):
            data = {"Value": data}
        self.doneLoading.emit(data, key, fname)

        if h5file:
            self.validateThis.emit(h5file, key)
        return True

    @pyqtSlot(object, str)
    def _bg_validate(self, f, key):
        # Background Validation
        self._get_h5py_dict(f, (key,), False)
        self._get_h5py_dict_data(f)

        # Close h5py file after all keys are validated
        if f:
            f.close()
