"""Mesh creator for Agisoft Metashape

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
import traceback
import gettext
import Metashape
from PySide2.QtWidgets import QApplication, QAction, QDockWidget, QWidget

from common.loggers.email_logger import log_method_by_crash_reporter
from .startapp.initialization import InstallLogging
from .build_parapet import create_parapet
from common.utils.bridge import real_vertices_in_shape_crs
from .ui import findMainWindow, find_tabifyDockWidget, show_error, show_info
from .models import mesh, save_obj, getBottomPoint, r_vertices
from .design import Ui_Form
from .PointProcessor import ConvexHullPointProcessor
from .build_plane import ModelBuilder, plane
from .build_roof import mesh_for_roof, mesh_for_gable_roof

PLUGIN_PATH = os.path.dirname(__file__)


class MeshCreatorUI(QWidget, Ui_Form):

    NAME = "Build Walls"
    VERSION = "1.0.1"

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.setupUi(self)
        self.z = 0
        self.selection = []
        point_processor = ConvexHullPointProcessor()
        self.mb = ModelBuilder(point_processor)
        self.logger = InstallLogging(__name__)

        self.wall_btn.clicked.connect(lambda: self.create(True))
        self.plane_roof_btn.clicked.connect(lambda: self.build_plane())
        self.roof_btn.clicked.connect(lambda: self.create_roof())
        self.inner_buffer_btn.clicked.connect(lambda: self.create_parapet())
        # self.test_btn.clicked.connect(lambda: self.contour_proc_selected(self.mb))
        # self.test_btn.clicked.connect(self.create_gable_roof)

    def new_feature(self):
        show_info(_("Info"), _("This function will be in future."))

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def create_parapet(self):
        if not Metashape.app.document.chunk.shapes:
            show_error(_('Error'), _("Please, open project."))
            return

        shapes = [s for s in Metashape.app.document.chunk.shapes if s.selected and
                  s.type in [Metashape.Shape.Type.Polygon, Metashape.Shape.Type.Polyline]]

        if len(shapes) == 0:
            show_error(_("Error"), _("Shape was not selected."))
            return

        try:
            m_in = -float(self.inner_buffer_text.text())
        except ValueError:
            show_info(_('Info'), _('Please, enter correct values.'))
            return

        if len(shapes) == 1:
            create_parapet(shapes[0], m_in)
        elif len(shapes) > 1:
            show_error(_("Error"), _("Too much shapes selected. Maximum 1 shape."))
        else:
            self.logger.error("Cannot define list of shapes in create_parapet function")
            return

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def create_roof(self):
        if not Metashape.app.document.chunk.shapes:
            show_error(_('Error'), _("Please, open project."))
            return

        faces = []
        shapes = [s for s in Metashape.app.document.chunk.shapes.shapes if s.selected and
                  s.type in [Metashape.Shape.Type.Polygon, Metashape.Shape.Type.Polyline]]

        if len(shapes) == 0:
            show_error(_("Error"), _("Shape was not selected."))
            return

        try:
            m_in = -float(self.inside_indent_text.text())
            m_low = -float(self.down_indent_text.text())
        except ValueError:
            show_info(_('Info'), _('Please, enter correct values.'))
            return

        if len(shapes) == 1:
            try:
                faces.extend(mesh_for_roof(shapes[0], m_in, m_low))
            except TypeError:
                pass
        elif len(shapes) > 1:
            show_error(_("Error"), _("Too much shapes selected. Maximum 1 shape."))
        else:
            self.logger.exception("Long of shapes' list {}".format(len(shapes)))
            return
        if not len(faces):
            return
        save_obj(faces)

    def create_gable_roof(self):
        if not Metashape.app.document.chunk.shapes:
            show_error(_('Error'), _("Please, open project."))
            return

        shapes = [s for s in Metashape.app.document.chunk.shapes.shapes if s.selected and
                  s.type in [Metashape.Shape.Type.Polygon, ]]

        if len(shapes) == 0:
            show_error(_("Error"), _("Shape was not selected."))
            return
        elif len(shapes) == 1:
            mesh_for_gable_roof(shapes[0])
        elif len(shapes) > 1:
            show_error(_("Error"), _("Too much shapes selected. Maximum 1 shape."))
        else:
            self.logger.exception("Long list of shapes.".format(len(shapes)))
            return

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def build_plane(self):
        if not Metashape.app.document.chunk.shapes:
            show_error(_('Error'), _("Please, open project."))
            return

        shapes = [s for s in Metashape.app.document.chunk.shapes.shapes if s.selected and
                  s.type in [Metashape.Shape.Type.Polygon, ]]

        if len(shapes) == 0:
            show_error(_("Error"), _("Shape was not selected."))
            return
        elif len(shapes) == 1:
            plane(shapes[0])
        else:
            show_info(_('Info'), _('Too much shapes selected.'))

    def contour_proc_selected(self, mb):
        if not Metashape.app.document.chunk.shapes:
            show_error(_('Error'), _("Please, open project."))
            return

        if self.is_textured():
            show_info(_('Info'), _('Unable to edit 3D model with texture.\n'
                                   'Please remove texture to continue editing 3D model.'))
            return

        mb.point_processor.max_face_size = None
        mb.process_selected()

    def build_texture(self):
        workflow = None
        build_texture = None
        translate_menu_item = ["&Ablauf", "&Workflow", "&Обработка", "&Flujo de trabajo", "&Traitements", "&Processi",
                               "ワークフロー(&W)", "Fluxo de &Trabalho", "工作流程(&W)"]
        translate_menu_actions = ["&Textur erzeugen...", "Build &Texture...", "Построить &текстуру...",
                                  "Crear &textura...", "Construire une &texture...", "Genera &Texture...",
                                  "テクスチャー構築(&T)...", "Construir &Textura...", "生成纹理(&T)..."]

        for i in QApplication.allWidgets():
            try:
                if i.title() in translate_menu_item:
                    workflow = i
                    break
            except AttributeError:
                pass

        for action in workflow.actions():
            if action.text() in translate_menu_actions:
                build_texture = action
                break

        if build_texture and build_texture.isEnabled():
            build_texture.activate(QAction.Trigger)
        else:
            show_info(_('Error'), _('Please, open project.'))

    def is_textured(self):
        action = None
        for w in QApplication.allWidgets():
            for a in w.children():
                if type(a) == QAction and a.text() in ['Текстурированный', 'Textured']:
                    action = a
        if action and action.isEnabled():
            return True
        return False

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def create(self, closed):
        if not Metashape.app.document.chunk.shapes:
            show_error(_('Error'), _("Please, open project."))
            return

        boxes = []
        faces = []
        stypes = []
        bottoms = []
        shapes = [s for s in Metashape.app.document.chunk.shapes.shapes if s.selected and
                  s.type in [Metashape.Shape.Type.Polygon, Metashape.Shape.Type.Polyline]]
        if len(shapes) == 0:
            show_error(_("Error"), _("Shape was not selected."))
            return

        for s in shapes:
            try:
                assert isinstance(s, Metashape.Shape)  # check that we've got the shape
            except AssertionError:
                self.logger.exception("The shape is not instance Metashape.Shape. Object is {}".format(s))
                show_info(_('Cannot define shape'), _('Please, sent to us .log file located in:\n{}').format(self.logger.fn))
                return

            if s.vertices:
                boxes.append(s.vertices)
            elif s.vertex_ids:
                try:
                    boxes.append(real_vertices_in_shape_crs(s))
                except TypeError:
                    self.logger.exception("Some vertices(attached markers) doesn't have position")
                    show_info(_('Cannot define shape'), _('Please, check all shape\'s vertices,\nsome vertices are not show.'))
                    return
            else:
                self.logger.error("Cannot define shape\'s vertices. {}".format(s.type))
                show_info(_('Cannot define shape\'s vertices'),
                          _('Please, sent to us .log file located in:\n{}').format(self.logger.fn))
                return

            stypes.append(s.type)

        try:
            if self.height_text.text() == "":
                for i in range(len(boxes)):
                    bottoms.append(-float(getBottomPoint(r_vertices(boxes[i]))))
            else:
                try:
                    height = abs(float(self.height_text.text()))
                except ValueError:
                    show_info(_('Info'), _('Please, enter correct values.'))
                    return
                for i in range(len(boxes)):
                    if self.direction_list.currentText() in ["Down", "Вниз"]:
                        bottoms.append(-height)
                    else:
                        bottoms.append(height)
        except:
            show_error(_("Warning"),
                _("It's impossible to detect the dense cloud under the point.\n"
                  "Please enter the building height manually"))
            return

        for i in range(len(boxes)):
            faces.extend(list(mesh(boxes[i], bottoms[i], stypes[i])))

        save_obj(faces)

    def log_values(self):
        return {}


def start_mesh_creator(trans):
    try:
        trans.install()
        _ = trans.gettext

        if Metashape.app.document.chunk is None:
            Metashape.app.messageBox(_("Empty chunk!"))
            return

        w = findMainWindow()
        dock = QDockWidget(_("3D Tools"), w)
        dock.setObjectName(_("3D Tools"))
        model_builder_dock = MeshCreatorUI(w)
        dock.setWidget(model_builder_dock)
        w.tabifyDockWidget(find_tabifyDockWidget(), dock)
        dock.raise_()
    except:
        traceback.print_exc()
