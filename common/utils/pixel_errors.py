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

import math
import PhotoScan


def extract_camera_pixel_error(cam):
    chunk = PhotoScan.app.document.chunk

    transform = cam.transform.inv()
    points = chunk.point_cloud.points
    projections = chunk.point_cloud.projections

    calib = cam.sensor.calibration
    npoints = len(points)
    point_index = 0
    total = 0
    n = 0

    for proj in projections[cam]:
        track_id = proj.track_id
        while point_index < npoints and points[point_index].track_id < track_id:
            point_index += 1
        if point_index < npoints and points[point_index].track_id == track_id:
            if not points[point_index].valid:
                continue
            coord = transform * points[point_index].coord
            coord.size = 3

            total += calib.error(coord, proj.coord).norm() ** 2
            n += 1
    error = math.sqrt(total / n)
    return error


def extract_all_cameras_pixel_errors():
    chunk = PhotoScan.app.document.chunk
    cameras = [c for c in chunk.cameras if c.transform]

    res_list = []
    counter = 0
    print('Extracting pixel errors', end='')
    for c in cameras:
        if counter == 10:
            PhotoScan.app.update()
            counter = 0
            print('.', end='')
        e = extract_camera_pixel_error(c)
        res_list.append([c, e])
        counter += 1
    print('\nExtracted successfully!')
    return res_list


def extract_marker_pixel_error(marker):
    total = 0
    n = 0
    for camera in marker.projections.keys():
        reproj = camera.sensor.calibration.project(camera.transform.inv().mulp(marker.position))
        proj = marker.projections[camera].coord
        total += (proj - reproj).norm() ** 2
        n += 1
    error = math.sqrt(total / n)
    return error


def extract_all_markers_pixel_errors():
    chunk = PhotoScan.app.document.chunk
    markers = [m for m in chunk.markers if m.projections]
    res_list = []
    for m in markers:
        e = extract_marker_pixel_error(m)
        res_list.append([m, e])

    return res_list


def get_cameras_by_pixel_errors(pixerror=4.0):
    errors = extract_all_cameras_pixel_errors()
    huge_errors = [e[0] for e in errors if e[1] >= pixerror]
    return huge_errors
