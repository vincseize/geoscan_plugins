"""Plugins configurator for Agisoft Metashape

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

from PySide2.QtCore import *
from PySide2.QtWidgets import *

from common.utils.ui import show_info
from common.startup.initialization import config


class PluginsConfigurator(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini")
        self.setMinimumSize(400, 650)
        self.vbox = QVBoxLayout(self)
        self.table = QTableWidget()
        self.save_changes_button = QPushButton()
        self.init_ui()

    @staticmethod
    def init_translate():
        pass

    def init_ui(self):
        plugins = self.get_current_installed_plugins()

        self.table.setColumnCount(2)
        self.table.setRowCount(len(plugins))
        self.table.setHorizontalHeaderLabels((_("Plugin name;Load;")).split(";"))

        for num, (plugin, enabled) in enumerate(plugins):
            plugin_name = QTableWidgetItem(_(plugin.split('.')[0]))
            plugin_name.name = plugin
            self.table.setItem(num, 0, plugin_name)
            check_box = QTableWidgetItem()
            enabled = True if enabled == 'True' else False
            if enabled:
                check_box.setCheckState(Qt.Checked)
            else:
                check_box.setCheckState(Qt.Unchecked)
            self.table.setItem(num, 1, check_box)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        self.vbox.addWidget(self.table)

        self.save_changes_button.setText(_("Save changes"))
        self.save_changes_button.clicked.connect(lambda: self.save_changes())
        self.vbox.addWidget(self.save_changes_button)

    @staticmethod
    def get_current_installed_plugins():
        return sorted(dict(config.items("Plugins")).items(), key=lambda item: item[0])

    def save_changes(self):
        for i in range(self.table.rowCount()):
            in_table = self.table.item(i, 1).checkState() is Qt.Checked
            in_config = (config.get("Plugins", self.table.item(i, 0).name) == "True")
            if in_table != in_config:
                config.remove_option("Plugins", self.table.item(i, 0).name)
                config.set("Plugins", self.table.item(i, 0).name, str(in_table))
        with open(self.config_path, 'w') as configfile:
            config.write(configfile)
        show_info(_("Plugins configurator"), _("You need to re-run Agisoft Metashape"))


def main(trans):
    trans.install()
    _ = trans.gettext
    app = QApplication.instance()
    parent = app.activeWindow()
    dlg = PluginsConfigurator(parent)
    dlg.setWindowTitle(_("Plugins configurator"))
    dlg.show()


