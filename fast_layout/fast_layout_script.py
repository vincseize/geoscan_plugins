# for clients

import copy
import math
import os
import time
from itertools import tee

import PhotoScan as ps


def chunk_crs_to_camera(coords, crs=None):
    """
    project point from crs to camera coordinates (inner)
    :param coords: point in chunk crs
    :param crs: optional coordinate system
    :return: coordinates in camera system (inner)
    """
    in_geocentric = chunk_crs_to_geocentric(coords, crs)
    return geocentric_to_camera(in_geocentric)


def chunk_crs_to_geocentric(coords, crs=None):
    """
    project point from crs to geocentric
    :param coords: point in chunk crs
    :param crs: optional coordinate system
    :return: coordinates in geocentric
    """
    if crs is None:
        crs = ps.app.document.chunk.crs
    vec = ps.Vector(coords)
    in_geocentric = crs.unproject(vec)
    return in_geocentric


def geocentric_to_camera(in_geocentric):
    """
    project point from geocentric to camera coordinates (inner)
    :param in_geocentric: point in geocentric
    :return: coordinates in camera system (inner)
    """
    return ps.app.document.chunk.transform.matrix.inv().mulp(in_geocentric)


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


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
    crs = ps.app.document.chunk.crs  # works for rectangular crs as well
    z = delta_vector_to_inner(ps.Vector([lon, lat, 0]), ps.Vector([lon, lat, 1]), crs)
    y = delta_vector_to_inner(ps.Vector([lon, lat, 0]), ps.Vector([lon + 0.001, lat, 0]), crs)
    x = delta_vector_to_inner(ps.Vector([lon, lat, 0]), ps.Vector([lon, lat+0.001, 0]), crs)
    return x, y, -z


def check_chunk(chunk):
    if chunk is None or len(chunk.cameras) == 0:
        print("Empty chunk!")
        return False

    if chunk.crs is None:
        print("Initialize chunk coordinate system first")
        return False

    return True


# returns distance estimation between two cameras in chunk
def get_photos_delta(chunk):
    mid_idx = int(len(chunk.cameras) / 2)
    if mid_idx == 0:
        return ps.Vector([0, 0, 0])

    while mid_idx > 0:
        c1_ref = chunk.cameras[mid_idx].reference.location
        c2_ref = chunk.cameras[mid_idx - 1].reference.location
        if c1_ref is None or c2_ref is None:
            mid_idx -= 1
        else:
            break
    else:
        return ps.Vector([0, 0, 0])

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
        result = ps.Vector([math.atan2(r1[2], r2[2]), math.atan2(-r0[2], sy), math.atan2(r0[1], r0[0])])
    else:
        result = ps.Vector([math.atan2(-r2[1], r1[1]), math.atan2(-r0[2], sy), 0])

    return result


def decompose_rotation_to_ypr_degrees(mat):
    result = decompose_rotation_to_ypr(mat)
    for i in range(3):
        result[i] = math.degrees(result[i])
    return result


def estimate_rotation_matrices(chunk, i, j):
    '''
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
    '''
    groups = copy.copy(chunk.camera_groups)

    groups.append(None)
    rotation_angles = {}
    crs = ps.app.document.chunk.camera_crs
    if not crs:
        crs = ps.app.document.chunk.crs

    for group in groups:
        group_cameras = [c for c in chunk.cameras if c.group == group]

        if len(group_cameras) == 0:
            continue

        if len(group_cameras) == 1:
            if group_cameras[0].reference.rotation is None:
                rotation_angles[group_cameras[0].key] = ps.Vector([0,0,0])
            else:
                rotation_angles[group_cameras[0].key] = group_cameras[0].reference.rotation
            continue

        prev_yaw = 0
        for c, next_camera in pairwise(group_cameras):
            if c.reference.rotation is None:
                if c.reference.location is None or next_camera.reference.location is None:
                    rotation_angles[c.key] = ps.Vector([prev_yaw, 0, 0])
                    continue
                direction = delta_vector_to_inner(c.reference.location, next_camera.reference.location, crs)

                prev_yaw = yaw = math.degrees(math.atan2(-direction * i, direction * j))
                rotation_angles[c.key] = ps.Vector([yaw, 0, 0])
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
def align_cameras(chunk):
    """
    Align unaligned selected cameras in given chunk
    :param chunk: chunk holding cameras to be aligned
    """

    mount_angle = ps.app.getFloat(label=_("Camera mount angle"), value=0)

    min_latitude, min_longitude, max_latitude, max_longitude = get_chunk_bounds(chunk)
    if chunk.transform.scale is None:
        chunk.transform.scale = 1
        chunk.transform.rotation = ps.Matrix([[1,0,0], [0,1,0], [0,0,1]])
        chunk.transform.translation = ps.Vector([0,0,0])

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

        yaw = math.radians(rotation.x + mount_angle + 90)  # correction
        roll = math.radians(rotation.z)
        pitch = math.radians(rotation.y)

        roll_mat = ps.Matrix([[1, 0, 0], [0, math.cos(roll), -math.sin(roll)], [0, math.sin(roll), math.cos(roll)]])
        pitch_mat = ps.Matrix([[math.cos(pitch), 0, math.sin(pitch)], [0, 1, 0], [-math.sin(pitch), 0, math.cos(pitch)]])
        yaw_mat = ps.Matrix([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])

        r = roll_mat * pitch_mat * yaw_mat
        ii = r[0, 0] * i + r[1, 0] * j + r[2, 0] * k
        jj = r[0, 1] * i + r[1, 1] * j + r[2, 1] * k
        kk = r[0, 2] * i + r[1, 2] * j + r[2, 2] * k
        c.transform = ps.Matrix([[ii.x, jj.x, kk.x, chunk_coordinates[0]],
                                 [ii.y, jj.y, kk.y, chunk_coordinates[1]],
                                 [ii.z, jj.z, kk.z, chunk_coordinates[2]],
                                 [0, 0, 0, 1]])


def run_camera_alignment():
    if not check_chunk(ps.app.document.chunk):
        return

    try:
        align_cameras(ps.app.document.chunk)
    except Exception as e:
        print(e)


if __name__ == '__main__':
    run_camera_alignment()
