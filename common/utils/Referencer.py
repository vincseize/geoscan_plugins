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

import os
import PhotoScan

try:
    from .sensor_tools import add_sensors_offset, remove_empty_sensors, LOCATION_REF_PATH
    from .flight_info_tools.ReferenceFile import open_unknown_reference_file, ReferenceXMLFile
except SystemError:
    from sensor_tools import add_sensors_offset, remove_empty_sensors, LOCATION_REF_PATH
    from flight_info_tools.ReferenceFile import open_unknown_reference_file, ReferenceXMLFile


class AbstractReferencer:
    """
    Abstract class for holding reference functionality
    """
    class _ReferenceProblems(set):
        """
        Represents set of unreferenced cameras
        """
        object_label = ''

        def report(self):
            """
            Creates report string
            :return: report str
            """
            count = len(self)
            if self:
                message = '{} are:\n'.format(self.object_label)
                message += '\n'.join(map(lambda x: x.label, sorted(self)[:5]))
                if count > 5:
                    message += '\n...'
                message += '\nCount = {}'.format(count)
            else:
                message = 'There are no {}. Congrats!'.format(self.object_label.lower())
            return message

    class UnreferencedSensors(_ReferenceProblems):
        """
        Represents set of sensors without offset
        """
        object_label = 'Sensors without offset'

    class UnreferencedCameras(_ReferenceProblems):
        """
        Represents set of unreferenced cameras
        """
        object_label = 'Unreferenced cameras'

    def __init__(
            self, paths_to_reference,  open_reference_file_func, offsets_ref_path, files_extensions, contains=None):
        self.offsets_ref_path = offsets_ref_path
        self._files = self._get_reference_files(paths_to_reference, files_extensions, contains)
        self._open_func = open_reference_file_func

        self._reference_loaded = False
        self._ref_dict = {}

    @staticmethod
    def _get_reference_files(paths_to_reference, files_extensions, contains):
        """
        Creates generator, which yields absolute path of file with same extension performed in self.extensions
        :return: Generator
        """
        def check_rule(p):
            """
            Checks extension of file. Case insensitive.
            :param p:
            :return:
            """
            name, ext = os.path.splitext(p.lower())
            correct_ext = ext in files_extensions
            if contains:
                return correct_ext and (contains in name)
            return correct_ext

        if contains:
            contains = contains.lower()

        if not isinstance(paths_to_reference, (list, set, tuple)):
            paths_to_reference = (paths_to_reference, )

        for main_path in paths_to_reference:
            for root, dirs, files in os.walk(main_path):
                for f in filter(check_rule, files):
                    yield os.path.join(root, f)

    def _load_reference(self):
        """
        Loads reference
        """
        for path in self._files:
            print(path)
            reffile = self._open_func(path)
            ref_dict = {cam.name: cam for cam in reffile.cam_list}
            self._ref_dict.update(ref_dict)
            PhotoScan.app.update()

    def apply_offset(self):
        """
        Split cameras by flight-camera (based on dir path). Applies offset and incline of sensor. Removes sensors
        without assigned cameras
        :return: UnreferencedSensors instance — unreferenced sensors
        """
        sensors_without_offset = add_sensors_offset(self.offsets_ref_path)
        remove_empty_sensors()
        return self.UnreferencedSensors(sensors_without_offset)

    @staticmethod
    def __apply4camera(ps_cam, ref_cam, load_rotation, load_accuracy):
        """
        Applies reference to camera from matched CameraRef instance
        :param ps_cam: PhotoScan.Camera
        :param ref_cam: CameraRef instance
        :param load_rotation: bool
        :param load_accuracy: bool
        :return: bool -- success of implementation
        """
        if ref_cam.has_location:
            ps_cam.reference.location = PhotoScan.Vector((ref_cam.x, ref_cam.y, ref_cam.alt))
        else:
            return False

        if load_rotation and ref_cam.has_rotation:
            ps_cam.reference.rotation = PhotoScan.Vector((ref_cam.yaw, ref_cam.pitch, ref_cam.roll))
            ps_cam.reference.rotation_accuracy = PhotoScan.Vector([10]*3)

        if load_accuracy and ref_cam.sd_alt:
            ps_cam.reference.location_accuracy = PhotoScan.Vector((ref_cam.sd_x, ref_cam.sd_y, ref_cam.sd_alt))

        return True

    def apply(self, load_rotation=True, load_accuracy=True):
        """
        Applies reference to cameras from matched CameraRef instances
        :param load_rotation: bool
        :param load_accuracy: bool
        :return: self.UnreferencedCameras instance — unreferenced cameras
        """
        if not self._reference_loaded:
            self._load_reference()

        unreferenced = self.UnreferencedCameras()
        for ps_cam in PhotoScan.app.document.chunk.cameras:
            ref_cam = self._ref_dict.get(ps_cam.label)
            if ref_cam is not None:
                success = self.__apply4camera(ps_cam, ref_cam,  load_rotation, load_accuracy)
            else:
                success = False
            if not success:
                unreferenced.add(ps_cam)

        return unreferenced


class Referencer(AbstractReferencer):
    """
    CSV (txt) referencer
    """
    def __init__(self, paths_to_reference, offsets_ref_path=LOCATION_REF_PATH):
        super(Referencer, self).__init__(
            paths_to_reference=paths_to_reference,
            open_reference_file_func=open_unknown_reference_file,
            offsets_ref_path=offsets_ref_path,
            files_extensions={'.txt', '.csv'}
        )


class XMLReferencer(AbstractReferencer):
    """
    Agisoft XML referencer
    """
    def __init__(self, paths_to_reference, offsets_ref_path=LOCATION_REF_PATH):
        super(XMLReferencer, self).__init__(
            paths_to_reference=paths_to_reference,
            open_reference_file_func=ReferenceXMLFile.from_file,
            offsets_ref_path=offsets_ref_path,
            files_extensions={'.xml'},
            contains='GNSS'
        )


if __name__ == "__main__":
    import sys
    r = Referencer(sys.argv[1])
    # r = XMLReferencer(sys.argv[1])
    print(r.apply())
    print(r.apply_offset().report())
