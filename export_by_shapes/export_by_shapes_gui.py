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

import os
from collections import OrderedDict
import traceback

import PhotoScan
from PySide2 import QtWidgets

from common.shape_worker.shape_worker import get_shapes_by_group
from .export_by_shapes import Exporter
from common.utils.PluginBase import PluginBase
from common.utils.ui import load_ui_widget


class MainPlugin(PluginBase):

    NAME = "Export by shapes"
    VERSION = "1.0.5"

    def __init__(self):
        ui_path = os.path.join(os.path.dirname(__file__), 'export_by_shapes_base.ui')
        super(MainPlugin, self).__init__(ui_path)

        self._tasks = list()

    def _init_ui(self):
        """
        Initialize UI of plugin.
        :return: None
        """
        dlg = self.dlg
        self.load_values()

        dlg.addTaskBtn.clicked.connect(self.add_task)
        dlg.exportBtn.clicked.connect(self.export)

    def add_task(self):
        """
        Method adds export task
        :return:
        """

        def add_task_string():
            """
            Adds task string item in ListWidget, and in tasks list
            :return:
            """
            values = task_creator.get_task_values()
            if not values:
                self.add_task()
                return
            name = task_creator.dlg.modelCBox.currentText()
            self.dlg.tasksList.addItem('Export ' + name)
            self._tasks.append(values)

        task_creator = TaskCreator()

        result = task_creator.dlg.exec_()
        if result:
            task_creator.dump_values()
            add_task_string()

    def export(self):
        """
        Starts export process
        :return:
        """

        def set_progress(val):
            """
            Progress function
            :param val: progress in percents
            :return: None
            """
            print('Current: {:.2f}%'.format(val))
            # dlg.progressBar.setValue(val)
            PhotoScan.app.update()

        def processing_task(lst, progress):
            """
            Creates one export processing task (also with joint progress callback) from multiple functions
            :param lst: List of functions
            :param progress: progress callback function
            :return:
            """

            def progress_callback(val):
                """
                Progress callback function
                :param val: value of callback from one function
                :return: float in range 0, 100
                """
                progress((val + j * 100) / total)

            total = len(lst)
            for j, func in enumerate(lst):
                func(progress_callback)

        # Creating list of export functions
        tasks_func = []
        shapes_states = Exporter.save_shapes_states()
        for i, values in enumerate(self._tasks):
            source, grid_model, shapes, path, format, crs, mtw_crs, height_correction, resolution, buffer, tiff_compression, write_world, \
            jpeg_quality, tile_scheme, big_tiff, alpha_ch, tiff_overviews, tiled_tiff, background_color = values
            exporter = Exporter(
                chunk=PhotoScan.app.document.chunk,
                source=source,
                grid_model=grid_model,
                shapes=shapes,
                path=path,
                format=format,
                crs=crs,
                mtw_crs=mtw_crs,
                height_correction=height_correction,
                resolution=resolution,
                buffer=buffer,
                tiff_compression=tiff_compression,
                write_world=write_world,
                jpeg_quality=jpeg_quality,
                tile_scheme=tile_scheme,
                big_tiff=big_tiff,
                alpha_ch=alpha_ch,
                tiff_overviews=tiff_overviews,
                tiled_tiff=tiled_tiff,
                background_color=background_color,
                estimated_resolution=None,
            )
            tasks_func.append(exporter.export)

        # Start export
        self.safe_process(
            func=processing_task,
            use_crash_reporter={'plugin_name': self.NAME, 'plugin_version': self.VERSION, 'items': {}},
            success_message=_("Successfully exported!"),
            aborted_func=lambda: Exporter.upload_shapes_states(shapes_states),
            lst=tasks_func,
            progress=set_progress
        )


