"""Export/Import model by marker plugin for Agisoft Metashape

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

import re
import Metashape
from PySide2 import QtWidgets

from common.loggers.email_logger import log_method_by_crash_reporter
from common.utils.ui import show_info
from .ExportImportModelGui import Ui_Dialog


class ExportApp(QtWidgets.QDialog, Ui_Dialog):

    NAME = "Export\Import model by marker"
    VERSION = "1.0.1"

    def __init__(self, doc):
        """
        Init methods.
        """
        super().__init__()
        self.doc = doc
        self.ui = Ui_Dialog()
        self.setupUi(self)
        self.markers()
        self.meshes()
        self.ExportButton.clicked.connect(self.exportmodel)
        self.ImportButton.clicked.connect(self.importmodel)
        self.BrowseButtonExport.clicked.connect(self.browse_to_export)
        self.BrowseButtonImport.clicked.connect(self.browse_to_import)
        self.MarkersList.setCurrentRow(0)
        self.MeshList.setCurrentRow(0)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def browse_to_export(self):
        """
        Actions for export Browse button
        :return:
        """
        directory = QtWidgets.QFileDialog.getSaveFileName(self, _("Create model to export"),
                                                          filter="OBJ (*.obj);;COLLADA (*.dae)")
        self.lineEdit_Export.setText(directory[0])

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def browse_to_import(self):
        """
        Actions for import Browse button
        :return:
        """
        directory = QtWidgets.QFileDialog.getOpenFileName(self, _("Choose model to import"),
                                                          filter="OBJ (*.obj);;COLLADA (*.dae)")
        self.lineEdit_Import.setText(directory[0])

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def exportmodel(self):
        """
        Actions for Export button (action to export selected model).
        :return:
        """
        if self.lineEdit_Export.text()[-3:] == 'obj':
            format = Metashape.ModelFormat.ModelFormatOBJ
        elif self.lineEdit_Export.text()[-3:] == 'dae':
            format = Metashape.ModelFormat.ModelFormatCOLLADA
        elif self.lineEdit_Export.text() == '':
            show_info("Info", 'Set export path')
            return
        else:
            show_info("Info", 'Model format is not supported')
            return

        if self.MeshList.currentRow() != -1:
            self.doc.chunk.model = self.doc.chunk.models[self.MeshList.currentRow()]
        else:
            show_info("Info", "No model has been selected.")
            return

        self.doc.chunk.exportModel(self.lineEdit_Export.text(),
                                   format=format,
                                   crs=self.doc.chunk.crs,
                                   shift=self.shift())
        self.lineEdit_Import.setText(self.lineEdit_Export.text())

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def importmodel(self):
        """
        Actions for Import button (action to import selected model).
        :return:
        """
        if self.lineEdit_Import.text()[-3:] == 'obj':
            format = Metashape.ModelFormat.ModelFormatOBJ
        elif self.lineEdit_Import.text()[-3:] == 'dae':
            format = Metashape.ModelFormat.ModelFormatCOLLADA
        elif self.lineEdit_Export.text() == '':
            show_info("Info", 'Set import path')
            return
        else:
            show_info("Info", 'Model format is not supported')
            return

        self.doc.chunk.importModel(self.lineEdit_Import.text(),
                                   format=format,
                                   crs=self.doc.chunk.crs,
                                   shift=self.shift())

    def shift(self):
        """
        Get shift to export/import by marker coordinates.
        Marker coordinates in chunk crs.
        :return:
        """
        marker = self.doc.chunk.markers[self.MarkersList.currentRow()]
        v = marker.position
        T = self.doc.chunk.transform.matrix
        v_t = T.mulp(v)
        v_out = self.doc.chunk.crs.project(v_t)

        return v_out

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def markers(self):
        """
        Get all names of markers and show them in GUI.
        :return:
        """
        markers = self.doc.chunk.markers
        if markers:
            for marker in markers:
                if marker.label != '':
                    self.MarkersList.addItem(marker.label)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def meshes(self):
        """
        Get all names and info of mesh models and show them in GUI.
         :return:
        """
        models = self.doc.chunk.models
        if models:
            for model in models:
                self.MeshList.addItem('Model ' + str(model.key) +
                                      ' [' +
                                      re.search(r".\'(.*)\'", str(model)).group(1) +
                                      ']')

    def log_values(self):
        return {}


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    doc = Metashape.app.document
    window = ExportApp(doc)
    window.exec_()


if __name__ == '__main__':
    main()
