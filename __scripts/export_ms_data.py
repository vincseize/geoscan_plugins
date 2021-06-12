"""Script to export Metashape data for Photomod project

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
from PySide2 import QtWidgets
import Metashape


def get_projects_from_dir(path):
    projects = []

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d[-6:] != '.files']
        for file in files:
            if os.path.splitext(file)[1] == '.psx':
                projects.append(os.path.join(root, file))

    return projects


def export_undistort_photos(savepath, psx_path):
    doc = Metashape.app.document
    doc.open(psx_path)

    psx_name = os.path.split(psx_path)[1][:-4]

    for chunk in doc.chunks:
        try:
            if chunk.enabled:
                undistort_dir = os.path.join(os.path.join(os.path.join(savepath, psx_name), chunk.label),
                                             'undistort_images')
                os.makedirs(undistort_dir)

                chunk.exportCameras(path=os.path.join(os.path.split(undistort_dir)[0], chunk.label + '_evo.txt'),
                                    format=Metashape.CamerasFormat.CamerasFormatOPK,
                                    projection=chunk.crs)
                for camera in chunk.cameras:
                    calibration = camera.sensor.calibration
                    imgu = camera.image().undistort(calibration, True, True)
                    imgu.save(os.path.join(undistort_dir, camera.label))

        except Exception as e:
            print(e)
            print('errors in {} / {}'.format(psx_path, chunk.label))


def undistort_task(chunk, path):
    task = Metashape.Tasks.UndistortPhotos()
    task.path = path
    task.apply(chunk)


def __export_undistort_photos(savepath, psx_path):
    doc = Metashape.app.document
    doc.open(psx_path)

    psx_name = os.path.split(psx_path)[1][:-4]

    for chunk in doc.chunks:
        undistort_dir = os.path.join(os.path.join(os.path.join(savepath, psx_name), chunk.label))
        os.makedirs(undistort_dir)

        chunk.exportCameras(path=os.path.join(undistort_dir, chunk.label + '_evo.txt'),
                            format=Metashape.CamerasFormat.CamerasFormatOPK,
                            projection=chunk.crs)
        undistort_task(chunk, os.path.join(undistort_dir, 'undistort_images'))


def main():
    path = r'.\photomod_data'
    projects = get_projects_from_dir(r'.\ps_processing')

    progress = QtWidgets.QProgressDialog()
    progress.setModal(True)
    progress.show()
    Metashape.app.update()
    i = 0

    for project in projects:

        progress.setLabelText("Work with {}".format(os.path.split(project)[1]))
        if progress.wasCanceled():
            break
        progress.setValue(i / len(projects) * 100)
        Metashape.app.update()

        export_undistort_photos(path,
                                project)

        i += 1


if __name__ == '__main__':
    pass
