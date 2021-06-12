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


def get_path_in_chunk(end=None, fn=None):
    """
    :param end: folder
    :param fn: file
    :return: full path to folder or file in chunk folder
    """
    chunk = PhotoScan.app.document.chunk
    d = os.path.splitext(PhotoScan.app.document.path)[0] + ".files"
    fileName = os.path.join(d, str(chunk.key))
    if not os.path.isdir(fileName):
        os.makedirs(fileName)
    if end is not None:
        fileName = os.path.join(fileName, end)
        if not os.path.isdir(fileName):
            os.makedirs(fileName)
    if fn is not None:
        fileName = os.path.join(fileName, fn)
    return fileName