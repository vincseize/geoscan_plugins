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

import gettext
import Metashape

from shapely.geometry import LinearRing, Polygon, LineString

from .startapp.initialization import InstallLogging
from .ui import show_error, show_info
from common.utils.bridge import chunk_crs_to_geocentric, get_geocentric_to_localframe, camera_coordinates_to_chunk_crs


def create_shape(vertices: list, chunk: Metashape.Chunk = None, label: str = "", group: Metashape.ShapeGroup = None,
                 z_coord: float = None, shape_type: str = 'Polygon', boundary_type: str = 'NoBoundary'):
    """
    Create shape
    @param vertices: List of shape vertices of dimensions [n][2] or [n][3]. if shape has dimension [n][2]
        the z coord can be defined as 'z_coord' param
    @param chunk: destination chunk (optional). is doesn't set, use current chunk
    @param label: shape label (optional)
    @param group: shape group in Metashape (optional)
    @param z_coord: use it if shape doesn't have third coord (optional)
    @param shape_type: must be one of "Point", "Polygon" (default) or "Polyline"
    @param boundary_type: must be one of "InnerBoundary", "NoBoundary" (default) or OuterBoundary
    """
    if chunk is None:
        chunk = Metashape.app.document.chunk  # current chunk if chunk not specify

    shp = chunk.shapes.addShape()
    shp.label = label

    # check is redundant if we are passing correct shape vertices anyway

    if len(vertices[0]) < 3:
        if z_coord is not None:
            shp.has_z = True
            shp.vertices = [[pt[0], pt[1], z_coord] for pt in vertices]
        else:
            shp.has_z = False
            shp.vertices = [[pt[0], pt[1]] for pt in vertices]
    else:
        shp.has_z = True
        shp.vertices = [[pt[0], pt[1], pt[2]] for pt in vertices]

    if group is not None:
        shp.group = group

    shp.type = Metashape.Shape.Type.values[shape_type]
    shp.boundary_type = Metashape.Shape.BoundaryType.values[boundary_type]

    return shp


def create_parapet(shape, m_in):
    """
    Create offset shape
    """
    logger = InstallLogging()

    try:
        assert isinstance(shape, Metashape.Shape)  # check that we've got the shape
    except AssertionError: # we can safely assume that we're passing shape object, or just change to f(shape: ps.Shape)
        logger.exception("The shape is not instance Metashape.Shape. Object is {}".format(shape))
        show_info(_('Cannot define shape'), _('Please, sent to us .log file located in:\n{}').format(logger.fn))
        return

    chunk = Metashape.app.document.chunk

    shapes_crs = chunk.shapes.crs
    chunk_crs = chunk.crs # process case when shape crs and chunk crs are different, also check that crs obj is not None
    if shape.vertices:
        # if not shapes_crs:
        #     shapes_crs = chunk_crs
        # svertices = [Metashape.CoordinateSystem.transform(v, shapes_crs, chunk_crs) for v in shape.vertices]
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
        logger.error("Cannot define shapes vertices. {}".format(shape.type))
        show_info(_('Cannot define shapes\'s vertices'), _('Please, sent to us .log file located in:\n{}').format(logger.fn))
        return

    if LinearRing(svertices).is_ccw:
        svertices = list(reversed(svertices))

    # we can simplify cs conversion: (shape | chunk) -> geocentric -> (inner | local)
    #                                 inner -> geocentric -> local
    #                                 inner may be metric too, needs checking out

    local = []
    geo = chunk_crs_to_geocentric(svertices[0])
    localframe = get_geocentric_to_localframe(geo)

    # can be replaced with: local = [frame.mulp(crs.unproject(p)) for p in vertices]
    for i in range(len(svertices)):
        geo = chunk_crs_to_geocentric(svertices[i])
        loc = localframe.mulp(geo)
        local.append([loc.x, loc.y])
    shape_type = 'Polygon'
    offset_shape_coords = []
    if shape.type == Metashape.Shape.Polygon:
        polygon = Polygon(local)
        try:
            offset_polygon = polygon.buffer(m_in, join_style=2).exterior
            offset_shape_coords = list(offset_polygon.coords)[:-1]
        except AttributeError:
            logger.exception('Cannot create offset Polygon')
            show_error(_('Error'), _('The buffer distance is more than distance between polygon sides.'))
            return

    elif shape.type == Metashape.Shape.Polyline:
        side = 'right' if m_in <= 0 else 'left'
        m_in = abs(m_in)
        poly = LineString(local)
        offset_line = poly.parallel_offset(m_in, side=side, join_style=2) # if offset_line.is_valid
        try:
            for i in list(offset_line.coords)[::-1]: # also can be replaced with switching 'side'
                offset_shape_coords.append(i) # coords = list(offset_line.coords)
        except NotImplementedError:
            logger.exception('Cannot create correct offset Polyline(intersection of the sides)')
            show_error(_('Error'), _('Incorrect topology.\n'
                                     'Please remove intersecting vertices.'))
            return

        shape_type = 'Polyline'

    else:
        logger.error('Cannot define type of shape. {}'.format(shape.type))
        show_info(_('Cannot define shapes\'s vertices'), _('Please, sent to us .log file located in:\n{}').format(logger.fn))
        return

    if len(offset_shape_coords) < 2:
        show_info(_('Error'), _("Cannot create inner buffer polygon.\n"
                                "The buffer distance is more than distance between polygon sides."))
        return

    local_offset_shape = []
    # vertices = (ps.Vector(p) for p in coords) # could be done when setting shapely objects with 3-coords vectors
    for i, v in enumerate(svertices):
        try:
            local_offset_shape.append(Metashape.Vector([offset_shape_coords[i][0], offset_shape_coords[i][1], v.z]))
            # use ps alias instead of Metashape, could use ps import from initialization.py
        except IndexError:
            continue
    shape_vertices = []
    # to_geo = frame.inv()
    # vertices = [crs.project(to_geo.mulp(p)) for p in vertices]
    for v in local_offset_shape:
        geo = localframe.inv().mulp(v)
        chunk_ver = chunk.crs.project(geo)
        shape_vertices.append(Metashape.CoordinateSystem.transform(chunk_ver, chunk_crs, shapes_crs))

    create_shape(vertices=shape_vertices, shape_type=shape_type)
