"""Script to convert OBJ models to PLY by Agisoft Metashape

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
from PySide2 import QtWidgets
import os
from shutil import copy2


class Converter:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.dir_path = os.path.dirname(path)
        self.ply_path = os.path.join(self.dir_path, 'PLY')

    def importmodel(self, storage_path):
        Metashape.app.document.chunk.importModel(storage_path,
                                                 format=Metashape.ModelFormat.ModelFormatOBJ)

    def exportmodel(self, storage_path):
        Metashape.app.document.chunk.exportModel(storage_path,
                                                 format=Metashape.ModelFormat.ModelFormatPLY)

    def get_models_from_dir(self, extension='.obj'):
        models_and_kml = []
        for address, dirs, files in os.walk(self.path):
            for file in files:
                if os.path.splitext(file)[1] == extension:
                    models_and_kml.append(os.path.join(address, file))
                if os.path.splitext(file)[1] == '.kml':
                    models_and_kml.append(os.path.join(address, file))

        return models_and_kml

    def convert(self):
        progress = QtWidgets.QProgressDialog()
        progress.setLabelText('Searching models in selected directory')
        progress.setModal(True)
        progress.show()
        Metashape.app.update()

        model_files = self.get_models_from_dir()

        progress.setLabelText('Export OBJ models to PLY')
        progress.setModal(True)
        progress.show()
        Metashape.app.update()

        for i, file in enumerate(model_files):

            if progress.wasCanceled():
                break
            progress.setValue(int(i / len(model_files) * 100))
            Metashape.app.update()

            new_dirs = os.path.dirname(os.path.relpath(file, start=self.path))
            new_file_dir_path = os.path.join(self.ply_path, new_dirs)
            if not os.path.exists(new_file_dir_path):
                os.makedirs(new_file_dir_path)

            if os.path.splitext(os.path.basename(file))[1] == '.obj':
                ply_filename = os.path.splitext(os.path.basename(file))[0] + '.ply'
                new_model_file_path = os.path.join(new_file_dir_path, ply_filename)
                if not os.path.exists(new_model_file_path):
                    print(new_model_file_path)
                    try:
                        self.importmodel(file)
                        self.exportmodel(new_model_file_path)
                    except Exception:
                        with open(os.path.join(self.dir_path, 'converter_log.txt'), 'a') as file:
                            file.write(new_model_file_path + '\n')
                else:
                    continue

            elif os.path.splitext(os.path.basename(file))[1] == '.kml':
                new_kml_file_path = os.path.join(new_file_dir_path, os.path.basename(file))
                if not os.path.exists(new_kml_file_path):
                    copy2(file, new_kml_file_path)


path = Metashape.app.getExistingDirectory('Select directory with OBJ models')
if Metashape.app.getBool('Convert existing OBJ models to PLY?'):
    converter = Converter(path)
    converter.convert()
