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

import os, json, datetime
try:
    import requests
except:
    print('requests import failed')
    pass

BASE_PATH = os.path.join(os.getenv('LOCALAPPDATA'),
                         'Agisoft/PhotoScan Pro/logs')

SERVER_HOST = 'http://10.10.0.96:5044'

DEVELOPERS = {'a.someone'}


def log(type=None, message=None):

    '''
    :param type: (str) 'crash' or str 'start'
    :param message: (str) some info message
    '''

    global DEVELOPERS
    try:
        if not type:
            type = 'info'
        elif type not in ['start', 'crash', 'log_err']:
            type = 'undefined'

        log_dict = {
            'plugin': caller_name(),
            'time': str(datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')),
            'type': type,
            'msg': message,
            'username': os.getlogin(),
        }

        if log_dict['username'] in DEVELOPERS:
            pass
        send_log(log_dict)
    except Exception as err:
        try:
            log_dict['type'] = 'log_err'
            log_dict['msg'] = err.args[0]
            send_log(log_dict)
        except:
            pass


def resend_logs():
    global BASE_PATH
    current_file = os.path.join(BASE_PATH, 'plugins', 'temp_err.log')
    resend_file = os.path.join(BASE_PATH, 'plugins', 'resend_temp_err.log')
    if os.path.isfile(current_file):
        os.rename(current_file, resend_file)
        with open(resend_file) as log_file:
            for line in log_file.readlines():
                send_log(json.loads(line))
        os.remove(resend_file)


def backup_log(data, temp=True):
    if temp:
        path = os.path.join(get_path(), 'temp_err.log')
    else:
        log_file_name = '{}_{}.log'.format(data['plugin'], data['type'])
        path = os.path.join(get_path(data['plugin']), log_file_name)
    with open(path, 'a') as log_file:
        log_file.write(json.dumps(data))
        log_file.write('\n')


def send_log(data):
    global SERVER_HOST
    try:
        #add requests to packages?
        request = requests.post(SERVER_HOST, data=json.dumps(data))
        assert request.status_code == 200
    except:
        backup_log(data=data)
    else:
        backup_log(data=data, temp=False)


def get_path(plugin=None):
    global BASE_PATH
    base_path = BASE_PATH
    if plugin:
        path = os.path.join(base_path, 'plugins', plugin)
    else:
        path = os.path.join(base_path, 'plugins')
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


def caller_name():
    import inspect
    frame = inspect.currentframe()
    frame = frame.f_back.f_back
    code = frame.f_code
    return os.path.basename(code.co_filename).split('.')[0]



