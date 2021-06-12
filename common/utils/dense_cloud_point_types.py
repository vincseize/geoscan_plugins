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

dense_cloud_point_types = {
    ("Created") : 0,
    ("Unclassified") : 1,
    ("Ground") : 2,
    ("LowVegetation") : 3,
    ("MediumVegetation") : 4,
    ("HighVegetation") : 5,
    ("Building") : 6,
    ("LowPoint") : 7,
    ("ModelKeyPoint") : 8,
    ("Water") : 9,
    ("OverlapPoints") : 12,
    ("Deleted"): 128
}