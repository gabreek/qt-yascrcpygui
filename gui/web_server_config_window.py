import base64
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
                               QLabel, QLineEdit, QSpinBox, QGroupBox)
from .common_widgets import CustomThemedDialog


class _Section(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 14, 8, 8)
        self._layout.setSpacing(6)

    def add_row(self, label_text, widget):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setObjectName("settings_field_label")
        label.setFixedWidth(80)
        row.addWidget(label)
        row.addWidget(widget)
        self._layout.addLayout(row)

    def add_widget(self, widget):
        self._layout.addWidget(widget)


class WebServerConfigWindow(CustomThemedDialog):
    start_server_requested = Signal()
    stop_server_requested = Signal()

    def __init__(self, app_config, parent=None):
        super().__init__(parent=parent, title=app_config.tr('web_server_config', 'title'))
        self.app_config = app_config
        self.is_running = False

        self.setMinimumWidth(420)
        tr = self.app_config.tr

        # ---- Server section ----
        self._server_section = _Section(tr('web_server_config', 'section_server'))
        server_section = self._server_section

        self.start_on_launch_checkbox = QCheckBox(tr('web_server_config', 'start_on_launch'))
        self.start_on_launch_checkbox.setChecked(self.app_config.get('start_web_server_on_launch', False))
        self.start_on_launch_checkbox.stateChanged.connect(self._on_start_on_launch_changed)
        server_section.add_widget(self.start_on_launch_checkbox)

        self.port_spinbox = QSpinBox()
        self.port_spinbox.setRange(1024, 65535)
        self.port_spinbox.setValue(int(self.app_config.get('web_port', 8000)))
        self.port_spinbox.setFixedWidth(120)
        self.port_spinbox.valueChanged.connect(self._on_port_changed)
        server_section.add_row(tr('web_server_config', 'port'), self.port_spinbox)

        self.add_content_widget(server_section)

        # ---- Auth section ----
        self._auth_section = _Section(tr('web_server_config', 'section_auth'))
        auth_section = self._auth_section

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(tr('web_server_config', 'username_placeholder'))
        self.username_input.setText(self.app_config.get('web_username', ''))

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText(tr('web_server_config', 'password_placeholder'))

        encoded_pass = self.app_config.get('web_password', '')
        if encoded_pass:
            try:
                self.password_input.setText(base64.b64decode(encoded_pass.encode()).decode())
            except Exception:
                self.password_input.setText('')

        self.username_input.textChanged.connect(self._on_auth_changed)
        self.password_input.textChanged.connect(self._on_auth_changed)

        auth_section.add_row(tr('web_server_config', 'username'), self.username_input)
        auth_section.add_row(tr('web_server_config', 'password'), self.password_input)

        self.add_content_widget(auth_section)

        # ---- Status section ----
        self._status_section = _Section(tr('web_server_config', 'section_status'))
        status_section = self._status_section

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(QLabel(tr('web_server_config', 'server_status')))
        self.status_label = QLabel(tr('web_server_config', 'stopped'))
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        self.control_button = QPushButton(tr('web_server_config', 'start_btn'))
        self.control_button.setFixedWidth(130)
        self.control_button.clicked.connect(self._on_control_button_clicked)
        status_row.addWidget(self.control_button)
        status_section._layout.addLayout(status_row)

        self.server_address_label = QLabel(tr('web_server_config', 'not_running'))
        self.server_address_label.setOpenExternalLinks(True)
        status_section._layout.addWidget(self.server_address_label)

        self.add_content_widget(status_section)

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
        tr = self.app_config.tr
        self.setWindowTitle(tr('web_server_config', 'title'))
        self.title_bar.title_label.setText(tr('web_server_config', 'title'))
        self._server_section.setTitle(tr('web_server_config', 'section_server'))
        self._auth_section.setTitle(tr('web_server_config', 'section_auth'))
        self._status_section.setTitle(tr('web_server_config', 'section_status'))
        self.start_on_launch_checkbox.setText(tr('web_server_config', 'start_on_launch'))
        self.update_status(self.is_running)

    def update_status(self, is_running, ip="127.0.0.1"):
        self.is_running = is_running
        port = self.app_config.get('web_port', 8000)
        tr = self.app_config.tr

        can_edit = not self.is_running
        self.port_spinbox.setEnabled(can_edit)
        self.username_input.setEnabled(can_edit)
        self.password_input.setEnabled(can_edit)

        if self.is_running:
            self.status_label.setText(f"<b style='color: #4CAF50;'>{tr('web_server_config', 'running')}</b>")
            self.control_button.setText(tr('web_server_config', 'stop_btn'))
            addr = tr('web_server_config', 'address_label')
            self.server_address_label.setText(
                f"{addr} <a href='http://{ip}:{port}' style='text-decoration: underline;'>http://{ip}:{port}</a>"
            )
        else:
            self.status_label.setText(f"<span style='color: #e74c3c;'>{tr('web_server_config', 'stopped')}</span>")
            self.control_button.setText(tr('web_server_config', 'start_btn'))
            addr = tr('web_server_config', 'address_label')
            self.server_address_label.setText(
                f"{addr} {tr('web_server_config', 'not_running')}"
            )
