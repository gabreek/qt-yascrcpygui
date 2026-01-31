import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QScrollArea, QGridLayout, QLabel,
                               QMessageBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QPixmap
import sys

from .base_grid_tab import BaseGridTab
from .workers import AppListWorker, IconWorker, ScrcpyLaunchWorker, AppLaunchWorker
from .dialogs import show_message_box



# --- ABA DE APPS ---
class AppsTab(BaseGridTab):
    launch_requested = Signal(str, str)
    config_changed = Signal(str)
    config_deleted = Signal(str)

    def __init__(self, app_config, main_window=None):
        super().__init__(app_config, main_window)

        # This will hold the complete list of app data dictionaries
        self.all_apps_data = []

        # Determine the base path for resources
        base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

        self.placeholder_icon_path = os.path.join(base_path, "gui/placeholder.png")
        self.launcher_icon_path = os.path.join(base_path, "gui/launcher.png")
        self.icon_cache_dir = self.app_config.get_icon_cache_dir()

        top_panel = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search apps...")

        self.refresh_button = QPushButton("Refresh Apps")

        top_panel.addWidget(self.search_input)
        top_panel.addWidget(self.refresh_button)
        self.main_layout.insertLayout(0, top_panel)

        self.refresh_button.clicked.connect(self.refresh_apps_list)
        self.search_input.textChanged.connect(self.filter_apps)

        self._connect_qml_signals()
        self.on_device_changed()

    def _connect_qml_signals(self):
        root = self.quick_widget.rootObject()
        if not root:
            QTimer.singleShot(100, self._connect_qml_signals)
            return
        
        root.launchRequested.connect(self._on_qml_launch_requested)
        root.settingsRequested.connect(self._on_qml_settings_requested)
        root.deleteConfigRequested.connect(self._on_qml_delete_config_requested)
        root.pinToggled.connect(self.on_pin_toggled)
        # root.iconDropped.connect(self.on_icon_dropped) # TODO: Implement drop handling

    @Slot(str, str)
    def _on_qml_settings_requested(self, itemKey, itemType):
        # The QML sends both key and type, but for apps we only need the key (pkg_name).
        self.on_settings_requested(itemKey)

    @Slot(str, str)
    def _on_qml_delete_config_requested(self, itemKey, itemType):
        # The QML sends both key and type, but for apps we only need the key (pkg_name).
        self.on_delete_config_requested(itemKey)

    @Slot(str, str)
    def _on_qml_launch_requested(self, itemKey, itemName):
        """Slot to receive launch request from QML and emit the Python signal."""
        self.launch_requested.emit(itemKey, itemName)

    def on_device_changed(self):
        self._clear_grid()
        self.all_apps_data = []
        device_id = self.app_config.get_connection_id()
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
        current_device_id = self.app_config.get_connection_id()
        show_system_apps_setting = self.app_config.get('show_system_apps', False)

        worker = AppListWorker(current_device_id, show_system_apps_setting)
        worker.signals.result.connect(self._on_app_list_loaded)
        worker.signals.error.connect(self._on_app_list_error)
        if self.main_window and hasattr(self.main_window, 'resume_device_check'):
            worker.signals.finished.connect(self.main_window.resume_device_check)

        if self.main_window:
            self.main_window.start_worker(worker)

    def load_apps_from_cache_and_update_display(self):
        cached_data = self.app_config.get_app_list_cache()
        if cached_data and cached_data.get('user_apps'):
               self._update_display()
        else:
            self.show_message("App list is empty. Click 'Refresh Apps' to load from device.")

    def _on_app_list_loaded(self, result_tuple):
        user_apps, system_apps = result_tuple

        user_app_list = [{'key': pkg, 'name': name} for name, pkg in user_apps.items()]
        system_app_list = [{'key': pkg, 'name': name} for name, pkg in system_apps.items()]


        new_cache = {
            'user_apps': user_app_list,
            'system_apps': system_app_list,
        }
        self.app_config.save_app_list_cache(new_cache)

        self._update_display()
        self.refresh_button.setEnabled(True)

    def _update_display(self):
        cached_data = self.app_config.get_app_list_cache()
        if not cached_data:
            self.show_message("App list is empty. Click 'Refresh Apps'.")
            return

        user_apps = cached_data.get('user_apps', [])
        system_apps = cached_data.get('system_apps', [])
        show_system_apps = self.app_config.get('show_system_apps', False)

        apps_to_process = list(user_apps)
        if show_system_apps:
            apps_to_process.extend(system_apps)

        if not apps_to_process:
            self.show_message("No applications to display.")
            return
        
        self.show_grid()
        self._populate_grid_model(apps_to_process)
        self.filter_apps() # This will apply the current filter and update the QML model

    def _on_app_list_error(self, error_msg):
        self.show_message(f"Error: {error_msg}")
        self.refresh_button.setEnabled(True)

    def _populate_grid_model(self, apps_from_cache):
        self.all_apps_data = [] # Reset
        
        launcher_pkg = self.app_config.get('default_launcher')
        launcher_name = 'Launcher'

        # Add launcher info first if it exists
        if launcher_pkg:
            self.all_apps_data.append({
                'key': launcher_pkg,
                'name': launcher_name,
                'item_type': "app",
                'is_launcher_shortcut': True,
                'icon_path': QUrl.fromLocalFile(self.launcher_icon_path).toString(),
                'is_pinned': self.app_config.get_app_metadata(launcher_pkg).get('pinned', False)
            })

        for app_info in apps_from_cache:
            # Handle both old ('pkg_name') and new ('key') cache formats, and ensure they are not empty
            pkg_name = app_info.get('key') or app_info.get('pkg_name')
            app_name = app_info.get('name') or app_info.get('app_name')

            if not pkg_name or not app_name:
                print(f"Skipping malformed app_info: {app_info}") # Debug print
                continue # Skip malformed records

            # Avoid adding the launcher app twice if it's in the main list
            if launcher_pkg and pkg_name == launcher_pkg:
                continue
            
            metadata = self.app_config.get_app_metadata(pkg_name)
            
            icon_path_file_exists = False
            icon_path_url = ""
            cached_icon_full_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")

            if os.path.exists(cached_icon_full_path):
                icon_path_url = QUrl.fromLocalFile(cached_icon_full_path).toString()
                icon_path_file_exists = True
            
            if not icon_path_file_exists:
                if os.path.exists(self.placeholder_icon_path):
                    icon_path_url = QUrl.fromLocalFile(self.placeholder_icon_path).toString()
                else:
                    print(f"WARNING: Placeholder icon not found at {self.placeholder_icon_path}. Icons will be blank.")
                    icon_path_url = ""
                
                # Load icon if not failed before and no custom icon
                if not metadata.get('has_custom_icon') and not metadata.get('icon_fetch_failed'):
                    self.load_icon(pkg_name, app_name)
            
            self.all_apps_data.append({
                'key': pkg_name,
                'name': app_name,
                'item_type': "app",
                'is_launcher_shortcut': False,
                'icon_path': icon_path_url,
                'is_pinned': metadata.get('pinned', False)
            })

    @Slot(str)
    def on_pin_toggled(self, pkg_name):
        # Update the pin status in the config
        metadata = self.app_config.get_app_metadata(pkg_name)
        is_pinned = not metadata.get('pinned', False)
        self.app_config.save_app_metadata(pkg_name, {'pinned': is_pinned})
        
        # Update the model data in-place
        for app_data in self.all_apps_data:
            if app_data['key'] == pkg_name:
                app_data['is_pinned'] = is_pinned
                break
        
        # Re-apply filter and sorting
        self.filter_apps()
        self.config_changed.emit(pkg_name) # Notify other components if needed

    @Slot(str)
    def on_delete_config_requested(self, pkg_name):
        app_name = next((app['name'] for app in self.all_apps_data if app['key'] == pkg_name), "N/A")

        icon_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")
        if not os.path.exists(icon_path):
            icon_path = None

        reply = show_message_box(
            self,
            'Delete Configuration',
            f"Are you sure you want to delete the specific configuration for<br><b>{app_name}</b>?",
            icon=QMessageBox.Question,
            buttons=QMessageBox.Yes | QMessageBox.No,
            default_button=QMessageBox.No,
            app_icon_path=icon_path
        )

        if reply == QMessageBox.Yes:
            if self.app_config.delete_app_scrcpy_config(pkg_name):
                show_message_box(self, "Success", f"Specific configuration for {app_name} has been deleted.", icon=QMessageBox.Information, app_icon_path=icon_path)
                self.config_deleted.emit(pkg_name)
            else:
                show_message_box(self, "Not Found", f"No specific configuration was found for {app_name}.", icon=QMessageBox.Warning, app_icon_path=icon_path)

    @Slot(str)
    def on_settings_requested(self, pkg_name):
        app_data = next((app for app in self.all_apps_data if app['key'] == pkg_name), None)
        if not app_data: return
        
        app_name = app_data['name']
        is_launcher_shortcut = app_data.get('is_launcher_shortcut', False)

        if is_launcher_shortcut:
            icon_path = self.launcher_icon_path
        else:
            cached_icon_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")
            icon_path = cached_icon_path if os.path.exists(cached_icon_path) else None

        is_launcher = (pkg_name == self.app_config.get('default_launcher'))
        global_config = self.app_config.get_global_values_no_profile()
        global_is_virtual = global_config.get('new_display') and global_config.get('new_display') != 'Disabled'

        if is_launcher and global_is_virtual:
            reply = show_message_box(
                self, 'Virtual Display Incompatibility',
                "Saving a specific configuration for the Launcher while a global virtual display is active is not recommended.\n\n"
                "Would you like to save a specific configuration for the Launcher with 'Max Size' set to 0 (native resolution) instead?",
                icon=QMessageBox.Warning, buttons=QMessageBox.Yes | QMessageBox.No, default_button=QMessageBox.Yes, app_icon_path=icon_path
            )
            if reply == QMessageBox.Yes:
                config_to_save = global_config.copy()
                config_to_save['new_display'] = 'Disabled'
                config_to_save['max_size'] = '0'
            else:
                show_message_box(
                    self, 'Action Cancelled',
                    "No specific configuration was saved for the Launcher.\n\n"
                    "To use the Launcher without a virtual display, please go to the 'Scrcpy' tab, "
                    "set 'Virtual Display' to 'Disabled', and select a desired 'Max Size'.",
                    icon=QMessageBox.Information, app_icon_path=icon_path
                )
                return
        else:
            config_to_save = global_config.copy()

        keys_to_exclude = {'device_id', 'theme', 'device_commercial_name', 'show_system_apps', 'default_launcher'}
        app_specific_config = {k: v for k, v in config_to_save.items() if k not in keys_to_exclude}

        self.app_config.save_app_scrcpy_config(pkg_name, app_specific_config)
        show_message_box(self, "Success", f"Current settings have been saved as a specific configuration for <b>{app_name}</b>.", icon=QMessageBox.Information, app_icon_path=icon_path)
        self.config_changed.emit(pkg_name)

    def filter_apps(self):
        search_text = self.search_input.text().lower()

        # Filter all apps that match the search text
        filtered_apps = [
            app for app in self.all_apps_data
            if search_text in app['name'].lower()
        ]

        # Separate the launcher from the rest of the apps
        launcher_item = None
        other_apps = []
        for app in filtered_apps:
            if app.get('is_launcher_shortcut', False):
                launcher_item = app
            else:
                other_apps.append(app)

        # Sort the other apps (pinned first, then by name)
        sorted_other_apps = sorted(other_apps, key=lambda x: (not x.get('is_pinned', False), x['name'].lower()))

        pinned_apps = [app for app in sorted_other_apps if app.get('is_pinned', False)]
        unpinned_apps = [app for app in sorted_other_apps if not app.get('is_pinned', False)]

        # Add the launcher to the correct list based on pinned items
        if launcher_item:
            if pinned_apps:
                pinned_apps.insert(0, launcher_item)
            else:
                unpinned_apps.insert(0, launcher_item)

        qml_model_data = []

        if pinned_apps:
            qml_model_data.append({'isSeparator': True, 'text': 'Pinned Apps'})
            qml_model_data.extend(pinned_apps)

        if unpinned_apps:
            qml_model_data.append({'isSeparator': True, 'text': 'All Apps'})
            qml_model_data.extend(unpinned_apps)

        self._update_grid_model(qml_model_data)

    def load_icon(self, pkg_name, app_name):
        # This check is now implicit in _populate_grid_model
        # The worker is started if the icon file doesn't exist and hasn't failed before.
        worker = IconWorker(pkg_name, app_name, self.icon_cache_dir, self.app_config)
        worker.signals.finished.connect(self._on_icon_loaded)
        worker.signals.error.connect(self._on_icon_error)
        if self.main_window:
            self.main_window.start_worker(worker)

    @Slot(str, QPixmap)
    def _on_icon_loaded(self, pkg_name, pixmap):
        if not pixmap.isNull():
            # Find the app in the model and update its icon path
            for app_data in self.all_apps_data:
                if app_data['key'] == pkg_name:
                    new_icon_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")
                    app_data['icon_path'] = QUrl.fromLocalFile(new_icon_path).toString()
                    break
            # Refresh the view
            self.filter_apps()

    @Slot(str, str)
    def _on_icon_error(self, pkg_name, error_msg):
        self.app_config.save_app_metadata(pkg_name, {'icon_fetch_failed': True})
        # The placeholder is already set, so no visual change is needed here.

    def _on_display_id_found_for_alt_launch(self, display_id, shortcut_path, package_name):
        app_icon_path = os.path.join(self.icon_cache_dir, f"{package_name}.png")
        if not os.path.exists(app_icon_path):
            app_icon_path = None
        if not display_id:
            show_message_box(self, "Error", "Virtual display not found for alternate launch.", icon=QMessageBox.Critical, app_icon_path=app_icon_path)
            return

        full_config = self.app_config.get_global_values_no_profile().copy()
        if app_specific_config := self.app_config.get_app_metadata(package_name).get('config', {}):
            full_config.update(app_specific_config)

        windowing_mode_str = full_config.get('windowing_mode', 'Fullscreen')
        windowing_mode_int = 1 if windowing_mode_str == 'Fullscreen' else 2

        app_launch_worker = AppLaunchWorker(
            package_name=package_name, display_id=display_id,
            windowing_mode=windowing_mode_int, connection_id=self.app_config.get_connection_id()
        )
        app_launch_worker.signals.error.connect(lambda msg: show_message_box(self, "App Launch Error", msg, icon=QMessageBox.Critical, app_icon_path=app_icon_path))
        if self.main_window:
            self.main_window.start_worker(app_launch_worker)

    def execute_launch(self, package_name, app_name):
        config_to_use = self.app_config.get_global_values_no_profile().copy()
        app_metadata = self.app_config.get_app_metadata(package_name)

        if 'config' in app_metadata and app_metadata['config']:
            config_to_use.update(app_metadata['config'])

        use_alt_launch = config_to_use.get('alternate_launch_method', False)
        is_launcher = (package_name == self.app_config.get('default_launcher'))
        
        session_type = 'app'
        if is_launcher:
            if config_to_use.get('new_display') and config_to_use.get('new_display') != 'Disabled':
                config_to_use['new_display'] = 'Disabled'
                config_to_use['max_size'] = '0'
            config_to_use['start_app'] = 'launcher_shortcut'
        elif use_alt_launch:
            session_type = 'app_alt_launch'
            config_to_use['start_app'] = ''
            config_to_use['package_name_for_alt_launch'] = package_name
        else:
            config_to_use['start_app'] = package_name

        icon_path = self.launcher_icon_path if is_launcher else os.path.join(self.icon_cache_dir, f"{package_name}.png")
        if not os.path.exists(icon_path):
            icon_path = None

        launch_worker = ScrcpyLaunchWorker(config_to_use, app_name, self.app_config.get_connection_id(), icon_path, session_type)
        launch_worker.signals.error.connect(lambda msg: show_message_box(self, "Scrcpy Error", msg, icon=QMessageBox.Critical, app_icon_path=icon_path))
        
        if use_alt_launch and not is_launcher:
            launch_worker.signals.display_id_found.connect(self._on_display_id_found_for_alt_launch)

        if self.main_window:
            self.main_window.start_worker(launch_worker)
