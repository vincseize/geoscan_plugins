"""Tools to parse flights data

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


def get_files_by_rule(rule, path):
    """
    Creates generator, which yields absolute path of file, which require rule function, recursively
    :param rule: rule function
    :param path: directory path
    :return: Generator
    """
    for root, dirs, files in os.walk(path):
        for f in filter(rule, files):
            yield os.path.join(root, f)


def get_dirs_by_rule(rule, path):
    """
    Creates generator, which yields absolute path of directory, which require rule function, recursively
    :param rule: rule function
    :param path: directory path
    :return: Generator
    """
    dirs = [x[0] for x in os.walk(path)]
    for d in filter(rule, dirs):
        yield d


def is_nav_photoscan_file(name):
    """
    Rule function. Returns True if filename pretty similar to NAV-file
    :param name:
    :return: bool
    """
    return 'photoScan' in name and (os.path.splitext(name)[1].lower() == '.txt') or 'telemetry' in name and (os.path.splitext(name)[1].lower() == '.txt')


def is_kml_file(name):
    """
    Rule function. Returns True if filename extension is 'kml'
    :param name:
    :return: bool
    """
    return os.path.splitext(name)[1].lower() == '.kml'


def is_tif_file(name):
    """
    Rule function. Returns True if filename extension is 'tif'
    :param name:
    :return: bool
    """
    return os.path.splitext(name)[1].lower() == '.tif'


def is_ortho_dir(name):
    """
    Rule function. Returns True if dir is 'ortho'
    :param name: - path
    :return: bool
    """
    return 'ortho' in name.lower()


def is_dem_dir(name):
    """
    Rule function. Returns True if dir is 'dem'
    :param name: - path
    :return: bool
    """
    return 'dem' in name.lower()


def get_nav_files(path):
    """
    Creates generator, which yields absolute path of all NAV files in dir recursively
    :param path: directory path
    :return: Generator
    """
    return get_files_by_rule(is_nav_photoscan_file, path)
