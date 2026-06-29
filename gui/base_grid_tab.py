# FILE: gui/base_grid_tab.py
# PURPOSE: Base class for tabs that display items in a grid.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox, QPushButton, QMenu
from .dialogs import show_message_box
from PySide6.QtCore import Qt, QUrl, QTimer, Slot, Signal
from PySide6.QtGui import QPalette
from PySide6.QtQuickWidgets import QQuickWidget
import gc
import os
import sys
import time
import queue
from utils.constants import CONF_QUICK_ACCESS, CONF_QUICK_ACCESS_FACTOR, CONF_QUICK_ACCESS_VISIBLE, CONF_HQ_ICON_RENDERING, CONF_WEB_HOVER_EFFECT
from . import themes


class BaseGridTab(QWidget):
    launch_requested = Signal(str, str)
    config_changed = Signal(str)
    config_deleted = Signal(str)

    def __init__(self, app_config, main_window=None):
        super().__init__()
        self.app_config = app_config
        self.main_window = main_window
        self.items = {}
        self.collapsed_sections = set()
        self._qa_items_cache = []
        self._base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        self.placeholder_icon_path = None

        self.main_layout = QVBoxLayout(self)

        # Create and add top panel in subclasses

        # New QQuickWidget for the grid
        self.quick_widget = QQuickWidget(self)
        # Make QML background transparent
        self.quick_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        qml_path = os.path.join(os.path.dirname(__file__), "DynamicGridView.qml")
        self.quick_widget.setSource(QUrl.fromLocalFile(qml_path))
        
        # Pass theme colors to QML once component is ready
        self.quick_widget.statusChanged.connect(self.update_theme)

        # Info Label for messages
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.main_layout.addWidget(self.quick_widget)
        self.main_layout.addWidget(self.info_label)

        self.info_label.hide()

    def _make_menu_button(self):
        self.menu = QMenu(self)
        self.menu_button = QPushButton("⚙")
        self.menu_button.setFixedWidth(35)
        self.menu_button.setMenu(self.menu)
        return self.menu_button

    def update_theme(self, status=None):
        """Passes the current palette colors to the QML component and triggers garbage collection."""
        if self.quick_widget is None:
            return
        # The status argument is passed when connected to statusChanged signal
        if status is not None and status != QQuickWidget.Status.Ready:
            return

        # Force garbage collection to help clean up unused textures
        if self.quick_widget.engine():
            self.quick_widget.engine().collectGarbage()

        root = self.quick_widget.rootObject()
        if root:
            palette = self.quick_widget.palette()
            
            # Colors
            bg_color = palette.color(QPalette.ColorRole.Window).name()
            text_color = palette.color(QPalette.ColorRole.WindowText).name()
            button_bg_color = palette.color(QPalette.ColorRole.Button).name()
            button_text_color = palette.color(QPalette.ColorRole.ButtonText).name()
            highlight_color = palette.color(QPalette.ColorRole.Highlight).name()
            alt_base_color = palette.color(QPalette.ColorRole.AlternateBase).name()
            border_color = palette.color(QPalette.ColorRole.Window).darker(140).name() if not themes.is_dark_theme(palette) else palette.color(QPalette.ColorRole.Window).lighter(170).name()

            # Pass colors to QML
            root.setProperty("backgroundColor", bg_color)
            root.setProperty("textColor", text_color)
            root.setProperty("buttonBgColor", button_bg_color)
            root.setProperty("buttonTextColor", button_text_color)
            root.setProperty("buttonPressedColor", palette.color(QPalette.ColorRole.Button).darker(120).name()) # A darker shade for pressed state
            root.setProperty("buttonBorderColor", border_color)
            root.setProperty("highlightColor", highlight_color)
            root.setProperty("highlightedTextColor", palette.color(QPalette.ColorRole.HighlightedText).name())
            root.setProperty("altBaseColor", alt_base_color)

            # Pass rendering settings
            hq_render = self.app_config.get(CONF_HQ_ICON_RENDERING, True)
            root.setProperty("iconAntiAliasing", hq_render)
            root.setProperty("iconSmoothing", hq_render)
            root.setProperty("iconMipmaps", hq_render)
            
            # Pass hover effect setting
            root.setProperty("hoverEffectEnabled", self.app_config.get(CONF_WEB_HOVER_EFFECT, True))

            # Pass Quick Access factor
            root.setProperty("quickAccessFactor", self.app_config.get(CONF_QUICK_ACCESS_FACTOR, 1.0))
            root.setProperty("quickAccessVisible", self.app_config.get(CONF_QUICK_ACCESS_VISIBLE, False))
            
            # Update strings
            self.update_strings()
            
            # Connect signals once per root to avoid duplicates
            if getattr(self, '_qa_connected_root', None) is not root:
                root.quickAccessFactorUpdated.connect(self.on_quick_access_factor_changed)
                root.quickAccessVisibilityChanged.connect(self.on_quick_access_visibility_changed)
                root.qaLaunchRequested.connect(self._on_qa_launch_requested)
                self._qa_connected_root = root

    def _get_qml_root(self):
        if self.quick_widget is None:
            return None
        return self.quick_widget.rootObject()

    def _set_qml_strings(self, root):
        root.setProperty("allAppsText", self.app_config.tr('apps_tab', 'all_section'))
        root.setProperty("settingsText", self.app_config.tr('common', 'settings'))
        root.setProperty("deleteConfigText", self.app_config.tr('apps_tab', 'delete_config_title'))
        root.setProperty("moveToText", self.app_config.tr('apps_tab', 'move_to'))
        root.setProperty("createNewFolderText", self.app_config.tr('apps_tab', 'create_session_title'))
        root.setProperty("launcherText", self.app_config.tr('apps_tab', 'launcher_label'))
        root.setProperty("quickAccessText", self.app_config.tr('apps_tab', 'quick_access_label'))

    def update_strings(self):
        root = self._get_qml_root()
        if root:
            self._set_qml_strings(root)

    def _get_icon_cache_dir(self):
        return self.app_config.get_icon_cache_dir()

    @Slot(str, str)
    def on_icon_dropped(self, key, file_url):
        if not file_url:
            return
        local_path = QUrl(file_url).toLocalFile()
        if not os.path.exists(local_path) or not local_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            show_message_box(self, self.app_config.tr('common', 'error'),
                            self.app_config.tr('apps_tab', 'invalid_image_error'),
                            icon=QMessageBox.Warning)
            return
        from .workers import IconSaveWorker
        icon_key = os.path.basename(key)
        destination_path = os.path.join(self._get_icon_cache_dir(), f"{icon_key}.png")
        worker = IconSaveWorker(key, local_path, destination_path)
        worker.signals.finished.connect(self._on_custom_icon_saved)
        worker.signals.error.connect(self._on_custom_icon_error)
        if self.main_window:
            self.main_window.start_worker(worker)

    @Slot(str, str)
    def _on_custom_icon_saved(self, key, destination_path):
        self.app_config.save_app_metadata(key, {'has_custom_icon': True})
        cache_buster = int(time.time())
        new_icon_url = QUrl.fromLocalFile(destination_path).toString() + f"?t={cache_buster}"
        self._on_icon_model_updated(key, new_icon_url)
        self._last_model_data = None
        self._refresh_after_icon_update()
        gc.collect()
        show_message_box(self, self.app_config.tr('apps_tab', 'custom_icon_success_title'),
                        self.app_config.tr('apps_tab', 'custom_icon_success_msg'),
                        icon=QMessageBox.Information)

    def _on_icon_model_updated(self, key, new_icon_url):
        """Subclass updates its in-memory model with the new icon URL."""

    def _refresh_after_icon_update(self):
        """Subclass refreshes the grid display after icon update."""

    @Slot(str, str)
    def _on_custom_icon_error(self, key, error_message):
        show_message_box(self, self.app_config.tr('apps_tab', 'custom_icon_error_title'),
                        self.app_config.tr('apps_tab', 'custom_icon_error_msg', pkg=key, error=error_message),
                        icon=QMessageBox.Critical)
        self._refresh_after_icon_update()

    @Slot(str, str)
    def _on_qml_launch_requested(self, itemKey, itemName):
        self.launch_requested.emit(itemKey, itemName)

    @Slot(str, str, str)
    def _on_qa_launch_requested(self, key, name, item_type):
        """Route QA launches to the correct tab handler based on item type."""
        if not self.main_window:
            return
        if item_type == "winlator_game":
            self.main_window._handle_launch_request(key, name, 'winlator')
        else:
            self.main_window._handle_launch_request(key, name, 'app')

    def get_qa_items(self):
        return self._qa_items_cache

    def _refresh_qa_model(self):
        if self.main_window:
            self.main_window._refresh_qa_model()

    def _connect_qml_signals(self):
        if self.quick_widget is None:
            QTimer.singleShot(100, self._connect_qml_signals)
            return
        root = self.quick_widget.rootObject()
        if not root:
            QTimer.singleShot(100, self._connect_qml_signals)
            return
        if getattr(self, '_connected_root', None) is root:
            return
        self._connect_tab_signals(root)
        self._connected_root = root
        self.update_strings()

    def _connect_tab_signals(self, root):
        """Subclasses override to connect QML signals specific to the tab."""

    @Slot(str, bool)
    def on_quick_access_requested(self, key, checked):
        metadata = self.app_config.get_app_metadata(key)
        pinned_val = metadata.get('pinned', "")
        if not isinstance(pinned_val, str):
            pinned_val = ""
        parts = [p.strip() for p in pinned_val.split(',') if p.strip()]
        if checked:
            if CONF_QUICK_ACCESS not in parts:
                parts.append(CONF_QUICK_ACCESS)
        else:
            if CONF_QUICK_ACCESS in parts:
                parts.remove(CONF_QUICK_ACCESS)
        new_pinned = ",".join(parts)
        self.app_config.save_app_metadata(key, {'pinned': new_pinned})
        self._on_quick_access_updated(key, new_pinned)

    def _on_quick_access_updated(self, key, new_pinned):
        """Subclasses override to refresh grid after quick access toggle."""

    @Slot(float)
    def on_quick_access_factor_changed(self, factor):
        self.app_config.set(CONF_QUICK_ACCESS_FACTOR, factor)

    @Slot(bool)
    def on_quick_access_visibility_changed(self, visible):
        self.app_config.set(CONF_QUICK_ACCESS_VISIBLE, visible)

    def _clear_grid(self):
        self.items = {}
        self._last_model_data = None
        if self.quick_widget is None:
            return
        root = self.quick_widget.rootObject()
        if root:
            root.setProperty("itemsModel", [])
            root.setProperty("quickAccessModel", [])

    def _trim_heap(self):
        """Release free heap pages back to the OS (Linux glibc)."""
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
        except Exception:
            pass

    def _unload_qml(self):
        """Destroy the QQuickWidget to free all scene graph, textures and QML engine memory."""
        self._last_model_data = None
        self.items = {}
        old = self.quick_widget
        if old is None:
            return
        self.quick_widget = None
        self.main_layout.removeWidget(old)
        from PySide6.QtCore import QCoreApplication
        # step 1: unload QML component tree (frees delegates, textures, scene graph)
        old.setSource(QUrl())
        if old.engine():
            old.engine().clearComponentCache()
            old.engine().collectGarbage()
        try:
            old.quickWindow().releaseResources()
        except Exception:
            pass
        QCoreApplication.instance().processEvents()
        # step 2: destroy the C++ object
        old.deleteLater()
        for _ in range(10):
            QCoreApplication.instance().processEvents()
            if not old:
                break
        # step 3: clear caches and release heap
        from PySide6.QtGui import QPixmapCache
        QPixmapCache.clear()
        gc.collect()
        self._trim_heap()

    def _reload_qml(self):
        """Create a new QQuickWidget in place of the destroyed one."""
        if self.quick_widget is not None:
            return
        self.quick_widget = QQuickWidget(self)
        self.quick_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        info_idx = self.main_layout.indexOf(self.info_label)
        self.main_layout.insertWidget(info_idx, self.quick_widget)
        qml_path = os.path.join(os.path.dirname(__file__), "DynamicGridView.qml")
        self.quick_widget.statusChanged.connect(self.update_theme)
        self.quick_widget.setSource(QUrl.fromLocalFile(qml_path))

    def show_message(self, text):
        self.info_label.setText(text)
        self.info_label.show()
        if self.quick_widget:
            self.quick_widget.hide()

    def show_grid(self):
        self.info_label.hide()
        if self.quick_widget:
            self.quick_widget.show()

    def _update_grid_model(self, model_data):
        """Updates the model in the QML GridView with optimization."""
        if self.quick_widget is None:
            return
        root = self.quick_widget.rootObject()
        if root:
            # Skip if model data is identical to last update
            if hasattr(self, '_last_model_data') and self._last_model_data == model_data:
                return
            self._last_model_data = model_data
            
            # Set the item list for the QML model property
            root.setProperty("itemsModel", model_data)
            gc.collect()
        else:
            # If the root object is not ready, wait a bit and retry.
            QTimer.singleShot(100, lambda: self._update_grid_model(model_data))

    @staticmethod
    def _drain_queue(q, num_workers):
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
            except queue.Empty:
                break
        for _ in range(num_workers):
            q.put(None)

    def set_device_status_message(self, message):
        if message:
            self.show_message(message)
        else:
            self.show_grid()

    def on_device_changed(self):
        raise NotImplementedError("Subclasses must implement on_device_changed")

    @Slot(str, bool)
    def on_section_toggled(self, section_id, collapsed):
        """Slot to handle section toggle from QML."""
        if collapsed:
            self.collapsed_sections.add(section_id)
        else:
            self.collapsed_sections.discard(section_id)
        
        # Persist collapsed state if it's a custom session or special section
        if hasattr(self, 'app_config'):
            if section_id in ['pinned', 'all']:
                # Maybe handle special sections too? 
                # For now, let's just use the app_config helper if it's an AppsTab
                if hasattr(self, 'save_session_state'):
                    self.save_session_state(section_id, collapsed)
            else:
                if hasattr(self, 'save_session_state'):
                    self.save_session_state(section_id, collapsed)
