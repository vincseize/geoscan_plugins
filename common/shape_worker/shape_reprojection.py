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

from math import radians, cos, sin, asin, sqrt
import Metashape
try:
    import pyproj
    from pyproj.aoi import AreaOfInterest
    from pyproj.database import query_utm_crs_info
except ImportError:
    pass
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from shapely.ops import transform
from osgeo import osr


class ShapeGeometry:
    def __init__(self, shape: Metashape.Shape, crs: str):
        self.shape = shape
        self.crs = crs

    @property
    def utm_crs(self):
        """
        Finding UTM zone by marker coordinates and creating UTM CRS definition in proj4 format.
        :return:
        """
        avg_vertice = self.get_average_vertice()
        north = True if avg_vertice.y >= 0 else False
        lon = avg_vertice.x
        zone_number = int((lon + 180) // 6 + 1) if lon != 180 else 60

        if north:
            utm_crs = '+proj=utm +zone={} +datum=WGS84 +units=m +no_defs'.format(zone_number)
        else:
            utm_crs = '+proj=utm +zone={} +south +datum=WGS84 +units=m +no_defs'.format(zone_number)
        return utm_crs

    def add_buffer(self, buffer_value, buffer_cap_style=1):
        """
        Add buffer to self.shape: Metashape.Shape
        :param buffer_value: Value in meters.
        :param buffer_cap_style: The styles of caps are specified by integer values: 1 (round), 2 (flat), 3 (square).
        :return:
        """
        if '+units=m' in self.crs:
            shapely_obj = self.convert_to_shapely_geometry(self.shape)
            shapely_obj = shapely_obj.buffer(buffer_value, cap_style=buffer_cap_style)
            self.convert_to_metashape_geometry(shapely_obj)

        elif '+proj=latlong' or '+proj=longlat' in self.crs:
            source_crs, target_crs = osr.SpatialReference(), osr.SpatialReference()
            source_crs.ImportFromProj4(self.crs)
            target_crs.ImportFromProj4(self.utm_crs)

            ms_source_crs, ms_target_crs = Metashape.CoordinateSystem(), Metashape.CoordinateSystem()
            ms_source_crs.init(source_crs.ExportToWkt())
            ms_target_crs.init(target_crs.ExportToWkt())

            shape = reproject_shape(self.shape, ms_source_crs, ms_target_crs)

            shapely_obj = ShapeGeometry.convert_to_shapely_geometry(shape)
            shapely_obj = shapely_obj.buffer(buffer_value, cap_style=buffer_cap_style)
            self.convert_to_metashape_geometry(shapely_obj)

            self.shape = reproject_shape(self.shape, ms_target_crs, ms_source_crs)
        else:
            raise ValueError('Unknown chunk CRS')

    @classmethod
    def convert_to_shapely_geometry(cls, metashape_obj):
        if metashape_obj.type == Metashape.Shape.Type.Point:
            return Point([(v.x, v.y) for v in metashape_obj.vertices])

        elif metashape_obj.type == Metashape.Shape.Type.Polyline:
            return LineString([(v.x, v.y) for v in metashape_obj.vertices])

        elif metashape_obj.type == Metashape.Shape.Type.Polygon:
            return Polygon([(v.x, v.y) for v in metashape_obj.vertices])

    def convert_to_metashape_geometry(self, shapely_obj):
        points = list()
        average_z = sum([v.z for v in self.shape.vertices]) / len(self.shape.vertices)
        for point in list(shapely_obj.exterior.coords):
            points.append(Metashape.Vector([point[0], point[1], average_z]))
        self.shape.vertices = points

    def get_average_vertice(self):
        x = sum([v.x for v in self.shape.vertices]) / len(self.shape.vertices)
        y = sum([v.y for v in self.shape.vertices]) / len(self.shape.vertices)
        z = sum([v.z for v in self.shape.vertices]) / len(self.shape.vertices)
        return Metashape.Vector([x, y, z])


class ShapelyGeometry:
    def __init__(self, shape: Polygon, crs: str):


        self.shape = shape
        self.crs = pyproj.CRS.from_user_input(crs)
        self.utm_crs = self.init_utm_crs()

    def init_utm_crs(self):
        """
        Finding UTM zone for self.shape.
        :return:
        """
        wgs84 = pyproj.CRS.from_epsg(4326)
        minx, miny, maxx, maxy = self.shape.bounds
        crs_to_wgs84 = pyproj.Transformer.from_crs(self.crs, wgs84, always_xy=True)
        wgs84_minx, wgs84_miny = crs_to_wgs84.transform(minx, miny)
        wgs84_maxx, wgs84_maxy = crs_to_wgs84.transform(maxx, maxy)

        utm_crs_list = query_utm_crs_info(
            datum_name="WGS 84",
            area_of_interest=AreaOfInterest(
                west_lon_degree=wgs84_minx,
                south_lat_degree=wgs84_miny,
                east_lon_degree=wgs84_maxx,
                north_lat_degree=wgs84_maxy,
            ),
        )
        return pyproj.CRS.from_epsg(utm_crs_list[0].code)

    def add_buffer(self, buffer_value, buffer_cap_style=1):
        """
        Add buffer to self.shape: Metashape.Shape
        :param buffer_value: Value in meters.
        :param buffer_cap_style: The styles of caps are specified by integer values: 1 (round), 2 (flat), 3 (square).
        :return:
        """
        if self.crs.is_projected:
            self.shape = self.shape.buffer(buffer_value, cap_style=buffer_cap_style)
        else:
            utm_shape = reproject_shapely_geometry(self.shape, self.crs, self.utm_crs)
            utm_shape_buffered = utm_shape.buffer(buffer_value, cap_style=buffer_cap_style)
            self.shape = reproject_shapely_geometry(utm_shape_buffered, self.utm_crs, self.crs)


def reproject_shapely_geometry(shapely_geometry: (Point, LineString, Polygon, MultiPolygon),
                               source_crs: (pyproj.CRS, str),
                               target_crs: (pyproj.CRS, str)):

    if isinstance(source_crs, str):
        source_crs = pyproj.CRS.from_user_input(source_crs)
    if isinstance(source_crs, str):
        target_crs = pyproj.CRS.from_user_input(target_crs)
    project = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True).transform

    return transform(project, shapely_geometry)


