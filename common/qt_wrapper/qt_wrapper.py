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

from abc import abstractmethod

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from common.PySide2Wrapper.PySide2Wrapper import ListWidget


class UiUnit(QObject):
    def __init__(self, parent=None):
        super(UiUnit, self).__init__(parent)
        self.enabled_dependencies = []

    @abstractmethod
    def set_enabled(self, flag):
        """
        Set unit enabled
        @param flag: boolean flag
        @type flag: bool
        """

    @abstractmethod
    def get_value(self):
        """
        Get value from ui unit
        @return: value
        """

    def add_enabled_dependency(self, dependency_unit):
        self.enabled_dependencies.append(dependency_unit)
        dependency_unit.toggled().connect(self.set_enabled)

        if not dependency_unit.get_value():
            self.set_enabled(False)

    def _can_be_enabled(self):
        for dep in self.enabled_dependencies:
            if not dep.get_value():
                return False
        return True


class QtListWidget(ListWidget):
    def __init__(self, parent_layout):
        super().__init__()
        parent_layout.addLayout(self._layout)

    def enable_extended_selection(self, flag):
        if flag:
            self._instance.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def get_selected_items(self):
        return [self._ListWidget__get_item_idx(item) for item in self._instance.selectedItems()]


class LineEdit(UiUnit):
    class LineException(Exception):
        pass

    def __init__(self, parent_layout, label_name=None, default_value=None, is_enabled=True):
        super(LineEdit, self).__init__(parent_layout)
        self.layout = QVBoxLayout()

        self.label = None

        if label_name is not None:
            self.label = QLabel()
            self.label.setText(label_name)
            self.layout.addWidget(self.label)

        default_value = str(default_value) if default_value is not None else ""

        self.__line_edit = QLineEdit()
        self.__line_edit.setText(default_value)

        self.layout.addWidget(self.__line_edit)
        if label_name is not None:
            self.layout.addStretch()
        parent_layout.addLayout(self.layout)

        self.value = default_value if default_value is not None else ""

        self.set_enabled(is_enabled)

    def set_enabled(self, flag):
        if not flag or (flag == self._can_be_enabled()):
            if self.label is not None:
                self.label.setEnabled(flag)

            self.__line_edit.setEnabled(flag)

    def add_on_changed_callback(self, callback: callable):
        self.__line_edit.textChanged.connect(callback)

    def get_value(self):
        """
        Get value from ui unit
        @return: value
        @rtype: str
        """
        return self.__line_edit.text()

    def set_value(self, value):
        self.__line_edit.setText(str(value))

    def set_validator(self, validator_type: str, *args, **kwargs):
        validators = {
            "int": QIntValidator,
            "double": QDoubleValidator,
            "regexp": QRegExpValidator,
        }

        validator = validators[validator_type]
        self.__line_edit.setValidator(validator(parent=self.__line_edit, *args, **kwargs))

    def editing_finished(self):
        return self.__line_edit.editingFinished


class CheckBoxInterface(UiUnit):
    def __init__(self, check_box_type, parent_layout, label_name, default_value=None, is_enabled=True):
        super(CheckBoxInterface, self).__init__(parent_layout)
        self.layout = QVBoxLayout()

        self.checkbox = check_box_type()
        self.checkbox.setText(label_name)
        self.checkbox.setChecked(default_value if default_value is not None else True)
        self.checkbox.setEnabled(is_enabled)

        self.layout.addWidget(self.checkbox)

        self.layout.addStretch()
        parent_layout.addLayout(self.layout)

    def set_enabled(self, flag):
        if not flag or (flag == self._can_be_enabled()):
            self.checkbox.setEnabled(flag)

    def set_checked(self, flag=True):
        self.checkbox.setChecked(flag)

    def get_value(self) -> bool:
        return self.checkbox.isChecked()

    def toggled(self):
        return self.checkbox.toggled

    def clicked(self):
        return self.checkbox.clicked


class CheckBox(CheckBoxInterface):
    def __init__(self, parent_layout, label_name, default_value=None, is_enabled=True):
        super().__init__(QCheckBox, parent_layout, label_name, default_value, is_enabled)


class RadioButton(CheckBoxInterface):
    def __init__(self, parent_layout, label_name, default_value=None, is_enabled=True):
        super().__init__(QRadioButton, parent_layout, label_name, default_value, is_enabled)


class Button(UiUnit):
    def __init__(self, parent_layout, name, callback=None, is_enabled=True):
        super(Button, self).__init__(parent_layout)

        self.__layout = QVBoxLayout()
        self.__button = QPushButton()

        self.set_name(name)

        self.__layout.addWidget(self.__button)
        parent_layout.addLayout(self.__layout)

        if callback is not None:
            self.__button.clicked.connect(callback)

        self.set_enabled(is_enabled)

    def set_enabled(self, flag: bool):
        if not flag or (flag == self._can_be_enabled()):
            self.__button.setEnabled(flag)

    def add_callback(self, callback: callable):
        self.__button.clicked.connect(callback)

    def get_value(self):
        return self.__button.clicked()

    def set_name(self, name: str):
        self.__button.setText(name)


