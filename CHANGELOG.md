# 1.0.8
- Overhaul combine operation to combine unequal datasets
- Use nanmin/nanmean/nanmax instead of min/mean/max to account for NaN Values
- Support new h5py IO
- Fixed setTickInterval breaking in python3.8
- Add npz and csv support

# 1.0.7
- Fix n-D-plotting Fixed Locator
- Fix Diff in Data Tree
- Fix printing of None and other types.
- Scrollbar if the names are too long
- Add .bin support
- Add tooltip for (usually too long) filenames
- Fix slicing labels for 1D/2D
- Fix min-max-labels and add macOS platform

# 1.0.6
- Fix Key sorting with "natsort"
- Support for float16 datatypes
- Operations over multiple dimensions
- 2D, 3D, 4D sparse data (Nx4 Array) can be shown as a scatterplot
- Shape Selectors are draggable to resort the array

# 1.0.5
- Windows entry point and desktop shortcut
- Dark Mode

# 1.0.4
- Enable the reshaping of multiple datasets in the data tree
- Reenable Diff in the data tree

# 1.0.3
- Flipped Data treeViewer
- Option to keep the selected slice on data change

# 1.0.2
- Loading of Numpy Dict (of any depth)

# 1.0.1
- Drag and Drop for files
- Loading of Images

# 1.0
- First Stable Version
