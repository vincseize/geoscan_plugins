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
from datetime import datetime
from shutil import copy
from typing import Callable

from PySide2 import QtCore
import Metashape

from common.qt_wrapper.helpers import open_file
from common.utils.flight_info_tools.parse_filenames import parse_cam_name_string
from gnss_post_processing.app.utils.exceptions import TelemetryTimeError
from gnss_post_processing.app.utils.rinex_parser import RinexParser, get_rinex_time_bounds
from gnss_post_processing.app.utils.telemetry_merger import PositionMerger, reproject_point


def set_crs(parent, line_edit=None):
    crs = Metashape.app.getCoordinateSystem()
    if crs:
        parent.crs = crs
        line_edit.setText(parent.crs.name)


def open_base_rinex(ui, line_edit, antenna_height_line_edit, antenna_type_combobox, plot_rinex_button,
                    new_file: bool, main_directory="."):
    """Open base's RINEX file with filling antenna height and antenna type options."""

    path = open_file(ui=ui, line_edit=line_edit, main_directory=main_directory) if new_file else line_edit.text()
    if path is None or not os.path.isfile(path):
        return

    antenna_height = RinexParser.get_antenna_height(path)
    antenna_height_line_edit.setText(str(antenna_height) if antenna_height else str(0))
    antenna_type = RinexParser.get_antenna_type(path)
    if antenna_type:
        index = antenna_type_combobox.findText(antenna_type, QtCore.Qt.MatchFixedString)
        if index >= 0:
            antenna_type_combobox.setCurrentIndex(index)
    else:
        antenna_type_combobox.setCurrentIndex(0)
    plot_rinex_button.setEnabled(True)


def is_geoscan_telemetry(filename):
    return True if re.search(r"_(?:telemetry|photoscan).txt", filename.lower()) else False


def get_time_from_geoscan_telemetry(path, time_column='time'):
    with open(path, 'r', encoding='utf8') as file:
        data = file.readlines()

    i = 0
    while data[i].startswith('#'):
        i += 1

    title = data[i-1].split()
    title.pop(0)
    try:
        time_index = title.index(time_column)
    except ValueError:
        return None, None

    for k in range(i, len(data)):
        line = data[k].split("\t")
        if len(line) == len(title):
            try:
                time = PositionMerger.get_date_from_telemetry_line(time_line=line, title_index=time_index)
            except (ValueError, IndexError):
                continue
        else:
            continue

        if time:
            start_time = time
            break
    else:
        # return None, None
        raise TelemetryTimeError("No line with start time was found")

    for k in range(len(data)-1, i, -1):
        line = data[k].split("\t")
        if len(line) == len(title):
            time = PositionMerger.get_date_from_telemetry_line(time_line=line, title_index=time_index)
        else:
            continue

        if time:
            end_time = time
            break
    else:
        return None, None
        # raise TelemetryTimeError("No line with end time was found")

    return start_time, end_time


def is_rinex(filename):
    return True if re.search(r".*\.\d\d[oO]|.*\.obs|.*\.OBS", filename) else False


def find_flights_data(path):
    """Find RINEX files and Geoscan telemetry files in directory"""

    telemetry_files = list()
    rinex_files = list()

    for root, dirs, files in os.walk(path):
        for file in files:
            if is_geoscan_telemetry(file):
                telemetry_files.append(os.path.join(root, file))
            if is_rinex(file):
                rinex_files.append(os.path.join(root, file))
    return rinex_files, telemetry_files


def has_time_overlap(A_start, A_end, B_start, B_end):
    latest_start = max(A_start, B_start)
    earliest_end = min(A_end, B_end)
    return latest_start <= earliest_end


def has_time_full_overlap(A_start, A_end, B_start, B_end):
    """A - rover, B - telemetry file"""
    start_in = A_start <= B_start < A_end
    end_in = A_start < B_end <= A_end
    return start_in and end_in


def get_uav_name_from_filename(name):
    pattern = re.compile(r"g\d\d\db\d*")
    res = re.search(pattern, name)
    return res.group() if res else None


