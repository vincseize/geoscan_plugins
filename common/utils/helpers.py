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

from collections import defaultdict
from itertools import tee

import PhotoScan as ps
import cv2
import numpy as np
from PySide2.QtWidgets import *

from .ui import show_error


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def get_current_cameras():
    app = QApplication.instance()
    win = app.activeWindow()
    children = win.children()
    if ps.app.document.chunk is None:
        QMessageBox.critical(win, _("Error"), _("Please open document which you want to work with!"), QMessageBox.Ok)
        return
    tabs = []
    for child in children:
        if isinstance(child, QSplitter):
            for tab in child.children():
                if isinstance(tab, QTabWidget):
                    tabs.append(tab)
    current_indexes = []
    for tab in tabs:
        current_indexes.append(tab.currentIndex())

    labels = []
    for tab, index in zip(tabs, current_indexes):
        label = tab.tabText(index)
        labels.append(label)

    cameras = [cam for cam in ps.app.document.chunk.cameras if cam.label in labels]
    if not cameras:
        show_error(_("No camera selected"), _("Please select camera you want to work with"))
    return cameras


def get_lab_image(cam):
    big_img = np.fromstring(cam.photo.image().tostring(),  dtype=np.uint8)
    w, h = cam.sensor.calibration.width, cam.sensor.calibration.height
    big_img = big_img.reshape((h, w, 3))
    img = cv2.cvtColor(big_img, cv2.COLOR_BGR2Lab)
    return img


def add_cam_to_group(cam, group_label, enabled=False):
    try:
        group = next(g for g in ps.app.document.chunk.camera_groups if g.label == group_label)
    except StopIteration:
        group = ps.app.document.chunk.addCameraGroup()
        group.label = group_label
    cam.group = group
    cam.enabled = enabled


def duplicate_items(L):
    dups = defaultdict(list)
    for i, e in enumerate(L):
        dups[e].append(i)
    return dups


def find_marker_group(label):
    try:
        group = next(g for g in ps.app.document.chunk.marker_groups if g.label == label)
    except StopIteration:
        group = ps.app.document.chunk.addMarkerGroup()
        group.label = label
    return group


def find_cam_by_name(cam_label):
    return next(cam for cam in ps.app.document.chunk.cameras if cam.label == cam_label)
