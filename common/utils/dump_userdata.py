"""Common scripts, classes and functions

Copyright (C) 2021  Geoscan Ltd. https://www.geoscan.aero/

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import shelve

from PySide2 import QtWidgets


HELPER = {
    QtWidgets.QLabel: {'set': lambda x, v: x.setText(v), 'extract': lambda x: x.text()},
    QtWidgets.QLineEdit: {'set': lambda x, v: x.setText(v), 'extract': lambda x: x.text()},
    QtWidgets.QGroupBox: {'set': lambda x, v: x.setChecked(v), 'extract': lambda x: x.isChecked()},
    QtWidgets.QWidget: {'set': lambda x, v: x.setWindowTitle(v), 'extract': lambda x: x.windowTitle()},
    QtWidgets.QCheckBox: {'set': lambda x, v: x.setChecked(v), 'extract': lambda x: x.isChecked()},
    QtWidgets.QComboBox: {'set': lambda x, v: set_combobox(x, v), 'extract': lambda x: extract_combobox(x)},
    QtWidgets.QSpinBox: {'set': lambda x, v: x.setValue(v), 'extract': lambda x: x.value()},
    QtWidgets.QDoubleSpinBox: {'set': lambda x, v: x.setValue(v), 'extract': lambda x: x.value()},
    QtWidgets.QRadioButton: {'set': lambda x, v: x.setChecked(v), 'extract': lambda x: x.isChecked()}
}


def set_combobox(widget, value):
    """
    :param widget: QtWidgets.QComboBox
    :param value: tuple. Format: (items: list, current_index: int)
    :return:
    """
    widget.addItems(value[0])
    widget.setCurrentIndex(value[1])


def extract_combobox(widget):
    items = [widget.itemText(i) for i in range(widget.count())]
    index = widget.currentIndex()
    return items, index


class UserDataDump:
    """Class to save and upload user data from Qt objects. Python shelve storage is used."""

    NAME = 'user_data'

    def __init__(self, directory, parent=None, filename=None, create_cache_dir=False):
        if not create_cache_dir:
            self.dir = directory
        else:
            self.dir = os.path.join(directory, '.cache')
            try:
                os.makedirs(self.dir)
            except FileExistsError:
                pass

        self.NAME = filename if filename else self.NAME
        self.parent = parent
        self.file = os.path.join(self.dir, self.NAME)
        self.file_dat = os.path.join(self.dir, self.NAME + '.dat')

    def create_and_update(self, **kwargs):
        if not os.path.exists(self.dir):
            raise OSError('{} is not exists'.format(self.dir))

        with shelve.open(self.file) as f:
            for ui_attr_name, value in kwargs.items():
                if ui_attr_name not in f:
                    f[ui_attr_name] = value

    def upload_to_ui(self, ui):
        if not os.path.exists(self.file_dat):
            return

        with shelve.open(self.file, 'r') as f:
            for ui_attr_name, value in f.items():
                if ui_attr_name.startswith("__") and isinstance(value, CustomSave):
                    value.set(self.parent)
                    continue
                elif ui_attr_name.startswith("__"):
                    continue

                try:
                    ui_attr = getattr(ui, ui_attr_name)
                except AttributeError:
                    continue

                try:
                    HELPER[ui_attr.__class__]['set'](ui_attr, value)
                except KeyError:
                    print("Unsupported Qt object for UserDataDump: {}. Passed.".format(ui_attr.__class__))

    def dump_from_ui(self, ui):
        if not os.path.exists(self.file_dat):
            return

        with shelve.open(self.file) as f:
            for ui_attr_name, value in f.items():
                if ui_attr_name.startswith("__") and isinstance(value, CustomSave):
                    value.extract(self.parent)
                    f[ui_attr_name] = value
                    continue
                elif ui_attr_name.startswith("__"):
                    continue

                try:
                    ui_attr = getattr(ui, ui_attr_name)
                except AttributeError:
                    continue

                extracted = HELPER[ui_attr.__class__]['extract'](ui_attr)
                f[ui_attr_name] = extracted

    def get_value(self, attr):
        with shelve.open(self.file) as f:
            return f[attr]

    @property
    def data(self) -> dict:
        with shelve.open(self.file) as f:
            data = dict(f)
        return data


class CustomSave:
    """Class to provide saving and uploading custom data from ui."""

    def __init__(self, item, set_func: str, extract_func: str):
        self.item = item
        self.set_func = set_func
        self.extract_func = extract_func

    def set(self, parent):
        func = getattr(parent, self.set_func)
        func(self.item)

    def extract(self, parent):
        func = getattr(parent, self.extract_func)
        self.item = func()


def __testcase1():
    import sys
    from PySide2.QtWidgets import (QLineEdit, QPushButton, QApplication,
                                   QVBoxLayout, QDialog, QLabel)

    temp_dir = r'C:\Users\a.kot.GEOSCAN\Downloads\TEMP\shelve'
    class Form(QDialog):

        def __init__(self, parent=None):
            super(Form, self).__init__(parent)
            self.label = QLabel("owwwwww")
            self.edit = QLineEdit("Write my name here")
            self.button = QPushButton("Show Greetings")
            layout = QVBoxLayout()
            layout.addWidget(self.label)
            layout.addWidget(self.edit)
            layout.addWidget(self.button)
            self.setLayout(layout)
            self.button.clicked.connect(self.greetings)

            self.saver = UserDataDump(directory=temp_dir)
            self.saver.create_and_update(label='hello world', edit='first_line')
            self.saver.upload_to_ui(self)

        def closeEvent(self, event):
            self.saver.dump_from_ui(self)
            event.accept()

        # Greets the user
        def greetings(self):
            print(f"Hello {self.edit.text()}")

    app = QApplication(sys.argv)
    form = Form()
    form.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    __testcase1()
