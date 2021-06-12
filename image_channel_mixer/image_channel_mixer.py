"""Image Channel Mixer plugin for Agisoft Metashape

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
import cv2
from PIL import Image
import numpy as np
from PySide2 import QtWidgets, QtGui, QtCore
import Metashape

from common.loggers.email_logger import log_method_by_crash_reporter
from common.utils.ui import load_ui_widget


class ImageChannelMixer(QtWidgets.QDialog):

    NAME = "Image Channel Mixer"
    VERSION = "1.1.0"

    def __init__(self, parent=None):
        super().__init__()
        self.ui = load_ui_widget(os.path.join(os.path.dirname(__file__), "image_channel_mixer.ui"),
                                 parent=parent)

        self.viewer = PhotoViewer(self.ui.ImageLabel)

        self.image = ''
        self.cameras = list()
        self.get_cameras()

        self.ui.LeftButton.clicked.connect(self.show_previous_image)
        self.ui.RightButton.clicked.connect(self.show_next_image)

        self.ui.RedSpinBox.setEnabled(False)
        self.ui.GreenSpinBox.setEnabled(False)
        self.ui.BlueSpinBox.setEnabled(False)

        self.ui.RedhSlider.valueChanged[int].connect(self.red_slider)
        self.ui.RedSpinBox.valueChanged.connect(self.red_spinbox)
        self.ui.GreenhSlider.valueChanged[int].connect(self.green_slider)
        self.ui.GreenSpinBox.valueChanged.connect(self.green_spinbox)
        self.ui.BluehSlider.valueChanged[int].connect(self.blue_slider)
        self.ui.BlueSpinBox.valueChanged.connect(self.blue_spinbox)

        self.ui.RedhSlider.sliderReleased.connect(self.channel_mixer)
        self.ui.GreenhSlider.sliderReleased.connect(self.channel_mixer)
        self.ui.BluehSlider.sliderReleased.connect(self.channel_mixer)

        self.ui.ChannelComboBox.addItems(['Red', 'Green', 'Blue'])
        self.ui.ChannelComboBox.currentTextChanged.connect(self.channel_box)

        self.ui.ShowButton.clicked.connect(self.show_button)

        self.ui.ConvertButton.clicked.connect(self.convert_images)

        self.CHANNELS()
        self.channel_box()

        self.ui.setMaximumSize(790, 930)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def show_button(self):
        self.channel_mixer(mode='next_image')

    def get_cameras(self):
        chunk = Metashape.app.document.chunk
        self.cameras = [camera for camera in chunk.cameras]
        self.ui.CamerasComboBox.addItems([camera.label for camera in self.cameras])

    def show_image(self, mode='dev', image=None):
        self.image = self.ui.CamerasComboBox.currentText()

        if mode == '_camera':
            self.viewer.setPhoto(QtGui.QPixmap(self.cameras[self.ui.CamerasComboBox.currentIndex()].photo.path))
            self.get_img_bands(self.cameras[self.ui.CamerasComboBox.currentIndex()].photo.path)
            self.channel_mixer(mode='next_image')
        elif mode == 'mixer':
            height, width, channel = image.shape
            bytesPerLine = 3 * width
            qImg = QtGui.QImage(image.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888).rgbSwapped()
            self.viewer.setPhoto(QtGui.QPixmap(qImg))
        elif mode == 'dev':
            image = self.rescale_input_image(self.cameras[self.ui.CamerasComboBox.currentIndex()].photo.path)
            height, width, channel = image.shape
            bytesPerLine = 3 * width
            qImg = QtGui.QImage(image.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888).rgbSwapped()
            self.viewer.setPhoto(QtGui.QPixmap(qImg))
        else:
            raise ValueError('Unknown mode in self.show_image(): {}'.format(mode))

    def show_previous_image(self):
        index = self.ui.CamerasComboBox.currentIndex() - 1
        if index >= 0:
            self.ui.CamerasComboBox.setCurrentIndex(index)
            self.channel_mixer(mode='next_image')

    def show_next_image(self):
        index = self.ui.CamerasComboBox.currentIndex() + 1
        if index < len(self.cameras):
            self.ui.CamerasComboBox.setCurrentIndex(index)
            self.channel_mixer(mode='next_image')

    def red_slider(self):
        self.ui.RedSpinBox.setValue(self.ui.RedhSlider.value())

    def green_slider(self):
        self.ui.GreenSpinBox.setValue(self.ui.GreenhSlider.value())

    def blue_slider(self):
        self.ui.BlueSpinBox.setValue(self.ui.BluehSlider.value())

    def red_spinbox(self):
        self.ui.RedhSlider.setValue(self.ui.RedSpinBox.value())

    def green_spinbox(self):
        self.ui.GreenhSlider.setValue(self.ui.GreenSpinBox.value())

    def blue_spinbox(self):
        self.ui.BluehSlider.setValue(self.ui.BlueSpinBox.value())

    def channel_box(self):
        if self.ui.ChannelComboBox.currentText() == 'Red':
            self.ui.RedhSlider.setValue(self.r_red)
            self.ui.GreenhSlider.setValue(self.r_green)
            self.ui.BluehSlider.setValue(self.r_blue)

        elif self.ui.ChannelComboBox.currentText() == 'Green':
            self.ui.RedhSlider.setValue(self.g_red)
            self.ui.GreenhSlider.setValue(self.g_green)
            self.ui.BluehSlider.setValue(self.g_blue)

        elif self.ui.ChannelComboBox.currentText() == 'Blue':
            self.ui.RedhSlider.setValue(self.b_red)
            self.ui.GreenhSlider.setValue(self.b_green)
            self.ui.BluehSlider.setValue(self.b_blue)

    def CHANNELS(self):
        self.r_red, self.r_green, self.r_blue = 100, 0, 0
        self.g_red, self.g_green, self.g_blue = 0, 100, 0
        self.b_red, self.b_green, self.b_blue = 0, 0, 100

    def rescale_input_image(self, image_path):
        image = Image.open(image_path)
        image = np.array(image)
        scale = (image.shape[0] / 500 + image.shape[1] / 750) / 2
        height = int(image.shape[0] / scale)
        width = int(image.shape[1] / scale)
        rescaled_image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)

        self.r = rescaled_image[:, :, 0].astype('uint16')
        self.g = rescaled_image[:, :, 1].astype('uint16')
        self.b = rescaled_image[:, :, 2].astype('uint16')

        self.nr, self.ng, self.nb = self.r, self.g, self.b

        return rescaled_image

    def channel_mixer(self, mode='update'):
        if mode == 'update':
            if self.ui.ChannelComboBox.currentText() == 'Red':
                self.r_red, self.r_green, self.r_blue = self.ui.RedhSlider.value(), \
                                                        self.ui.GreenhSlider.value(), \
                                                        self.ui.BluehSlider.value()
                nr = np.round(self.r * (self.r_red / 100)) + \
                     np.round(self.g * (self.r_green / 100)) + \
                     np.round(self.b * (self.r_blue / 100))
                self.nr = np.clip(nr, 0, 255)
                mixed_image = cv2.merge((self.nb.astype('uint8'), self.ng.astype('uint8'), self.nr.astype('uint8')))
                self.show_image(mode='mixer', image=mixed_image)

            elif self.ui.ChannelComboBox.currentText() == 'Green':
                self.g_red, self.g_green, self.g_blue = self.ui.RedhSlider.value(), \
                                                        self.ui.GreenhSlider.value(), \
                                                        self.ui.BluehSlider.value()
                ng = np.round(self.r * (self.g_red / 100)) + \
                     np.round(self.g * (self.g_green / 100)) + \
                     np.round(self.b * (self.g_blue / 100))
                self.ng = np.clip(ng, 0, 255)
                mixed_image = cv2.merge((self.nb.astype('uint8'), self.ng.astype('uint8'), self.nr.astype('uint8')))
                self.show_image(mode='mixer', image=mixed_image)

            elif self.ui.ChannelComboBox.currentText() == 'Blue':
                self.b_red, self.b_green, self.b_blue = self.ui.RedhSlider.value(), \
                                                        self.ui.GreenhSlider.value(), \
                                                        self.ui.BluehSlider.value()
                nb = np.round(self.r * (self.b_red / 100)) + \
                     np.round(self.g * (self.b_green / 100)) + \
                     np.round(self.b * (self.b_blue / 100))
                self.nb = np.clip(nb, 0, 255)
                mixed_image = cv2.merge((self.nb.astype('uint8'), self.ng.astype('uint8'), self.nr.astype('uint8')))
                self.show_image(mode='mixer', image=mixed_image)
            else:
                raise ValueError('Oops')
        elif mode == 'next_image':
            self.rescale_input_image(self.cameras[self.ui.CamerasComboBox.currentIndex()].photo.path)
            nr = np.round(self.r * (self.r_red / 100)) + \
                 np.round(self.g * (self.r_green / 100)) + \
                 np.round(self.b * (self.r_blue / 100))
            self.nr = np.clip(nr, 0, 255)

            ng = np.round(self.r * (self.g_red / 100)) + \
                 np.round(self.g * (self.g_green / 100)) + \
                 np.round(self.b * (self.g_blue / 100))
            self.ng = np.clip(ng, 0, 255)

            nb = np.round(self.r * (self.b_red / 100)) + \
                 np.round(self.g * (self.b_green / 100)) + \
                 np.round(self.b * (self.b_blue / 100))
            self.nb = np.clip(nb, 0, 255)

            mixed_image = cv2.merge((self.nb.astype('uint8'), self.ng.astype('uint8'), self.nr.astype('uint8')))
            self.show_image(mode='mixer', image=mixed_image)

    def get_img_bands(self, image):
        img = Image.open(image)
        img = np.array(img)
        self.r = img[:, :, 0].astype('uint16')
        self.g = img[:, :, 1].astype('uint16')
        self.b = img[:, :, 2].astype('uint16')

        self.nr, self.ng, self.nb = self.r, self.g, self.b
        del img

    def mix_image(self, image_path):
        self.get_img_bands(image_path)

        nr = np.round(self.r * (self.r_red / 100)) + \
             np.round(self.g * (self.r_green / 100)) + \
             np.round(self.b * (self.r_blue / 100))
        self.nr = np.clip(nr, 0, 255)

        ng = np.round(self.r * (self.g_red / 100)) + \
             np.round(self.g * (self.g_green / 100)) + \
             np.round(self.b * (self.g_blue / 100))
        self.ng = np.clip(ng, 0, 255)

        nb = np.round(self.r * (self.b_red / 100)) + \
             np.round(self.g * (self.b_green / 100)) + \
             np.round(self.b * (self.b_blue / 100))
        self.nb = np.clip(nb, 0, 255)

        mixed_image = cv2.merge((self.nb.astype('uint8'), self.ng.astype('uint8'), self.nr.astype('uint8')))

        return mixed_image


    def __convert_images(self):
        paths = [camera.photo.path for camera in self.cameras]

        progress = QtWidgets.QProgressDialog()
        progress.setLabelText("Saving new images ")
        progress.setModal(True)
        progress.show()
        Metashape.app.update()

        dirs = []
        for i, path in enumerate(paths):

            dir_for_mixed_images = os.path.join(os.path.dirname(path), 'mixed_images')
            if not os.path.exists(dir_for_mixed_images):
                os.mkdir(dir_for_mixed_images)
            dirs.append(dir_for_mixed_images)

            if progress.wasCanceled():
                break
            progress.setValue(int(i / len(paths) * 100))
            Metashape.app.update()

            image = Image.open(path)
            exif = image._getexif()
            del image
            mixed_image = cv2.merge((self.nb.astype('uint8'), self.ng.astype('uint8'), self.nr.astype('uint8')))
            new_image = Image.fromarray(mixed_image)
            new_image.save(os.path.join(dir_for_mixed_images, os.path.basename(path)), format='JPEG', exif=exif)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def convert_images(self):
        if not self.ui.DirCheckBox.isChecked():
            path = Metashape.app.getExistingDirectory()
            if not path:
                return
        else:
            path = None

        progress = QtWidgets.QProgressDialog()
        progress.setLabelText("Saving new images ")
        progress.setModal(True)
        progress.show()
        Metashape.app.update()

        if self.ui.SelectedCheckBox.isChecked():
            cameras = [camera for camera in self.cameras if camera.selected]
        else:
            cameras = [camera for camera in self.cameras]

        dirs = []
        for i, camera in enumerate(cameras):
            if self.ui.DirCheckBox.isChecked():
                dir_for_mixed_images = os.path.join(os.path.dirname(camera.photo.path), 'mixed_images')
                if not os.path.exists(dir_for_mixed_images):
                    os.mkdir(dir_for_mixed_images)
                dirs.append(dir_for_mixed_images)
            else:
                dir_for_mixed_images = path

            if progress.wasCanceled():
                break
            progress.setValue(int(i / len(cameras) * 100))
            Metashape.app.update()

            mixed_image = self.mix_image(camera.photo.path)
            mixed_image_str = mixed_image.tostring()
            new_image = Metashape.Image.fromstring(mixed_image_str, self.nr.shape[1], self.nr.shape[0], 'BGR', 'U8')
            new_image_dir = os.path.join(dir_for_mixed_images, os.path.basename(camera.photo.path))
            new_image.save(new_image_dir)

            if self.ui.checkBox.isChecked():
                camera.photo.path = new_image_dir

        Metashape.app.messageBox('Finished!')

    def log_values(self):
        d = {
            "Channel": self.ui.ChannelComboBox.currentText(),
            "Red value": self.ui.RedSpinBox.value(),
            "Green value": self.ui.GreenSpinBox.value(),
            "Blue value": self.ui.BlueSpinBox.value(),
            "Create new directories": self.ui.DirCheckBox.isChecked(),
            "Convert only selected": self.ui.SelectedCheckBox.isChecked(),
            "Change paths to new": self.ui.checkBox.isChecked(),
            "First Camera path from chunk": self.cameras[0].photo.path if self.cameras else None,
        }
        return d


class PhotoViewer(QtWidgets.QGraphicsView):
    photoClicked = QtCore.Signal(QtCore.QPoint)

    def __init__(self, parent):
        super(PhotoViewer, self).__init__(parent)
        self._zoom = 0
        self._empty = True
        self._scene = QtWidgets.QGraphicsScene(self)
        self._scene.setSceneRect(0, 0, 750, 500)
        self._photo = QtWidgets.QGraphicsPixmapItem()
        self._scene.addItem(self._photo)
        self.setScene(self._scene)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

    def hasPhoto(self):
        return not self._empty

    def fitInView(self, scale=True):
        rect = QtCore.QRectF(self._photo.pixmap().rect())
        if not rect.isNull():
            self.setSceneRect(rect)
            if self.hasPhoto():
                unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.scale(factor, factor)
            self._zoom = 0

    def setPhoto(self, pixmap=None):
        self._zoom = 0
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
        else:
            self._empty = True
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self._photo.setPixmap(QtGui.QPixmap())
        self.fitInView()

    def wheelEvent(self, event):
        if self.hasPhoto():
            if event.angleDelta().y() > 0:
                factor = 1.25
                self._zoom += 1
            else:
                factor = 0.8
                self._zoom -= 1
            if self._zoom > 0:
                self.scale(factor, factor)
            elif self._zoom == 0:
                self.fitInView()
            else:
                self._zoom = 0

    def toggleDragMode(self):
        if self.dragMode() == QtWidgets.QGraphicsView.ScrollHandDrag:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        elif not self._photo.pixmap().isNull():
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()
    dlg = ImageChannelMixer(parent=parent)
    dlg.ui.exec_()
