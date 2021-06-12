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
import subprocess
import tempfile
import multiprocessing
import concurrent.futures
import traceback
from datetime import datetime
from shutil import copy, rmtree
from threading import Thread
import re

from PySide2 import QtCore, QtWidgets, QtGui
import Metashape

from common.loggers.email_logger import log_method_by_crash_reporter
from common.utils.dump_userdata import UserDataDump, CustomSave
from common.qt_wrapper.helpers import open_dir
from common.utils.ui import show_progress, init_progress
from gnss_post_processing.app.meta import NAME, VERSION

from gnss_post_processing.app.utils.antennas import get_antennas
from gnss_post_processing.app.utils.error_handlers import check_missed_flights_data, is_correct_rover_data, \
    custom_user_error
from gnss_post_processing.app.utils.exceptions import InputDataError, IndexErrorInPosFile, NoEpochs, NoEvents
from gnss_post_processing.app.utils.helpers import set_crs, open_base_rinex, find_flights_data, \
    find_matches_in_flights_data, is_rinex, copy_rinex, upgrade_rover_rinex, create_configuration_file, \
    update_gnss_processing_parameters, rtklib_solutions, merge_telemetry_with_gnss, create_report
from gnss_post_processing.app.utils.pos_parser import PosParser


class SingleBaseMultipleFlights:
    def __init__(self, ui, rnx2rtkp, rtklib_config, igs14, rtkplot):
        self.ui = ui
        self.rnx2rtkp = rnx2rtkp
        self.igs14 = igs14
        self.rtklib_config = rtklib_config
        self.rtkplot = rtkplot

        self.crs = Metashape.CoordinateSystem()
        self.matches = None
        self.processing = dict()

        self.saver = UserDataDump(directory=os.path.dirname(__file__), filename='singlebase_multipleflights',
                                  parent=self, create_cache_dir=True)
        self.saver.create_and_update(
            tab2_BaseLineEdit="",
            tab2_BaseNorthLineEdit="", tab2_BaseEastLineEdit="", tab2_BaseHeightLineEdit="",
            tab2_BaseAntennaHeightLineEdit="",
            tab2_InputDataLineEdit="",
            __crs=CustomSave(item=Metashape.CoordinateSystem("EPSG::4326").wkt,
                             set_func="set_crs_userdata", extract_func="extract_crs_userdata")
        )

        self.saver.upload_to_ui(self.ui)
        self.ui.tab2_PlotBasePushButton.setText("\u2315")

        self.not_strict_overlap, self.refine_by_geoscan_name, \
        self.use_date, self.use_flight_type, self.use_drone_id, self.use_flight_id = SearchFlightsSettings.values()
        self.connect_buttons()

    def log_values(self):
        return {}

    def set_crs_userdata(self, item):
        self.crs.init(item)
        self.ui.tab2_CrsNameLabel.setText(self.crs.name)

    def extract_crs_userdata(self):
        return self.crs.wkt

    def plot_thread(self, plot_func):
        thread = Thread(target=plot_func)
        thread.start()

    def connect_buttons(self):
        def check_all(status):
            table = self.ui.tab2_tableWidget
            is_enable = QtCore.Qt.Checked if status else QtCore.Qt.Unchecked
            for row in range(table.rowCount()):
                table.item(row, 0).setCheckState(is_enable)

        def fill_antenna_types():
            antennas = get_antennas()
            self.ui.tab2_BaseAntennaTypeComboBox.addItems(antennas)

        def open_base(new_file):
            main_directory = os.path.dirname(self.ui.tab2_BaseLineEdit.text()) if self.ui.tab2_BaseLineEdit.text() else False
            return open_base_rinex(ui=self.ui,
                                   line_edit=self.ui.tab2_BaseLineEdit,
                                   antenna_height_line_edit=self.ui.tab2_BaseAntennaHeightLineEdit,
                                   antenna_type_combobox=self.ui.tab2_BaseAntennaTypeComboBox,
                                   plot_rinex_button=self.ui.tab2_PlotBasePushButton,
                                   new_file=new_file,
                                   main_directory=main_directory)

        def full_files_paths():
            if self.ui.tab2_FullPathCheckBox.isChecked() and self.matches is not None:
                self.fill_table(self.matches, full_path=True, update=True)
            if not self.ui.tab2_FullPathCheckBox.isChecked() and self.matches is not None:
                self.fill_table(self.matches, full_path=False, update=True)

        def plot_base():
            if self.ui.tab2_BaseLineEdit.text():
                thread = Thread(target=lambda: subprocess.run([self.rtkplot, self.ui.tab2_BaseLineEdit.text()]))
                thread.start()

        def init_settings():
            dlg = SearchFlightsSettings(parent=self.ui)
            self.not_strict_overlap, self.refine_by_geoscan_name, \
            self.use_date, self.use_flight_type, self.use_drone_id, self.use_flight_id = dlg.exec_()

        fill_antenna_types()
        open_base(new_file=False)

        self.ui.tab2_BaseLineEdit.textChanged.connect(lambda: open_base(new_file=False))
        self.ui.tab2_BasePushButton.clicked.connect(lambda: open_base(new_file=True))
        self.ui.tab2_PlotBasePushButton.clicked.connect(plot_base)

        self.ui.tab2_CrsSetPushButton.clicked.connect(lambda: set_crs(parent=self, line_edit=self.ui.tab2_CrsNameLabel))
        self.ui.tab2_InputDataPushButton.clicked.connect(
            lambda: open_dir(ui=self.ui,
                             line_edit=self.ui.tab2_InputDataLineEdit,
                             main_directory=self.ui.tab2_InputDataLineEdit.text() if self.ui.tab2_InputDataLineEdit.text() else False)
        )
        self.ui.tab2_FullPathCheckBox.stateChanged.connect(full_files_paths)
        self.ui.tab2_pushButton.clicked.connect(self.find_data)
        self.ui.tab2_UncheckPushButton.clicked.connect(lambda: check_all(False))
        self.ui.process_pushButton.clicked.connect(self.run)
        self.ui.tab2_FindFlightsSettingsPushButton.clicked.connect(init_settings)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def find_data(self):
        self.table.clear()

        if not (self.flights_data_dir and os.path.exists(self.flights_data_dir)):
            custom_user_error(text=_("Invalid path to flights directory."), write_to_status=False)
            return

        if not (self.base_rinex and os.path.exists(self.base_rinex)) or not is_rinex(self.base_rinex):
            custom_user_error(text=_("Invalid path to base RINEX file."), write_to_status=False)
            return

        progress_start = init_progress(_("Searching flights..."))
        rinex_files, telemetry_files = find_flights_data(self.flights_data_dir)
        progress = show_progress(progress=progress_start, label=_("Identifying flights data..."),
                                 value_func=lambda i: i / len(rinex_files) * 100)
        self.matches, missed = find_matches_in_flights_data(rinex_files=rinex_files, telemetry_files=telemetry_files,
                                                            base=self.base_rinex,
                                                            refine_by_geoscan_name=self.refine_by_geoscan_name,
                                                            use_date=self.use_date,
                                                            use_flight_type=self.use_flight_type,
                                                            use_drone_id=self.use_drone_id,
                                                            use_flight_id=self.use_flight_id,
                                                            not_strict_overlap=self.not_strict_overlap,
                                                            progress_func=progress)
        self.fill_table(self.matches, full_path=self.is_full_paths_in_table, update=False)
        check_missed_flights_data(missed)

    def fill_table(self, matches, full_path=False, update=False):
        def set_enabled_status(column=0):
            checkbox_item = QtWidgets.QTableWidgetItem()
            checkbox_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            status = QtCore.Qt.Checked if not update else table.item(row, column).checkState()
            checkbox_item.setCheckState(status)
            table.setItem(row, column, checkbox_item)

        table = self.table
        if not update:
            table.setRowCount(0)

            table.setColumnCount(3)
            table.setRowCount(len(matches))
            table.setHorizontalHeaderLabels(["\u2705", _("Rover files"), _("Geoscan telemetry")])

            header = table.horizontalHeader()
            table.setColumnWidth(0, 50)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
            table.horizontalHeaderItem(1).setTextAlignment(QtCore.Qt.AlignHCenter)
            table.horizontalHeaderItem(2).setTextAlignment(QtCore.Qt.AlignHCenter)

        for row, match in enumerate(matches):
            set_enabled_status()
            rinex = match['rinex']
            rinex_path = rinex if full_path else os.path.basename(rinex)
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(rinex_path))
            telemetry = match['telemetry']
            telemetry_path = telemetry if full_path else os.path.basename(telemetry)
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(telemetry_path))

        self.ui.setMaximumSize(1005, 950)
        self.ui.resize(1005, 950)

    def run(self):
        if self.active_tab != 1:
            return
        if self.matches is None:
            return

        export_path = Metashape.app.getExistingDirectory()

        self.ui.status_Label.setText("Collecting base station data...")
        Metashape.app.update()

        filtered_matches = list(filter(lambda item: self.match_is_checked(row=item[0]), enumerate(self.matches)))

        common_dir = os.path.join(tempfile.gettempdir(), "gnss_temp_{}".format(datetime.now().strftime("%m_%d_%H_%M_%S")))
        base_obs, base_nav, base_gnav = self.init_base_file(common_dir=common_dir)

        unexpected_errors = list()
        i = 0
        self.update_progress(i, len(filtered_matches))
        with concurrent.futures.ThreadPoolExecutor(multiprocessing.cpu_count()) as executor:
            futures = dict()
            for n, match in filtered_matches:
                future = executor.submit(self.create_task, export_path=export_path, match=match,
                                         common_dir=common_dir,
                                         base_obs=base_obs, base_nav=base_nav, base_gnav=base_gnav)
                futures[future] = match

            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                    i += 1
                    self.update_progress(i, len(filtered_matches))
                except Exception:
                    match = futures[future]
                    match_name = os.path.splitext(os.path.basename(match['rinex']))[0] + '_' + \
                                 os.path.splitext(os.path.basename(match['telemetry']))[0]
                    unexpected_errors.append((match_name, traceback.format_exc()))

        rmtree(common_dir)

        report_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        with open(os.path.join(export_path, 'processing_log_{}.txt'.format(report_time)), 'w') as file:
            unexpected_errors_str = "\n\n".join(["{}: {}".format(match, error) for match, error in unexpected_errors])
            processing_descriptions = "\n\n".join([str(k) + str(v) for k, v in self.processing.items()])
            file.write(unexpected_errors_str + '\n\n' + processing_descriptions)

        create_report(processing_data=self.processing, export_dir=export_path, report_time=report_time)
        self.ui.status_Label.setText("Finished!")

    def create_task(self, export_path, match, common_dir, base_obs, base_nav, base_gnav):
        match_name = self.collect_data_for_match(
            match=match,
            common_dir=common_dir,
            base_obs=base_obs, base_nav=base_nav, base_gnav=base_gnav)
        if match_name is not None:
            self.process_by_rtklib(export_path=export_path, processing_item=self.processing[match_name], name=match_name)
            rmtree(os.path.join(common_dir, match_name))

    def update_progress(self, value, total):
        self.ui.status_Label.setText("Processing tasks... [{} / {}]".format(value, total))
        Metashape.app.update()

    def init_base_file(self, common_dir):
        base_dir = os.path.join(common_dir, 'base_st')
        if not os.path.exists(common_dir):
            os.makedirs(common_dir)
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        base_obs, base_nav, base_gnav = copy_rinex(path=self.base_rinex, processing_dir=base_dir)
        return base_obs, base_nav, base_gnav

    def collect_data_for_match(self, match, common_dir, base_obs, base_nav, base_gnav):
        error = False

        rinex_name = os.path.splitext(os.path.basename(match['rinex']))[0]
        telemetry_name = os.path.splitext(os.path.basename(match['telemetry']))[0]
        match_name = rinex_name + '_' + telemetry_name
        self.processing[match_name] = {'input': {}, 'errors': [], 'warnings': {}, 'solutions': {}}
        rover_path, telemetry1 = match['rinex'], match['telemetry']
        processing_dir = os.path.join(common_dir, match_name)
        if not os.path.exists(processing_dir):
            os.makedirs(processing_dir)
        copy_rinex(path=rover_path, processing_dir=processing_dir, exclude_list=['o'])
        try:
            upgraded_rover_obs, start_obs, end_obs, rinex_parser = upgrade_rover_rinex(rover_path, processing_dir)
            is_correct_rover_data(rp=rinex_parser, parent=self.ui,
                                  transfer_warnings_to_list=self.processing[match_name]['warnings'])
        except (InputDataError, NoEvents, NoEpochs) as e:
            self.processing[match_name]['errors'].append("{}: {}".format(type(e).__name__, e))
            error = True

        config_path = os.path.join(processing_dir, 'rtklib_configuration.conf')
        self.processing[match_name]['warnings']['missed_events'] = [x['data'] for x in rinex_parser.missed_events] if not error else [""]
        self.processing[match_name]['input']['processing_dir'] = processing_dir
        self.processing[match_name]['input']['base_obs'] = base_obs
        self.processing[match_name]['input']['base_nav'] = base_nav
        self.processing[match_name]['input']['base_gnav'] = base_gnav
        self.processing[match_name]['input']['rover_obs'] = upgraded_rover_obs if not error else None
        self.processing[match_name]['input']['source_rover_obs'] = rover_path
        self.processing[match_name]['input']['start_obs'] = start_obs if not error else None
        self.processing[match_name]['input']['end_obs'] = end_obs if not error else None
        self.processing[match_name]['input']['config'] = config_path
        self.processing[match_name]['input']['telemetry'] = match['telemetry']

        return match_name if not error else None

    def match_is_checked(self, row, column=0):
        return self.table.item(row, column).checkState() == QtCore.Qt.Checked

    def process_by_rtklib(self, export_path, processing_item, name):
        match_name = name
        data = processing_item['input']
        warnings = processing_item['warnings']
        errors = processing_item['errors']
        SOLUTIONS = rtklib_solutions()
        try:
            results = dict()
            for sol in SOLUTIONS.keys():
                sol_dir = os.path.join(data['processing_dir'], sol)
                if not os.path.exists(sol_dir):
                    os.makedirs(sol_dir)
                results[sol] = {'path': sol_dir, 'quality': -1}
            for i, solution in enumerate(SOLUTIONS.keys()):
                self.init_configuration_file(path=data['config'], solution=solution)
                args = [self.rnx2rtkp,
                        '-k', data['config'],
                        '-o', os.path.join(results[solution]['path'], 'ppk_track.pos'),
                        '-ts', "{}/{}/{}".format(data['start_obs'].year, data['start_obs'].month, data['start_obs'].day),
                        "{}:{}:{}".format(data['start_obs'].hour, data['start_obs'].minute, data['start_obs'].second),
                        '-te', "{}/{}/{}".format(data['end_obs'].year, data['end_obs'].month, data['end_obs'].day),
                        "{}:{}:{}".format(data['end_obs'].hour, data['end_obs'].minute, data['end_obs'].second),
                        data['rover_obs'], data['base_obs'], data['base_nav']]
                if self.is_glonass and data['base_gnav']:
                    args.append(data['base_gnav'])

                subprocess.run(args)
                pos_events = os.path.join(results[solution]['path'], 'ppk_track_events.pos')
                if not os.path.exists(pos_events):
                    continue
                pos_parser = PosParser(file=pos_events)
                results[solution]['quality'] = pos_parser.quality
                self.processing[match_name]['solutions'][solution] = round(pos_parser.quality, 3)
                if pos_parser.quality > 95:
                    break

            success_solution = max(results, key=lambda sol: results[sol]['quality'])
            merger = merge_telemetry_with_gnss(
                processing_dir=data['processing_dir'],
                pos_file=os.path.join(results[success_solution]['path'], 'ppk_track_events.pos'),
                telemetry_file=data['telemetry'],
                crs=self.crs,
                quality=results[success_solution]['quality'],
                silently=True
            )
            if merger is not None:
                telemetry_name = os.path.splitext(os.path.basename(data['telemetry']))[0]
                name = re.sub(r"_(?:telemetry|photo[sS]can)", '_GNSS', telemetry_name)
                merger.write_merged_xml(os.path.join(export_path, name + '.xml'))
                merger.write_merged_txt(os.path.join(export_path, name + '.txt'))

                copy(os.path.join(results[success_solution]['path'], 'ppk_track_events.pos'),
                     os.path.join(data['processing_dir'], 'ppk_track_events.pos'))
                copy(os.path.join(results[success_solution]['path'], 'ppk_track.pos'),
                     os.path.join(data['processing_dir'], 'ppk_track.pos'))
            else:
                errors.append("Merge error with {} and {}".format(data['telemetry'], data['rover_obs']))

        except Exception as e:
            if type(e) in [IndexErrorInPosFile]:
                errors.append("IndexErrorInPosFile")
            else:
                errors.append(traceback.format_exc())

    def init_configuration_file(self, path, solution=None):
        north, east, height = self.base_coordinates
        gnss_data = update_gnss_processing_parameters(
            antenna_height=self.antenna_height,
            base_north=north, base_east=east, base_height=height,
            antenna_type=self.antenna_type,
            is_gps=self.is_gps, is_glonass=self.is_glonass, elevation_mask=self.elevation_mask,
            excluded_sats=self.excluded_sats,
            crs=self.crs
        )
        solution = rtklib_solutions()[solution] if solution is not None else rtklib_solutions()['forward']
        create_configuration_file(source_file=self.rtklib_config, igs14=self.igs14,
                                  solution=solution,
                                  new_config=path, gnss_data=gnss_data)

    @property
    def base_rinex(self):
        return self.ui.tab2_BaseLineEdit.text()

    @property
    def base_coordinates(self):
        return (self.ui.tab2_BaseNorthLineEdit.text(),
                self.ui.tab2_BaseEastLineEdit.text(),
                self.ui.tab2_BaseHeightLineEdit.text())

    @property
    def antenna_height(self):
        return self.ui.tab2_BaseAntennaHeightLineEdit.text()

    @property
    def antenna_type(self):
        return self.ui.tab2_BaseAntennaTypeComboBox.currentText()

    @property
    def flights_data_dir(self):
        return self.ui.tab2_InputDataLineEdit.text()

    @property
    def is_full_paths_in_table(self):
        return self.ui.tab2_FullPathCheckBox.isChecked()

    @property
    def table(self):
        return self.ui.tab2_tableWidget

    #processing parameters
    @property
    def is_gps(self):
        return self.ui.gps_checkBox.isChecked()

    @property
    def is_glonass(self):
        return self.ui.glonass_checkBox.isChecked()

    @property
    def elevation_mask(self):
        return self.ui.elv_mask_spinBox.value()

    @property
    def excluded_sats(self):
        return self.ui.excluded_sats_lineEdit.text()

    @property
    def active_tab(self):
        return self.ui.tabWidget.currentIndex()


