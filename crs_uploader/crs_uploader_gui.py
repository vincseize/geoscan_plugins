"""CRS uploader for Agisoft Metashape.
Examples with CRS definitions you can find in 'crs' folder.

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
import shutil
import traceback
import textwrap
from configparser import NoOptionError
import Metashape

from common.loggers.email_logger import log_method_by_crash_reporter
from common.qt_wrapper.helpers import open_dir, open_file
from common.startup.initialization import config
from common.utils.PluginBase import PluginBase
from __scripts.add_russian_projections_to_MAGNET import process as upload_crs_to_magnet


class MainDialog(PluginBase):
    name = "Upload User's Coordinates Systems"
    version = "1.0.0"

    def __init__(self):
        ui_path = os.path.join(os.path.dirname(__file__), 'crs_uploader_base.ui')
        super(MainDialog, self).__init__(ui_path)

        self.dlg.Open1_pushButton.clicked.connect(lambda: open_dir(ui=self.dlg,
                                                                   line_edit=self.dlg.lineEdit_1))
        self.dlg.Open2_pushButton.clicked.connect(lambda: open_file(ui=self.dlg,
                                                                    line_edit=self.dlg.lineEdit_2,
                                                                    extensions="Txt file with proj4 strings (*.txt)"))
        self.dlg.checkBox_1.stateChanged.connect(
            lambda: self.dlg.lineEdit_1.setEnabled(self.dlg.checkBox_1.isChecked())
        )
        self.dlg.checkBox_2.stateChanged.connect(
            lambda: self.dlg.lineEdit_2.setEnabled(self.dlg.checkBox_2.isChecked())
        )

        self.dlg.pushButton.clicked.connect(self.run)

        try:  # geoscan stuff?
            self.dlg.lineEdit_1.setText(config.get('Paths', 'geoscan_prj_files'))
            self.dlg.lineEdit_2.setText(config.get('Paths', 'geoscan_proj4_msk_txt'))
        except NoOptionError:
            pass

    def copy_crs_files(self, src_dir):
        path = os.path.abspath(__file__)
        splited = path.split(os.sep)
        crs_dir = os.path.join(splited[0], os.sep, *splited[1:splited.index('scripts')], 'crs')
        print(crs_dir)

        os.makedirs(crs_dir, exist_ok=True)

        for f in os.listdir(src_dir):
            src = os.path.join(src_dir, f)
            dst = os.path.join(crs_dir, f)
            shutil.copy(src, dst)

    @log_method_by_crash_reporter(plugin_name=name, version=version)
    def upload(self):
        if self.dlg.checkBox_1.isChecked():
            self.copy_crs_files(src_dir=self.dlg.lineEdit_1.text())
            Metashape.app.messageBox(textwrap.fill(_("New CRS added to Agisoft Metashape!"), 65))
        if self.dlg.checkBox_2.isChecked():
            try:
                upload_crs_to_magnet(projs_source=self.dlg.lineEdit_2.text())
                Metashape.app.messageBox(textwrap.fill(_("New CRS added to Magnet Tools!"), 65))
            except FileNotFoundError:
                Metashape.app.messageBox(textwrap.fill(_("Input txt file doesn't exist or Magnet Tools is not installed"), 65))

    def log_values(self):
        magnet_file = self.dlg.lineEdit_2.text()
        if self.dlg.checkBox_2.isChecked() and os.path.exists(magnet_file) and os.path.isfile(magnet_file) \
                and os.path.splitext(magnet_file)[1] == '.txt':
            with open(magnet_file, 'r') as file:
                magnet_data = file.read()
        else:
            magnet_data = None

        d = {
            'crs_files': None if not os.path.exists(self.dlg.lineEdit_1.text()) else os.listdir(self.dlg.lineEdit_1.text()),
            'magnet_crs': magnet_data,
        }

        return d

    def run(self):
        self.safe_process(self.upload)


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    else:
        def _(s): return s
    exporter = MainDialog()
    exporter.dlg.exec_()


if __name__ == "__main__":
    main()
