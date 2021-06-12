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
import socket
import traceback
from datetime import datetime
import smtplib
from email.message import EmailMessage
from PySide2 import QtWidgets, QtCore

from common.startup.initialization import config
from common.loggers.logger_params import init, developers


REPORT_FLAG = config.get('Paths', 'report_about_errors') == 'True'


class LoggerError(Exception):
    pass


class LoggerValues:
    def __init__(self, input: dict, plugin_name: str, plugin_version=None, reply_email=None, user_annotation=None):
        """
        Helper to log errors which produced by Metashape plugins.
        :param input: dict. Input data of your app.
        :param plugin_name: App name.
        :param plugin_version: App version.
        :param reply_email: Add user email to message.
        :param user_annotation: Text message by user.
        """

        self.input = input
        self.plugin_name = plugin_name
        self.plugin_version = str(plugin_version)
        self.plugins_build = self.get_plugins_version()
        self.reply_email = str(reply_email)
        self.user_annotation = user_annotation

    @property
    def text_input(self):
        return "\n".join(["{}: {}".format(k, v) for k, v in self.input.items()])

    @staticmethod
    def get_plugins_version():
        scripts_dir = os.path.join(config.get('Paths', 'local_app_data'), 'scripts')
        version_file = os.path.join(scripts_dir, 'version')

        if not os.path.exists(version_file):
            return "None"

        with open(version_file, 'r') as file:
            version_text = file.read().strip()

        return version_text


def build_error_message(values: LoggerValues, error_type, error_text):
    """
    Build string subject and text for email message.
    :param values:
    :param error_type:
    :param error_text:
    :return:
    """

    time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    subject = "{}: {}".format(values.plugin_name, error_type)
    user_ann = "" if values.user_annotation is None else "User annotation:\n\n{}\n\n".format(values.user_annotation)

    text = "Date: {}\n\n" \
           "Plugin name: {}\n" \
           "Plugin version: {}\n" \
           "Plugins build: {}\n\n" \
           "Input values:\n\n{}\n\n" \
           "{}" \
           "Error:\n\n{}".format(values.reply_email if values.reply_email else '',
                                 time,
                                 values.plugin_name,
                                 values.plugin_version,
                                 values.plugins_build,
                                 values.text_input,
                                 user_ann,
                                 error_text)

    return subject, text


def send_email(server_params, user_to, subject, text):
    try:
        server = smtplib.SMTP_SSL(server_params['host'], server_params['port'])
        server.login(server_params['app_email'], server_params['password'])

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = server_params['app_email']
        msg['To'] = user_to
        msg.set_content(text)

        server.send_message(msg)
        server.quit()
    except socket.gaierror:
        raise Warning("Sending error log to developers is failed.")


def send_geoscan_plugins_error_to_devs(error, values):
    server_params = init()
    error_type = error.strip().split("\n")[-1].split(':')[0]
    subject, text = build_error_message(values=values, error_type=error_type, error_text=error)

    for dev in developers():
        send_email(server_params=server_params,
                   user_to=dev,
                   subject=subject,
                   text=text)


def show_message_error(text):
    msg = QtWidgets.QMessageBox()
    msg.setWindowTitle('Error')
    msg.setIcon(QtWidgets.QMessageBox.Critical)
    msg.setText(text)
    msg.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    msg.exec_()


def log_method(plugin_name: str, version: str):
    """To use this method self.log_values -> dict method is required in class object."""

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            try:
                func(self, *args, **kwargs)
            except Exception:
                values = LoggerValues(input=self.log_values(), plugin_name=plugin_name, plugin_version=version)
                send_geoscan_plugins_error_to_devs(error=traceback.format_exc(), values=values)
                show_message_error(text=traceback.format_exc())
        return wrapper
    return decorator


def log_func(plugin_name: str, version: str, input_items):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                res = func(*args, **kwargs)
                return res
            except Exception:
                values = LoggerValues(input=input_items, plugin_name=plugin_name, plugin_version=version)
                send_geoscan_plugins_error_to_devs(error=traceback.format_exc(), values=values)
                show_message_error(text=traceback.format_exc())
        return wrapper
    return decorator


def log_method_by_crash_reporter(plugin_name: str, version: str):
    """To use this method self.log_values -> dict method is required in class object."""

    import common.loggers.crash_reporter as cr

    def decorator_class(func):
        def wrapper(self, *args, **kwargs):
            try:
                res = func(self, *args, **kwargs)
                return res
            except Exception:
                if REPORT_FLAG:
                    values = LoggerValues(input=self.log_values(), plugin_name=plugin_name, plugin_version=version)
                    cr.run_crash_reporter(error=traceback.format_exc(), values=values, run_thread=False)
                else:
                    show_message_error(text=traceback.format_exc())
                raise LoggerError
        return wrapper
    return decorator_class


def log_func_by_crash_reporter(plugin_name: str, version: str, items: dict):
    import common.loggers.crash_reporter as cr

    def decorator_func(func):
        def wrapper(*args, **kwargs):
            try:
                res = func(*args, **kwargs)
                return res
            except Exception:
                if REPORT_FLAG:
                    values = LoggerValues(input=items, plugin_name=plugin_name, plugin_version=version)
                    cr.run_crash_reporter(error=traceback.format_exc(), values=values, run_thread=False)
                else:
                    show_message_error(text=traceback.format_exc())
                raise LoggerError
        return wrapper
    return decorator_func


def __testcase():
    input_items = {"Rover": "asda.txt", "Base": "base.txt", 'unit': 2}

    @log_func(plugin_name='test_app', version='0.4.7', input_items=input_items)
    def testcase1():
        shit_happens_value = 1 / 0

    testcase1()


if __name__ == "__main__":
    __testcase()
