"""Script to add custom CRSs to Magnet tools

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

import csv
import getpass
import os
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom


class Projection:
    def __init__(self):
        self.name = None
        self.datum = None
        self.proj_type = None
        self.units = None
        self.lon_0 = None
        self.lat_0 = None
        self.x_0 = None
        self.y_0 = None
        self.scale = None

    @classmethod
    def name_decode(cls, name):
        new_name = re.sub(r'\-', '', name)
        new_name = re.sub('\s', '_', new_name)
        translit_new_name = transliterate(new_name)
        return 'CustomCRS-' + translit_new_name

    @property
    def magnet_name(self):
        return self.name_decode(self.name)

    @property
    def magnet_lon_0(self):
        if self.lon_0:
            return self.string_number(self.lon_0)
        else:
            raise ValueError('Projection {} do not have lon_0'.format(self.name))

    @property
    def magnet_lat_0(self):
        if self.lon_0:
            return self.string_number(self.lat_0)
        else:
            raise ValueError('Projection {} do not have lat_0'.format(self.name))

    @property
    def magnet_units(self):
        if self.units == 'm':
            return 'Meters'
        else:
            print('unknown units', self.units)
            return self.units

    @property
    def magnet_datum(self):
        if self.datum == 'krass':
            return 'SK42'
        elif self.datum == 'bessel':
            return 'BESS'
        else:
            print('unknown datum or ellipsoid', self.datum)
            return self.datum

    @staticmethod
    def string_number(data):
        value = float(data)
        degree = int(value)
        minutes = int((value - degree) * 60)
        seconds = round(((value - degree) * 60 - minutes) * 60, 5)
        if seconds == 60:
            return str(degree).zfill(2) + str(minutes + 1).zfill(2) + '00.00000'
        else:
            return str(degree).zfill(2) + str(minutes).zfill(2) + str(int(seconds)).zfill(2) + '{0:.5f}'.format(seconds - int(seconds))[1:]

    def parse_proj4_string(self, proj4_string):
        proj_type = re.search(r'.*\+proj=(\w+) ', proj4_string)
        if proj_type:
            self.proj_type = proj_type.group(1)

        datum = re.search(r'.*\+ellps=(\w+) ', proj4_string)  # not true, but only for our data
        if datum:
            self.datum = datum.group(1)

        units = re.search(r'.*\+units=(\w+) ', proj4_string)
        if units:
            self.units = units.group(1)

        lon_0 = re.search(r'.*\+lon_0=(\S*) ', proj4_string)
        if lon_0:
            self.lon_0 = lon_0.group(1)

        lat_0 = re.search(r'.*\+lat_0=(\S*) ', proj4_string)
        if lat_0:
            self.lat_0 = lat_0.group(1)

        x_0 = re.search(r'.*\+x_0=(\S*) ', proj4_string)
        if x_0:
            self.x_0 = x_0.group(1)

        y_0 = re.search(r'.*\+y_0=(\S*) ', proj4_string)
        if y_0:
            self.y_0 = y_0.group(1)

        scale = re.search(r'.*\+k=(\S*) ', proj4_string)
        if scale:
            self.scale = scale.group(1)


def add_projections_to_xml(projs, xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        print(e)
        root = ET.Element('data')
        tree = ET.ElementTree(root)

    try:
        source_projections = [projection.text for projection in root.iter('Name')]
    except TypeError as e:
        print(e)
        source_projections = []

    for proj_data in projs:
        if Projection.name_decode(proj_data[0]) in source_projections:
            continue

        proj = Projection()
        proj.name = proj_data[0]
        proj.parse_proj4_string(proj_data[3])
        if proj.magnet_datum != 'SK42':
            continue

        magnet_xml = magnet_xml_projection(proj)
        root.append(magnet_xml)

    raw_new_tree = ET.tostring(root, 'utf-8')
    reparsed_new_tree = minidom.parseString(raw_new_tree)
    with open(xml_file, 'w', encoding='utf-8') as file:
        new_tree_xml = reparsed_new_tree.toprettyxml()
        file.write(new_tree_xml)


def magnet_xml_projection(proj):
    projection = ET.Element('Projection')

    name = ET.SubElement(projection, 'Name')
    name.text = proj.magnet_name

    unit = ET.SubElement(projection, 'Unit')
    unit.text = proj.magnet_units

    datum = ET.SubElement(projection, 'Datum')
    datum.text = proj.magnet_datum

    any_datum = ET.SubElement(projection, 'AnyDatum')
    any_datum.text = '0'

    proj_type = ET.SubElement(projection, 'Type')
    proj_type.text = proj.proj_type.upper()

    p0 = ET.SubElement(projection, 'P0')
    p0.set('name', 'Central Meridian')
    p0.text = proj.magnet_lon_0

    p1 = ET.SubElement(projection, 'P1')
    p1.set('name', 'Scale')
    p1.text = proj.scale

    p2 = ET.SubElement(projection, 'P2')
    p2.set('name', 'Lat0')
    p2.text = proj.magnet_lat_0

    p3 = ET.SubElement(projection, 'P3')
    p3.set('name', 'East0')
    p3.text = proj.x_0

    p4 = ET.SubElement(projection, 'P4')
    p4.set('name', 'North0')
    p4.text = proj.y_0

    return projection


def transliterate(name):
    slovar = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
              'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
              'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h',
              'ц': 'c', 'ч': 'cz', 'ш': 'sh', 'щ': 'scz', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
              'ю': 'u', 'я': 'ja', 'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
              'Ж': 'ZH', 'З': 'Z', 'И': 'I', 'Й': 'I', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
              'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H',
              'Ц': 'C', 'Ч': 'CZ', 'Ш': 'SH', 'Щ': 'SCH', 'Ъ': '', 'Ы': 'y', 'Ь': '', 'Э': 'E',
              'Ю': 'U', 'Я': 'YA', ',': '', '?': '', ' ': '_', '~': '', '!': '', '@': '', '#': '',
              '$': '', '%': '', '^': '', '&': '', '*': '', '(': '', ')': '', '-': '', '=': '', '+': '',
              ':': '', ';': '', '<': '', '>': '', '\'': '', '"': '', '\\': '', '/': '', '№': '',
              '[': '', ']': '', '{': '', '}': '', 'ґ': '', 'ї': '', 'є': '', 'Ґ': 'g', 'Ї': 'i',
              'Є': 'e', '—': ''}

    for key in slovar:
        name = name.replace(key, slovar[key])
    return name


def process(projs_source):
    if not os.path.exists(projs_source):
        raise FileNotFoundError("Can't find txt file with MSK projections: {}".format(projs_source))

    magnet_user_dir = r'C:\Users\{}\AppData\Roaming\MAGNET\Tools'.format(getpass.getuser())
    if not os.path.exists(magnet_user_dir):  # only for geoscan staff
        magnet_user_dir = r'C:\Users\{}\AppData\Roaming\MAGNET\Tools'.format(getpass.getuser() + '.GEOSCAN')

    if os.path.exists(magnet_user_dir):
        projs_data = list()
        with open(projs_source, 'r') as source:
            reader = csv.reader(source, delimiter='\t')
            start_line = True
            for row in reader:
                if not start_line:
                    projs_data.append(row)
                else:
                    start_line = False

        for root, dir, names in os.walk(magnet_user_dir):
            if 'userprojections.xml' in names:
                magnet_prj_source = os.path.join(root, 'userprojections.xml')
                add_projections_to_xml(projs_data, magnet_prj_source)
    else:
        raise FileNotFoundError("Can't find Magnet Tools user directory: {}".format(magnet_user_dir))


if __name__ == '__main__':
    # process("russian_msk.txt")
    pass
