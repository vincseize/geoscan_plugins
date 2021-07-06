from osgeo import gdal, osr
import re
import os
import json
import subprocess
import Metashape
from PySide2 import QtWidgets

from .tab_generation_gui import Ui_Dialog
from common.loggers.email_logger import log_method_by_crash_reporter
from common.shape_worker.mapinfo_formats import fix_mapinfo_ref


class TabGeneration(QtWidgets.QDialog, Ui_Dialog):

    NAME = "Create TAB metadata for orthomosaics"
    VERSION = "1.0.1"

    def __init__(self):
        super().__init__()

        self.ui = Ui_Dialog()
        self.dir = ""
        self.setupUi(self)
        self.extensions()

        self.Browse.clicked.connect(self.browse)
        self.Path.textChanged.connect(self.pathline_signal)
        self.pushButton.clicked.connect(self.main)

        self.json = os.path.join(os.path.dirname(__file__), 'path_storage.json')
        if os.path.exists(self.json):
            with open(self.json, 'r') as file:
                self.dir = json.load(file)
                self.Path.setText(self.dir)

    @staticmethod
    def show_warning(header, text):
        app = QtWidgets.QApplication.instance()
        win = app.activeWindow()
        QtWidgets.QMessageBox.warning(win, header, text, QtWidgets.QMessageBox.Ok)

    def pathline_signal(self):
        self.dir = os.path.abspath(self.Path.text())

    def browse(self):
        self.dir = os.path.abspath(Metashape.app.getExistingDirectory('Select directory with orthoimages'))
        self.Path.setText(self.dir)

    def extensions(self):
        extensions = ['TIFF', 'JPEG', 'TIFF and JPEG']
        self.comboBox.addItems(extensions)
        self.comboBox.setCurrentIndex(0)

    @staticmethod
    def get_data_from_raster(raster):
        ds = gdal.Open(raster)

        filename = os.path.basename(raster)
        ref = osr.SpatialReference()
        ref.ImportFromWkt(ds.GetProjectionRef())
        mapinfo_ref = fix_mapinfo_ref(ref)
        ulx, xres, xskew, uly, yskew, yres = ds.GetGeoTransform()
        lrx = ulx + (ds.RasterXSize * xres)
        lry = uly + (ds.RasterYSize * yres)
        y_size, x_size = ds.RasterYSize, ds.RasterXSize

        del ds
        return filename, mapinfo_ref, ulx, uly, lrx, lry, x_size, y_size

    def create_tab_content(self, raster):
        filename, mapinfo_ref, ulx, uly, lrx, lry, x_size, y_size = self.get_data_from_raster(raster)
        start = '!table\n!version 300\n!charset WindowsCyrillic\n\nDefinition Table\n'
        name = '  File "{filename}"\n'.format(filename=filename)
        type_ = '  Type "RASTER"\n'
        p1 = '  ({x},{y}) (0,0) Label "Точка 1",\n'.format(x=ulx, y=uly)
        p2 = '  ({x},{y}) ({x_size},0) Label "Точка 2",\n'.format(x=lrx, y=uly, x_size=x_size)
        p3 = '  ({x},{y}) ({x_size},{y_size}) Label "Точка 3",\n'.format(x=lrx, y=lry, x_size=x_size, y_size=y_size)
        p4 = '  ({x},{y}) (0,{y_size}) Label "Точка 4"\n'.format(x=ulx, y=lry, y_size=y_size)

        if self.save_with_projection:
            projection = '  {proj}\n'.format(proj=mapinfo_ref)
        else:
            projection = '  CoordSys NonEarth Units "m" Units "m"\n'

        tab_content = start + name + type_ + p1 + p2 + p3 + p4 + projection
        return tab_content

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def main(self):
        def extension_filter(file):
            extension = os.path.splitext(file)[1].lower()

            if self.comboBox.currentText() == 'TIFF':
                result = True if extension in ['.tif', '.tiff'] else False
            elif self.comboBox.currentText() == 'JPEG':
                result = True if extension in ['.jpeg', '.jpg'] else False
            else:
                result = True if extension in ['.tif', '.tiff', '.jpeg', '.jpg'] else False

            return result

        self.save_with_projection = self.checkBox.isChecked()
        if not self.dir or not os.path.exists(self.dir):
            self.show_warning('Warning', "Path doesn't exist")
            return

        files = list(filter(extension_filter, os.listdir(self.dir)))

        if not files:
            ext = self.comboBox.currentText()
            self.show_warning('Warning', 'There are no {} orthoimages in the selected directory'.format(ext))
            return

        for file in files:
            tab = self.create_tab_content(os.path.abspath(os.path.join(self.dir, file)))
            with open(os.path.join(self.dir, os.path.splitext(file)[0] + '.tab'), 'w', encoding='cp1251') as tab_file:
                tab_file.write(tab)

        with open(self.json, 'w') as file:
            json.dump(self.dir, file)

        subprocess.call('explorer {}'.format(self.dir))

    def log_values(self):
        exts = set([os.path.splitext(file)[1] for file in os.listdir(self.dir)]) if self.dir else None
        d = {
            'Extension': self.comboBox.currentText(),
            'Unique extensions in user directory': exts,
            'Create TAB files with coordinate system parameters': self.checkBox.isChecked()
        }
        return d


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    exporter = TabGeneration()
    exporter.exec_()


if __name__ == '__main__':
    pass
