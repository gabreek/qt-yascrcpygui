import os
import base64
from PySide6.QtCore import Qt, Signal, QThreadPool, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QMessageBox, QHBoxLayout, QLabel,
                               QPushButton, QStyle, QCheckBox, QLineEdit,
                               QListWidget, QListWidgetItem, QWidget, QVBoxLayout,
                               QTabWidget, QSpinBox, QGroupBox)
from .common_widgets import CustomThemedDialog, CustomTitleBar
from . import themes
from .workers import AdbConnectWorker, AdbPairWorker
from utils.constants import CONF_SHOW_WINLATOR_TAB


# ── Message Box ──────────────────────────────────────────────

def _get_standard_icon_pixmap(icon_type):
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    style = app.style()
    pixmap = QPixmap(QSize(32, 32))
    if icon_type == QMessageBox.Information:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
    elif icon_type == QMessageBox.Warning:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
    elif icon_type == QMessageBox.Critical:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
    elif icon_type == QMessageBox.Question:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
    else:
        return QPixmap()
    return icon.pixmap(pixmap.size())


class CustomMessageBox(CustomThemedDialog):
    def __init__(self, parent=None, title=None, text="", icon_type=QMessageBox.NoIcon, buttons=QMessageBox.Ok, app_icon_path=None):
        if title is None:
            title = self.app_config.tr('common', 'info') if self.app_config else "Message"
        super().__init__(parent, title)
        self.title_bar.minimize_button.clicked.disconnect()
        self.title_bar.minimize_button.clicked.connect(self.close)
        self.title_bar.minimize_button.setText("—")
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        message_content_layout = QHBoxLayout()
        message_content_layout.setSpacing(10)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setScaledContents(True)
        if app_icon_path:
            self.set_app_icon(app_icon_path)
        else:
            self.set_icon_type(icon_type)
        message_content_layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextFormat(Qt.RichText)
        message_content_layout.addWidget(self.text_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.add_content_layout(message_content_layout)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.added_buttons = []
        self.add_buttons(buttons, button_layout)
        button_layout.addStretch()
        self.add_content_layout(button_layout)
        self.result = QMessageBox.NoButton

    def set_icon_type(self, icon_type):
        if icon_type != QMessageBox.NoIcon:
            self.icon_label.setPixmap(_get_standard_icon_pixmap(icon_type))
        else:
            self.icon_label.clear()

    def set_app_icon(self, icon_path):
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap)
                return
        self.icon_label.clear()

    def add_buttons(self, buttons, layout):
        if buttons & QMessageBox.Ok:
            text = self.app_config.tr('common', 'ok') if self.app_config else "OK"
            ok_button = QPushButton(text)
            ok_button.clicked.connect(lambda: self._set_result_and_accept(QMessageBox.Ok))
            layout.addWidget(ok_button)
            self.added_buttons.append(ok_button)
        if buttons & QMessageBox.Cancel:
            text = self.app_config.tr('common', 'cancel') if self.app_config else "Cancel"
            cancel_button = QPushButton(text)
            cancel_button.clicked.connect(lambda: self._set_result_and_accept(QMessageBox.Cancel))
            layout.addWidget(cancel_button)
            self.added_buttons.append(cancel_button)
        if buttons & QMessageBox.Yes:
            text = self.app_config.tr('common', 'yes') if self.app_config else "Yes"
            yes_button = QPushButton(text)
            yes_button.clicked.connect(lambda: self._set_result_and_accept(QMessageBox.Yes))
            layout.addWidget(yes_button)
            self.added_buttons.append(yes_button)
        if buttons & QMessageBox.No:
            text = self.app_config.tr('common', 'no') if self.app_config else "No"
            no_button = QPushButton(text)
            no_button.clicked.connect(lambda: self._set_result_and_accept(QMessageBox.No))
            layout.addWidget(no_button)
            self.added_buttons.append(no_button)

    def _set_result_and_accept(self, result):
        self.result = result
        self.accept()

    def exec(self):
        super().exec()
        return self.result


