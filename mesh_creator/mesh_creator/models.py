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

import os
import tempfile

import numpy as np
import triangle as tr

import Metashape

from common.cg.geometry import proj_mat, planes_angle
from common.utils.bridge import chunk_crs_to_camera, camera_coordinates_to_chunk_crs
from shapely.geometry.polygon import LinearRing


def triangulate(positions):
    """
    Generates faces using Delaunay.
    positions: list of Metashape vertices
    return: set of faces
    """
    faces = set()
    p1, p2, p3, p4 = positions

    proj = proj_mat(p1, p2, p3)
    projected_positions = [proj.mulp(position) for position in positions]
    vertices = [[proj_position[0], proj_position[1]] for proj_position in projected_positions]

    len_s = len(projected_positions)
    segments = [[i, i + 1] if i != len_s - 1 else [i, 0] for i in range(len_s)]

    A = {'vertices': vertices,
         'segments': segments}

    tri = tr.triangulate(A, 'p')
    for i in range(len(tri['triangles'])):
        try:
            f = tuple(positions[idx] for idx in tri['triangles'][i])
        except IndexError:
            continue
        faces.add(f)
        yield f


def r_vertices(vertices):
    if vertices:
        shapes_crs = Metashape.app.document.chunk.shapes.crs
        chunk_crs = Metashape.app.document.chunk.crs
        check = []
        raw_vertices = []
        for v in vertices:
            if [v.x, v.y, v.z] not in check:
                raw_vertices.append(v)
                check.append([v.x, v.y, v.z])
        vertices = [Metashape.CoordinateSystem.transform(v, shapes_crs, chunk_crs) for v in raw_vertices]
        return vertices
    return []


def r_vertices_in_shape_crs(pts):
    shapes_crs = Metashape.app.document.chunk.shapes.crs
    chunk_crs = Metashape.app.document.chunk.crs
    vertices = [Metashape.CoordinateSystem.transform(camera_coordinates_to_chunk_crs(v), chunk_crs, shapes_crs)
                for v in r_vertices(pts)]
    return vertices


def getBottomPoint(vertices):
    bottom = vertices[0]
    for v in vertices:
        if bottom.z > getIntersection(v).z:
            bottom = getIntersection(v)

    z = vertices[0].z - bottom.z
    return z


def getIntersection(vertice):
    chunk = Metashape.app.document.chunk
    v2 = vertice.copy()
    v2.z += -1
    T = chunk.transform.matrix
    pt1 = T.inv().mulp(chunk.crs.unproject(vertice))
    pt2 = T.inv().mulp(chunk.crs.unproject(v2))
    pp = chunk.dense_cloud.pickPoint(pt1, pt2)
    return chunk.crs.project(T.mulp(pp))


def lower(positions, distance):
    """
    Lowers positions.
    positions: list of Metashape vertices
    distance: float value on which positions must be lowered
    return: list of positions and its lower equivalents
    """
    pts = r_vertices(positions)
    lowerpts = [None] * len(pts)

    for i in range(len(pts)):
        lowerpts[i] = pts[i].copy()
        lowerpts[i].z += distance

    for i in range(len(pts)):
        pts[i] = chunk_crs_to_camera(pts[i])
        lowerpts[i] = chunk_crs_to_camera(lowerpts[i])
    return list(pts) + list(lowerpts)


