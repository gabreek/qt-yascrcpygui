from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QCheckBox, QPushButton, QLabel
from .common_widgets import CustomThemedDialog

class WebServerConfigWindow(CustomThemedDialog):
    start_server_requested = Signal()
    stop_server_requested = Signal()

    def __init__(self, app_config, parent=None):
        super().__init__(parent=parent, title="Web Server Configuration")
        self.app_config = app_config
        self.is_running = False

        self.setMinimumWidth(400)

        # Start on launch checkbox
        self.start_on_launch_checkbox = QCheckBox("Start web server on application launch")
        self.start_on_launch_checkbox.setChecked(self.app_config.get('start_web_server_on_launch', False))
        self.start_on_launch_checkbox.stateChanged.connect(self._on_start_on_launch_changed)
        self.add_content_widget(self.start_on_launch_checkbox)

        # Status and control
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Server Status:"))
        self.status_label = QLabel("Stopped")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.control_button = QPushButton("Start Server")
        self.control_button.clicked.connect(self._on_control_button_clicked)
        status_layout.addWidget(self.control_button)
        self.add_content_layout(status_layout)

        # Server Address Label
        self.server_address_label = QLabel("Server Address: Not Running")
        self.add_content_widget(self.server_address_label)

    def _on_start_on_launch_changed(self, state):
        self.app_config.set('start_web_server_on_launch', bool(state))

    def _on_control_button_clicked(self):
        if self.is_running:
            self.stop_server_requested.emit()
        else:
            self.start_server_requested.emit()

    def update_status(self, is_running, ip="127.0.0.1", port=8000):
        self.is_running = is_running
        if self.is_running:
            self.status_label.setText("<b style='color: green;'>Running</b>")
            self.control_button.setText("Stop Server")
            self.server_address_label.setText(f"Server Address: <a href='http://{ip}:{port}' style='color: white;'>http://{ip}:{port}</a>")
            self.server_address_label.setOpenExternalLinks(True)
        else:
            self.status_label.setText("<b style='color: red;'>Stopped</b>")
            self.control_button.setText("Start Server")
            self.server_address_label.setText("Server Address: Not Running")
