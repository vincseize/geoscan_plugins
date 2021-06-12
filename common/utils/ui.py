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

import time

import Metashape

try:
    import shiboken2
except ImportError:
    from PySide2 import shiboken2

from PySide2 import QtUiTools
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtWidgets import QProgressDialog

from .markers import get_marker_position_or_location

photos = ['photos', 'снимки']
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
                ptr = shiboken2.getCppPointer(w)
                main_window = shiboken2.wrapInstance(int(ptr[0]), QMainWindow)
                break
    return main_window


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

undesired_text_glb = ""


def filter_photos_by_markers(undesired_text=None):
    global undesired_text_glb
    if undesired_text is not None:
        undesired_text_glb = undesired_text
    sel_markers = [m for m in Metashape.app.document.chunk.markers if m.selected]
    if not sel_markers:
        return
    enabled_filter = next(tb for tb in tool_buttons(photos) if tb.text() == "Hide disabled")
    if enabled_filter.isChecked() or undesired_text_glb:
        show_cameras = []
        pane = Metashape.app.PhotosPane()
        for marker in sel_markers:
            for cam in Metashape.app.document.chunk.cameras:
                if not cam.center:
                    continue
                width = cam.sensor.calibration.width
                height = cam.sensor.calibration.height
                proj = cam.project(marker.position)
                if proj is None:
                    continue
                if enabled_filter.isChecked() and not cam.enabled:
                    continue
                if undesired_text_glb and undesired_text_glb in cam.label:
                    continue
                if 0 <= proj.x <= width and 0 <= proj.y <= height:
                    if cam not in show_cameras:
                        show_cameras.append(cam)
        pane.setFilter(show_cameras)
    else:
        mw = findMainWindow()
        docks = []
        for c in mw.children():
            if isinstance(c, QDockWidget):
                docks.append(c)
        for dock in docks:
            for c in dock.children():
                if isinstance(c, QAction):
                    if c.text() in filter_photos_by_markers_lbl:
                        c.trigger()
    pos = Metashape.app.document.chunk.transform.matrix.mulp(get_marker_position_or_location(sel_markers[0]))
    Metashape.app.model_view.viewpoint.coo = pos
    for m in sel_markers:
        m.selected = True


def find_action_bars(texts):
    docks = []
    if not docks:
        docks = [shiboken2.wrapInstance(int(shiboken2.getCppPointer(w)[0]), QDockWidget) for w in QApplication.allWidgets() if w.inherits("QDockWidget")]
    # action_bars = [shiboken2.wrapInstance(int(shiboken2.getCppPointer(w)[0]), QToolBar) for w in qApp.allWidgets() if w.inherits("QToolBar")]
    for dock in docks:
        if dock.windowTitle().lower() not in texts:
            continue
        if not dock.widget():
            continue
        for c in dock.widget().children():
            if isinstance(c, QToolBar):
                return c


def add_filter_enabled():
    ab = find_action_bars(photos)
    filter_photos = QToolButton()
    filter_photos.clicked.connect(filter_photos_by_markers)
    filter_photos.setText("By marker")

    hide_disabled = QToolButton()
    # toolbutton.clicked.connect(filter_photos_by_markers)
    hide_disabled.setText("Hide disabled")
    hide_disabled.setCheckable(True)

    ab.addWidget(filter_photos)
    ab.addWidget(hide_disabled)


def tool_buttons(action_bar_texts):
    a_b = find_action_bars(action_bar_texts)
    return [c for c in a_b.children() if isinstance(c, QToolButton)]


# Don't use
def toggle_current_photos(texts):
    pane = Metashape.app.PhotosPane()
    not_enabled_filter = next(tb for tb in tool_buttons(texts) if tb.text() == "Hide disabled")
    if not not_enabled_filter.isChecked():
        pane.resetFilter()
    show_cameras = []
    docks = [shiboken2.wrapInstance(int(shiboken2.getCppPointer(w)[0]), QDockWidget)
             for w in QApplication.allWidgets() if w.inherits("QDockWidget")]
    for dock in docks:
        if dock.windowTitle().lower() in texts:
            m = next(m for m in dock.children() if isinstance(m, QAbstractItemModel))
            for idx in range(m.rowCount()):
                index = m.createIndex(idx, 0)
                cam_label = m.data(index)
                cam = next(cam for cam in Metashape.app.document.chunk.cameras if cam.label == cam_label)
                if not_enabled_filter.isChecked() and not cam.enabled:
                    continue
                show_cameras.append(cam)
    pane.setFilter(show_cameras)


def find_by_marker_button():
    return next(tb for tb in tool_buttons(photos) if tb.text() == "By marker")


def trigger_by_marker_button():
    btn = find_by_marker_button()
    btn.clicked.emit()


class ProgressBar:
    def __init__(self, text="", window_title="", modality=True, cancel_button=None):
        self.progress = QProgressDialog(text, cancel_button, 0, 100)
        # self.progress.setLabelText(text)
        self.progress.setModal(modality)
        self.progress.setWindowTitle(window_title)
        self.progress.show()
        self.update(0)

    def update(self, val, text=""):
        self.progress.setValue(val)
        if text:
            self.progress.setLabelText(text)
        self.progress.update()
        Metashape.app.update()

    def __getattr__(self, *args, **kwargs):
        return self.progress.__getattribute__(*args, **kwargs)


class DoubleProgressBar(QDialog):
    def __init__(self, text="", window_title="", modality=True, cancel_button=None):
        super().__init__()
        self.setWindowTitle(window_title)
        self.label = QLabel(text)
        self.progress_outer = QProgressBar(self)
        self.progress_inner = QProgressBar(self)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.progress_outer)
        layout.addWidget(self.progress_inner)
        self.was_cancelled = False

        if cancel_button is not None:
            self.cancel_button = QPushButton(cancel_button)
            layout.addWidget(self.cancel_button)
            self.cancel_button.clicked.connect(lambda : self.set_was_cancelled(True))

        self.setLayout(layout)
        self.show()

    def set_was_cancelled(self, value):
        self.was_cancelled = value

    def set_outer_value(self, value):
        self.progress_outer.setValue(value)

    def set_inner_value(self, value):
        self.progress_inner.setValue(value)

    def wasCanceled(self):
        return self.was_cancelled


def load_ui_widget(uifilename, parent=None):
    """
    Loads Qt widget from XML file (.ui) which is created by Qt Designer.
    :param uifilename: path to .ui file
    :param parent: parent widget
    :return: Qt Widget
    """
    loader = QtUiTools.QUiLoader()
    uifile = QFile(uifilename)
    uifile.open(QFile.ReadOnly)
    ui = loader.load(uifile, parent)
    uifile.close()
    return ui


def init_progress(start_label="Processing..."):
    progress = QProgressDialog()
    progress.setModal(True)
    progress.setLabelText(start_label)
    progress.show()
    Metashape.app.update()
    return progress


def show_progress(progress, label=None, value_func=None):
    def progress_window(*args):
        if progress.wasCanceled():
            raise AssertionError("Cancelled by user")
        progress.setValue(value_func(*args))
        Metashape.app.update()

    if not progress:
        return lambda: None
    else:
        progress.setLabelText(label)
        return progress_window
