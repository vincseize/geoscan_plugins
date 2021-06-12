"""Mesh creator for Agisoft Metashape

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

import time

import Metashape
from PySide2.QtWidgets import QApplication, QMessageBox, QMainWindow, QDockWidget, QToolButton, QProgressDialog
try:
    from shiboken2 import getCppPointer, wrapInstance
except ImportError:
    from PySide2.shiboken2 import getCppPointer, wrapInstance


photos = ['photos', 'фотографии']
filter_photos_by_markers_lbl = ["Filter Photos by Markers", "Отфильтровать по маркерам"]


def show_info(title, message):
    app = QApplication.instance()
    win = app.activeWindow()
    QMessageBox.information(win, title, message, QMessageBox.Ok)


def show_error(title, message):
    app = QApplication.instance()
    win = app.activeWindow()
    QMessageBox.critical(win, title, message, QMessageBox.Ok)
    # logger.log(loglevels.S_DEBUG, ("Got error: {} / {}".format(title, message))
    # logger.log(loglevels.S_DEBUG, ("Traceback: ", exc_info=1)


def show_warning_yes_no(title, message):
    app = QApplication.instance()
    win = app.activeWindow()
    return QMessageBox.warning(win, title, message, QMessageBox.Yes | QMessageBox.No)


def findMainWindow():
    main_window = None
    if main_window is None:
        for w in QApplication.allWidgets():
            if w.inherits("QMainWindow"):
                ptr = getCppPointer(w)
                main_window = wrapInstance(int(ptr[0]), QMainWindow)
                break
    return main_window


def find_tabifyDockWidget():
    translate_workspace = ["Workspace", "Проект", "Arbeitsbereich", "Espacio de trabajo", "Espace de travail",
                           "Progetto", "ワークスペース", "Projeto", "工作区"]
    window = [w for w in QApplication.allWidgets() if w.windowTitle() in translate_workspace][0]
    ptr = getCppPointer(window)
    tabifyDockWidget = wrapInstance(int(ptr[0]), QDockWidget)
    return tabifyDockWidget


def move_to_ui_state(target, sleep=0):
    """
    takes ui to target state
    :param target: list of names of target state (lower names)
    """

    for w in QApplication.allWidgets():
        if isinstance(w, QToolButton):
            if w.text().lower() in target:
                w.click()
    #
    # children = findMainWindow().children()
    # for child in children:
    #     if isinstance(child, QAction):
    #         if child.text().lower() in target:
    #             child.triggered.emit()
    #             print('hello')
    if sleep:
        time.sleep(sleep)
    Metashape.app.update()


class ProgressBar:
    def __init__(self, text="", window_title="", modality=True, cancel_button=None):
        self.progress = QProgressDialog(text, cancel_button, 0, 100)
        # self.progress.setLabelText(text)
        self.progress.setModal(modality)
        self.progress.setWindowTitle(window_title)
        self.progress.show()
        self.update(0)

    def update(self, val):
        self.progress.setValue(val)
        self.progress.update()
        Metashape.app.update()

    def __getattr__(self, *args, **kwargs):
        return self.progress.__getattribute__(*args, **kwargs)

