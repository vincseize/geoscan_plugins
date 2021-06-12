"""Magnet Merger

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

import xml.etree.ElementTree as ET
import re
from datetime import datetime


class Point:
    """
    Holder for point with degrees coordinates
    """

    class StdDev:
        """
        Holder for standard deviation of point
        """
        easting = None
        northing = None
        up = None

        def __str__(self):
            return 'StdDev: easting={:.3f}, northing={:.3f}, up={:.3f}'.format(self.easting, self.northing, self.up)

        def __repr__(self):
            return '<StDev instance: ({})>'.format(str(self))

    name = None
    time_mark = None
    code = None
    easting = None
    northing = None
    height = None

    xy_repr_accuracy = 9
    easting_attrib = 'Longitude'
    northing_attrib = 'Latitude'

    def __init__(self):
        self.stddev = self.StdDev()

    def __repr__(self):
        template = '<Point instance: "{{}}" (easting={{:.{}f}}, northing={{:.{}f}}, height={{:.3f}}, ' \
                   'time_mark={{}})>'.format(self.xy_repr_accuracy, self.xy_repr_accuracy)
        s = template.format(
            self.name,
            self.easting,
            self.northing,
            self.height,
            self.time_mark,
            self.stddev
        )
        return s


class ProjectedPoint(Point):
    """
    Represent point in projection in meters. For example MSK.
    """
    xy_repr_accuracy = 3
    easting_attrib = 'Easting'
    northing_attrib = 'Northing'


class TopconXMLFile:
    """
    Holds parsed Topcon XML file. Accepts only degrees with decimal degrees (dd.dd..)
    """
    def __init__(self, path):
        self.point_class = None
        self.points = self.__parse_file(path)

    @staticmethod
    def __get_time(name_str):
        """
        Function parses *name_str* and returns Point instance
        :param name_str:
        :return name, timemark: str, datetime
        """
        pattern = re.compile(r'\d\d-\d\d-\d\d\d\d \d\d:\d\d:\d\d\.\d+')
        match = re.search(pattern, name_str)
        date_str = match[0][:-3].replace(',', '.')
        timemark = datetime.strptime(date_str, r'%d-%m-%Y %H:%M:%S.%f')
        return timemark

    def __parse_point(self, point_elem):
        """
        Function parses *point* and returns Point instance
        :param point_elem: ElementTree
        :return: Point instance
        """
        point = self.point_class()
        # If coordinates or standard deviation values don't exist, we will get AttributeError
        try:
            point.easting = float((point_elem.find(self.point_class.easting_attrib)).text)
            point.northing = float((point_elem.find(self.point_class.northing_attrib)).text)

            point.height = float(point_elem.find('OrthoHeight').text)
            point.code = point_elem.find('Code').text if point_elem.find('Code') is not None else None
            if point.code is None:
                return

            point.time_mark = self.__get_time(point_elem.find('PointNumber').text)

            stdev_elem = point_elem.find('StdDev')
            point.stddev.easting = float(stdev_elem.find('Easting').text)
            point.stddev.northing = float(stdev_elem.find('Northing').text)
            point.stddev.up = float(stdev_elem.find('Up').text)
        except AttributeError:
            return
        else:
            return point

    def __parse_file(self, path):
        """
        Function parses file in Topcon XML format by given path
        :param path: pathlike
        :return:
        """

        tree = ET.parse(path)
        root = tree.getroot()

        projection_defined = root.find('Project').find('Projection')
        if projection_defined is not None:
            self.point_class = ProjectedPoint
        else:
            self.point_class = Point

        points = list()
        for elem in root.iterfind('Point'):
            point = self.__parse_point(elem)
            if not point or point.code != 'USER':
                continue
            points.append(point)

        points.sort(key=lambda x: x.time_mark)
        return points


if __name__ == '__main__':
    pass
