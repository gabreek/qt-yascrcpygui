from PySide6.QtCore import Qt, QPoint, Signal, QEvent, QThread
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QDialog, QProgressBar, QLineEdit, QSizePolicy,
                               QScrollArea, QFrame) # Added QProgressBar

from . import themes # Assuming themes.py is in the same directory
from utils import adb_handler


class CustomTitleBar(QWidget):
    """Custom title bar for frameless windows."""
    def __init__(self, parent_window, title="Window"): # Renamed parent to parent_window for clarity
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(35) # Based on main_window.py

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QLabel(title, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.close_button = QPushButton("✕", self)
        self.close_button.setObjectName("close_button")
        self.close_button.setFixedSize(40, 35)
        self.close_button.clicked.connect(self.parent_window.close) # Connect to parent_window's close

        self.minimize_button = QPushButton("-", self)
        self.minimize_button.setObjectName("minimize_button")
        self.minimize_button.setFixedSize(40, 35)
        self.minimize_button.clicked.connect(self.parent_window.showMinimized) # Connect to parent_window's showMinimized

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.close_button)

        self.pressing = False
        self.start_pos = QPoint(0, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # If within resize border of the top edge, start resize on parent directly
            if event.position().y() < getattr(self.parent_window, 'RESIZE_BORDER', 5):
                parent = self.parent_window
                if hasattr(parent, 'resize_border_start'):
                    parent.resize_border_start(self.mapToParent(event.position().toPoint()))
                return
            if event.type() == QEvent.Type.MouseButtonDblClick:
                if self.parent_window.isMaximized():
                    self.parent_window.showNormal()
                else:
                    self.parent_window.showMaximized()
            else:
                self.pressing = True
                self.start_pos = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.pressing:
            self.parent_window.move(event.globalPosition().toPoint() - self.start_pos)
            event.accept()
        elif hasattr(self.parent_window, '_set_edge_cursor'):
            self.parent_window._set_edge_cursor(self.mapToParent(event.position().toPoint()))

    def mouseReleaseEvent(self, event):
        self.pressing = False
        event.accept()

    def leaveEvent(self, event):
        if hasattr(self.parent_window, 'unsetCursor'):
            self.parent_window.unsetCursor()
        super().leaveEvent(event)


class CustomThemedDialog(QDialog):
    """A frameless, themed QDialog with a custom title bar and edge resize."""
    RESIZE_BORDER = 5

    def __init__(self, parent=None, title="Dialog", auto_delete=True):
        super().__init__(parent)
        self.app_config = getattr(parent, 'app_config', None) if parent else None
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)
        if auto_delete:
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self._resize_edges = Qt.Edges()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.styled_container = QWidget()
        self.styled_container.setObjectName("main_widget")
        main_layout.addWidget(self.styled_container)

        container_vbox_layout = QVBoxLayout(self.styled_container)
        container_vbox_layout.setContentsMargins(0, 0, 0, 0)
        container_vbox_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self, title)
        container_vbox_layout.addWidget(self.title_bar)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(10)

        container_vbox_layout.addLayout(self.content_layout)
        container_vbox_layout.addStretch()

        self.update_theme()

    def add_content_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_content_layout(self, layout):
        self.content_layout.addLayout(layout)

    def showMinimized(self):
        self.setWindowState(Qt.WindowMinimized)

    def update_theme(self):
        themes.apply_stylesheet_to_window(self)

    def resize_border_start(self, pos):
        """Called by title bar when click is on the top resize edge."""
        edges = self.get_resize_edges(pos)
        if edges:
            self._resizing = True
            self._resize_edges = edges
            self._resize_start_pos = self.mapToGlobal(pos)
            self._resize_start_geometry = self.geometry()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseMove and not self._resizing:
            w = obj
            while w:
                if w is self:
                    self._set_edge_cursor(self.mapFromGlobal(event.globalPosition().toPoint()))
                    break
                w = w.parentWidget() if hasattr(w, 'parentWidget') else None
        return super().eventFilter(obj, event)

    def get_resize_edges(self, pos):
        edges = Qt.Edges()
        if pos.x() < self.RESIZE_BORDER:
            edges |= Qt.LeftEdge
        if pos.x() > self.width() - self.RESIZE_BORDER:
            edges |= Qt.RightEdge
        if pos.y() < self.RESIZE_BORDER:
            edges |= Qt.TopEdge
        if pos.y() > self.height() - self.RESIZE_BORDER:
            edges |= Qt.BottomEdge
        return edges

    def _set_edge_cursor(self, pos):
        edges = self.get_resize_edges(pos)
        if not edges:
            self.unsetCursor()
        elif edges in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges & (Qt.LeftEdge | Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.SizeVerCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self.get_resize_edges(event.position().toPoint())
            if edges:
                self._resizing = True
                self._resize_edges = edges
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            global_pos = event.globalPosition().toPoint()
            delta = global_pos - self._resize_start_pos
            rect = self._resize_start_geometry

            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

            if self._resize_edges & Qt.LeftEdge:
                x = rect.x() + delta.x()
                w = rect.width() - delta.x()
            if self._resize_edges & Qt.RightEdge:
                w = rect.width() + delta.x()
            if self._resize_edges & Qt.TopEdge:
                y = rect.y() + delta.y()
                h = rect.height() - delta.y()
            if self._resize_edges & Qt.BottomEdge:
                h = rect.height() + delta.y()

            if w < self.minimumWidth():
                if self._resize_edges & Qt.LeftEdge:
                    x = rect.x() + rect.width() - self.minimumWidth()
                w = self.minimumWidth()
            if h < self.minimumHeight():
                if self._resize_edges & Qt.TopEdge:
                    y = rect.y() + rect.height() - self.minimumHeight()
                h = self.minimumHeight()

            self.setGeometry(x, y, w, h)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._resizing:
            self._resizing = False
            self._resize_edges = Qt.Edges()
            self._resize_start_pos = None
            self._resize_start_geometry = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)


