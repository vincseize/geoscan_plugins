"""Quality estimator plugin for Agisoft Metashape

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

from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
import numpy as np
import Metashape
from collections import OrderedDict, defaultdict

from common.loggers.email_logger import log_method_by_crash_reporter
from common.utils.ui import ProgressBar
import random


class QualityEstimator(QDialog):

    NAME = "Estimate images quality"
    VERSION = "1.0.1"

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        vbox = QVBoxLayout()
        num_box = QHBoxLayout()
        description = QLabel(_("Set number of images that will be randomly selected \n"
                               "from the chunk to estimate sharpness.\n\n"
                               "Result - 10 filtered images.The first 5 images are the sharpest,\n"
                               "the next five are the most blurry of the random set.\n"))

        lab_num_images = QLabel(_("Number of images to estimate:"))
        self.num_images = QLineEdit(str(50))
        num_box.addWidget(lab_num_images)
        num_box.addWidget(self.num_images)

        run = QPushButton(_("Run"))

        vbox.addWidget(description)
        vbox.addLayout(num_box)
        vbox.addWidget(run)
        self.setLayout(vbox)

        run.clicked.connect(self.run)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def run(self):
        estimate(int(self.num_images.text()))

    def log_values(self):
        d = {
            "Num images": self.num_images.text(),
            "PSX project path": Metashape.app.document.path,
        }
        return d


def main(trans):
    trans.install()
    _ = trans.gettext

    app = QApplication.instance()

    parent = app.activeWindow()

    dlg = QualityEstimator(parent)
    dlg.show()


def random_crop(img, height, width):
    h, w, c = img.shape
    x1 = np.random.randint(2*width, w-2*width)
    y1 = np.random.randint(2*height, h-2*height)
    x2 = x1 + width
    y2 = y1 + height
    img = img[y1:y2, x1:x2, :]
    return img


def estimate(num=50):
    quality = defaultdict(float)
    cameras = Metashape.app.document.chunk.cameras
    random.shuffle(cameras)

    pb = ProgressBar(_("Estimating Image quality"))
    for idx, cam in enumerate(cameras):
        if idx > num:
            break
        pb.update(int((idx / num) * 100))
        big_img = np.frombuffer(cam.photo.image('RGB', 'U8').tostring(),  dtype=np.uint8)
        w, h = cam.sensor.calibration.width, cam.sensor.calibration.height
        big_img = big_img.reshape((h, w, 3))
        for i in range(3):
            small_img = random_crop(big_img, int(0.2*h), int(0.2*w))
            h, w = small_img.shape[:2]
            im = Metashape.Image.fromstring(small_img.tostring(), w, h, 'RGB', 'U8')
            quality[cam.label] = max(Metashape.utils.estimateImageQuality(im), quality[cam.label])
    quality = OrderedDict(sorted(quality.items(), key=lambda x: x[1]))
    f = list(quality.keys())[-5:] + list(quality.keys())[:5]
    cams = [cam for cam in Metashape.app.document.chunk.cameras if cam.label in f]
    Metashape.app.photos_pane.setFilter(cams)
