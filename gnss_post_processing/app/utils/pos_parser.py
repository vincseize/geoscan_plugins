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


from collections import OrderedDict, Counter
from datetime import datetime, timedelta

from .exceptions import IndexErrorInPosFile


class PosParser:

    pos_indices = {
        'date': 0,
        'time': 1,
        'lat': 2,
        'lon': 3,
        'height': 4,
        'quality': 5,
        'ns': 6,
        'sdn': 7,
        'sde': 8,
        'sdu': 9,
        'sdne': 10,
        'sdeu': 11,
        'sdun': 12,
        'age': 13,
        'ratio': 14,
    }

    def __init__(self, file):
        self.file = file
        self.positions, self.quality = self.parse_pos_file()

    def parse_pos_file(self) -> (list, float):
        positions = OrderedDict()
        qualities = list()

        with open(self.file, 'r') as file:
            lines = file.readlines()

        try:
            start_index = 0
            while lines[start_index].startswith('%'):
                start_index += 1
        except IndexError:
            raise IndexErrorInPosFile(_("Pos file with computed result is empty"))

        for i in range(start_index, len(lines)):
            data_line = lines[i].split()
            if len(data_line) == len(self.pos_indices):
                date = data_line[self.pos_indices['date']].split("/")
                time = data_line[self.pos_indices['time']].split(":")
                time_event = datetime(year=int(date[0]), month=int(date[1]), day=int(date[2]),
                                      hour=int(time[0]), minute=int(time[1]), second=int(float(time[2])),
                                      microsecond=int(round((float(time[2]) - int(float(time[2]))), 3) * 1000000))

                lat, lon = float(data_line[self.pos_indices['lat']]), float(data_line[self.pos_indices['lon']])
                height = float(data_line[self.pos_indices['height']])
                quality = int(data_line[self.pos_indices['quality']])
                sdn = float(data_line[self.pos_indices['sdn']])
                sde = float(data_line[self.pos_indices['sde']])
                sdu = float(data_line[self.pos_indices['sdu']])

                position = dict(lat=lat, lon=lon, height=height, quality=quality, sdn=sdn, sde=sde, sdu=sdu)
                positions[time_event-timedelta(milliseconds=1)] = position
                positions[time_event] = position
                positions[time_event+timedelta(milliseconds=1)] = position

                qualities.append(quality)
            else:
                print("Unknown line in pos file: {}".format(lines[i]))

        avg_quality = Counter(qualities)[1] / len(qualities) * 100

        return positions, avg_quality


if __name__ == "__main__":
    pass
