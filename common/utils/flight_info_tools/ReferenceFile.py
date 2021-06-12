#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

from __future__ import print_function, unicode_literals

import re
import sys
from datetime import datetime
from io import open
from xml.etree import ElementTree as ETree

DEFAULT_ENCODINGS = ('utf-8-sig', 'utf-8', 'cp1251')

if sys.version_info < (3, 0):
    def to_str(x): return x.encode(sys.stdout.encoding)
else:
    def to_str(x): return x


class CamReference(object):
    """
    Class for interpreting reference of camera
    """

    def __init__(self, name=None, y=None, x=None, alt=None, roll=None, pitch=None, yaw=None, error=None, mark=None):
        self.name = name
        self.x = x
        self.y = y
        self.alt = alt
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.sd_x = error
        self.sd_y = error
        self.sd_alt = error
        self.mark = mark

    @property
    def sd_plane(self):
        if self.sd_x is not None:
            sd_plane = (self.sd_x ** 2 + self.sd_y ** 2) ** 0.5
        else:
            sd_plane = None
        return sd_plane

    @property
    def sd_spatial(self):
        if self.sd_x is not None:
            sd_spatial = (self.sd_x ** 2 + self.sd_y ** 2 + self.sd_alt ** 2) ** 0.5
        else:
            sd_spatial = None
        return sd_spatial

    @property
    def has_location(self):
        result = all((
            self.x is not None,
            self.y is not None,
            self.alt is not None,
        ))
        return result

    @property
    def has_rotation(self):
        result = all((
            self.roll is not None,
            self.pitch is not None,
            self.yaw is not None,
        ))
        return result

    @sd_plane.setter
    def sd_plane(self, value):
        self.sd_x = value/(2**0.5)
        self.sd_y = value/(2**0.5)

    @sd_spatial.setter
    def sd_spatial(self, value):
        self.sd_x = value/(3**0.5)
        self.sd_y = value/(3**0.5)
        self.sd_alt = value/(3**0.5)

    def __repr__(self):
        lst = (self.name, self.x, self.y, self.alt)
        message = u'<Class "CamReference": [name: {}, East: {}, North: {}, Height: {}]>'.format(*lst)
        return to_str(message)


