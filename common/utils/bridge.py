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

import PhotoScan
import os
from itertools import zip_longest, chain
from functools import partial
from operator import is_not


def real_vertices(s, default_z=None):
    """
    mostly done to handle case when vertices are defined by markers.
    also handles existence of different coordinate systems for shapes and chunk
    :param s: shape to work with
    :param default_z: default Z coordinate
    :type s: ps.Shape
    :rtype: List[ps.Vector]
    :return: list of shape vertices in cameras coordinates
    """
    if s.vertices:
        shapes_crs = PhotoScan.app.document.chunk.shapes.crs
        chunk_crs = PhotoScan.app.document.chunk.crs
        raw_vertices = s.vertices
        if not s.has_z:
            if default_z is not None:
                raw_vertices = [PhotoScan.Vector((*v, default_z)) for v in raw_vertices]
            else:
                raise ValueError('Shape has no Z coordinate!')
        vertices = [PhotoScan.CoordinateSystem.transform(v, shapes_crs, chunk_crs) for v in raw_vertices]
        return [chunk_crs_to_camera(c) for c in vertices]
    elif s.vertex_ids:
        return [next(m for m in PhotoScan.app.document.chunk.markers if m.key == key).position for key in s.vertex_ids]
    return []


def real_vertices_in_shape_crs(s):
    """
    mostly done to handle case when vertices are defined by markers.
    also handles existence of different coordinate systems for shapes and chunk
    :param s: shape to work with
    :type s: ps.Shape
    :rtype: List[ps.Vector]
    :return: list of shape vertices in shape coordinates
    """
    shapes_crs = PhotoScan.app.document.chunk.shapes.crs
    chunk_crs = PhotoScan.app.document.chunk.crs
    vertices = [PhotoScan.CoordinateSystem.transform(camera_coordinates_to_chunk_crs(v), chunk_crs, shapes_crs)
                for v in real_vertices(s)]
    return vertices


def chunk_crs_to_image(coords, cam, crs=None):
    """
    project point from crs to image
    :param coords: point in chunk crs
    :param cam: camera to which project point
    :param crs: optional coordinate system
    :return: coordinates in image
    """
    in_cam = chunk_crs_to_camera(coords, crs)
    res = cam.project(in_cam)
    if res is not None:
        if 0 < res.x < cam.sensor.width and 0 < res.y < cam.sensor.height:
            return res
    return None


def chunk_crs_to_geocentric(coords, crs=None):
    """
    project point from crs to geocentric
    :param coords: point in chunk crs
    :param crs: optional coordinate system
    :return: coordinates in geocentric
    """
    if crs is None:
        crs = PhotoScan.app.document.chunk.crs
    vec = PhotoScan.Vector(coords)
    in_geocentric = crs.unproject(vec)
    return in_geocentric


def chunk_crs_to_camera(coords, crs=None):
    """
    project point from crs to camera coordinates (inner)
    :param coords: point in chunk crs
    :param crs: optional coordinate system
    :return: coordinates in camera system (inner)
    """
    in_geocentric = chunk_crs_to_geocentric(coords, crs)
    return geocentric_to_camera(in_geocentric)


def geocentric_to_camera(in_geocentric):
    """
    project point from geocentric to camera coordinates (inner)
    :param in_geocentric: point in geocentric
    :return: coordinates in camera system (inner)
    """
    return PhotoScan.app.document.chunk.transform.matrix.inv().mulp(in_geocentric)


def get_geocentric_to_localframe(point):
    """
    localframe is metric coordinate system with center in point and z direction is opposite to gravity
    :param point: point in geocentric
    :return: transform matrix from geocetric to local system based on point
    """
    return PhotoScan.app.document.chunk.crs.localframe(point)  # geocentric to local


def get_camera_coordinates_to_localframe(point):
    """
    see get_geocentric_to_localframe
    :param point: point in camera coordinate system (inner)
    :return: transform matrix from camera coordinates to local system based on point
    """
    geoc_to_local = get_geocentric_to_localframe(camera_coordinates_to_geocentric(point))
    inner_to_local = geoc_to_local * PhotoScan.app.document.chunk.transform.matrix
    return inner_to_local


