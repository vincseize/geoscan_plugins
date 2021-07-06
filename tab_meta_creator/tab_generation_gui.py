# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'tab_generation_gui.ui',
# licensing of 'tab_generation_gui.ui' applies.
#
# Created: Tue Sep 24 18:46:23 2019
#      by: pyside2-uic  running on PySide2 5.12.3
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(484, 183)
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(Dialog)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.Path = QtWidgets.QLineEdit(Dialog)
        self.Path.setObjectName("Path")
        self.horizontalLayout.addWidget(self.Path)
        self.Browse = QtWidgets.QPushButton(Dialog)
        self.Browse.setObjectName("Browse")
        self.horizontalLayout.addWidget(self.Browse)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.comboBox = QtWidgets.QComboBox(Dialog)
        self.comboBox.setMaximumSize(QtCore.QSize(16700000, 16777215))
        self.comboBox.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.comboBox.setInsertPolicy(QtWidgets.QComboBox.InsertAtBottom)
        self.comboBox.setObjectName("comboBox")
        self.verticalLayout.addWidget(self.comboBox)
        self.checkBox = QtWidgets.QCheckBox(Dialog)
        self.checkBox.setObjectName("checkBox")
        self.verticalLayout.addWidget(self.checkBox)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.pushButton = QtWidgets.QPushButton(Dialog)
        self.pushButton.setObjectName("pushButton")
        self.verticalLayout.addWidget(self.pushButton)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtWidgets.QApplication.translate("Dialog", "Create MapInfo TAB files for orthomosaics", None, -1))
        self.label.setText(QtWidgets.QApplication.translate("Dialog", "Directory with orthoimages", None, -1))
        self.Browse.setText(QtWidgets.QApplication.translate("Dialog", "Browse", None, -1))
        self.checkBox.setText(QtWidgets.QApplication.translate("Dialog", "Create TAB files with coordinate system parameters", None, -1))
        self.pushButton.setText(QtWidgets.QApplication.translate("Dialog", "Generate TAB files", None, -1))

