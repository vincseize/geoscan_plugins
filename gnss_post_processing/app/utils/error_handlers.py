"""GNSS Post Processing plugin for Agisoft Metashape

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
import re
import textwrap
from PySide2 import QtWidgets,QtCore, QtGui
import Metashape

from common.loggers.email_logger import LoggerValues, send_geoscan_plugins_error_to_devs
from gnss_post_processing.app.meta import VERSION, NAME
from gnss_post_processing.app.utils.exceptions import InputDataError
from .rinex_parser import RinexMeta, RinexParser, get_rinex_time_bounds
from .telemetry_merger import PositionMerger


INPUT_DATA_ERROR = _("Input Data Error.\n")

SET_PATH_TO_PLOT = _("Set path before plotting")


TELEMETRY_ERRORS = [
    _("Error during parsing Geoscan telemetry file 1. Is it correct?"),
    _("Error during parsing Geoscan telemetry file 2. Is it correct?"),
    _("First time event in telemetry file 1 is later than last observation in rover RINEX file"),
    _("First time event in telemetry file 2 is later than last observation in rover RINEX file"),
    _("Last time event in telemetry file 1 is earlier than first observation in rover RINEX file"),
    _("Last time event in telemetry file 2 is earlier than first observation in rover RINEX file"),
    _("Start time event in telemetry file 1 is earlier than rover start observation time.\nContinue?"),
    _("Start time event in telemetry file 2 is earlier than rover start observation time.\nContinue?"),
    _("Last time event in telemetry file 1 is later than rover end observation time.\nContinue?"),
    _("Last time event in telemetry file 2 is later than rover end observation time.\nContinue?"),
    _("Invalid path to Geoscan telemetry1 file."),
    _("Invalid path to Geoscan telemetry2 file."),
    _("Unknown format of Geoscan telemetry1 file."),
    _("Unknown format of Geoscan telemetry2 file.")
    ]


ROVER_BASE_ERRORS = [
    _("Invalid path to rover RINEX file."),
    _("Invalid path to base RINEX file."),
    _("Unknown format to rover RINEX file."),
    _("Unknown format to base RINEX file."),
]

RINEX_NAVIGATION_ERROR = _("No RINEX navigation files were found.\n\n"
                           "Observation and navigation RINEX files must have the same filenames.")


def custom_user_error(text: (str, Exception), write_to_status=True, status_label=None):
    if isinstance(text, str):
        str_text = text
    elif isinstance(text, Exception):
        str_text = _("Error: ") + "\n".join(text.args) if text.args else type(text).__name__
    else:
        raise TypeError(type(text))

    if write_to_status and status_label:
        status_label.setText(str_text)
    else:
        Metashape.app.messageBox(textwrap.fill(str_text, 65))


def error_handler(self, error):
    items = dict()
    for k, v in self.saver.data.items():
        items[k] = v if not k.startswith('__') else v.item  # by common.utils.dump_userdata.CustomSave structure
    try:
        values = LoggerValues(input=items, plugin_name=NAME, plugin_version=VERSION)
        send_geoscan_plugins_error_to_devs(error=error, values=values)
    except Exception:
        pass

    self.ui.status_Label.setText("Unexpected error")


def ok_cancel_dialog(parent, text, title="Warning"):
    reply = QtWidgets.QMessageBox.question(parent, title,
                                           text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                           QtWidgets.QMessageBox.No)

    if reply == QtWidgets.QMessageBox.Yes:
        pass
    else:
        raise InterruptedError


class MissedEvents(QtWidgets.QDialog):
    def __init__(self, missed_events: list, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.missed_events = missed_events
        self.cancel_processing = False
        self.initUI()

    def initUI(self):
        self.setFixedSize(QtCore.QSize(500, 500))

        vlayout = QtWidgets.QVBoxLayout()

        info = QtWidgets.QLabel(_("Rover RINEX has missed epochs. Result for the listed events will be empty.\n"
                                "Do you want to continue?"))
        vlayout.addWidget(info)

        table = QtWidgets.QTableWidget()
        table.setColumnCount(1)
        table.setRowCount(len(self.missed_events))
        table.setHorizontalHeaderLabels([_("Event")])
        for i, event in enumerate(self.missed_events):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(event['data']))
        table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

        vlayout.addWidget(table)

        hlayout = QtWidgets.QHBoxLayout()

        go = QtWidgets.QPushButton(_("Continue"))
        go.clicked.connect(self.close)
        hlayout.addWidget(go)

        cancel = QtWidgets.QPushButton(_("Cancel processing"))
        cancel.clicked.connect(self.init_cancel_processing)
        hlayout.addWidget(cancel)

        vlayout.addLayout(hlayout)
        self.setLayout(vlayout)

    def init_cancel_processing(self):
        self.cancel_processing = True
        self.close()


def check_missed_epochs(rp: RinexParser, parent=None):
    if rp.missed_events:
        window = MissedEvents(rp.missed_events, parent=parent)
        window.exec_()
        if window.cancel_processing:
            raise InterruptedError


class MissedFlightFiles(QtWidgets.QDialog):
    def __init__(self, missed_data: dict, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.missed_data = missed_data
        self.cancel_processing = False
        self.initUI()

    def initUI(self):
        self.setMinimumSize(QtCore.QSize(800, 600))

        vlayout = QtWidgets.QVBoxLayout()

        info = QtWidgets.QLabel(_("The files listed below were not added to processing table:"))
        vlayout.addWidget(info)

        table = QtWidgets.QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels([_("Type"),_("Reason"), _("File")])
        table.setColumnWidth(0, 100)
        table.setColumnWidth(1, 250)
        table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)

        for reason, data in self.missed_data.items():
            for datatype, files in data.items():
                for file in files:
                    row_position = table.rowCount()
                    table.insertRow(row_position)
                    table.setItem(row_position, 0, QtWidgets.QTableWidgetItem(datatype))
                    table.setItem(row_position, 1, QtWidgets.QTableWidgetItem(reason))
                    table.setItem(row_position, 2, QtWidgets.QTableWidgetItem(file))

        vlayout.addWidget(table)

        hlayout = QtWidgets.QHBoxLayout()
        hspacer1 = QtWidgets.QSpacerItem(20, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        hlayout.addItem(hspacer1)
        ok = QtWidgets.QPushButton(_("OK"))
        ok.setFixedSize(QtCore.QSize(50, 25))
        ok.clicked.connect(self.close)
        hlayout.addWidget(ok)
        hspacer2 = QtWidgets.QSpacerItem(20, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        hlayout.addItem(hspacer2)

        vlayout.addLayout(hlayout)
        self.setLayout(vlayout)


def check_missed_flights_data(data, parent=None):
    if data is not None:
        window = MissedFlightFiles(data, parent=parent)
        window.exec_()


def is_correct_rover_data(rp: RinexParser, parent=None, transfer_warnings_to_list: (None, list) = None):
    """Check rover RINEX file"""
    warnings = transfer_warnings_to_list if transfer_warnings_to_list is not None else None

    if not rp.events or len(rp.events) == 0:
        msg = _("No time events in rover RINEX file. Continue?")
        if transfer_warnings_to_list is None:
            ok_cancel_dialog(parent, text=textwrap.fill(msg, 65))
        else:
            warnings.append("No time events in rover RINEX file")

    if not rp.epochs or len(rp.epochs) == 0:
        msg = INPUT_DATA_ERROR + _("No epochs in rover RINEX file")
        Metashape.app.messageBox(textwrap.fill(msg, 65))
        raise InputDataError(msg)


def is_correct_time_bounds(rover_file, base_file, telemetry_file1, telemetry_file2, parent=None,
                           rover_time_start=None, rover_time_end=None,
                           base_time_start=None, base_time_end=None,
                           telemetry_time_start=None, telemetry_time_end=None):
    """Checking if time bounds is equal for rover RINEX, base RINEX and telemetry files"""

    if rover_time_start is None and rover_time_end is None:
        rover_time_start, rover_time_end = get_rinex_time_bounds(rover_file)

    if not all([rover_time_start, rover_time_end]):
        msg = INPUT_DATA_ERROR + _("Couldn't get time bounds from Rover RINEX.")
        Metashape.app.messageBox(textwrap.fill(msg, 65))
        raise InputDataError(msg)

    if base_time_start is None or base_time_end is None:
        base_time_start, base_time_end = get_rinex_time_bounds(base_file)

    if not all([base_time_start, base_time_end]):
        msg = INPUT_DATA_ERROR + _("Couldn't get time bounds from Base RINEX.")
        Metashape.app.messageBox(textwrap.fill(msg, 65))
        raise InputDataError(msg)

    if rover_time_start < base_time_start:
        rover_time_start_str = rover_time_start.strftime("%H:%M:%S")
        base_time_start_str = base_time_start.strftime("%H:%M:%S")
        msg = _("Start time of rover RINEX file is earlier than base RINEX start observation time.") + \
              "\nRover start time: {}.\nBase start time: {}.".format(rover_time_start_str, base_time_start_str) + \
              "\n\n" + _("Continue?")
        ok_cancel_dialog(text=textwrap.fill(msg, 65), parent=parent)

    if rover_time_end > base_time_end:
        rover_time_end_str = rover_time_end.strftime("%H:%M:%S")
        base_time_end_str = base_time_end.strftime("%H:%M:%S")
        msg = _("End time of rover RINEX file is later than base RINEX end observation time.") + \
              "\nRover end time: {}.\nBase end time: {}.".format(rover_time_end_str, base_time_end_str) + \
              "\n\n" + _("Continue?")
        ok_cancel_dialog(text=textwrap.fill(msg, 65), parent=parent)

    for i, file in enumerate([telemetry_file1, telemetry_file2]):
        if not file and file == telemetry_file2:
            continue

        try:
            telemetry_positions = PositionMerger.parse_telemetry_file(file)
            telemetry_items = list(telemetry_positions.items())
            telemetry_time_start, telemetry_time_end = telemetry_items[0][0], telemetry_items[-1][0]
        except:
            msg = INPUT_DATA_ERROR + _("Error during parsing Geoscan telemetry file {}. Is it correct?".format(i+1))
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise AssertionError(msg)

        print("Base time bounds: ", base_time_start, ", ", base_time_end, '\n',
              "Rover time bounds: ", rover_time_start, ", ", rover_time_end, '\n',
              "Telemetry time bounds: ", telemetry_time_start, ", ", telemetry_time_end, '\n')

        if telemetry_time_start > rover_time_end:
            msg = INPUT_DATA_ERROR + \
                  _("First time event in telemetry file {} is later than last observation in rover RINEX file".format(i+1))
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise InputDataError(msg)

        if telemetry_time_end < rover_time_start:
            msg = INPUT_DATA_ERROR + \
                  _("Last time event in telemetry file {} is earlier than first observation in rover RINEX file".format(i+1))
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise InputDataError(msg)

        if telemetry_time_start < rover_time_start:
            msg = _("Start time event in telemetry file {} is earlier than rover start observation time.\n" \
                  "Continue?".format(i+1))
            ok_cancel_dialog(text=textwrap.fill(msg, 65), parent=parent)

        if telemetry_time_end > rover_time_end:
            msg = _("Last time event in telemetry file {} is later than rover end observation time.\n" \
                  "Continue?".format(i+1))
            ok_cancel_dialog(text=textwrap.fill(msg, 65), parent=parent)

    return rover_time_start, rover_time_end


def is_correct_input_formats(**kwargs):
    is_correct_rinex_format(kwargs)
    is_correct_values(kwargs)
    is_correct_telemetry_files(kwargs)
    check_excluded_satellites_format(kwargs)


def is_correct_values(data: dict):
    try:
        float(data['x'])
        float(data['y'])
        float(data['z'])
        float(data['antenna_h'])
    except ValueError:
        msg = _("Invalid coordinates values")
        Metashape.app.messageBox(msg)
        raise InputDataError(msg)


def check_excluded_satellites_format(data: dict):
    """
    Check to correct format for text line with excluded satelites.
    GPS and GLONASS satellites is supported.
    """
    if not 'excluded_satellites' in data:
        Metashape.app.messageBox('AssertionError')
        raise AssertionError

    if not data['excluded_satellites']:
        return True

    satellites = [x.strip() for x in data['excluded_satellites'].split(',')]
    for sat in satellites:
        if not re.match(r"[RG]\d\d", sat):
            msg = INPUT_DATA_ERROR + _("Unkhown satellite in excluded satellites form:") + "{}.\n".format(sat) + \
                  _("Supported satellite groups: GPS (G), GLONASS (R).")
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise InputDataError(msg)


def is_correct_rinex_format(files: dict):
    """Checking paths"""

    for _type in ['rover', 'base']:
        if _type not in files:
            msg = "AssertionError: is_correct_rinex_format, input_arg = {}".format(_type)
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise AssertionError(msg)

        if not os.path.exists(files[_type]) or not os.path.isfile(files[_type]):
            msg = INPUT_DATA_ERROR + _("Invalid path to {} RINEX file.".format(_type))
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise InputDataError(msg)

        if not re.search(r"\.\d\d[oO]$|\.obs|\.OBS", os.path.basename(files[_type])):
            msg = INPUT_DATA_ERROR + _("Unknown format to {} RINEX file.".format(_type))
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise InputDataError(msg)


def is_correct_telemetry_files(files: dict):
    """Checking paths"""

    for _type in ['telemetry1', 'telemetry2']:
        if _type not in files:
            msg = "AssertionError: is_correct_rinex_format, input_arg = {}".format(_type)
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise AssertionError(msg)

        if _type.endswith('2') and not files['telemetry2']:
            continue

        if not files['telemetry1']:
            msg = INPUT_DATA_ERROR + _("Set telemetry file path to continue")
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise InputDataError(msg)

        if not os.path.exists(files[_type]) or not os.path.isfile(files[_type]):
            msg = INPUT_DATA_ERROR + _("Invalid path to Geoscan {} file.".format(_type))
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise InputDataError(msg)

        if not re.search(r"\.txt$", os.path.basename(files[_type])):
            msg = INPUT_DATA_ERROR + _("Unknown format of Geoscan {} file.".format(_type))
            Metashape.app.messageBox(textwrap.fill(msg, 65))
            raise InputDataError(msg)


if __name__ == "__main__":
    pass