def show_message_box(parent, title, text, icon=QMessageBox.Information, buttons=QMessageBox.Ok, default_button=QMessageBox.Ok, app_icon_path=None):
    msg_box = CustomMessageBox(parent, title, text, icon, buttons, app_icon_path=app_icon_path)
    for btn in msg_box.added_buttons:
        if (btn.text().lower() == "ok" and default_button == QMessageBox.Ok) or \
           (btn.text().lower() == "yes" and default_button == QMessageBox.Yes) or \
           (btn.text().lower() == "no" and default_button == QMessageBox.No) or \
           (btn.text().lower() == "cancel" and default_button == QMessageBox.Cancel):
            btn.setDefault(True)
            btn.setFocus()
            break
    return msg_box.exec()


# ── Session / Folder Dialogs ──────────────────────────────────

class CreateSessionDialog(CustomThemedDialog):
    def __init__(self, app_config, all_apps, parent=None, session_name=None, selected_apps=None):
        title = app_config.tr('apps_tab', 'create_session_title') if not session_name else app_config.tr('apps_tab', 'edit_session_title')
        super().__init__(parent, title=title)
        self.app_config = app_config
        self.all_apps = all_apps
        self.setMinimumSize(400, 100)
        self.setMaximumHeight(600)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(self.app_config.tr('apps_tab', 'session_name_placeholder'))
        if session_name:
            self.name_input.setText(session_name)
        self.add_content_widget(QLabel(self.app_config.tr('apps_tab', 'session_name_label')))
        self.add_content_widget(self.name_input)
        self.add_content_widget(QLabel(self.app_config.tr('apps_tab', 'select_apps_label')))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setObjectName("session_app_list")
        selected_pkgs = set(selected_apps) if selected_apps else set()
        apps_to_show = [app for app in all_apps if not app.get('is_launcher_shortcut')]
        apps_to_show.sort(key=lambda x: x['name'].lower())
        for app in apps_to_show:
            item = QListWidgetItem(self.list_widget)
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(10, 5, 10, 5)
            checkbox = QCheckBox(app['name'])
            checkbox.setProperty('pkg_name', app['key'])
            if app['key'] in selected_pkgs:
                checkbox.setChecked(True)
            item_layout.addWidget(checkbox)
            item_layout.addStretch()
            item.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)
        self.add_content_widget(self.list_widget)
        btns = QHBoxLayout()
        self.save_btn = QPushButton(self.app_config.tr('common', 'ok'))
        self.cancel_btn = QPushButton(self.app_config.tr('common', 'cancel'))
        btns.addStretch()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        self.add_content_layout(btns)
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def accept(self):
        self.session_name, self.selected_apps = self.get_data()
        super().accept()

    def get_data(self):
        selected_pkgs = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox.isChecked():
                selected_pkgs.append(checkbox.property('pkg_name'))
        return self.name_input.text().strip(), selected_pkgs


