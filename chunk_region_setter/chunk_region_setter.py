"""Set region plugin for Agisoft Metashape

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

import Metashape
import re
import numpy as np
from osgeo import osr, ogr
from PySide2.QtWidgets import *
from PySide2 import QtCore

from common.loggers.email_logger import log_method_by_crash_reporter
from .CoordinateUI import CoordinateUI


dlg = None


class ChunkRegionSetter(QDialog):

    NAME = "Set region"
    VERSION = "1.0.1"

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.vbox = QVBoxLayout(self)
        self.firstPoint = CoordinateUI()
        self.firstPointLabel = QLabel()
        self.secondPointLabel = QLabel()
        self.bufferLabel = QLabel()
        self.bufferLine = QLineEdit()
        self.secondPoint = CoordinateUI()
        self.process_btn = QPushButton()
        self.process_btn.setMinimumSize(400, 23)
        self.cnt_process_btn = QPushButton()
        self.cnt_process_btn.setMinimumSize(400, 23)

        self.chunk = Metashape.app.document.chunk
        self.init_ui()

    def init_ui(self):
        self.firstPointLabel.setText(_("Southwest point:"))
        self.vbox.addWidget(self.firstPointLabel)
        self.vbox.addLayout(self.firstPoint.layout)
        self.secondPointLabel.setText(_("Northeast point:"))
        self.vbox.addWidget(self.secondPointLabel)
        self.vbox.addLayout(self.secondPoint.layout)

        self.cnt_process_btn.setText(_("Add coordinates from selected contour"))
        self.cnt_process_btn.clicked.connect(lambda: self.process(True))
        self.vbox.addWidget(self.cnt_process_btn)

        self.bufferLabel.setText(_("Buffer (m):"))
        self.vbox.addWidget(self.bufferLabel)
        self.bufferLine.setText("0")
        self.vbox.addWidget(self.bufferLine)

        self.process_btn.setText(_("Set region"))
        self.process_btn.clicked.connect(lambda: self.process())
        self.vbox.addWidget(self.process_btn)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def process(self, by_contour=False):
        from common.utils import bridge
        reg = Metashape.Region()
        if by_contour:
            if self.chunk.crs.proj4 == self.chunk.shapes.crs.proj4:
                self.coordinates_from_shp(reproject=False)
            else:
                self.coordinates_from_shp(reproject=True)
        else:
            buffer = float(self.bufferLine.text())
            xf = self.firstPoint.X.line.text()
            yf = self.firstPoint.Y.line.text()
            zf = self.firstPoint.Z.line.text()

            xs = self.secondPoint.X.line.text()
            ys = self.secondPoint.Y.line.text()
            zs = self.secondPoint.Z.line.text()

            if buffer != 0 and ('proj=latlong' or 'proj=longlat') in self.chunk.crs.proj4:
                x1, y1, z1 = self.reproject_points(float(xf), float(yf), float(zf), mode='tobuffer')

                x2, y2, z2 = self.reproject_points(float(xs), float(ys), float(zs), mode='tobuffer')

                out_x1, out_y1, out_z1 = self.reproject_points(x1 - buffer, y1 - buffer, z1, mode='frombuffer')

                out_x2, out_y2, out_z2 = self.reproject_points(x2 + buffer, y2 + buffer, z2, mode='frombuffer')

                self.firstPoint.X.line.setText('{}'.format(round(out_x1, 7)))
                self.firstPoint.Y.line.setText('{}'.format(round(out_y1, 7)))
                self.firstPoint.Z.line.setText('{}'.format(round(out_z1, 3)))

                self.secondPoint.X.line.setText('{}'.format(round(out_x2, 7)))
                self.secondPoint.Y.line.setText('{}'.format(round(out_y2, 7)))
                self.secondPoint.Z.line.setText('{}'.format(round(out_z2, 3)))

            elif buffer != 0 and re.search('units=m', self.chunk.crs.proj4):
                self.firstPoint.X.line.setText('{}'.format((float(xf) - buffer)))
                self.firstPoint.Y.line.setText('{}'.format(float(yf) - buffer))
                self.firstPoint.Z.line.setText(zf)

                self.secondPoint.X.line.setText('{}'.format(float(xs) + buffer))
                self.secondPoint.Y.line.setText('{}'.format(float(ys) + buffer))
                self.secondPoint.Z.line.setText(zs)

            f = self.firstPoint.get_vector()
            s = self.secondPoint.get_vector()
            if f is None or s is None:
                return
            for i in range(3):
                if f[i] > s[i]:
                    f[i], s[i] = s[i], f[i]
            f = bridge.chunk_crs_to_geocentric(f)
            s = bridge.chunk_crs_to_geocentric(s)

            reg.center = bridge.geocentric_to_camera((f + s) / 2.)

            reg.rot = self.get_rot()
            # reg.size = (s - f) / scale
            reg.size = (bridge.geocentric_to_camera(s) - bridge.geocentric_to_camera(f))
            reg.size = reg.rot.t() * reg.size
            self.chunk.region = reg

            self.firstPoint.X.line.setText('{}'.format(xf))
            self.firstPoint.Y.line.setText('{}'.format(yf))
            self.firstPoint.Z.line.setText('{}'.format(zf))
            self.secondPoint.X.line.setText('{}'.format(xs))
            self.secondPoint.Y.line.setText('{}'.format(ys))
            self.secondPoint.Z.line.setText('{}'.format(zs))

    def coordinates_from_shp(self, reproject):
        x, y, z = [], [], []
        if not reproject:
            for shape in self.chunk.shapes:
                if shape.selected:
                    for point in shape.vertices:
                        x.append(point[0])
                        y.append(point[1])
                        z.append(point[2])
        else:
            for shape in self.chunk.shapes:
                if shape.selected:
                    for point in shape.vertices:
                        rx, ry, rz = self.reproject_points(point[0], point[1], point[2])
                        x.append(rx)
                        y.append(ry)
                        z.append(rz)

        if ('proj=latlong' or 'proj=longlat') in self.chunk.crs.proj4:
            round_n = 7
        else:
            round_n = 3

        self.firstPoint.X.line.setText("{}".format(round(min(x), round_n)))
        self.firstPoint.Y.line.setText("{}".format(round(min(y), round_n)))
        self.firstPoint.Z.line.setText("{}".format(round(min(z)-200, 3)))

        self.secondPoint.X.line.setText("{}".format(round(max(x), round_n)))
        self.secondPoint.Y.line.setText("{}".format(round(max(y), round_n)))
        self.secondPoint.Z.line.setText("{}".format(round(max(z)+200, 3)))

    def reproject_points(self, x, y, z, mode=''):
        if mode == 'tobuffer':
            self.utm_crs = self.get_utm_crs(x, y)

            source_crs = self.chunk.crs
            
            target = self.utm_crs
            osr_target_crs = osr.SpatialReference()
            osr_target_crs.ImportFromProj4(target)
            target_crs = Metashape.CoordinateSystem()
            target_crs.init(osr_target_crs.ExportToWkt())

        elif mode == 'frombuffer':
            source = self.utm_crs
            osr_source_crs = osr.SpatialReference()
            osr_source_crs.ImportFromProj4(source)
            source_crs = Metashape.CoordinateSystem()
            source_crs.init(osr_source_crs.ExportToWkt())

            target_crs = self.chunk.crs

        else:
            source_crs = self.chunk.shapes.crs
            target_crs = self.chunk.crs

        x, y, z = Metashape.CoordinateSystem.transform([x, y, z], source_crs, target_crs)

        return x, y, z

    def get_utm_crs(self, x, y):
        if y >= 0:
            north = True
        else:
            north = False
        lon = x
        if lon != 180:
            zone_number = int((lon + 180) // 6 + 1)
        else:
            zone_number = 60
        if north:
            utm_crs = '+proj=utm +zone={} +datum=WGS84 +units=m +no_defs'.format(zone_number)
        else:
            utm_crs = '+proj=utm +zone={} +south +datum=WGS84 +units=m +no_defs'.format(zone_number)

        return utm_crs

    @staticmethod
    def get_rot():
        import math
        doc = Metashape.app.document
        chunk = doc.chunk
        T = chunk.transform.matrix
        v = Metashape.Vector([0, 0, 0, 1])
        v_t = T * v
        v_t.size = 3
        m = chunk.crs.localframe(v_t)
        m = m * T
        s = math.sqrt(m[0, 0] * m[0, 0] + m[0, 1] * m[0, 1] + m[0, 2] * m[0, 2])  # scale factor
        # S = Metashape.Matrix( [[s, 0, 0], [0, s, 0], [0, 0, s]] ) #scale matrix
        matr = np.array([[m[0, 0], m[0, 1], m[0, 2]],
                         [m[1, 0], m[1, 1], m[1, 2]],
                         [m[2, 0], m[2, 1], m[2, 2]]])
        R = Metashape.Matrix(matr)
        R = R * (1. / s)
        return R.t()

    def log_values(self):
        d = {
            "First point": (self.firstPoint.X.line.text(), self.firstPoint.Y.line.text(), self.firstPoint.Z.line.text()),
            "Second point": (self.secondPoint.X.line.text(), self.secondPoint.Y.line.text(), self.secondPoint.Z.line.text()),
            "Buffer zone (m)": self.bufferLine.text(),
        }
        return d


def main(trans):
    global dlg
    trans.install()
    _ = trans.gettext
    app = QApplication.instance()
    parent = app.activeWindow()
    dlg = ChunkRegionSetter(parent)
    dlg.show()
