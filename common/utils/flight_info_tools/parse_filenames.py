#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

from __future__ import print_function, unicode_literals
import re
from .path_constants import *


def parse_cam_name_string(string):
    """
    Function get parameters of flight.
    EXAMPLE:
    u'2016_09_15_Nadir_g101b10108_f001_1266.IMG' --> (u'2016_09_15', u'Nadir', u'g101b10108', u'f001')
    :param string:
    :return: tuple
    """

    day_pattern = re.compile(r'^20[\d]{2}_[\d]{2}_[\d]{2}_')
    flnum_pattern = re.compile(r'_f[0-9]+(_|.)', re.IGNORECASE)
    bort_pattern = re.compile(r'_g((101)|(201)|(401))b[\d]{5}_')

    searchday = re.search(day_pattern, string)
    searchflnum = re.search(flnum_pattern, string)
    searchbort = re.search(bort_pattern, string)

    bort = searchbort.group()[1:-1] if searchbort else None
    day = searchday.group()[:-1] if searchday else None

    if day and bort:
        type_pattern = re.compile(r'{}_(.+)_{}'.format(day, bort))
        searchtype = re.search(type_pattern, string)
        fltype = searchtype.group(1) if searchtype else None
    else:
        fltype = None

    if not day:
        day_pattern = re.compile(r'^[\d]{6,8}_')
        searchday = re.search(day_pattern, string)
        day = searchday.group()[:-1] if searchday else None

    if fltype and fltype.endswith('_'):
        fltype = fltype[:-1]
    flnum = searchflnum.group()[1:-1] if searchflnum else None

    res = (day, fltype, bort, flnum)

    return res


def parse_afsfolder_string(string):
    """
    Function get parameters of flight.
    EXAMPLE:
    u'G10108_F01_B01-02_Nadir_289_001_290-292' --> (u'G10108', u'F01', u'B01-02', u'Nadir', u'289_001_290-292')
    :param string:
    :return: tuple
    """
    string += u'_'
    bort_pattern = re.compile(r'^(G[0-9]{5})_')
    base_pattern = re.compile(r'_B(-?[P\d]+)+_')
    type_pattern = re.compile('|'.join(['(_%s_){1}' % str(i) for i in DIR_FLTYPES]))
    flnum_pattern = re.compile(r'_F[0-9]+_')

    searchbort = re.search(bort_pattern, string)
    searchbase = re.search(base_pattern, string)
    searchflnum = re.search(flnum_pattern, string)
    searchtype = re.search(type_pattern, string)

    bort = searchbort.group()[:-1] if searchbort else None
    fltype = searchtype.group()[1:] if searchtype else None
    if fltype and fltype.endswith('_'):
        fltype = fltype[:-1]

    base = searchbase.group()[1:-1] if searchbase else None
    flnum = searchflnum.group()[1:-1] if searchflnum else None

    res = [bort, flnum, base, fltype]

    if fltype != u'2000':
        pp_pattern = re.compile(r'_(\d{1,3}[-_]?)+|(_R\d{2})')
        searchpp = re.search(pp_pattern, string)
        pp = searchpp.group()[1:] if searchpp else None
        if pp:
            if pp.endswith('_'):
                pp = pp[:-1]
            res.append(pp)
    return tuple(res)


def split_image_name(string):
    """
    Function splits image name on three-components tuple: (prefix, id, extension)
    EXAMPLE:
    2016_09_15_Nadir_g101b10108_f001_1266.IMG --> ('2016_09_15_Nadir_g101b10108_f001_', '1266', '.IMG')
    :param string:
    :return: (string, string, string)
    """
    pattern = re.compile(r'(.+_)(\d+)(\..+)')
    search = re.search(pattern, string)
    return search.group(1), search.group(2), search.group(3)


# noinspection PyTypeChecker
def _test():
    def one_test(func, inp, expectation):
        one_test.num += 1
        print('Test {}. Function name: "{}". Test is '.format(one_test.num, func.__name__), end='')
        res = func(inp)
        print('passed!' if res == expectation else 'failed!\nExpected: {}\nGot: {}'.format(expectation, res))

    one_test.num = 0

    one_test(
        parse_afsfolder_string,
        u'G10108_F01_B01-02_Nadir_289_001_290-292',
        (u'G10108', u'F01', u'B01-02', u'Nadir', u'289_001_290-292')
    )
    one_test(
        parse_afsfolder_string,
        u'G10108_F01_B01-02_Nadir_R18',
        (u'G10108', u'F01', u'B01-02', u'Nadir', u'R18')
    )
    one_test(
        parse_cam_name_string,
        u'2016_09_15_Nadir_g101b10108_f001_1266.IMG',
        (u'2016_09_15', u'Nadir', u'g101b10108', u'f001')
    )
    one_test(
        parse_cam_name_string,
        u'2017_09_15_Nadir-2000_g201b10108_f001_1266.IMG',
        (u'2017_09_15', u'Nadir-2000', u'g201b10108', u'f001')
    )
    one_test(
        split_image_name,
        u'2016_09_15_Nadir_g101b10108_f001_1266.IMG',
        (u'2016_09_15_Nadir_g101b10108_f001_', u'1266', u'.IMG')
    )
    one_test(
        split_image_name,
        u'2017_09_15_Nadir-2000_g201b10108_f001_1266.IMG',
        (u'2017_09_15_Nadir-2000_g201b10108_f001_', u'1266', u'.IMG')
    )
