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
from PySide2 import QtWidgets


def browse_dir(ui, title="Select directory", main_directory=False):
    dir_ = QtWidgets.QFileDialog.getExistingDirectory(
        ui,
        title,
        os.path.expanduser("~") if not main_directory else main_directory,
        QtWidgets.QFileDialog.ShowDirsOnly
    )
    return dir_ if dir_ else None


def browse_file(ui, extensions=None, title="Open file", main_directory=False):
    path = QtWidgets.QFileDialog.getOpenFileName(
        ui,
        title,
        os.path.expanduser("~") if not main_directory else main_directory,
        extensions,
    )
    return path[0] if path[0] else None


def open_dir(ui, line_edit=None, title="Select directory", main_directory=False):
    path = browse_dir(ui=ui, title=title, main_directory=main_directory)
    if path and line_edit is not None:
        line_edit.setText(path.replace('/', '\\'))
    return path


def open_file(ui, extensions=None, line_edit=None, title="Open file", main_directory=False):
    path = browse_file(ui=ui, extensions=extensions, title=title, main_directory=main_directory)
    if path and line_edit is not None:
        line_edit.setText(path.replace('/', '\\'))
    return path


def save_file(ui, extension, title="Save file", main_directory=False):
    path = QtWidgets.QFileDialog.getSaveFileName(
        ui,
        title,
        os.path.expanduser("~") if not main_directory else main_directory,
        extension)
    return path[0] if path[0] else None