class FoldersManagerDialog(CustomThemedDialog):
    def __init__(self, app_config, apps_tab, parent=None):
        super().__init__(parent, title=app_config.tr('apps_tab', 'folders_manager_title'))
        self.app_config = app_config
        self.apps_tab = apps_tab
        self.setMinimumSize(400, 100)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("folders_list")
        self.add_content_widget(self.list_widget)
        self.load_folders()
        actions = QHBoxLayout()
        self.create_btn = QPushButton(self.app_config.tr('apps_tab', 'create_session_btn'))
        self.close_btn = QPushButton(self.app_config.tr('common', 'close'))
        actions.addWidget(self.create_btn)
        actions.addStretch()
        actions.addWidget(self.close_btn)
        self.add_content_layout(actions)
        self.create_btn.clicked.connect(self.on_create_clicked)
        self.close_btn.clicked.connect(self.accept)

    def load_folders(self):
        self.list_widget.clear()
        custom_sessions = self.app_config.get_custom_sessions()
        order = self.app_config.get_custom_sessions_order()
        existing_folders = set(k for k in custom_sessions.keys() if k != 'all')
        sorted_folders = [f for f in order if f in existing_folders]
        remaining_folders = sorted(list(existing_folders - set(sorted_folders)), key=lambda x: x.lower())
        for folder in (sorted_folders + remaining_folders):
            self.add_folder_item(folder, folder, is_system=False)

    def add_folder_item(self, folder_id, display_name, is_system=False):
        item = QListWidgetItem(self.list_widget)
        item_widget = QWidget()
        layout = QHBoxLayout(item_widget)
        layout.setContentsMargins(10, 5, 10, 5)
        name_label = QLabel(display_name)
        layout.addWidget(name_label)
        layout.addStretch()
        btn_up = QPushButton("↑")
        btn_up.setFixedSize(30, 30)
        btn_up.clicked.connect(lambda: self.move_item(item, -1))
        btn_down = QPushButton("↓")
        btn_down.setFixedSize(30, 30)
        btn_down.clicked.connect(lambda: self.move_item(item, 1))
        layout.addWidget(btn_up)
        layout.addWidget(btn_down)
        if not is_system:
            btn_edit = QPushButton("✎")
            btn_edit.setFixedSize(30, 30)
            btn_edit.clicked.connect(lambda: self.on_edit_clicked(folder_id))
            btn_delete = QPushButton("✕")
            btn_delete.setFixedSize(30, 30)
            btn_delete.clicked.connect(lambda: self.on_delete_clicked(folder_id))
            layout.addWidget(btn_edit)
            layout.addWidget(btn_delete)
        item.setData(Qt.UserRole, folder_id)
        item.setSizeHint(item_widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, item_widget)

    def move_item(self, item, direction):
        row = self.list_widget.row(item)
        new_row = row + direction
        if 0 <= new_row < self.list_widget.count():
            item_to_move = self.list_widget.takeItem(row)
            self.list_widget.insertItem(new_row, item_to_move)
            self.list_widget.setItemWidget(item_to_move, self.list_widget.itemWidget(item))
            self.load_folders_from_current_order()
            self.save_order()

    def load_folders_from_current_order(self):
        pass

    def move_item(self, item, delta):
        row = self.list_widget.row(item)
        new_row = row + delta
        if 0 <= new_row < self.list_widget.count():
            current_order = []
            for i in range(self.list_widget.count()):
                current_order.append(self.list_widget.item(i).data(Qt.UserRole))
            current_order[row], current_order[new_row] = current_order[new_row], current_order[row]
            self.app_config.save_custom_sessions_order(current_order)
            self.load_folders()
            self.apps_tab.filter_apps()

    def save_order(self):
        order = []
        for i in range(self.list_widget.count()):
            order.append(self.list_widget.item(i).data(Qt.UserRole))
        self.app_config.save_custom_sessions_order(order)
        self.apps_tab.filter_apps()

    def on_create_clicked(self):
        dialog = CreateSessionDialog(self.app_config, self.apps_tab.all_apps_data, self)
        if dialog.exec():
            name = dialog.session_name
            apps = dialog.selected_apps
            if not name or name == 'all': return
            self.app_config.save_custom_session(name)
            for pkg in apps:
                self.app_config.save_app_metadata(pkg, {'pinned': name})
            self.load_folders()
            self.save_order()
            self.apps_tab._update_folder_list_in_qml()

    def on_edit_clicked(self, folder_id):
        selected_apps = []
        for app in self.apps_tab.all_apps_data:
            metadata = self.app_config.get_app_metadata(app['key'])
            if metadata.get('pinned') == folder_id:
                selected_apps.append(app['key'])
        dialog = CreateSessionDialog(self.app_config, self.apps_tab.all_apps_data, self, session_name=folder_id, selected_apps=selected_apps)
        if dialog.exec():
            new_name = dialog.session_name
            new_apps = dialog.selected_apps
            if not new_name or new_name == 'all': return
            if new_name != folder_id:
                self.app_config.delete_custom_session(folder_id)
                self.app_config.save_custom_session(new_name)
                for pkg in new_apps:
                    self.app_config.save_app_metadata(pkg, {'pinned': new_name})
            else:
                for pkg_id in selected_apps:
                    self.app_config.save_app_metadata(pkg_id, {'pinned': False})
                for pkg_id in new_apps:
                    self.app_config.save_app_metadata(pkg_id, {'pinned': folder_id})
            self.load_folders()
            self.save_order()
            self.apps_tab._update_folder_list_in_qml()

    def on_delete_clicked(self, folder_id):
        confirm = QMessageBox.question(self, self.app_config.tr('common', 'confirm'),
                                       self.app_config.tr('apps_tab', 'delete_session_confirm', name=folder_id))
        if confirm == QMessageBox.Yes:
            self.app_config.delete_custom_session(folder_id)
            self.load_folders()
            self.save_order()


