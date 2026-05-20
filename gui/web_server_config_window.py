import base64
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QCheckBox, QPushButton, QLabel, QLineEdit, QFormLayout, QSpinBox
from .common_widgets import CustomThemedDialog

class WebServerConfigWindow(CustomThemedDialog):
    start_server_requested = Signal()
    stop_server_requested = Signal()

    def __init__(self, app_config, parent=None):
        super().__init__(parent=parent, title=app_config.tr('web_server_config', 'title'))
        self.app_config = app_config
        self.is_running = False

        self.setMinimumWidth(350)

        # Start on launch
        self.start_on_launch_checkbox = QCheckBox(self.app_config.tr('web_server_config', 'start_on_launch'))
        self.start_on_launch_checkbox.setChecked(self.app_config.get('start_web_server_on_launch', False))
        self.start_on_launch_checkbox.stateChanged.connect(self._on_start_on_launch_changed)
        self.add_content_widget(self.start_on_launch_checkbox)

        # Port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel(self.app_config.tr('web_server_config', 'port')))
        self.port_spinbox = QSpinBox()
        self.port_spinbox.setRange(1024, 65535)
        self.port_spinbox.setValue(int(self.app_config.get('web_port', 8000)))
        self.port_spinbox.valueChanged.connect(self._on_port_changed)
        port_layout.addWidget(self.port_spinbox)
        port_layout.addStretch()
        self.add_content_layout(port_layout)

        # Auth Settings (Vertical)
        auth_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(self.app_config.tr('web_server_config', 'username_placeholder'))
        self.username_input.setText(self.app_config.get('web_username', ''))
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText(self.app_config.tr('web_server_config', 'password_placeholder'))
        
        encoded_pass = self.app_config.get('web_password', '')
        if encoded_pass:
            try:
                self.password_input.setText(base64.b64decode(encoded_pass.encode()).decode())
            except:
                self.password_input.setText('')
        
        self.username_input.textChanged.connect(self._on_auth_changed)
        self.password_input.textChanged.connect(self._on_auth_changed)
        
        auth_layout.addRow(self.app_config.tr('web_server_config', 'username'), self.username_input)
        auth_layout.addRow(self.app_config.tr('web_server_config', 'password'), self.password_input)
        self.add_content_layout(auth_layout)

        # Status and control
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel(self.app_config.tr('web_server_config', 'server_status')))
        self.status_label = QLabel(self.app_config.tr('web_server_config', 'stopped'))
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.control_button = QPushButton(self.app_config.tr('web_server_config', 'start_btn'))
        self.control_button.clicked.connect(self._on_control_button_clicked)
        status_layout.addWidget(self.control_button)
        self.add_content_layout(status_layout)

        self.server_address_label = QLabel(self.app_config.tr('web_server_config', 'not_running'))
        self.add_content_widget(self.server_address_label)

    def _on_start_on_launch_changed(self, state):
        self.app_config.set('start_web_server_on_launch', bool(state))

    def _on_port_changed(self, val):
        self.app_config.set('web_port', int(val))

    def _on_auth_changed(self, *args):
        self.app_config.set('web_username', self.username_input.text())
        encoded_pass = base64.b64encode(self.password_input.text().encode()).decode()
        self.app_config.set('web_password', encoded_pass)

    def _on_control_button_clicked(self):
        if self.is_running:
            self.stop_server_requested.emit()
        else:
            self.start_server_requested.emit()

    def retranslate_ui(self):
        """Updates all labels and UI texts in the window."""
        self.setWindowTitle(self.app_config.tr('web_server_config', 'title'))
        self.title_bar.title_label.setText(self.app_config.tr('web_server_config', 'title'))
        self.start_on_launch_checkbox.setText(self.app_config.tr('web_server_config', 'start_on_launch'))
        # Re-update status labels to apply new translations
        # Assuming we can just call update_status with current state
        # We need to know if it's running. Let's store that or re-detect.
        # update_status is usually called from main_window, but we can do it here too.
        # For now, let's just update common labels.
        self.update_status(self.is_running)

    def update_status(self, is_running, ip="127.0.0.1"):
        self.is_running = is_running
        port = self.app_config.get('web_port', 8000)
        
        # Bloqueia/Desbloqueia inputs se o servidor estiver rodando
        can_edit = not self.is_running
        self.port_spinbox.setEnabled(can_edit)
        self.username_input.setEnabled(can_edit)
        self.password_input.setEnabled(can_edit)
        
        if self.is_running:
            running_text = self.app_config.tr('web_server_config', 'running')
            self.status_label.setText(f"<b style='color: green;'>{running_text}</b>")
            self.control_button.setText(self.app_config.tr('web_server_config', 'stop_btn'))
            addr_label = self.app_config.tr('web_server_config', 'address_label')
            self.server_address_label.setText(f"{addr_label} <a href='http://{ip}:{port}' style='color: white;'>http://{ip}:{port}</a>")
            self.server_address_label.setOpenExternalLinks(True)
        else:
            stopped_text = self.app_config.tr('web_server_config', 'stopped')
            self.status_label.setText(f"<b style='color: red;'>{stopped_text}</b>")
            self.control_button.setText(self.app_config.tr('web_server_config', 'start_btn'))
            addr_label = self.app_config.tr('web_server_config', 'address_label')
            not_run = self.app_config.tr('web_server_config', 'not_running')
            self.server_address_label.setText(f"{addr_label} {not_run}")
