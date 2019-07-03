#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 28 15:24:19 2019

@author: alexschw
"""
try:
    import cPickle as pickle
except ImportError:
    import pickle

import os
import re
import h5py
import scipy.io
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import numpy as np

class Loader(QObject):
    """ Seperate Loader to simultaneously load data. """
    doneLoading = pyqtSignal(dict, str)
    load = pyqtSignal(str, str)
    infoMsg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        """ Initialize the Loader. """
        super(QObject, self).__init__(parent)
        self.fname = ''
        self.load.connect(self.add_data)

    def filltoequal(self, lil):
        """ Fill a list of lists. Append smaller lists with nan. """
        maxlen = len(sorted(lil,key=len, reverse=True)[0])
        return [[xi+[np.nan]*(maxlen - len(xi))] for xi in lil]

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
                    data = self.filltoequal(data)
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
            if isinstance(subdat, str):
                return ndata
            else:
                return np.array(ndata)
        elif isinstance(data, h5py._hl.files.File) \
                or isinstance(data, h5py._hl.group.Group):
            dct = {}
            for key in data:
                dct[key] = self.validate(data[key])
            return dct
        elif not isinstance(data, (np.ndarray, h5py._hl.dataset.Dataset, int,
                                   float, str, type(u''), tuple)):
            self.infoMsg.emit("DataType (" + type(data) +
                              ") not recognized. Skipping", 0)
            return None
        return data

    @pyqtSlot(str, str)
    def add_data(self, fname, key=""):
        """ Add a new data to the dataset. Ask if the data already exists. """
        splitted = fname.split("/")
        if key == "":
            key = str(splitted[-2] + " - " + splitted[-1])
        # Check if the File is bigger than 15 GB, than it will not be loaded
        if os.path.getsize(fname) > 15e9:
            self.infoMsg.emit("File bigger than 15GB. Not loading!", -1)
            self.doneLoading.emit({}, '')
            return False
        # Load the different data types
        if fname[-5:] == '.hdf5':
            data = self.validate(h5py.File(str(fname)))
        elif fname[-4:] == '.mat':
            try:
                # old matlab versions
                data = self.validate(scipy.io.loadmat(str(fname),
                                                      squeeze_me=True,
                                                      struct_as_record=False))
            except NotImplementedError:
                # v7.3
                data = self.validate(h5py.File(str(fname)))
        elif fname[-4:] == '.npy':
            try:
                data = {'Value': np.load(str(fname))}
            except UnicodeDecodeError:
                data = {'Value': np.load(str(fname), encoding='latin1')}
        elif fname[-5:] == '.data':
            try:
                f = pickle.load(open(str(fname)))
            except UnicodeDecodeError:
                f = pickle.load(open(str(fname), 'rb'), encoding='latin1')
            data = self.validate(f)
        elif fname[-4:] == '.txt':
            lines = open(fname).readlines()
            numberRegEx = r'([-+]?\d+\.?\d*(?:[eE][-+]\d+)?)'
            lil = [re.findall(numberRegEx, line) for line in lines]
            data = {'Value': np.array(lil, dtype=float)}
        else:
            print('File type not recognized!')
            return False

        self.doneLoading.emit(data, key)
        return True
