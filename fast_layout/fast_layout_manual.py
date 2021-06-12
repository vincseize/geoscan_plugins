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

import copy
import math

import Metashape as ms
from common.utils.bridge import chunk_crs_to_camera
from common.utils.helpers import pairwise
from fast_layout.utils import time_measure, delta_vector_to_inner, get_chunk_bounds, get_inner_vectors, check_yaw, \
    check_chunk


def estimate_rotation_matrices(chunk, i, j):
    """
    Evaluates rotation matrices for cameras that have location
    algorithm is straightforward: we assume copter has zero pitch and roll,
    and yaw is evaluated from current copter direction.
    Current direction is evaluated simply subtracting location of
    current camera from the next camera location
    i and j are unit axis vectors in inner coordinate system, i || North
    :param chunk: chunk which is being processed
    :param i: north direction in inner crs
    :param j: west direction in inner crs
    :return: dict with rotation angles for every selected camera for which angles estimation succeeded
    """

    groups = copy.copy(chunk.camera_groups)

    groups.append(None)
    rotation_angles = {}
    crs = ms.app.document.chunk.camera_crs
    if not crs:
        crs = ms.app.document.chunk.crs

    for group in groups:
        group_cameras = [c for c in chunk.cameras if c.group == group]

        if len(group_cameras) == 0:
            continue

        if len(group_cameras) == 1:
            if group_cameras[0].reference.rotation is None:
                rotation_angles[group_cameras[0].key] = ms.Vector([0,0,0])
            else:
                rotation_angles[group_cameras[0].key] = group_cameras[0].reference.rotation
            continue

        prev_yaw = 0
        for c, next_camera in pairwise(group_cameras):
            if c.reference.rotation is None:
                if c.reference.location is None or next_camera.reference.location is None:
                    rotation_angles[c.key] = ms.Vector([prev_yaw, 0, 0])
                    continue
                direction = delta_vector_to_inner(c.reference.location, next_camera.reference.location, crs)

                prev_yaw = yaw = math.degrees(math.atan2(-direction * i, direction * j)) + 90
                rotation_angles[c.key] = ms.Vector([yaw, 0, 0])
            else:
                rotation_angles[c.key] = c.reference.rotation
                prev_yaw = c.reference.rotation.x

        # process last camera
        if group_cameras[-1].reference.rotation is None:
            rotation_angles[group_cameras[-1].key] = rotation_angles[group_cameras[-2].key]
        else:
            rotation_angles[group_cameras[-1].key] = group_cameras[-1].reference.rotation
    return rotation_angles


@time_measure
def align_cameras(chunk, mount_angle=0):
    """
    Align unaligned selected cameras in given chunk
    :param chunk: chunk holding cameras to be aligned
    """

    min_latitude, min_longitude, max_latitude, max_longitude = get_chunk_bounds(chunk)
    if chunk.transform.scale is None:
        chunk.transform.scale = 1
        chunk.transform.rotation = ms.Matrix([[1,0,0], [0,1,0], [0,0,1]])
        chunk.transform.translation = ms.Vector([0,0,0])

    i, j, k = get_inner_vectors(min_latitude, min_longitude) # i || North
    rotation_angles = estimate_rotation_matrices(chunk, i, j)

    for c in chunk.cameras:
        if c.transform is not None or not c.selected:
            continue

        location = c.reference.location
        if location is None:
            continue
        chunk_coordinates = chunk_crs_to_camera(location)
        rotation = rotation_angles[c.key]

        if check_yaw(rotation.x) == 'north_direction':
            yaw = math.radians(rotation.x + mount_angle + 90)  # correction
        else:
            yaw = math.radians(rotation.x - mount_angle + 90)
        roll = math.radians(rotation.z)
        pitch = math.radians(rotation.y)

        roll_mat = ms.Matrix([[1, 0, 0], [0, math.cos(roll), -math.sin(roll)], [0, math.sin(roll), math.cos(roll)]])
        pitch_mat = ms.Matrix([[math.cos(pitch), 0, math.sin(pitch)], [0, 1, 0], [-math.sin(pitch), 0, math.cos(pitch)]])
        yaw_mat = ms.Matrix([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])

        r = roll_mat * pitch_mat * yaw_mat
        ii = r[0, 0] * i + r[1, 0] * j + r[2, 0] * k
        jj = r[0, 1] * i + r[1, 1] * j + r[2, 1] * k
        kk = r[0, 2] * i + r[1, 2] * j + r[2, 2] * k
        c.transform = ms.Matrix([[ii.x, jj.x, kk.x, chunk_coordinates[0]],
                                 [ii.y, jj.y, kk.y, chunk_coordinates[1]],
                                 [ii.z, jj.z, kk.z, chunk_coordinates[2]],
                                 [0, 0, 0, 1]])


def run_camera_alignment_manual(mount_angle):
    if not check_chunk(ms.app.document.chunk):
        return

    try:
        align_cameras(ms.app.document.chunk, mount_angle)
    except Exception as e:
        print(e)


if __name__ == "__main__":
    pass
