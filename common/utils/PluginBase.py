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
import json
import typing

from PySide2.QtWidgets import *
import traceback

from common.loggers.email_logger import LoggerValues
from common.utils.ui import load_ui_widget


class PluginBase:
    """
    Main GUI class
    """
    DUMPABLE_TYPES = (
        QLineEdit,
        QSpinBox,
        QDoubleSpinBox,
        QRadioButton,
        QCheckBox,
        QComboBox
    )

    def __init__(self, path):
        self.dlg = create_dialog(path)
        self._dump_path = os.path.splitext(path)[0] + '_values.json'
        self._init_ui()

    def _init_ui(self):
        """
        UI initialization
        :return:
        """

    def select_dir(self, edit):
        """
        Directory path selection callback
        :param edit: LineEdit.
        :return:
        """
        dir_path = QFileDialog.getExistingDirectory(self.dlg, _('Chose directory'), edit.text())
        if dir_path:
            edit.setText(os.path.normpath(dir_path))

    def _select_file(self, edit, existing, **kwargs):
        text = edit.text()
        recent_dir = os.path.dirname(text) if text else ''
        open_func = QFileDialog.getOpenFileName if existing else QFileDialog.getSaveFileName
        path = open_func(self.dlg, _('Chose file'), recent_dir, **kwargs)[0]
        if path:
            edit.setText(os.path.normpath(path))

    def select_existing_file(self, edit, **kwargs):
        """
        Existing file choosing callback
        :param edit: LineEdit
        :param kwargs: QFileDialog open function arguments
        :return: None
        """
        self._select_file(edit, existing=True, **kwargs)

    def select_save_file(self, edit, **kwargs):
        """
        Save file choosing callback
        :param edit: LineEdit
        :param kwargs: QFileDialog open function arguments
        :return: None
        """
        self._select_file(edit, existing=False, **kwargs)

    def set_working_state(self, enable=True):
        """
        If 'enable' is True, sets working state: disables dialog. Doing opposite if False
        :param enable: bool
        :return: None
        """
        self.dlg.setEnabled(not enable)

    def show_message(self, heading, text, error=False):
        """
        Shows message dialog with plugin main dialog as parent.
        :param heading: Name of window.
        :param text: Text of message.
        :param error: if True QMessageBox.critical instance would be created, else -- QMessageBox.information
        :return: None
        """
        if error:
            QMessageBox.critical(self.dlg, heading, text)
        else:
            QMessageBox.information(self.dlg, heading, text)

    def check_input_dir(self, input_dir):
        """
        Checks path of directory on existing.
        :param input_dir:
        :return: bool -- success of operation
        """
        if not os.path.isdir(input_dir):
            self.show_message(
                _("Not a directory"),
                _("Path:\n{}\nIs not an existing directory!").format(input_dir),
                error=True
            )
            return False
        return True

    def safe_process(self, func, success_message='Processing finished',
                     close_after=True,
                     aborted_func: typing.Callable = None,
                     use_crash_reporter: (None, dict) = None,
                     *args, **kwargs):
        """
        Provides safe processing for function: covers funcion it try except block. If function raises any error,
        critical message would be shawn
        :param func: processing function
        :param success_message: str. Message which would be shawn if processing finished successfully
        :param close_after: bool.
        :param aborted_func: typing.Callable. Function to run after user aborted process.
        :param use_crash_reporter: (None, dict). Used to run common.loggers.crash_reporter.
            To use it keep dict to that param in format {'plugin_name': str(), 'plugin_version': str(), 'items': dict()}
        :param args: args which will be passed in function
        :param kwargs: named args which will be passed in function
        :return:
        """
        self.set_working_state(True)

        # noinspection PyBroadException
        try:
            self.dump_values()
            result = func(*args, **kwargs)
        except Exception:
            if use_crash_reporter is None:
                traceback.print_exc()
                self.show_message(
                    _("Processing failed!"),
                    _("Unexpected error!\n{}").format(traceback.format_exc()),
                    error=True
                )
            else:
                import common.loggers.crash_reporter as cr

                data = use_crash_reporter
                if 'items' not in data or 'plugin_name' not in data or 'plugin_version' not in data:
                    self.show_message(
                        _("Processing failed!"),
                        _("Unexpected error!\n{}").format(traceback.format_exc()),
                        error=True
                    )
                    raise AssertionError("System error during initialization crash reporter.")

                values = LoggerValues(input=data['items'],
                                      plugin_name=data['plugin_name'],
                                      plugin_version=data['plugin_version'])

                cr.run_crash_reporter(error=traceback.format_exc(), values=values, run_thread=False)

        except KeyboardInterrupt:
            if aborted_func is not None:
                aborted_func()
            self.show_message(_("Aborted by user!"), _("Processing stopped! Aborted by user!"))
        else:
            self.show_message(_("Processing finished!"), success_message)
            return result
        finally:
            self.set_working_state(False)
            if close_after:
                self.dlg.close()

    @staticmethod
    def __get_value(attr):
        if isinstance(attr, QLineEdit):
            return attr.text()
        elif isinstance(attr, (QSpinBox, QDoubleSpinBox)):
            return attr.value()
        elif isinstance(attr, (QCheckBox, QRadioButton)):
            return attr.isChecked()
        elif isinstance(attr, QComboBox):
            return attr.currentText()

    @staticmethod
    def __set_value(attr, value):
        if isinstance(attr, QLineEdit):
            attr.setText(value)
        elif isinstance(attr, (QSpinBox, QDoubleSpinBox)):
            attr.setValue(value)
        elif isinstance(attr, (QCheckBox, QRadioButton)):
            attr.setChecked(value)
        elif isinstance(attr, QComboBox):
            idx = attr.findText(value)
            if idx == -1:
                attr.addItem(value)
            attr.setCurrentText(value)

    def dump_values(self):
        """
        Dumps all values from dialog to json file
        :return:
        """
        values = dict()
        dlg = self.dlg
        for member in dir(dlg):
            attr = getattr(dlg, member)
            if isinstance(attr, self.DUMPABLE_TYPES):
                values[member] = self.__get_value(getattr(dlg, member))

        with open(self._dump_path, 'w', encoding='utf-8') as f:
            json.dump(values, f, ensure_ascii=False, sort_keys=True, indent=4)

    def load_values(self):
        """
        Loads all values from json file to dialog
        :return:
        """
        def set_item(item, value):
            """
            sets attribute *item* value *value*
            :param item: str. item name
            :param value:
            :return:
            """
            try:
                attr = getattr(dlg, item)
                self.__set_value(attr, value)
            except (ValueError, AttributeError, TypeError):
                pass

        if not os.path.isfile(self._dump_path):
            return

        try:
            with open(self._dump_path, 'r', encoding='utf-8') as f:
                values = json.load(f)
        except json.JSONDecodeError:
            print(traceback.format_exc())
            return

        dlg = self.dlg
        for k, v in values.items():
            set_item(k, v)


def create_dialog(path):
    """
    Creates QDialog instance from .ui file
    :param path: path to .ui file
    :return: QDialog instance
    """

    ui_path = os.path.join(path)
    return load_ui_widget(ui_path)


if __name__ == '__main__':
    d_ = PluginBase(
        r'C:\Users\e.baryshkov\Desktop\waste\test_widget.ui'
    )
    d_.load_values()
    d_.dlg.exec_()
    d_.dump_values()