class FileDialogInterface(UiUnit):
    class FileDialogException(Exception):
        pass

    def __init__(self, parent_layout, label_name, button_name, default_value="", default_path="", dialog_title="", is_enabled=True):
        super(FileDialogInterface, self).__init__(parent_layout)
        self.__layout = QVBoxLayout()

        self._label = QLabel()
        self._label.setText(label_name)
        self.__layout.addWidget(self._label)

        self._line_edit = LineEdit(self.__layout, is_enabled=is_enabled)

        self._btn = Button(self.__layout, button_name)

        self.__layout.addStretch()
        parent_layout.addLayout(self.__layout)

        self._value = default_value
        self._dialog_title = dialog_title
        self._default_path = default_path

    @abstractmethod
    def __get_from_dialog(self):
        """
        Get value from gui dialog
        """

    def get_value(self):
        return self._line_edit.get_value()

    def set_value(self, value):
        self._line_edit.set_value(value)

    def set_enabled(self, flag):
        if not flag or (flag == self._can_be_enabled()):
            self._label.setEnabled(flag)
            self._line_edit.set_enabled(flag)
            self._btn.set_enabled(flag)

    def add_on_changed_callback(self, callback: callable):
        self._line_edit.add_on_changed_callback(callback)


class File(FileDialogInterface):
    def __init__(self, parent_layout, label_name, button_name, default_value="", default_path="", files_type=None, dialog_title=None, is_enabled=True):
        super(File, self).__init__(parent_layout, label_name, button_name, default_value, default_path, dialog_title, is_enabled)
        self.files_type = files_type if files_type is not None else "(*.*)"
        self._btn.add_callback(self.__get_from_dialog)
        self.set_value(default_value)

    def __get_from_dialog(self):
        res = QFileDialog.getOpenFileName(caption=self._dialog_title, dir=self._default_path, filter=self.files_type)[0]
        if len(res) < 1:
            return

        self.set_value(res)


class SaveFile(FileDialogInterface):
    def __init__(self, parent_layout, label_name, button_name, default_value="", default_path="", files_type=None, dialog_title=None, is_enabled=True):
        super(SaveFile, self).__init__(parent_layout, label_name, button_name, default_value, default_path, dialog_title, is_enabled)
        self.files_type = files_type if files_type is not None else "(*.*)"
        self._btn.add_callback(self.__get_from_dialog)
        self.set_value(default_value)

    def __get_from_dialog(self):
        res = QFileDialog.getSaveFileName(caption=self._dialog_title, dir=self._default_path, filter=self.files_type)[0]
        if len(res) < 1:
            return

        self.set_value(res)


class Path(FileDialogInterface):
    def __init__(self, parent_layout, label_name, button_name, default_value="", default_path="", dialog_title=None, is_enabled=True):
        super(Path, self).__init__(parent_layout, label_name, button_name, default_value, default_path, dialog_title, is_enabled)
        self._btn.add_callback(self.__get_from_dialog)
        self.set_value(default_value)

    def __get_from_dialog(self):
        res = QFileDialog.getExistingDirectory(caption=self._dialog_title, dir=self._default_path)
        if len(res) < 1:
            return

        self.set_value(res)


class ComboBox(UiUnit):
    def __init__(self, parent_layout, label_name, default_value=None, is_enabled=True):
        super(ComboBox, self).__init__(parent_layout)
        self.layout = QVBoxLayout()

        self.label = QLabel()
        self.label.setText(label_name)

        self.combo_box = QComboBox()
        if default_value is not None:
            self.combo_box.addItem(default_value)

        self.set_enabled(is_enabled)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.combo_box)

        self.layout.addStretch()
        parent_layout.addLayout(self.layout)

        self.combo_box.currentIndexChanged.connect(self.__slot)

        self.value = 0

    def set_enabled(self, flag):
        if not flag or (flag == self._can_be_enabled()):
            self.label.setEnabled(flag)
            self.combo_box.setEnabled(flag)

    def set_default_index(self, idx):
        self.combo_box.setCurrentIndex(idx)

    def get_value(self):
        return self.value

    def add_items(self, items):
        for item in items:
            self.combo_box.addItem(item)

    def __slot(self, index):
        self.value = index

    def changed(self):
        return self.combo_box.currentIndexChanged


