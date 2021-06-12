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

import os
import json

from common.startup.initialization import config


IGS14_FILE = os.path.join(config.get('Paths', 'resources'), 'GnssPostProcessing', 'igs14.atx')


class Igs14Parser:
    def __init__(self, igs14: str):
        self.igs14 = igs14
        self.antennas = os.path.join(os.path.dirname(igs14), 'antennas.json')
        if not os.path.exists(self.antennas):
            create_antenna_names_json(igs14=self.igs14, out=self.antennas)

    def get_antennas(self):
        with open(self.antennas, 'r') as file:
            antennas_data = json.load(file)

        if not antennas_data['modified'] == os.path.getmtime(self.igs14):
            antennas_data = create_antenna_names_json(igs14=self.igs14, out=self.antennas)

        return antennas_data['antennas']


def get_antennas():
    igs14 = Igs14Parser(IGS14_FILE)
    return igs14.get_antennas()


def create_antenna_names_json(igs14, out):
    path = igs14
    with open(path, 'r') as file:
        lines = file.readlines()

    voc = set()
    voc.add('')
    for line in lines:
        data = line.split()
        if data[-4:] == ['TYPE', '/', 'SERIAL', 'NO']:
            if data[0] in voc:
                voc.remove(data[0])
            else:
                voc.add(data[0])

    dataset = {'antennas': sorted(list(voc)), 'modified': os.path.getmtime(igs14)}
    with open(out, 'w') as file:
        json.dump(dataset, file)

    return dataset


if __name__ == '__main__':
    pass
