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

import traceback
from pathlib import Path
from threading import Thread
import textwrap
import os
import re
import concurrent.futures

import Metashape
from PySide2 import QtWidgets, QtCore, QtGui
import tempfile
from shutil import copy, rmtree
import subprocess

# from common.loggers.crash_reporter import run_crash_reporter
from common.startup.initialization import config
from common.utils.ui import load_ui_widget
from common.utils.dump_userdata import UserDataDump, CustomSave
from gnss_post_processing.app.meta import NAME, VERSION, HELP
from gnss_post_processing.app.multiple_processing import SingleBaseMultipleFlights
from gnss_post_processing.app.translations import init_gnss_post_processing_translations
from gnss_post_processing.app.utils.antennas import get_antennas
from gnss_post_processing.app.utils.pos_parser import PosParser
from gnss_post_processing.app.utils.telemetry_merger import PositionMerger, reproject_point
from gnss_post_processing.app.utils.rinex_parser import RinexParser
from gnss_post_processing.app.utils.error_handlers import error_handler, is_correct_input_formats, \
    is_correct_time_bounds, is_correct_rover_data, custom_user_error, SET_PATH_TO_PLOT, check_missed_epochs
from gnss_post_processing.app.utils.exceptions import IndexErrorInPosFile, InputDataError, NoEvents, NoEpochs