class SearchFlightsSettings(QtWidgets.QDialog):
    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.initUI()
        self.saver = UserDataDump(directory=os.path.dirname(__file__), filename='searchflights_settings',
                                  parent=self, create_cache_dir=True)
        self.saver.create_and_update(
            strict_overlap=True,
            not_strict_overlap=False,
            refine_by_geoscan_name=True,
            use_date=True,
            use_flight_type=False,
            use_drone_id=True,
            use_flight_id=True,
        )

        self.saver.upload_to_ui(self)

    def initUI(self):
        self.setWindowTitle(_("Search flights settings"))

        self.verticalLayout = QtWidgets.QVBoxLayout()

        self.strict_overlap = QtWidgets.QRadioButton(_("Telemetry time bounds must be within "
                                                       "rover RINEX time bounds"))
        self.verticalLayout.addWidget(self.strict_overlap)
        self.not_strict_overlap = QtWidgets.QRadioButton(_("Telemetry time bounds must overlap "
                                                           "rover RINEX time bounds"))
        self.verticalLayout.addWidget(self.not_strict_overlap)

        self.verticalSpacer = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.verticalLayout.addItem(self.verticalSpacer)

        self.refine_by_geoscan_name = QtWidgets.QGroupBox()
        self.refine_by_geoscan_name.setTitle(_("* Use Geoscan filenames to refine matches"))
        self.refine_by_geoscan_name.setCheckable(True)

        self.gbLayout = QtWidgets.QVBoxLayout(self.refine_by_geoscan_name)

        self.use_date = QtWidgets.QCheckBox(self.refine_by_geoscan_name)
        self.use_date.setText(_("Use date"))
        self.gbLayout.addWidget(self.use_date)
        self.use_flight_type = QtWidgets.QCheckBox(self.refine_by_geoscan_name)
        self.use_flight_type.setText(_("Use flight type"))
        self.gbLayout.addWidget(self.use_flight_type)
        self.use_drone_id = QtWidgets.QCheckBox(self.refine_by_geoscan_name)
        self.use_drone_id.setText(_("Use drone id"))
        self.gbLayout.addWidget(self.use_drone_id)
        self.use_flight_id = QtWidgets.QCheckBox(self.refine_by_geoscan_name)
        self.use_flight_id.setText(_("Use flight id"))
        self.gbLayout.addWidget(self.use_flight_id)
        self.desc = QtWidgets.QLabel(self.refine_by_geoscan_name)
        self.desc.setText(_("* Required part of filename (example):\n"
                                       "name: 2020_07_22_reg36_g201b20395_f077, where\n\n"
                                       "date: 2020_07_22,\n"
                                       "flight type: reg36,\n"
                                       "drone id: g201b20395,\n"
                                       "flight id: f077"))
        self.gbLayout.addWidget(self.desc)

        self.verticalLayout.addWidget(self.refine_by_geoscan_name)
        self.setLayout(self.verticalLayout)

    def exec_(self):
        super(SearchFlightsSettings, self).exec_()
        self.saver.dump_from_ui(self)
        return self.is_not_strict_overlap(), self.is_refine_by_geoscan_name(), \
               self.use_date.isChecked(), self.use_flight_type.isChecked(),\
               self.use_drone_id.isChecked(), self.use_flight_id.isChecked()

    def is_refine_by_geoscan_name(self):
        return self.refine_by_geoscan_name.isChecked()

    def is_not_strict_overlap(self):
        return self.not_strict_overlap.isChecked()

    @classmethod
    def values(cls):
        import shelve
        cache = os.path.join(os.path.dirname(__file__), '.cache', 'searchflights_settings.dat')
        if not os.path.exists(cache):
            return False, True, True, False, True, True
        else:
            with shelve.open(os.path.join(os.path.dirname(__file__), '.cache', 'searchflights_settings')) as f:
                try:
                    return f['not_strict_overlap'], f['refine_by_geoscan_name'], \
                           f['use_date'], f['use_flight_type'], f['use_drone_id'], f['use_flight_id']
                except Exception:
                    return False, True, True, False, True, True