def mesh(svertices, distance, type):
    """
    Generates mesh.
    return: faces generator
    """
    chunk = Metashape.app.document.chunk
    T = chunk.transform.matrix

    if len(svertices) > 2:
        if not LinearRing(np.array(list(svertices))).is_ccw:
            svertices = list(reversed(svertices))
    else:
        LSE = chunk.crs.localframe(T.mulp(svertices[0]))
        vp = LSE.mulp(Metashape.app.viewpoint.center)
        p1, p2 = list(svertices)
        if planes_angle(LSE.mulp(chunk.crs.unproject(p1)) - vp, LSE.mulp(chunk.crs.unproject(p2)) - vp) > 0:
            svertices = list(reversed(svertices))

    up = False
    if distance > 0:
        up = True

    pts = lower(svertices, distance)
    faces = []

    if up:
        positions = [pts[0], pts[len(pts)//2], pts[len(pts) - 1], pts[len(pts)//2 - 1]]
    else:
        positions = [pts[0], pts[len(pts)//2 - 1], pts[len(pts) - 1], pts[len(pts)//2]]
    faces.append(positions)

    for i in range(len(pts)//2 - 1):
        if up:
            positions = [pts[i], pts[i + 1], pts[len(pts)//2 + 1 + i],  pts[len(pts)//2 + i]]
        else:
            positions = [pts[i], pts[len(pts)//2 + i], pts[len(pts)//2 + 1 + i], pts[i + 1]]

        faces.append(positions)

    if type == Metashape.Shape.Type.Polyline:
        faces.pop(0)

    for pts in faces:
        yield from triangulate(pts)


def generate_obj_strings(faces):
    """
    Generates strings for OBJ file.
    faces: list of faces
    return: strings including vertices and string including faces
    """
    # This comment code must be uncomment when we solve a problem with remove texture and Metashape's fall
    # vertex_strings = []
    # face_strings = []
    # model = Metashape.app.document.chunk.model
    #
    # check = []
    # for face in faces:
    #     indexes = []
    #     for pos in face:
    #
    #         s = (pos.x, pos.y, pos.z)
    #         if s not in check:
    #             idx = len(vertex_strings) + len(model.vertices)
    #             vertex_strings.append(Metashape.Vector(s))
    #             check.append(s)
    #         else:
    #             idx = check.index(s) + len(model.vertices)
    #         indexes.append(idx)
    #
    #     face_strings.append(tuple(indexes))
    # return vertex_strings, face_strings

    vertex_strings = []
    face_strings = []

    model = Metashape.app.document.chunk.model
    if model:
        ps_vertices = (v.coord for v in model.vertices)
        ps_vertices = map(camera_coordinates_to_chunk_crs, ps_vertices)
        vertex_strings += ['v ' + ' '.join(map(str, v)) for v in ps_vertices]

        ps_faces = (f.vertices for f in model.faces)
        face_strings += ['f ' + ' '.join(map(lambda i: str(i + 1), f)) for f in ps_faces]

    for face in faces:
        indexes = []
        for pos in face:

            pt3d = camera_coordinates_to_chunk_crs(pos)
            s = "v " + str(pt3d.x) + " " + str(pt3d.y) + " " + str(pt3d.z)
            if s not in vertex_strings:
                vertex_strings.append(s)
                idx = len(vertex_strings)
            else:
                idx = vertex_strings.index(s) + 1
            indexes.append(idx)

        face_string = "f " + " ".join(map(str, indexes))
        face_strings.append(face_string)
    return vertex_strings, face_strings


def get_path_in_chunk(end=None, fn=None):
    """
    :param end: folder
    :param fn: file
    :return: full path to folder or file in chunk folder
    """
    chunk = Metashape.app.document.chunk
    d = os.path.splitext(Metashape.app.document.path)[0] + ".files"
    fileName = os.path.join(d, str(chunk.key))
    if not os.path.isdir(fileName):
        os.makedirs(fileName)
    if end is not None:
        fileName = os.path.join(fileName, end)
        if not os.path.isdir(fileName):
            os.makedirs(fileName)
    if fn is not None:
        fileName = os.path.join(fileName, fn)
    return fileName


def save_obj(faces):
    """
    Saves model file and importing to Metashape.
    faces: list of faces in inner(camera) crs
    """
    # This comment code must be uncomment when we solve a problem with remove texture and Metashape's fall
    # chunk = Metashape.app.document.chunk
    # model = chunk.model
    #
    # if not model:
    #     tmp_dir = tempfile.gettempdir()
    #     model_file = os.path.join(tmp_dir, 'model.obj')
    #     with open(model_file, 'a') as f:
    #         pass
    #     chunk.importModel(model_file)
    #     model = chunk.model
    #
    # vertex_strings, face_strings = generate_obj_strings(faces)
    # model.vertices.resize(len(model.vertices) + len(vertex_strings))
    # model.faces.resize(len(model.faces) + len(face_strings))
    #
    # for i in range(-1, -(len(vertex_strings)+1), -1):
    #     model.vertices[i].coord = vertex_strings[i]
    #
    # for i in range(-1, -(len(face_strings)+1), -1):
    #     model.faces[i].vertices = face_strings[i]
    #
    # chunk.decimateModel(len(model.faces))

    try:
        tmp_dir = tempfile.gettempdir()
        model_file = os.path.join(tmp_dir, "model.obj")
    except KeyError:
        model_file = get_path_in_chunk(fn="model.obj")

    vertex_strings, face_strings = generate_obj_strings(faces)

    if model_file:
        with open(model_file, 'w') as fn:
            for m in vertex_strings:
                fn.write(m + "\n")
            for m in face_strings:
                fn.write(m + "\n")

        crs = Metashape.app.document.chunk.crs
        import_model(model_file, crs)


def import_model(model_file, crs):
    """
    Imports model to Metashape.
    model_file: model file.
    crs: coordinate system in Metashape format.
    """
    try:
        Metashape.app.document.chunk.importModel(model_file, format=Metashape.ModelFormatOBJ, crs=crs)
    except AttributeError:
        Metashape.app.document.chunk.importModel(model_file, format="obj", crs=crs)
