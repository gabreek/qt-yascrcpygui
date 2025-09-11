# FILE: gui/winlator_item_widget.py
# PURPOSE: Defines the widget for a single Winlator game item in the grid, inheriting from BaseItemWidget.

import os
from PySide6.QtWidgets import QPushButton, QMessageBox
from PySide6.QtCore import Qt, Signal
from .base_item_widget import BaseItemWidget

class WinlatorItemWidget(BaseItemWidget):
    # Specific signals for WinlatorItemWidget
    config_saved = Signal(str) # Signal to notify the tab that a config was saved
    config_deleted = Signal(str) # Signal to notify the tab that a config was deleted

    def __init__(self, game_info, app_config, placeholder_icon):
        # game_info must have 'name' and 'path'
        super().__init__({'key': game_info['path'], 'name': game_info['name']}, app_config, placeholder_icon, item_type="winlator_game")
        self.game_path = self.item_key
        self.game_name = self.item_name

        # Style adjustments for Winlator (removing size and bold overrides)
        # The widget and icon size are now defined by BaseItemWidget (75x110 and 32x32)
        self.name_label.setStyleSheet("font-size: 8pt;") # Removed font-weight: bold;

        # Adds specific buttons using the base class's centralized method
        self.settings_button = self._create_action_button("⚙️")
        self.delete_button = self._create_action_button("🗑️")

        self.action_layout.addStretch()
        self.action_layout.addWidget(self.settings_button)
        self.action_layout.addWidget(self.delete_button)
        self.action_layout.addStretch()

        # Connections
        self.settings_button.clicked.connect(self.save_game_config)
        self.delete_button.clicked.connect(self.delete_game_config)

    def save_game_config(self):
        current_scrcpy_config = self.app_config.get_global_values_no_profile().copy()
        self.app_config.save_winlator_game_config(self.game_path, current_scrcpy_config)
        QMessageBox.information(self, "Configuration Saved", f"Configuration saved for {self.game_name}.")
        self.config_saved.emit(self.game_path)

    def delete_game_config(self):
        reply = QMessageBox.question(self, "Confirm Deletion",
                                     f"Are you sure you want to delete the saved configuration for {self.game_name}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.app_config.delete_winlator_game_config(self.game_path):
                QMessageBox.information(self, "Configuration Deleted", f"Configuration for {self.game_name} has been deleted.")
                self.config_deleted.emit(self.game_path)
            else:
                QMessageBox.warning(self, "No Configuration Found", f"No specific configuration was found for {self.game_name} to delete.")
