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

import re
from osgeo import osr


def fix_mapinfo_ref(ref: osr.SpatialReference):
    """
    Fix bug in gdal v3.1 with incorrect scale coefficient in helmert transformation parameters.
    Details: https://redmine.corp.geoscan.aero/issues/41996#change-255926
    """
    mapinfo_ref = ref.ExportToMICoordSys()
    proj4_ref = ref.ExportToProj4()
    if re.search(r"Earth Projection \d+, 9999", mapinfo_ref):
        towgs84 = re.search(r"towgs84=(.+),(.+),(.+),(.+),(.+),(.+),(.+?)($|\s)", proj4_ref)
        try:
            dx, dy, dz, rx, ry, rz, k = list(map(float, [towgs84.group(i) for i in range(1, 8)]))
        except Exception:
            return mapinfo_ref

        search_params = re.search(r"Earth Projection (.+)", mapinfo_ref)
        if search_params:
            params = search_params.group(1)
            values = [x.strip() for x in params.split(',')]
            for i, param in zip(range(3, 10), [dx, dy, dz, -rx, -ry, -rz, k]):
                values[i] = str(param)
            return "CoordSys Earth Projection " + ', '.join(values)
        else:
            return mapinfo_ref


if __name__ == "__main__":
    pass
