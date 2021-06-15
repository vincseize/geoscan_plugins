import os
import textwrap
import Metashape

from PySide2 import QtWidgets, QtCore
from common.startup.initialization import config


class PluginsSettings(QtWidgets.QDialog):
    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.initUI()

    def initUI(self):
        self.setWindowTitle(_("Plugins Settings"))

        self.resize(400, 120)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.setSizePolicy(sizePolicy)
        self.setMinimumSize(QtCore.QSize(400, 0))
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalSpacer_2 = QtWidgets.QSpacerItem(20, 5, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.auto_update = QtWidgets.QCheckBox()
        self.auto_update.setText(_("Get auto updates for Plugins"))
        self.auto_update.setChecked(config.get('Options', 'auto_update') == 'True')
        self.verticalLayout.addWidget(self.auto_update)

        self.error_logs = QtWidgets.QCheckBox()
        self.error_logs.setText(_("Send error logs to developers"))
        self.error_logs.setChecked(config.get('Options', 'report_about_errors') == 'True')
        self.verticalLayout.addWidget(self.error_logs)

        self.verticalSpacer = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.verticalLayout.addItem(self.verticalSpacer)

        self.buttonBox = QtWidgets.QDialogButtonBox()
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(True)

        self.verticalLayout.addWidget(self.buttonBox)

        self.setLayout(self.verticalLayout)

        self.buttonBox.accepted.connect(self.ok_process)
        self.buttonBox.rejected.connect(self.close)

    def ok_process(self):
        if self.auto_update.isChecked():
            config.set('Options', 'auto_update', 'True')
        else:
            config.set('Options', 'auto_update', 'False')

        if self.error_logs.isChecked():
            config.set('Options', 'report_about_errors', 'True')
        else:
            config.set('Options', 'report_about_errors', 'False')

        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.ini')
        with open(config_path, mode='wt', encoding='utf-8') as file:
            config.write(file)

        Metashape.app.messageBox(textwrap.fill(_("Please, re-run Agisoft Metashape to apply new settings"), 65))
        self.close()


def settings_window(trans):
    trans.install()
    _ = trans.gettext
    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()
    dlg = PluginsSettings(parent=parent)
    dlg.exec_()
