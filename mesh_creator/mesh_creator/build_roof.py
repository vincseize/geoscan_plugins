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
import triangle as tr
import gettext

from shapely.geometry import LinearRing, Polygon, LineString, Point

from .startapp.initialization import InstallLogging
from .ui import show_error, show_info
from .models import save_obj
from common.cg.geometry import proj_mat
from common.utils.bridge import chunk_crs_to_camera, chunk_crs_to_geocentric, get_geocentric_to_localframe, \
    camera_coordinates_to_chunk_crs

logger = InstallLogging(__name__)


def triangulate_vertical(positions):

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
    return faces


def triangulate(local, offset_svertices=None, stype=None):
    """
    Generates faces using Delaunay.
    positions: list of PhotoScan vertices
    return: set of faces
    """
    s = [[coord[0], coord[1]] for coord in local]

    if stype == Metashape.Shape.Polyline:
        if not Polygon(local + offset_svertices).is_ring:
            offset_svertices = list(reversed(offset_svertices))

        local += offset_svertices
        s = [[coord[0], coord[1]] for coord in local]
        offset_svertices = None
    len_s = len(s)
    segments = [[i, i + 1] if i != len_s - 1 else [i, 0] for i in range(len_s)]

    A = {'vertices': s,
         'segments': segments}

    tri = tr.triangulate(A)

    if offset_svertices:
        offset_s = [[coord[0], coord[1]] for coord in offset_svertices]
        len_offset_s = len(offset_s)
        segments += [[i, i + 1] if i != len_s + len_offset_s - 1 else [i, len_s] for i in range(len_s, len_s + len_offset_s)]
        hole_sq = [offset_s[0], offset_s[1], offset_s[-1]]
        hole = LineString(hole_sq).centroid

        A = {'vertices': s + offset_s,
             'segments': segments,
             'holes': [[hole.x, hole.y]]}

        tri = tr.triangulate(A, 'p')

    return tri


