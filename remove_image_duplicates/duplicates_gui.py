import Metashape as ms
import os

from common.PySide2Wrapper.PySide2Wrapper import\
    ModalWindow, StateSaver, ComboBox, RadioButton, Button
from common.loggers.email_logger import log_method_by_crash_reporter
from remove_image_duplicates.duplicates_core import\
    remove_duplicates, disable_duplicates, merge_groups

local_dir = os.path.abspath(os.path.dirname(__file__))


class PluginWindow(ModalWindow):

    NAME = "Remove image duplicates"
    VERSION = "1.0.0"

    def __init__(self):
        super().__init__(_('Remove image duplicates'))

        state_saver = StateSaver(os.path.join(local_dir, 'remove_duplicates.json'))
        self.set_state_saver(state_saver)

        self.start_horizontal()
        self.from_all = self.add_widget(RadioButton(_('From all groups')).set_value(True), need_store=True)
        self.from_group = self.add_widget(RadioButton(_('From group name')).set_value(False), need_store=True)
        self.cancel()

        self.chunk = ms.app.document.chunk
        self.group_labels = {group.label for group in self.chunk.camera_groups}
        self.group_labels = list(self.group_labels)

        self.group_name = ComboBox().add_label(_('Group name'), 'left').add_items(self.group_labels)
        self.group_name.add_enabled_dependency(self.from_group)
        self.add_widget(self.group_name, need_store=True)

        self.disable = RadioButton(_('Disable')).set_value(True)
        self.remove = RadioButton(_('Remove')).set_value(False)
        self.merge = RadioButton(_('Merge')).set_value(False)

        self.add_to_group_box(_('Choose action:'), [self.disable, self.remove, self.merge])
        self._state_saver.add_widget(self.disable)
        self._state_saver.add_widget(self.remove)
        self._state_saver.add_widget(self.merge)

        self.add_widget(Button(_('Execute')).set_on_click_callback(self.do_something))
        self.add_widget(Button(_('Cancel')).set_on_click_callback(self.close))

        state_saver.load()

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def do_something(self):
        if self.from_all.get_value():
            group_name = None

        if self.from_group.get_value():
            group_name = self.group_labels[self.group_name.get_value()]

        if self.disable.get_value():
            disable_duplicates(group_name)

        if self.remove.get_value():
            remove_duplicates(group_name)

        if self.merge.get_value():
            merge_groups(group_name)

        ms.app.update()
        self.close()

    def log_values(self):
        d = {
            'From all groups': self.from_all.get_value(),
            'From group name': self.from_group.get_value(),
            'Group name':  self.group_name.get_value(),
            'Disable': self.disable.get_value(),
            'Remove': self.remove.get_value(),
            'Merge': self.merge.get_value(),
        }

        return d


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    dlg = PluginWindow()
    dlg.show()


if __name__ == "__main__":
    main()
