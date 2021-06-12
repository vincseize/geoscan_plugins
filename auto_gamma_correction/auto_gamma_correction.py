"""Auto-gamma correction plugin for Agisoft Metashape

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
import os
import shutil
import subprocess
import numpy as np
import traceback
from PySide2 import QtWidgets

from common.loggers.email_logger import log_method_by_crash_reporter
from common.startup.initialization import config
from .auto_gamma_correction_gui import Ui_Dialog


class GammaCorrection(QtWidgets.QDialog, Ui_Dialog):

    NAME = "Auto-gamma correction"
    VERSION = "1.0.2"

    def __init__(self):
        super().__init__()
        self.ui = Ui_Dialog()
        self.setupUi(self)
        self.checkBox.setChecked(False)
        self.signals()

        self.mogrify = os.path.join(config.get('Paths', 'resources'), 'imagemagick', 'mogrify.exe')

    @staticmethod
    def show_warning(text, header='Error'):
        app = QtWidgets.QApplication.instance()
        win = app.activeWindow()
        QtWidgets.QMessageBox.warning(win, header, text, QtWidgets.QMessageBox.Ok)

    def signals(self):
        self.buttonBox.accepted.connect(self.run)
        self.buttonBox.rejected.connect(self.close)

    def __rescale_intensity(self, image, in_range='image'):
        '''
        Contrast stretching for numpy arrays
        '''
        if in_range == 'image':
            imin, imax = np.min(image), np.max(image)
        else:
            imin, imax = in_range
        omin, omax = 0, 255
        image = np.clip(image, imin, imax)

        if imin != imax:
            image = (image - imin) / float(imax - imin)
        return np.asarray(image * (omax - omin) + omin, dtype=np.uint8)

    def __levels(self, rgb, p_low=1, p_high=99):
        '''
        Common method for contrast stretching
        '''
        p1 = np.percentile(rgb, p_low)
        p99 = np.percentile(rgb, p_high)
        rgb_exp_arr = self.rescale_intensity(rgb, in_range=(p1, p99))
        return rgb_exp_arr

    def auto_gamma(self, in_image, out_dir):
        shutil.copy(in_image, out_dir)
        out_camera_path = os.path.join(out_dir, os.path.basename(in_image))

        subprocess.call([self.mogrify, '-auto-gamma', os.path.abspath(out_camera_path)])
        subprocess.call([self.mogrify, '-contrast-stretch', '0.1%', os.path.abspath(out_camera_path)])

        return out_camera_path

    def __auto_gamma(self, in_image, out_dir):
        '''
        Deprecated.
        Auto-gamma by Wand (Python API for Imagemagick).
        Need fixes.
        :param in_image:
        :param out_dir:
        :return:
        '''
        from wand.image import Image

        out_camera_path = os.path.join(out_dir, os.path.basename(in_image))
        with Image(filename=in_image) as img:
            img.auto_gamma()
            img.save(filename=out_camera_path)

    def get_cameras(self):
        '''
        Get all cameras in Metashape project
        :return:
        '''
        chunk = Metashape.app.document.chunk
        if not self.checkBox.isChecked():
            self.cameras = [camera for camera in chunk.cameras]
        else:
            self.cameras = [camera for camera in chunk.cameras if camera.selected]
            if not self.cameras:
                raise ValueError

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def run(self):
        '''
        Main method
        :return:
        '''
        try:
            self.get_cameras()
        except ValueError:
            self.show_warning(_('There are no selected images'), 'Warning')
            return
        progress = QtWidgets.QProgressDialog()
        progress.setLabelText("Saving new images")
        progress.setModal(True)
        progress.show()
        Metashape.app.update()

        dirs = []
        for i, camera in enumerate(self.cameras):
            if progress.wasCanceled():
                break
            progress.setValue(int(i / len(self.cameras) * 100))
            Metashape.app.update()

            out_path_dir = os.path.join(os.path.dirname(camera.photo.path), 'autogamma_images')
            dirs.append(out_path_dir)

            if not os.path.exists(out_path_dir):
                os.mkdir(out_path_dir)

            try:
                out_camera_path = self.auto_gamma(camera.photo.path, out_path_dir)
                if self.checkBox2.isChecked():
                    camera.photo.path = out_camera_path
            except FileNotFoundError as e:
                print(traceback.print_exc())
                return

        try:
            dirs = set(dirs)
            dirs = list(dirs)
            for dir in dirs:
                subprocess.call('explorer {}'.format(os.path.abspath(dir)))
        except Exception:
            raise SystemError("Can't open 'dirs'")

    def log_values(self):
        d = {
            "Only selected": self.checkBox.isChecked(),
            "Change paths": self.checkBox2.isChecked(),
        }
        return d


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    window = GammaCorrection()
    window.exec_()
