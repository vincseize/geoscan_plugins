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
import cv2
import numpy as np


def rotation_from_mat(mat):
    """
    get matrix rotation component
    """
    size = mat.size
    rotation = PhotoScan.Matrix([[0,0,0],[0,0,0],[0,0,0]])
    for r in range(size[0] - 1):
        for c in range(size[1] - 1):
            rotation[r, c] = mat[r, c]
    return rotation


def parametric_line3d(pt1, pt2):
    """
    parametric equation of line on two points
    """
    x1, y1, z1 = pt1.x, pt1.y, pt1.z
    x2, y2, z2 = pt2.x, pt2.y, pt2.z
    m = x2 - x1
    n = y2 - y1
    p = z2 - z1
    return x1, m, y1, n, z1, p


def line_in_cam(s, e, camera):
    """
    make line in camera using its ray 3d coordinates
    """
    w = camera.sensor.calibration.width
    h = camera.sensor.calibration.height
    x1, m, y1, n, z1, p = parametric_line3d(s, e)
    l = -10000
    maxl = abs(l)
    start = False
    pts = []
    prev = None
    step = 100
    while prev is None:
        tmp_pt = PhotoScan.Vector([x1 + m * l, y1 + n * l, z1 + p * l])
        prev = camera.project(tmp_pt)
        l += step
        if l > maxl:
            break
    while True:
        tmp_pt = PhotoScan.Vector([x1 + m * l, y1 + n * l, z1 + p * l])
        point = camera.project(tmp_pt)
        if point is not None:
            dist = np.linalg.norm(np.array([prev.x - point.x, prev.y - point.y]))
            if dist > 10:
                step = .2
            elif dist < 1:
                step = 20
            else:
                step = 5
            prev = point
            if 0 < point.x < w and 0 < point.y < h:
                start = True
                if dist > 10:
                    pts.append(point)
            elif start:
                break
        elif start:
            break
        l += step
        if l > maxl:
            break
    return pts


def ray(marker, camera):
    """
    ray from camera center to point
    """
    proj = marker.projections[camera]
    pt = proj.coord.x, proj.coord.y

    intrinsic, distortion = convert_cam_params(camera)

    rotation = rotation_from_mat(camera.transform)
    point2docv = np.array(pt, dtype=np.float32)
    point2docv = point2docv.reshape((1, 1, 2))
    undist_pts = cv2.undistortPoints(point2docv, intrinsic, distortion)
    undist_pts = undist_pts.reshape(2)
    pts = undist_pts
    pt = PhotoScan.Vector([pts[0], pts[1], 1])
    d = rotation * pt
    d = PhotoScan.Vector([d[0], d[1], d[2], 1])
    ans = camera.transform.col(3) - d
    return camera.transform.col(3), ans


def convert_cam_params(camera):
    return convert_sensor_params(camera.sensor)


def convert_sensor_params(sensor):
    c = sensor.calibration
    intrinsic = np.array([[c.f + c.b1, c.b2, c.width / 2 + c.cx], [0, c.f, c.height / 2 + c.cy], [0, 0, 1]])
    distortion = np.array([c.k1, c.k2, c.p1, c.p2, c.k3, c.k4, 0, 0])
    return intrinsic, distortion


def distort(point, camera):
    intrinsic, distortion = convert_cam_params(camera)
    x = (point[0] - intrinsic[0,2]) / intrinsic[0,0]
    y = (point[1] - intrinsic[1,2]) / intrinsic[1,1]
    c = camera.sensor.calibration
    r2 = x*x + y*y
    x_distort = x * (1 + c.k1 * r2 + c.k2 * r2 * r2 + c.k3 * r2 * r2 * r2)
    y_distort = y * (1 + c.k1 * r2 + c.k2 * r2 * r2 + c.k3 * r2 * r2 * r2)

    x_distort += 2 * c.p1 * x * y + c.p2 * (r2 + 2 * x * x)
    y_distort += c.p1 * (r2 + 2 * y * y) + 2 * c.p2 * x * y

    x_distort = x_distort * intrinsic[0, 0] + intrinsic[0, 2]
    y_distort = y_distort * intrinsic[1, 1] + intrinsic[1, 2]
    return PhotoScan.Vector([x_distort, y_distort])
