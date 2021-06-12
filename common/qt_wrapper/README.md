# Оболочка на PySide для создания GUI плагинов

## Поддерживаются типы:
1. Window
    - MainWindow
    - MessageBox
2. UiUnit
    - LineEdit
    - CheckBox
    - RadioButton
    - Button
    - File - диалог выбора файла
    - Path - диалог выбора файла
    - ComboBox - выпадающий список

# Пример использования кода:
```python
class something_worker(Window):
    def __init__(self):
        super().__init__(_("Do a barrel roll"), [270, 0])
        self.__init_ui()

    def __init_ui(self):
        self.__line_edit = self.add_unit(LineEdit, label_name="Do a barrel", default_value=1)

        self.start_group_box(_("Barrel parameters"))
        self.insert_text_label(_("Center"))
        self.start_horisontal()
        self.__x_center_coord = self.add_unit(LineEdit)
        self.insert_text_label("-")
        self.__y_center_coord = self.add_unit(LineEdit)
        self.insert_text_label(_("Coords"))
        self.cancel()

        self.__proc_btn = self.add_unit(Button, _("Do a barrel"), self.__process)

    def __process(self):
        try:
            do_a_barrel()
        except PsLoader.Error as err:
            self.show_message(str(err))
        except:
            traceback.print_exc()

def main():
    worker = something_worker()
    worker.show()
```