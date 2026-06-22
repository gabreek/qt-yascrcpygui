# FILE: gui/base_grid_tab.py
# PURPOSE: Base class for tabs that display items in a grid.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QUrl, QTimer, Slot
from PySide6.QtGui import QPalette
from PySide6.QtQuickWidgets import QQuickWidget
import gc
import os
from . import themes


class BaseGridTab(QWidget):
    def __init__(self, app_config, main_window=None):
        super().__init__()
        self.app_config = app_config
        self.main_window = main_window
        self.items = {}  # This will hold the model data
        self.collapsed_sections = set()

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
            from utils.constants import CONF_HQ_ICON_RENDERING
            hq_render = self.app_config.get(CONF_HQ_ICON_RENDERING, True)
            root.setProperty("iconAntiAliasing", hq_render)
            root.setProperty("iconSmoothing", hq_render)
            root.setProperty("iconMipmaps", hq_render)
            
            # Pass hover effect setting
            from utils.constants import CONF_WEB_HOVER_EFFECT
            root.setProperty("hoverEffectEnabled", self.app_config.get(CONF_WEB_HOVER_EFFECT, True))

            # Pass Quick Access factor
            from utils.constants import CONF_QUICK_ACCESS_FACTOR, CONF_QUICK_ACCESS_VISIBLE
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

    def update_strings(self):
        """Passes localized strings to the QML component."""
        if self.quick_widget is None:
            return
        root = self.quick_widget.rootObject()
        if not root:
            return

        # Map strings from app_config.tr to QML properties
        root.setProperty("allAppsText", self.app_config.tr('apps_tab', 'all_section'))
        root.setProperty("settingsText", self.app_config.tr('common', 'settings'))
        root.setProperty("deleteConfigText", self.app_config.tr('apps_tab', 'delete_config_title'))
        root.setProperty("moveToText", self.app_config.tr('apps_tab', 'move_to'))
        root.setProperty("createNewFolderText", self.app_config.tr('apps_tab', 'create_session_title'))
        root.setProperty("launcherText", self.app_config.tr('apps_tab', 'launcher_label'))
        root.setProperty("quickAccessText", self.app_config.tr('apps_tab', 'quick_access_label'))

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
        """Subclasses must return their list of Quick Access items."""
        return []

    @Slot(float)
    def on_quick_access_factor_changed(self, factor):
        from utils.constants import CONF_QUICK_ACCESS_FACTOR
        self.app_config.set(CONF_QUICK_ACCESS_FACTOR, factor)

    @Slot(bool)
    def on_quick_access_visibility_changed(self, visible):
        from utils.constants import CONF_QUICK_ACCESS_VISIBLE
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
