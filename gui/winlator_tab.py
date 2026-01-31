import os
import tempfile
import queue
from PIL import Image

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QGridLayout, QLabel, QMessageBox) # Removed QProgressDialog
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QTimer
from PySide6.QtGui import QPixmap
import sys

from utils import scrcpy_handler
from .workers import GameListWorker, IconExtractorWorker, WinlatorLaunchWorker, ScrcpyLaunchWorker
from .dialogs import show_message_box
from .base_grid_tab import BaseGridTab
from .common_widgets import CustomThemedProgressDialog # Import CustomThemedProgressDialog

class WinlatorTab(BaseGridTab):
    launch_requested = Signal(str, str)
    config_changed = Signal(str)
    config_deleted = Signal(str)

    def __init__(self, app_config, main_window=None):
        super().__init__(app_config, main_window)
        self.all_games_data = [] # Holds the full data model
        self.game_items = {} # Kept for icon extraction logic to find items by path
        self.temp_dir = tempfile.gettempdir()
        self.extraction_queue = queue.Queue()
        self.icon_extractor_workers = []
        self.total_tasks = 0
        self.completed_tasks_count = 0
        self.NUM_WORKERS = 2
        self.scrcpy_process = None

        base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        self.placeholder_icon_path = os.path.join(base_path, "gui/winlator_placeholder.png")

        top_panel = QHBoxLayout()
        top_panel.addStretch(1)

        self.refresh_button = QPushButton("Refresh Apps")
        top_panel.addWidget(self.refresh_button)

        self.fetch_icons_button = QPushButton("Refresh Icons")
        top_panel.addWidget(self.fetch_icons_button)
        self.main_layout.insertLayout(0, top_panel)

        self.refresh_button.clicked.connect(self.refresh_games_list)
        self.fetch_icons_button.clicked.connect(lambda: self.prompt_for_icon_update())

        self._connect_qml_signals()
        self.on_device_changed()

    def _connect_qml_signals(self):
        root = self.quick_widget.rootObject()
        if not root:
            QTimer.singleShot(100, self._connect_qml_signals)
            return

        root.launchRequested.connect(self._on_qml_launch_requested)
        root.settingsRequested.connect(self.on_settings_requested)
        root.deleteConfigRequested.connect(self.on_delete_config_requested)

    @Slot(str, str)
    def _on_qml_launch_requested(self, itemKey, itemName):
        """Slot to receive launch request from QML and emit the Python signal."""
        self.launch_requested.emit(itemKey, itemName)

    def update_theme(self, status=None):
        """Passes the theme update call to the base class."""
        super().update_theme(status)

    def on_device_changed(self):
        self._clear_grid()
        self.all_games_data = []
        device_id = self.app_config.get_connection_id()
        if not device_id or device_id == "no_device":
            self.show_message("Please connect a device.")
            self.refresh_button.setEnabled(False)
            self.fetch_icons_button.setEnabled(False)
        else:
            self.refresh_button.setEnabled(True)
            self.fetch_icons_button.setEnabled(True)
            self.refresh_games_list()

    def refresh_games_list(self):
        device_id = self.app_config.get_connection_id()
        if device_id is None or device_id == "no_device":
            self.show_message("Please connect a device to see Winlator games.")
            return

        self.refresh_button.setEnabled(False)
        self._clear_grid()
        self.show_message("Searching for games...")

        self.game_list_worker = GameListWorker(device_id)
        self.game_list_worker.signals.result.connect(self._on_game_list_loaded)
        self.game_list_worker.signals.error.connect(self._on_game_list_error)
        self.game_list_worker.signals.finished.connect(lambda: self.refresh_button.setEnabled(True))
        if self.main_window:
            self.main_window.start_worker(self.game_list_worker)

    def _on_game_list_loaded(self, games_with_pkg):
        if not games_with_pkg:
            self.show_message("No Winlator shortcut found on device.\nPlease export to frontend in Winlator app.")
        else:
            self.populate_games_grid_model(games_with_pkg)
            self.show_grid()

        self.refresh_button.setEnabled(True)

    def _on_game_list_error(self, error_msg):
        self.show_message(f"Error: {error_msg}")
        self.refresh_button.setEnabled(True)

    def populate_games_grid_model(self, games):
        self.all_games_data = []
        self.game_items = {} # Reset game_items for new population

        # Group games by their 'pkg' (which represents the Winlator CMOD version)
        grouped_games = {}
        for game_info in games:
            pkg = game_info.get('pkg', 'com.winlator.cmod') # Default to cmod if pkg is missing
            if pkg not in grouped_games:
                grouped_games[pkg] = []
            grouped_games[pkg].append(game_info)
        
        # Sort packages (e.g., cmod first, then by version string)
        sorted_packages = sorted(grouped_games.keys(), key=lambda p: (0 if p == 'com.winlator.cmod' else 1, p))

        qml_model_data = []

        for pkg in sorted_packages:
            games_in_pkg = sorted(grouped_games[pkg], key=lambda x: x.get('name', '').lower())
            
            # Add a separator for each Winlator version
            # Assuming pkg 'com.winlator.cmod' refers to "Winlator CMOD"
            # And other pkgs might have version numbers in their name or we can default
            display_name = pkg.replace('com.winlator.', '').replace('cmod', 'CMOD ').replace('custom', 'Custom ')
            if display_name == 'CMOD': # Catch for base CMOD package
                display_name = 'Winlator CMOD'
            else: # If there's a version suffix, format it nicely
                display_name = f"Winlator {display_name}"

            qml_model_data.append({'isSeparator': True, 'text': display_name})

            for game_info in games_in_pkg:
                game_path = game_info.get('path', '')
                game_name = game_info.get('name', 'Unnamed')
                
                icon_path = self.placeholder_icon_path
                if game_path:
                    icon_key = os.path.basename(game_path)
                    cached_icon_path = os.path.join(self.app_config.get_icon_cache_dir(), f"{icon_key}.png")
                    if os.path.exists(cached_icon_path):
                        icon_path = cached_icon_path

                game_data = {
                    'key': game_path,
                    'name': game_name,
                    'item_type': "winlator_game",
                    'icon_path': QUrl.fromLocalFile(icon_path).toString(),
                    'pkg': pkg # Store pkg for launch worker
                }
                qml_model_data.append(game_data)
                self.game_items[game_path] = game_data # Update game_items for icon extraction/config

        self._update_grid_model(qml_model_data)

    @Slot(str, str)
    def on_settings_requested(self, itemKey, itemType):
        if itemType != 'winlator_game': return
        
        game_name = self.game_items.get(itemKey, {}).get('name', 'N/A')
        current_scrcpy_config = self.app_config.get_global_values_no_profile().copy()
        self.app_config.save_winlator_game_config(itemKey, current_scrcpy_config)
        
        icon_path = self._get_game_icon_path(itemKey)
        show_message_box(self, "Configuration Saved", f"Configuration saved for {game_name}.", icon=QMessageBox.Information, app_icon_path=icon_path)
        self.config_changed.emit(itemKey)

    @Slot(str, str)
    def on_delete_config_requested(self, itemKey, itemType):
        if itemType != 'winlator_game': return

        game_name = self.game_items.get(itemKey, {}).get('name', 'N/A')
        icon_path = self._get_game_icon_path(itemKey)

        reply = show_message_box(self, "Confirm Deletion",
                                     f"Are you sure you want to delete the saved configuration for {game_name}?",
                                     icon=QMessageBox.Question,
                                     buttons=QMessageBox.Yes | QMessageBox.No,
                                     app_icon_path=icon_path)
        if reply == QMessageBox.Yes:
            if self.app_config.delete_winlator_game_config(itemKey):
                show_message_box(self, "Configuration Deleted", f"Configuration for {game_name} has been deleted.", icon=QMessageBox.Information, app_icon_path=icon_path)
                self.config_deleted.emit(itemKey)
            else:
                show_message_box(self, "No Configuration Found", f"No specific configuration was found for {game_name} to delete.", icon=QMessageBox.Warning, app_icon_path=icon_path)

    def _get_game_icon_path(self, game_path):
        icon_key = os.path.basename(game_path)
        icon_path = os.path.join(self.app_config.get_icon_cache_dir(), f"{icon_key}.png")
        return icon_path if os.path.exists(icon_path) else None

    def prompt_for_icon_update(self):
        missing_icons = []
        for path, item_data in self.game_items.items():
            icon_key = os.path.basename(path)
            cached_icon_path = os.path.join(self.app_config.get_icon_cache_dir(), f"{icon_key}.png")
            if not os.path.exists(cached_icon_path):
                metadata = self.app_config.get_app_metadata(path)
                if not metadata.get('exe_icon_fetch_failed') and not metadata.get('custom_icon'):
                    missing_icons.append((path, cached_icon_path))

        if not missing_icons:
            show_message_box(self, "Icons", "No icons to extract.")
            return

        reply = show_message_box(
            self, "Search missing icons?",
            f"{len(missing_icons)} games without icons.\n\nThis process may take several minutes.\n\nWish to continue?",
            icon=QMessageBox.Question, buttons=QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.start_icon_extraction_flow(missing_icons)

    def start_icon_extraction_flow(self, tasks):
        self.total_tasks = len(tasks)
        self.completed_tasks_count = 0
        self.progress_dialog = CustomThemedProgressDialog("Extracting Icons", "Cancel", 0, self.total_tasks, self)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()

        self.icon_extractor_workers = []
        for _ in range(self.NUM_WORKERS):
            worker = IconExtractorWorker(self.extraction_queue, self.app_config, self.temp_dir, self.placeholder_icon_path, self.app_config.get_connection_id())
            worker.signals.icon_extracted.connect(self._on_icon_extracted)
            worker.signals.error.connect(self._on_icon_extraction_error)
            self.icon_extractor_workers.append(worker)
            if self.main_window: self.main_window.start_worker(worker)

        for task in tasks: self.extraction_queue.put(task)
        for _ in range(self.NUM_WORKERS): self.extraction_queue.put(None)

    def _on_icon_extracted(self, path, success, new_icon_path=None):
        self.completed_tasks_count += 1
        self.progress_dialog.setValue(self.completed_tasks_count)
        self.progress_dialog.setLabelText(f"Processing {self.completed_tasks_count} of {self.total_tasks}...")

        if path in self.game_items and success and new_icon_path:
            self.game_items[path]['icon_path'] = QUrl.fromLocalFile(new_icon_path).toString()
        
        if self.completed_tasks_count >= self.total_tasks:
            self._on_all_icons_extracted()

    def _on_icon_extraction_error(self, path, error_msg):
        print(f"Error extracting icon for {path}: {error_msg}")
        self.completed_tasks_count += 1
        self.progress_dialog.setValue(self.completed_tasks_count)
        if self.completed_tasks_count >= self.total_tasks:
            self._on_all_icons_extracted()

    def _on_all_icons_extracted(self):
        if self.progress_dialog.isVisible(): self.progress_dialog.close()
        show_message_box(self, "Finished", "Icons extraction finished!")
        self.icon_extractor_workers.clear()
        self._update_grid_model(list(self.game_items.values()))

    def execute_launch(self, shortcut_path, game_name):
        game_info = self.game_items.get(shortcut_path)
        if not game_info:
            show_message_box(self, "Error", "Could not find game information to launch.", icon=QMessageBox.Critical)
            return

        package_name = game_info.get('pkg', 'com.winlator.cmod')
        if package_name == 'unknown':
            show_message_box(self, "Error", "Could not determine Winlator package name.", icon=QMessageBox.Critical)
            return

        config_to_use = self.app_config.get_global_values_no_profile().copy()
        if game_data := self.app_config.get_winlator_game_config(shortcut_path):
            config_to_use.update(game_data)

        config_to_use.update({
            'start_app': '',
            'shortcut_path': shortcut_path,
            'package_name': package_name
        })

        icon_path = self._get_game_icon_path(shortcut_path)

        self.scrcpy_launch_worker = ScrcpyLaunchWorker(
            config_values=config_to_use,
            window_title=game_name,
            connection_id=self.app_config.get_connection_id(),
            icon_path=icon_path,
            session_type='winlator'
        )
        self.scrcpy_launch_worker.signals.error.connect(lambda msg: self._on_scrcpy_launch_error(msg, icon_path))
        self.scrcpy_launch_worker.signals.scrcpy_process_started.connect(self._on_scrcpy_process_started)
        self.scrcpy_launch_worker.signals.display_id_found.connect(self._on_display_id_found)
        if self.main_window:
            self.main_window.start_worker(self.scrcpy_launch_worker)

    def _on_scrcpy_launch_error(self, error_msg, icon_path=None):
        show_message_box(self, "Scrcpy Error", f"Failed to start scrcpy: {error_msg}", icon=QMessageBox.Critical, app_icon_path=icon_path)

    def _on_scrcpy_process_started(self, process):
        self.scrcpy_process = process

    def _on_display_id_found(self, display_id, shortcut_path, package_name):
        icon_path = self._get_game_icon_path(shortcut_path)
        if not display_id:
            show_message_box(self, "Error", "Virtual display not found.", icon=QMessageBox.Critical, app_icon_path=icon_path)
            return

        full_config = self.app_config.get_global_values_no_profile().copy()
        if game_specific_config := self.app_config.get_winlator_game_config(shortcut_path):
            full_config.update(game_specific_config)

        windowing_mode_str = full_config.get('windowing_mode', 'Fullscreen')
        windowing_mode_int = 1 if windowing_mode_str == 'Fullscreen' else 2

        self.winlator_launch_worker = WinlatorLaunchWorker(
            shortcut_path=shortcut_path, display_id=display_id, package_name=package_name,
            connection_id=self.app_config.get_connection_id(), windowing_mode=windowing_mode_int
        )
        self.winlator_launch_worker.signals.error.connect(lambda msg: show_message_box(self, "Winlator Launch Error", msg, icon=QMessageBox.Critical, app_icon_path=icon_path))
        if self.main_window:
            self.main_window.start_worker(self.winlator_launch_worker)
