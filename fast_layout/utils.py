"""Apply Vertical Camera Alignment plugin for Agisoft Metashape

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

import math
import time

import Metashape as ms
from PySide2.QtWidgets import *
from common.utils.bridge import chunk_crs_to_camera


def time_measure(func):
    def wrapper(*args, **kwargs):
        t1 = time.time()
        res = func(*args, **kwargs)
        t2 = time.time()
        print("Finished processing in {} sec.".format(t2 - t1))
        return res
    return wrapper


def delta_vector_to_inner(v1, v2, crs):
    v1 = chunk_crs_to_camera(v1, crs)
    v2 = chunk_crs_to_camera(v2, crs)

    return (v2 - v1).normalized()


def get_inner_vectors(lat, lon):
    crs = ms.app.document.chunk.crs  # works for rectangular crs as well
    z = delta_vector_to_inner(ms.Vector([lon, lat, 0]), ms.Vector([lon, lat, 1]), crs)
    y = delta_vector_to_inner(ms.Vector([lon, lat, 0]), ms.Vector([lon + 0.001, lat, 0]), crs)
    x = delta_vector_to_inner(ms.Vector([lon, lat, 0]), ms.Vector([lon, lat+0.001, 0]), crs)
    return x, y, -z

def show_message(msg):
    msgBox = QMessageBox()
    print(msg)
    msgBox.setText(_(msg))
    msgBox.exec()


def check_chunk(chunk):
    if chunk is None or len(chunk.cameras) == 0:
        show_message("Empty chunk!")
        return False

    if chunk.crs is None:
        show_message("Initialize chunk coordinate system first")
        return False

    return True


def get_photos_delta(chunk):
    """Returns distance estimation between two cameras in chunk"""
    mid_idx = int(len(chunk.cameras) / 2)
    if mid_idx == 0:
        return ms.Vector([0, 0, 0])

    while mid_idx > 0:
        c1_ref = chunk.cameras[mid_idx].reference.location
        c2_ref = chunk.cameras[mid_idx - 1].reference.location
        if c1_ref is None or c2_ref is None:
            mid_idx -= 1
        else:
            break
    else:
        return ms.Vector([0, 0, 0])

    offset = c1_ref - c2_ref

    for i in range(len(offset)):
        offset[i] = math.fabs(offset[i])
    return offset


def get_chunk_bounds(chunk):
    min_latitude = min(c.reference.location[1] for c in chunk.cameras if c.reference.location is not None)
    max_latitude = max(c.reference.location[1] for c in chunk.cameras if c.reference.location is not None)
    min_longitude = min(c.reference.location[0] for c in chunk.cameras if c.reference.location is not None)
    max_longitude = max(c.reference.location[0] for c in chunk.cameras if c.reference.location is not None)
    offset = get_photos_delta(chunk)
    offset_factor = 2
    delta_latitude = offset_factor * offset.y
    delta_longitude = offset_factor * offset.x

    min_longitude -= delta_longitude
    max_longitude += delta_longitude
    min_latitude -= delta_latitude
    max_latitude += delta_latitude

    return min_latitude, min_longitude, max_latitude, max_longitude


def decompose_rotation_to_ypr(mat):
    r0 = mat.row(0)
    r1 = mat.row(1)
    r2 = mat.row(2)
    sy = (r0[0] * r0[0] + r0[1] * r0[1]) ** 0.5
    singular = sy < 1e-6

    if not singular:
        result = ms.Vector([math.atan2(r1[2], r2[2]), math.atan2(-r0[2], sy), math.atan2(r0[1], r0[0])])
    else:
        result = ms.Vector([math.atan2(-r2[1], r1[1]), math.atan2(-r0[2], sy), 0])

    return result


def decompose_rotation_to_ypr_degrees(mat):
    result = decompose_rotation_to_ypr(mat)
    for i in range(3):
        result[i] = math.degrees(result[i])
    return result


def check_yaw(yaw):
    if yaw > 180:
        yaw -= 360
    elif yaw < -180:
        yaw += 360

    if -90 < yaw < 90:
        return 'north_direction'
    else:
        return 'south_direction'