class GnssProcessor(QtWidgets.QDialog):

    SOLUTIONS = {"forward": "pos1-soltype       =forward\n",
                 "backward": "pos1-soltype       =backward\n",
                 "combined": "pos1-soltype       =combined\n"}

    def __init__(self, parent=None):
        super(GnssProcessor, self).__init__()
        self.ui = load_ui_widget(
            os.path.join(os.path.dirname(__file__), "gnss_post_processing_gui.ui"),
            parent=parent,
        )

        self.ui.versionLabel.setText('<html><head/><body><p><span style=" color:#8b8b8b;">'
                                     '{}'
                                     '</span></p></body></html>'.format(_("v")+VERSION))
        self.saver = UserDataDump(directory=os.path.dirname(__file__), filename='single',
                                  parent=self, create_cache_dir=True)

        self.parent = parent
        self.processing_dir = ""
        self.stop_workers = False

        self.rnx2rtkp = os.path.join(config.get('Paths', 'resources'), 'GnssPostProcessing', 'rnx2rtkp_win64.exe')
        self.conf = os.path.join(config.get('Paths', 'resources'), 'GnssPostProcessing', 'rtklib_configuration.conf')
        self.rtkplot = os.path.join(config.get('Paths', 'resources'), 'GnssPostProcessing', 'rtkplot.exe')
        self.igs14 = os.path.join(config.get('Paths', 'resources'), 'GnssPostProcessing', 'igs14.atx')

        self.crs = Metashape.CoordinateSystem()

        try:
            if self.ui.roverpath_lineEdit.text():
                self.processing_dir = os.path.join(tempfile.gettempdir(),
                                                   os.path.basename(self.ui.roverpath_lineEdit.text()).split('.')[0])
                if self.processing_dir and not os.path.exists(self.processing_dir):
                    os.makedirs(self.processing_dir)
        except Exception:
            print("***GNSS Post Processing*** Unexpected error with processing directory.")

        self.ui.roverpath_pushButton.clicked.connect(self.browse_rover)
        self.ui.plot_rover_pushButton.setText("\u2315")
        self.ui.plot_rover_pushButton.clicked.connect(lambda: self.plot_thread(self.plot_rover))
        self.ui.RevolutionCheckBox.clicked.connect(self.enable_epochs_number)
        self.ui.basepath_pushButton.clicked.connect(self.browse_base)
        self.ui.plot_base_pushButton.setText("\u2315")
        self.ui.plot_base_pushButton.clicked.connect(lambda: self.plot_thread(self.plot_base))
        self.ui.telemetrypath1_pushButton.clicked.connect(self.browse_telemetry1)
        self.ui.telemetrypath2_pushButton.clicked.connect(self.browse_telemetry2)
        self.ui.telemetry2_checkBox.stateChanged.connect(self.telemetry2_enable)
        self.previous_dir = Path.home().__str__()

        self.ui.crs_pushButton.clicked.connect(self.select_crs)

        self.ui.plot_track_pushButton.clicked.connect(lambda: self.plot_thread(self.plot_track))
        self.ui.plot_marks_pushButton.clicked.connect(lambda: self.plot_thread(self.plot_marks))
        self.ui.export_pushButton.clicked.connect(self.export_merged_result)
        self.ui.import_pushButton.clicked.connect(self.import_to_chunk)

        self.ui.process_pushButton.clicked.connect(self.process_btn)

        if self.ui.roverpath_lineEdit.text():
            self.ui.plot_rover_pushButton.setEnabled(True)
        if self.ui.basepath_lineEdit.text():
            self.ui.plot_base_pushButton.setEnabled(True)

        self.ui.installEventFilter(self)

        self.fill_antenna_types()
        self.enable_epochs_number()

        self.ui.basepath_lineEdit.textChanged.connect(self.set_antenna_values)
        self.telemetry2_enable()

        self.saver.create_and_update(
            roverpath_lineEdit="", RevolutionCheckBox=False, EpochsNumberSpinBox=10,
            basepath_lineEdit="",
            north_lineEdit="52.0975", east_lineEdit="23.6877", height_lineEdit="130.7", antennaH_lineEdit="0",
            glonass_checkBox=False, elv_mask_spinBox=15, excluded_sats_lineEdit="",
            telemetrypath1_lineEdit="",
            telemetrypath2_lineEdit="", telemetry2_checkBox=False,
            __crs=CustomSave(item=Metashape.CoordinateSystem("EPSG::4326").wkt,
                             set_func="set_crs_userdata", extract_func="extract_crs_userdata")
        )
        self.saver.upload_to_ui(self.ui)

        self.multiple_processing = SingleBaseMultipleFlights(ui=self.ui,
                                                             rnx2rtkp=self.rnx2rtkp,
                                                             rtklib_config=self.conf,
                                                             igs14=self.igs14,
                                                             rtkplot=self.rtkplot)

        init_gnss_post_processing_translations(self.ui)

    @property
    def active_tab(self):
        return self.ui.tabWidget.currentIndex()

    @QtCore.Slot()
    def quit_app(self, event):
        self.saver.dump_from_ui(self.ui)
        self.multiple_processing.saver.dump_from_ui(self.ui)

        try:
            self.runner.join()
            if self.processing_dir and os.path.exists(self.processing_dir):
                for file in os.listdir(self.processing_dir):
                    os.remove(os.path.abspath(os.path.join(self.processing_dir, file)))
                rmtree(self.processing_dir, ignore_errors=True)
                print('***GNSS Post Processing*** Temporary directory removed.')
            self.ui.removeEventFilter(self)
            event.accept()
        except Exception:
            if self.processing_dir and os.path.exists(self.processing_dir):
                rmtree(self.processing_dir, ignore_errors=True)
                print('***GNSS Post Processing*** Temporary directory removed.')
            self.ui.removeEventFilter(self)
            event.accept()
        return True

    def eventFilter(self, qobject, qevent):
        qtype = qevent.type()
        if qtype in [QtCore.QEvent.Type.Hide, QtCore.QEvent.Type.Close]:
            self.quit_app(qevent)
            return True
        if qtype == QtCore.QEvent.EnterWhatsThisMode:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(HELP))
        return False

    def set_crs_userdata(self, item):
        self.crs.init(item)
        self.ui.crs_Label.setText(self.crs.name)

    def extract_crs_userdata(self):
        return self.crs.wkt

    def browse_rover(self):
        if self.ui.roverpath_lineEdit.text():
            self.previous_dir = os.path.dirname(self.ui.roverpath_lineEdit.text())

        directory = QtWidgets.QFileDialog.getOpenFileName(self.ui, _("Choose rover RINEX"), self.previous_dir)
        rover_file = directory[0]
        if not rover_file:
            return

        if os.path.exists(rover_file) and re.search(r".*\.\d\d[oO]", rover_file):
            if self.processing_dir and os.path.exists(self.processing_dir):
                rmtree(self.processing_dir)

            self.processing_dir = os.path.join(tempfile.gettempdir(), os.path.basename(directory[0]).split('.')[0])
            os.makedirs(self.processing_dir)
            self.previous_dir = os.path.dirname(directory[0])
            self.ui.plot_rover_pushButton.setEnabled(True)
            self.ui.roverpath_lineEdit.setText(directory[0].replace('/', '\\'))

    def browse_base(self):
        if self.ui.basepath_lineEdit.text():
            self.previous_dir = os.path.dirname(self.ui.basepath_lineEdit.text())

        directory = QtWidgets.QFileDialog.getOpenFileName(self.ui, _("Choose base RINEX"), self.previous_dir)
        if directory[0]:
            self.ui.basepath_lineEdit.setText(directory[0].replace('/', '\\'))
            self.previous_dir = os.path.dirname(directory[0])
            antenna_height = RinexParser.get_antenna_height(os.path.abspath(directory[0]))
            if antenna_height:
                self.ui.antennaH_lineEdit.setText(str(antenna_height))
            else:
                self.ui.antennaH_lineEdit.setText(str(0))
            antenna_type = RinexParser.get_antenna_type(os.path.abspath(directory[0]))
            if antenna_type:
                index = self.ui.antennaTypeComboBox.findText(antenna_type, QtCore.Qt.MatchFixedString)
                if index >= 0:
                    self.ui.antennaTypeComboBox.setCurrentIndex(index)
            else:
                self.ui.antennaTypeComboBox.setCurrentIndex(0)

            self.ui.plot_base_pushButton.setEnabled(True)

    def browse_telemetry1(self):
        if self.ui.telemetrypath1_lineEdit.text():
            self.previous_dir = os.path.dirname(self.ui.telemetrypath1_lineEdit.text())

        directory = QtWidgets.QFileDialog.getOpenFileName(self.ui, _("Choose telemetry file"), self.previous_dir,
                                                          filter="Geoscan telemetry (*.txt)")
        if directory[0]:
            self.ui.telemetrypath1_lineEdit.setText(directory[0].replace('/', '\\'))
            self.previous_dir = os.path.dirname(directory[0])

    def browse_telemetry2(self):
        if self.ui.telemetrypath2_lineEdit.text():
            self.previous_dir = os.path.dirname(self.ui.telemetrypath2_lineEdit.text())

        directory = QtWidgets.QFileDialog.getOpenFileName(self.ui, _("Choose telemetry file"), self.previous_dir,
                                                          filter="Geoscan telemetry (*.txt)")
        if directory[0]:
            self.ui.telemetrypath2_lineEdit.setText(directory[0].replace('/', '\\'))
            self.previous_dir = os.path.dirname(directory[0])

    def select_crs(self):
        crs = Metashape.app.getCoordinateSystem()
        if crs:
            self.crs = crs
            self.ui.crs_Label.setText(self.crs.name)

    def update_gnss_processing_parameters(self):
        self.antenna_height = self.ui.antennaH_lineEdit.text().replace(",", ".")

        self.base_north = self.ui.north_lineEdit.text().replace(",", ".")
        self.base_east = self.ui.east_lineEdit.text().replace(",", ".")

        if self.crs.name != "WGS 84":
            self.base_height = self.ui.height_lineEdit.text().replace(",", ".")
            reprojected_base = reproject_point(source_crs=self.crs,
                                               target_crs=Metashape.CoordinateSystem("EPSG::4326"),
                                               north=float(self.base_north),
                                               east=float(self.base_east),
                                               height=float(self.base_height))
            self.base_north = str(reprojected_base.y)
            self.base_east = str(reprojected_base.x)
            self.base_height = str(reprojected_base.z + float(self.antenna_height))
        else:
            self.base_height = str(float(self.ui.height_lineEdit.text().replace(",", ".")) + float(self.antenna_height))

        self.antenna_type = self.ui.antennaTypeComboBox.currentText()

        self.is_gps = self.ui.gps_checkBox.isChecked()
        self.is_glonass = self.ui.glonass_checkBox.isChecked()
        self.elevation_mask = self.ui.elv_mask_spinBox.value()
        self.excluded_sats = self.ui.excluded_sats_lineEdit.text().split(',')
        # for RINEX 3.x
        """
        self.is_galileo = self.ui.galileo_checkBox.isChecked()
        self.is_qzss = self.ui.qzss_checkBox.isChecked()
        self.is_sbas = self.ui.sbas_checkBox.isChecked()
        self.is_beidou = self.ui.beidou_checkBox.isChecked()
        self.is_irnss = self.ui.irnss_checkBox.isChecked()
        """

        if '' in [self.base_north, self.base_east, self.base_height, self.antenna_height] or \
                None in [self.is_gps, self.is_glonass, self.elevation_mask]:
            Metashape.app.messageBox(_("Incorrect input data"))
            raise ValueError("Incorrect input data")

    def create_configuration_file(self, solution, solution_path):
        self.update_gnss_processing_parameters()

        with open(self.conf, 'r') as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            if "pos1-soltype" in line:
                lines[i] = self.SOLUTIONS[solution]
            if "pos1-elmask" in line:
                lines[i] = re.sub('=.+', '={}'.format(self.elevation_mask), line)
            elif "pos1-navsys" in line:
                value = 1  # gps
                if self.is_glonass:
                    value += 4

                # for RINEX 3.x
                """
                if self.is_galileo:
                    value += 8
                if self.is_qzss:
                    value += 16
                if self.is_sbas:
                    value += 2
                if self.is_beidou:
                    value += 32
                if self.is_irnss:
                    value += 64
                """

                lines[i] = re.sub('=\d+', '={}'.format(value), line)
            elif "pos1-exclsats" in line:
                sats = ''.join([x for x in self.excluded_sats])
                lines[i] = re.sub('=.*', '={}'.format(sats), line)
            elif "ant2-pos1" in line:
                lines[i] = re.sub('=.*', '={}'.format(self.base_north), line)
            elif "ant2-pos2" in line:
                lines[i] = re.sub('=.*', '={}'.format(self.base_east), line)
            elif "ant2-pos3" in line:
                lines[i] = re.sub('=.*', '={}'.format(self.base_height), line)
            elif "ant2-antdelu" in line:
                lines[i] = re.sub('=.*', '=0', line)
            elif "ant2-anttype" in line:
                lines[i] = re.sub('=.*', '={}'.format(self.antenna_type), line)
            elif "file-rcvantfile" in line:
                lines[i] = "file-rcvantfile    ={}\n".format(self.igs14)

        with open(os.path.join(solution_path, os.path.basename(self.conf)), 'w') as file:
            for line in lines:
                file.write(line)

    def upgrade_rover_rinex(self, rover_path):
        self.upgraded_rover = os.path.join(self.processing_dir, os.path.basename(rover_path).split('.')[0] + '.obs')
        rinex_parser = RinexParser(obs_file=rover_path)

        if self.ui.RevolutionCheckBox.isChecked():
            epochs_number = int(int(self.ui.EpochsNumberSpinBox.value()) / 2)
            rinex_parser.make_obs_rinex(path=self.upgraded_rover, epochs_buffer=epochs_number)
        else:
            rinex_parser.make_obs_rinex(path=self.upgraded_rover, epochs_buffer=None)

        # check rinex files
        is_correct_rover_data(rp=rinex_parser, parent=self.ui)
        check_missed_epochs(rp=rinex_parser, parent=self.ui)

        return rinex_parser.meta.time_start, rinex_parser.meta.time_end

    def process_btn(self):
        if self.active_tab != 0:
            return

        self.ui.status_Label.setText(_("Checking input data..."))
        Metashape.app.update()

        rover_path = self.ui.roverpath_lineEdit.text()
        base_path = self.ui.basepath_lineEdit.text()
        telemetry1 = self.ui.telemetrypath1_lineEdit.text()
        telemetry2 = self.ui.telemetrypath2_lineEdit.text() if self.ui.telemetry2_checkBox.isChecked() else ""
        try:
            is_correct_input_formats(
                rover=rover_path,
                base=base_path,
                telemetry1=telemetry1,
                telemetry2=telemetry2,
                excluded_satellites=self.ui.excluded_sats_lineEdit.text(),
                y=self.ui.north_lineEdit.text(),
                x=self.ui.east_lineEdit.text(),
                z=self.ui.height_lineEdit.text(),
                antenna_h=self.ui.antennaH_lineEdit.text(),
            )
        except InputDataError:
            self.ui.status_Label.setText("")
            return
        try:
            self.enable_qt_objects(False)
            if not self.processing_dir:
                self.processing_dir = os.path.join(tempfile.gettempdir(), os.path.basename(rover_path).split('.')[0])
            if not os.path.exists(self.processing_dir):
                os.makedirs(self.processing_dir)
            print('***GNSS Post Processing*** Temporary directory with raw files: ', self.processing_dir)

            base_obs, base_nav, base_gnav = self.find_rinex_files(base_path)
            self.ui.status_Label.setText(_("Processing RINEX files..."))
            Metashape.app.update()
            rover_time_start, rover_time_end = self.upgrade_rover_rinex(rover_path)

            self.ui.status_Label.setText(_("Checking time bounds..."))
            Metashape.app.update()
            # check time bounds of input files
            rover_time_start, rover_time_end = is_correct_time_bounds(
                rover_file=self.upgraded_rover,
                base_file=base_obs,
                telemetry_file1=telemetry1,
                telemetry_file2=telemetry2,
                parent=self.ui,
                rover_time_start=rover_time_start,
                rover_time_end=rover_time_end,
            )
            Metashape.app.update()
        except Exception as error:
            self.saver.dump_from_ui(self.ui)
            self.enable_qt_objects(True)
            self.ui.status_Label.setText("")
            if type(error) in [NoEvents, NoEpochs]:
                custom_user_error(error, write_to_status=True, status_label=self.ui.status_Label)
            if not type(error) in [InterruptedError, InputDataError]:
                if config.get('Options', 'report_about_errors') == 'True':
                    error_handler(self, error=traceback.format_exc())
                else:
                    traceback.print_exc()
            return

        self.ui.status_Label.setText(_("Reading RINEX files..."))
        Metashape.app.update()
        self.runner = Thread(target=self.run_rnx2rtkp,
                             args=(self.processing_dir, self.upgraded_rover, base_obs, base_nav, base_gnav,
                                   rover_time_start, rover_time_end),
                             daemon=True)
        self.runner.start()

    def run_rnx2rtkp(self, processing_dir, rover_path, base_path, nav_path, gnav_path, start, end):
        try:
            results = dict()
            for sol in self.SOLUTIONS.keys():
                sol_dir = os.path.join(processing_dir, sol)
                if not os.path.exists(sol_dir):
                    os.makedirs(sol_dir)
                results[sol] = {'path':  sol_dir, 'quality': -1,
                                'rover_path': rover_path, 'base_path': base_path,
                                'nav_path': nav_path, 'gnav_path': gnav_path}

            with concurrent.futures.ThreadPoolExecutor(3) as executor:
                futures = dict()
                for i, solution in enumerate(self.SOLUTIONS.keys()):
                    future = executor.submit(self.process_gnss_data, data=results[solution], solution=solution,
                                             start=start, end=end)
                    futures[future] = solution
                for future in concurrent.futures.as_completed(futures):
                    success_result = future.result()
                    if success_result:
                        self.stop_workers = True

            self.ui.status_Label.setText(_("Merging with telemetry..."))
            success_solution = max(results, key=lambda sol: results[sol]['quality'])
            self.merge_telemetry_with_gnss(os.path.join(results[success_solution]['path'], 'ppk_track_events.pos'),
                                           quality=results[success_solution]['quality'])
            self.enable_qt_objects(True)
            self.ui.status_Label.setText(_("Completed!"))
            copy(os.path.join(results[success_solution]['path'], 'ppk_track_events.pos'),
                 os.path.join(processing_dir, 'ppk_track_events.pos'))
            copy(os.path.join(results[success_solution]['path'], 'ppk_track.pos'),
                 os.path.join(processing_dir, 'ppk_track.pos'))
            self.stop_workers = False
        except Exception as e:
            self.saver.dump_from_ui(self.ui)
            self.enable_qt_objects(True)
            if type(e) in [IndexErrorInPosFile]:
                custom_user_error(e, write_to_status=True, status_label=self.ui.status_Label)
                self.ui.plot_marks_pushButton.setEnabled(False)
                self.ui.plot_track_pushButton.setEnabled(False)
                self.ui.export_pushButton.setEnabled(False)
                self.ui.import_pushButton.setEnabled(False)
            else:
                if config.get('Options', 'report_about_errors') == 'True':
                    error_handler(self, error=traceback.format_exc())
                else:
                    traceback.print_exc()

    def process_gnss_data(self, data, solution, start, end):
        self.create_configuration_file(solution=solution, solution_path=data['path'])
        args = [self.rnx2rtkp,
                '-k', os.path.join(data['path'], os.path.basename(self.conf)),
                '-o', os.path.join(data['path'], 'ppk_track.pos'),
                '-ts', "{}/{}/{}".format(start.year, start.month, start.day),
                "{}:{}:{}".format(start.hour, start.minute, start.second),
                '-te', "{}/{}/{}".format(end.year, end.month, end.day),
                "{}:{}:{}".format(end.hour, end.minute, end.second),
                data['rover_path'], data['base_path'], data['nav_path']]
        if self.is_glonass and data['gnav_path']:
            args.append(data['gnav_path'])

        if solution == 'combined':
            for line in self.execute(args):
                if 'processing' in line:
                    event_log = ":".join(line.split(':')[1:])
                    self.ui.status_Label.setText(event_log)
                if self.stop_workers:
                    return False
        else:
            for line in self.execute(args):
                if self.stop_workers:
                    return False

        pos_events = os.path.join(data['path'], 'ppk_track_events.pos')
        if not os.path.exists(pos_events):
            return False

        pos_parser = PosParser(file=pos_events)
        data['quality'] = pos_parser.quality
        print(f"Processing method = {solution}, quality = {round(pos_parser.quality, 3)}%")

        return True if pos_parser.quality > 95 else False

    def execute(self, cmd):
        popen = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
        for stderr_line in iter(popen.stderr.readline, ""):
            yield stderr_line
        popen.stderr.close()
        return_code = popen.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, cmd)

    def merge_telemetry_with_gnss(self, pos_file, quality):
        telemetry1 = self.ui.telemetrypath1_lineEdit.text()
        telemetry2 = self.ui.telemetrypath2_lineEdit.text() if self.ui.telemetry2_checkBox.isChecked() else ""

        output1 = os.path.join(self.processing_dir, 'merged_events1')
        output2 = os.path.join(self.processing_dir, 'merged_events2')

        chunk = Metashape.app.document.chunk

        extension = True if len(chunk.cameras) > 0 and len(chunk.cameras[0].label.split('.')) > 1 else False

        if telemetry1 and os.path.exists(telemetry1):
            self.merger1 = PositionMerger(pos_file=pos_file,
                                          telemetry_file=telemetry1,
                                          output=output1,
                                          extension=extension,
                                          reproject=[Metashape.CoordinateSystem("EPSG::4326"), self.crs],
                                          quality=quality)
            self.merger1.merge()
        else:
            self.merger1 = None

        if telemetry2 and os.path.exists(telemetry2):
            self.merger2 = PositionMerger(pos_file=pos_file,
                                          telemetry_file=telemetry2,
                                          output=output2,
                                          extension=extension,
                                          reproject=[Metashape.CoordinateSystem("EPSG::4326"), self.crs],
                                          quality=quality)
            self.merger2.merge()
        else:
            self.merger2 = None

        if self.merger1 is not None or self.merger2 is not None:
            self.ui.import_pushButton.setEnabled(True)

    def enable_qt_objects(self, enable: bool):
        buttons = [
            self.ui.process_pushButton,
            self.ui.plot_marks_pushButton,
            self.ui.plot_track_pushButton,
            self.ui.export_pushButton,
            self.ui.import_pushButton,
            self.ui.roverpath_lineEdit,
            self.ui.roverpath_pushButton,
            self.ui.RevolutionCheckBox,
            self.ui.EpochsNumberLabel,
            self.ui.EpochsNumberSpinBox,
            self.ui.basepath_lineEdit,
            self.ui.basepath_pushButton,
            self.ui.crs_pushButton,
            self.ui.north_lineEdit,
            self.ui.east_lineEdit,
            self.ui.height_lineEdit,
            self.ui.antennaH_lineEdit,
            self.ui.antennaTypeComboBox,
            self.ui.elv_mask_spinBox,
            self.ui.glonass_checkBox,
            self.ui.excluded_sats_lineEdit,
            self.ui.telemetrypath1_lineEdit,
            self.ui.telemetrypath1_pushButton,
            self.ui.telemetrypath2_lineEdit,
            self.ui.telemetrypath2_pushButton,
            self.ui.telemetry1_checkBox,
            self.ui.telemetry2_checkBox,
        ]

        for button in buttons:
            button.setEnabled(enable)

    def find_rinex_files(self, obs_path):
        dir_, obs = os.path.dirname(obs_path), os.path.basename(obs_path)
        nav = None
        gnav = None
        for file in filter(lambda x: os.path.splitext(x)[0] == os.path.splitext(obs)[0], os.listdir(dir_)):
            name, ext = os.path.splitext(file)
            if re.match(r"\.(?:\d\d[nN]|nav|NAV)", ext):
                nav = os.path.join(dir_, file)
            if re.match(r"\.(?:\d\d[gG]|gnav|GNAV)", ext):
                gnav = os.path.join(dir_, file)

        return obs_path, nav, gnav

    def import_to_chunk(self):
        chunk = Metashape.app.document.chunk
        chunk.crs = self.crs

        for merger, name, qt_obj in [(self.merger1, "merged_events1.xml", self.ui.telemetry1_checkBox),
                                     (self.merger2, "merged_events2.xml", self.ui.telemetry2_checkBox)]:
            if not qt_obj.isChecked() or merger is None:
                continue

            if len(chunk.cameras) > 0:
                merger.write_merged_xml()

                chunk.importReference(path=os.path.join(self.processing_dir, name),
                                      format=Metashape.ReferenceFormat.ReferenceFormatXML,
                                      crs=self.crs)
            else:
                Metashape.app.messageBox(_("No cameras in chunk"))

    def plot_thread(self, plot_func):
        thread = Thread(target=plot_func)
        thread.start()

    def plot_track(self):
        subprocess.run([self.rtkplot, os.path.join(self.processing_dir, 'ppk_track.pos')])

    def plot_marks(self):
        subprocess.run([self.rtkplot, os.path.join(self.processing_dir, 'ppk_track_events.pos')])

    def plot_base(self):
        base_path = os.path.abspath(self.ui.basepath_lineEdit.text())
        if base_path:
            subprocess.run([self.rtkplot, base_path])
        else:
            Metashape.app.messageBox(textwrap.fill(SET_PATH_TO_PLOT, 65))

    def plot_rover(self):
        rover_path = os.path.abspath(self.ui.roverpath_lineEdit.text())
        if rover_path:
            subprocess.run([self.rtkplot, rover_path])
        else:
            Metashape.app.messageBox(textwrap.fill(SET_PATH_TO_PLOT, 65))

    def fill_antenna_types(self):
        antennas = get_antennas()
        self.ui.antennaTypeComboBox.addItems(antennas)

    def enable_epochs_number(self):
        status = self.ui.RevolutionCheckBox.isChecked()
        self.ui.EpochsNumberLabel.setEnabled(status)
        self.ui.EpochsNumberSpinBox.setEnabled(status)

    def set_antenna_values(self):
        path = self.ui.basepath_lineEdit.text()
        if os.path.exists(path) and re.search(r".*\.\d\d[oO]|.*\.obs|.*\.OBS", path):
            h = RinexParser.get_antenna_height(path)
            if h:
                self.ui.antennaH_lineEdit.setText(str(h))
            else:
                self.ui.antennaH_lineEdit.setText(str(0))
            antenna_type = RinexParser.get_antenna_type(path)
            index = self.ui.antennaTypeComboBox.findText(antenna_type, QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.ui.antennaTypeComboBox.setCurrentIndex(index)
        else:
            self.ui.antennaH_lineEdit.setText("None")
            self.ui.antennaTypeComboBox.setCurrentIndex(0)

    def telemetry2_enable(self):
        self.ui.telemetrypath2_lineEdit.setEnabled(self.ui.telemetry2_checkBox.isChecked())
        self.ui.telemetrypath2_pushButton.setEnabled(self.ui.telemetry2_checkBox.isChecked())

    def export_merged_result(self):
        saved_file = QtWidgets.QFileDialog.getExistingDirectory(
            self.ui,
            _("Select directory to save files with merged telemetry and GNSS data"),
            os.path.dirname(self.ui.telemetrypath1_lineEdit.text()))

        if saved_file:
            if self.merger1:
                xml1 = os.path.join(self.processing_dir, self.merger1.title + '.xml')
                txt1 = os.path.join(self.processing_dir, self.merger1.title + '.txt')
                self.merger1.write_merged_xml(path=xml1)
                self.merger1.write_merged_txt(path=txt1)
                copy(xml1, os.path.join(saved_file, self.merger1.title + '.xml'))
                copy(txt1, os.path.join(saved_file, self.merger1.title + '.txt'))

            if self.merger2:
                xml2 = os.path.join(self.processing_dir, self.merger2.title + '.xml')
                txt2 = os.path.join(self.processing_dir, self.merger2.title + '.txt')
                self.merger2.write_merged_xml(path=xml2)
                self.merger2.write_merged_txt(path=txt2)
                copy(xml2, os.path.join(saved_file, self.merger2.title + '.xml'))
                copy(txt2, os.path.join(saved_file, self.merger2.title + '.txt'))

            subprocess.call('explorer {}'.format(os.path.abspath(saved_file)))


if __name__ == '__main__':
    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()
    window = GnssProcessor(parent)

    window.ui.show()