def mesh_for_roof(shape, m_in, m_low):
    """
    Generates mesh.
    return: faces generator
    """
    chunk = Metashape.app.document.chunk

    try:
        assert isinstance(shape, Metashape.Shape)  # check that we've got the shape
    except AssertionError:
        logger.exception("The shape is not instance Metashape.Shape. Object is {}".format(shape))
        show_info(_('Cannot define shape'), _('Please, sent to us .log file located in:\n{}').format(logger.fn))
        return

    if shape.vertices:
        shapes_crs = chunk.shapes.crs
        chunk_crs = chunk.crs
        if not shapes_crs:
            shapes_crs = chunk_crs
        svertices = [Metashape.CoordinateSystem.transform(shape.vertices[i], shapes_crs, chunk_crs)
                     for i in range(len(shape.vertices) - 1)]
    elif shape.vertex_ids:
        try:
            svertices = [camera_coordinates_to_chunk_crs(next(m for m in Metashape.app.document.chunk.markers
                                                              if m.key == key).position) for key in shape.vertex_ids]
        except TypeError:
            logger.exception("Some vertices(attached markers) doesn't have position")
            show_info(_('Cannot define shape'), _('Please, check all shape\'s vertices,\nsome vertices are not show.'))
            return
    else:
        logger.error("Cannot define shape\'s vertices. {}".format(shape.type))
        show_info(_('Cannot define shape\'s vertices'), _('Please, sent to us .log file located in:\n{}').format(logger.fn))
        return

    if len(svertices) < 3:
        show_error(_('Error'), _('Shape must have 3 or more vertices.'))
        return

    if LinearRing(svertices).is_ccw:
        svertices = list(reversed(svertices))

    # code is present in the build_parapet.py; could be rewrote and reused by placing same functions into geometry module

    local = []
    geo = chunk_crs_to_geocentric(svertices[0])
    localframe = get_geocentric_to_localframe(geo)

    for i in range(len(svertices)):
        geo = chunk_crs_to_geocentric(svertices[i])
        loc = localframe.mulp(geo)
        local.append([loc.x, loc.y])

    offset_shape = []
    if shape.type == Metashape.Shape.Polygon:
        polygon = Polygon(local)
        try:
            offset_polygon = polygon.buffer(m_in, join_style=2).exterior
            offset_shape = list(offset_polygon.coords)[:-1]
        except AttributeError:
            logger.exception('Cannot create offset Polygon')
            show_error(_('Error'), _('The buffer distance is more than distance between polygon sides.'))
            return

    elif shape.type == Metashape.Shape.Polyline:
        side = 'right' if m_in <= 0 else 'left'
        m_in = abs(m_in)
        poly = LineString(local)
        offset_line = poly.parallel_offset(m_in, side=side, join_style=2)
        try:
            for i in list(offset_line.coords)[::-1]:
                offset_shape.append(i)
        except NotImplementedError:
            logger.exception('Cannot create correct offset Polyline(intersection of the sides)')
            show_error(_('Error'), _('Incorrect topology.\n'
                                     'Please remove intersecting vertices.'))
            return

        # This method finds new boundary points for the offset shape. This is done to draw a cut along the wall.
        result_line = LineString([local[0], local[-1]])
        line1 = LineString([offset_shape[1], offset_shape[0]])
        line2 = LineString([offset_shape[-2], offset_shape[-1]])

        V = Metashape.Vector
        if result_line.intersects(line1):
            first_point = result_line.intersection(line1)
            offset_shape[0] = [p for p in first_point.coords[0]]
            line2 = LineString([offset_shape[-2], V(offset_shape[-2]) + 3*(V(offset_shape[-1]) - V(offset_shape[-2]))])
            second_point = result_line.intersection(line2)
            try:
                offset_shape[-1] = [p for p in second_point.coords[0]]
            except NotImplementedError:
                logger.exception('Cannot create cut along the wall between last vertices')

        elif result_line.intersects(line2):
            first_point = result_line.intersection(line2)
            offset_shape[-1] = [p for p in first_point.coords[0]]
            line1 = LineString([offset_shape[1], V(offset_shape[1]) + 3*(V(offset_shape[0]) - V(offset_shape[1]))])
            second_point = result_line.intersection(line1)
            try:
                offset_shape[0] = [p for p in second_point.coords[0]]
            except NotImplementedError:
                logger.exception('Cannot create cut along the wall between last vertices')

        else:
            line1 = LineString([offset_shape[1], V(offset_shape[1]) + 3*(V(offset_shape[0]) - V(offset_shape[1]))])
            line2 = LineString([offset_shape[-2], V(offset_shape[-2]) + 3*(V(offset_shape[-1]) - V(offset_shape[-2]))])
            try:
                first_point = result_line.intersection(line1)
                second_point = result_line.intersection(line2)
                offset_shape[0] = [p for p in first_point.coords[0]]
                offset_shape[-1] = [p for p in second_point.coords[0]]
            except NotImplementedError:
                logger.exception('Cannot create cut along the wall between last vertices')

    else:
        logger.error('Cannot define type of shape. {}'.format(shape.type))
        show_info(_('Cannot define shapes\'s vertices'), _('Please, sent to us .log file located in:\n{}').format(logger.fn))
        return

    if len(offset_shape) < 2:
        show_info(_('Error'), _("Cannot create inner buffer polygon.\n"
                                "The buffer distance is more than distance between polygon sides."))
        return

    shape_vertices = []

    for i, v in enumerate(svertices):
        try:
            vec = Metashape.Vector([offset_shape[i][0], offset_shape[i][1], v.z])
            geo = localframe.inv().mulp(vec)
            chunk_ver = chunk.crs.project(geo)
            shape_vertices.append(chunk_ver)
        except IndexError:
            continue

    # from mesh_creator.build_parapet import create_shape
    # create_shape(vertices=shape_vertices, shape_type='Polyline')

    low_shape = []
    for v in shape_vertices:
        low_shape.append([v.x, v.y, v.z + m_low])

    # create_shape(vertices=low_shape, shape_type='Polyline')

    second_sh = shape_vertices
    third_sh = low_shape

    first = [None] * len(svertices)
    second = []
    third = []

    faces = []

    for i in range(len(svertices)):
        first[i] = chunk_crs_to_camera(svertices[i])
    for i in range(len(shape_vertices)):
        second.append(chunk_crs_to_camera(second_sh[i]))
        third.append(chunk_crs_to_camera(third_sh[i]))

    pts_vertical = second + third
    if shape.type == Metashape.Shape.Polygon:
        positions = [pts_vertical[0], pts_vertical[len(second) - 1], pts_vertical[len(second) * 2 - 1], pts_vertical[len(second)]]
        faces.append(positions)

    for i in range(len(second) - 1):
        positions = [pts_vertical[i], pts_vertical[len(second) + i], pts_vertical[len(second) + 1 + i], pts_vertical[i + 1]]
        faces.append(positions)

    list_faces = []
    for pts in faces:
        list_faces.extend(triangulate_vertical(pts))

    if shape.type == Metashape.Shape.Polyline and not Polygon(local + offset_shape).is_ring:
        second = list(reversed(second))

    tri = triangulate(local, offset_shape, shape.type)
    up = first + second
    for i in range(len(tri['triangles'])):
        try:
            f = tuple(up[idx] for idx in tri['triangles'][i])
        except IndexError:
            continue
        list_faces.append(f)

    tri_low = triangulate(offset_shape)
    for i in range(len(tri_low['triangles'])):
        try:
            f = tuple(third[idx] for idx in tri_low['triangles'][i])
        except IndexError:
            continue
        list_faces.append(f)

    return list_faces


