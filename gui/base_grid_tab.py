# FILE: gui/base_grid_tab.py
# PURPOSE: Base class for tabs that display items in a grid.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QUrl, QTimer, Slot
from PySide6.QtGui import QPalette
from PySide6.QtQuickWidgets import QQuickWidget
import os
from . import themes


class BaseGridTab(QWidget):
    def __init__(self, app_config, main_window=None):
        super().__init__()
        self.app_config = app_config
        self.main_window = main_window
        self.items = {}  # This will hold the model data

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
        """Passes the current palette colors to the QML component."""
        # The status argument is passed when connected to statusChanged signal
        if status is not None and status != QQuickWidget.Status.Ready:
            return

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
            root.setProperty("altBaseColor", alt_base_color)

    
    def _clear_grid(self):
        self.items = {}
        root = self.quick_widget.rootObject()
        if root:
            root.setProperty("itemsModel", [])

    def show_message(self, text):
        self.info_label.setText(text)
        self.info_label.show()
        self.quick_widget.hide()

    def show_grid(self):
        self.info_label.hide()
        self.quick_widget.show()

    def _update_grid_model(self, model_data):
        """Updates the model in the QML GridView."""
        root = self.quick_widget.rootObject()
        if root:
            # Set the item list for the QML model property
            root.setProperty("itemsModel", model_data)
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