def find_matches_in_flights_data(rinex_files, telemetry_files, base: (None, str) = None,
                                 refine_by_geoscan_name: bool = True,
                                 use_date: bool = True,
                                 use_flight_type: bool = True,
                                 use_drone_id: bool = True,
                                 use_flight_id: bool = True,
                                 not_strict_overlap: bool = False,
                                 progress_func: Callable = lambda x: x):
    """Find matches between RINEX files and Geoscan telemetry files"""

    return find_matches_by_time_bounds(rinex_files, telemetry_files, base,
                                       refine_by_geoscan_name=refine_by_geoscan_name,
                                       use_date=use_date,
                                       use_flight_type=use_flight_type,
                                       use_drone_id=use_drone_id,
                                       use_flight_id=use_flight_id,
                                       not_strict_overlap=not_strict_overlap,
                                       progress_func=progress_func)


def find_matches_by_time_bounds(rinex_files, telemetry_files, base: (None, str) = None,
                                refine_by_geoscan_name: bool = False,
                                use_date: bool = True,
                                use_flight_type: bool = True,
                                use_drone_id: bool = True,
                                use_flight_id: bool = True,
                                not_strict_overlap: bool = False,
                                progress_func: Callable = lambda x: x):
    """Find matches between RINEX files and Geoscan telemetry files by time bounds"""

    matches = list()
    time_error = _('time error')
    no_time_overlap = _('no time overlap or equal name with other files')
    not_rover = _('not rover')
    not_for_selected_base = _('not for selected Base RINEX')
    missed = {
        time_error: {'telemetry': [], 'rinex': []},
        no_time_overlap: {'telemetry': [], 'rinex': []},
        not_rover: {"rinex": []},
        not_for_selected_base: {"rinex": [], "telemetry": []},
    }
    used_telemetries = set()
    if base is not None:
        base_start, base_end = get_rinex_time_bounds(base)
    else:
        base_start, base_end = datetime.min, datetime.max

    check_overlap = has_time_overlap if not_strict_overlap else has_time_full_overlap

    for i in range(len(rinex_files)):
        progress_func(i)

        r_start, r_end, is_rover = RinexParser.get_start_end_times(rinex_files[i], identify_rover=True)
        if not is_rover:
            missed[not_rover]['rinex'].append(rinex_files[i])
            rinex_files[i] = None
            continue

        if r_start is None or r_end is None:
            missed[time_error]['rinex'].append(rinex_files[i])
            rinex_files[i] = None
            continue

        if r_start > base_end or r_end < base_start:
            missed[not_for_selected_base]['rinex'].append(rinex_files[i])
            rinex_files[i] = None
            continue

        if refine_by_geoscan_name:
            r_day, r_fltype, r_bort, r_flnum = parse_cam_name_string(os.path.basename(rinex_files[i]))
        else:
            r_day, r_fltype, r_bort, r_flnum = None, None, None, None

        for k in range(len(telemetry_files)):
            if telemetry_files[k] is None:
                continue

            t_start, t_end = get_time_from_geoscan_telemetry(telemetry_files[k])
            if t_start is None or t_end is None:
                missed[time_error]['telemetry'].append(telemetry_files[k])
                telemetry_files[k] = None
                continue

            if t_start < base_start or t_end > base_end:
                missed[not_for_selected_base]['telemetry'].append(telemetry_files[k])
                telemetry_files[k] = None
                continue

            if refine_by_geoscan_name:
                t_day, t_fltype, t_bort, t_flnum = parse_cam_name_string(os.path.basename(telemetry_files[k]))
                if use_date and r_day != t_day:
                    continue
                if use_flight_type and r_fltype != t_fltype:
                    continue
                if use_drone_id and r_bort != t_bort:
                    continue
                if use_flight_id and r_flnum != t_flnum:
                    continue

            if check_overlap(A_start=r_start, A_end=r_end, B_start=t_start, B_end=t_end):
                matches.append({'telemetry': telemetry_files[k], 'rinex': rinex_files[i]})
                used_telemetries.add(os.path.basename(telemetry_files[k]))
        rinex_files[i] = None

    missed[no_time_overlap]['rinex'].extend([x for x in rinex_files if x is not None])
    telemetry_overlaps = [x for x in telemetry_files if x is not None and os.path.basename(x) not in used_telemetries]
    missed[no_time_overlap]['telemetry'].extend(telemetry_overlaps)

    is_missed = False
    for reason, data in missed.items():
        for datatype, files in data.items():
            if files:
                is_missed = True
                break

    return matches, missed if is_missed else None