def mesh_for_gable_roof(shape):    # todo: continue to develop

    chunk = Metashape.app.document.chunk
    V = Metashape.Vector

    try:
        assert isinstance(shape, Metashape.Shape)  # check that we've got the shape
    except AssertionError:
        logger.exception("The shape is not instance Metashape.Shape. Object is {}".format(shape))
        show_info(_('Cannot define shape'), _('Please, sent to us .log file in the path:\n{}').format(logger.fn))
        return

    if shape.vertices:
        shapes_crs = chunk.shapes.crs
        chunk_crs = chunk.crs
        if not shapes_crs:
            shapes_crs = chunk_crs
        svertices = [Metashape.CoordinateSystem.transform(v, shapes_crs, chunk_crs) for v in shape.vertices]
    elif shape.vertex_ids:
        try:
            svertices = [camera_coordinates_to_chunk_crs(next(m for m in Metashape.app.document.chunk.markers
                                                         if m.key == key).position) for key in shape.vertex_ids]
        except TypeError:
            logger.exception("Some vertices(attached markers) doesn't have position")
            show_info(_('Cannot define shape'), _('Please, check all shape\'s vertices,\nsome vertices are not show.'))
            return
    else:
        logger.error("Cannot define shape\'s vertices. {}".format(shape.type))
        show_info(_('Cannot define shape\'s vertices'), _('Please, sent to us .log file located in:\n{}').format(logger.fn))
        return

    z_low = min([v.z for v in svertices])

    # segment_points = [i for i, v in enumerate(svertices) if 66 <= v.z <= 68]
    segment_points = [i for i, v in enumerate(svertices) if z_low <= v.z <= z_low + 1.5]
    len_s = len(segment_points)
    segments = [[segment_points[i], segment_points[i + 1]] if i != len_s - 1 else [segment_points[i], 0] for i in range(len_s)]
    svertices_camera = [chunk_crs_to_camera(v) for v in svertices]

    geo = chunk_crs_to_geocentric(svertices[0])
    localframe = get_geocentric_to_localframe(geo)
    local = []
    local_to_cpp = []
    for i in range(len(svertices)):
        geo = chunk_crs_to_geocentric(svertices[i])
        loc = localframe.mulp(geo)
        local.append([loc.x, loc.y])
        local_to_cpp.append([round(loc.x, 4), round(loc.y, 4), round(loc.z, 4)])

    poly = Polygon([local[i] for i in segment_points])

    for i in range(len(svertices)):
        if i not in segment_points:
            point = Point(local[i])
            if point.distance(poly) != 0:
                pol_ext = LinearRing(poly.exterior.coords)
                d = pol_ext.project(point)
                p = pol_ext.interpolate(d)
                point_in = Point(V([point.x, point.y]) + 2 * (V([p.x, p.y]) - V([point.x, point.y])))
                local[i] = [point_in.x, point_in.y]

    faces = set()

    s = [[coords[0], coords[1]] for coords in local]

    # segments = [[i, i + 1] if i != len_s - 1 else [i, 0] for i in range(len_s)]

    A = {'vertices': s,
         'segments': segments}
    vertices = svertices_camera
    tri = tr.triangulate(A, 'p')
    for i in range(len(tri['triangles'])):
        try:
            f = tuple(vertices[idx] for idx in tri['triangles'][i])
        except IndexError:
            continue
        faces.add(f)
    save_obj(faces)


