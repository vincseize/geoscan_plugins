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


# Allowed names in main flight directory
ALLOWED_NAMES = {
    u'GCS',
    u'GNSS_log',
}


# Allowed images extensions
ALLOWED_IMAGES_EXTENSIONS = {
    u'.jpg',
    u'.jpeg',
    u'.arw',
    u'.png',
}


# Match camera type from image with flight type in main flight directory name
# "2017_09_18_Naklon-Left_g201b20184_f003_003.JPG" --> camera type == "Naklon-Left"
# "G20184_F003_B06_Naklon_029" --> flight type == "Naklon"
# There is no mistake!
MATCH_PHOTOS_FLTYPE = {
    u'Nadir': {u'Nadir', u'Nadir-Naklon'},
    u'Nadir-2000': {u'Nadir-2000'},
    u'Naklon': {u'Naklon'},
    u'2000': {u'2000'},
    u'Naklon-Right': {u'Naklon'},
    u'Naklon-Left': {u'Naklon', u'Nadir-Naklon'},
    u'Naklon-Forward': {u'Nadir-Naklon'},
    u'Variable': {u'Variable'},
    u'Vis': {u'Vis-Mult', u'Vis-TeplV'},
    u'Mult': {u'Vis-Mult'},
    u'TeplV': {u'Vis-TeplV'},
}


# Match camera type from image with default camera name. Which often is persisted in events directory (by mistake)
# "2017_09_18_Naklon-Left_g201b20184_f003_003.JPG" --> camera type == "Naklon-Left"
# It matches "PhotoLeft"
MATCH_EVENTS_FLTYPE = {
    u'Nadir': u'PhotoCamera',
    u'Nadir-2000': u'PhotoCamera',
    u'Naklon': u'PhotoCamera',
    u'2000': u'PhotoCamera',
    u'Naklon-Right': u'PhotoRight',
    u'Naklon-Left': u'PhotoLeft',
    u'Nadir-Right': u'PhotoRight',
    u'Nadir-Left': u'PhotoLeft'
}

# Match camera type from image directory with camera type in image names
# "Photo-L"  --> camera type == "Naklon-Left"
# "2017_09_18_Naklon-Left_g201b20184_f003_003.JPG" --> camera type == "Naklon-Left"
# There is no mistake!
MATCH_FLTYPE_BY_PHOTODIR = {
    u'Photo-L': u'Naklon-Left',
    u'Photo-R': u'Naklon-Right',
    u'Photo-N': u'Nadir',
    u'Photo-F': u'Naklon-Forward',
    u'Photo-Vis': u'Vis',
    u'Photo-Mult': u'Mult',
    u'Photo-TeplV': u'TeplV',
    u'Photo': None
}

# Allowed flight types in main flight directory name
DIR_FLTYPES = []
for __v in MATCH_PHOTOS_FLTYPE.values():
    DIR_FLTYPES.extend(__v)
DIR_FLTYPES = set(DIR_FLTYPES)

# Allowed names for images directory
PHOTO_DIRS = set(MATCH_FLTYPE_BY_PHOTODIR.keys())
