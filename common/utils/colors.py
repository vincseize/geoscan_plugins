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

from common.utils.ui import show_error


def hex_to_rgb(value):
    lv = len(value)
    try:
        return tuple(reversed(tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))))
    except (ValueError, IndexError):
        show_error(_("Color error"), _("Not valid color: ") + str(value))

def hex_to_bgr(value):
    lv = len(value)
    try:
        return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
    except (ValueError, IndexError):
        show_error(_("Color error"), _("Not valid color: ") + str(value))


def marker_color(marker, properties):
    """
    get color by label
    """
    wire = marker.label.split()[-1].strip("_")
    if properties.wire_colors.get(wire, None) is not None:
        color = properties.wire_colors[wire]
        color = hex_to_rgb(color[2:])
        return color
    return None