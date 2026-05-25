import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QScrollArea, QGridLayout, QLabel,
                               QMessageBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QPixmap
import sys
import time
import queue # Added for managing download queue
import gc

from .base_grid_tab import BaseGridTab
from .workers import (AppListWorker, IconWorker, ScrcpyLaunchWorker, AppLaunchWorker, 
                      IconSaveWorker, BatchIconDownloadWorker, BatchSaveWorker)
from .dialogs import show_message_box
from .session_dialogs import CreateSessionDialog, FoldersManagerDialog
from .common_widgets import CustomThemedProgressDialog
from utils.constants import *



# --- ABA DE APPS ---
class AppsTab(BaseGridTab):
    launch_requested = Signal(str, str)
    config_changed = Signal(str)
    config_deleted = Signal(str)

    def __init__(self, app_config, main_window=None):
        super().__init__(app_config, main_window)

        # This will hold the complete list of app data dictionaries
        self.all_apps_data = []

        # Batch icon download related attributes
        self.pending_icon_downloads = {} # Stores pkg_name: app_name for icons to download
        self.download_queue = queue.Queue()
        self.icon_download_workers = []
        self.total_icon_tasks = 0
        self.completed_icon_tasks = 0
        self.NUM_ICON_WORKERS = 5 # Number of concurrent icon download workers

        # Determine the base path for resources
        base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

        self.placeholder_icon_path = os.path.join(base_path, "gui/placeholder.png")
        self.launcher_icon_path = os.path.join(base_path, "gui/launcher.png")
        self.icon_cache_dir = self.app_config.get_icon_cache_dir()

        self._last_model_fingerprint = None # 8. Otimização de reconstrução do modelo

        top_panel = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.app_config.tr('apps_tab', 'search_placeholder'))

        self.refresh_button = QPushButton(self.app_config.tr('apps_tab', 'refresh_btn'))
        
        # 7. Botão "Folders" como ícone
        self.folders_button = QPushButton("📁")
        self.folders_button.setToolTip(self.app_config.tr('apps_tab', 'folders_btn'))
        self.folders_button.setFixedWidth(35)

        top_panel.addWidget(self.search_input)
        top_panel.addWidget(self.refresh_button)
        top_panel.addWidget(self.folders_button)
        self.main_layout.insertLayout(0, top_panel)

        self.refresh_button.clicked.connect(self.refresh_apps_list)
        self.folders_button.clicked.connect(self.open_folders_manager)
        
        # 6. Campo de busca com debounce
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self.filter_apps)
        self.search_input.textChanged.connect(self._search_timer.start)

        self._connect_qml_signals()
        self.on_device_changed()

    def trigger_icon_redownload(self):
        """Deletes existing icon files and clears failure flags to force a complete re-download."""
        print("Forcing icon redownload for all apps...")
        for app_data in self.all_apps_data:
            pkg_name = app_data['key']
            if not app_data.get('is_launcher_shortcut'):
                # 1. Clear failure flag in metadata
                self.app_config.save_app_metadata(pkg_name, {'icon_fetch_failed': False})

                # 2. Delete local icon file if it exists to force redownload
                cached_icon_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")
                if os.path.exists(cached_icon_path):
                    try:
                        os.remove(cached_icon_path)
                    except Exception as e:
                        print(f"Error deleting icon for {pkg_name}: {e}")

        # 3. Update display which will identify missing icons and trigger the batch download
        self._update_display()

    def stop_all_workers(self):
        """Clears the download queue and stops all icon download workers."""
        if not hasattr(self, 'download_queue'):
            return

        print("Stopping AppsTab workers...")
        # Clear existing queue
        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
                self.download_queue.task_done()
            except queue.Empty:
                break

        # Add sentinel values for each possible worker to ensure they stop
        for _ in range(self.NUM_ICON_WORKERS):
            self.download_queue.put(None)

        print("AppsTab workers signaled to stop.")

    def open_folders_manager(self):
        dialog = FoldersManagerDialog(self.app_config, self, self)
        dialog.exec()

    def retranslate_ui(self):
        """Updates all labels and UI texts in the tab."""
        self.search_input.setPlaceholderText(self.app_config.tr('apps_tab', 'search_placeholder'))
        self.refresh_button.setText(self.app_config.tr('apps_tab', 'refresh_btn'))
        # Refresh the grid display and strings
        self.update_strings()
        self.filter_apps()

    def _connect_qml_signals(self):
        root = self.quick_widget.rootObject()
        if not root:
            QTimer.singleShot(100, self._connect_qml_signals)
            return

        root.launchRequested.connect(self._on_qml_launch_requested)
        root.settingsRequested.connect(self._on_qml_settings_requested)
        root.deleteConfigRequested.connect(self._on_qml_delete_config_requested)
        root.iconDropped.connect(self.on_icon_dropped)
        root.sectionToggled.connect(self.on_section_toggled)
        root.launchLauncherRequested.connect(self.execute_launcher_launch)
        root.folderRequested.connect(self.open_create_session_dialog)
        root.moveRequested.connect(self.on_move_to_folder)
        root.quickAccessRequested.connect(self.on_quick_access_requested)

        # Initialize folder list in QML
        self._update_folder_list_in_qml(root)

    def _update_folder_list_in_qml(self, root=None):
        if not root: root = self.quick_widget.rootObject()
        if root:
            # Refresh from app_config and filter out 'all'
            folders = [f for f in self.app_config.get_custom_sessions().keys() if f != 'all']
            root.setProperty("folderList", folders)
            root.setProperty("allAppsText", self.app_config.tr('apps_tab', 'all_section'))
            root.setProperty("settingsText", self.app_config.tr('common', 'settings'))
            root.setProperty("deleteConfigText", self.app_config.tr('apps_tab', 'delete_config_title'))
            root.setProperty("moveToText", self.app_config.tr('apps_tab', 'move_to'))
            root.setProperty("createNewFolderText", self.app_config.tr('apps_tab', 'create_session_title'))
            root.setProperty("launcherText", self.app_config.tr('apps_tab', 'launcher_label'))
            root.setProperty("quickAccessText", self.app_config.tr('apps_tab', 'quick_access_label'))

    @Slot(str, str)
    def on_move_to_folder(self, pkg_name, folder_name):
        metadata = self.app_config.get_app_metadata(pkg_name)
        pinned_val = metadata.get('pinned', "")
        if not isinstance(pinned_val, str): pinned_val = ""
        parts = [p.strip() for p in pinned_val.split(',') if p.strip()]
        
        is_qqs = CONF_QUICK_ACCESS in parts
        
        # Replace non-qqs parts with actual_folder
        actual_folder = "" if folder_name == "all" else folder_name
        new_parts = [actual_folder] if actual_folder else []
        if is_qqs:
            new_parts.append(CONF_QUICK_ACCESS)
            
        new_pinned = ",".join(new_parts)
        self.app_config.save_app_metadata(pkg_name, {'pinned': new_pinned})
        
        # Surgical update: find item in all_apps_data and update it
        for app in self.all_apps_data:
            if app['key'] == pkg_name:
                app['pinned'] = new_pinned
                break
        
        self.filter_apps()

    @Slot(str, bool)
    def on_quick_access_requested(self, pkg_name, checked):
        metadata = self.app_config.get_app_metadata(pkg_name)
        pinned_val = metadata.get('pinned', "")
        if not isinstance(pinned_val, str): pinned_val = ""
        parts = [p.strip() for p in pinned_val.split(',') if p.strip()]
        
        if checked:
            if CONF_QUICK_ACCESS not in parts: parts.append(CONF_QUICK_ACCESS)
        else:
            if CONF_QUICK_ACCESS in parts: parts.remove(CONF_QUICK_ACCESS)
            
        new_pinned = ",".join(parts)
        self.app_config.save_app_metadata(pkg_name, {'pinned': new_pinned})
        
        # Surgical update: find item in all_apps_data and update it
        for app in self.all_apps_data:
            if app['key'] == pkg_name:
                app['pinned'] = new_pinned
                break
        
        self.filter_apps()


    @Slot(str)
    def open_create_session_dialog(self, pkg_name=None):
        # Pass all apps to the dialog
        selected_apps = [pkg_name] if pkg_name else None
        dialog = CreateSessionDialog(self.app_config, self.all_apps_data, self, selected_apps=selected_apps)
        if dialog.exec():
            name = dialog.session_name
            apps = dialog.selected_apps
            if not name or name == 'all': return
            self.app_config.save_custom_session(name)
            for pkg in apps:
                self.app_config.save_app_metadata(pkg, {'pinned': name})
            self.filter_apps()
            self._update_folder_list_in_qml()

    @Slot()
    def execute_launcher_launch(self):
        launcher_pkg = self.app_config.get(CONF_DEFAULT_LAUNCHER)
        if launcher_pkg:
            self.execute_launch(launcher_pkg, "Launcher")
        else:
            show_message_box(self, self.app_config.tr('common', 'error'), "Launcher not configured.")

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

    def save_session_state(self, session_id, collapsed):
        self.app_config.save_custom_session(session_id, collapsed)

    def on_device_changed(self):
        self._clear_grid()
        self.all_apps_data = []
        self._last_model_fingerprint = None
        device_id = self.app_config.get_connection_id()
        if not device_id or device_id == "no_device":
            self.show_message(self.app_config.tr('scrcpy_tab', 'labels', key='please_connect'))
            self.refresh_button.setEnabled(False)
            self.folders_button.setEnabled(False)
        else:
            self.refresh_button.setEnabled(True)
            self.folders_button.setEnabled(True)

            # Load collapsed sections from config
            self.collapsed_sections = set()
            custom_sessions = self.app_config.get_custom_sessions()
            for name, data in custom_sessions.items():
                if data.get('collapsed'):
                    self.collapsed_sections.add(name)

            cached_data = self.app_config.get_app_list_cache()
            if cached_data and cached_data.get('user_apps'):
                self.load_apps_from_cache_and_update_display()
            else:
                self.refresh_apps_list()

    def refresh_apps_list(self):
        if self.main_window and hasattr(self.main_window, 'pause_device_check'):
            self.main_window.pause_device_check()

        self.show_message(self.app_config.tr('apps_tab', 'loading_from_device'))
        self.refresh_button.setEnabled(False)
        current_device_id = self.app_config.get_connection_id()
        show_system_apps_setting = self.app_config.get(CONF_SHOW_SYSTEM_APPS, False)

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
            self.show_message(self.app_config.tr('apps_tab', 'empty_list'))

    def _on_app_list_loaded(self, result_tuple):
        user_apps, system_apps = result_tuple

        user_app_list = [{'key': pkg, 'name': name} for name, pkg in user_apps.items()]
        system_app_list = [{'key': pkg, 'name': name} for name, pkg in system_apps.items()]


        new_cache = {
            'user_apps': user_app_list,
            'system_apps': system_app_list,
        }
        self.app_config.save_app_list_cache(new_cache)

        # Synchronize memory cache for ScrcpyTab profile filtering
        self.app_config.device_app_cache['installed_apps'] = set(user_apps.values()) | set(system_apps.values())

        self._update_display()
        self.refresh_button.setEnabled(True)
        gc.collect()

    def _update_display(self):
        cached_data = self.app_config.get_app_list_cache()
        if not cached_data:
            self.show_message(self.app_config.tr('apps_tab', 'empty_list'))
            return

        user_apps = cached_data.get('user_apps', [])
        system_apps = cached_data.get('system_apps', [])
        show_system_apps = self.app_config.get('show_system_apps', False)

        apps_to_process = list(user_apps)
        if show_system_apps:
            apps_to_process.extend(system_apps)

        if not apps_to_process:
            self.show_message(self.app_config.tr('apps_tab', 'no_apps'))
            return

        self.show_grid()
        self._populate_grid_model(apps_to_process)
        self.filter_apps() # This will apply the current filter and update the QML model
        self._update_folder_list_in_qml() # Ensure folder list is updated

    def _on_app_list_error(self, error_msg):
        self.show_message(f"{self.app_config.tr('common', 'error')}: {error_msg}")
        self.refresh_button.setEnabled(True)

    def _populate_grid_model(self, apps_from_cache):
        self.all_apps_data = [] # Reset

        launcher_pkg = self.app_config.get(CONF_DEFAULT_LAUNCHER)

        # Pass launcher key to QML
        root = self.quick_widget.rootObject()
        if root:
            root.setProperty("launcherPkg", launcher_pkg if launcher_pkg else "")

        launcher_name = 'Launcher'

        # Add launcher info first if it exists
        if launcher_pkg:
            folder = self.app_config.get_app_metadata(launcher_pkg).get('pinned', "")
            self.all_apps_data.append({
                'key': launcher_pkg,
                'name': launcher_name,
                'item_type': "app",
                'is_launcher_shortcut': True,
                'icon_path': QUrl.fromLocalFile(self.launcher_icon_path).toString(),
                'is_pinned': False,
                'pinned': folder if isinstance(folder, str) else ""
            })

        for app_info in apps_from_cache:
            # Handle both old ('pkg_name') and new ('key') cache formats, and ensure they are not empty
            pkg_name = app_info.get('key') or app_info.get('pkg_name')
            app_name = app_info.get('name') or app_info.get('app_name')

            if not pkg_name or not app_name:
                continue # Skip malformed records

            # Avoid adding the launcher app twice if it's in the main list
            if launcher_pkg and pkg_name == launcher_pkg:
                continue

            metadata = self.app_config.get_app_metadata(pkg_name)
            pinned_val = metadata.get('pinned', "")
            if not isinstance(pinned_val, str): pinned_val = ""

            icon_path_file_exists = False
            icon_path_url = ""
            cached_icon_full_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")

            if os.path.exists(cached_icon_full_path):
                icon_path_url = QUrl.fromLocalFile(cached_icon_full_path).toString()
                icon_path_file_exists = True

            if not icon_path_file_exists:
                if os.path.exists(self.placeholder_icon_path):
                    icon_path_url = QUrl.fromLocalFile(self.placeholder_icon_path).toString()

                # Load icon if not failed before and no custom icon
                if not metadata.get('has_custom_icon') and not metadata.get('icon_fetch_failed'):
                    self.pending_icon_downloads[pkg_name] = app_name # Add to pending list

            self.all_apps_data.append({
                'key': pkg_name,
                'name': app_name,
                'item_type': "app",
                'is_launcher_shortcut': False,
                'icon_path': icon_path_url,
                'is_pinned': False, # This is the legacy role, keeping it false
                'pinned': pinned_val
            })
        if self.pending_icon_downloads:
            self._start_batch_icon_download()

    @Slot(str)
    def on_delete_config_requested(self, pkg_name):
        app_name = next((app['name'] for app in self.all_apps_data if app['key'] == pkg_name), "N/A")

        icon_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")
        if not os.path.exists(icon_path):
            icon_path = None

        reply = show_message_box(
            self,
            self.app_config.tr('apps_tab', 'delete_config_title'),
            self.app_config.tr('apps_tab', 'delete_config_msg', name=app_name),
            icon=QMessageBox.Question,
            buttons=QMessageBox.Yes | QMessageBox.No,
            default_button=QMessageBox.No,
            app_icon_path=icon_path
        )

        if reply == QMessageBox.Yes:
            if self.app_config.delete_app_scrcpy_config(pkg_name):
                show_message_box(self, self.app_config.tr('common', 'success'), self.app_config.tr('apps_tab', 'delete_success', name=app_name), icon=QMessageBox.Information, app_icon_path=icon_path)
                self.config_deleted.emit(pkg_name)
            else:
                show_message_box(self, self.app_config.tr('apps_tab', 'delete_config_title'), self.app_config.tr('apps_tab', 'delete_not_found', name=app_name), icon=QMessageBox.Warning, app_icon_path=icon_path)

    @Slot(str, str)
    def on_icon_dropped(self, pkg_name, file_url):
        """Handles a dropped image file to set a custom icon asynchronously."""
        if not file_url:
            return

        local_path = QUrl(file_url).toLocalFile()

        if not os.path.exists(local_path) or not local_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            show_message_box(self, self.app_config.tr('common', 'error'), self.app_config.tr('apps_tab', 'invalid_image_error'), icon=QMessageBox.Warning)
            return

        destination_path = os.path.join(self.icon_cache_dir, f"{pkg_name}.png")

        # Create and start the background worker
        worker = IconSaveWorker(pkg_name, local_path, destination_path)
        worker.signals.finished.connect(self._on_custom_icon_saved)
        worker.signals.error.connect(self._on_custom_icon_error)
        if self.main_window:
            self.main_window.start_worker(worker)

    @Slot(str, str)
    def _on_custom_icon_saved(self, pkg_name, destination_path):
        """Handles the successful save of a custom icon."""
        self.app_config.save_app_metadata(pkg_name, {'has_custom_icon': True})
        new_icon_url = QUrl.fromLocalFile(destination_path).toString()

        # Update the model in memory
        for app_data in self.all_apps_data:
            if app_data['key'] == pkg_name:
                app_data['icon_path'] = new_icon_url
                break

        self.filter_apps()
        gc.collect() # Force cleanup of image processing resources
        
        show_message_box(self, self.app_config.tr('apps_tab', 'custom_icon_success_title'), self.app_config.tr('apps_tab', 'custom_icon_success_msg'), icon=QMessageBox.Information)

    @Slot(str, str)
    def _on_custom_icon_error(self, pkg_name, error_message):
        """Handles an error during icon saving."""
        show_message_box(self, self.app_config.tr('apps_tab', 'custom_icon_error_title'), self.app_config.tr('apps_tab', 'custom_icon_error_msg', pkg=pkg_name, error=error_message), icon=QMessageBox.Critical)
        # Optionally, revert to the old icon if you stored it before starting the worker
        self.filter_apps()

    @Slot(str)
    def on_settings_requested(self, pkg_name):
        app_data = next((app for app in self.all_apps_data if app['key'] == pkg_name), None)

        # If it's the launcher and not in all_apps_data, reconstruct minimal metadata
        if not app_data and pkg_name == self.app_config.get(CONF_DEFAULT_LAUNCHER):
            app_data = {'key': pkg_name, 'name': 'Launcher', 'is_launcher_shortcut': True}

        if not app_data: return

        # Check if config already exists
        existing_configs = self.app_config.get_app_config_keys(include_name=False)

        if pkg_name not in existing_configs:
            # Create a new config only if it doesn't exist
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
                    self, self.app_config.tr('apps_tab', 'virtual_display_warn_title'),
                    self.app_config.tr('apps_tab', 'virtual_display_warn_msg'),
                    icon=QMessageBox.Warning, buttons=QMessageBox.Yes | QMessageBox.No, default_button=QMessageBox.Yes, app_icon_path=icon_path
                )
                if reply == QMessageBox.Yes:
                    config_to_save = global_config.copy()
                    config_to_save[CONF_NEW_DISPLAY] = 'Disabled'
                    config_to_save[CONF_MAX_SIZE] = '0'
                else:
                    show_message_box(
                        self, self.app_config.tr('apps_tab', 'action_cancelled_title'),
                        self.app_config.tr('apps_tab', 'action_cancelled_msg'),
                        icon=QMessageBox.Information, app_icon_path=icon_path
                    )
                    return
            else:
                config_to_save = global_config.copy()

            keys_to_exclude = {CONF_DEVICE_ID, CONF_THEME, CONF_LANGUAGE, CONF_DEVICE_COMMERCIAL_NAME, CONF_SHOW_SYSTEM_APPS, CONF_DEFAULT_LAUNCHER}
            app_specific_config = {k: v for k, v in config_to_save.items() if k not in keys_to_exclude}

            self.app_config.save_app_scrcpy_config(pkg_name, app_specific_config)
            self.config_changed.emit(pkg_name)

        # Switch to configuration tab and select this profile
        if self.main_window:
            self.main_window.tabs.setCurrentIndex(2) # Tab index for ScrcpyTab
            self.main_window.scrcpy_tab.select_profile(pkg_name)

    def filter_apps(self):
        search_text = self.search_input.text().lower()
        is_searching = bool(search_text)

        # Filter all apps that match the search text
        filtered_apps = [
            app for app in self.all_apps_data
            if search_text in app['name'].lower()
        ]

        sessions = {} # folder_name -> list of apps
        unassigned_apps = []
        quick_access_items = []

        # Get custom sessions configuration
        session_order = self.app_config.get_custom_sessions_order()

        for app in filtered_apps:
            pkg_name = app['key']
            # Fetch the most up-to-date folder assignment from AppConfig
            metadata = self.app_config.get_app_metadata(pkg_name)
            pinned_val = metadata.get('pinned', "")
            if not isinstance(pinned_val, str): pinned_val = ""
            
            parts = [p.strip() for p in pinned_val.split(',') if p.strip()]
            folder = next((p for p in parts if p != CONF_QUICK_ACCESS), "")
            
            if app.get('is_launcher_shortcut'):
                launcher_item = app
                quick_access_items.append(app)
            elif CONF_QUICK_ACCESS in parts:
                quick_access_items.append(app)

            if not app.get('is_launcher_shortcut'):
                if folder:
                    sessions.setdefault(folder, []).append(app)
                else:
                    unassigned_apps.append(app)

        qml_model_data = []

        # 1. Custom Sessions (respecting saved order)
        existing_folders = list(sessions.keys())
        sorted_folders = [f for f in session_order if f in existing_folders]
        remaining_folders = sorted([f for f in existing_folders if f not in sorted_folders], key=lambda x: x.lower())

        for folder_name in (sorted_folders + remaining_folders):
            # If searching, force expand. Otherwise, use saved state.
            is_collapsed = (folder_name in self.collapsed_sections) and not is_searching

            qml_model_data.append({
                'isSeparator': True, 
                'text': folder_name,
                'sectionId': folder_name,
                'isCollapsed': is_collapsed,
                'key': f"sep_{folder_name}" # Unique key for separators too
            })
            for app in sorted(sessions[folder_name], key=lambda x: x['name'].lower()):
                app_copy = app.copy()
                app_copy['is_pinned'] = False
                app_copy['isHidden'] = is_collapsed
                qml_model_data.append(app_copy)

        # 2. All Apps (Unassigned)
        if unassigned_apps:
            # If searching, force expand. Otherwise, use saved state.
            is_collapsed = ("all" in self.collapsed_sections) and not is_searching

            qml_model_data.append({
                'isSeparator': True, 
                'text': self.app_config.tr('apps_tab', 'all_section'),
                'sectionId': 'all',
                'isCollapsed': is_collapsed,
                'key': "sep_all" # Unique key
            })
            for app in sorted(unassigned_apps, key=lambda x: x['name'].lower()):
                app_copy = app.copy()
                app_copy['is_pinned'] = False
                app_copy['isHidden'] = is_collapsed
                qml_model_data.append(app_copy)

        # Update QML models
        final_quick_access = sorted(quick_access_items, key=lambda x: (0 if x.get('is_launcher_shortcut') else 1, x['name'].lower()))

        root = self.quick_widget.rootObject()
        if root:
            root.setProperty("quickAccessModel", final_quick_access)

        # 8. Fingerprint optimization
        model_fingerprint = hash(str(qml_model_data))
        if model_fingerprint == self._last_model_fingerprint:
            return
        self._last_model_fingerprint = model_fingerprint

        self._update_grid_model(qml_model_data)

    def _start_batch_icon_download(self):
        self.total_icon_tasks = len(self.pending_icon_downloads)
        if not self.total_icon_tasks:
            return

        self.completed_icon_tasks = 0
        self.progress_dialog = CustomThemedProgressDialog(
            self.app_config.tr('apps_tab', 'downloading_icons'),
            cancelButtonText=None, # No cancel button
            minimum=0,
            maximum=self.total_icon_tasks,
            parent=self
        )
        self.progress_dialog.setWindowFlags(self.progress_dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        self.progress_dialog.title_bar.minimize_button.setVisible(False) # Hide minimize button
        self.progress_dialog.title_bar.close_button.setVisible(False) # Hide close button
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()

        # Clear existing queue and workers for a new batch
        while not self.download_queue.empty():
            self.download_queue.get()
            self.download_queue.task_done()
        self.icon_download_workers.clear()

        # Add tasks to queue
        for pkg_name, app_name in self.pending_icon_downloads.items():
            self.download_queue.put((pkg_name, app_name))

        # Start workers
        for _ in range(self.NUM_ICON_WORKERS):
            worker = BatchIconDownloadWorker(self.download_queue, self.icon_cache_dir, self.app_config)
            worker.signals.finished.connect(self._on_icon_batch_finished)
            worker.signals.error.connect(self._on_icon_batch_error)
            if self.main_window: self.main_window.start_worker(worker)

        # Add sentinel values for workers to stop after processing all tasks
        for _ in range(self.NUM_ICON_WORKERS):
            self.download_queue.put(None)

    @Slot(str, str) # pkg_name, icon_path_string
    def _on_icon_batch_finished(self, pkg_name, icon_path_string):
        self.completed_icon_tasks += 1
        self.progress_dialog.setValue(self.completed_icon_tasks)
        self.progress_dialog.setLabelText(f"{self.app_config.tr('apps_tab', 'downloading_icons')} ({self.completed_icon_tasks}/{self.total_icon_tasks})")

        # Update the model in memory
        for app_data in self.all_apps_data:
            if app_data['key'] == pkg_name:
                app_data['icon_path'] = QUrl.fromLocalFile(icon_path_string).toString()
                break

        if self.completed_icon_tasks >= self.total_icon_tasks:
            self._on_all_icons_downloaded()

    @Slot(str, str) # pkg_name, error_msg
    def _on_icon_batch_error(self, pkg_name, error_msg):
        print(f"Error downloading icon for {pkg_name}: {error_msg}")
        self._save_metadata_async(pkg_name, {'icon_fetch_failed': True}) # Mark as failed
        self.completed_icon_tasks += 1
        self.progress_dialog.setValue(self.completed_icon_tasks)
        self.progress_dialog.setLabelText(f"{self.app_config.tr('apps_tab', 'downloading_icons')} ({self.completed_icon_tasks}/{self.total_icon_tasks})")

        if self.completed_icon_tasks >= self.total_icon_tasks:
            self._on_all_icons_downloaded()

    def _save_metadata_async(self, pkg_name, data):
        worker = BatchSaveWorker(pkg_name, data, self.app_config)
        if self.main_window:
            self.main_window.start_worker(worker)

    def _on_all_icons_downloaded(self):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater() # Ensure cleanup
            self.progress_dialog = None

        self.icon_download_workers.clear() # Clear worker references
        self.pending_icon_downloads.clear() # Clear pending tasks

        # Aggressive memory cleanup
        gc.collect()

        self.filter_apps() # Refresh the UI once with all new icons

    def _on_display_id_found_for_alt_launch(self, display_id, shortcut_path, package_name):
        app_icon_path = os.path.join(self.icon_cache_dir, f"{package_name}.png")
        if not os.path.exists(app_icon_path):
            app_icon_path = None
        if not display_id:
            show_message_box(self, self.app_config.tr('common', 'error'), self.app_config.tr('apps_tab', 'virtual_display_error'), icon=QMessageBox.Critical, app_icon_path=app_icon_path)
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
        app_launch_worker.signals.error.connect(lambda msg: show_message_box(self, self.app_config.tr('apps_tab', 'app_launch_error_title'), msg, icon=QMessageBox.Critical, app_icon_path=app_icon_path))
        if self.main_window:
            self.main_window.start_worker(app_launch_worker)

    def execute_launch(self, package_name, app_name):
        config_to_use = self.app_config.get_global_values_no_profile().copy()
        app_metadata = self.app_config.get_app_metadata(package_name)

        if 'config' in app_metadata and app_metadata['config']:
            config_to_use.update(app_metadata['config'])

        use_alt_launch = config_to_use.get(ALTERNATE_LAUNCH_METHOD, False)
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
        launch_worker.signals.error.connect(lambda msg: show_message_box(self, self.app_config.tr('apps_tab', 'scrcpy_error_title'), msg, icon=QMessageBox.Critical, app_icon_path=icon_path))

        if use_alt_launch and not is_launcher:
            launch_worker.signals.display_id_found.connect(self._on_display_id_found_for_alt_launch)

        if self.main_window:
            self.main_window.start_worker(launch_worker)
