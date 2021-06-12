"""Export/Import model by marker plugin for Agisoft Metashape

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

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(638, 300)
        Dialog.setMinimumSize(QtCore.QSize(670, 300))
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.label = QtWidgets.QLabel(Dialog)
        self.label.setMaximumSize(QtCore.QSize(200, 100000))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label.setFont(font)
        self.label.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setObjectName("label")
        self.horizontalLayout_2.addWidget(self.label)
        self.label_2 = QtWidgets.QLabel(Dialog)
        self.label_2.setMaximumSize(QtCore.QSize(100000, 100000))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.label_2.setFont(font)
        self.label_2.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout_2.addWidget(self.label_2)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.MarkersList = QtWidgets.QListWidget(Dialog)
        self.MarkersList.setMaximumSize(QtCore.QSize(200, 16777215))
        self.MarkersList.setObjectName("MarkersList")
        self.horizontalLayout.addWidget(self.MarkersList)
        self.MeshList = QtWidgets.QListWidget(Dialog)
        self.MeshList.setObjectName("MeshList")
        self.horizontalLayout.addWidget(self.MeshList)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.BrowseButtonExport = QtWidgets.QPushButton(Dialog)
        self.BrowseButtonExport.setObjectName("BrowseButtonExport")
        self.horizontalLayout_3.addWidget(self.BrowseButtonExport)
        self.lineEdit_Export = QtWidgets.QLineEdit(Dialog)
        self.lineEdit_Export.setObjectName("lineEdit_Export")
        self.horizontalLayout_3.addWidget(self.lineEdit_Export)
        self.ExportButton = QtWidgets.QPushButton(Dialog)
        self.ExportButton.setObjectName("ExportButton")
        self.horizontalLayout_3.addWidget(self.ExportButton)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.BrowseButtonImport = QtWidgets.QPushButton(Dialog)
        self.BrowseButtonImport.setObjectName("BrowseButtonImport")
        self.horizontalLayout_4.addWidget(self.BrowseButtonImport)
        self.lineEdit_Import = QtWidgets.QLineEdit(Dialog)
        self.lineEdit_Import.setObjectName("lineEdit_Import")
        self.horizontalLayout_4.addWidget(self.lineEdit_Import)
        self.ImportButton = QtWidgets.QPushButton(Dialog)
        self.ImportButton.setObjectName("ImportButton")
        self.horizontalLayout_4.addWidget(self.ImportButton)
        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtWidgets.QApplication.translate("Dialog", _("Export/Import model by marker"), None, -1))
        self.label.setText(QtWidgets.QApplication.translate("Dialog", _("Markers"), None, -1))
        self.label_2.setText(QtWidgets.QApplication.translate("Dialog", _("Models"), None, -1))
        self.ExportButton.setText(QtWidgets.QApplication.translate("Dialog", _("Export"), None, -1))
        self.BrowseButtonExport.setText(QtWidgets.QApplication.translate("Dialog", _("Browse"), None, -1))
        self.ImportButton.setText(QtWidgets.QApplication.translate("Dialog", _("Import"), None, -1))
        self.BrowseButtonImport.setText(QtWidgets.QApplication.translate("Dialog", _("Browse"), None, -1))
