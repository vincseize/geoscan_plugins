import os
from shutil import copy

import Metashape

from common.loggers.email_logger import log_method_by_crash_reporter
from common.qt_wrapper.helpers import open_file, save_file
from common.utils.dump_userdata import UserDataDump
from gnss_post_processing.app.meta import NAME, VERSION
from gnss_post_processing.app.utils.rinex_parser import RinexParser


class GnssUtilities:
    def __init__(self, ui):
        # utilities
        shrink_rover = ShrinkRoverRinex(ui=ui)

        self.saver = UserDataDump(directory=os.path.dirname(__file__), filename='gnss_utilities',
                                  parent=self, create_cache_dir=True)
        self.saver.create_and_update(
            ShrinkRover_spinBox=4,
            ShrinkRoverFile_lineEdit="",
        )

        self.saver.upload_to_ui(ui)


class ShrinkRoverRinex:
    def __init__(self, ui):
        self.ui = ui
        self.result = ''
        self.connect_buttons()

    def connect_buttons(self):
        self.ui.ShrinkRoverFile_pushButton.clicked.connect(lambda: open_file(ui=self.ui,
                                                                             line_edit=self.ui.ShrinkRoverFile_lineEdit))
        self.ui.ShrinkRover_pushButton.clicked.connect(self.run)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def run(self):
        rover_path = self.rover_rinex
        rover_name, rover_ext = os.path.splitext(os.path.basename(rover_path))
        self.result = save_file(ui=self.ui,
                                extension="*{}".format(rover_ext),
                                title=_("Save new shrinked Rover RINEX file"),
                                main_directory=os.path.dirname(rover_path) if rover_path else False)
        if not self.result:
            return

        self.ui.status_Label.setText(_("Shrinking Rover RINEX file..."))
        Metashape.app.update()
        parser = RinexParser(obs_file=rover_path)
        parser.make_obs_rinex(
            path=self.result,
            epochs_buffer=self.epochs_per_event // 2
        )

        files_to_copy = list()
        for file in os.listdir(os.path.dirname(rover_path)):
            file_name, file_ext = os.path.splitext(file)
            if file_name == rover_name and file_ext != rover_ext:
                files_to_copy.append(os.path.join(os.path.dirname(rover_path), file))
        for file in files_to_copy:
            file_name, file_ext = os.path.splitext(file)
            result_name, result_ext = os.path.splitext(os.path.basename(self.result))
            copy(file, os.path.join(os.path.dirname(self.result), result_name + file_ext))

        self.ui.status_Label.setText(_("Finished!"))

    def log_values(self):
        d = {
            'rover': self.rover_rinex,
            'epochs_number': self.epochs_per_event,
            'save_file': self.result,
        }
        return d

    @property
    def rover_rinex(self):
        return self.ui.ShrinkRoverFile_lineEdit.text()

    @property
    def epochs_per_event(self):
        return self.ui.ShrinkRover_spinBox.value()
