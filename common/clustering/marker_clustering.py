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

import logging
from collections import defaultdict, OrderedDict
from itertools import combinations

import PhotoScan as ps
import numpy as np

from common.utils import loglevels
from common.cg.basis_line_ops import convert_cam_params
from common.utils.bridge import camera_coordinates_to_geocentric
from common.cg.geometry import parametric_line
from common.clustering.icp import icp, transform_rf_to_array, find_distances_indices

logger = logging.getLogger("powerlines")

class Ray:
    def __init__(self, cam, proj_coord):
        self.cam = cam
        self.coord = proj_coord
        self.ray = ray_eqn(cam, proj_coord)


def ray_ray_dist(ray1, ray2):
    if ray1.cam == ray2.cam:
        return 1000
    return skew_line_dist_3d(ray1.ray, ray2.ray)


def skew_line_dist_3d(line1, line2):
    x1, m1, y1, n1, z1, p1 = parametric_line(line1[0], line1[1])
    x2, m2, y2, n2, z2, p2 = parametric_line(line2[0], line2[1])
    A = np.array([[m1*m2 + n1*n2 + p1*p2, -m1**2 - n1**2 - p1**2],
                  [m2**2 + n2**2 + p2**2, -m1*m2 - n1*n2 - p1*p2]])
    b = np.array([(x1-x2)*m1 + (y1-y2)*n1 + (z1-z2)*p1, (x1-x2)*m2 + (y1-y2)*n2 + (z1-z2)*p2])
    X = np.linalg.solve(A, b)
    x = x1 + m1 * X[1]
    y = y1 + n1 * X[1]
    z = z1 + p1 * X[1]
    x_ = x2 + m2 * X[0]
    y_ = y2 + n2 * X[0]
    z_ = z2 + p2 * X[0]
    return np.linalg.norm([x-x_, y-y_, z-z_])


def ray_eqn(camera, point2d, cx=None, cy=None):
    """
    formula: r*x+t where x is undistorted and normalized
    """
    import cv2
    intrinsic, distortion = convert_cam_params(camera)
    if cx is not None and cy is not None:
        intrinsic[0,2] = cx
        intrinsic[1,2] = cy
    transform = np.array(camera.transform).reshape(4, 4)
    rotation = transform[:3,:3]

    point2docv = np.array([point2d.x, point2d.y])
    point2docv = point2docv.reshape((1, 1, 2))
    undist_pts = cv2.undistortPoints(point2docv, intrinsic, distortion)
    undist_pts = undist_pts.reshape(2)
    undist_pts = np.concatenate([undist_pts, np.array([1])])
    d = np.dot(rotation, undist_pts)
    ans = transform[:3, 3].flatten() - d

    pos = ps.Vector([ans[0], ans[1], ans[2]])
    # m = ps.app.document.chunk.addMarker()
    # m.reference.location = camera_coordinates_to_chunk_crs(pos)
    cam_pos = transform[:3, 3].flatten()
    cam_pos_ps = ps.Vector([cam_pos[0], cam_pos[1], cam_pos[2]])
    return camera_coordinates_to_geocentric(cam_pos_ps), camera_coordinates_to_geocentric(pos)


def order_cams_by_dist(marker):
    lines = {}
    for cam, proj in marker.projections.items():
        lines[cam.label] = ray_eqn(cam, proj.coord)
    dists = defaultdict(dict)
    for (cam1, l1), (cam2, l2) in combinations(lines.items(), 2):
        dist = skew_line_dist_3d(l1, l2)
        dists[cam1][cam2] = dist
        dists[cam2][cam1] = dist

    ordered_cams = OrderedDict(sorted(dists.items(), key=lambda x: sum(x[1].values())))
    return ordered_cams


def clear_cams(marker, min_proj=5):
    ordered_cams = order_cams_by_dist(marker)
    i = 0
    while len(marker.projections.keys()) > min_proj:
        i += 1
        worst_cam_label = list(ordered_cams.keys())[-i]
        try:
            worst_cam = next(cam for cam in ps.app.document.chunk.cameras if cam.label == worst_cam_label)
        except StopIteration:
            break
        marker.projections[worst_cam] = None


def cameras_rays_dist(marker, cam1, cam2):
    if marker.projections[cam1] and marker.projections[cam2]:
        l1 = ray_eqn(cam1, marker.projections[cam1])
        l2 = ray_eqn(cam2, marker.projections[cam2])
        return skew_line_dist_3d(l1, l2)
    return float('inf')


def simple_correspondence(reference, found, mindist=10):
    """
    deprecated. use rigid correspondence
    """
    resulting = []
    ref_a, found_a = transform_rf_to_array(reference, found)
    d, indices = find_distances_indices(ref_a, found_a)
    ref_del = []
    for row, col in enumerate(indices):
        if d[row] < mindist:
            found[col].label = reference[row].label
            found[col].reference.location = reference[row].reference.location
            resulting.append(found[col])
            ref_del.append(reference[row])
    ps.app.document.chunk.remove([m for m in found if m not in resulting])
    ps.app.document.chunk.remove(ref_del)
    return resulting

def rigid_correspondence(reference, found, mindist=10):
    """
    given rigid reference markers configuration find the best markers in found matching this configuration
    :returns transformation matrix, resulting markers
    """
    good_approx = 1.
    ref_a, found_a = transform_rf_to_array(reference, found)
    T, distances, indices = icp(ref_a, found_a, mindist)
    good_markers = np.count_nonzero(distances < good_approx)
    logging.log(loglevels.S_DEBUG, "distances: {}".format(distances))
    if indices is None:
        return None, None
    if good_markers < 3:
        ps.app.document.chunk.remove(found)
        return None, None
    transformation_matrix = ps.Matrix(T)
    ref_del = []
    resulting = []
    for row, col in enumerate(indices):
        translated_ref = transformation_matrix.mulp(ps.Vector(ref_a[row]))
        loc = ps.app.document.chunk.crs.project(translated_ref)
        if distances[row] < good_approx:
            found[col].label = reference[row].label
            found[col].reference.location = loc
            resulting.append(found[col])
            ref_del.append(reference[row])
        else:
            reference[row].reference.location = loc
    ps.app.document.chunk.remove([m for m in found if m not in resulting])
    ps.app.document.chunk.remove(ref_del)
    return transformation_matrix, resulting