class CustomThemedInputDialog(CustomThemedDialog):
    """A frameless, themed input dialog."""
    def __init__(self, parent=None, title="Input", label_text="", text_input_mode=QLineEdit.Normal, initial_text="", auto_delete=True):
        super().__init__(parent, title=title, auto_delete=auto_delete)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(400, 150) # Adjust size as needed

        self.input_line_edit = QLineEdit(self)
        self.input_line_edit.setEchoMode(text_input_mode)
        self.input_line_edit.setText(initial_text)
        self.input_line_edit.setFocus() # Set initial focus
        self.input_line_edit.returnPressed.connect(self.accept) # Connect Enter key to accept
        
        # Optionally make the line edit expand horizontally
        self.input_line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        ok_text = self.app_config.tr('common', 'ok') if self.app_config else "OK"
        cancel_text = self.app_config.tr('common', 'cancel') if self.app_config else "Cancel"

        self.ok_button = QPushButton(ok_text)
        self.cancel_button = QPushButton(cancel_text)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        # Content layout for message and input
        input_content_layout = QVBoxLayout()
        if label_text:
            input_content_layout.addWidget(QLabel(label_text, self))
        input_content_layout.addWidget(self.input_line_edit)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()

        self.add_content_layout(input_content_layout)
        self.add_content_layout(button_layout) # Add buttons to the content layout

    def textValue(self):
        return self.input_line_edit.text()

    @staticmethod
    def getText(parent, title, label, text_input_mode=QLineEdit.Normal, initial_text=""):
        dialog = CustomThemedInputDialog(parent, title, label, text_input_mode, initial_text, auto_delete=False)
        result = dialog.exec()
        value = ""
        success = False
        if result == QDialog.Accepted:
            value = dialog.textValue()
            success = True
        
        dialog.deleteLater() # Clean up manually
        return value, success

