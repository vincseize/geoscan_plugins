"""Magnet Merger

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
import re

try:
    from .MagnetParser import TopconXMLFile
    from .flight_info_tools.ReferenceFile import NavRefFile, CamReference
    from .flight_info_tools.parse_filenames import parse_cam_name_string
except (ImportError, SystemError):
    from MagnetParser import TopconXMLFile
    from flight_info_tools.ReferenceFile import NavRefFile, CamReference
    from flight_info_tools.parse_filenames import parse_cam_name_string

from datetime import datetime, timedelta


class Merger:
    """
    Provides file merging. NAV file and Topcon XML file from MAGNET Tools
    """
    class TimeMatchingError(Exception):
        """
        Represents matching error
        """
        pass

    gnss = None  # parsed Topcon XML file
    ref_file = None  # reference file. Based on parsed NAV file
    __current_gnss_id = 0

    def __init__(self, gnss_file=None, nav_file=None):
        self.gnss_path = gnss_file
        self.nav_path = nav_file

    def __load_files(self):
        """
        Loads and parses GNSS XML file and NAV file
        :return: None
        """
        if not self.gnss:
            self.gnss = TopconXMLFile(self.gnss_path)
        self.ref_file = NavRefFile.from_file(self.nav_path)
        self.__current_gnss_id = 0

    def __match_points_by_time(self, cam_ref):
        """
        Finds match of GNSS point and NAV point and replaces coordinate values from NAV to GNSS.
        Matches by time difference. Accuracy 0.001 sec
        :param cam_ref:
        :raises self.TimeMatchingError if there is no close GNSS point
        :return: None
        """
        if cam_ref.mark is not None:
            for i, point in enumerate(self.gnss.points[self.__current_gnss_id:]):
                if abs(point.time_mark - cam_ref.mark) < timedelta(milliseconds=1):
                    cam_ref.mark = point.time_mark
                    cam_ref.x = point.easting
                    cam_ref.y = point.northing
                    cam_ref.alt = point.height
                    stddev = point.stddev
                    cam_ref.sd_x = stddev.easting
                    cam_ref.sd_y = stddev.northing
                    cam_ref.sd_alt = stddev.up

                    self.__current_gnss_id += i + 1
                    return

        raise self.TimeMatchingError('Cannot find match for camera "{}"'.format(cam_ref.__repr__()))

    def merge(self):
        """
        Provides merging based on time difference
        :return: None
        """
        self.__load_files()
        dst_list = []

        for cam_ref in self.ref_file.cam_list:
            try:
                self.__match_points_by_time(cam_ref)
            except self.TimeMatchingError:
                cam_ref = CamReference(name=cam_ref.name)
            dst_list.append(cam_ref)

        heading = '# This file was created at {}, by {}.\n# User: {}.'.format(
            datetime.now().isoformat(' '),
            "MagnetMerger",
            os.getlogin()
        )
        cam_list = dst_list

        self.ref_file = NavRefFile.from_data(cam_list=cam_list, heading=heading)

    def write_tsv(self, path):
        """
        Writes reference file to tab-separated file
        :param path: result path
        :return: None
        """
        self.ref_file.dump_txt(
            path,
            lines_format='\t'.join((
                '{name}',
                '{{y:.{}f}}'.format(self.gnss.point_class.xy_repr_accuracy),
                '{{x:.{}f}}'.format(self.gnss.point_class.xy_repr_accuracy),
                '{alt:.3f}',
                '{roll:.2f}',
                '{pitch:.2f}',
                '{yaw:.2f}',
                '{sd_spatial:.3f}',
                '{sd_y:.3f}',
                '{sd_x:.3f}',
                '{sd_alt:.3f}'
            )),
            head_row='\t'.join((
                '# Name',
                'Northing',
                'Easting',
                'Height',
                'Roll',
                'Pitch',
                'Yaw',
                'SD_Spatial',
                'SD_Northing',
                'SD_Easting',
                'SD_Height'
            )),
        )

    def write_xml(self, path):
        """
        Writes reference to PhotoScan reference XML file
        :param path: result path
        :return:
        """
        self.ref_file.dump_xml(path)


def merge_magnet_file(gnss_file, nav_file, result_path):
    """
    Creates new reference tab-separated file based on NAV-file and Topcon XML file from MAGNET Tools
    :param gnss_file: path to Topcon XML file
    :param nav_file: path to NAV-file
    :param result_path: result path
    :return:
    """
    merger = Merger(gnss_file, nav_file)
    merger.merge()
    merger.write_tsv(result_path)


def __get_files_by_rule(rule, path):
    """
    Creates generator, which yields absolute path of file, which require rule function, recursively
    :param rule: rule function
    :param path: directory path
    :return: Generator
    """
    for root, dirs, files in os.walk(path):
        for f in filter(rule, files):
            yield os.path.join(root, f)


def __is_nav_photoscan_file(name):
    """
    Rule function. Returns True if filename pretty similar to NAV-file
    :param name:
    :return:
    """
    return ('photoScan' or 'telemetry' in name) and (os.path.splitext(name)[1].lower() == '.txt')


def __get_nav_files(path):
    """
    Creates generator, which yields absolute path of all NAV files in dir recursively
    :param path: directory path
    :return: Generator
    """
    return __get_files_by_rule(__is_nav_photoscan_file, path)


def __is_gnss_file(name):
    """
    Rule function. Returns True if file extension is XML and 'GNSS' not in filename
    :param name:
    :return:
    """
    return (os.path.splitext(name)[1].lower() == '.xml') and 'gnss' not in name.lower()


def __get_gnss_files(path):
    """
    Creates generator, which yields absolute path of all XML files in dir recursively
    :param path: directory path
    :return: Generator
    """
    return __get_files_by_rule(__is_gnss_file, path)


def pocket_merging(afs_dir, gnss_dir, res_dir, save_xml=True, save_tsv=True, progress=lambda _: None):
    """
    Creates new reference tab-separated files based on NAV-files from *afs_dir* and
    Topcon XML files (MAGNET Tools) from  *gnss_dir*. Result files will be to *res_dir*
    :param afs_dir: path
    :param gnss_dir: path
    :param res_dir: path
    :param save_xml: bool, write or not Agisoft XML reference file
    :param save_tsv: bool, write or not TSV reference file
    :param progress: callable progress function
    :return:
    """
    def match_gnss_with_nav(gnss):
        """
        Finds NAV files relative to GNSS XML file
        :param gnss:
        :return: set of NAV files paths
        """
        mathes = set()
        day, fltype, bort, flnum = parse_cam_name_string(os.path.basename(gnss))
        gnss_parts = {day, bort, flnum}

        for nf in nav_files:
            day, fltype, bort, flnum = parse_cam_name_string(os.path.basename(nf))
            nav_parts = {day, bort, flnum}
            if nav_parts == gnss_parts:
                mathes.add(nf)
        return mathes

    if not (save_xml or save_tsv):
        progress(100)
        return

    gnss_files = list(__get_gnss_files(gnss_dir))
    nav_files = list(__get_nav_files(afs_dir))

    try:
        os.mkdir(res_dir)
    except FileExistsError:
        pass

    total = len(gnss_files)

    for i, gnss_file in enumerate(gnss_files):
        print(gnss_file)
        matched_nav_files = match_gnss_with_nav(gnss_file)
        if not matched_nav_files:
            continue

        merger = Merger(gnss_file)

        for nav_file in matched_nav_files:
            if re.match('.*photoscan.*', os.path.basename(nav_file), flags=re.IGNORECASE):
                res_path_base = os.path.join(res_dir, re.sub('_photoscan.txt', '_GNSS', os.path.basename(nav_file),
                                                             flags=re.IGNORECASE))
            elif re.match('.*telemetry.*', os.path.basename(nav_file), flags=re.IGNORECASE):
                res_path_base = os.path.join(res_dir, re.sub('_telemetry.txt', '_GNSS', os.path.basename(nav_file),
                                                             flags=re.IGNORECASE))
            else:
                continue

            merger.nav_path = nav_file
            print(res_path_base)
            merger.merge()
            if save_tsv:
                merger.write_tsv(res_path_base + '.csv')
            if save_xml:
                merger.write_xml(res_path_base + '.xml')

        progress((i + 1) * 100 / total)


def __example():
    n_path = r'C:\Users\user\Desktop\waste\magmerg\txts'
    g_path = r'C:\Users\user\Desktop\waste\magmerg\xmls'

    r_path = os.path.join(g_path, 'test1')
    pocket_merging(n_path, g_path, r_path)


if __name__ == '__main__':
    pass
