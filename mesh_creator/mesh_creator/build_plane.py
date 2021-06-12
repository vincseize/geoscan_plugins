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

from shapely.geometry import LinearRing

from common.utils.bridge import camera_coordinates_to_chunk_crs, chunk_crs_to_geocentric, get_geocentric_to_localframe, \
    chunk_crs_to_camera
from .models import save_obj
from .startapp.initialization import InstallLogging
from .build_roof import triangulate
from .ui import move_to_ui_state, show_info
from .PointProcessor import PointProcessorInterface


class ModelBuilder:
    """
    operations to work with faces.
    model building in pointprocessor
    """
    fast_points_widget = None
    point_processor = None

    def __init__(self, point_processor: PointProcessorInterface):
        """
        :param point_processor:
        """
        self.point_processor = point_processor  # DI

    def process_selected(self):
        try:
            faces = list(self.point_processor.process_selected())
            print('number of newly generated faces: ', len(faces))
            save_obj(faces)
        except:
            import traceback
            traceback.print_exc()


def reload_model():
    transitional = ["wireframe", "каркас"]
    target = ["solid", "сплошной"]
    move_to_ui_state(transitional, .1)
    move_to_ui_state(target)


def import_model(model_file, crs):
    try:
        Metashape.app.document.chunk.importModel(model_file, format=Metashape.ModelFormatOBJ, projection=crs)
    except AttributeError:
        Metashape.app.document.chunk.importModel(model_file, format="obj", projection=crs)


def plane(shape):

    logger = InstallLogging()

    try:
        assert isinstance(shape, Metashape.Shape)  # check that we've got the shape
    except AssertionError:
        logger.exception("The shape is not instance Metashape.Shape. Object is {}".format(shape))
        show_info(_('Cannot define shape'), _('Please, sent to us .log file located in:\n{}').format(logger.fn))
        return

    chunk = Metashape.app.document.chunk
    faces = set()

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

    if LinearRing(svertices).is_ccw:
        svertices = list(reversed(svertices))

    svertices_camera = [chunk_crs_to_camera(v) for v in svertices]

    local = []
    geo = chunk_crs_to_geocentric(svertices[0])
    localframe = get_geocentric_to_localframe(geo)

    for i in range(len(svertices)):
        geo = chunk_crs_to_geocentric(svertices[i])
        loc = localframe.mulp(geo)
        local.append([loc.x, loc.y])

    tri = triangulate(local)
    for t in tri['triangles']:
        f = tuple(svertices_camera[i] for i in t)
        faces.add(f)
    save_obj(faces)


def plane_between(shapes):
    pass