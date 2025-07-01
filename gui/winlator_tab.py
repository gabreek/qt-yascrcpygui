# FILE: gui/winlator_tab.py
# PURPOSE: Cria e gerencia a aba de controle do Winlator com PySide6.

import os
import tempfile
import queue
from PIL import Image

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QGridLayout, QLabel, QCheckBox, QProgressDialog, QStackedWidget, QMessageBox
from PySide6.QtCore import Qt, QSize, QThread, QThreadPool
from PySide6.QtGui import QPixmap, QIcon
import sys

from .winlator_item_widget import WinlatorItemWidget
from utils import adb_handler, scrcpy_handler
from .workers import GameListWorker, IconExtractorWorker, WinlatorLaunchWorker, QueueJoinWorker, ScrcpyLaunchWorker
from .dialogs import show_message_box
from .base_grid_tab import BaseGridTab

class WinlatorTab(BaseGridTab):
    def __init__(self, app_config):
        super().__init__(app_config)
        self.all_games = []
        self.game_items = {}
        self.temp_dir = tempfile.gettempdir()
        self.extraction_queue = queue.Queue()
        self.icon_extractor_workers = []
        self.total_tasks = 0
        self.completed_tasks_count = 0
        self.NUM_WORKERS = 4
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
        self.use_ludashi_check = QCheckBox("Use Ludashi pkg")
        self.use_ludashi_check.setChecked(self.app_config.get('use_ludashi_pkg'))
        self.use_ludashi_check.stateChanged.connect(lambda state: self.app_config.set('use_ludashi_pkg', bool(state)))
        top_panel.addWidget(self.use_ludashi_check)

        self.refresh_button = QPushButton("Refresh Apps")
        self.refresh_button.setFixedSize(90, 20)
        top_panel.addWidget(self.refresh_button)

        self.fetch_icons_button = QPushButton("Refresh Icons")
        self.fetch_icons_button.setFixedSize(90, 20)
        top_panel.addWidget(self.fetch_icons_button)
        self.main_layout.insertLayout(0, top_panel)

        self.refresh_button.clicked.connect(self.refresh_games_list)
        self.fetch_icons_button.clicked.connect(lambda: self.prompt_for_icon_update())

        # Start icon extractor workers
        for _ in range(self.NUM_WORKERS):
            worker = IconExtractorWorker(self.extraction_queue, self.app_config, self.temp_dir, self.placeholder_icon)
            thread = QThread()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            worker.icon_extracted.connect(self._on_icon_extracted)
            thread.start()
            self.icon_extractor_workers.append((thread, worker))

        self.on_device_changed()

    def update_winlator_display(self):
        self.on_device_changed()

    def on_device_changed(self):
        self._clear_grid()
        device_id = self.app_config.get('device_id')
        if not device_id or device_id == "no_device":
            self.info_label.setText("Please connect a device.")
            self.stacked_widget.setCurrentWidget(self.info_label)
            self.refresh_button.setEnabled(False)
            self.fetch_icons_button.setEnabled(False)
        else:
            self.refresh_button.setEnabled(True)
            self.fetch_icons_button.setEnabled(True)
            self.refresh_games_list()





    def refresh_games_list(self):
        device_id = adb_handler.get_connected_device_id()
        if device_id is None or device_id == "no_device":
            self.info_label.setText("Please connect a device to see Winlator games.")
            self.info_label.setVisible(True)
            self.scroll_area.setVisible(False)
            self.refresh_button.setEnabled(True)
            return
        else:
            self.info_label.setVisible(False)
            self.scroll_area.setVisible(True)

        self.refresh_button.setEnabled(False)
        self._clear_grid()
        self.info_label.setText("Searching for games...")
        self.info_label.setVisible(True)

        self.game_list_thread = QThread()
        self.game_list_worker = GameListWorker() # Assuming GameListWorker is defined elsewhere or will be defined
        self.game_list_worker.moveToThread(self.game_list_thread)
        self.game_list_worker.finished.connect(self._on_game_list_loaded)
        self.game_list_worker.error.connect(self._on_game_list_error)
        self.game_list_thread.started.connect(self.game_list_worker.run)
        self.game_list_thread.finished.connect(self.game_list_thread.deleteLater)
        self.game_list_thread.start()

    def _on_game_list_loaded(self, games_with_names):
        self.all_games = sorted([{'name': name, 'path': path} for name, path in games_with_names], key=lambda x: x['name'].lower())

        if not self.all_games:
            self.info_label.setText("No Winlator shortcut found on device.\nPlease export to frontend in Winlator app.")
            self.stacked_widget.setCurrentWidget(self.info_label)
        else:
            self.populate_games_grid()
            self.stacked_widget.setCurrentWidget(self.scroll_area)

        self.refresh_button.setEnabled(True)
        if hasattr(self, 'game_list_thread') and self.game_list_thread:
            self.game_list_thread.quit()
            self.game_list_thread.wait()

    def _on_game_list_error(self, error_msg):
        self.info_label.setText(f"Error: {error_msg}")
        self.stacked_widget.setCurrentWidget(self.info_label)
        self.refresh_button.setEnabled(True)
        if hasattr(self, 'game_list_thread') and self.game_list_thread:
            self.game_list_thread.quit()
            self.game_list_thread.wait()

    def populate_games_grid(self):
        self._clear_grid()

        for i in range(4):
            self.grid_layout.setColumnStretch(i, 1)

        if not self.all_games:
            self.info_label.setText("No Winlator shortcut found.")
            self.info_label.setVisible(True)
            return

        row, col = 0, 0
        for game_info in self.all_games:
            item = WinlatorItemWidget(game_info, self.app_config, self.placeholder_icon) # Use WinlatorItemWidget
            item.launch_requested.connect(self.execute_winlator_flow)
            item.config_saved.connect(self.update_winlator_display) # Refresh display after save
            item.config_deleted.connect(self.update_winlator_display) # Refresh display after delete
            item.icon_dropped.connect(self._on_icon_dropped)

            self.grid_layout.addWidget(item, row, col)
            self.game_items[game_info['path']] = item

            col += 1
            if col > 3:
                col = 0
                row += 1
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
                except Exception as e:
                    print(f"Error loading cached icon for {path}: {e}")
                    item.set_icon(self.placeholder_icon)

    def _on_icon_dropped(self, game_path, filepath):
        # This signal is emitted by WinlatorGameItemWidget after a successful drop
        # The icon is already set on the widget, so we just need to refresh the display if needed
        pass # No explicit action needed here for now

    def prompt_for_icon_update(self):
        missing_icons = []
        for path, item in self.game_items.items():
            icon_key = os.path.basename(path)
            cached_icon_path = os.path.join(self.app_config.get_icon_cache_dir(), f"{icon_key}.png")
            if not os.path.exists(cached_icon_path):
                metadata = self.app_config.get_app_metadata(path)
                if not metadata.get('exe_icon_fetch_failed') and not metadata.get('custom_icon'):
                    missing_icons.append((path, item, cached_icon_path))

        if not missing_icons:
            show_message_box(self, "Icons", "No icons to extract.")
            return

        reply = show_message_box(
            self, "Search missing icons?",
            f"""{len(missing_icons)} games without icons.\n\n"
            "This process will download the .exe files to your phone temporarily and may take several minutes depending on the number and size of the file\n\n"
            "Wish to continue?""",
            icon=QMessageBox.Question,
            buttons=QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.start_icon_extraction_flow(missing_icons)

    def start_icon_extraction_flow(self, tasks):
        self.total_tasks = len(tasks) # Armazena como atributo da instância
        self.completed_tasks_count = 0 # Resetar o contador de tarefas concluídas
        self.progress_dialog = QProgressDialog("Processing...", "Cancel", 0, self.total_tasks, self)
        self.progress_dialog.setWindowTitle("Processing...")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(False) # Keep open until explicitly closed
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()

        for task in tasks:
            self.extraction_queue.put(task)

        # Add sentinels to stop workers after all tasks are processed
        for _ in range(self.NUM_WORKERS):
            self.extraction_queue.put(None)

        # Start a worker to wait for the queue to be empty
        self.queue_join_worker = QueueJoinWorker(self.extraction_queue)
        self.queue_join_worker.signals.finished.connect(self._on_all_icons_extracted)
        QThreadPool.globalInstance().start(self.queue_join_worker)

    def _on_icon_extracted(self, path, success, pixmap=None):
        # This slot is connected to the icon_extracted signal from IconExtractorWorker
        self.completed_tasks_count += 1 # Incrementa o contador de tarefas concluídas
        self.progress_dialog.setValue(self.completed_tasks_count)
        self.progress_dialog.setLabelText(f"Processing {self.completed_tasks_count} of {self.total_tasks}...")

        if path in self.game_items:
            item = self.game_items[path]
            if success and pixmap:
                item.set_icon(pixmap)
            else:
                item.set_icon(self.placeholder_icon)

    def _on_all_icons_extracted(self):
        # This slot is called when queue.join() completes
        self.progress_dialog.close()
        show_message_box(self, "Finished", "Icons extraction finished!")
        self.populate_games_grid() # Refresh grid after extraction

    def execute_winlator_flow(self, shortcut_path, game_name):
        game_specific_config = self.app_config.get_all_values().copy()
        game_data = self.app_config.get_winlator_game_config(shortcut_path)
        if game_data:
            game_specific_config.update(game_data)

        # IMPORTANT: Do NOT set 'start_app' here for Winlator flow
        game_specific_config['start_app'] = '' # Ensure it's empty for initial scrcpy launch

        use_ludashi = self.app_config.get('use_ludashi_pkg')
        package_name = "com.ludashi.benchmark" if use_ludashi else "com.winlator"

        icon_key = os.path.basename(shortcut_path)
        icon_path = os.path.join(self.app_config.get_icon_cache_dir(), f"{icon_key}.png")
        if not os.path.exists(icon_path):
            icon_path = None

        # Pass shortcut_path and package_name to ScrcpyLaunchWorker for later use
        game_specific_config['shortcut_path'] = shortcut_path
        game_specific_config['package_name'] = package_name

        # Use QThread for scrcpy launch to keep UI responsive
        self.scrcpy_launch_thread = QThread()
        self.scrcpy_launch_worker = ScrcpyLaunchWorker(
            config_values=game_specific_config, # Now includes shortcut_path and package_name
            window_title=game_name,
            device_id=adb_handler.get_connected_device_id(),
            icon_path=icon_path,
            session_type='winlator'
        )
        self.scrcpy_launch_worker.moveToThread(self.scrcpy_launch_thread)
        self.scrcpy_launch_worker.finished.connect(self.scrcpy_launch_thread.quit)
        self.scrcpy_launch_worker.finished.connect(self.scrcpy_launch_worker.deleteLater)
        self.scrcpy_launch_thread.finished.connect(self.scrcpy_launch_thread.deleteLater)
        self.scrcpy_launch_worker.error.connect(self._on_scrcpy_launch_error)
        self.scrcpy_launch_worker.scrcpy_process_started.connect(self._on_scrcpy_process_started)
        # Connect display_id_found to a new slot that handles Winlator launch
        self.scrcpy_launch_worker.display_id_found.connect(self._on_display_id_found)
        self.scrcpy_launch_thread.started.connect(self.scrcpy_launch_worker.run)
        self.scrcpy_launch_thread.start()

    def _on_scrcpy_launch_error(self, error_msg):
        show_message_box(self, "Scrcpy Error", f"Failed to start scrcpy for game: {error_msg}", icon=QMessageBox.Critical)

    def _on_scrcpy_process_started(self, process):
        self.scrcpy_process = process

    def _on_display_id_found(self, display_id, shortcut_path, package_name):
        print(f"DEBUG: _on_display_id_found received display_id: {display_id}")
        if not display_id:
            show_message_box(self, "Error", "Virtual display not found.", icon=QMessageBox.Critical)
            return

        # Launch Winlator app in a new thread
        self.winlator_launch_thread = QThread()
        self.winlator_launch_worker = WinlatorLaunchWorker(
            shortcut_path=shortcut_path,
            display_id=display_id,
            package_name=package_name,
            device_id=adb_handler.get_connected_device_id()
        )
        self.winlator_launch_worker.moveToThread(self.winlator_launch_thread)
        self.winlator_launch_worker.finished.connect(self.winlator_launch_thread.quit)
        self.winlator_launch_worker.finished.connect(self.winlator_launch_worker.deleteLater)
        self.winlator_launch_thread.finished.connect(self.winlator_launch_thread.deleteLater)
        self.winlator_launch_worker.error.connect(lambda msg: show_message_box(self, "Winlator Launch Error", msg, icon=QMessageBox.Critical))
        self.winlator_launch_thread.started.connect(self.winlator_launch_worker.run)
        self.winlator_launch_thread.start()




