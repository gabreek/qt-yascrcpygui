# FILE: gui/apps_tab.py
# PURPOSE: Cria e gerencia a aba de Apps com PySide6.
# VERSION: 10.0 (Fixed silent crash and added system apps filter)

import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QScrollArea, QGridLayout, QLabel,
                               QStackedWidget, QMessageBox)
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QPixmap
import sys

from .base_grid_tab import BaseGridTab
from .app_item_widget import AppItemWidget
from .workers import AppListWorker, IconWorker, ScrcpyLaunchWorker
from .dialogs import show_message_box



# --- ABA DE APPS ---
class AppsTab(BaseGridTab):
    def __init__(self, app_config, main_window=None):
        super().__init__(app_config, main_window)

        self.app_items = self.items # Alias for clarity

        # Determine the base path for resources
        if getattr(sys, 'frozen', False):
            # Running in a PyInstaller bundle
            base_path = sys._MEIPASS
        else:
            # Running in a normal Python environment
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        self.placeholder_icon = QPixmap(os.path.join(base_path, "gui/placeholder.png"))
        self.icon_cache_dir = self.app_config.get_icon_cache_dir()
        self.thread_pool = QThreadPool.globalInstance()

        top_panel = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search apps...")

        self.refresh_button = QPushButton("Refresh Apps")
        self.refresh_button.setFixedSize(90, 20)

        top_panel.addWidget(self.search_input)
        top_panel.addWidget(self.refresh_button)
        self.main_layout.insertLayout(0, top_panel)

        self.refresh_button.clicked.connect(self.refresh_apps_list)
        self.search_input.textChanged.connect(self.filter_apps)

        
        self.on_device_changed()

    def on_device_changed(self):
        self._clear_grid()
        device_id = self.app_config.get('device_id')
        if not device_id or device_id == "no_device":
            self.show_message("Please connect a device.")
            self.refresh_button.setEnabled(False)
        else:
            self.refresh_button.setEnabled(True)

            cached_data = self.app_config.get_app_list_cache()
            if cached_data and cached_data.get('user_apps'):
                self.load_apps_from_cache_and_update_display()
            else:
                self.refresh_apps_list()

    def refresh_apps_list(self):
        if self.main_window and hasattr(self.main_window, 'pause_device_check'):
            self.main_window.pause_device_check()

        self.show_message("Loading apps from device...")
        self.refresh_button.setEnabled(False)
        current_device_id = self.app_config.get('device_id')

        worker = AppListWorker(current_device_id)
        worker.signals.result.connect(self._on_app_list_loaded)
        worker.signals.error.connect(self._on_app_list_error)
        if self.main_window and hasattr(self.main_window, 'resume_device_check'):
            worker.finished.connect(self.main_window.resume_device_check)

        self.thread_pool.start(worker)

    def load_apps_from_cache_and_update_display(self):
        cached_data = self.app_config.get_app_list_cache()
        if cached_data and cached_data.get('user_apps'):
               self._update_display()
        else:
            self.show_message("App list is empty. Click 'Refresh Apps' to load from device.")

    def _on_app_list_loaded(self, result_tuple):
        user_apps, system_apps = result_tuple

        user_app_list = [{'key': pkg, 'name': name} for name, pkg in user_apps.items()]


        new_cache = {'user_apps': user_app_list}
        self.app_config.save_app_list_cache(new_cache)

        self._update_display()
        self.refresh_button.setEnabled(True)

    def _update_display(self):
        cached_data = self.app_config.get_app_list_cache()
        if not cached_data:
            self.show_message("App list is empty. Click 'Refresh Apps'.")
            return

        user_apps = cached_data.get('user_apps', [])

        apps_to_display = list(user_apps)

        if not apps_to_display:
            self.show_message("No user applications to display.")
            return

        self._clear_grid()
        self.show_grid()
        self._populate_grid(apps_to_display)
        self.filter_apps()

    def _on_app_list_error(self, error_msg):
        self.show_message(f"Error: {error_msg}")
        self.refresh_button.setEnabled(True)

    def _populate_grid(self, apps):
        pinned = sorted([a for a in apps if self.app_config.get_app_metadata(a['key']).get('pinned')], key=lambda x: x['name'].lower())
        unpinned = sorted([a for a in apps if not self.app_config.get_app_metadata(a['key']).get('pinned')], key=lambda x: x['name'].lower())

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
            for app_info in app_list:
                widget = AppItemWidget({'pkg_name': app_info['key'], 'app_name': app_info['name']}, self.app_config, self.placeholder_icon)
                widget.pin_toggled.connect(self.on_pin_toggled)
                widget.launch_requested.connect(self.on_launch_requested)
                widget.delete_config_requested.connect(self.on_delete_config_requested)
                widget.settings_requested.connect(self.on_settings_requested)
                self.grid_layout.addWidget(widget, row, col)
                self.app_items[app_info['key']] = widget
                self.load_icon(app_info['key'], app_info['name'])
                col += 1
                if col >= columns: col = 0; row += 1
            # Ensure row advances to the next line if the last row was partially filled
            if col != 0: 
                row += 1

        add_section("Pinned", pinned)
        add_section("All Apps", unpinned)
        self.grid_layout.setRowStretch(row, 1)

    def on_pin_toggled(self):
        self._update_display()

    def on_delete_config_requested(self, pkg_name):
        if not (widget := self.app_items.get(pkg_name)): return
        app_name = widget.item_name

        reply = show_message_box(
            self,
            'Delete Configuration',
            f"Are you sure you want to delete the specific configuration for<br><b>{app_name}</b>?",
            icon=QMessageBox.Question,
            buttons=QMessageBox.Yes | QMessageBox.No,
            default_button=QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.app_config.delete_app_scrcpy_config(pkg_name):
                show_message_box(self, "Success", f"Specific configuration for {app_name} has been deleted.", icon=QMessageBox.Information)
            else:
                show_message_box(self, "Not Found", f"No specific configuration was found for {app_name}.", icon=QMessageBox.Warning)

    def on_settings_requested(self, pkg_name):
        app_name = "this app"
        if widget := self.app_items.get(pkg_name):
            app_name = widget.item_name

        current_config = self.app_config.get_all_values().copy()
        keys_to_exclude = {'device_id', 'theme', 'use_ludashi_pkg', 'device_commercial_name', 'show_system_apps'}
        app_specific_config = {k: v for k, v in current_config.items() if k not in keys_to_exclude}

        self.app_config.save_app_scrcpy_config(pkg_name, app_specific_config)

        show_message_box(self, "Success", f"Configurações globais salvas para <b>{app_name}</b>.", icon=QMessageBox.Information)

    def filter_apps(self):
        search_text = self.search_input.text().lower()
        if not self.app_items: return
        for pkg_name, widget in self.app_items.items():
            widget.setVisible(search_text in widget.item_name.lower())

    def load_icon(self, pkg_name, app_name):
        cached_icon_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")
        if os.path.exists(cached_icon_path):
            self._on_icon_loaded(pkg_name, QPixmap(cached_icon_path))
            return
        metadata = self.app_config.get_app_metadata(pkg_name)
        if metadata.get('has_custom_icon') or metadata.get('icon_fetch_failed'): return
        worker = IconWorker(pkg_name, app_name, self.icon_cache_dir, self.app_config)
        worker.signals.finished.connect(self._on_icon_loaded)
        worker.signals.error.connect(self._on_icon_error)
        self.thread_pool.start(worker)

    def _on_icon_loaded(self, pkg_name, pixmap):
        if widget := self.app_items.get(pkg_name): widget.set_icon(pixmap)

    def _on_icon_error(self, pkg_name, error_msg):
        print(f"Icon error for {pkg_name}: {error_msg}")
        self.app_config.save_app_metadata(pkg_name, {'icon_fetch_failed': True})

    def on_launch_requested(self, pkg_name, app_name):
        config_to_use = self.app_config.get_all_values().copy()
        app_metadata = self.app_config.get_app_metadata(pkg_name)
        if 'config' in app_metadata and app_metadata['config']:
            config_to_use.update(app_metadata['config'])
        config_to_use['start_app'] = pkg_name
        window_title = app_name
        device_id = self.app_config.get('device_id')
        icon_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")
        if not os.path.exists(icon_path): icon_path = None
        launch_worker = ScrcpyLaunchWorker(config_to_use, window_title, device_id, icon_path, 'app')
        launch_worker.error.connect(lambda msg: show_message_box(self, "Scrcpy Error", msg, icon=QMessageBox.Critical))
        self.thread_pool.start(launch_worker.run)