def reproject_shape(shape: Metashape.Shape,
                    source_crs: Metashape.CoordinateSystem,
                    target_crs: Metashape.CoordinateSystem):

    if isinstance(shape, Metashape.Shape):
        if shape.type == Metashape.Shape.Type.Point:
            shape = reproject_point(shape, source_crs, target_crs)
        elif shape.type == Metashape.Shape.Type.Polyline:
            shape = reproject_line(shape, source_crs, target_crs)
        elif shape.type == Metashape.Shape.Type.Polygon:
            shape = reproject_polygon(shape, source_crs, target_crs)
        else:
            raise NotImplementedError('Unknown type of Metashape.Shape object')
    else:
        if isinstance(shape, Point):
            reprojected_point = Metashape.CoordinateSystem.transform(list(shape.coords), source_crs, target_crs)
            shape = Point(reprojected_point.vertices)
        elif isinstance(shape, LineString):
            reprojected_points = list()
            for point in shape.coords:
                reprojected_point = Metashape.CoordinateSystem.transform(point, source_crs, target_crs)
                reprojected_points.append(reprojected_point)
            shape = LineString(reprojected_points)
        elif isinstance(shape, Polygon):
            reprojected_points = list()
            for point in shape.exterior.coords:
                reprojected_point = Metashape.CoordinateSystem.transform(point, source_crs, target_crs)
                reprojected_points.append(reprojected_point)
            shape = Polygon(reprojected_points)
        else:
            raise NotImplementedError('Unknown type of shapely.geometry object: {}'.format(shape.type))

    return shape


def reproject_point(shape: Metashape.Shape,
                    source_crs: Metashape.CoordinateSystem,
                    target_crs: Metashape.CoordinateSystem):
    if shape.type == Metashape.Shape.Type.Point:
        transform_point = Metashape.CoordinateSystem.transform(shape.vertices[0], source_crs, target_crs)
        shape.vertices = transform_point
        return shape
    else:
        raise TypeError('Type of shape is {}, not Metashape.Shape.Type.Point'.format(shape.type))


def reproject_coordinates(coords: list,
                          source_crs: Metashape.CoordinateSystem,
                          target_crs: Metashape.CoordinateSystem):
    return Metashape.CoordinateSystem.transform(coords, source_crs, target_crs)


def reproject_line(shape: Metashape.Shape,
                   source_crs: Metashape.CoordinateSystem,
                   target_crs: Metashape.CoordinateSystem):
    if shape.type == Metashape.Shape.Type.Polyline:
        vertices = shape.vertices
        transform_vertices = list()
        for vertice in vertices:
            transform_vertices.append(Metashape.CoordinateSystem.transform(vertice, source_crs, target_crs))
        shape.vertices = transform_vertices
        return shape
    else:
        raise TypeError('Type of shape is {}, not Metashape.Shape.Type.Polyline'.format(shape.type))


def reproject_polygon(shape: Metashape.Shape,
                      source_crs: Metashape.CoordinateSystem,
                      target_crs: Metashape.CoordinateSystem):
    if shape.type == Metashape.Shape.Type.Polygon:
        vertices = shape.vertices
        transform_vertices = list()
        for vertice in vertices:
            transform_vertices.append(Metashape.CoordinateSystem.transform(vertice, source_crs, target_crs))
        shape.vertices = transform_vertices
        return shape
    else:
        raise TypeError('Type of shape is {}, not Metashape.Shape.Type.Polygon'.format(shape.type))


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r
