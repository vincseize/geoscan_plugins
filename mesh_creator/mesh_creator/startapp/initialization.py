"""Mesh creator for Agisoft Metashape

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

import gettext
import locale
import logging
import sys
import os
import tempfile
import threading
import time
from xml.etree import ElementTree as ET

from PySide2.QtCore import QSettings
from PySide2.QtWidgets import QMessageBox, QApplication

from ..ui import ProgressBar, show_info

initial_locale = locale.getlocale()

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

try:
    tree = ET.parse(os.path.join(localdir, 'scripts/.install4j/i4jparams.conf'))
    root = tree.getroot()
    plugin_version = root[0].attrib['applicationVersion']
except FileNotFoundError:
    plugin_version = '0.8'


def install_sp():
    default_sp_path = os.path.join(localdir, 'site-packages')
    # artifacts = os.path.join(localdir, 'artifacts')
    artifacts = os.path.join(localdir, 'scripts', 'artifacts')
    import pip
    whl_dir = 'whl' + '' if os.name == 'nt' else '_linux'
    # pip_repo_tp = os.path.join(artifacts, whl_dir, 'third-party')
    pip_repo_tp = artifacts
    app = QApplication.instance()
    win = app.activeWindow()

    with open(os.path.join(pip_repo_tp, 'requirements.txt')) as f:
        whl_list = list(l.strip() for l in f.readlines())

    installed_packages = [p.project_name for p in pip.utils.get_installed_distributions()]
    whl_list = [w for w in whl_list if w not in installed_packages]

    if len(whl_list) != 0:
        ret = QMessageBox.warning(win, _("Need to update site packages."),
                                  _("Please close other Metashape instances or click Cancel!"), QMessageBox.Ok | QMessageBox.Cancel)
        if ret == QMessageBox.Cancel:
            InstallLogging().info('Site-packages were not installed')
            show_info(_('Info'), _('3D tools was not installed.\nNeed to update from previous step.\n'
                                   'Please restart Metashape.'))
            return

        print("Installing {}".format(" ".join(whl_list)))
        ps.app.update()
        progress = ProgressBar(_("Installing site-packages"))
        for idx, whl in enumerate(whl_list):
            pip.main(['install', '--upgrade', "--target={}".format(default_sp_path), "--no-index",
                      "--find-links={}".format(pip_repo_tp), whl])
            progress.update(idx / len(whl_list) * 100)
        progress.close()

    return


def update_sp_path():
    default_sp_path = os.path.join(localdir, "site-packages")
    if not os.path.exists(default_sp_path):
        os.makedirs(default_sp_path)
    if default_sp_path not in sys.path:
        sys.path = [default_sp_path] + sys.path
    os.environ["PATH"] += os.pathsep + default_sp_path


class InstallLogging(logging.Logger):
    def __init__(self, name=__name__):
        logging.Logger.__init__(self, name)

        self.formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
        self.fn = os.path.join(tempfile.gettempdir(), "ms_3d_tools.log")

        self.setLevel(logging.INFO)
        fhandler = logging.FileHandler(filename=self.fn)
        fhandler.setFormatter(self.formatter)
        self.addHandler(fhandler)

    def start_log_session(self):
        self.log(logging.INFO, "Welcome to 3D Tools v{}.".format(plugin_version))

    def show_info_window(self):
        ps.app.addMenuItem(_("Plugins") + "/" + _("Log_file"), lambda: show_info(_('Log file'), _('Your .log file:\n{}').format(self.fn)))


translate = None


def install_translation(plugin_name):
    settings = QSettings()
    lang = settings.value('main/language')
    if lang not in ['en', 'ru']:
        lang = 'en'
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    trans = gettext.translation(plugin_name, os.path.join(root, 'locale'), [lang])
    trans.install()
    if translate:
        trans.add_fallback(translate)
    return trans


def import_module(plugin_name):
    try:
        from mesh_creator.MeshCreator import start_mesh_creator
        trans = install_translation(plugin_name)
        ps.app.addMenuItem(_("Plugins") + "/" + "/" + _("3D Tools"), lambda: start_mesh_creator(trans))
        print('imported ', '3D Tools')
    except ImportError:
        import traceback
        logger = InstallLogging()
        logger.exception('Import error')
        # traceback.print_exc()