def copy_rinex(path, processing_dir, exclude_list=None):
    if not exclude_list:
        exclude_list = list()
    name = os.path.splitext(os.path.basename(path))[0]
    obs_files = [x for x in os.listdir(os.path.dirname(path)) if os.path.splitext(x)[0] == name]
    obs, nav, gnav = None, None, None
    for file in obs_files:
        source = os.path.join(os.path.dirname(path), file)
        filename, ext = os.path.splitext(file)
        if 'g' not in exclude_list and ('g' in ext or 'G' in ext):
            copy(source, os.path.join(processing_dir, filename + '.gnav'))
            gnav = os.path.join(processing_dir, filename + '.gnav')
        if 'n' not in exclude_list and ('n' in ext or 'N' in ext):
            copy(source, os.path.join(processing_dir, filename + '.nav'))
            nav = os.path.join(processing_dir, filename + '.nav')
        if 'o' not in exclude_list and ('o' in ext or 'O' in ext):
            copy(source, os.path.join(processing_dir, filename + '.obs'))
            obs = os.path.join(processing_dir, filename + '.obs')
    return obs, nav, gnav


def upgrade_rover_rinex(rover_path, processing_dir, use_epochs_limit=False):
    upgraded_rover = os.path.join(processing_dir, os.path.basename(rover_path).split('.')[0] + '.obs')
    rinex_parser = RinexParser(obs_file=rover_path)
    if use_epochs_limit:
        # epochs_number = int(int(self.ui.EpochsNumberSpinBox.value()) / 2)
        # rinex_parser.make_obs_rinex(path=self.upgraded_rover, epochs_buffer=epochs_number)
        raise NotImplementedError
    else:
        rinex_parser.make_obs_rinex(path=upgraded_rover, epochs_buffer=None)

    start_obs, end_obs = rinex_parser.meta.time_start, rinex_parser.meta.time_end
    if start_obs is None or end_obs is None:
        rinex_parser.get_start_end_times(upgraded_rover)

    return upgraded_rover, start_obs, end_obs, rinex_parser


def create_configuration_file(source_file, igs14, solution, new_config, gnss_data):
    with open(source_file, 'r') as file:
        lines = file.readlines()

    for i, line in enumerate(lines):
        if "pos1-soltype" in line:
            lines[i] = solution
        if "pos1-elmask" in line:
            lines[i] = re.sub('=.+', '={}'.format(gnss_data['elevation_mask']), line)
        elif "pos1-navsys" in line:
            value = 1  # gps
            if gnss_data['is_glonass']:
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
            sats = ''.join([x for x in gnss_data['excluded_sats']])
            lines[i] = re.sub('=.*', '={}'.format(sats), line)
        elif "ant2-pos1" in line:
            lines[i] = re.sub('=.*', '={}'.format(gnss_data['base_north']), line)
        elif "ant2-pos2" in line:
            lines[i] = re.sub('=.*', '={}'.format(gnss_data['base_east']), line)
        elif "ant2-pos3" in line:
            lines[i] = re.sub('=.*', '={}'.format(gnss_data['base_height']), line)
        elif "ant2-antdelu" in line:
            lines[i] = re.sub('=.*', '=0', line)
        elif "ant2-anttype" in line:
            lines[i] = re.sub('=.*', '={}'.format(gnss_data['antenna_type']), line)
        elif "file-rcvantfile" in line:
            lines[i] = "file-rcvantfile    ={}\n".format(igs14)
    with open(new_config, 'w') as file:
        for line in lines:
            file.write(line)