class AbstractReferenceFile(object):
    class ColumnsPosition(object):
        name = None
        x = None
        y = None
        alt = None
        roll = None
        pitch = None
        yaw = None
        sd_x = None
        sd_y = None
        sd_alt = None
        sd_spatial = None
        mark = None

        def __init__(self, positions=None):
            if positions:
                self.fill(positions)

        def fill(self, d):
            ids = set()
            attrs = dir(self)
            for k, v in d.items():
                if v is not None and v in ids:
                    raise ValueError(u'ID={} was found twice in columns position dict!'.format(v))
                if k not in attrs:
                    raise ValueError(u'Attribute="{}" was not found in class ColumnsPosition!'.format(k))
                setattr(self, k, v)
                ids.add(v)

        def all_columns(self, empty=False):
            attrs = filter(lambda a: not callable(getattr(self, a)) and not a.startswith('_'), dir(self))

            d = dict()
            for attr in attrs:
                val = getattr(self, attr)
                if not empty and val is None:
                    continue
                d[attr] = val
            return d

        def __repr__(self):
            items = sorted(self.all_columns().items(), key=lambda x: x[1])
            s = u' | '.join(u'{}: {}'.format(k, v) for k, v in items) or 'Empty'
            return u'<ColumnsPosition: {}>'.format(s)

    columns = ColumnsPosition()
    _header = None
    _cols = None
    _cam_list = None

    @classmethod
    def from_data(cls, cam_list, heading=None):
        if isinstance(heading, str):
            heading = heading.split(u'\n')
        elif heading is None:
            heading = []

        instance = cls()
        instance._header = cls._rstrip_strings(heading)
        instance._cam_list = list(cam_list)
        return instance

    @classmethod
    def from_file(cls, path, enc, columns, header_contains=None):
        instance = cls()

        instance.columns = instance.ColumnsPosition(columns)
        data = cls._safe_open_txt(path, enc)
        instance._header, data = instance._split_data(data)

        if header_contains and header_contains not in u''.join(instance._header):
            raise ValueError(u'The file header must contain "{}".'.format(header_contains))

        instance._parse_data(data)
        return instance

    @staticmethod
    def _rstrip_strings(lst):
        return [r.rstrip() for r in lst]

    @staticmethod
    def _split_data(data):
        i = 0
        # while data[i][0] == u'#':
        while data[i][0] == u'#' or data[i][1] == u'#':
            i += 1
        return data[:i], data[i:]

    @staticmethod
    def _safe_open_txt(path, enc='cp1251'):
        encodings = [enc] if enc else []
        encodings.extend(filter(lambda x: x not in encodings, DEFAULT_ENCODINGS))

        with open(path, u'rb') as f:
            data = f.read()

        for enc in encodings:
            try:
                data = AbstractReferenceFile._rstrip_strings(data.decode(enc).strip().split('\n'))
            except UnicodeDecodeError:
                print('''Can't decode file in "%s" encoding. Trying to use other...''' % enc)
            else:
                return data
        raise ValueError('Wrong encoding "{}"'.format(encodings[0]))

    @property
    def cam_list(self):
        return self._cam_list

    @property
    def header(self):
        return self._header

    @staticmethod
    def _parse_time_mark(string):
        string = re.sub(r'^(20\d\d)\D(\d\d)\D(\d\d) (\d+)\D(\d+)\D(\d+)[,.](\d+)',
                        r"\1.\2.\3 \4:\5:\6.\7",
                        string.strip())
        dt = datetime.strptime(string, r'%Y.%m.%d %H:%M:%S.%f')
        return dt

    def _parse_data(self, data):
        """
        Method for parsing reference file
        :return: list of CamReference
        """

        cam_ref_list = []
        self._cols = self.columns.all_columns()

        if not self._cols:
            raise ValueError('Column indexes are empty!')

        for row in data:
            lst = row.strip().split('\t')
            cam = self._parse_row_list(lst)
            cam_ref_list.append(cam)

        self._cam_list = cam_ref_list
        return cam_ref_list

    def _parse_row_list(self, lst):
        def fill_value(k, idx):
            if idx >= len(lst):
                return
            val = lst[idx]
            try:
                if k == u'mark':
                    val = self._parse_time_mark(val)
                elif k == u'name':
                    pass
                else:
                    val = float(val)
            except ValueError:
                pass
            else:
                setattr(cam, k, val)

        cam = CamReference()
        for col, i in self._cols.items():
            fill_value(col, i)

        if cam.x is None or cam.y is None or cam.alt is None:
            cam = CamReference(name=cam.name)

        return cam

    @staticmethod
    def _get_attrs_output_dict(cam, lines_format):
        d = dict()
        for attr in dir(cam):
            if u'{}'.format(attr) in lines_format:
                d[attr] = getattr(cam, attr)
        return d

    def dump_txt(self, path, lines_format='{name}\t{y}\t{x}\t{alt}', head_row=None):
        def format_row(attrs):
            try:
                return lines_format.format(**attrs)
            except TypeError:
                pass

            if u'name' in attrs:
                return attrs['name']
            else:
                return u''

        out_list = []
        out_list.extend(self._header)

        if head_row:
            out_list.append(head_row)
        else:
            out_list.append(u'# ' + lines_format.replace(u'{', u'').replace(u'}', u''))

        for i in self._cam_list:
            out_list.append(format_row(self._get_attrs_output_dict(i, lines_format)))

        out_list.append('')
        out_str = u'\n'.join(out_list)
        with open(path, u'wb') as f:
            f.write(out_str.encode('utf-8'))

    @staticmethod
    def _add_camera_to_tree(parent, cam):
        if cam.has_location:
            ref_attribs = {
                u'x': str(cam.x),
                u'y': str(cam.y),
                u'z': str(cam.alt),
                u'sypr': u'10',
                u'enabled': u'1',
            }
        else:
            return

        if cam.has_rotation:
            ref_attribs['roll'] = str(cam.roll)
            ref_attribs['yaw'] = str(cam.yaw)
            ref_attribs['pitch'] = str(cam.pitch)

        if cam.sd_alt:
            ref_attribs['sx'] = str(cam.sd_x)
            ref_attribs['sy'] = str(cam.sd_y)
            ref_attribs['sz'] = str(cam.sd_alt)
        elif cam.sd_x:
            ref_attribs['sxyz'] = str(cam.sd_plane)

        xml_cam = ETree.SubElement(parent, u'camera')
        xml_cam.attrib = {'label': cam.name}
        xml_ref = ETree.SubElement(xml_cam, u'reference')
        xml_ref.attrib = ref_attribs

    def dump_xml(self, path):
        xml_root = ETree.Element(u'reference')
        xml_root.attrib = {u'version': u'1.2.0'}
        xml_cameras = ETree.SubElement(xml_root, u'cameras')

        for cam in self._cam_list:
            self._add_camera_to_tree(xml_cameras, cam)

        xml_tree = ETree.ElementTree(xml_root)
        with open(path, 'wb') as f:
            xml_tree.write(f, encoding='utf-8', xml_declaration=True)

    def xy_list(self):
        """
        Method returns  all coordinates as (x, y) tuples
        :return: list of tuples
        """
        res = [(cam.x, cam.y) for cam in self._cam_list if cam.has_location]
        return res


