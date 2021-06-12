"""Mesh creator for Agisoft Metashape

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

import Metashape
import numpy as np
import triangle
from scipy.spatial import ConvexHull, Delaunay

from common.utils.bridge import geocentric_to_camera, real_vertices, get_camera_coordinates_to_localframe
from common.cg.geometry import proj_mat, triangle_normal, angle_between, unit_vector
from .ui import show_error


class PointProcessorInterface:
    """
    You should implement process selected method. it builds model from markers or contours or whatever you like.
    Produces faces of created triangles
    """
    def process_selected(self):
        raise NotImplementedError


# need to completely redo this part in the future
class ConvexHullPointProcessor(PointProcessorInterface):
    """
    class builds model on markers or shapes.
    can be used to build triangles, planes or convex hulls
    """

    def __init__(self):
        self.max_face_size = None  # requires user input for maximum face square size

    def process_selected(self):
        faces = set()

        # markers = [m for m in Metashape.app.document.chunk.markers if m.selected and m.position]
        # positions = [m.position for m in markers]
        positions = []

        if Metashape.app.document.chunk.shapes:
            for s in Metashape.app.document.chunk.shapes:
                if not s.selected or s.type != Metashape.Shape.Type.Polygon:
                    continue
                positions += real_vertices(s)

        vp_center = np.array(geocentric_to_camera(Metashape.app.viewpoint.center))
        if len(positions) < 3:
            show_error("Model builder", "Select polygon(s) to make a hull")
        if len(positions) == 3:
            faces.add(tuple(positions))
        elif len(positions) == 4:
            p1, p2, p3, p4 = positions
            # project to plane
            proj = proj_mat(p1, p2, p3)
            projected_positions = [proj.mulp(position) for position in positions]
            projected_positions = [[pos.x, pos.y] for pos in projected_positions]
            # we run delaunay in 2d, but pick points from 3d
            t = Delaunay(projected_positions)
            for s in t.simplices:
                f = tuple(positions[idx] for idx in s)
                print('got face: ', f, 'its type is: ', type(f))
                faces.add(f)
        else:
            faces.update(process_selected_hull(positions))

        # # inserting overtriangulation
        # for face in faces:
        #     print('got face: ', face, 'its type is: ', type(face))
        #     face_size = get_face_size(face)
        #     if not self.max_face_size:
        #         divide_by = 0
        #     else:
        #         divide_by = face_size / self.max_face_size
        #     if divide_by > 1:
        #         print('splitting face with size: ', face_size)
        #         new_faces = face_split(face, divide_by)
        #         yield from (check_angle(face, vp_center) for face in new_faces)
        #     else:
        #         yield check_angle(face, vp_center)
        return faces

def process_selected_hull(positions, exclude=None):
    faces = set()
    if len(positions) < 5:
        return
    cv = ConvexHull(positions)
    facets = cv.simplices
    eq = cv.equations

    for e, face in zip(eq, facets):
        f = tuple(positions[idx] for idx in face)
        if is_exclude(face, exclude):
            continue
        norm = triangle_normal(f)
        if not np.allclose(norm, e[:3]):
            f = tuple(reversed(f))

        print('got face: ', face, 'its type is: ', type(face))

        faces.add(f)
    return faces

def is_exclude(face, exclude):
    if exclude is not None:
        for s in exclude:
            if set(face).issubset(s):
                return True
    return False

def check_angle(f, vp_center):
    """
    depending on current viewpoint flips face normal to make face facing to user
    :param f: face
    :param vp_center: viewpoint center
    :return: face
    """
    norm = triangle_normal(f)
    angle = np.abs(angle_between(norm, vp_center - np.mean([np.array(face) for face in f], axis=0)))
    return tuple(f) if angle < np.pi / 2 else tuple(reversed(f))


def get_face_size(face):
    pts = [get_camera_coordinates_to_localframe(face[0]).mulp(p) for p in face]
    return np.linalg.norm(np.cross(pts[1] - pts[0], pts[2] - pts[0])) / 2


def face_split(pts, divide_by):
    # get rotation matrix to place initial triangle on z=const plane
    v1 = unit_vector(pts[1] - pts[0])
    v2 = unit_vector(pts[2] - pts[0])

    alpha = angle_between(v1, v2)

    vectors = np.hstack((np.asmatrix(v1).T, np.asmatrix(v2).T, np.asmatrix(np.cross(v1, v2)).T))

    result = np.hstack((np.asmatrix([1.0, 0.0, 0.0]).T, np.asmatrix([np.cos(alpha), np.sin(alpha), 0]).T,
                        np.asmatrix([0.0, 0.0, 1.0]).T))

    rotation_matrix = np.dot(result, np.linalg.inv(vectors))

    # rotate triangle
    pts = np.dot(np.asarray(pts), rotation_matrix.T)
    z_plane = pts[0, 2]
    pts = pts[:, :2]

    # evaluate face size constraint in rotated crs
    face_size = np.linalg.norm(np.cross(pts[2] - pts[0], pts[1] - pts[0])) / 2
    max_face_size = face_size / divide_by

    # options to obtain quality mesh('q')(angles > 20) with constrained cell size('a' + 'size'); each cell is delaunay conforming('D')
    opts = 'q' + 'a' + str(max_face_size) + 'D'

    refined = triangle.triangulate(dict(vertices=pts), opts)
    vertices = refined['vertices']
    triangles = refined['triangles']
    faces = vertices[triangles]

    # add z_plane to all triangles
    faces = [np.hstack((face, np.asmatrix([1, 1, 1]).T * z_plane)) for face in faces]

    # rotate all triangles back to camera crs
    faces = [np.array((np.dot(np.linalg.inv(rotation_matrix), face.T)).T) for face in faces]

    # convert to Metashape.Vector
    faces = [[Metashape.Vector(f) for f in face] for face in faces]

    return faces
