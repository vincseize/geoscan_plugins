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
import random
import textwrap

import Metashape as ms
from common.utils.bridge import chunk_crs_to_camera
from common.utils.helpers import pairwise
from collections import deque
from statistics import mean

from fast_layout.utils import delta_vector_to_inner, get_chunk_bounds, get_inner_vectors, time_measure, check_chunk


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

    try:
        tacks = get_tacks(chunk, chunk.cameras)
    except Exception as e:
        print(e)
        return

    if not tacks:
        raise ValueError('Error. Tacks are None.')

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
        first_camera = True

        for c, next_camera in pairwise(group_cameras):
            if not c.reference.rotation:
                continue

            if c.reference.location is None or next_camera.reference.location is None:
                rotation_angles[c.key] = ms.Vector([prev_yaw, 0, 0])
                continue

            if first_camera:
                current_tack = [tack_number for tack_number in tacks.keys() if c in tacks[tack_number]][0]
                first_camera = False

            direction = delta_vector_to_inner(c.reference.location, next_camera.reference.location, crs)
            yaw = math.degrees(math.atan2(-direction * i, direction * j))

            if next_camera in tacks[current_tack]:
                rotation_angles[c.key] = ms.Vector([yaw, c.reference.rotation.y, c.reference.rotation.z])
                prev_yaw = yaw
            else:
                rotation_angles[c.key] = ms.Vector([prev_yaw, c.reference.rotation.y, c.reference.rotation.z])
                current_tack = [tack_number for tack_number in tacks.keys() if next_camera in tacks[tack_number]][0]

        # process last camera
        rotation_angles[group_cameras[-1].key] = rotation_angles[group_cameras[-2].key]
    tack_angle = dict()
    for n, cameras in tacks.items():
        mount_angles = [until360(rotation_angles[camera.key][0] + 90) - get_camera_orientation(chunk, camera) for camera
                        in tacks[n] if camera.center and camera.key in rotation_angles]
        plus_angles = 0
        for mount_angle in mount_angles:
            if get_sign(mount_angle):
                plus_angles += 1
            if plus_angles >= len(mount_angles) - plus_angles:
                tack_angle.update({n: True})
            else:
                tack_angle.update({n: False})

    return rotation_angles, tacks, tack_angle


def get_tacks(chunk, cameras):
    tacks = dict()
    tack_number = 0
    start_camera = cameras[0]
    i = 0
    if start_camera.center:
        prev_yaw = get_camera_orientation(chunk, cameras[0])
        i += 1
    else:
        while not cameras[i].reference.rotation:
            i += 1
        if i == len(cameras):
            raise ValueError('Error. Tacks are None.')

        prev_yaw = cameras[i].reference.rotation.x
    tacks.update({tack_number: [cameras[0]]})

    for i in range(i, len(cameras)):
        if cameras[i].center:
            yaw = get_camera_orientation(chunk, cameras[i])
        else:
            try:
                yaw = cameras[i].reference.rotation.x
            except Exception:
                continue

        if math.fabs(until360(yaw) - until360(prev_yaw)) < 90:
            tacks[tack_number].append(cameras[i])
        else:
            tack_number += 1
            tacks.update({tack_number: [cameras[i]]})

        prev_yaw = yaw

    return tacks


def get_camera_orientation(chunk, camera):
    T = chunk.transform.matrix
    m = chunk.crs.localframe(T.mulp(camera.center))
    R = m * T * camera.transform * ms.Matrix().Diag([1, -1, -1, 1])
    row = list()

    for j in range(0, 3):  # creating normalized rotation matrix 3x3
        row.append(R.row(j))
        row[j].size = 3
        row[j].normalize()
    R = ms.Matrix([row[0], row[1], row[2]])
    yaw, pitch, roll = ms.utils.mat2ypr(R)
    return yaw


def until360(angle):
    if angle > 360:
        return angle - 360
    elif angle < 0:
        return angle + 360
    else:
        return angle


def until180(angle):
    if angle > 180:
        return angle - 180
    else:
        return angle


def get_sign(value):
    return value > 0


def calculate_mount_angle(last_angles, future_angles):
    if last_angles and future_angles:
        mount_angle = (math.fabs(mean(last_angles)) + math.fabs(mean(future_angles))) / 2
    elif not last_angles and future_angles:
        mount_angle = math.fabs(mean(future_angles))
    elif not future_angles and last_angles:
        mount_angle = math.fabs(mean(last_angles))
    else:
        mount_angle = 0
    mount_angle += 90
    return mount_angle


