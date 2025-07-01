# FILE: gui/app_item_widget.py
# PURPOSE: Define o widget para um único item de app na grade, herdando de BaseItemWidget.

import os
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, Signal
from .base_item_widget import BaseItemWidget

class AppItemWidget(BaseItemWidget):
    # Sinais específicos para AppItemWidget
    settings_requested = Signal(str)
    pin_toggled = Signal()
    delete_config_requested = Signal(str)

    def __init__(self, app_info, app_config, placeholder_icon):
        # app_info deve ter 'app_name' e 'pkg_name'
        super().__init__({'key': app_info['pkg_name'], 'name': app_info['app_name']}, app_config, placeholder_icon, item_type="app")
        self.pkg_name = self.item_key

        # Adiciona botões específicos para AppItemWidget ao action_layout do BaseItemWidget
        self.settings_button = QPushButton("⚙️")
        self.delete_config_button = QPushButton("🗑️")
        self.pin_button = QPushButton()

        for btn in [self.settings_button, self.delete_config_button, self.pin_button]:
            btn.setFixedSize(22, 22)

        self.action_layout.addStretch()
        self.action_layout.addWidget(self.settings_button)
        self.action_layout.addWidget(self.delete_config_button)
        self.action_layout.addWidget(self.pin_button)
        self.action_layout.addStretch()

        # Conexões
        self.settings_button.clicked.connect(lambda: self.settings_requested.emit(self.pkg_name))
        self.pin_button.clicked.connect(self.toggle_pin)
        self.delete_config_button.clicked.connect(lambda: self.delete_config_requested.emit(self.pkg_name))

        self.update_pin_status()

    def toggle_pin(self):
        metadata = self.app_config.get_app_metadata(self.pkg_name)
        is_pinned = not metadata.get('pinned', False)
        self.app_config.save_app_metadata(self.pkg_name, {'pinned': is_pinned})
        self.update_pin_status()
        self.pin_toggled.emit()

    def update_pin_status(self):
        metadata = self.app_config.get_app_metadata(self.pkg_name)
        is_pinned = metadata.get('pinned', False)
        self.pin_button.setText("⭐" if is_pinned else "☆")