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

import glob
import os
from configparser import ConfigParser


class PluginImportError(Exception):
    pass


plugins_init = os.path.join(os.path.dirname(__file__), "plugins.txt")
plugins_in_dir = set([os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.dirname(__file__)+"/*.py")])

activated_plugins = list()
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
config = ConfigParser()
config.read(config_path, encoding='utf-8')

if os.path.exists(plugins_init):
    with open(plugins_init, 'r') as f:
        for line in f.readlines():
            plugin = line.strip()

            if plugin not in plugins_in_dir:
                # raise PluginImportError("{} is not exists in installed_plugins/".format(plugin))
                continue

            activated_plugins.append(plugin)

no_to_load = set()
update_config = False
current_plugins = dict(config.items('Plugins'))

# check if user turn off some plugin by plugins_configurator
if not config.has_section('Plugins'):
    config.add_section('Plugins')

for plugin in activated_plugins:
    try:
        status = current_plugins[plugin]
        if status == "False":
            no_to_load.add(plugin)
    except KeyError:
        update_config = True
        config.set("Plugins", plugin, "True")

deprecated_plugins = set(current_plugins.keys()) - set(activated_plugins)
if deprecated_plugins:
    for plugin in list(deprecated_plugins):
        config.remove_option('Plugins', plugin)
    update_config = True

if update_config:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
    with open(path, mode='wt', encoding='utf-8') as file:
        config.write(file)


__all__ = [f for f in activated_plugins if f not in no_to_load]
