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

import json
import os
import tempfile

from common.startup.initialization import config


PLUGINS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def create_requirements():
    packages = get_all_packages()
    requirements = os.path.join(PLUGINS_DIR, 'requirements.txt')
    with open(requirements, 'w') as file:
        data = list()
        for package, version in sorted(packages.items(), key=lambda item: item[0].lower()):
            if version:
                data.append("{}=={}\n".format(package, version))
            else:
                data.append("{}\n".format(package))
        file.writelines(data)


def get_all_packages():
    packages = dict()
    for item in os.listdir(PLUGINS_DIR):
        if item == 'local_repo':
            continue
        obj = os.path.join(PLUGINS_DIR, item)
        if os.path.isdir(obj) and not item.startswith('.'):
            for file in filter(lambda x: x == 'requirements.txt', os.listdir(obj)):
                parse_requirements_txt(source=os.path.join(obj, file), packages=packages)
    return packages


def parse_requirements_txt(source: str, packages: dict):
    with open(source, 'r') as file:
        for line in file.readlines():
            data = [x.strip() for x in line.split('==')]
            package = data[0] if data[0] not in ['', '\n'] else None
            version = data[1] if len(data) == 2 else None

            if package and package not in packages:
                packages[package] = version


def change_version_for_package(package, version):
    for item in os.listdir(PLUGINS_DIR):
        obj = os.path.join(PLUGINS_DIR, item)
        if os.path.isdir(obj) and not item.startswith('.'):
            for file in filter(lambda x: x == 'requirements.txt', os.listdir(obj)):
                with open(os.path.join(obj, file), 'r') as source_r:
                    data = source_r.readlines()

                with open(os.path.join(obj, file), 'w') as source_w:
                    to_write = list()
                    for line in data:
                        info = [x.strip() for x in line.split('==')]
                        if info[0] == package and version:
                            to_write.append("{}=={}\n".format(package, version))
                        elif info[0] == package and not version:
                            to_write.append("{}\n".format(package))
                        else:
                            to_write.append(line)
                    source_w.writelines(to_write)


def remove_package_from_all(package):
    for item in os.listdir(PLUGINS_DIR):
        obj = os.path.join(PLUGINS_DIR, item)
        if os.path.isdir(obj) and not item.startswith('.'):
            for file in filter(lambda x: x == 'requirements.txt', os.listdir(obj)):
                with open(os.path.join(obj, file), 'r') as source_r:
                    data = source_r.readlines()

                with open(os.path.join(obj, file), 'w') as source_w:
                    to_write = list()
                    for line in data:
                        info = [x.strip() for x in line.split('==')]
                        if info[0] == package:
                            pass
                        else:
                            to_write.append(line)
                    source_w.writelines(to_write)


def find_package_in_plugins(package):
    for item in os.listdir(PLUGINS_DIR):
        obj = os.path.join(PLUGINS_DIR, item)
        if os.path.isdir(obj) and not item.startswith('.'):
            for file in filter(lambda x: x == 'requirements.txt', os.listdir(obj)):
                with open(os.path.join(obj, file), 'r') as source_r:
                    for line in source_r.readlines():
                        info = [x.strip() for x in line.split('==')]
                        if info[0] == package:
                            print(obj, line)


def download_prebuilt_package(package, prebuilt_packages) -> (str, None):
    if package not in prebuilt_packages:
        return None

    public_key, filename = prebuilt_packages[package]['url'], prebuilt_packages[package]['name']
    path = download_file(url=public_key, name=filename, progress=True, progress_label=_("Download python package..."))
    return path


def download_file(url, name, progress=False, progress_label=""):
    try:
        import requests
    except ImportError:
        import subprocess
        default_sp_path = config.get('Paths', 'sp_path')
        python = config.get('Paths', 'python')
        subprocess.run([python, '-m', 'pip', 'install', '--upgrade', "--target={}".format(default_sp_path), 'requests'])
        import requests

    temp = tempfile.gettempdir()

    if not progress:
        download_response = requests.get(url)
        with open(os.path.join(temp, name), 'wb') as f:  # Здесь укажите нужный путь к файлу
            f.write(download_response.content)
    else:
        from common.utils.ui import ProgressBar

        progress = ProgressBar(progress_label)
        with open(os.path.join(temp, name), 'wb') as f:
            response = requests.get(url, stream=True)
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                f.write(response.content)
            else:
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    dl += len(data)
                    f.write(data)
                    done = int(100 * dl / total_length)
                    progress.update(done)

    return os.path.join(temp, name)


def download_yandexdisk_file(url: str, name: str, progress=False, progress_label="") -> str:
    from urllib.parse import urlencode
    try:
        import requests
    except ImportError:
        import subprocess
        default_sp_path = config.get('Paths', 'sp_path')
        python = config.get('Paths', 'python')
        subprocess.run([python, '-m', 'pip', 'install', '--upgrade', "--target={}".format(default_sp_path), 'requests'])
        import requests

    base_url = 'https://cloud-api.yandex.net/v1/disk/public/resources/download?'

    final_url = base_url + urlencode(dict(public_key=url))
    response = requests.get(final_url)
    download_url = response.json()['href']

    temp = tempfile.gettempdir()

    if not progress:
        download_response = requests.get(download_url)
        with open(os.path.join(temp, name), 'wb') as f:  # Здесь укажите нужный путь к файлу
            f.write(download_response.content)
    else:
        from common.utils.ui import ProgressBar

        progress = ProgressBar(progress_label)
        with open(os.path.join(temp, name), 'wb') as f:
            response = requests.get(download_url, stream=True)
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                f.write(response.content)
            else:
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    dl += len(data)
                    f.write(data)
                    done = int(100 * dl / total_length)
                    progress.update(done)

    return os.path.join(temp, name)


def __create_prebuilt_packages_json():
    prebuilt_packages = {
        'gdal': {'url': 'https://disk.yandex.ru/d/z2-frDGSqlPTvQ', 'name': 'GDAL-3.1.4-cp38-cp38-win_amd64.whl'},
        'numpy': {'url': 'https://disk.yandex.ru/d/g9uxVIcGfE6jHw', 'name': 'numpy-1.20.3+mkl-cp38-cp38-win_amd64.whl'},
        'shapely': {'url': 'https://disk.yandex.ru/d/60HwVXWSupZaIg', 'name': 'Shapely-1.7.1-cp38-cp38-win_amd64.whl'},
    }

    with open(os.path.join(PLUGINS_DIR, 'prebuilt_requirements.json'), 'w') as f:
        json.dump(prebuilt_packages, f, indent=4, sort_keys=True)


if __name__ == "__main__":
    # find_package_in_plugins('pyshp')
    # create_requirements()
    # change_version_for_package('numpy', '1.20.3+mkl')
    # download_prebuilt_package('numpy')
    __create_prebuilt_packages_json()
    # download_file(url="https://disk.yandex.ru/d/g7gYtJkv9zgfKA", name='resources.zip', progress=False)
    # update_plugins_from_git("git@gitlab.corp.geoscan.aero:cv/metashape/plugins.git")
    pass

