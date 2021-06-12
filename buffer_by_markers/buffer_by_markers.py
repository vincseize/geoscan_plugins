"""Create buffer zone plugin for Agisoft Metashape

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
import os
import random
import re
import numpy as np
from PySide2 import QtWidgets
from osgeo import osr
from scipy.spatial import Delaunay
from shapely.geometry import mapping, Point, MultiPoint, LineString, Polygon, MultiPolygon, MultiLineString
import shapely.wkt

import Metashape
from shapely.ops import cascaded_union, triangulate, polygonize

from common.loggers.email_logger import log_method_by_crash_reporter
from common.utils.ui import load_ui_widget
from common.shape_worker import shape_worker as sw
from common.shape_worker.shape_reprojection import reproject_shape


class LinearBuffer:

    NAME = "Create buffer zone"
    VERSION = "1.0.1"

    def __init__(self, parent=None):
        self.ui = load_ui_widget(
            os.path.join(os.path.dirname(__file__), "buffer_by_markers_gui.ui"),
            parent=parent,
        )

        self.ui.LinearRadioButton.clicked.connect(self.fill_list)
        self.ui.OuterRadioButton.clicked.connect(self.fill_list)

        self.ui.CreateButton.clicked.connect(self.create_buffer)
        self.fill_list()
        self.ui.CapStyleComboBox.addItems(['Round', 'Flat', 'Square'])

    @property
    def cap_style(self):
        if self.ui.CapStyleComboBox.currentText() == 'Round':
            return 1
        elif self.ui.CapStyleComboBox.currentText() == 'Flat':
            return 2
        elif self.ui.CapStyleComboBox.currentText() == 'Square':
            return 3
        else:
            raise AssertionError

    def fill_list(self):
        if self.ui.LinearRadioButton.isChecked():
            self.get_markers()
        elif self.ui.OuterRadioButton.isChecked():
            self.get_shapesgroups()

    def get_markers(self):
        """
        Get all names of markers and show them in GUI.
        :return:
        """
        self.ui.listWidget.clear()
        self.markers = {}
        chunk = Metashape.app.document.chunk
        markers = chunk.markers
        if markers:
            for marker in markers:
                if marker.label != '':
                    self.ui.listWidget.addItem(marker.label)
                    self.markers.update({marker.label: marker.reference.location})

    def get_shapesgroups(self):
        """
        Get all names of shapegroups and show them in GUI.
        :return:
        """
        self.ui.listWidget.clear()
        self.shapegroups = {}
        chunk = Metashape.app.document.chunk
        for i, group in enumerate(chunk.shapes.groups):
            name = "{}:{}".format(i, group.label)
            self.shapegroups[name] = group.key
            self.ui.listWidget.addItem(name)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def create_buffer(self):
        group = Metashape.app.document.chunk.shapes.addGroup()
        group.label = 'buffer_zone'

        if self.ui.LinearRadioButton.isChecked():
            buffered_polygon = self.create_buffer_by_markers(buffer_distance=self.ui.BufferSpinBox.value(),
                                                             cap_style=self.cap_style)
        elif self.ui.OuterRadioButton.isChecked():
            buffered_polygon = self.create_buffer_by_shapegroups(buffer_distance=self.ui.BufferSpinBox.value(),
                                                                 cap_style=self.cap_style)
        else:
            raise SystemError

        if isinstance(buffered_polygon, Polygon):
            sw.create_shape(vertices=list(buffered_polygon.exterior.coords), label='buffer', group=group)
        elif isinstance(buffered_polygon, MultiPolygon):
            for poly in buffered_polygon:
                sw.create_shape(vertices=list(poly.exterior.coords), label='buffer', group=group)
        else:
            raise TypeError("Couldn't create shape with type: {}".format(type(buffered_polygon)))

    def create_buffer_by_markers(self, buffer_distance, cap_style):
        """
        :param buffer_distance: int. Distance in meters
        :param cap_style: int. Cap style for shapely.geometry.buffer() {1: round, 2: flat, 3: square}
        :return: shapely.geometry
        """
        chunk = Metashape.app.document.chunk
        selected_indexes = self.ui.listWidget.selectedIndexes()
        if not selected_indexes:
            Metashape.app.messageBox("Select markers to continue")
            return
        points = [self.markers[index.data()] for index in selected_indexes]

        line = LineString([(p[0], p[1], p[2]) for p in points])
        reproject = self.get_reprojection_func(chunk=chunk, geometry=line, is_marker=True)
        buffered_line_in_meters = reproject(line, to_meters=True).buffer(distance=buffer_distance, cap_style=cap_style)
        return reproject_shape(reproject(buffered_line_in_meters, to_degrees=True),
                               source_crs=chunk.marker_crs if chunk.marker_crs else chunk.crs,
                               target_crs=chunk.shapes.crs)

    def create_buffer_by_shapegroups(self, buffer_distance, cap_style):
        """
        :param buffer_distance: int. Distance in meters
        :param cap_style: int. Cap style for shapely.geometry.buffer() {1: round, 2: flat, 3: square}
        :return: shapely.geometry
        """
        chunk = Metashape.app.document.chunk
        selected_indexes = self.ui.listWidget.selectedIndexes()
        if not selected_indexes:
            Metashape.app.messageBox("Select shapegroups to continue")
            return
        selected_shapegroup_keys = {self.shapegroups[index.data()] for index in selected_indexes}

        selected_points, selected_lines, selected_polygons, random_point = list(), list(), list(), None
        for shape in chunk.shapes:
            if shape.group.key in selected_shapegroup_keys:
                if shape.type == Metashape.Shape.Type.Point:
                    selected_points.append(Point(*shape.vertices))
                elif shape.type == Metashape.Shape.Type.Polyline:
                    selected_lines.append(LineString(shape.vertices))
                elif shape.type == Metashape.Shape.Type.Polygon:
                    selected_polygons.append(Polygon(shape.vertices))
                else:
                    raise NotImplementedError

                if not random_point:
                    random_point = Point(shape.vertices[0])

        reproject = self.get_reprojection_func(chunk=chunk, geometry=random_point, is_marker=False)
        buffered_points = [reproject(x, to_meters=True).buffer(distance=buffer_distance, cap_style=cap_style)
                           for x in selected_points]
        buffered_lines = [reproject(x, to_meters=True).buffer(distance=buffer_distance, cap_style=cap_style)
                          for x in selected_lines]
        buffered_polygons = [reproject(x, to_meters=True).buffer(distance=buffer_distance, cap_style=cap_style)
                             for x in selected_polygons]
        union = cascaded_union(buffered_points + buffered_lines + buffered_polygons).simplify(0.05)
        if isinstance(union, Polygon):
            return reproject(union, to_degrees=True)
        elif isinstance(union, MultiPolygon):
            return MultiPolygon([reproject(poly, to_degrees=True) for poly in union])
        else:
            raise TypeError

    def __create_buffer_by_shapegroups(self, buffer_distance, cap_style):
        """
        :param buffer_distance: int. Distance in meters
        :param cap_style: int. Cap style for shapely.geometry.buffer() {1: round, 2: flat, 3: square}
        :return: shapely.geometry
        """
        chunk = Metashape.app.document.chunk
        selected_indexes = self.ui.listWidget.selectedIndexes()
        if not selected_indexes:
            Metashape.app.messageBox("Select shapegroups to continue")
            return
        selected_shapegroup_keys = {self.shapegroups[index.data()] for index in selected_indexes}
        selected_shapes = [shape for shape in chunk.shapes if shape.group.key in selected_shapegroup_keys]
        points = list()
        for shape in selected_shapes:
            points.extend([Point(v.x, v.y) for v in shape.vertices])

        # concave_hull = create_concave_hull(points, alpha=100)
        geometry = MultiPoint(points).buffer(0)
        reproject = self.get_reprojection_func(chunk=chunk, geometry=geometry, point=list(geometry.exterior.coords)[0],
                                               is_marker=False)
        concave_hull_in_meters = reproject(geometry, to_meters=True)
        buffered_shape = concave_hull_in_meters.buffer(distance=buffer_distance, cap_style=cap_style)
        return reproject(buffered_shape, to_degrees=True)

    def get_reprojection_func(self, chunk, geometry, is_marker: bool, point=None):
        """If crs is latlong return reprojection func, else - return empty func without reporjection"""
        if is_marker and chunk.marker_crs is not None:
            crs = chunk.marker_crs
        elif is_marker and chunk.marker_crs is None:
            crs = chunk.crs
        elif not is_marker:
            crs = chunk.shapes.crs
        else:
            raise SystemError

        if re.search(r"\+units=m", crs.proj4):
            def no_reproject(geometry: shapely.geometry, **kwargs):
                if is_marker:
                    return geometry

            return no_reproject

        elif re.search(r"(?:\+proj=latlong|\+proj=longlat)", crs.proj4):
            source_crs = crs
            target_crs = Metashape.CoordinateSystem()
            if point:
                random_point = point
            else:
                try:
                    random_point = random.choice(geometry.coords)
                except NotImplementedError:
                    try:
                        random_point = random.choice(geometry.exterior.coords)
                    except AttributeError:
                        random_point = random.choice(list(geometry)[0].exterior.coords)

            utm_crs = self.get_utm_crs(lon=random_point[0], lat=random_point[1])
            osr_crs = osr.SpatialReference()
            osr_crs.ImportFromProj4(utm_crs)
            target_crs.init(osr_crs.ExportToWkt())

            def reproject_latlong(geometry: shapely.geometry, **kwargs):
                """
                param: to_meters: bool. True: from source_crs to target_crs (in meters),
                param: to_degrees: bool. True: from target_crs to source_crs (in degrees).
                """

                if 'to_meters' in kwargs and kwargs['to_meters'] is True:
                    return reproject_shape(geometry, source_crs=source_crs, target_crs=target_crs)
                elif 'to_degrees' in kwargs and kwargs['to_degrees'] is True:
                    return reproject_shape(geometry, source_crs=target_crs, target_crs=source_crs)
                else:
                    raise AttributeError

            return reproject_latlong

        else:
            raise SystemError("Unknown shapes crs: {}".format(chunk.shapes.crs.proj4))

    def get_utm_crs(self, lon, lat):
        """
        Finding UTM zone by marker coordinates and creating UTM CRS definition in proj4 format.
        :return:
        """
        north = True if lat >= 0 else False
        zone_number = int((lon + 180) // 6 + 1) if lon != 180 else 60

        if north:
            utm_crs = '+proj=utm +zone={} +datum=WGS84 +units=m +no_defs'.format(zone_number)
        else:
            utm_crs = '+proj=utm +zone={} +south +datum=WGS84 +units=m +no_defs'.format(zone_number)
        return utm_crs

    def log_values(self):
        d = {
            "By markers": self.ui.LinearRadioButton.isChecked(),
            "By selected shapes": self.ui.OuterRadioButton.isChecked(),
            "Cap style": self.cap_style,
            "Buffer distance(m)": self.ui.BufferSpinBox.value(),
            "Selected indices in Tab": self.ui.listWidget.selectedIndexes(),
        }
        return d


def create_concave_hull(points, alpha):
    """
    source: https://gist.github.com/dwyerk/10561690#gistcomment-2819818
    Compute the alpha shape (concave hull) of a set
    of points.
    @param points: Iterable container of points.
    @param alpha: alpha value to influence the
        gooeyness of the border. Smaller numbers
        don't fall inward as much as larger numbers.
        Too large, and you lose everything!
    """
    if len(points) < 4:
        # When you have a triangle, there is no sense
        # in computing an alpha shape.
        return MultiPoint(list(points)).convex_hull
    coords = np.array([point.coords[0] for point in points])
    tri = Delaunay(coords)
    triangles = coords[tri.vertices]
    a = ((triangles[:, 0, 0] - triangles[:, 1, 0]) ** 2 + (triangles[:, 0, 1] - triangles[:, 1, 1]) ** 2) ** 0.5
    b = ((triangles[:, 1, 0] - triangles[:, 2, 0]) ** 2 + (triangles[:, 1, 1] - triangles[:, 2, 1]) ** 2) ** 0.5
    c = ((triangles[:, 2, 0] - triangles[:, 0, 0]) ** 2 + (triangles[:, 2, 1] - triangles[:, 0, 1]) ** 2) ** 0.5
    s = (a + b + c) / 2.0
    areas = (s * (s - a) * (s - b) * (s - c)) ** 0.5
    circums = a * b * c / (4.0 * areas)
    filtered = triangles[circums < (1.0 / alpha)]
    edge1 = filtered[:, (0, 1)]
    edge2 = filtered[:, (1, 2)]
    edge3 = filtered[:, (2, 0)]
    edge_points = np.unique(np.concatenate((edge1, edge2, edge3)), axis=0).tolist()
    m = MultiLineString(edge_points)
    triangles = list(polygonize(m))
    return cascaded_union(triangles)


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()
    dialog = LinearBuffer(parent)
    dialog.ui.show()
    result = dialog.ui.exec_()
    if result:
        pass


if __name__ == "__main__":
    main()