class TaskCreator(PluginBase):
    """
    Main GUI class
    """

    def __init__(self):
        ui_path = os.path.join(os.path.dirname(__file__), 'add_export_task_base.ui')
        super(TaskCreator, self).__init__(ui_path)

    def _init_ui(self):
        """
        Initialize UI of plugin.
        :return: None
        """
        dlg = self.dlg
        dlg.BackgroundColorComboBox.addItems(["White", "Black"])
        dlg.TIFFComrComboBox.addItems(['None', 'LZW', 'JPEG', 'Packbits', 'Deflate'])

        self.load_values()

        self.crs = PhotoScan.app.document.chunk.crs
        dlg.Crs_label.setText(self.crs.name)
        self.mtw_crs = None

        dlg.JPEGqualityBox.setValue(90)
        dlg.JPEGqualityBox.setSingleStep(1)

        dlg.pathBtn.clicked.connect(lambda: self.select_dir(dlg.pathLineEdit))
        dlg.crs_pushButton.clicked.connect(self.select_crs)
        dlg.format_comboBox.currentTextChanged.connect(lambda: self.set_mtw_crs())
        dlg.modelCBox.currentTextChanged.connect(lambda: self.block_height_correction())

        self.__fill_shapes_group_cbox()
        self.__fill_format_group_box()

    def select_crs(self):
        crs = PhotoScan.app.getCoordinateSystem()
        if crs:
            self.crs = crs
            self.dlg.Crs_label.setText(self.crs.name)

    def set_mtw_crs(self):
        if self.dlg.format_comboBox.currentText() == "MTW (only for DEM)":
            mtw_crs = MtwCrs()
            res = mtw_crs.dlg.exec_()
            if res:
                self.mtw_crs = mtw_crs.result
            else:
                pass
        else:
            pass

    def block_height_correction(self):
        if self.dlg.modelCBox.currentText() == "Orthomosaic":
            self.dlg.heightCorrection_doubleSpinBox.setEnabled(False)
        else:
            self.dlg.heightCorrection_doubleSpinBox.setEnabled(True)

    def __fill_shapes_group_cbox(self):
        """
        Fills shapes group checkbox from chunk.
        :raises RuntimeError if chunk is None.
        :return: None
        """
        chunk = PhotoScan.app.document.chunk

        try:
            d = OrderedDict((shp_group.label, shp_group) for shp_group in chunk.shapes.groups)
            self.dlg.shapesGroupCBox.clear()
            self.dlg.shapesGroupCBox.addItems(list(map(str, d.keys())))
            self.shape_groups_dict = d
        except AttributeError:
            PhotoScan.app.messageBox('Please, create shapes to use this plugin')

    def __fill_format_group_box(self):
        formats = ["TIFF/GeoTIFF", "JPEG", "JPEG 2000", "MTW (only for DEM)", "PNG", "BMP"]
        self.dlg.format_comboBox.clear()
        self.dlg.format_comboBox.addItems(formats)

    def __get_grid_model(self):
        """
        Matches selected check box item with grid model (orthomosaic or elevation).
        :return: Grid model
        """
        name = self.dlg.modelCBox.currentText()
        if name == "Orthomosaic":
            return PhotoScan.app.document.chunk.orthomosaic
        elif name == 'Digital elevation model':
            return PhotoScan.app.document.chunk.elevation
        else:
            self.show_message(_("Unexpected error"), _("Cannot resolve string \"{}\" and existing grid model"
                                                       ).format(name))

    def get_task_values(self):
        """
        Returns task values
        :return: None
        """

        # TODO: set progress to progress bar. App crashes in the end of processing

        def check_input_values():
            """
            Checks input values
            :return: bool. Success of check
            """
            if not os.path.isdir(path):
                self.show_message(
                    _("Not a directory"),
                    _("Path:\n{}\nIs not an existing directory!").format(path),
                    error=True
                )
                return False

            if not shapes:
                self.show_message(
                    _("Empty shapes list"),
                    _("Group: \"{}\" is empty!\nChoose other shapes group").format(shapes_label),
                    error=True
                )
                return False

            if grid_model is None:
                self.show_message(
                    _("Empty data source"),
                    _("There is no {} in chunk!").format(self.dlg.modelCBox.currentText().lower()),
                    error=True
                )
                return False
            return True

        dlg = self.dlg
        source = dlg.modelCBox.currentText()
        shapes_label = dlg.shapesGroupCBox.currentText()
        shapes = get_shapes_by_group(self.shape_groups_dict[shapes_label])
        grid_model = self.__get_grid_model()
        path = dlg.pathLineEdit.text()
        format = dlg.format_comboBox.currentText()
        crs = self.crs
        mtw_crs = self.mtw_crs
        height_correction = dlg.heightCorrection_doubleSpinBox.value()
        resolution = dlg.resolutionXSBox.value()
        buffer = dlg.bufferSBox.value()
        tiff_compression = dlg.TIFFComrComboBox.currentText()
        write_world = dlg.WorldBox.isChecked()
        jpeg_quality = dlg.JPEGqualityBox.value()
        tile_scheme = dlg.SchemeCheckBox.isChecked()
        big_tiff = dlg.BigTiffCheckBox.isChecked()
        alpha_ch = dlg.AlphaCheckBox.isChecked()
        tiff_overviews = dlg.TiffOverwiewsCheckBox.isChecked()
        tiled_tiff = dlg.TiledTiffCheckBox.isChecked()
        background_color = dlg.BackgroundColorComboBox.currentText() == 'White'

        if check_input_values():
            return source, \
                   grid_model, \
                   shapes, \
                   path, \
                   format, \
                   crs, \
                   mtw_crs, \
                   height_correction,  \
                   resolution, \
                   buffer, \
                   tiff_compression, \
                   write_world, \
                   jpeg_quality, \
                   tile_scheme, \
                   big_tiff, \
                   alpha_ch, \
                   tiff_overviews, \
                   tiled_tiff,\
                   background_color
        else:
            return False


class MtwCrs:
    def __init__(self):
        self.dlg = load_ui_widget(os.path.join(os.path.dirname(__file__), "mtw", "mtw_crs_gui.ui"))
        self.dlg.accepted.connect(self.ok)
        self.dlg.rejected.connect(self.cancel)
        self.result = None
        self.fill_vertical_datum_box()

    def fill_vertical_datum_box(self):
        datums = ["Baltic 1977 height", "Ellipsoidal Height", "Average Sea Level"]
        self.dlg.verticalDatum_comboBox.addItems(datums)
        self.dlg.verticalDatum_comboBox.setCurrentIndex(0)

    @staticmethod
    def get_vertical_datum_id(name):
        if name == "Baltic 1977 height":
            return 25
        elif name == "Ellipsoidal Height":
            return 29
        elif name == "Average Sea Level":
            return 27
        else:
            return None

    def ok(self):
        vertical_datum = self.get_vertical_datum_id(self.dlg.verticalDatum_comboBox.currentText())
        if self.dlg.GskProj_radioButton.isChecked():
            self.result = (1, vertical_datum, self.dlg.zone_spinBox.value())
        elif self.dlg.GskLatLong_radioButton.isChecked():
            self.result = (2, vertical_datum, None)
        elif self.dlg.noCrs_radioButton.isChecked():
            self.result = (3, vertical_datum, None)
        else:
            raise AssertionError("Unexpected error")

    def cancel(self):
        self.result = (0, None)


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext

    if PhotoScan.app.document.chunk is None:
        return PhotoScan.app.messageBox(_("Empty chunk!"))

    # noinspection PyBroadException
    try:
        exporter = MainPlugin()
        exporter.add_task()
        exporter.dlg.exec_()
    except Exception:
        traceback.print_exc()
        PhotoScan.app.messageBox(traceback.format_exc())