def camera_coordinates_to_geocentric(point):
    """
    :param point: point in camera coordinates (inner)
    :return: point in geocentric
    """
    return PhotoScan.app.document.chunk.transform.matrix.mulp(point)


def camera_coordinates_to_chunk_crs(point):
    """
    :param point: point in camera coordinates (inner)
    :return: point in chunk crs
    """
    pt3d = camera_coordinates_to_geocentric(point)
    crs = PhotoScan.app.document.chunk.crs
    proj = crs.project(pt3d)
    return proj


def visible_in_cameras(coords, check_existence=False, check_one=False, is_latlon=True):
    """
    :param check_existence: check existence of image on HDD
    :param check_one: check at least one camera viewing point
    :param is_latlon: point in latlon or in camera coordinates
    :returns cameras which contain point coords
    :rtype: List[ps.Camera]
    """
    cameras = PhotoScan.app.document.chunk.cameras
    res = []
    width = cameras[0].sensor.calibration.width
    height = cameras[0].sensor.calibration.height
    for cam in cameras:
        if cam.enabled:
            if check_existence and not os.path.exists(cam.photo.path):
                continue
            width = cam.sensor.calibration.width
            height = cam.sensor.calibration.height
            if is_latlon:
                projected = chunk_crs_to_image(coords, cam)
            else:
                projected = cam.project(coords)
            if projected:
                if width * 0.1 < projected.x < width - width * .1 and height * .1 < projected.y < height - height * .1:
                    res.append((cam, projected))
                    if check_one:
                        return True

    # sorted_res = []
    res.sort(key=lambda x: 0.3 * abs(1 - x[1].x / width * 2) + 0.7 * abs(1 - x[1].y / height * 2), reverse=True)
    lower = filter(lambda val: 1 - (val[1].y / height * 2) > 0, res)
    upper = filter(lambda val: 1 - (val[1].y / height * 2) <= 0, res)
    zipped = zip_longest(lower, upper)
    merged = list(filter(partial(is_not, None), list(chain.from_iterable(zipped))))
    merged = [m[0] for m in merged]
    return merged


def cameras_on(tower_marker, group=None, skip_disabled=True):
    """
    cameras seeing specific marker
    :param group: optional group label
    """
    from .markers import get_marker_position_or_location
    cameras = PhotoScan.app.document.chunk.cameras
    for cam in cameras:
        if cam.center is None:
            continue
        if group is not None:
            if cam.group is None:
                continue
            if cam.group is not None and cam.group.label != group:
                continue
        if group is None:
            if not cam.enabled and skip_disabled:
                continue
        width = cam.sensor.calibration.width
        height = cam.sensor.calibration.height
        projected = cam.project(get_marker_position_or_location(tower_marker))
        if projected:
            if 0 < projected.x < width and 0 < projected.y < height:
                yield cam


def get_estimated_camera_position(camera):
    chunk = PhotoScan.app.document.chunk
    estimated_coord = chunk.crs.project(chunk.transform.matrix.mulp(camera.center)) #estimated XYZ

    T = chunk.transform.matrix
    m = chunk.crs.localframe(T.mulp(camera.center)) #transformation matrix to the LSE coordinates in the given point
    R = (m * T * camera.transform * PhotoScan.Matrix().Diag([1, -1, -1, 1])).rotation()
    estimated_ypr = PhotoScan.utils.mat2ypr(R) #estimated orientation angles
    return estimated_coord, estimated_ypr


def project_point(camera, point):
    """
    project point in camera coordinates to image
    """
    if not point:
        return
    pos = camera.project(point)
    try:
        if 0 < pos.x < camera.sensor.calibration.width and 0 < pos.y < camera.sensor.calibration.height:
            return pos
    except ValueError:
        pass
    return None