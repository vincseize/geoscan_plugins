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
import os
import json
import traceback

from datetime import datetime

try:
    from .flight_info_tools.parse_filenames import parse_cam_name_string
    from .project import sensor_by_key
except SystemError:
    from flight_info_tools.parse_filenames import parse_cam_name_string
    from project import sensor_by_key


LOCATION_REF_DICT = {
    'g101': (0.33, -0.24, -0.02),
    'g201_Nadir': (0.45, -0.17, -0.04),
    'g201_Naklon-Left': (0.49, -0.18, -0.01),
    'g201_Naklon-Right': (0.37, -0.18, -0.01),
}

LOCATION_REF_PATH = r'\\taiga\data\SupplementaryData\Cameras Calibration\Offsets'
SENSOR_CALIBRATIONS_BASE_PATH = r'\\taiga\data\SupplementaryData\Cameras Calibration'


class OffsetResolveError(RuntimeError):
    pass


class OffsetFileNotFoundError(OffsetResolveError):
    pass


def parse_sensor_label(label):
    return parse_cam_name_string(label + '_')


def duplicate_sensor(oldsensor, name=None):

    chunk = PhotoScan.app.document.chunk
    sensor = chunk.addSensor()
    if name:
        sensor.label = name
    else:
        sensor.label = oldsensor.label

    sensor.type = oldsensor.type
    sensor.width = oldsensor.width
    sensor.height = oldsensor.height
    sensor.calibration = oldsensor.calibration
    sensor.fixed = oldsensor.fixed
    sensor.focal_length = oldsensor.focal_length
    sensor.pixel_height = oldsensor.pixel_height
    sensor.pixel_width = oldsensor.pixel_width
    sensor.user_calib = oldsensor.user_calib
    sensor.antenna = oldsensor.antenna

    print('Sensor created ', sensor.label)
    return sensor


def add_sensors_offset(location_ref_path=LOCATION_REF_PATH, strict_offsets_match=True):
    chunk = PhotoScan.app.document.chunk

    if chunk is None:
        raise RuntimeError("No chunk!")

    cameras = chunk.cameras

    # Формирует словарь {путь к директории: [лист камер]}
    cam_dict = dict()
    for i, cam in enumerate(cameras):
        cam_path = os.path.normpath(cam.photo.path)
        lst = os.path.split(cam_path)
        cam_dir = lst[0]

        photos_list = cam_dict.get(cam_dir, [])
        photos_list.append(i)
        cam_dict[cam_dir] = photos_list

    # создает словарь сенсоров {путь к директории: сенсор}
    # дублирует сенсоры
    sensors_dict = dict()
    for d in cam_dict:
        oldsensor = cameras[cam_dict[d][0]].sensor
        sensor = duplicate_sensor(oldsensor)
        sensors_dict[d] = sensor

    # Присваивает камерам сенсор и добавляет оффсет
    sensors_without_offset = set()
    for d in cam_dict:
        sensor = sensors_dict[d]
        photos_list = cam_dict[d]
        label = cameras[photos_list[0]].label
        sensor.label = '_'.join(label.split('_')[:-1])

        try:
            location_reference, rotation_reference = get_offset_reference(
                sensor.label,
                location_ref_path=location_ref_path,
                strict_offsets_match=strict_offsets_match
            )
        except OffsetResolveError:
            traceback.print_exc()
            sensors_without_offset.add(sensor)
        else:
            sensor.antenna.location_ref = PhotoScan.Vector(location_reference)
            sensor.antenna.rotation_ref = PhotoScan.Vector(rotation_reference)

        for cam_key in photos_list:
            camera = cameras[cam_key]
            camera.sensor = sensor

    return sensors_without_offset


def get_offset_reference(label, location_ref_path=LOCATION_REF_PATH, strict_offsets_match=True):
    ref_dict = get_offset_dict(label, location_ref_path=location_ref_path)

    if ref_dict:
        if "values" in ref_dict:
            ref_dict = ref_dict["values"]
        location = (ref_dict['x'], ref_dict['y'], ref_dict['z'])
        rotation = (ref_dict['yaw'], ref_dict['pitch'], ref_dict['roll'])
    elif not strict_offsets_match:
        location = __get_default_offset_location(label)
        rotation = __get_default_offset_rotation(label)
    else:
        raise OffsetResolveError('Cannot find offset reference for sensor: "{}"!'.format(label))

    return location, rotation


