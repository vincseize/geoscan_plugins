"""Script to initialize plugins in Agisoft Metashape

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
import webbrowser

from common.startup.initialization import ps, config

from common.startup.initialization import common_trans
from common.startup.auto_update import update_plugins


update_plugins()

try:
    from common.utils.ui import add_filter_enabled
    add_filter_enabled()
except:
    import traceback
    traceback.print_exc()

TOP_MENU = 'Plugins'


from installed_plugins import *
_ = common_trans.gettext


def about():
    webbrowser.open(url=config.get('Paths', 'help'), new=2)


ps.app.addMenuItem(_(TOP_MENU) + "/" + _("Help"), about)
