from PySide6.QtCore import Qt, QPoint, Signal, QRunnable, QObject, QThreadPool
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit)
from PySide6.QtGui import QPalette

from utils import adb_handler
from . import themes
from .common_widgets import CustomTitleBar
from .workers import AdbConnectWorker, AdbWorkerSignals

class AdbWifiWindow(QWidget):
    def __init__(self, app_config, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self.thread_pool = QThreadPool.globalInstance()

        self.setWindowTitle("ADB over Wifi")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        styled_container = QWidget()
        styled_container.setObjectName("main_widget")
        main_layout.addWidget(styled_container)

        container_vbox_layout = QVBoxLayout(styled_container)
        container_vbox_layout.setContentsMargins(0, 0, 0, 0)
        container_vbox_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(parent_window=self, title="ADB over Wifi")
        container_vbox_layout.addWidget(self.title_bar)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("Device IP Address")
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("Port")
        self.port_input.setFixedWidth(60)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.ip_input)
        input_layout.addWidget(self.port_input)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.handle_connect)

        self.status_label = QLabel("Enter the device IP and port.")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("adb_status_label") # Add objectName

        content_layout.addLayout(input_layout)
        content_layout.addWidget(self.connect_button)
        content_layout.addWidget(self.status_label)
        content_layout.addStretch()

        container_vbox_layout.addWidget(content_widget)

        self.resize(400, 160)
        self.update_theme()

    def set_status(self, text, is_error=False):
        self.status_label.setText(text)
        self.status_label.setProperty("error", is_error) # Set a dynamic property
        self.style().polish(self.status_label) # Repolish to apply stylesheet changes

    def handle_connect(self):
        ip = self.ip_input.text().strip()
        port = self.port_input.text().strip()
        if not ip or not port:
            self.set_status("IP and Port cannot be empty.", is_error=True)
            return

        address = f"{ip}:{port}"
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Connecting...")
        self.set_status(f"Connecting to {address}...")

        worker = AdbConnectWorker(address)
        worker.signals.result.connect(self._on_connect_success)
        worker.signals.error.connect(self._on_connect_error)
        self.thread_pool.start(worker)

    def _on_connect_success(self, message):
        self.set_status(message)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Connect")
        self.close()

    def _on_connect_error(self, error_message):
        self.set_status(error_message, is_error=True)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Connect")

    def showMinimized(self):
        self.setWindowState(Qt.WindowMinimized)

    def update_theme(self):
        if self.parent():
            self.setPalette(self.parent().palette())
        themes.apply_stylesheet_to_window(self)