"""Common scripts, classes and functions

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

import PhotoScan
import math
import os.path
import pickle
from traceback import print_exc

from .get_list_of_projects import get_list_of_projects_from_dir_or_txt


def extracting_errors_pvo(mar):

    chunk = PhotoScan.app.document.chunk
    source_geoc = chunk.crs.unproject(mar.reference.location)
    estim_geoc = chunk.transform.matrix.mulp(mar.position)
    local = chunk.crs.localframe(estim_geoc)
    error = local.mulv(estim_geoc - source_geoc)
    return error[0], error[1], error[2]


def extracting_error(camera):
    chunk = PhotoScan.app.document.chunk
    if camera.center and camera.reference.enabled:

        transform = chunk.transform.matrix * camera.transform

        sensorloc = camera.sensor.antenna.location
        if not sensorloc:
            sensorloc = PhotoScan.Vector([0, 0, 0])
        antenna_location = PhotoScan.Matrix().Diag([1, -1, -1]) * sensorloc

        translation = transform.translation()

        sensor_offset = transform.rotation() * antenna_location
        # measured values in geocentric coordinates
        location = translation + sensor_offset

        try:
            # measured values in geocentric coordinates
            sourceGeoc = chunk.crs.unproject(camera.reference.location)
        except TypeError:
            return None
        estimGeoc = location

        # local camera LSE coordinates
        local = chunk.crs.localframe(estimGeoc)
        error = tuple(local.mulv(estimGeoc - sourceGeoc))

        return error
    else:
        return None


def get_gcp_list():
    markers = PhotoScan.app.document.chunk.markers
    listGCP = [mar for mar in markers if mar.reference.enabled and mar.reference.location]
    return listGCP


def get_check_points_list():
    markers = PhotoScan.app.document.chunk.markers
    listGCP = [mar for mar in markers if not mar.reference.enabled and mar.reference.location and len(mar.projections) > 1]
    return listGCP


def extracting_all_errors(items_type='Cameras'):

    chunk = PhotoScan.app.document.chunk
    if items_type == 'Cameras':
        items = chunk.cameras
        func = extracting_error
    elif items_type == 'GCP':
        items = get_gcp_list()
        func = extracting_errors_pvo
    elif items_type == 'CheckPoints':
        items = get_check_points_list()
        func = extracting_errors_pvo
    else:
        raise ValueError('Unsupported reference items type!')

    lst = []
    for i in items:
        result = func(i)
        if result:
            dx, dy, dh = result
            dAll = math.sqrt(dx*dx + dy*dy + dh*dh)
            dPlan = math.sqrt(dx*dx + dy*dy)
        else:
            continue
        lst.append([i, dx, dy, dh, dPlan, dAll])

    return lst


def error_info(items_type='Cameras'):

    error_list = extracting_all_errors(items_type)
    if not error_list:
        return [None, None, None, None, None]

    sumdX = 0
    sumdY = 0
    sumdH = 0

    for i in error_list:
        sumdX += i[1]
        sumdY += i[2]
        sumdH += i[3]

    q = len(error_list)

    sumVarX = 0
    sumVarY = 0
    sumVarH = 0

    for i in error_list:
        sumVarX += (i[1])**2
        sumVarY += (i[2])**2
        sumVarH += (i[3])**2

    totalX = math.sqrt(sumVarX/q)
    totalY = math.sqrt(sumVarY/q)
    totalH = math.sqrt(sumVarH/q)
    totalPlane = math.sqrt(totalX*totalX + totalY*totalY)
    totalSpatial = math.sqrt(totalX*totalX + totalY*totalY + totalH*totalH)

    print('Total ', totalX, totalY, totalH)
    print('Total Spatial', totalSpatial)
    print('Total Plane', totalPlane)
    print('Quantity', q)
    return [totalX, totalY, totalH, totalPlane, totalSpatial]


def make_errors_info_dict(listOfPaths, outpath, allChunks=True, txt=True):

    projects_info_dict = {}

    for path in listOfPaths:
        normpath = os.path.abspath(path)
        try:
            PhotoScan.app.document.open(normpath)
            chunk_dict = {}
            if allChunks:
                chunks_list = PhotoScan.app.document.chunks
            else:
                chunks_list = [PhotoScan.app.document.chunk]
            for ch in chunks_list:
                chunk = ch
                PhotoScan.app.document.chunk = chunk
                chunk_dict[chunk.label] = errorsInfoDict()
            projects_info_dict[normpath] = chunk_dict
        except Exception:
            print('Exception was handled!\n%s' % print_exc())

    outpath = os.path.abspath(outpath)
    name, ext = os.path.splitext(outpath)
    if ext.lower() not in ('.pd', '.txt'):
        name = outpath
    dumppath = name + '.pd'
    with open(dumppath, 'wb') as f:
        pickle.dump(projects_info_dict, f)
    if txt:
        txtpath = name + '.txt'
        text = projects_info_dict_to_text(projects_info_dict)
        with open(txtpath, 'w') as f:
            f.write(text)

    return projects_info_dict


def projects_info_dict_to_text(projectsInfoDict):

    out = 'Project\tPath\tChunk\tQuantity\t\t\tCameras\t\t\t\t\tGCP\t\t\t\t\tCheckPoints' \
          '\t\t\t\t\t\n\t\t\tCameras\tGCP\tCheckPoints\tdx\tdy\tdh\tPlane\tSpatial\tdx\t' \
          'dy\tdh\tPlane\tSpatial\tdx\tdy\tdh\tPlane\tSpatial\t\n'

    for path, chunk_dict in projectsInfoDict.items():
        proj_name = os.path.basename(path)
        for chunk, errors in chunk_dict.items():
            row = '\t'.join([proj_name, path, chunk, ''])
            allList = errors['Cameras']['errors'] + errors['GCP']['errors'] + errors['CheckPoints']['errors']
            row += '%s\t%s\t%s\t' % (
                errors['Cameras']['quantity'],
                errors['GCP']['quantity'],
                errors['CheckPoints']['quantity']
            )
            row += '\t'.join([str(i) for i in allList]) + '\n'
            out += row
    return out


def errors_from_projects_list(input_path, outpath, allChunks=True, txt=True):
    projects = get_list_of_projects_from_dir_or_txt(input_path)
    out = make_errors_info_dict(projects, outpath, allChunks, txt)
    return out


def errorsInfoDict():
    chunk = PhotoScan.app.document.chunk
    q_cameras = len(chunk.cameras)
    q_check_points = len(get_check_points_list())
    q_GCP = len(get_gcp_list())

    errorsCameras = error_info('Cameras')
    errorsCheckPoints = error_info('CheckPoints')
    errorsGCP = error_info('GCP')

    resDict = {
        'Cameras':
            {
                'errors': errorsCameras,
                'quantity': q_cameras
            },
        'GCP':
            {
                'errors': errorsGCP,
                'quantity': q_GCP
            },
        'CheckPoints':
            {
                'errors': errorsCheckPoints,
                'quantity': q_check_points
            }
    }

    return resDict


if __name__ == '__main__':
    c = PhotoScan.app.document.chunk.cameras[-1]
    print(c.label)
    print(extracting_error(c))
