"""
Data Tree for the ArrayViewer
"""
# Author: Alex Schwarz <alex.schwarz@informatik.tu-chemnitz.de>
from natsort import realsorted, ns
from PyQt5.QtWidgets import (QHeaderView, QTabWidget, QTreeWidget,
                             QTreeWidgetItem)
from PyQt5.QtWidgets import QSizePolicy as QSP
from PyQt5.QtCore import Qt


class TreeWidget(QTreeWidget):
    """ Overloaded QTreeWidget for the Data Tree tabs. """
    def __init__(self, parent=None):
        """ """
        super().__init__(parent)
        self.setSizePolicy(QSP(QSP.Fixed, QSP.Expanding))
        self.headerItem().setText(0, "")
        self.headerItem().setText(1, "")
        self.setTreePosition(1)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.header().setStretchLastSection(False)
        self.header().setVisible(False)
        self.setColumnWidth(0, 10)
        self.setColumnHidden(0, True)
        self.currentItemChanged.connect(parent.viewer._change_tree)
        self.resizeColumnToContents(1)


class DataTree(QTabWidget):
    """ Class Definition for the Data Tree. """
    def __init__(self, viewer, parent=None):
        """ Initialize the Datatree """
        super().__init__(parent)
        self.old_trace = []
        self.similar_items = []
        self.checkableItems = []
        self.changing_item = None
        self.viewer = viewer

        # Add the Tree Widgets
        self.Tree = TreeWidget(self)
        self.Tree.contextMenuEvent = self.viewer._dropdown
        self.secTree = TreeWidget(self)
        self.addTab(self.Tree, "Files")
        self.addTab(self.secTree, "Data")

        # Connect Signal at the end to avoid errors
        self.root = self.currentWidget().invisibleRootItem()
        self.currentChanged.connect(self._update_treetab)
        self.setAcceptDrops(True)

    def clear_tree(self):
        """ Clear the Tree. """
        self.checkableItems = []
        self.update_tree()

    def current_item(self):
        """ Return the currently selected Item. """
        return self.currentWidget().currentItem()

    def is_files_tree(self):
        """ Return True if the currently open Tree is the "Files"-Tree. """
        return self.currentWidget() == self.Tree

    def _finish_renaming(self):
        """ Finish the renaming of a data-key. """
        if not self.old_trace:
            return
        new_trace = self.viewer.get_obj_trace(self.changing_item)
        if new_trace == self.old_trace:
            return
        self.Tree.itemChanged.disconnect(self._finish_renaming)
        # Check if the name exists in siblings
        itemIndex = self.Tree.indexFromItem(self.changing_item, 1)
        siblingTxt = []
        if self.changing_item.parent():
            for n in range(self.changing_item.parent().childCount()):
                if itemIndex.sibling(n, 1) != itemIndex:
                    siblingTxt.append(itemIndex.sibling(n, 1).data(0))
        else:
            for n in range(self.Tree.topLevelItemCount()):
                if self.Tree.topLevelItem(n) != self.changing_item:
                    siblingTxt.append(itemIndex.sibling(n, 1).data(0))
        if new_trace[-1] in siblingTxt:
            self.changing_item.setData(0, 1, self.old_trace[-1])
            self.old_trace = []
            return
        # Replace the key
        self.viewer.set_data(new_trace, self.viewer.pop(self.old_trace))
        self.old_trace = []
        # Make Item non-editable
        self.changing_item.setFlags(Qt.ItemFlag(61))

    def remove_from_checkables(self, item_list):
        """ Remove items from the checkableItems list. As it causes errors. """
        for item in item_list:
            if item in self.checkableItems:
                self.checkableItems.remove(item)
            if item.childCount() > 0:
                self.remove_from_checkables(item.takeChildren())

    def rename_key(self):
        """ Start the renaming of a data-key. """
        self.changing_item = self.Tree.currentItem()
        self.old_trace = self.viewer.get_obj_trace(self.changing_item)
        # Make Item editable
        self.changing_item.setFlags(Qt.ItemFlag(63))
        self.Tree.editItem(self.changing_item, 1)
        self.Tree.itemChanged.connect(self._finish_renaming)

    def select_key(self, keypath):
        """ Select the key with the given path. """
        item = self.currentWidget().invisibleRootItem()
        for key in keypath:
            for c_no in range(item.childCount()):
                if item.child(c_no).data(1, 0) == key:
                    item = item.child(c_no)
                    break
        if item.data(1, 0) == keypath[-1]:
            self.currentWidget().setCurrentItem(item)

    def _update_subtree(self, item, data, is_sec=False):
        """ Add a new subtree to the current QTreeWidgetItem. """
        for k, v in realsorted(data, alg=ns.IC|ns.NA):
            child = QTreeWidgetItem([None, k])
            item.addChild(child)
            if isinstance(v, tuple):
                self._update_subtree(child, v, is_sec)
            else:
                if is_sec:
                    for s in self.similar_items:
                        sitem = QTreeWidgetItem([None, s])
                        sitem.setToolTip(1, s)
                        child.addChild(sitem)
                    if not v:
                        for c in range(child.childCount()):
                            item.child(c).setCheckState(0, Qt.Unchecked)
                            self.checkableItems.append(item.child(c))
                elif not v:
                    child.setCheckState(0, Qt.Unchecked)
                    self.checkableItems.append(child)

    def update_tree(self, select_key=None):
        """ Add new data to TreeWidget. """
        itemList = []
        self.checkableItems = []
        if self.currentWidget() == self.Tree:
            for name, val in self.viewer.files.items():
                item = QTreeWidgetItem([None, name])
                item.setToolTip(0, name)
                self._update_subtree(item, val)
                itemList.append(item)
            self.Tree.clear()
            self.Tree.addTopLevelItems(itemList)
        else:
            self._update_treetab(1)
        if select_key:
            self.select_key(select_key)

    def _update_treetab(self, index):
        """ Update the currently selected treetab, on switching. """
        if self.viewer.diffBtn.isVisible():
            self.viewer._start_diff()
        if index == 1:
            self._update_tree_sec()
        else:
            self.update_tree()

    def _update_tree_sec(self):
        """ Generate the data tree. """
        self.checkableItems = []
        # get TopLevelItem of the current item as a reference
        ref = self.Tree.currentItem()
        self.secTree.clear()
        if ref is None:  # If no item is selected
            ref = self.Tree.topLevelItem(0)
            if ref is None:  # If no item is available
                return
        while ref.parent() is not None:
            ref = ref.parent()
        # Get the keys of the selected item
        flipped_var = self.viewer.files[ref.text(1)]
        # Find all with a similar structure
        self.similar_items = [k for k, v in self.viewer.files.items() if v == flipped_var]
        # Build the tree
        self._update_subtree(self.secTree.invisibleRootItem(), flipped_var, True)
        itemList = []
        for k in self.viewer.files:
            if k[:4] == "Diff":
                item = QTreeWidgetItem([None, k])
                self._update_subtree(item, self.viewer.files[k])
                itemList.append(item)
        self.secTree.addTopLevelItems(itemList)

    def dragEnterEvent(self, ev):
        """ Catch dragEnterEvents for file dropdown. """
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        """ Catch dropEvent to load the dropped file. """
        fnames = []
        for url in ev.mimeData().urls():
            fnames.append(url.toLocalFile())
        self.viewer.load_files(fnames)