class NavRefFile(AbstractReferenceFile):
    @staticmethod
    def get_columns_dict(header):
        if not header:
            raise ValueError('Empty header!')

        def safe_find(lst, val):
            try:
                idx = lst.index(val)
            except ValueError:
                idx = None
            return idx

        def find_several(lst, keys):
            vals = []
            for k in keys:
                idx = safe_find(lst, k)
                if idx is not None:
                    vals.append(idx)
            return vals

        d = {
            u'name': 0,
            u'x': 2,
            u'y': 1,
        }

        splitted = header[-1][2:].strip().split('\t')
        splitted = [s.strip() for s in splitted]
        alt_pos = find_several(splitted, ['altGPS', u'alt', u'altBaro'])
        d[u'alt'] = alt_pos[0] if alt_pos else 3
        d[u'mark'] = safe_find(splitted, u'time')
        d[u'roll'] = safe_find(splitted, u'roll')
        d[u'pitch'] = safe_find(splitted, u'pitch')
        d[u'yaw'] = safe_find(splitted, u'yaw')
        return d

    @classmethod
    def from_file(cls, path=None, enc=None, *args, **kwargs):
        instance = cls()
        instance.path = path
        instance.enc = enc

        data = cls._safe_open_txt(path, enc)
        instance._header, data = instance._split_data(data)

        columns = cls.get_columns_dict(instance._header)
        instance.columns = cls.ColumnsPosition(columns)

        instance._parse_data(data)
        return instance


class ReferenceCSVFile(AbstractReferenceFile):
    @classmethod
    def from_file(cls, path=None, *args, **kwargs):
        columns = {
            u'name': 0,
            u'x': 2,
            u'y': 1,
            u'alt': 3,
            u'roll': 4,
            u'pitch': 5,
            u'yaw': 6,
            u'sd_x': 8,
            u'sd_y': 9,
            u'sd_alt': 10,
        }

        instance = super(ReferenceCSVFile, cls).from_file(
            path=path, enc='utf8', columns=columns, header_contains='MagnetMerger'
        )

        return instance


class OldRefFile(AbstractReferenceFile):
    @classmethod
    def from_file(cls, path=None, *args, **kwargs):
        columns = {
           u'name': 0,
           u'x': 2,
           u'y': 1,
           u'alt': 3,
           u'roll': 4,
           u'pitch': 5,
           u'yaw': 6,
           u'sd_spatial': 7,
        }
        return super(OldRefFile, cls).from_file(path=path, enc='utf8', columns=columns)


class RefOnlyFile(AbstractReferenceFile):
    @classmethod
    def from_file(cls, path=None, *args, **kwargs):
        columns = {
            u'name': 0,
            u'x': 2,
            u'y': 1,
            u'alt': 3,
        }
        return super(RefOnlyFile, cls).from_file(path=path, enc='utf8', columns=columns)