class CustomThemedProgressDialog(CustomThemedDialog):
    canceled = Signal()

    def __init__(self, labelText, cancelButtonText=None, minimum=0, maximum=100, parent=None):
        title_text = "Progress"
        if parent and hasattr(parent, 'app_config'):
             title_text = parent.app_config.tr('common', 'loading')
        elif hasattr(self, 'app_config') and self.app_config: # Added in base class
             title_text = self.app_config.tr('common', 'loading')

        super().__init__(parent, title=title_text)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(350, 150)

        self._canceled = False

        self.progress_label = QLabel(labelText)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(minimum, maximum)
        self.progress_bar.setValue(minimum)

        self.add_content_widget(self.progress_label)
        self.add_content_widget(self.progress_bar)

        if cancelButtonText:
            self.cancel_button = QPushButton(cancelButtonText)
            self.cancel_button.clicked.connect(self._handle_cancel)
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            button_layout.addWidget(self.cancel_button)
            button_layout.addStretch()
            self.add_content_layout(button_layout)
        else:
            self.cancel_button = None

        # Override minimize button behavior for progress dialog: close
        self.title_bar.minimize_button.clicked.disconnect()
        self.title_bar.minimize_button.clicked.connect(self.close)
        self.title_bar.minimize_button.setText("—")

        # Hide close button if no cancel button is provided to prevent accidental closing
        if not cancelButtonText:
            self.title_bar.close_button.setVisible(False)


    def setLabelText(self, text):
        self.progress_label.setText(text)

    def setRange(self, minimum, maximum):
        self.progress_bar.setRange(minimum, maximum)

    def setValue(self, value):
        self.progress_bar.setValue(value)
        if value >= self.progress_bar.maximum() and not self._canceled:
            self.close()

    def _handle_cancel(self):
        self._canceled = True
        self.canceled.emit()
        self.close()

    def cancel(self):
        self._handle_cancel()

    def wasCanceled(self):
        return self._canceled

    def closeEvent(self, event):
        if not self._canceled: # If closed without explicit cancel, treat as canceled
            self._canceled = True
            self.canceled.emit()
        super().closeEvent(event)


class CustomThemedConfirmationDialog(CustomThemedDialog):
    """A themed confirmation dialog with Yes/No buttons."""
    def __init__(self, parent=None, title="Confirm", message=""):
        super().__init__(parent, title=title)
        self.setMinimumSize(400, 150)
        
        # Hide standard title bar buttons
        self.title_bar.close_button.setVisible(False)
        self.title_bar.minimize_button.setVisible(False)

        label = QLabel(message)
        label.setWordWrap(True)
        self.add_content_widget(label)

        btn_layout = QHBoxLayout()
        yes_text = self.app_config.tr('common', 'yes') if self.app_config else "Yes"
        no_text = self.app_config.tr('common', 'no') if self.app_config else "No"

        self.yes_btn = QPushButton(yes_text)
        self.no_btn = QPushButton(no_text)

        self.yes_btn.clicked.connect(self.accept)
        self.no_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.yes_btn)
        btn_layout.addWidget(self.no_btn)
        btn_layout.addStretch()

        self.add_content_layout(btn_layout)


class DeviceInfoFetcher(QThread):
    """Background thread to fetch device info (commercial name + battery) for all connected devices."""
    finished = Signal(dict)

    def __init__(self, device_ids):
        super().__init__()
        self.device_ids = device_ids

    def run(self):
        result = {}
        for dev_id in self.device_ids:
            info = adb_handler.get_device_info(dev_id)
            if info:
                result[dev_id] = info
            else:
                result[dev_id] = {"commercial_name": dev_id, "battery": "?"}
        self.finished.emit(result)


