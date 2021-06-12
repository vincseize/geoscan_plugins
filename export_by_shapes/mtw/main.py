"""Export by shapes plugin for Agisoft Metashape

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

from osgeo import gdal
import numpy as np
import os
import sys
import struct


def read_bytes(file):
    file = open(file, 'r+b')
    return file, file.read()


def read_int(s):
    return int.from_bytes(s, byteorder=sys.byteorder)


class MtwCrsBuilder:

    crs_offset = 320

    def __init__(self, mtw_file):
        self.length = 0
        self.file = mtw_file

    def set_nodata(self, value: int):
        self.write_object(296, "d", value)

    def create_geo_gsk(self, vertical_datum: int):
        self.set_units(units=2)
        self.set_map_type(map=16)
        self.set_projection(proj=33)
        self.set_epsg(epsg=0)
        self.set_ellipsoid(n=46)
        self.set_crs(n=33)
        self.set_vertical_datum(n=vertical_datum)
        self.set_k(1)

    def create_gsk_zone(self, zone: int, vertical_datum: int):
        self.set_units(units=2)
        self.set_map_type(map=21)
        self.set_projection(proj=1)
        self.set_epsg(epsg=0)
        self.set_ellipsoid(n=46)
        self.set_crs()
        self.set_crs_zone(zone)
        self.set_vertical_datum(n=vertical_datum)
        self.set_y_offset(500000)
        self.set_k(1)

        self.set_geod_dx(0.013)
        self.set_geod_dy(-0.092)
        self.set_geod_dz(-0.03)
        self.set_geod_rx(0.001738)
        self.set_geod_ry(-0.003559)
        self.set_geod_rz(0.004263)
        self.set_geod_m(0.0074 * 10**(-6))
        self.set_reprojection_type(7)

    def create_no_crs(self):
        self.set_units(units=2)

    @staticmethod
    def parse_wkt(wkt):
        pass

    def write_object(self, offset: int, format: str, object):
        bytesdata = struct.pack(format, object)

        self.file.seek(offset)
        self.file.write(bytesdata)

    def set_units(self, units: int = 2):
        """2 = cm"""
        self.write_object(304, "i", units)

    def set_map_type(self, map: int = 21):
        self.write_object(124, "i", map)

    def set_projection(self, proj: int = -1):
        self.write_object(128, "i", proj)

    def set_epsg(self, epsg: int = 0):
        self.write_object(132, "i", epsg)

    def set_additional_def_length(self):
        self.write_object(312, "i", self.length)

    def set_ellipsoid(self, n: int = 46):
        """
        ГСК-2011 = 46
        :param n: int - номер эллипсоида.
        """
        self.write_object(self.crs_offset + 24, "i", n)
        self.length += 4

    def set_vertical_datum(self, n: int = -1):
        """Не установлена = -1"""
        self.write_object(self.crs_offset + 28, "i", n)
        self.length += 4

    def set_crs(self, n: int = 10):
        """ГСК-2011 = 10"""
        self.write_object(self.crs_offset + 32, "i", n)
        self.length += 4

    def set_crs_zone(self, n: int):
        """ГСК-2011 = 10"""
        self.write_object(self.crs_offset + 36, "i", n)
        self.length += 4

    def set_y_offset(self, n: (int, float)):
        self.write_object(self.crs_offset + 40, "d", float(n))
        self.length += 8

    def set_x_offset(self, n: (int, float)):
        self.write_object(self.crs_offset + 48, "d", float(n))
        self.length += 8

    def set_k(self, k: (int, float) = 1.0):
        """масштабный коэффициент"""
        self.write_object(self.crs_offset + 216, "d", float(k))
        self.length += 8

    def set_geod_dx(self, n: (int, float)):
        self.write_object(self.crs_offset + 248, "d", float(n))
        self.length += 8

    def set_geod_dy(self, n: (int, float)):
        self.write_object(self.crs_offset + 256, "d", float(n))
        self.length += 8

    def set_geod_dz(self, n: (int, float)):
        self.write_object(self.crs_offset + 264, "d", float(n))
        self.length += 8

    def set_geod_rx(self, n: (int, float)):
        self.write_object(self.crs_offset + 272, "d", float(n))
        self.length += 8

    def set_geod_ry(self, n: (int, float)):
        self.write_object(self.crs_offset + 280, "d", float(n))
        self.length += 8

    def set_geod_rz(self, n: (int, float)):
        self.write_object(self.crs_offset + 288, "d", float(n))
        self.length += 8

    def set_geod_m(self, n: (int, float)):
        self.write_object(self.crs_offset + 296, "d", float(n))
        self.length += 8

    def set_reprojection_type(self, n: int = 7):
        self.write_object(self.crs_offset + 304, "i", n)
        self.length += 4


def raster_to_mtw(path, no_crs, height_correction=0, remove_raster=True, xsize=None, ysize=None):
    raster = gdal.Open(path)

    mtw_driver = gdal.GetDriverByName("RMF")
    mtw_name = os.path.splitext(os.path.basename(path))[0] + ".mtw"
    mtw_path = os.path.join(os.path.dirname(path), mtw_name)

    geotransform = raster.GetGeoTransform()
    if all([xsize, ysize]):
        geotransform = (geotransform[0], xsize, geotransform[2], geotransform[3], geotransform[4], -ysize)

    mtw = mtw_driver.Create(mtw_path,
                            xsize=raster.RasterXSize,
                            ysize=raster.RasterYSize,
                            bands=1,
                            eType=gdal.GDT_Int32,
                            options=["MTW=ON"])

    mtw.SetGeoTransform(geotransform)
    if not no_crs:
        mtw.SetProjection(raster.GetProjection())
    data = raster.GetRasterBand(1).ReadAsArray()
    nodata = raster.GetRasterBand(1).GetNoDataValue()
    data = (data * 100 + height_correction * 100).astype("int32")
    data[data == (nodata * 100 + height_correction * 100)] = -111111
    mtw.GetRasterBand(1).WriteArray(data)
    mtw.GetRasterBand(1).SetNoDataValue(-111111)
    mtw.SetMetadata({"ELEVATION_MINIMUM": str(np.min(data[data != -111111])),
                     "ELEVATION_MAXIMUM": str(np.max(data[data != -111111])),
                     "ELEVATION_UNITS": "cm"})
    del mtw
    del raster
    if remove_raster:
        os.remove(path)

    return mtw_path


def true_mtw(path):
    from shutil import copy

    raster_to_mtw(path, no_crs=True, remove_raster=False,
                  #xsize=1,
                  #ysize=1
                  )
    copy(path[:-4] + '.mtw', path[:-4] + '_new.mtw')

    mtw = open(path[:-4] + '_new.mtw', 'r+b')
    translator = MtwCrsBuilder(mtw)
    translator.create_no_crs()
    mtw.close()


def __read_test():
    offset = 320
    mtw_src, mtw = read_bytes(r"\\taiga\data\P281_2007_TulskayaforRR\paperwork\тестирование_плагинов\mtw\M-37-030-(118-ж).mtw")
    print(struct.unpack('i', mtw[offset * 2 + 12:offset * 2 + 16]))

    mtw_src, mtw = read_bytes(r"\\taiga\data\P281_2007_TulskayaforRR\paperwork\тестирование_плагинов\mtw\Прилужный_M-37-030-(118-ж)_ЦМР_2020_ГСК2011.mtw")
    print(struct.unpack('i', mtw[offset + 32:offset + 36]))

# def edit_mtw(path, offset, format, object):
def edit_mtw():
    path = r"C:\Users\a.kot.GEOSCAN\Downloads\reports_new\test\source_priluzh_scale.mtw"
    file = open(path, 'r+b')
    mtw_builder = MtwCrsBuilder(mtw_file=file)
    mtw_builder.write_object(136, "d", 2000)
    file.close()


mtw_structure1 = [4,4,4,4,4,32,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,8,8,8,8,8,8,8,8,8,1,1,1,1,4,4,4,4,1,1,1,1,1,2,1,4,4,1,1,1,1,32,8,8,8,4,1,1,1,1,4,4]
mtw_structure2 = [4,4,8,8,4,4,4,4,8,8,4,1,1,1,1,8,4,4,4,4,4,4,4,4,8,4,4,4,4,24,4,4,4,4,4,4,4,4,4,4,6,1,1,8,8,8,8,8,8,8,8,8,8,8,8,8,4,4,4,4]

def ppc():
    file_true = r"\\taiga\data\P302_2011_Voronezhskaya\SD_field\образцы\MTW - матрицы\Азарапино_N-38-076-(041-и)_ЦМР_2020_ГСК2011_зона_8.mtw"
    # file_false = r"\\taiga\data\P281_2007_TulskayaforRR\paperwork\тестирование_плагинов\mtw\Прилужный_M-37-030-(118-ж)_ЦМР_2020_ГСК2011.mtw"
    file_false = r"\\taiga\data\P281_2007_TulskayaforRR\paperwork\тестирование_плагинов\mtw\Прилужный_M-37-030-(118-ж)_ЦМР_2020_ГСК2011.mtw"
    file_panorama = r"\\taiga\data\P232_1909_TulskayaforRR\results\Пример оформления\Тульская область\Масштаб 1_2000\02_ЦОФП\04_ЦМР\01_ГСК-2011\Березовка_Тульская_N-37-051-(109-ж)_ЦОФП_2016_ГСК2011.mtw"

    mtw_src_true, mtw_true = read_bytes(file_true)
    mtw_src_false, mtw_false = read_bytes(file_false)

    # offset_min, offset_max = 16, 20

    offset_min = 0
    for l in mtw_structure1:
        offset_max = offset_min + l
        if (offset_max - offset_min) == 4:
            type = 'i'
        elif (offset_max - offset_min) == 8:
            type = 'd'
        elif (offset_max - offset_min) == 1:
            type = 'b'
        elif (offset_max - offset_min) == 2:
            type = 'h'
        elif (offset_max - offset_min) == 32:
            type = 's' * 32
            print(offset_min, offset_max,
                  "True: ", [s.decode('ascii') for s in struct.unpack(type, mtw_true[offset_min:offset_max])],
                  "False: ", struct.unpack(type, mtw_false[offset_min:offset_max]),
                  'panorama', struct.unpack(type, mtw_false[offset_min:offset_max]))

        else:
            print(offset_min, offset_max, 'passed')
            offset_min = offset_max
            continue

        print(offset_min, offset_max,
              "True: ", struct.unpack(type, mtw_true[offset_min:offset_max]),
              "False: ", struct.unpack(type, mtw_false[offset_min:offset_max]),
              'panorama', struct.unpack(type, mtw_false[offset_min:offset_max]))

        offset_min = offset_max

    print('_____________________________________________________________')
    offset_min = 320
    for l in mtw_structure2:
        offset_max = offset_min + l
        if (offset_max - offset_min) == 4:
            type = 'i'
        elif (offset_max - offset_min) == 8:
            type = 'd'
        elif (offset_max - offset_min) == 1:
            type = 'b'
        elif (offset_max - offset_min) == 2:
            type = 'h'
        else:
            print(offset_min, offset_max, 'passed')
            offset_min = offset_max
            continue

        print(offset_min, offset_max,
              "True: ", struct.unpack(type, mtw_true[offset_min:offset_max]),
              "False: ", struct.unpack(type, mtw_false[offset_min:offset_max]),
              'panorama', struct.unpack(type, mtw_false[offset_min:offset_max]))

        offset_min = offset_max


def edit_mtw(path):
    from shutil import copy
    copy(path, path[:-4] + '_new.mtw')

    mtw = open(path[:-4] + '_new.mtw', 'r+b')

    translator = MtwCrsBuilder(mtw)
    # translator.write_object(16, 'i', 1)
    # translator.write_object(96, 'i', 320)
    translator.write_object(312, 'i', 1376)

    mtw.close()


if __name__ == "__main__":
    path = r"\\nas1\Share\a.kot\mtw_exp\M-37-082-(057-з).tif"
    true_mtw(path)
    # ppc()
    # edit_mtw(r"\\taiga\data\P281_2007_TulskayaforRR\paperwork\тестирование_плагинов\mtw\Прилужный_M-37-030-(118-ж)_ЦМР_2020_ГСК2011.mtw")
