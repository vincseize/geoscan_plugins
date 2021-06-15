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

import contextlib
import datetime
import logging
import json
import re
import os
import shutil
import subprocess
import tempfile
import textwrap
import traceback
import zipfile
from configparser import ConfigParser
from shutil import copy2
from urllib.parse import urlparse
import sys
from functools import reduce

from PySide2.QtWidgets import *

import Metashape
from common.loggers.email_logger import send_geoscan_plugins_error_to_devs, LoggerValues
from common.utils.ui import ProgressBar
from common.startup.initialization import config, ps, update_sp_path
from common.startup.requirements_utils import PLUGINS_DIR, create_requirements, download_prebuilt_package, \
    download_file

import locale
initial_locale = locale.getlocale()


def copytree_scripts(src, dst, ignored_patterns: (None, set) = None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    files_list = []
    dirs = [(src, dst)]
    while len(dirs) > 0:
        cur, cur_dst = dirs.pop()
        for item in os.listdir(cur):
            if item in ignored_patterns:
                continue
            s = os.path.join(cur, item)
            d = os.path.join(cur_dst, item)
            if os.path.isdir(s):
                if not os.path.exists(d):
                    os.makedirs(d)
                dirs.append((s, d))
            else:
                files_list.append((s, d))

    progress = ProgressBar(_("Updating scripts"))
    cnt = 0
    for source, destination in files_list:
        try:
            copy2(source, destination)
        except PermissionError:
            print("Permission error: ", destination)
        cnt += 1
        progress.update(cnt / len(files_list) * 100)


def update_build_from_git(repo, latest_version):
    try:
        import requests
    except ImportError:
        import subprocess
        default_sp_path = config.get('Paths', 'sp_path')
        python = config.get('Paths', 'python')
        subprocess.run([python, '-m', 'pip', 'install', '--upgrade', "--target={}".format(default_sp_path), 'requests'])
        import requests

    source_code_url = repo[:-4] + "/archive/refs/tags/build{}.zip".format(latest_version)
    source_code_zip = download_file(url=source_code_url, name="build{}.zip".format(latest_version))
    with zipfile.ZipFile(source_code_zip, 'r') as source:
        main_dir = source.infolist()[0]
        source.extractall(path=os.path.dirname(source_code_zip))

    source_dir = os.path.join(os.path.dirname(source_code_zip), main_dir.filename)
    target_dir = os.path.join(config.get('Paths', 'local_app_data'), 'scripts')
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    copytree_scripts(source_dir, target_dir, ignored_patterns={'.git'})

    try:
        os.remove(source_code_zip)
        shutil.rmtree(source_dir)
    except PermissionError:
        pass


def update_plugins_from_git(repo, update_submodules=False):
    """Not used in geoscan plugins"""
    try:
        import git
    except ImportError:
        import subprocess
        default_sp_path = config.get('Paths', 'sp_path')
        python = config.get('Paths', 'python')
        subprocess.run([python, '-m', 'pip', 'install', '--upgrade', "--target={}".format(default_sp_path),
                        'GitPython==3.1.17'])
        import git

    temp = os.path.join(tempfile.gettempdir(),
                        'git_plugins_{}'.format(datetime.datetime.now().strftime("%Y_%m_%d_%H-%M-%S")))
    os.makedirs(temp)
    git.Git(temp).clone(repo)
    if update_submodules:
        raise NotImplementedError

    plugins_temp = os.path.join(temp, os.listdir(temp)[0])

    plugins_user = os.path.join(config.get('Paths', 'local_app_data'), 'scripts')
    copytree_scripts(plugins_temp, plugins_user, ignored_patterns={'.git'})

    for item in os.listdir(temp):
        path = os.path.join(temp, item)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            if os.path.isfile(path):
                os.remove(path)
        except PermissionError:
            continue


def get_remote_version():
    try:
        import requests
    except ImportError:
        import subprocess
        default_sp_path = config.get('Paths', 'sp_path')
        python = config.get('Paths', 'python')
        subprocess.run([python, '-m', 'pip', 'install', '--upgrade', "--target={}".format(default_sp_path),
                        'requests==2.25.1'])
        import requests

    version = None
    artifacts = config.get('Paths', 'artifacts')
    if artifacts.endswith('.git'):
        parsed_git = urlparse(artifacts)
        if 'gitlab' in artifacts:
            version_path_master = 'https://' + parsed_git.scheme + parsed_git.path[:-4] + '/-/raw/master/version'
            version_path_main = 'https://' + parsed_git.scheme + parsed_git.path[:-4] + '/-/raw/main/version'
        elif 'github.com' in artifacts:
            version_path_master = "https://raw.githubusercontent.com" + parsed_git.path[:-4] + '/master/' + 'version'
            version_path_main = "https://raw.githubusercontent.com" + parsed_git.path[:-4] + '/main/' + 'version'
        else:
            raise NotImplementedError
        for url in [version_path_master, version_path_main]:
            try:
                r = requests.get(url)
            except requests.exceptions.ConnectionError:
                return None
            if r.status_code == 404:
                continue
            version = int(re.search(r'_(\d+)', r.text)[1])
    else:
        # scripts data collected in local storage
        version_path = os.path.join(artifacts, 'version')
        try:
            with open(version_path, 'r') as file:
                text = file.read()
            version = int(re.search(r'_(\d+)', text)[1])
        except FileNotFoundError:
            pass

    return version


def get_local_version():
    scripts = os.path.join(config.get('Paths', 'local_app_data'), 'scripts')
    local_version = os.path.join(scripts, 'version')
    if not os.path.exists(local_version):
        return None
    with open(local_version, 'r') as file:
        text = file.read()
    version = int(re.search(r'_(\d+)', text)[1])
    return version


def is_requirements():
    r = os.path.join(config.get("Paths", "local_app_data"), 'scripts', 'requirements.txt')
    return os.path.exists(r)


def show_warning_yes_cancel(title, message):
    app = QApplication.instance()
    win = app.activeWindow()
    return QMessageBox.warning(win, title, message, QMessageBox.Ok | QMessageBox.Cancel)


def update_plugins():
    update_sp_path()
    if config.get('Options', 'auto_update') == 'True':
        try:
            remote_version = get_remote_version()
            current_version = get_local_version()
            if remote_version is not None and (current_version is None or current_version < remote_version):
                title = _('Agisoft Metashape plugins')
                message = _('Do you want to update plugins?')
                app = QApplication.instance()
                win = app.activeWindow()
                ret = QMessageBox.warning(win, title, message, QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.No:
                    return

                artifacts = config.get('Paths', 'artifacts')
                if artifacts.endswith('.git'):
                    update_build_from_git(repo=artifacts, latest_version=remote_version)
                else:
                    dst = os.path.join(config.get('Paths', 'local_app_data'), 'scripts')
                    copytree_scripts(artifacts, dst, ignored_patterns={'.git'})

                check_and_install_sitepackages(online=True)
                update_resources()
                update_config()
                if remote_version in [568]:  # temporary
                    Metashape.app.messageBox(textwrap.fill(_('Please, re-run Agisoft Metashape to apply updates'), 65))

            if not is_requirements():
                check_and_install_sitepackages(online=True)
                update_resources()

        except Exception:
            print("Auto update is not available :(")
            sec, opt = 'Options', 'report_about_errors'
            if config.has_option(sec, opt) and config.get(sec, opt) == 'True':
                values = LoggerValues(input={}, plugin_name='main')
                send_geoscan_plugins_error_to_devs(error=traceback.format_exc(), values=values)

    check_and_install_sitepackages(online=False)


def update_config():
    new_config = ConfigParser()
    new_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.ini')
    new_config.read(new_config_path, encoding='utf-8')

    blocked_sections, config_blocked = ['Options', 'Plugins'], dict()
    for section in blocked_sections:
        if not config.has_section(section):
            continue
        for option, status in config.items(section):
            if section not in config_blocked:
                config_blocked[section] = {option: status}
            else:
                config_blocked[section][option] = status

    for section, data in config_blocked.items():
        for option, status in data.items():
            if config.has_option(section, option):
                new_config.set(section, option, status)

    with open(new_config_path, mode='wt', encoding='utf-8') as file:
        new_config.write(file)


def check_and_install_sitepackages(online: bool):
    create_requirements()

    default_sp_path = config.get('Paths', 'sp_path')
    pip_repo_offline = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'local_repo')

    update_site_packages_window = True
    for pip_repo, status in [(PLUGINS_DIR, 'online'), (pip_repo_offline, 'offline')]:
        if (online and status == 'offline') or (not online and status == 'online'):
            continue

        try:
            installed, needed_packages, outdated, requirements = check_pip_repo(pip_repo)
        except FileNotFoundError:
            continue

        if not needed_packages.issubset(installed) or outdated:
            if update_site_packages_window:
                update_site_packages_window = False
                ret = show_warning_yes_cancel(_("Python packages update is required (Internet connection is required)."),
                                              _("Please, close all other Agisoft Metashape applications or click Cancel."))
                if ret == QMessageBox.Cancel:
                    return

            clean_old_packages(outdated)
            needed_packages.difference_update(installed)
            needed_packages = needed_packages.union(outdated)

            if status == 'online':
                with open(os.path.join(PLUGINS_DIR, 'prebuilt_requirements.json'), 'r') as file:
                    prebuilt_packages = json.load(file)
            else:
                prebuilt_packages = dict()

            print("Installing {}".format(" ".join(needed_packages)))
            ret = True
            ps.app.update()
            progress = ProgressBar(_("Installing site-packages"))
            try:
                python = config.get('Paths', 'python')
                for idx, package in enumerate(sorted(list(needed_packages))):
                    progress.update(idx / len(needed_packages) * 100, text=_("Installing site-packages") + ': ' + package)
                    if status == 'online' and package not in prebuilt_packages:
                        p = package if not requirements[package] else "{}=={}".format(package, requirements[package])
                        subprocess.run([python, '-m', 'pip', 'install',
                                        '--upgrade', "--target={}".format(default_sp_path), p])
                    elif status == 'online' and package in prebuilt_packages:
                        whl_file = download_prebuilt_package(package=package, prebuilt_packages=prebuilt_packages)
                        subprocess.run([python, '-m', 'pip', 'install',
                                        '--upgrade', "--target={}".format(default_sp_path), whl_file])
                        try:
                            os.remove(whl_file)
                        except Exception:
                            pass
                    elif status == 'offline':
                        subprocess.run([python, '-m', 'pip', 'install', '--upgrade',
                                        "--target={}".format(default_sp_path), "--no-index",
                                        "--find-links={}".format(pip_repo), package])
                    else:
                        raise SystemError
                # pip resets locale, we set it back
            except:
                logging.critical("Error installing with pip")
                import traceback
                traceback.print_exc()
                ret = False
            finally:
                locale.setlocale(locale.LC_ALL, initial_locale)
                progress.close()

    return False


def clean_old_packages(outdated):
    default_sp_path = config.get('Paths', 'sp_path')
    for f in os.listdir(default_sp_path):
        for o in outdated:
            if o in f.lower():
                # it stores every version of every package installed so we need to delete them manually
                path = os.path.join(default_sp_path, f)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            # sometimes we have naming errors, every package should be ckecked
            if o == 'tensorflow-gpu':
                if 'tensorflow_gpu' in f:
                    shutil.rmtree(os.path.join(default_sp_path, f))


def check_pip_repo(pip_repo):
    from importlib import metadata as importlib_metadata
    import warnings
    warnings.filterwarnings("ignore")

    if not os.path.exists(os.path.join(pip_repo, "requirements.txt")):
        raise FileNotFoundError
    # list outdated packages
    python = config.get('Paths', 'python')
    with tempfile.TemporaryFile('w+') as temp:
        with contextlib.redirect_stdout(temp):
            subprocess.run([python, '-m', 'pip', 'list', '-o', "--no-index", "--find-links={}".format(pip_repo)])
        temp.seek(0)
        outdated = set(l.lower().split()[0] for l in temp.readlines())
        locale.setlocale(locale.LC_ALL, initial_locale)

    installed = importlib_metadata.distributions()
    installed = [p.metadata["Name"].lower() for p in installed if p.metadata["Name"]]

    requirements = dict()
    with open(os.path.join(pip_repo, 'requirements.txt')) as f:
        needed_packages = set()
        for line in f.readlines():
            data = [x.strip().lower() for x in line.split('==')]
            package = data[0] if data[0] not in ['', '\n'] else None
            version = data[1] if len(data) == 2 else None
            if package:
                requirements[package] = version
                needed_packages.add(package)

    outdated = set(o for o in outdated if o in needed_packages)

    return installed, needed_packages, outdated, requirements


def update_resources():
    resources_url = config.get('Paths', 'binaries')
    resources_zip = download_file(url=resources_url, name='resources.zip',
                                  progress=True, progress_label=_("Update resources"))

    with zipfile.ZipFile(resources_zip, 'r') as zip_ref:
        zip_ref.extractall(config.get('Paths', 'local_app_data'))

    try:
        os.remove(resources_zip)
    except Exception:
        pass
