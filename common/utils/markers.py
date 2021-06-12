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

import PhotoScan as ps

from common.utils.bridge import chunk_crs_to_camera


def have_position(marker):
    return len(list(filter(None.__ne__, marker.projections.values()))) > 1


def get_selected_markers():
    return [marker for marker in ps.app.document.chunk.markers if marker.selected]


def get_any_of_selected_markers():
    try:
        return next(m for m in get_selected_markers())
    except StopIteration:
        raise NoMarkerSelected

def get_marker_by_name(name):
    try:
        return next(marker for marker in ps.app.document.chunk.markers if marker.label == name)
    except StopIteration:
        raise MarkerNameError

class MarkerNameError(Exception):
    pass

class NoMarkerSelected(Exception):
    pass


def get_marker_position_or_location(m):
    """
    in one of photoscan versions it was not automatically get position from reference.
    """
    if len(m.projections) > 1 and m.position:
        return m.position
    elif m.reference.location:
        return chunk_crs_to_camera(m.reference.location)
    else: return None