def mesh_for_horizontal_tube():   # todo: transfer function to new file with same things
    import math
    import numpy as np
    from shapely.geometry import LinearRing
    from mesh_creator.build_parapet import create_shape

    chunk = Metashape.app.document.chunk
    try:
        markers = [m for m in chunk.markers if m.selected]
        geo = chunk.crs.unproject(markers[0].reference.location)
    except IndexError:
        print('no markers')
    else:

        localframe = chunk.crs.localframe(geo)

        markers_geo = [chunk.crs.unproject(m.reference.location) for m in markers]
        markers_local = [localframe.mulp(m) for m in markers_geo]
        tube_radius = 1
        circle_points = 32
        list_faces = []

        for i in range(len(markers_local) - 1):
            points_camera = []
            for k in range(2):
                n = markers_local[i+1] - markers_local[i] if k == 0 else markers_local[i] - markers_local[i + 1]
                if n.x <= min(n.y, n.z):
                    i1 = np.cross(n, Metashape.Vector([1, 0, 0]))
                elif n.y <= min(n.x, n.z):
                    i1 = np.cross(n, Metashape.Vector([0, 1, 0]))
                else:
                    i1 = np.cross(n, Metashape.Vector([0, 0, 1]))

                j1 = np.cross(n, i1)

                i1 = Metashape.Vector(i1).normalized()
                j1 = Metashape.Vector(j1).normalized()

                points_raw = []
                for j in range(circle_points):
                    points_raw.append(markers_local[i+k] +
                                      (tube_radius * math.cos(j * math.pi * 2 / circle_points) * i1) / i1.norm() +
                                      (tube_radius * math.sin(j * math.pi * 2 / circle_points) * j1) / j1.norm())

                if LinearRing(points_raw).is_ccw:
                    points_raw = list(reversed(points_raw))

                height = -1000
                start_index = 0
                for num, v in enumerate(points_raw):
                    if v.z >= height:
                        height = v.z
                        start_index = num

                points = [points_raw[i] for i in range(start_index, len(points_raw))]

                for p in range(0, start_index):
                    points.append(points_raw[p])

                ver = []
                for p in points:
                    geo = localframe.inv().mulp(p)
                    points_camera.append(Metashape.app.document.chunk.transform.matrix.inv().mulp(geo))
                    ver.append(chunk.crs.project(geo))

                ver_s = []
                for v in ver:
                    ver_s.append([v.x, v.y, v.z])
                create_shape(vertices=ver_s, shape_type='Polygon')

            faces = []

            pts = points_camera
            # positions = [pts[0], pts[len(pts) // 2], pts[len(pts) - 1], pts[len(pts) // 2 - 1]]  # change normal
            positions = [pts[0], pts[len(pts) // 2 - 1], pts[len(pts) - 1], pts[len(pts) // 2]]

            faces.append(positions)

            for p in range(len(pts) // 2 - 1):
                # positions = [pts[p], pts[p + 1], pts[len(pts) // 2 + 1 + p], pts[len(pts) // 2 + p]] # change normal
                positions = [pts[p], pts[len(pts) // 2 + p], pts[len(pts) // 2 + 1 + p], pts[p + 1]]
                faces.append(positions)

            faces.append(positions)

            for pts in faces:
                list_faces.extend(triangulate_vertical(pts))

        save_obj(list_faces)


def mesh_for_vertical_tube(up_rad, down_rad, height):   # todo: transfer function to new file with same things
    import math
    import numpy as np
    from shapely.geometry import LinearRing
    from mesh_creator.build_parapet import create_shape

    chunk = Metashape.app.document.chunk
    try:
        markers = [m for m in chunk.markers if m.selected]
        geo = chunk.crs.unproject(markers[0].reference.location)
    except IndexError:
        print('no markers')
    else:

        localframe = chunk.crs.localframe(geo)

        markers_geo = [chunk.crs.unproject(m.reference.location) for m in markers]
        markers_local = [localframe.mulp(m) for m in markers_geo]
        tube_up_radius = up_rad
        tube_down_radius = down_rad
        tube_height = height
        circle_points = 32
        list_faces = []
        m = markers_local[0]

        points_camera = []
        for k in range(2):
            tube_radius = tube_up_radius if k == 0 else tube_down_radius
            n = markers_local[0] - Metashape.Vector([m.x, m.y, m.z - tube_height])
            if n.x <= min(n.y, n.z):
                i1 = np.cross(n, Metashape.Vector([1, 0, 0]))
            elif n.y <= min(n.x, n.z):
                i1 = np.cross(n, Metashape.Vector([0, 1, 0]))
            else:
                i1 = np.cross(n, Metashape.Vector([0, 0, 1]))

            j1 = np.cross(n, i1)

            i1 = Metashape.Vector(i1).normalized()
            j1 = Metashape.Vector(j1).normalized()

            points_raw = []
            for j in range(circle_points):
                if k == 0:
                    points_raw.append(m + (tube_radius * math.cos(j * math.pi * 2 / circle_points) * i1) / i1.norm() +
                                          (tube_radius * math.sin(j * math.pi * 2 / circle_points) * j1) / j1.norm())
                else:
                    points_raw.append(Metashape.Vector([m.x, m.y, m.z - tube_height]) +
                                      (tube_radius * math.cos(j * math.pi * 2 / circle_points) * i1) / i1.norm() +
                                      (tube_radius * math.sin(j * math.pi * 2 / circle_points) * j1) / j1.norm())

            if LinearRing(points_raw).is_ccw:
                points_raw = list(reversed(points_raw))

            x = 0
            start_index = 0
            for num, v in enumerate(points_raw):
                if v.x >= x:
                    x = v.x
                    start_index = num

            points = [points_raw[i] for i in range(start_index, len(points_raw))]

            for p in range(0, start_index):
                points.append(points_raw[p])

            ver = []
            for p in points:
                geo = localframe.inv().mulp(p)
                points_camera.append(Metashape.app.document.chunk.transform.matrix.inv().mulp(geo))
                ver.append(chunk.crs.project(geo))

            ver_s = []
            for v in ver:
                ver_s.append([v.x, v.y, v.z])
            create_shape(vertices=ver_s, shape_type='Polygon')

            faces = []

            pts = points_camera
            positions = [pts[0], pts[len(pts) // 2], pts[len(pts) - 1], pts[len(pts) // 2 - 1]]
            # positions = [pts[0], pts[len(pts) // 2 - 1], pts[len(pts) - 1], pts[len(pts) // 2]]

            faces.append(positions)

            for p in range(len(pts) // 2 - 1):
                positions = [pts[p], pts[p + 1], pts[len(pts) // 2 + 1 + p], pts[len(pts) // 2 + p]]
                # positions = [pts[p], pts[len(pts) // 2 + p], pts[len(pts) // 2 + 1 + p], pts[p + 1]]
                faces.append(positions)

            faces.append(positions)

            for pts in faces:
                list_faces.extend(triangulate_vertical(pts))

        save_obj(list_faces)