class TextEdit(UiUnit):
    def __init__(self, parent_layout, default_value=None, is_editable=True):
        super(TextEdit, self).__init__(parent_layout)
        self._layout = QVBoxLayout()
        self._text_field = QTextEdit()

        self._layout.addWidget(self._text_field)

        if default_value is not None:
            self._text_field.setText(default_value)

        parent_layout.addLayout(self._layout)

    def get_value(self):
        return self._text_field.toPlainText()

    def set_value(self, value):
        self._text_field.setText(value)

    def set_enabled(self, flag):
        self._text_field.setEnabled(flag)


class MessageBox(QObject):
    def __init__(self, title, message, size=None, parent=None):
        self.__window = QMessageBox(parent)
        # self._window.setWindowFlags(self._window.windowFlags() & (~Qt.WindowContextHelpButtonHint))  # disable help button
        super(MessageBox, self).__init__(self.__window)

        self.__window.setText(message)

        self.__window.setWindowTitle(title)

    def show(self):
        self.__window.show()


class AbstractWindow(QObject):
    def __init__(self, parent, type, title=None, size=None, enable_scrolling=False):
        self._window = type(parent)
        super(AbstractWindow, self).__init__(self._window)

        if enable_scrolling:
            self.__scroll = QScrollArea(self._window)
            # self.__scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

            self._viewport = QWidget(self.__scroll)
            self.__layout = QVBoxLayout(self._viewport)
            self.__layout.setMargin(0)
            self.__layout.setSpacing(0)
            self._viewport.setLayout(self.__layout)

            self.__scroll.setWidget(self._viewport)
            self.__scroll.setWidgetResizable(True)

            self._window.setWidget(self.__scroll)

            self._layouts = [self.__layout]
            self._window_layout = QVBoxLayout(self._window)
            self._window_layout.setMargin(0)
            self._window_layout.setSpacing(0)
            self._window.setLayout(self._window_layout)
        else:
            self._layouts = [QVBoxLayout()]
            self._window.setLayout(self._layouts[0])

        if size is not None:
            self._window.resize(size[0], size[1])

        if title is not None:
            self.__title = title
            self._window.setWindowTitle(title)

    def add_unit(self, unit: type, *args, **kwargs):
        return unit(self._get_cur_layout(), *args, **kwargs)

    def insert_text_label(self, text, is_link=False):
        widget = QLabel(text)
        widget.setOpenExternalLinks(is_link)
        self._get_cur_layout().addWidget(widget)

    def start_group_box(self, name):
        group_box = QGroupBox(name)
        group_box_layout = QVBoxLayout()
        group_box.setLayout(group_box_layout)

        self._get_cur_layout().addWidget(group_box)
        self._push_layout(group_box_layout)

    def start_horizontal(self):
        horizontal_layout = QHBoxLayout()
        self._get_cur_layout().addLayout(horizontal_layout)
        self._push_layout(horizontal_layout)

    def start_vertical(self):
        vertical_layout = QVBoxLayout()
        self._get_cur_layout().addLayout(vertical_layout)
        self._push_layout(vertical_layout)

    def cancel(self):
        if len(self._layouts) > 1:
            del self._layouts[-1]

    def show(self):
        self._window.show()

    def show_message(self, message):
        MessageBox(self.__title, message).show()

    def show_text(self, text):
        TextWindow(self.__title, text, self._window).show()

    def close(self):
        self._window.close()

    def _get_cur_layout(self):
        return self._layouts[-1]

    def _push_layout(self, layout):
        self._layouts.append(layout)


class TextWindow(AbstractWindow):
    def __init__(self, title, text, parent=None):
        super().__init__(parent, QDialog, title)

        self.add_unit(TextEdit, text)
        self.add_unit(Button, _("Ok"), self.close)


class Window(AbstractWindow):
    def __init__(self, title=None, size=None, enable_scrolling=False):
        super().__init__(QApplication.instance().activeWindow(), QDialog, title, size, enable_scrolling)
        self._window.setWindowFlags(self._window.windowFlags() & (~Qt.WindowContextHelpButtonHint))  # disable help button

    def finished(self):
        return self._window.finished

    def focus_changed(self):
        return QApplication.instance().focusChanged


class DockWidget(AbstractWindow):
    def __init__(self, title, parent, enable_scrolling=False):
        super().__init__(parent, QDockWidget, title, enable_scrolling=enable_scrolling)

        if not enable_scrolling:
            fake_widget = QWidget(self._viewport)
            fake_widget.setLayout(self._layouts[-1])
            self._window.setWidget(fake_widget)

        parent.addDockWidget(Qt.LeftDockWidgetArea, self._window)

        self.__parent = parent

        self._window.show()

    def tabify(self, dock: QDockWidget):
        """
        Align dock widget with existing
        :param dock: dock widget
        """

        self.__parent.tabifyDockWidget(dock, self._window)