# ── Web Server Config ─────────────────────────────────────────

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


# ── Winlator Frontend Config ──────────────────────────────────

class WinlatorFrontendConfigWindow(CustomThemedDialog):
    winlator_visibility_changed = Signal(bool)

    def __init__(self, app_config, parent=None):
        super().__init__(parent=parent, title=app_config.tr('winlator_frontend_config', 'title'))
        self.app_config = app_config
        self.setMinimumWidth(320)
        self.show_tab_checkbox = QCheckBox(app_config.tr('winlator_frontend_config', 'show_tab'))
        self.show_tab_checkbox.setChecked(app_config.get(CONF_SHOW_WINLATOR_TAB, True))
        self.show_tab_checkbox.stateChanged.connect(self._on_show_tab_changed)
        self.add_content_widget(self.show_tab_checkbox)

    def _on_show_tab_changed(self, state):
        visible = bool(state)
        self.app_config.set(CONF_SHOW_WINLATOR_TAB, visible)
        self.winlator_visibility_changed.emit(visible)

    def retranslate_ui(self):
        self.setWindowTitle(self.app_config.tr('winlator_frontend_config', 'title'))
        self.title_bar.title_label.setText(self.app_config.tr('winlator_frontend_config', 'title'))
        self.show_tab_checkbox.setText(self.app_config.tr('winlator_frontend_config', 'show_tab'))


# ── ADB WiFi ──────────────────────────────────────────────────