class DeviceSelectorDialog(CustomThemedDialog):
    """Modal dialog showing all connected devices with Switch/Disconnect options."""

    DEVICE_SELECTED = 1
    DEVICE_DISCONNECTED = 2

    def __init__(self, device_ids, current_device_id, parent=None):
        title = parent.app_config.tr('common', 'device_selector_title') if parent and hasattr(parent, 'app_config') else "Select Device"
        super().__init__(parent, title=title)
        self.setMinimumSize(420, 300)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._result_data = None
        self._fetched_info = {}

        # Content
        content = QVBoxLayout()
        content.setSpacing(8)

        self.status_label = QLabel(
            self.app_config.tr('common', 'fetching_devices') if self.app_config else "Fetching device info..."
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(200)

        self.device_container = QWidget()
        self.device_list_layout = QVBoxLayout(self.device_container)
        self.device_list_layout.setSpacing(6)
        self.device_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.device_container)
        content.addWidget(self.scroll)

        # Initial loading state
        self.status_label.show()
        self.scroll.hide()

        # Refresh button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.refresh_btn = QPushButton(
            self.app_config.tr('common', 'refresh') if self.app_config else "Refresh"
        )
        self.refresh_btn.clicked.connect(lambda: self._populate_devices(self.device_ids, self._current_id))
        btn_layout.addWidget(self.refresh_btn)

        self.close_btn = QPushButton(
            self.app_config.tr('common', 'close') if self.app_config else "Close"
        )
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)
        btn_layout.addStretch()
        content.addLayout(btn_layout)

        self.add_content_layout(content)

        self.device_ids = list(device_ids)
        self._current_id = current_device_id
        self._populate_devices(self.device_ids, self._current_id)

    def _populate_devices(self, device_ids, current_id):
        # Clear existing items
        while self.device_list_layout.count():
            item = self.device_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Show loading
        self.status_label.setText(
            self.app_config.tr('common', 'fetching_devices') if self.app_config else "Fetching device info..."
        )
        self.status_label.show()
        self.scroll.hide()

        # Add placeholder items showing device IDs while fetching
        for dev_id in device_ids:
            card = self._create_device_card(dev_id, {"commercial_name": dev_id, "battery": "?"}, current_id)
            self.device_list_layout.addWidget(card)

        # Start background fetch
        self._fetcher = DeviceInfoFetcher(device_ids)
        self._fetcher.finished.connect(lambda info: self._on_info_fetched(info, current_id))
        self._fetcher.start()

    def _on_info_fetched(self, info_map, current_id):
        self._fetched_info = info_map
        # Clear placeholders
        while self.device_list_layout.count():
            item = self.device_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for dev_id in self.device_ids:
            info = info_map.get(dev_id, {"commercial_name": dev_id, "battery": "?"})
            card = self._create_device_card(dev_id, info, current_id)
            self.device_list_layout.addWidget(card)

        self.status_label.hide()
        self.scroll.show()

    def _create_device_card(self, dev_id, info, current_id):
        card = QFrame()
        card.setObjectName("device_card")
        card.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Device icon/type indicator
        type_label = QLabel("📱" if ":" in dev_id else "🔌")
        type_label.setToolTip(
            self.app_config.tr('common', 'wifi_device') if ":" in dev_id
            else self.app_config.tr('common', 'usb_device')
        ) if self.app_config else None
        type_label.setFixedWidth(24)
        layout.addWidget(type_label)

        # Info area
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name = info.get("commercial_name", dev_id)
        name_label = QLabel(name)
        name_label.setObjectName("device_name_label")
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)

        id_label = QLabel(dev_id)
        id_label.setObjectName("device_id_label")
        id_label.setStyleSheet("color: gray; font-size: 11px;")
        info_layout.addWidget(id_label)

        battery = info.get("battery", "?")
        battery_label = QLabel(f"🔋 {battery}%")
        battery_label.setObjectName("device_battery_label")
        battery_label.setStyleSheet("font-size: 11px;")
        info_layout.addWidget(battery_label)

        layout.addLayout(info_layout, 1)

        # Action buttons
        is_current = (dev_id == current_id)
        if is_current:
            current_label = QLabel(
                self.app_config.tr('common', 'current_device') if self.app_config else "Current"
            )
            current_label.setObjectName("current_device_label")
            current_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
            layout.addWidget(current_label)
        else:
            switch_btn = QPushButton(
                self.app_config.tr('common', 'switch_device') if self.app_config else "Switch"
            )
            switch_btn.setObjectName("device_switch_btn")
            switch_btn.clicked.connect(lambda checked, d=dev_id: self._on_switch(d))
            layout.addWidget(switch_btn)

        if ":" in dev_id:
            disconnect_btn = QPushButton(
                self.app_config.tr('common', 'disconnect_device') if self.app_config else "Disconnect"
            )
            disconnect_btn.setObjectName("device_disconnect_btn")
            disconnect_btn.clicked.connect(lambda checked, d=dev_id: self._on_disconnect(d))
            layout.addWidget(disconnect_btn)

        return card

    def _on_switch(self, device_id):
        self._result_data = (self.DEVICE_SELECTED, device_id)
        self.accept()

    def _on_disconnect(self, device_id):
        result = adb_handler.disconnect_device(device_id)
        self._result_data = (self.DEVICE_DISCONNECTED, device_id)
        self.accept()

    def get_result(self):
        return self._result_data
