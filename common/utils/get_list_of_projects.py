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


def get_list_of_projects_from_txt(txt_path):
    with open(txt_path, encoding='utf-8') as f:
        paths = f.read().strip().split('\n')
    return _clean_list(paths)


def get_list_of_projects_from_dir(dir_path):
    paths = [os.path.join(dir_path, i) for i in os.listdir(dir_path)]
    return _clean_list(paths)


def get_list_of_projects_from_dir_or_txt(path):
    if os.path.isfile(path):
        return get_list_of_projects_from_txt(path)
    elif os.path.isdir(path):
        return get_list_of_projects_from_dir(path)
    else:
        raise OSError('Path is not a file or directory!\n%s' % path)


def _clean_list(lst):
    lst = [os.path.abspath(i) for i in lst]
    lst = filter(lambda x: (os.path.isfile(x) and os.path.splitext(x.lower())[1] == '.psx'), lst)
    lst = sorted(set(lst))
    return lst


if __name__ == '__main__':
    ppath = r'\\storage-nas-6\data3\GP01_Tulskaya_region\2017_03_Tulskaya_Suvorovskiy\PS_processing'
    for p in sorted(get_list_of_projects_from_dir_or_txt(ppath)):
        print(p)
