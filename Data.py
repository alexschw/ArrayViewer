#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 28 15:24:19 2019

@author: alexschw
"""
import pickle

import os
import re
import h5py
import scipy.io
import numpy as np
from PyQt4 import QtGui
from PyQt4.QtCore import QObject, pyqtSignal, pyqtSlot

class Loader(QObject):
    doneLoading = pyqtSignal(dict, str)
    load = pyqtSignal(str)

    def __init__(self, parent=None):
        super(QObject, self).__init__(parent)
        self.keys = []
        self.fname = ''
        self.load.connect(self.add_data)

    def filltoequal(self, lil):
        """ Fill a list of lists. Append smaller lists with nan """
        maxlen = max(list(map(len, lil)))
        [[xi.append(np.nan) for _ in range(maxlen - len(xi))] for xi in lil]

    def validate(self, data):
        """ Data validation. Replace lists of numbers with np.ndarray."""
        if isinstance(data, dict):
            # List of global variables (that should not be shown)
            glob = []
            for subdat in data:
                # global variables start with two underscores
                if subdat[:2] == "__":
                    glob.append(subdat)
                    continue
                # Run the validation again for each subelement in the dict
                data[subdat] = self.validate(data[subdat])
            # Remove global variables
            for g in glob:
                data.pop(g)
        elif isinstance(data, list):
            if data != [] and not isinstance(data[0], str):
                # not all elements in the list have the same length
                if isinstance(data[0], list) and len(set(map(len, data))) != 1:
                    self.filltoequal(data)
                data = np.array(data)
        elif isinstance(data, scipy.io.matlab.mio5_params.mat_struct):
            # Create a dictionary from matlab structs
            dct = {}
            for key in data._fieldnames:
                exec("dct[key] = self.validate(data.%s)"%key)
            data = dct
        elif isinstance(data, np.ndarray) and data.dtype == "O":
            # Create numpy arrays from matlab cell types
            ndata = []
            for subdat in data:
                ndata.append(self.validate(subdat))
            return np.array(ndata)
        elif isinstance(data, h5py._hl.files.File) \
                or isinstance(data, h5py._hl.group.Group):
            dct = {}
            for key in data:
                dct[key] = self.validate(data[key])
            return dct
        elif isinstance(data, h5py._hl.dataset.Dataset):
            return np.array(data)
        elif not isinstance(data, (np.ndarray, int, float, str, unicode, tuple)):
            print("DataType (", type(data), ") not recognized. Skipping")
            return None
        return data

    @pyqtSlot(str)
    def add_data(self, fname):
        """ Add a new data to the dataset. Ask if the data already exists. """
        splitted = fname.split("/")
        folder = splitted[-2]
        filename = splitted[-1]
        key = str(folder + " - " + filename)
        # Show warning if data exists
        if key in self.keys:
            msg = QtGui.QMessageBox()
            msg.setText("Data(%s) exists. Do you want to overwrite it?"%key)
            msg.setIcon(QtGui.QMessageBox.Warning)
            msg.setStandardButtons(QtGui.QMessageBox.No|QtGui.QMessageBox.Yes)
            msg.setDefaultButton(QtGui.QMessageBox.Yes)
            if msg.exec_() != QtGui.QMessageBox.Yes:
                return
            else:
                self.keys.remove(key)
        # Check if the File is bigger than 15 GB, than it will not be loaded
        if os.path.getsize(fname) > 15e9:
            print("File bigger than 15GB. Not loading!")
            self.doneLoading.emit({},'')
            return False
        # Load the different data types
        if fname[-5:] == '.hdf5':
            f = h5py.File(str(fname))
            data = dict([(n, np.array(f[n])) for n in f])
        elif fname[-4:] == '.mat':
            try:
                # old matlab versions
                data = self.validate(scipy.io.loadmat(str(fname), squeeze_me=True,
                                                 struct_as_record=False))
            except NotImplementedError:
                # v7.3
                data = self.validate(h5py.File(str(fname)))
        elif fname[-4:] == '.npy':
            data = {'Value': np.load(open(str(fname)))}
        elif fname[-5:] == '.data':
            data = self.validate(pickle.load(open(str(fname))))
        elif fname[-4:] == '.txt':
            lines = open(fname).readlines()
            numberRegEx = r'([-+]?\d+\.?\d*(?:[eE][-+]\d+)?)'
            lil = [re.findall(numberRegEx, line) for line in lines]
            data = {'Value': np.array(lil, dtype=float)}
        else:
            print('File type not recognized!')
            return False

        self.doneLoading.emit(data,key)
