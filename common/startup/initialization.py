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

import logging
import re
import tempfile
import sys
import os
import gettext
from configparser import ConfigParser
from PySide2.QtCore import QSettings

from common.utils import loglevels


ps = None
try:
    import Metashape as ps
except ImportError:
    print("Couldn't find Metashape module, trying to import PhotoScan module instead")
    try:
        import PhotoScan as ps
    except ImportError as error:
        print("Couldn't find PhotoScan module either, aborting")
        raise error
if not ps:
    raise ImportError('PhotoScan module import was failed')


def init_config():
    localdir = init_versions()

    config_parser = ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.ini')

    if not os.path.isfile(config_path):
        raise FileNotFoundError('config.ini is not found')

    config_parser.read(config_path, encoding='utf-8')

    if not config_parser.has_option('Paths', 'local_app_data'):
        config_parser.set('Paths', 'local_app_data', localdir)
    if not config_parser.has_option('Paths', 'resources'):
        config_parser.set('Paths', 'resources', os.path.join(localdir, 'resources'))
    if not config_parser.has_option('Paths', 'sp_path'):
        config_parser.set('Paths', 'sp_path', os.path.join(localdir, 'site-packages-py3{}'.format(sys.version_info[1])))
    if not config_parser.has_option('Paths', 'python'):
        ms_exec = sys.executable
        python_exec = os.path.join(os.path.dirname(ms_exec), 'python', 'python.exe')
        if not os.path.exists(python_exec):
            ps.app.messageBox("Invalid path to python.exe")
            return
        config_parser.set('Paths', 'python', python_exec)

    check_python = re.search(r"py3(\d+)", os.path.basename(config_parser.get('Paths', 'sp_path')))
    if check_python and int(check_python.groups(1)[0]) != sys.version_info[1]:
        config_parser.set('Paths', 'sp_path', os.path.join(localdir, 'site-packages-py3{}'.format(sys.version_info[1])))
        os.makedirs(os.path.join(localdir, 'site-packages-py3{}'.format(sys.version_info[1])))

    if not config_parser.has_section('Plugins'):
        config_parser.add_section('Plugins')

    with open(config_path, mode='wt', encoding='utf-8') as file:
        config_parser.write(file)

    return config_parser


def init_versions():
    try:
        ps_version = float('.'.join(ps.app.version.split('.')[:2]))
    except ValueError:
        ps_version = 1.5
    if ps_version >= 1.5:
        ps_dist_name = 'Metashape Pro'
    else:
        ps_dist_name = 'PhotoScan Pro'

    localdir = os.path.expanduser('~')
    if sys.platform.startswith('win32'):
        localdir = os.path.join(localdir, 'AppData', 'Local', 'Agisoft', ps_dist_name)
    elif sys.platform.startswith('linux'):
        localdir = os.path.join(localdir, '.local', 'share', 'Agisoft', ps_dist_name)
    elif sys.platform.startswith('darwin'):
        localdir = os.path.join(localdir, 'Library', 'Application Support', 'Agisoft', ps_dist_name)
    else:
        raise OSError("Couldn't detect your OS type, aborting")

    return localdir


config = init_config()
common_trans = None


def install_translation(plugin_dir_name, plugin_name):
    settings = QSettings()
    lang = settings.value('main/language')
    if lang not in ['en', 'ru']:
        lang = 'en'
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    trans = gettext.translation(plugin_name, os.path.join(root, plugin_dir_name, 'locale'), [lang])
    trans.install()
    if common_trans:
        trans.add_fallback(common_trans)
    return trans


def install_common_trans():
    return install_translation("common", "common")

try:
    common_trans = install_common_trans()
    _ = common_trans.gettext
except:
    import traceback

    traceback.print_exc()
    _ = lambda x: x


def install_logging():
    logfmt = '[%(name)s] %(levelname)s: %(message)s'
    formatter = logging.Formatter(logfmt)
    fn = os.path.join(tempfile.gettempdir(), "photoscan_plugins.log")
    fhandler = logging.FileHandler(filename=fn, mode='w')
    fhandler.setLevel(loglevels.S_DEBUG)
    fhandler.setFormatter(formatter)
    # logging.getLogger().addHandler(console)
    logger = logging.getLogger()
    logging.addLevelName(loglevels.S_DEBUG, 'S_DEBUG')
    logging.addLevelName(loglevels.S_INFO, 'S_INFO')
    logger.setLevel(loglevels.S_DEBUG)
    # if not logger.handlers:
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(loglevels.S_INFO)
    for handler in logger.handlers:
        handler.setLevel(loglevels.S_INFO + 1)
        # handler.setFormatter(formatter)
    # fhandler.setFormatter(formatter)
    logger.addHandler(fhandler)
    logger.addHandler(console)
    logging.log(loglevels.S_INFO, "Welcome. Your debug log will be in {}".format(fn))
    # import sys
    # sys.excepthook = exception_handler
    return fn


def update_sp_path():
    default_sp_path = config.get('Paths', 'sp_path')
    if not os.path.exists(default_sp_path):
        os.makedirs(default_sp_path)
    if default_sp_path not in sys.path:
        sys.path = [default_sp_path] + sys.path
    os.environ["PATH"] += os.pathsep + default_sp_path


def import_module(plugin_name, inject, subplugin=None):
    try:
        trans = install_translation(plugin_name, plugin_name)
        inject(trans)
        if not subplugin:
            print('imported ', plugin_name)
        else:
            print('imported ', subplugin)
    except:
        import traceback
        traceback.print_exc()
