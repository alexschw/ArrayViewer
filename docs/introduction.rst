Basics
######

.. _load_data:

Load Data
*********
To load a dataset click ``Start > Load data``. You can select a file of the types *.data, .hdf5, .mat, .npy, .txt*. If your data is structured such that the first dimension should be put to the end of the dataset, you can check the corresponding checkbox at the bottom of the load dialog. The selected option is saved for consecutive loadings, even after closing the program. If you are loading a dataset with the same name as an existing file you will be asked if the file should be replaced or if a similar dataset should be added with a different name instead.

Window Structure
****************
.. image:: aview.png

The main ArrayViewer window consists of five separate sections as shown above and explained hereafter.

Data Tree
=========
The Data Tree contains the previously loaded data. The structure of the tree represents the structure of the loaded data. Right-click on any to rename, reshape or delete it in the tree. These operations will not change the original file! If you select any value without a child value its representation will appear in the Charts View.

Charts View
===========
Contains a plot of the last selected data. Depending on the datatype of the values this might be just text (for single values, strings and list of strings), a plot (for 1D or 2D data) or an image (for multidimensional data).

Slice Selectors
===============
The slice selectors enable the slicing of the selected dataset. The amount of neighboring fields corresponds to the number of dimensions. You can enter any number within the range given above the textfield. Slicing with colons is also supported. Lists of single values are currently not supported. When over one of the textfields using the scrollwheel increments (or decrements) the values within the field by 1 (10 with [Ctrl] and 100 with the [Shift] modifier). This also works for colon-slicing, where the [Ctrl] modifier increments (or decrements) by the given stepsize.

Fast Access
===========
The two values (min/max) give the extrema of the currently selected and sliced dataset.
With the transpose checkbox the first two dimensions of the data can be flipped in the plots.
Finally the Permute field and its adjacent button can be used to permute the Dimensions of the current dataset. For that you have to enter the order of dimensions seperated by commas into the textfield and push the button. Any brackets and braces will be striped. The input must include all dimension indices of the data.

Range Slider
============
The range slider is inactive by default. When a colorbar is added to the plot, one can change the color limits of the shown plot.

