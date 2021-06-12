"""Utilities to load plugins to Agisoft Metashape

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

from functools import partial
from common.startup.initialization import ps, import_module
from installed_plugins.utils.utils import init_top_menu


TOP_MENU = init_top_menu()


def inject(trans):
    from quality_estimator.estimate_quality import main
    ps.app.addMenuItem(_(TOP_MENU) + "/" + _("Cameras") + "/" + _("Estimate images quality"), partial(main, trans))


import_module("quality_estimator", inject)
