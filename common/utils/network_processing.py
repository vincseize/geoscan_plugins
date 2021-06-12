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

import os

import PhotoScan as ps
from common.utils.paths import get_path_in_chunk


def get_plugins_work_path(fn=None):
    """
    Returns plugins work dir path if fn is not defined, else returns plugins work file path
    :param fn: filename
    :return: path
    """

    path = get_path_in_chunk(end='plugins_workdir', fn=fn)
    return path


def create_client():
    """
    Create and connect PhotoScan.NetworkClient
    :return: client instance
    """

    s = ps.app.settings
    ip = s.network_host
    port = s.network_port
    client = ps.NetworkClient()
    client.connect(ip, port)
    return client


def get_network_path(path=None):
    """
    Returns network relative path
    :param path:
    :return: relative path
    """

    if not path:
        path = ps.app.document.path

    path = path.replace('\\', '//')
    root = ps.app.settings.network_path
    try:
        net_path = os.path.relpath(path, root)
        net_path = net_path.replace('\\', '/')
    except ValueError:
        net_path = path
    return net_path


def get_frame(chunk_id=None, frame_id=None):
    """
    Returns chunk key, frame id
    :param chunk_id:
    :param frame_id:
    :return:chunk key, frame id
    """

    chunk = ps.app.document.chunk
    if not chunk_id:
        chunk_id = chunk.key
    if not chunk_id:
        frame_id = chunk.frames.index(chunk.frame)
    return chunk_id, frame_id


def send_to_network_processing(script_path):
    with open(script_path, encoding='UTF-8') as f:
        text = f.read()

    # task = ps.Tasks.RunScript()
    # task.code = text

    task = ps.NetworkTask()
    task.name = 'RunScript'
    task.params['code'] = text

    client = create_client()
    net_path = get_network_path()
    batch_id = client.createBatch(net_path, [task])
    client.resumeBatch(batch_id)


if __name__ == '__main__':
    n_path = get_network_path()
    tasks = []
    t = ps.NetworkTask()
    t.frames = get_frame()
    t.name = 'OptimizeCameras'
    t.params['network_distribute'] = True
    t.params['fit_b1'] = False
    t.params['fit_b2'] = False
    t.params['fit_k4'] = False
    tasks.append(t)
    cl = create_client()
    batchID = cl.createBatch(n_path, tasks)
    cl.resumeBatch(batchID)
