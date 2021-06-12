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

PROCESSING_STATUSES = [
    _("processing method: forward"),
    _("processing method: backward"),
    _("processing method: combined"),
]

def init_gnss_post_processing_translations(ui):
    ui.setWindowTitle(_("GNSS Post Processing"))

    # tabs
    ui.tabWidget.setTabText(0, _("Single files"))
    ui.tabWidget.setTabText(1, _("Single base + Multiple rovers"))

    # tab1

    # rover
    ui.Rover_groupBox.setTitle(_("Rover"))

    ui.roverpath_label.setText(_("RINEX file:"))
    ui.roverpath_pushButton.setText(_("Open"))

    ui.RevolutionCheckBox.setText(_("Use epochs which placed next to events only (experimental, "
                                    "processing wil be faster)"))
    ui.EpochsNumberLabel.setText(_("Epochs number per event:"))

    # base
    ui.Base_groupBox.setTitle(_("Base"))

    ui.basepath_label.setText(_("RINEX file:"))
    ui.basepath_pushButton.setText(_("Open"))

    ui.CrsUi_Label.setText(_("Coordinate System:"))
    ui.crs_pushButton.setText(_("Select CRS"))

    ui.BaseUi_label.setText(_("Base coordinates:"))
    ui.North_label.setText(_("North (Lat)"))
    ui.East_label.setText(_("East (Lon)"))
    ui.Height_label.setText(_("Height (m):"))

    ui.AntennaType_label.setText(_("Antenna type:"))
    ui.AntennaHeight_label.setText(_("Antenna height (m):"))

    # telemetry
    ui.Telemetry_groupBox.setTitle(_("Geoscan telemetry files"))

    ui.telemetry1_checkBox.setText(_("Telemetry file 1:"))
    ui.telemetrypath1_pushButton.setText(_("Open"))

    ui.telemetry2_checkBox.setText(_("Telemetry file 2:"))
    ui.telemetrypath2_pushButton.setText(_("Open"))

    # tab2

    # base
    ui.groupBox.setTitle(_("Base"))
    ui.tab2_BaseLabel.setText(_("RINEX file:"))
    ui.tab2_BasePushButton.setText(_("Open"))

    ui.tab2_CrsLabel.setText(_("Coordinate System:"))
    ui.tab2_CrsSetPushButton.setText(_("Select CRS"))

    ui.tab2_BaseCoordinatesLabel.setText(_("Base coordinates:"))
    ui.tab2_BaseNorthLabel.setText(_("North (Lat)"))
    ui.tab2_BaseEastLabel.setText(_("East (Lon)"))
    ui.tab2_BaseHeightLabel.setText(_("Height (m):"))

    ui.tab2_BaseAntennaTypeLabel.setText(_("Antenna type:"))
    ui.tab2_BaseAntennaHeightLabel.setText(_("Antenna height (m):"))

    # Dir
    ui.tab2_InputDataLabel.setText(_("Directory with flights data*:"))
    ui.tab2_InputDataPushButton.setText(_("Open"))
    ui.DirInfoLabel.setText(_("* The directory must include rover and telemetry files. "
                            "Files will be searched recursively in all subdirectories"))

    # Table
    ui.FlightsDataLabel.setText(_("Flights data:"))
    ui.tab2_FullPathCheckBox.setText(_("Show full file paths"))
    ui.tab2_UncheckPushButton.setText(_("Uncheck all"))
    ui.tab2_pushButton.setText(_("Find flights in selected directory"))
    ui.tab2_FindFlightsSettingsPushButton.setText(_("Search flights settings"))

    # processing parameters
    ui.Parameters_groupBox.setTitle(_("Processing parameters"))

    ui.glonass_checkBox.setText(_("GLONASS"))
    ui.ElevMask_label.setText(_("Elevation mask (°):"))

    ui.ExcludedSatellites_label.setText(_("Excluded satellites:"))
    ui.ExampleExclude_label.setText(_("Example: G10, R07"))

    # menu
    ui.plot_track_pushButton.setText(_("Plot track"))
    ui.plot_marks_pushButton.setText(_("Plot marks"))
    ui.export_pushButton.setText(_("Export result to xml / txt files"))
    ui.import_pushButton.setText(_("Import result to chunk"))
    ui.process_pushButton.setText(_("Process"))

    ui.RtkLibInfo_label.setText(_('<html><head/><body><p><span style=" color:#8b8b8b;">'
                                  'Powered by RTKLIB 2.4.3 Demo5 b34b'
                                  '</span></p></body></html>'))