class AdbWifiWindow(QWidget):
    def __init__(self, app_config, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self.thread_pool = QThreadPool.globalInstance()
        self.setWindowTitle(self.app_config.tr('adb_wifi', 'title'))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        styled_container = QWidget()
        styled_container.setObjectName("main_widget")
        main_layout.addWidget(styled_container)
        container_vbox_layout = QVBoxLayout(styled_container)
        container_vbox_layout.setContentsMargins(0, 0, 0, 0)
        container_vbox_layout.setSpacing(0)
        self.title_bar = CustomTitleBar(parent_window=self, title=self.app_config.tr('adb_wifi', 'title'))
        container_vbox_layout.addWidget(self.title_bar)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        self.tabs = QTabWidget()
        self.connect_tab = QWidget()
        connect_tab_layout = QVBoxLayout(self.connect_tab)
        connect_tab_layout.setContentsMargins(5, 10, 5, 5)
        connect_tab_layout.setSpacing(10)
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'placeholder'))
        self.address_input.returnPressed.connect(self.handle_connect)
        self.connect_button = QPushButton(self.app_config.tr('adb_wifi', 'connect_btn'))
        self.connect_button.clicked.connect(self.handle_connect)
        connect_tab_layout.addWidget(self.address_input)
        connect_tab_layout.addWidget(self.connect_button)
        connect_tab_layout.addStretch()
        self.pair_tab = QWidget()
        pair_tab_layout = QVBoxLayout(self.pair_tab)
        pair_tab_layout.setContentsMargins(5, 10, 5, 5)
        pair_tab_layout.setSpacing(10)
        pair_inputs_layout = QHBoxLayout()
        pair_inputs_layout.setSpacing(10)
        self.pair_address_input = QLineEdit()
        self.pair_address_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'pair_placeholder'))
        self.pair_code_input = QLineEdit()
        self.pair_code_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'code_placeholder'))
        self.pair_code_input.returnPressed.connect(self.handle_pair)
        pair_inputs_layout.addWidget(self.pair_address_input, 7)
        pair_inputs_layout.addWidget(self.pair_code_input, 3)
        self.pair_button = QPushButton(self.app_config.tr('adb_wifi', 'pair_btn'))
        self.pair_button.clicked.connect(self.handle_pair)
        pair_tab_layout.addLayout(pair_inputs_layout)
        pair_tab_layout.addWidget(self.pair_button)
        pair_tab_layout.addStretch()
        self.tabs.addTab(self.connect_tab, self.app_config.tr('adb_wifi', 'tabs', key='connect'))
        self.tabs.addTab(self.pair_tab, self.app_config.tr('adb_wifi', 'tabs', key='pair'))
        self.status_label = QLabel(self.app_config.tr('adb_wifi', 'initial_msg'))
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("adb_status_label")
        content_layout.addWidget(self.tabs)
        content_layout.addWidget(self.status_label)
        container_vbox_layout.addWidget(content_widget)
        self.resize(350, 180)
        self.update_theme()
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index):
        if index == 0:
            self.status_label.setText(self.app_config.tr('adb_wifi', 'initial_msg'))
        else:
            self.status_label.setText(self.app_config.tr('adb_wifi', 'pair_initial_msg'))

    def set_status(self, text, is_error=False):
        self.status_label.setText(text)
        self.status_label.setProperty("error", is_error)
        self.style().polish(self.status_label)

    def retranslate_ui(self):
        self.setWindowTitle(self.app_config.tr('adb_wifi', 'title'))
        self.title_bar.title_label.setText(self.app_config.tr('adb_wifi', 'title'))
        self.tabs.setTabText(0, self.app_config.tr('adb_wifi', 'tabs', key='connect'))
        self.tabs.setTabText(1, self.app_config.tr('adb_wifi', 'tabs', key='pair'))
        self.address_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'placeholder'))
        self.connect_button.setText(self.app_config.tr('adb_wifi', 'connect_btn'))
        self.pair_address_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'pair_placeholder'))
        self.pair_code_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'code_placeholder'))
        self.pair_button.setText(self.app_config.tr('adb_wifi', 'pair_btn'))
        if self.connect_button.isEnabled() and self.pair_button.isEnabled():
            self._on_tab_changed(self.tabs.currentIndex())

    def handle_connect(self):
        address = self.address_input.text().strip()
        if not address:
            self.set_status(self.app_config.tr('adb_wifi', 'empty_error'), is_error=True)
            return
        self.connect_button.setEnabled(False)
        self.pair_button.setEnabled(False)
        self.connect_button.setText(self.app_config.tr('common', 'loading'))
        self.set_status(self.app_config.tr('adb_wifi', 'connecting', address=address))
        worker = AdbConnectWorker(address)
        worker.signals.result.connect(self._on_connect_success)
        worker.signals.error.connect(self._on_connect_error)
        self.thread_pool.start(worker)

    def handle_pair(self):
        address = self.pair_address_input.text().strip()
        code = self.pair_code_input.text().strip()
        if not address or not code:
            self.set_status(self.app_config.tr('adb_wifi', 'pair_empty_error'), is_error=True)
            return
        self.connect_button.setEnabled(False)
        self.pair_button.setEnabled(False)
        self.pair_button.setText(self.app_config.tr('common', 'loading'))
        self.set_status(self.app_config.tr('adb_wifi', 'pairing', address=address))
        worker = AdbPairWorker(address, code)
        worker.signals.result.connect(self._on_connect_success)
        worker.signals.error.connect(self._on_connect_error)
        self.thread_pool.start(worker)

    def _on_connect_success(self, message):
        self.set_status(message)
        self.connect_button.setEnabled(True)
        self.pair_button.setEnabled(True)
        self.connect_button.setText(self.app_config.tr('adb_wifi', 'connect_btn'))
        self.pair_button.setText(self.app_config.tr('adb_wifi', 'pair_btn'))
        if self.tabs.currentIndex() == 0:
            self.close()

    def _on_connect_error(self, error_message):
        self.set_status(error_message, is_error=True)
        self.connect_button.setEnabled(True)
        self.pair_button.setEnabled(True)
        self.connect_button.setText(self.app_config.tr('adb_wifi', 'connect_btn'))
        self.pair_button.setText(self.app_config.tr('adb_wifi', 'pair_btn'))

    def showMinimized(self):
        self.setWindowState(Qt.WindowMinimized)

    def update_theme(self):
        if self.parent():
            self.setPalette(self.parent().palette())
        themes.apply_stylesheet_to_window(self)
