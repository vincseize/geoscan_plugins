"""Merge MAGNET XMLs plugin for Agisoft Metashape

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
from .MagnetMerger.MagnetMerger import pocket_merging
from common.utils.PluginBase import PluginBase

import Metashape


class MainDialog(PluginBase):

    NAME = "Merge MAGNET XMLs"
    VERSION = "1.0.1"

    def __init__(self):
        ui_path = os.path.join(os.path.dirname(__file__), 'magnet_merger_dialog_base.ui')
        super(MainDialog, self).__init__(ui_path)
        
    def _init_ui(self):
        """
        Initialize UI of plugin.
        :return: None
        """
        dlg = self.dlg
        self.load_values()

        dlg.gnssBtn.clicked.connect(lambda: self.select_dir(dlg.lineEditGnss))
        dlg.afsBtn.clicked.connect(lambda: self.select_dir(dlg.lineEditAfs))
        dlg.resultBtn.clicked.connect(lambda: self.select_dir(dlg.lineEditResult))

        dlg.goBtn.clicked.connect(self.__run)

    def __run(self):
        """
        Starts merge process
        :return: None
        """

        dlg = self.dlg
        gnss_path = dlg.lineEditGnss.text()
        afs_path = dlg.lineEditAfs.text()
        result_path = dlg.lineEditResult.text()
        save_xml = dlg.saveXmlCheckBox.isChecked()
        save_tsv = dlg.saveTsvCheckBox.isChecked()

        for path in gnss_path, afs_path, result_path:
            if not os.path.isdir(path):
                self.show_message(_('Incorrect path!'), _('Path: "{}"\nIs not a directory!').format(path))
                return

        if not (save_tsv or save_xml):
            self.show_message(_('Warning!'), _('Processing has no effect!\nChoose at least one writing type!'))
            return

        self.set_working_state(True)
        self.dump_values()
        self.safe_process(
            pocket_merging,
            _("Processing finished successfully!"),
            use_crash_reporter={'plugin_name': self.NAME, 'plugin_version': self.VERSION, 'items': {}},
            close_after=False,
            afs_dir=afs_path,
            gnss_dir=gnss_path,
            res_dir=result_path,
            save_tsv=save_tsv,
            save_xml=save_xml,
            progress=lambda _: Metashape.app.update()
        )


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    exporter = MainDialog()
    exporter.dlg.exec_()


if __name__ == "__main__":
    main()
