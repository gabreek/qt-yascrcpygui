import os
import asyncio # New import for uvicorn server management
import uvicorn # New import for uvicorn server management
import time
from PySide6.QtCore import Qt, QTimer, QThreadPool, Signal, QThread
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QTabWidget, QInputDialog, QLineEdit, QMessageBox)
from PySide6.QtGui import QIcon

from .scrcpy_tab import ScrcpyTab
from .apps_tab import AppsTab
from .scrcpy_session_manager_window_pyside import ScrcpySessionManagerWindow
from .winlator_tab import WinlatorTab
from .workers import DeviceCheckWorker, DeviceConfigLoaderWorker
from .dialogs import show_message_box
from .adb_wifi_window import AdbWifiWindow
from . import themes
from .common_widgets import CustomTitleBar
from utils import adb_handler
import web_server

class WebServerThread(QThread):
    """
    Thread to run the FastAPI web server with graceful shutdown using uvicorn.Server.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.server_config = None
        self.server = None
        self._loop = None

    def run(self):
        # Create a new event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self.server_config = uvicorn.Config(
            web_server.app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            loop="asyncio"
        )
        self.server = uvicorn.Server(self.server_config)

        # Uvicorn's serve() is an async method
        async def serve_with_graceful_shutdown():
            await self.server.serve()

        try:
            self._loop.run_until_complete(serve_with_graceful_shutdown())
        except asyncio.CancelledError:
            print("Web server thread cancelled.")
        except Exception as e:
            print(f"Web server crashed: {e}")
        finally:
            if self._loop and not self._loop.is_closed():
                # Ensure pending tasks are cancelled and loop is properly closed
                for task in asyncio.all_tasks(self._loop):
                    task.cancel()
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                self._loop.close()
            self._loop = None
            self.server = None
            self.server_config = None

    def stop(self):
        """Gracefully signals the uvicorn server to shut down."""
        if self.server and not self.server.should_exit:
            self.server.should_exit = True
            print("Signal sent to stop web server.")
            # It's important to wait for the thread to actually finish its loop
            self.wait()


class MainWindow(QMainWindow):
    """Janela principal da aplicação."""
    device_status_updated = Signal(str)
    web_server_status_changed = Signal(bool)

    def __init__(self, app, app_config):
        super().__init__()
        self.app = app
        self.app_config = app_config
        self.thread_pool = QThreadPool.globalInstance()
        self.active_workers = []
        self.web_server_thread = None
        self.web_config_window = None

        self.setWindowTitle("yaScrcpy")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icon.png")))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_widget = QWidget()
        main_widget.setObjectName("main_widget")
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self, title="yaScrcpy")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget()
        self.scrcpy_tab = ScrcpyTab(self.app_config, self)
        self.apps_tab = AppsTab(self.app_config, self)
        self.winlator_tab = WinlatorTab(self.app_config, self)
        self.tabs.addTab(self.apps_tab, "Apps")
        self.tabs.addTab(self.winlator_tab, "Winlator")
        self.tabs.addTab(self.scrcpy_tab, "Config")

        self.apps_tab.launch_requested.connect(
            lambda pkg, name: self._handle_launch_request(pkg, name, 'app')
        )
        self.winlator_tab.launch_requested.connect(
            lambda key, name: self._handle_launch_request(key, name, 'winlator')
        )

        self.apps_tab.config_changed.connect(self.scrcpy_tab.update_profile_dropdown)
        self.apps_tab.config_deleted.connect(self.scrcpy_tab.update_profile_dropdown)
        self.winlator_tab.config_changed.connect(self.scrcpy_tab.update_profile_dropdown)
        self.winlator_tab.config_deleted.connect(self.scrcpy_tab.update_profile_dropdown)
        self.scrcpy_tab.theme_changed.connect(self.update_theme)
        self.scrcpy_tab.config_updated_on_worker.connect(self._on_scrcpy_tab_config_ready)

        self.wifi_button = QPushButton("🛜")
        self.wifi_button.setObjectName("wifi_button")
        self.wifi_button.setFixedSize(25, 25)
        self.wifi_button.setToolTip("ADB over WiFi")
        self.wifi_button.clicked.connect(self.open_adb_wifi_manager)

        self.session_manager_button = QPushButton(">")
        self.session_manager_button.setObjectName("session_manager_button")
        self.session_manager_button.setFixedSize(25, 25)
        self.session_manager_button.clicked.connect(self.toggle_scrcpy_session_manager)

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 2, 5, 0)
        button_layout.addWidget(self.wifi_button)
        button_layout.addWidget(self.session_manager_button)
        self.tabs.setCornerWidget(button_container)

        content_layout.addWidget(self.tabs)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(content_widget)

        self.setCentralWidget(main_widget)
        self.resize(410, 650)

        self.scrcpy_session_manager_window = None
        self.adb_wifi_window = None

        self.update_theme()

        self.last_known_device_id = None
        self.device_check_timer = QTimer(self)
        self.device_check_timer.timeout.connect(self.check_device_connection)
        self.device_check_timer.start(2000)
        self.check_device_connection()

        self.device_status_updated.connect(self._handle_device_status_update)

        if self.app_config.get('start_web_server_on_launch'):
            self.start_web_server()

    def start_web_server(self):
        if self.is_web_server_running():
            return
        self.web_server_thread = WebServerThread()
        self.web_server_thread.start()
        self.web_server_status_changed.emit(True)
        print("Web server started.")

    def stop_web_server(self):
        if not self.is_web_server_running():
            return
        if self.web_server_thread:
            self.web_server_thread.stop() # Call the graceful stop method
            self.web_server_thread = None
        self.web_server_status_changed.emit(False)
        print("Web server stopped.")

    def is_web_server_running(self):
        return self.web_server_thread is not None and self.web_server_thread.isRunning()

    def closeEvent(self, event):
        self.stop_web_server() # Ensure server is stopped first
        if self.scrcpy_session_manager_window:
            self.scrcpy_session_manager_window.close()
        self.device_check_timer.stop()
        self.thread_pool.clear()
        self.thread_pool.waitForDone()
        self.scrcpy_tab.stop_all_workers()
        event.accept()
        
    # ... (rest of the methods are the same) ...

    def pause_device_check(self):
        self.device_check_timer.stop()

    def resume_device_check(self):
        self.device_check_timer.start(2000)

    def _handle_launch_request(self, item_key, item_name, launch_type):
        device_id = self.app_config.get_connection_id()
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
                    show_message_box(self, "Unlock Skipped", "No PIN entered. Attempting to launch on locked device.", icon=QMessageBox.Warning)
                else:
                    show_message_box(self, "Launch Cancelled", "Unlock process was cancelled by the user.", icon=QMessageBox.Information)
                    return
        if launch_type == 'app':
            self.apps_tab.execute_launch(item_key, item_name)
        elif launch_type == 'winlator':
            self.winlator_tab.execute_launch(item_key, item_name)

    def update_theme(self):
        themes.apply_stylesheet_to_window(self)
        if self.adb_wifi_window and self.adb_wifi_window.isVisible():
            self.adb_wifi_window.update_theme()
        if self.scrcpy_session_manager_window and self.scrcpy_session_manager_window.isVisible():
            self.scrcpy_session_manager_window.update_theme()

    def minimize(self):
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

    def open_adb_wifi_manager(self):
        if self.adb_wifi_window is None or not self.adb_wifi_window.isVisible():
            self.adb_wifi_window = AdbWifiWindow(self.app_config, self)
            self.adb_wifi_window.show()

    def start_worker(self, worker):
        self.active_workers.append(worker)
        worker.signals.finished.connect(lambda: self._on_worker_finished(worker))
        self.thread_pool.start(worker)

    def _on_worker_finished(self, worker):
        if worker in self.active_workers:
            self.active_workers.remove(worker)

    def check_device_connection(self):
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
            self.last_known_device_id = current_device_id
            if current_device_id:
                self._update_all_tabs_status("Please wait, loading...")
                self.pause_device_check()
                config_loader_worker = DeviceConfigLoaderWorker(current_device_id, self.app_config)
                config_loader_worker.signals.result.connect(self._on_device_config_loaded)
                config_loader_worker.signals.error.connect(self._on_device_load_error)
                config_loader_worker.signals.finished.connect(self.resume_device_check)
                self.active_workers.append(config_loader_worker)
                self.thread_pool.start(config_loader_worker)
            else:
                self.app_config.load_config_for_device(None)
                self._update_all_tabs_status()

    def _on_device_config_loaded(self, result_data, installed_apps_packages, winlator_shortcuts_on_device):
        self.last_known_device_id = result_data["device_id"]
        self.app_config.device_app_cache['installed_apps'] = installed_apps_packages
        self.app_config.device_app_cache['winlator_shortcuts'] = winlator_shortcuts_on_device
        self._update_all_tabs_status()

    def _on_device_load_error(self, error_message):
        self._update_all_tabs_status(f"Error: {error_message}")

    def _on_scrcpy_tab_config_ready(self):
        self.scrcpy_tab._update_all_widgets_from_config()
        self.apps_tab._update_display()