"""Tools to parse flights data

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

import xml.etree.ElementTree as ETree
import re
import os
import datetime

try:
    from .pathbased_operations import get_files_by_rule, get_nav_files, is_kml_file
    from .ReferenceFile import NavRefFile
except (SystemError, ImportError):
    from pathbased_operations import get_files_by_rule, get_nav_files, is_kml_file
    from ReferenceFile import NavRefFile


class StandardizedInfo:
    class KmlTxtMismatch(ValueError):
        pass

    _vehicle = None
    _flight_number = None
    _elevation = None
    _in_track_overlap = None
    _cross_track_overlap = None
    _resolution = None
    _home_point = None
    _time_start = None
    _time_finish = None
    _total_images = None
    _total_telemetry = None
    _total_images_wt = None

    _kml_parsed = False
    _txt_parsed = False

    _VEHICLE_NAMES = ('Номер борта', 'Vehicle')
    _FLIGHT_NUMBER_NAMES = ('Номер полета', 'Flight Number')
    _DATE_NAMES = ('Дата', 'Date')
    _TIME_NAMES = ('Время', 'Time')
    _ELEVATION_NAMES = ('Высота', 'Elevation')
    _OVERLAPS_NAMES = ('Перекрытия', 'Overlaps')
    _RESOLUTION_NAMES = ('Разрешение', 'Resolution')

    def __init__(self, *, txt_path=None, kml_path=None, dir_path=None, raise_time_mismatch=True):
        if not any((txt_path, kml_path, dir_path)):
            raise ValueError('You must specify path!')

        self.txt_path = txt_path
        self.kml_path = kml_path
        self._raise_time_mismatch = raise_time_mismatch

        if not (txt_path and kml_path):
            dir_path = dir_path or os.path.dirname(txt_path or kml_path)
            self._fill_paths_from_dir(path=dir_path)

    @staticmethod
    def _get_first_kml(path):
        for p in get_files_by_rule(is_kml_file, path):
            return p

    @staticmethod
    def _get_first_txt(path):
        for p in get_nav_files(path):
            return p

    @staticmethod
    def _get_item_by_keys(d, keys):
        for k in keys:
            it = d.get(k)
            if it is not None:
                return it

    @staticmethod
    def resolve_vehicle(vehicle):
        """
        Converts vehicle number in different formats to standard 5-digit number.
        Examples: '29' --> 10029, '2022' --> 20022, '12058' --> 12058, '11026' --> 10026
        :param vehicle: string or int
        :return: int (5-digit number)
        """

        vehicle = int(vehicle)

        if 52000 > vehicle > 40000:
            return vehicle
        elif 30000 > vehicle > 20000:
            num = vehicle % 1000
            return 20000 + num
        elif 13000 > vehicle > 12000:
            return vehicle
        elif 15000 > vehicle > 10000:
            num = vehicle % 1000
            return 10000 + num
        elif vehicle > 5000000:
            return vehicle
        elif 5000 > vehicle > 1000:
            pref, num = divmod(vehicle, 1000)
            return pref*10000 + num
        elif 600 > vehicle >= 100:
            pref, num = divmod(vehicle, 100)
            return pref*10000 + num
        elif vehicle < 100:
            return 10000 + vehicle
        else:
            raise ValueError('Cannot resolve vehicle number: "{}"!'.format(vehicle))

    @staticmethod
    def _get_txt_datetime(time_interval):
        """
        Gets time of start and time of end of observing from time interval string (from txt file)
        :param time_interval: string
        :return: tuple of datetime object
        """

        splitted = time_interval.split(' ')

        main, tail = splitted[:5], splitted[5:]
        start_date, start_time, _, end_date, end_time = main

        start_s = start_date + start_time
        end_s = end_date + end_time

        if len(splitted) > 5:
            offset_s = ''.join([tail[-3], tail[-2], tail[-1][:2], tail[-1][3:]])
            start_s += offset_s
            end_s += offset_s

        templates = ('%Y.%m.%d%H:%M:%S%Z%z', '%d.%m.%Y%H:%M:%S%Z%z', '%d.%m.%Y%H:%M:%S')

        start_dt = None
        end_dt = None
        for template in templates:
            try:
                start_dt = datetime.datetime.strptime(start_s, template)
                end_dt = datetime.datetime.strptime(end_s, template)
            except ValueError:
                pass
            else:
                break
        return start_dt, end_dt

    def _get_kml_datetime(self, date_s, time_s):
        """
        Converts date and time strings from KML to datetime object with same time zone as in self.time_start (from TXT)
        :param date_s: string
        :param time_s: string
        :return: datetime object
        """

        dt = datetime.datetime.strptime(' '.join([date_s, time_s]), '%d.%m.%Y %H:%M:%S')
        dt = dt.replace(tzinfo=self.time_start.tzinfo)
        return dt

    def _fill_paths_from_dir(self, path):
        """
        Gets path of KML and TXT in dir
        :param path: directory path
        :return:
        """

        if not os.path.isdir(path):
            raise ValueError('Path: "{}" is not a directory!'.format(path))

        self.kml_path = self.kml_path or self._get_first_kml(path)
        self.txt_path = self.txt_path or self._get_first_txt(path)

    @staticmethod
    def _get_home_point(s):
        """
        Returns coordinates of home point if s else None
        :param s:
        :return: tuple (lat, lon, alt)
        """

        if not s:
            return
        s = s.replace(',', '.')
        coords = tuple(map(float, s.split('. ')))
        return coords

    @staticmethod
    def _get_overlaps(s):
        """
        Splits overlaps string (like "50.0 / 70.0") to two float (or if empty, two None)
        :param s:
        :return: tuple of cross-track and in-track overlaps
        """
        if not s:
            return None, None
        return tuple(map(float, s.split('/')))

    def _parse_txt(self):
        """
        Parses TXT file
        :return:
        """

        info_dict = from_txt(self.txt_path)
        self._time_start, self._time_finish = self._get_txt_datetime(info_dict['Временной интервал'])
        self._home_point = self._get_home_point(info_dict['Домашняя точка'])

        q_images = info_dict['Количество снимков']
        q_images_wt = info_dict['Количество снимков с координатами']
        q_telemetry = info_dict['Количество координат']

        self._total_images = int(q_images) if q_images else None
        self._total_images_wt = int(q_images_wt) if q_images_wt else None
        self._total_telemetry = int(q_telemetry) if q_telemetry else None

        self._txt_parsed = True

    def _parse_kml(self):
        """
        Parses KML file (if self.kml_path)
        :return:
        """

        self._kml_parsed = True

        if not self.kml_path:
            return
        try:
            info_dict = from_kml(self.kml_path)
        except ETree.ParseError:
            return

        date = self._get_item_by_keys(info_dict, self._DATE_NAMES)
        time = self._get_item_by_keys(info_dict, self._TIME_NAMES)
        kml_dt = self._get_kml_datetime(date, time)
        txt_dt = self.time_start

        if abs(kml_dt - txt_dt) > datetime.timedelta(minutes=1):
            msg = 'KML datetime does not match TXT datetime:\nTXT: "{}"\nKML: "{}"'.format(self.kml_path, self.txt_path)
            if self._raise_time_mismatch:
                raise self.KmlTxtMismatch(msg)
            else:
                print(msg)
                return

        vehicle = self._get_item_by_keys(info_dict, self._VEHICLE_NAMES)
        flight_number = self._get_item_by_keys(info_dict, self._FLIGHT_NUMBER_NAMES)
        elevation = self._get_item_by_keys(info_dict, self._ELEVATION_NAMES)
        overlaps = self._get_item_by_keys(info_dict, self._OVERLAPS_NAMES)
        resolution = self._get_item_by_keys(info_dict, self._RESOLUTION_NAMES)

        try:
            self._vehicle = self.resolve_vehicle(vehicle) if vehicle else None
        except ValueError:
            msg = 'Wow! Really interesting! Vehicle number in kml is "{}"!\nPath:"{}"'.format(vehicle, self.kml_path)
            raise ValueError(msg)

        self._flight_number = int(flight_number) if flight_number else None
        self._elevation = float(elevation) if elevation else None
        self._cross_track_overlap, self._in_track_overlap = self._get_overlaps(overlaps)
        self._resolution = float(resolution) if resolution else None

    def _from_parsed_txt_getter(self, attr):
        """
        Gets attribute by name, but if txt nav file is not parsed, parses it
        :param attr:
        :return: attribute value
        """
        if not self._txt_parsed:
            self._parse_txt()
        return getattr(self, attr)

    def _from_parsed_kml_getter(self, attr):
        """
        Gets attribute by name, but if txt nav file is not parsed, parses it
        :param attr:
        :return: attribute value
        """
        if not self._kml_parsed:
            self._parse_kml()
        return getattr(self, attr)

    @property
    def vehicle(self):
        return self._from_parsed_kml_getter('_vehicle')

    @property
    def flight_number(self):
        return self._from_parsed_kml_getter('_flight_number')

    @property
    def elevation(self):
        return self._from_parsed_kml_getter('_elevation')

    @property
    def cross_track_overlap(self):
        return self._from_parsed_kml_getter('_cross_track_overlap')

    @property
    def in_track_overlap(self):
        return self._from_parsed_kml_getter('_in_track_overlap')

    @property
    def time_start(self):
        return self._from_parsed_txt_getter('_time_start')

    @property
    def home_point(self):
        return self._from_parsed_txt_getter('_home_point')

    @property
    def resolution(self):
        return self._from_parsed_txt_getter('_resolution')

    @property
    def time_finish(self):
        return self._from_parsed_txt_getter('_time_finish')

    @property
    def total_images(self):
        return self._from_parsed_txt_getter('_total_images')

    @property
    def total_telemetry(self):
        return self._from_parsed_txt_getter('_total_telemetry')

    @property
    def total_images_wt(self):
        return self._from_parsed_txt_getter('_total_images_wt')


def from_kml(kml_path):
    tree = ETree.parse(kml_path)
    root = tree.getroot()
    info_dict = {}
    for child in root.findall('.//{http://www.opengis.net/kml/2.2}description'):
        description = ETree.fromstring(child.text)
        for row in description.findall('tr'):
            if row[0].text != 'Тип элемента':
                info_dict[row[0].text] = row[1].text
    return info_dict


def from_txt_header(header):
    date_pattern = r'((\d{4}\.\d{2}\.\d{2})|(\d{2}\.\d{2}\.\d{4}))'
    time_pattern = r'(\d{2}:\d{2}:\d{2})'
    timezone_pattern = r'( UTC [+-] \d{2}:\d{2})'
    time_interval_template = r'%s %s - %s %s%s?' % (
        date_pattern, time_pattern, date_pattern, time_pattern, timezone_pattern)
    time_interval = re.search(time_interval_template, header).group()

    latlon_template = r'-?\d{1,3}[,.]\d*'
    alt_template = r'-?\d{0,4}[,.]\d*'
    home_point_template = r'\(%s, %s, %s\)' % (latlon_template, latlon_template, alt_template)

    home_point_q = re.search(home_point_template, header)
    home_point = home_point_q.group()[1:-1] if home_point_q else None

    q_images_q = re.search(r'images: \d{1,4};', header)
    q_images = q_images_q.group()[8:-1] if q_images_q else None

    q_images_wt_q = re.search(r'images with telemetry: \d{1,4};', header)
    q_images_wt = q_images_wt_q.group()[23:-1] if q_images_wt_q else None

    q_telemetry_q = re.search(r'telemetry count: \d{1,4}', header)
    q_telemetry = q_telemetry_q.group()[17:] if q_telemetry_q else None

    info_dict = {
        'Домашняя точка': home_point,
        'Временной интервал': time_interval,
        'Количество снимков': q_images,
        'Количество снимков с координатами': q_images_wt,
        'Количество координат': q_telemetry
    }

    return info_dict


def from_txt(txt_path):
    reffile = NavRefFile.from_file(txt_path)
    return from_txt_header('\n'.join(reffile.header))
