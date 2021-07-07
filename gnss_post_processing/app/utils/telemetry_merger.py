"""GNSS Post Processing plugin for Agisoft Metashape

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

from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
import os
import re
from xml.dom import minidom
import xml.etree.cElementTree as ET
import Metashape

from .pos_parser import PosParser


def reproject_point(source_crs, target_crs, north, east, height):
    point = Metashape.Vector([east, north, height])
    reprojected_point = Metashape.CoordinateSystem.transform(point, source_crs, target_crs)
    return reprojected_point


class PositionMerger:
    def __init__(self, pos_file, pos_track_file, telemetry_file, output, reproject,
                 crs=None, extension=False, quality=None,
                 use_estimated_accuracy=True, q1_accuracy=0.1, q2_accuracy=1,
                 use_telemetry_coordinates=True):
        self.crs = crs
        self.extension = extension
        self.pos_file = pos_file
        self.pos_track_file = pos_track_file
        self.telemetry_file = telemetry_file
        self.output = output
        self.reproject = reproject
        self.quality = quality
        self.use_estimated_accuracy = use_estimated_accuracy
        self.use_telemetry_coordinates = use_telemetry_coordinates
        self.q_accuracy = defaultdict(lambda: 10)
        self.q_accuracy.update({1: q1_accuracy, 2: q2_accuracy})

        self.title = None

    def parse_pos_file(self):
        pos_parser = PosParser(file=self.pos_file)
        return pos_parser.positions

    def parse_pos_track_file(self):
        pos_parser = PosParser(file=self.pos_track_file)
        return pos_parser.positions

    @classmethod
    def parse_telemetry_file(cls, telemetry_file, silently=False):
        telemetry_positions = OrderedDict()
        with open(telemetry_file, 'r', encoding='utf8') as file:
            lines = file.readlines()

        start_index = 0
        title = None
        while '#' in lines[start_index]:
            title = lines[start_index].split()
            start_index += 1

        title.pop(0)
        for i in range(start_index, len(lines)):
            data_line = lines[i].split("\t")

            if len(title) == len(data_line):
                try:
                    time_event = cls.get_date_from_telemetry_line(data_line, title_index=title.index('time'))
                    position = dict(name=data_line[title.index('file')],
                                    lat=float(data_line[title.index('lat')]), lon=float(data_line[title.index('lon')]),
                                    height=float(data_line[title.index('altGPS')]),
                                    roll=float(data_line[title.index('roll')]),
                                    pitch=float(data_line[title.index('pitch')]),
                                    yaw=float(data_line[title.index('yaw')]))
                    telemetry_positions[time_event] = position
                except (ValueError, IndexError):
                    if not silently:
                        print("Invalid string ({}) in telemetry file ({}), event excluded".format(telemetry_file,
                                                                                                  start_index + i))
                    continue

            else:
                if not silently:
                    print("Empty/incorrect line in telemetry file: {}".format(lines[i]))

        return telemetry_positions

    @staticmethod
    def get_date_from_telemetry_line(time_line, title_index):
        date_format = re.compile(r"(\d\d\d\d)[./\\:\-](\d\d)[./\\:\-](\d\d) (\d+?)[./\\:\-](\d+?)[./\\:\-](\d+)[\.,](\d*)")
        date = re.search(date_format, time_line[title_index])
        if not date:
            raise ValueError("Unknown type of time string in telemetry file: {}".format(time_line))

        try:
            microseconds = int(date.group(7)) * 10**(6-len(date.group(7)))
            time_event = datetime(year=int(date.group(1)), month=int(date.group(2)), day=int(date.group(3)),
                                  hour=int(date.group(4)), minute=int(date.group(5)), second=int(date.group(6)),
                                  microsecond=int(microseconds))
        except:
            raise IndexError("date parser error: [{}, {}, {}, {}, {}, {}, {} equals to ]".format(
                date.group(1), date.group(2), date.group(3), date.group(4), date.group(5), date.group(6), date.group(7),
            int(date.group(7)) * 10**(6-len(date.group(7))))
            )

        if time_event.microsecond % 1000 >= 500:
            microseconds = (time_event.microsecond // 1000 + 1) * 1000
            time_event = time_event.replace(microsecond=0)
            time_event += timedelta(microseconds=microseconds)
        else:
            microseconds = (time_event.microsecond // 1000) * 1000
            time_event = time_event.replace(microsecond=0)
            time_event += timedelta(microseconds=microseconds)

        return time_event

    def get_point(self, event, positions):
        if self.reproject:
            point = reproject_point(source_crs=self.reproject[0],
                                    target_crs=self.reproject[1],
                                    north=float(positions[event]['lat']),
                                    east=float(positions[event]['lon']),
                                    height=float(positions[event]['height'])
                                    )
        else:
            point = (positions[event]['lon'],
                     positions[event]['lat'],
                     positions[event]['height'])
        return point

    @staticmethod
    def __find_nearest_position(event_time, pos_positions, limit=0.1):
        for time, data in pos_positions.items():
            if abs(time - event_time) < timedelta(seconds=limit):
                return time
        return None

    @staticmethod
    def interpolate_position(event_time, pos_positions):
        before = event_time.replace(microsecond=event_time.microsecond // 10**5 * 10**5)
        after = before + timedelta(seconds=0.1)
        w = event_time.microsecond / 10**6
        if before in pos_positions and after in pos_positions:
            pos_before, pos_after = pos_positions[before], pos_positions[after]
            try:
                interpolated = dict(
                    lat=round((w * pos_before['lat'] + (1 - w) * pos_after['lat']), 9),
                    lon=round((w * pos_before['lon'] + (1 - w) * pos_after['lon']), 9),
                    height=round((w * pos_before['height'] + (1 - w) * pos_after['height']), 3),
                    quality=max(pos_before['quality'], pos_after['quality']),
                    sdn=max(pos_before['sdn'], pos_after['sdn']),
                    sde=max(pos_before['sde'], pos_after['sde']),
                    sdu=max(pos_before['sdu'], pos_after['sdu']),
                )
                return interpolated
            except KeyError:
                return None
        else:
            return None

    def build_estimated_pos_line(self, name, pos_event, telemetry_event, pos_positions, telemetry_positions):
        point = self.get_point(pos_event, pos_positions)
        line = [
            name,
            str(round(point[1], 9)),
            str(round(point[0], 9)),
            str(round(point[2], 3)),
            telemetry_positions[telemetry_event]['roll'],
            telemetry_positions[telemetry_event]['pitch'],
            telemetry_positions[telemetry_event]['yaw'],
            pos_positions[pos_event]['quality'],
            pos_positions[pos_event]['sdn'],
            pos_positions[pos_event]['sde'],
            pos_positions[pos_event]['sdu'],
            telemetry_event.strftime('%Y.%m.%d %H:%M:%S.%f\n'),
        ]
        return line

    def build_navigation_pos_line(self, name, event, telemetry_positions, silently=False):
        point = self.get_point(event, telemetry_positions)
        line = [
            name,
            str(round(point[1], 9)),
            str(round(point[0], 9)),
            str(round(point[2], 3)),
            telemetry_positions[event]['roll'],
            telemetry_positions[event]['pitch'],
            telemetry_positions[event]['yaw'],
            '',
            '',
            '',
            '',
            event.strftime('%Y.%m.%d %H:%M:%S.%f\n'),
        ]
        if not silently:
            print("{}: can't find in adjusted coordinates, "
                  "navigation coordinates will be used in merged file.".format(name))
        return line

    def merge(self, silently=False):
        self.result = list()
        self.result.append(
            "# Processed by Geoscan GNSS Post Processing plugin (Agisoft Metashape).\n" \
            "# Time: {}.\n" \
            "# User: {}.\n" \
            "# Fixed solutions: {} %.\n" \
            "# file\t lat\t lon\t height\t roll\t pitch\t yaw\t quality\t sdn\t sde\t sdu\t time\n".format(
                datetime.now().replace(microsecond=0), os.getlogin(), round(self.quality, 1))
        )

        pos_positions = self.parse_pos_file()
        pos_track_positions = self.parse_pos_track_file()
        telemetry_positions = self.parse_telemetry_file(self.telemetry_file)
        self.nav_positions = list()

        for photo_event in telemetry_positions.keys():
            if self.extension:
                name = telemetry_positions[photo_event]['name']
            else:
                name = os.path.splitext(telemetry_positions[photo_event]['name'])[0]
            self.title = name.split('.')[0] + '_GNSS' if not self.title else self.title

            if photo_event in pos_positions:
                line = self.build_estimated_pos_line(name=name, pos_event=photo_event, telemetry_event=photo_event,
                                                     pos_positions=pos_positions, telemetry_positions=telemetry_positions)
            else:
                interpolated = self.interpolate_position(photo_event, pos_track_positions)
                if interpolated:
                    pos_positions[photo_event] = interpolated
                    line = self.build_estimated_pos_line(name=name, pos_event=photo_event, telemetry_event=photo_event,
                                                         pos_positions=pos_positions,
                                                         telemetry_positions=telemetry_positions)
                elif self.use_telemetry_coordinates:
                    line = self.build_navigation_pos_line(name=name, event=photo_event,
                                                          telemetry_positions=telemetry_positions,
                                                          silently=silently)
                    self.nav_positions.append(name)
                else:
                    continue

            self.result.append(line)

    def write_merged_txt(self, path=None):
        if not path:
            path = self.output + '.txt'

        with open(path, 'w') as file:
            start = True
            for line in self.result:
                if start:
                    file.write(line)
                    start = False
                else:
                    file.write("\t".join(["{}".format(item) for item in line]))

    def write_merged_xml(self, path=None):
        root = ET.Element('reference')
        root.set("version", "1.2.0")
        cameras = ET.SubElement(root, 'cameras')
        for i in range(1, len(self.result)):
            label, y, x, z, roll, pitch, yaw, quality, sdn, sde, sdu, event_time = self.result[i]
            camera = ET.SubElement(cameras, 'camera')
            camera.set("label", label)
            c_reference = ET.SubElement(camera, 'reference')
            c_reference.set("x", str(x))
            c_reference.set("y", str(y))
            c_reference.set("z", str(z))
            c_reference.set("roll", str(roll))
            c_reference.set("pitch", str(pitch))
            c_reference.set("yaw", str(yaw))
            c_reference.set("sypr", "10")
            if label in self.nav_positions:
                c_reference.set("enabled", "false")
            else:
                if self.use_estimated_accuracy:
                    c_reference.set("sx", str(sde))
                    c_reference.set("sy", str(sdn))
                    c_reference.set("sz", str(sdu))
                else:
                    c_reference.set("sxyz", str(self.q_accuracy[quality]))
                c_reference.set("enabled", "true")

        if self.crs:
            reference = ET.SubElement(root, 'reference')
            reference.text = self.crs

        settings = ET.SubElement(root, 'settings')
        s_property1 = ET.SubElement(settings, 'property')
        s_property1.set("name", "accuracy_tiepoints")
        s_property1.set("value", "1")
        s_property2 = ET.SubElement(settings, 'property')
        s_property2.set("name", "accuracy_cameras")
        s_property2.set("value", "10")
        s_property3 = ET.SubElement(settings, 'property')
        s_property3.set("name", "accuracy_cameras_ypr")
        s_property3.set("value", "10")
        s_property4 = ET.SubElement(settings, 'property')
        s_property4.set("name", "accuracy_markers")
        s_property4.set("value", "0.005")
        s_property5 = ET.SubElement(settings, 'property')
        s_property5.set("name", "accuracy_scalebars")
        s_property5.set("value", "0.001")
        s_property5 = ET.SubElement(settings, 'property')
        s_property5.set("name", "accuracy_projections")
        s_property5.set("value", "0.5")

        dom = minidom.parseString(ET.tostring(root))
        if not path:
            with open(self.output + '.xml', 'w') as file:
                file.write(dom.toprettyxml(indent='  '))
        else:
            with open(path, 'w') as file:
                file.write(dom.toprettyxml(indent='  '))


if __name__ == '__main__':
    pass
