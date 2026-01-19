import os
import tempfile
import queue
from PIL import Image

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QGridLayout, QLabel, QMessageBox) # Removed QProgressDialog
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
import sys

from .winlator_item_widget import WinlatorItemWidget
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
        self.all_games = []
        self.game_items = {}
        self.temp_dir = tempfile.gettempdir()
        self.extraction_queue = queue.Queue()
        self.icon_extractor_workers = []
        self.total_tasks = 0
        self.completed_tasks_count = 0
        self.NUM_WORKERS = 2
        self.scrcpy_process = None # To store the Scrcpy Popen object

        # Determine the base path for resources
        if getattr(sys, 'frozen', False):
            # Running in a PyInstaller bundle
            base_path = sys._MEIPASS
        else:
            # Running in a normal Python environment
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        self.placeholder_icon = QPixmap(os.path.join(base_path, "gui/winlator_placeholder.png"))
        if self.placeholder_icon.isNull():
            self.placeholder_icon = QPixmap(40, 40)
            self.placeholder_icon.fill(Qt.GlobalColor.darkGray)

        top_panel = QHBoxLayout()
        top_panel.addStretch(1)

        self.refresh_button = QPushButton("Refresh Apps")
        top_panel.addWidget(self.refresh_button)

        self.fetch_icons_button = QPushButton("Refresh Icons")
        top_panel.addWidget(self.fetch_icons_button)
        self.main_layout.insertLayout(0, top_panel)

        self.refresh_button.clicked.connect(self.refresh_games_list)
        self.fetch_icons_button.clicked.connect(lambda: self.prompt_for_icon_update())

        self.on_device_changed()

    def on_device_changed(self):
        self._clear_grid()
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
            self.refresh_button.setEnabled(True)
            return

        self.refresh_button.setEnabled(False)
        self._clear_grid()
        self.show_message("Searching for games...")

        self.game_list_worker = GameListWorker(device_id)
        self.game_list_worker.signals.result.connect(self._on_game_list_loaded)
        self.game_list_worker.signals.error.connect(self._on_game_list_error)
        self.game_list_worker.signals.finished.connect(self._on_game_list_worker_finished)
        if self.main_window:
            self.main_window.start_worker(self.game_list_worker)

    def _on_game_list_loaded(self, games_with_pkg):
        self.all_games = sorted(games_with_pkg, key=lambda x: x['name'].lower())

        if not self.all_games:
            self.show_message("No Winlator shortcut found on device.\nPlease export to frontend in Winlator app.")
        else:
            self.populate_games_grid()
            self.show_grid()

        self.refresh_button.setEnabled(True)

    def _on_game_list_error(self, error_msg):
        self.show_message(f"Error: {error_msg}")
        self.refresh_button.setEnabled(True)

    def _on_game_list_worker_finished(self):
        self.refresh_button.setEnabled(True)

    def _on_game_config_changed(self, game_path):
        self.config_changed.emit(game_path)
        self.populate_games_grid()

    def _on_game_config_deleted(self, game_path):
        self.config_deleted.emit(game_path)
        self.populate_games_grid()

    def populate_games_grid(self):
        self._clear_grid()
        self.game_items = {}

        if not self.all_games:
            self.show_message("No Winlator shortcut found.")
            return

        self.show_grid()

        cmod_games = [g for g in self.all_games if g['pkg'] == 'com.winlator.cmod']
        ludashi_games = [g for g in self.all_games if g['pkg'] == 'com.ludashi.benchmark']
        winlator_games = [g for g in self.all_games if g['pkg'] == 'com.winlator']
        other_games = [g for g in self.all_games if g['pkg'] not in ['com.winlator.cmod', 'com.ludashi.benchmark', 'com.winlator']]


        row = 0
        columns = 4
        for i in range(columns):
            self.grid_layout.setColumnStretch(i, 1)

        def add_section(title, app_list):
            nonlocal row
            if not app_list: return
            title_label = QLabel(f"<b>{title}</b>")
            self.grid_layout.addWidget(title_label, row, 0, 1, columns)
            row += 1
            col = 0
            for game_info in app_list:
                item = WinlatorItemWidget(game_info, self.app_config, self.placeholder_icon)
                item.launch_requested.connect(self.launch_requested)
                item.config_saved.connect(self._on_game_config_changed)
                item.config_deleted.connect(self._on_game_config_deleted)

                self.grid_layout.addWidget(item, row, col)
                self.game_items[game_info['path']] = item

                col += 1
                if col >= columns:
                    col = 0
                    row += 1
            if col != 0:
                row += 1

        add_section("Winlator CMOD", cmod_games)
        add_section("Ludashi", ludashi_games)
        add_section("Winlator Official", winlator_games)
        add_section("Other", other_games)

        self.grid_layout.setRowStretch(row, 1)
        self.load_cached_icons()


    def load_cached_icons(self):
        for path, item in list(self.game_items.items()):
            icon_key = os.path.basename(path)
            cached_icon_path = os.path.join(self.app_config.get_icon_cache_dir(), f"{icon_key}.png")
            if os.path.exists(cached_icon_path):
                try:
                    img = Image.open(cached_icon_path).resize((48, 48), Image.LANCZOS)
                    pixmap = QPixmap.fromImage(img.toqimage()) # Convert PIL Image to QPixmap
                    item.set_icon(pixmap)
                except Exception:
                    item.set_icon(self.placeholder_icon)

    def prompt_for_icon_update(self):
        missing_icons = []
        for path, item in self.game_items.items():
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
            self,
            "Search missing icons?",
            f"""
            {len(missing_icons)} games without icons.\n\n"
            "This process will download the .exe files to your phone temporarily and may take several minutes depending on the number and size of the file\n\n"
            "Wish to continue?""",
            icon=QMessageBox.Question,
            buttons=QMessageBox.Yes | QMessageBox.No,
            app_icon_path=None # No specific app icon for this general question
        )
        if reply == QMessageBox.Yes:
            self.start_icon_extraction_flow(missing_icons)

    def start_icon_extraction_flow(self, tasks):
        self.total_tasks = len(tasks)
        self.completed_tasks_count = 0
        self.progress_dialog = CustomThemedProgressDialog("Extracting Icons", "Cancel", 0, self.total_tasks, self)
        # CustomThemedProgressDialog constructor already sets the title, modality, and min/max.
        # So, the explicit calls for setWindowTitle, setWindowModality, setAutoClose, setMinimumDuration are removed.
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()

        # Create and start workers dynamically
        self.icon_extractor_workers = []
        for _ in range(self.NUM_WORKERS):
            worker = IconExtractorWorker(self.extraction_queue, self.app_config, self.temp_dir, self.placeholder_icon, self.app_config.get_connection_id())
            worker.signals.icon_extracted.connect(self._on_icon_extracted)
            worker.signals.error.connect(self._on_icon_extraction_error) # Connect error signal
            worker.signals.finished.connect(self._on_worker_finished_in_extraction_flow) # Connect worker finished signal
            self.icon_extractor_workers.append(worker)
            if self.main_window:
                self.main_window.start_worker(worker)

        for task in tasks:
            self.extraction_queue.put(task)

        for _ in range(self.NUM_WORKERS):
            self.extraction_queue.put(None) # Add None sentinel for each worker


    def _on_icon_extracted(self, path, success, pixmap=None):
        self.completed_tasks_count += 1
        self.progress_dialog.setValue(self.completed_tasks_count)
        self.progress_dialog.setLabelText(f"Processing {self.completed_tasks_count} of {self.total_tasks}...")

        if path in self.game_items:
            item = self.game_items[path]
            if success and pixmap:
                item.set_icon(pixmap)
            else:
                item.set_icon(self.placeholder_icon)
        
        if self.completed_tasks_count >= self.total_tasks:
            self._on_all_icons_extracted()

    def _on_icon_extraction_error(self, path, error_msg):
        print(f"Error extracting icon for {path}: {error_msg}")
        self.completed_tasks_count += 1 # Increment count even on error
        self.progress_dialog.setValue(self.completed_tasks_count)
        self.progress_dialog.setLabelText(f"Processing {self.completed_tasks_count} of {self.total_tasks}...")

        # If there's an error, make sure the item's icon is set to placeholder
        if path in self.game_items:
            item = self.game_items[path]
            item.set_icon(self.placeholder_icon)
        
        if self.completed_tasks_count >= self.total_tasks:
            self._on_all_icons_extracted()

    def _on_worker_finished_in_extraction_flow(self):
        # This slot is called when a worker finishes.
        # It's primarily for cleanup if needed, but for task completion logic,
        # we rely on completed_tasks_count and _on_all_icons_extracted.
        pass

    def _on_icon_extraction_error(self, path, error_msg):
        # This slot is called when a worker encounters an error during icon extraction
        # The worker itself will still emit icon_extracted with success=False in its finally block
        # So, we just log the error and ensure the progress count is updated.
        print(f"Error extracting icon for {path}: {error_msg}")
        # The progress count and display update is already handled by _on_icon_extracted
        # which will be called regardless of success due to the worker's finally block.
        # No need to increment completed_tasks_count here again.
        # If we need to show specific errors per item, we would do it here.

    # This slot will be called when each worker finishes (after processing its None sentinel)
    # However, with queue.join(), we don't need to explicitly wait for workers to finish
    # for total task completion.
    def _on_worker_finished_in_extraction_flow(self):
        # This can be used for cleanup specific to the worker thread.
        # For now, simply ensures the worker is properly managed by the thread pool.
        pass

    def _on_all_icons_extracted(self):
        if self.progress_dialog.isVisible():
            self.progress_dialog.close()
        show_message_box(self, "Finished", "Icons extraction finished!", app_icon_path=None) # No specific app icon
        self.icon_extractor_workers.clear()
        self.populate_games_grid()

    def execute_launch(self, shortcut_path, game_name):
        game_info = next((g for g in self.all_games if g['path'] == shortcut_path), None)
        if not game_info:
            show_message_box(self, "Error", "Could not find game information to launch.", icon=QMessageBox.Critical)
            return

        package_name = game_info.get('pkg', 'com.winlator.cmod')
        if package_name == 'unknown':
            show_message_box(self, "Error", "Could not determine Winlator package name from shortcut.\nCannot launch game.", icon=QMessageBox.Critical)
            return

        game_specific_config = self.app_config.get_global_values_no_profile().copy()
        game_data = self.app_config.get_winlator_game_config(shortcut_path)
        if game_data:
            game_specific_config.update(game_data)

        game_specific_config['start_app'] = ''

        icon_key = os.path.basename(shortcut_path)
        icon_path = os.path.join(self.app_config.get_icon_cache_dir(), f"{icon_key}.png")
        if not os.path.exists(icon_path):
            icon_path = None

        game_specific_config['shortcut_path'] = shortcut_path
        game_specific_config['package_name'] = package_name

        self.scrcpy_launch_worker = ScrcpyLaunchWorker(
            config_values=game_specific_config,
            window_title=game_name,
            connection_id=self.app_config.get_connection_id(),
            icon_path=icon_path,
            session_type='winlator'
        )
        self.scrcpy_launch_worker.signals.error.connect(lambda msg: self._on_scrcpy_launch_error(msg, icon_path))
        self.scrcpy_launch_worker.signals.scrcpy_process_started.connect(self._on_scrcpy_process_started)
        self.scrcpy_launch_worker.signals.display_id_found.connect(lambda display_id, shortcut_path, package_name: self._on_display_id_found(display_id, shortcut_path, package_name, icon_path))
        if self.main_window:
            self.main_window.start_worker(self.scrcpy_launch_worker)

    def _on_scrcpy_launch_error(self, error_msg, icon_path=None):
        show_message_box(self, "Scrcpy Error", f"Failed to start scrcpy for game: {error_msg}", icon=QMessageBox.Critical, app_icon_path=icon_path)

    def _on_scrcpy_process_started(self, process):
        self.scrcpy_process = process

    def _on_display_id_found(self, display_id, shortcut_path, package_name, icon_path=None):
        if not display_id:
            show_message_box(self, "Error", "Virtual display not found.", icon=QMessageBox.Critical, app_icon_path=icon_path)
            return

        full_config = self.app_config.get_global_values_no_profile().copy()
        game_specific_config = self.app_config.get_winlator_game_config(shortcut_path)
        if game_specific_config:
            full_config.update(game_specific_config)

        windowing_mode_str = full_config.get('windowing_mode', 'Fullscreen')
        windowing_mode_int = 1 if windowing_mode_str == 'Fullscreen' else 2

        self.winlator_launch_worker = WinlatorLaunchWorker(
            shortcut_path=shortcut_path,
            display_id=display_id,
            package_name=package_name,
            connection_id=self.app_config.get_connection_id(),
            windowing_mode=windowing_mode_int
        )
        self.winlator_launch_worker.signals.error.connect(lambda msg: show_message_box(self, "Winlator Launch Error", msg, icon=QMessageBox.Critical, app_icon_path=icon_path))
        if self.main_window:
            self.main_window.start_worker(self.winlator_launch_worker)
