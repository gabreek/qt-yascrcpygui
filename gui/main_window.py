import sys
import os
from PySide6.QtCore import Qt, QPoint, QTimer, QThreadPool, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QTabWidget, QMessageBox, QInputDialog, QLineEdit)
from PySide6.QtGui import QIcon, QPalette, QColor

from .scrcpy_tab import ScrcpyTab
from .apps_tab import AppsTab
from .scrcpy_session_manager_window_pyside import ScrcpySessionManagerWindow
from .winlator_tab import WinlatorTab
from .workers import DeviceCheckWorker, DeviceConfigLoaderWorker
from .dialogs import show_message_box
from utils import adb_handler


class CustomTitleBar(QWidget):
    """Barra de título customizada."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QLabel("yaScrcpy", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: white; padding-left: 10px; font-weight: bold;")
        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(40, 35)
        self.close_button.clicked.connect(self.parent.close)


        button_style = """
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """
        self.close_button.setStyleSheet(button_style)

        self.minimize_button = QPushButton("-", self)
        self.minimize_button.setFixedSize(40, 35)
        # Connect to the new minimize method in MainWindow
        self.minimize_button.clicked.connect(self.parent.minimize)

        # Add style for minimize button (you had an empty string)
        minimize_button_style = """
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #424242; /* Slightly darker on hover */
            }
            QPushButton:pressed {
                background-color: #2e2e2e; /* Even darker when pressed */
            }
        """
        self.minimize_button.setStyleSheet(minimize_button_style)

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.close_button)

        self.pressing = False
        self.start_pos = QPoint(0, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressing = True
            self.start_pos = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.pressing:
            self.parent.move(event.globalPosition().toPoint() - self.start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.pressing = False
        event.accept()


class MainWindow(QMainWindow):
    """Janela principal da aplicação."""
    device_status_updated = Signal(str)

    def __init__(self, app_config):
        super().__init__()
        self.app_config = app_config
        self.thread_pool = QThreadPool.globalInstance()
        self.active_workers = []

        self.setWindowTitle("yaScrcpy")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icon.png")))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_widget = QWidget()
        main_widget.setObjectName("main_widget")
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget()
        self.scrcpy_tab = ScrcpyTab(self.app_config)
        self.apps_tab = AppsTab(self.app_config, self)
        self.winlator_tab = WinlatorTab(self.app_config, self)
        self.tabs.addTab(self.apps_tab, "Apps")
        self.tabs.addTab(self.winlator_tab, "Winlator")
        self.tabs.addTab(self.scrcpy_tab, "Config")

        # --- NEW: Centralized Launch Handling ---
        self.apps_tab.launch_requested.connect(
            lambda pkg, name: self._handle_launch_request(pkg, name, 'app')
        )
        self.winlator_tab.launch_requested.connect(
            lambda key, name: self._handle_launch_request(key, name, 'winlator')
        )
        # --- END NEW ---

        # --- Profile Change Signal Connections ---
        self.apps_tab.config_changed.connect(self.scrcpy_tab.update_profile_dropdown)
        self.apps_tab.config_deleted.connect(self.scrcpy_tab.update_profile_dropdown)
        self.winlator_tab.config_changed.connect(self.scrcpy_tab.update_profile_dropdown)
        self.winlator_tab.config_deleted.connect(self.scrcpy_tab.update_profile_dropdown)

        self.scrcpy_tab.config_updated_on_worker.connect(self._on_scrcpy_tab_config_ready)

        self.session_manager_button = QPushButton(">")
        self.session_manager_button.setFixedSize(25, 25)
        self.session_manager_button.clicked.connect(self.toggle_scrcpy_session_manager)

        # Use a container widget to get more control over alignment
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 2, 5, 0)
        button_layout.addWidget(self.session_manager_button)
        self.tabs.setCornerWidget(button_container)

        content_layout.addWidget(self.tabs)

        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(content_widget)

        self.setCentralWidget(main_widget)
        self.resize(410, 650)

        self.scrcpy_session_manager_window = None

        self.update_theme()

        self.last_known_device_id = None
        self.device_check_timer = QTimer(self)
        self.device_check_timer.timeout.connect(self.check_device_connection)
        self.device_check_timer.start(2000)
        self.check_device_connection()

        # Connect the new signal to the new slot
        self.device_status_updated.connect(self._handle_device_status_update)

    def _handle_launch_request(self, item_key, item_name, launch_type):
        """
        Central handler for all scrcpy launch requests.
        Orchestrates the optional unlock workflow before launching.
        """
        device_id = self.app_config.get('device_id')
        if not device_id or device_id == "no_device":
            show_message_box(self, "Device Error", "No device connected.", icon=QMessageBox.Critical)
            return

        if self.app_config.get('try_unlock'):
            lock_state = adb_handler.get_device_lock_state(device_id)

            if lock_state in ['LOCKED_SCREEN_ON', 'LOCKED_SCREEN_OFF']:
                pin, ok = QInputDialog.getText(self, "Device Locked", "Enter PIN to unlock:", QLineEdit.Password)
                if ok and pin:
                    adb_handler.unlock_device(device_id, pin)
                elif ok and not pin:
                    # User pressed OK without entering a PIN
                    show_message_box(self, "Unlock Skipped", "No PIN entered. Attempting to launch on locked device.", icon=QMessageBox.Warning)
                else:
                    # User pressed Cancel
                    show_message_box(self, "Launch Cancelled", "Unlock process was cancelled by the user.", icon=QMessageBox.Information)
                    return # Stop the launch process

        # Proceed with the original launch logic from the specific tab
        if launch_type == 'app':
            self.apps_tab.execute_launch(item_key, item_name)
        elif launch_type == 'winlator':
            self.winlator_tab.execute_launch(item_key, item_name)

    def is_dark_theme(self):
        """Verifica se o tema do sistema é escuro."""
        return self.palette().color(QPalette.ColorRole.Window).value() < 128

    def update_theme(self):
        """Atualiza o tema da janela principal e da barra de título."""
        palette = self.palette()
        window_bg_qcolor = palette.color(QPalette.ColorRole.Window)
        main_bg_color = window_bg_qcolor.name()

        if self.is_dark_theme():
            border_color = window_bg_qcolor.lighter(170).name()
        else:
            border_color = window_bg_qcolor.darker(140).name()

        title_text_color = palette.color(QPalette.ColorRole.WindowText).name()
        minimize_hover_qcolor = palette.color(QPalette.ColorRole.AlternateBase)
        minimize_hover_color = minimize_hover_qcolor.lighter(130).name()
        minimize_pressed_color = palette.color(QPalette.ColorRole.Mid).name()
        tab_bg_color = palette.color(QPalette.ColorRole.Base).name()
        tab_text_color = palette.color(QPalette.ColorRole.ButtonText).name()
        tab_selected_bg_color = palette.color(QPalette.ColorRole.Highlight).name()
        tab_selected_text_color = palette.color(QPalette.ColorRole.HighlightedText).name()
        tab_hover_bg_color = palette.color(QPalette.ColorRole.AlternateBase).name()

        style = f"""
            #main_widget {{
                background-color: {main_bg_color};
                border: 1px solid {border_color};
                border-radius: 15px;
            }}
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar::tab {{
                background: {tab_bg_color};
                color: {tab_text_color};
                padding: 8px;
                border-radius: 10px;
                margin: 4px 2px;
            }}
            QTabBar::tab:selected {{
                background: {tab_selected_bg_color};
                color: {tab_selected_text_color};
            }}
            QTabBar::tab:!selected:hover {{
                background: {tab_hover_bg_color};
            }}
            QGroupBox {{
                border: 1px solid {border_color};
                border-radius: 10px;
                margin-top: 7px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                color: {title_text_color};
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {border_color};
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {tab_selected_bg_color};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
                border: none;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QPushButton {{
                background-color: {main_bg_color};
                color: {title_text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {minimize_hover_color};
            }}
            QPushButton:pressed {{
                background-color: {minimize_pressed_color};
            }}
        """
        self.setStyleSheet(style)

        title_style = f"color: {title_text_color}; padding-left: 10px; font-weight: bold;"
        self.title_bar.title_label.setStyleSheet(title_style)

        close_button_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {{title_text_color}};
                border: none;
                font-size: 16px;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
            QPushButton:pressed {{
                background-color: #b71c1c;
            }}
        """
        self.title_bar.close_button.setStyleSheet(close_button_style)

        minimize_button_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {title_text_color};
                border: none;
                font-size: 16px;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: {minimize_hover_color};
            }}
            QPushButton:pressed {{
                background-color: {minimize_pressed_color};
            }}
        """
        self.title_bar.minimize_button.setStyleSheet(minimize_button_style)

    def closeEvent(self, event):
        """Manipula o evento de fechamento da janela."""
        print("Closing application...")
        if self.scrcpy_session_manager_window:
            self.scrcpy_session_manager_window.close()

        self.device_check_timer.stop()
        self.thread_pool.clear()
        self.thread_pool.waitForDone()
        self.scrcpy_tab.stop_all_workers()

        print("All threads and workers stopped. Accepting close event.")
        event.accept()

    def minimize(self):
        """Minimizes the main window."""
        self.showMinimized()

    def toggle_scrcpy_session_manager(self):
        if self.scrcpy_session_manager_window is None or not self.scrcpy_session_manager_window.isVisible():
            parent_geometry = self.geometry()
            self.scrcpy_session_manager_window = ScrcpySessionManagerWindow(
                self.app_config,
                self,
                parent_geometry.x(),
                parent_geometry.y(),
                parent_geometry.width()
            )
            self.scrcpy_session_manager_window.show()
            self.session_manager_button.setText("<")
        else:
            self.scrcpy_session_manager_window.close()
            self.scrcpy_session_manager_window = None
            self.session_manager_button.setText(">")

    def start_worker(self, worker):
        self.active_workers.append(worker)
        worker.signals.finished.connect(lambda: self._on_worker_finished(worker))
        self.thread_pool.start(worker)

    def _on_worker_finished(self, worker):
        if worker in self.active_workers:
            self.active_workers.remove(worker)

    def check_device_connection(self):
        """Inicia a verificação da conexão do dispositivo em um worker thread."""
        worker = DeviceCheckWorker()
        worker.signals.result.connect(self._on_device_check_result)
        worker.signals.finished.connect(lambda: self._on_worker_finished(worker))
        self.active_workers.append(worker)
        self.thread_pool.start(worker)

    def _on_device_check_result(self, current_device_id):
        self.device_status_updated.emit(current_device_id)

    def _update_all_tabs_status(self, message=None):
        if message:
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if hasattr(tab, 'set_device_status_message'):
                    tab.set_device_status_message(message)
        else:
            self.scrcpy_tab.refresh_device_info()
            self.apps_tab.on_device_changed()
            self.winlator_tab.on_device_changed()

    def _handle_device_status_update(self, current_device_id):
        if current_device_id != self.last_known_device_id:
            print(f"MainWindow: Device ID changed from {self.last_known_device_id} to {current_device_id}.")
            self.last_known_device_id = current_device_id

            if current_device_id:
                self._update_all_tabs_status("Please wait, loading...")
                config_loader_worker = DeviceConfigLoaderWorker(current_device_id, self.app_config)
                config_loader_worker.signals.result.connect(self._on_device_config_loaded)
                config_loader_worker.signals.error.connect(self._on_device_load_error)
                config_loader_worker.signals.finished.connect(lambda: self._on_worker_finished(config_loader_worker))
                self.active_workers.append(config_loader_worker)
                self.thread_pool.start(config_loader_worker)
            else:
                self.app_config.load_config_for_device(None)
                self._update_all_tabs_status()

    def _on_device_config_loaded(self, result_data):
        print("MainWindow: Device config loaded successfully.")
        self._update_all_tabs_status()

    def _on_device_load_error(self, error_message):
        print(f"MainWindow: Error loading device config: {error_message}")
        self._update_all_tabs_status(f"Error: {error_message}")

    def _on_scrcpy_tab_config_ready(self):
        self.scrcpy_tab._update_all_widgets_from_config()
