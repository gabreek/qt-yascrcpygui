from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox
from .common_widgets import CustomThemedDialog
from utils.constants import CONF_SHOW_WINLATOR_TAB


class WinlatorFrontendConfigWindow(CustomThemedDialog):
    winlator_visibility_changed = Signal(bool)

    def __init__(self, app_config, parent=None):
        super().__init__(parent=parent, title=app_config.tr('winlator_frontend_config', 'title'))
        self.app_config = app_config

        self.setMinimumWidth(320)

        self.show_tab_checkbox = QCheckBox(app_config.tr('winlator_frontend_config', 'show_tab'))
        self.show_tab_checkbox.setChecked(app_config.get(CONF_SHOW_WINLATOR_TAB, True))
        self.show_tab_checkbox.stateChanged.connect(self._on_show_tab_changed)

        self.add_content_widget(self.show_tab_checkbox)

    def _on_show_tab_changed(self, state):
        visible = bool(state)
        self.app_config.set(CONF_SHOW_WINLATOR_TAB, visible)
        self.winlator_visibility_changed.emit(visible)

    def retranslate_ui(self):
        self.setWindowTitle(self.app_config.tr('winlator_frontend_config', 'title'))
        self.title_bar.title_label.setText(self.app_config.tr('winlator_frontend_config', 'title'))
        self.show_tab_checkbox.setText(self.app_config.tr('winlator_frontend_config', 'show_tab'))