def __get_default_offset_location(cam_label):
    cam_label = cam_label.lower()

    if 'g101' in cam_label:
        location_ref = LOCATION_REF_DICT['g101']
    elif 'g201' in cam_label:
        if 'left' in cam_label:
            location_ref = LOCATION_REF_DICT['g201_Naklon-Left']
        elif 'right' in cam_label:
            location_ref = LOCATION_REF_DICT['g201_Naklon-Right']
        else:
            location_ref = LOCATION_REF_DICT['g201_Nadir']
    else:
        raise OffsetResolveError('Unknown antenna reference. Sensor: {}'.format(cam_label))
    return PhotoScan.Vector(location_ref)


def __get_default_offset_rotation(cam_label):
    rotation_ref = PhotoScan.Vector((0, 0, 0))
    cam_label = cam_label.lower()

    if 'naklon' in cam_label:
        if 'right' in cam_label:
            rotation_ref[2] = +15
        elif 'left' in cam_label:
            rotation_ref[2] = -15
        elif 'forward' in cam_label:
            rotation_ref[1] = -15
        else:
            rotation_ref[2] = -20

    return rotation_ref


def get_offset_dict(label, location_ref_path=LOCATION_REF_PATH):
    day, fltype, bort, flnum = parse_sensor_label(label)

    if not fltype or not bort:
        print('Parsing of camera "%s" failed!' % label)
        return
    if fltype == '2000' or fltype == 'Nadir-2000':
        fltype = 'Nadir'

    filename = '_'.join([bort, fltype, 'offset']) + '.json'
    filepath = os.path.join(location_ref_path, filename)

    try:
        with open(filepath) as f:
            loc_dict = json.loads(f.read())
    except FileNotFoundError:
        message = 'Cannot find offset reference file for sensor: "{}"!\nPath: "{}"'.format(label, filepath)
        raise OffsetFileNotFoundError(message)
    return loc_dict


def get_cameras_dict():
    # Формирует словарь {сенсор.key: [лист камер]}
    chunk = PhotoScan.app.document.chunk
    cameras = chunk.cameras
    cam_dict = dict()
    for i, cam in enumerate(cameras):
        cam_dict.setdefault(cam.sensor.key, []).append(cam)
    return cam_dict


def __sensor_by_key(key):
    try:
        return sensor_by_key(key)
    except RuntimeError:
        print("Can't find sensor!")


def remove_empty_sensors():
    chunk = PhotoScan.app.document.chunk
    sensors = chunk.sensors

    sensors_keys = set([i.key for i in sensors])
    cam_dict = get_cameras_dict()
    empty_sensors = sensors_keys - set(cam_dict.keys())
    empty_sensors = [__sensor_by_key(i) for i in empty_sensors]
    if empty_sensors:
        chunk.remove(empty_sensors)
        print('Removed sensors:')
        for i in empty_sensors:
            print(i)
    else:
        print('There are no empty sensors!')


def add_sensor_calibration(auto=True):
    if auto:
        for sens in PhotoScan.app.document.chunk.sensors:
            sens.user_calib = None
        return

    cam_dict = get_cameras_dict()
    for sens_id, camlist in cam_dict.items():

        label = camlist[0].label
        parsed_cam = parse_cam_name_string(label)
        day, fltype, bort, flnum = parsed_cam

        cal_path = os.path.join(SENSOR_CALIBRATIONS_BASE_PATH, '_'.join([bort, fltype, 'calibration.xml']))
        print(cal_path, os.path.isfile(cal_path))
        sensor = __sensor_by_key(sens_id)
        if os.path.isfile(cal_path):
            c = PhotoScan.Calibration()
            c.load(cal_path)
            sensor.user_calib = c
        else:
            message = "Can't find calibration file!\n"
            print(message)
            sensor.user_calib = None


def create_offset_file(path, x, y, z, yaw, pitch, roll, trusted=False):
    """
    Creates JSON offset file
    :param path: str
    :param x: float
    :param y: float
    :param z: float
    :param yaw: float
    :param pitch: float
    :param roll: float
    :param trusted: bool
    :return:
    """
    values = {
        "x": x,
        "y": y,
        "z": z,
        "yaw": yaw,
        "pitch": pitch,
        "roll": roll
    }
    user = os.getlogin()
    date = datetime.now().isoformat(' ')
    d = {
        "created": {
            "user": user,
            "date": date,
            "trusted": trusted
        },
        "values": values
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(d, f, sort_keys=True, indent=4)
