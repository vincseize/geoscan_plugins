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
import numpy as np
from scipy.optimize import leastsq
from common.utils.bridge import geocentric_to_camera


def unit_vector(vector):
    """ Returns the unit vector of the vector.  """
    return vector / np.linalg.norm(vector)


def angle_between(v1, v2):
    """ Returns the angle in radians between vectors 'v1' and 'v2'::
    """
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))


def triangle_normal(f):
    p1, p2, p3 = f
    A = p2 - p1
    B = p3 - p1
    cross = np.cross(A, B)
    return cross / np.linalg.norm(cross)


def cross(p1, p2):
    res = np.cross(p1, p2)
    return PhotoScan.Vector((res[0], res[1], res[2]))


def proj_mat(p1, p2, p3):
    """
    projection matrix to plane given by 3 points
    """
    xbase = PhotoScan.Vector.normalized(p2 - p1)
    zbase = PhotoScan.Vector.normalized(cross((p3 - p1), xbase))
    ybase = PhotoScan.Vector.normalized(cross(xbase, zbase))
    proj = PhotoScan.Matrix([[xbase.x, xbase.y, xbase.z, 0], [ybase.x, ybase.y, ybase.z, 0], [zbase.x, zbase.y, zbase.z, 0],[0, 0, 0, 1]])
    return proj


def parametric_line(pt1, pt2):
    x1, y1, z1 = pt1
    x2, y2, z2 = pt2
    m = x2 - x1
    n = y2 - y1
    p = z2 - z1
    return x1, m, y1, n, z1, p


def rotate(origin, point, angle):
    """
    Rotate a point counterclockwise by a given angle around a given origin.

    The angle should be given in radians.
    """
    ox, oy = origin
    px, py = point

    qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
    qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
    return qx, qy


def plane_three_pts(points):
    p1, p2, p3 = points[:3]
    v1 = p3 - p1
    v2 = p2 - p1
    cp = np.cross(v1, v2)
    a, b, c = cp
    d = np.dot(cp, p3)
    return np.array([a, b, c, d])

def plane_fitting(points):
    # Inital guess of the plane
    p0 = plane_three_pts(points)
    if len(points) == 3:
        return p0
    XYZ = np.array(points).T
    sol = leastsq(residuals, p0, args=(None, XYZ))[0]
    return sol

def f_min(X, p):
    plane_xyz = p[0:3]
    distance = (plane_xyz * X.T).sum(axis=1) + p[3]
    return distance / np.linalg.norm(plane_xyz)

def residuals(params, signal, X):
    return f_min(X, params)

def planes_angle(p1, p2):
    n1, n2 = p1[:2], p2[:2]
    sign = np.sign(np.cross(n1, n2))
    return sign * (np.arccos(np.dot(n1, n2) / np.linalg.norm(n1) / np.linalg.norm(n2)))

def rotation_matrix(axis, theta):
    """
    Return the rotation matrix associated with counterclockwise rotation about
    the given axis by theta radians.
    """
    axis = np.asarray(axis)
    axis = axis/math.sqrt(np.dot(axis, axis))
    a = math.cos(theta/2.0)
    b, c, d = -axis*math.sin(theta/2.0)
    aa, bb, cc, dd = a*a, b*b, c*c, d*d
    bc, ad, ac, ab, bd, cd = b*c, a*d, a*c, a*b, b*d, c*d
    return np.array([[aa+bb-cc-dd, 2*(bc+ad), 2*(bd-ac)],
                     [2*(bc-ad), aa+cc-bb-dd, 2*(cd+ab)],
                     [2*(bd+ac), 2*(cd-ab), aa+dd-bb-cc]])

# changed from x, y to [0], [1] to work with standard vector types
def ccw(A,B,C):
    return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])

# Return true if line segments AB and CD intersect
def intersect(A,B,C,D):
    return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)

def project_point_on_viepoint(origin, point):
    coo = geocentric_to_camera(PhotoScan.app.model_view.viewpoint.coo)
    center = geocentric_to_camera(PhotoScan.app.model_view.viewpoint.center)
    n = center - coo
    n = n / np.linalg.norm(n)
    # d = -n[0] * origin[0] - n[1] * origin[1] - n[2] * origin[2]
    projected = point - np.dot(point - origin, n) * n
    return projected

def to_local_plane(origin):
    coo = geocentric_to_camera(PhotoScan.app.model_view.viewpoint.coo)
    center = geocentric_to_camera(PhotoScan.app.model_view.viewpoint.center)
    n = center - coo
    normal = n / np.linalg.norm(n)
    loc0 = origin
    any_vector = origin + PhotoScan.Vector([0, 0, 1])
    locx = np.cross(normal, any_vector)
    locy = np.cross(normal, locx)

    return lambda p: (np.dot(p - loc0, locx), np.dot(p - loc0, locy))


def lines_dist(line1, line2):
    return np.cross(line1[1] - line1[0], line2[0] - line1[0]) / np.linalg.norm(line1[1] - line1[0])

def line_2d(p1, p2):
    A = (p1[1] - p2[1])
    B = (p2[0] - p1[0])
    C = (p1[0]*p2[1] - p2[0]*p1[1])
    return A, B, -C

def line2d_intersection(L1, L2):
    D  = L1[0] * L2[1] - L1[1] * L2[0]
    Dx = L1[2] * L2[1] - L1[1] * L2[2]
    Dy = L1[0] * L2[2] - L1[2] * L2[0]
    if D != 0:
        x = Dx / D
        y = Dy / D
        return x,y
    else:
        return False

def is_between(p1, p2, p3):
    if (p1[0] < p3[0] < p2[0]) or (p2[0] < p3[0] < p1[0]):
        return (p1[1] < p3[1] < p2[1]) or (p2[1] < p3[1] < p1[1])
    return False