def update_gnss_processing_parameters(antenna_height: str, base_north: str, base_east: str, base_height: str,
                                      antenna_type: str,
                                      is_gps: bool, is_glonass: bool, elevation_mask: int, excluded_sats: str,
                                      crs: Metashape.CoordinateSystem):
    antenna_height = antenna_height.replace(",", ".")
    base_north = base_north.replace(",", ".")
    base_east = base_east.replace(",", ".")
    base_height = base_height.replace(",", ".")

    if crs.name != "WGS 84":
        base_height = base_height.replace(",", ".")
        reprojected_base = reproject_point(source_crs=crs,
                                           target_crs=Metashape.CoordinateSystem("EPSG::4326"),
                                           north=float(base_north),
                                           east=float(base_east),
                                           height=float(base_height))
        base_north = str(reprojected_base.y)
        base_east = str(reprojected_base.x)
        base_height = str(reprojected_base.z + float(antenna_height))
    else:
        base_height = str(float(base_height) + float(antenna_height))

    excluded_sats = excluded_sats.split(',')
    # for RINEX 3.x
    """
    self.is_galileo = self.ui.galileo_checkBox.isChecked()
    self.is_qzss = self.ui.qzss_checkBox.isChecked()
    self.is_sbas = self.ui.sbas_checkBox.isChecked()
    self.is_beidou = self.ui.beidou_checkBox.isChecked()
    self.is_irnss = self.ui.irnss_checkBox.isChecked()
    """
    if '' in [base_north, base_east, base_height, antenna_height] or None in [is_gps, is_glonass, elevation_mask]:
        Metashape.app.messageBox(_("Incorrect input data"))
        raise ValueError("Incorrect input data")

    return {"base_north": base_north, "base_east": base_east, "base_height": base_height, "antenna_type": antenna_type,
            "is_gps": is_gps, "is_glonass": is_glonass, "elevation_mask": elevation_mask, "excluded_sats": excluded_sats}


def merge_telemetry_with_gnss(processing_dir, pos_file, telemetry_file, crs, quality, silently=False):
    output = os.path.join(processing_dir, 'merged_events')
    chunk = Metashape.app.document.chunk
    extension = True if len(chunk.cameras) > 0 and len(chunk.cameras[0].label.split('.')) > 1 else False

    if telemetry_file and os.path.exists(telemetry_file):
        merger = PositionMerger(pos_file=pos_file, telemetry_file=telemetry_file, quality=quality,
                                output=output, extension=extension,
                                reproject=[Metashape.CoordinateSystem("EPSG::4326"), crs])
        merger.merge(silently=silently)
    else:
        merger = None
    return merger


def rtklib_solutions():
    return {"forward": "pos1-soltype       =forward\n",
            "backward": "pos1-soltype       =backward\n",
            "combined": "pos1-soltype       =combined\n"}


def create_report(processing_data, export_dir, report_time=""):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment

    wb = Workbook()
    ws = wb.active
    wrap_alignment = Alignment(wrap_text=True)

    ws.append(["Quality (fixed %)", "Missed events", "Telemetry file", "Rover RINEX", "System Errors"])

    rows = list()
    sort_func = lambda x: max(x[1]['solutions'].values()) if x[1]['solutions'].values() else -1
    for match_name, data in sorted(processing_data.items(), key=sort_func, reverse=True):
        solution_res = max(data['solutions'].values()) if data['solutions'].values() else 'No solution'
        rows.append([solution_res,
                     str(len(data['warnings']['missed_events'])),
                     data['input']['telemetry'],
                     data['input']['source_rover_obs'],
                     " ,".join(data['errors']),]
                    )

    for row in rows:
        ws.append(row)

    columns = list(ws.columns)
    for i in range(len(columns)):
        column_cells = columns[i]
        if i == 0:  # quality
            ws.column_dimensions[column_cells[0].column_letter].width = 15
        elif i == 1:  # missed events
            ws.column_dimensions[column_cells[0].column_letter].width = 15
        elif i == 4:
            ws.column_dimensions[column_cells[0].column_letter].width = 40
            for cell in column_cells:
                cell.alignment = wrap_alignment
        else:
            ws.column_dimensions[column_cells[0].column_letter].width = 80
            for cell in column_cells:
                cell.alignment = wrap_alignment

    wb.save(os.path.join(export_dir, "processing_report_{}.xlsx".format(report_time)))


if __name__ == '__main__':
    pass