@time_measure
def align_cameras(chunk):
    """
    Align unaligned selected cameras in given chunk
    :param chunk: chunk holding cameras to be aligned
    """
    if not [cam for cam in chunk.cameras if cam.reference.rotation]:
        ms.app.messageBox(textwrap.fill("Please, load rotation angles to use automatic mode", 65))
        return

    min_latitude, min_longitude, max_latitude, max_longitude = get_chunk_bounds(chunk)
    if chunk.transform.scale is None:
        chunk.transform.scale = 1
        chunk.transform.rotation = ms.Matrix([[1,0,0], [0,1,0], [0,0,1]])
        chunk.transform.translation = ms.Vector([0,0,0])

    i, j, k = get_inner_vectors(min_latitude, min_longitude) # i || North
    try:
        rotation_angles, tacks, tack_angle = estimate_rotation_matrices(chunk, i, j)
    except Exception as e:
        print(e)
        raise AssertionError('Sth in estimate_rotation_matrices')
    if not rotation_angles:
        raise ValueError('Error. No rotation angles.')

    last2cameras = deque(maxlen=2)
    last2cameras.append('start')
    future2cameras = list()
    untransformed = deque()

    for c in chunk.cameras:
        if c.key not in rotation_angles:
            continue

        if c.transform is not None or not c.selected:
            if not last2cameras and len(future2cameras) < 2:
                future2cameras.append(c)
                continue
            if future2cameras:
                last_mount_angles = [until360(rotation_angles[c.key][0] + 90) - get_camera_orientation(chunk, c) for c in lastcameras]
                future_mount_angles = [until360(rotation_angles[c.key][0] + 90) - get_camera_orientation(chunk, c) for c in future2cameras]

                future2cameras = list()
                mount_angle = calculate_mount_angle(last_mount_angles, future_mount_angles)

                while untransformed:
                    untransformed_camera = untransformed.popleft()
                    apply_transform(untransformed_camera, rotation_angles, mount_angle, i, j, k, tacks, tack_angle)

            last2cameras.append(c)
            continue

        if last2cameras:
            lastcameras = [c for c in last2cameras if c != 'start']
            last2cameras.clear()

        untransformed.append(c)

    if untransformed:
        last_mount_angles = [until360(rotation_angles[c.key][0] + 90) - get_camera_orientation(chunk, c) for c in
                             lastcameras]
        while untransformed:
            untransformed_camera = untransformed.popleft()
            mount_angle = calculate_mount_angle(last_angles=last_mount_angles, future_angles=None)
            apply_transform(untransformed_camera, rotation_angles, mount_angle, i, j, k, tacks, tack_angle)


def apply_transform(camera, rotation_angles, mount_angle, i, j, k, tacks, tack_angle):
    location = camera.reference.location
    if location is None:
        return
    chunk_coordinates = chunk_crs_to_camera(location)
    rotation = rotation_angles[camera.key]

    camera_tack = None
    for n in tacks.keys():
        if camera in tacks[n]:
            camera_tack = n
            break

    if not camera_tack and camera_tack != 0:
        raise AssertionError('Error. No such camera in tacks')

    if camera_tack in tack_angle:
        if tack_angle[camera_tack]:
            yaw = math.radians(rotation.x - mount_angle + 90)  # correction
        else:
            yaw = math.radians(rotation.x + mount_angle + 90)
    else:
        random_key = random.choice(list(tack_angle.keys()))
        if tack_angle[random_key] and random_key % 2 == camera_tack % 2:
            yaw = math.radians(rotation.x - mount_angle + 90)
        elif tack_angle[random_key] and random_key % 2 != camera_tack % 2:
            yaw = math.radians(rotation.x + mount_angle + 90)
        elif not tack_angle[random_key] and random_key % 2 != camera_tack % 2:
            yaw = math.radians(rotation.x - mount_angle + 90)
        elif not tack_angle[random_key] and random_key % 2 == camera_tack % 2:
            yaw = math.radians(rotation.x + mount_angle + 90)

    roll = math.radians(rotation.z)
    pitch = math.radians(rotation.y)

    roll_mat = ms.Matrix([[1, 0, 0], [0, math.cos(roll), -math.sin(roll)], [0, math.sin(roll), math.cos(roll)]])
    pitch_mat = ms.Matrix([[math.cos(pitch), 0, math.sin(pitch)], [0, 1, 0], [-math.sin(pitch), 0, math.cos(pitch)]])
    yaw_mat = ms.Matrix([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])

    r = roll_mat * pitch_mat * yaw_mat
    ii = r[0, 0] * i + r[1, 0] * j + r[2, 0] * k
    jj = r[0, 1] * i + r[1, 1] * j + r[2, 1] * k
    kk = r[0, 2] * i + r[1, 2] * j + r[2, 2] * k
    camera.transform = ms.Matrix([[ii.x, jj.x, kk.x, chunk_coordinates[0]],
                                 [ii.y, jj.y, kk.y, chunk_coordinates[1]],
                                 [ii.z, jj.z, kk.z, chunk_coordinates[2]],
                                 [0, 0, 0, 1]])


def run_camera_alignment_automatic():
    if not check_chunk(ms.app.document.chunk):
        return

    try:
        align_cameras(ms.app.document.chunk)
    except Exception as e:
        print(e)


if __name__ == '__main__':
    pass