class ReferenceXMLFile(AbstractReferenceFile):
    """
    Parser for Agisoft XML referencer
    """

    @classmethod
    def from_file(cls, path, *args, **kwargs):
        instance = cls()
        instance._header = []
        instance._cam_list = cls._parse_xml(path)
        return instance

    @staticmethod
    def _parse_camera(camera_elem):
        """
        Converts 'camera' ETree.Element to CameraRef instance
        :param camera_elem:
        :return:
        """
        reference_attribs = camera_elem.find(u'reference').attrib
        camera = CamReference()
        camera.name = camera_elem.attrib[u'label']

        try:
            camera.x = float(reference_attribs[u'x'])
            camera.y = float(reference_attribs[u'y'])
            camera.alt = float(reference_attribs[u'z'])
        except (KeyError, ValueError):
            return camera

        try:
            camera.roll = float(reference_attribs[u'roll'])
            camera.pitch = float(reference_attribs[u'pitch'])
            camera.yaw = float(reference_attribs[u'yaw'])
        except (KeyError, ValueError):
            camera.roll = None
            camera.pitch = None

        if u'sx' in reference_attribs:
            camera.sd_x = float(reference_attribs[u'sx'])
            camera.sd_y = float(reference_attribs[u'sy'])
            camera.sd_alt = float(reference_attribs[u'sz'])
        elif u'sxyz' in reference_attribs:
            camera.sd_spatial = float(reference_attribs[u'sxyz'])
        elif u'sxy' in reference_attribs:
            camera.sd_plane = float(reference_attribs[u'sxy'])
            camera.sd_alt = float(reference_attribs[u'sz'])

        return camera

    @staticmethod
    def _parse_xml(path):
        """
        Parses XML file
        :param path: file path
        :return: list of CameraRef
        """
        cameras = []
        tree = ETree.parse(path)
        cameras_elem = tree.getroot().find('cameras')
        for camera_elem in cameras_elem.iterfind('camera'):
            camera = ReferenceXMLFile._parse_camera(camera_elem)
            cameras.append(camera)
        return cameras


def open_unknown_reference_file(path):
    """
    Tries to open file as ReferenceCSVFile, then as OldRefFile
    :param path:
    :return: Instance of reference class (ReferenceCSVFile or OldRefFile)
    """
    try:
        f = ReferenceCSVFile.from_file(path)
    except ValueError:
        f = OldRefFile.from_file(path)
    return f


def _test():
    import os

    test_dir = os.path.join(os.path.dirname(__file__), 'test_data')
    if not os.path.isdir(test_dir):
        raise Exception('"test_data" directory does not exist!')
    os.chdir(test_dir)

    NavRefFile.from_file(r'Old_TNK_POLET_2_g101b11108_f002_photoScan.txt')
    NavRefFile.from_file(r'Current_Broken_2017_08_31_PUTI_c9_g201b20075_f001_photoScan.txt')
    NavRefFile.from_file(r'Current_2017_08_31_PUTI_c9_g201b20075_f001_photoScan.txt')
    NavRefFile.from_file(r'New_2018_10_15_PUTI_SonyRX1_g401b40140_f001_photoScan.txt')
    ReferenceCSVFile.from_file(r'GNSS_Magnet_2018_05_15_Naklon-Left_g201b20141_f016_GNSS.csv')
    ReferenceXMLFile.from_file(r'GNSS_Magnet_2018_05_15_Naklon-Left_g201b20141_f016_GNSS.xml')
    OldRefFile.from_file(r'GNSS_OLD_2017_07_16_2000_g201b20138_f083__GNSS.txt')
    RefOnlyFile.from_file(r'Old_TNK_POLET_2_g101b11108_f002_photoScan.txt')

    f = open_unknown_reference_file(r'Old_TNK_POLET_2_g101b11108_f002_photoScan.txt')
    c5 = f.cam_list[5]
    assert c5.roll is not None and c5.sd_alt is None

    f1 = open_unknown_reference_file(r'Reference_only_07_04_16_POZHARSKOE_g101b00085_f003_photoScan_GNSS.txt')
    assert isinstance(f1, OldRefFile)
    f2 = open_unknown_reference_file(r'GNSS_Magnet_2018_05_15_Naklon-Left_g201b20141_f016_GNSS.csv')
    assert isinstance(f2, ReferenceCSVFile)

    f1.dump_xml(r'out1.xml')
    f2.dump_xml(r'GNSS_Magnet_2018_05_15_Naklon-Left_g201b20141_f016_GNSS.xml')
    f1.dump_txt(r'out1')
    f2.dump_txt(r'out2')

    cyrillic = NavRefFile.from_file(r'Current_Кириллица_2017_08_31_PUTI_c9_g201b20075_f001_photoScan.txt')

    for c in cyrillic.cam_list:
        print(c, c.mark, c.sd_plane)
    print(f2.columns)
    print('\nTests passed')


if __name__ == '__main__':
    _test()
