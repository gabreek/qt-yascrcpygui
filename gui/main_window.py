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
from .common_widgets import CustomTitleBar, CustomThemedInputDialog
from utils import adb_handler
import web_server

class WebServerThread(QThread):
    """
    Thread to run the FastAPI web server with graceful shutdown using uvicorn.Server.
    """
    config_needs_reload = Signal() # Added for synchronization
    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = None
        self._loop = None

    def run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            # Set the thread instance in the web_server module
            web_server.set_thread_instance(self)

            config = uvicorn.Config(web_server.app, host="0.0.0.0", port=8000, log_level="info", loop="asyncio")
            self.server = uvicorn.Server(config)

            self._loop.run_until_complete(self.server.serve())

        except Exception as e:
            if "Event loop is closed" not in str(e):
                 print(f"Web server thread crashed: {e}")
        finally:
            if self._loop and self._loop.is_running():
                self._loop.close()
            print("Web server event loop finished.")


    def stop(self):
        """Gracefully signals the uvicorn server to shut down."""
        if self.server and self.isRunning():
            print("Requesting web server shutdown...")
            self.server.should_exit = True

            # Give the thread up to 5 seconds to terminate gracefully.
            if not self.wait(5000):
                print("Web server thread did not terminate gracefully within 5 seconds.")
                # We do not call terminate() here as it can lead to resource leaks.
                # Instead, we rely on the main application to eventually exit.

            print("Web server thread has been stopped.")


class MainWindow(QMainWindow):
    """Janela principal da aplicação."""
    device_status_updated = Signal(str)
    web_server_status_changed = Signal(bool)

    RESIZE_BORDER = 5 # Width of the resize border area

    def __init__(self, app, app_config):
        super().__init__()
        self.app = app
        self.app_config = app_config
        self.thread_pool = QThreadPool.globalInstance()
        self.active_workers = []
        self.web_server_thread = None
        self.web_config_window = None

        # Resizing related properties
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self._resize_edges = Qt.Edges()

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
        self.resize(495, 700)
        self.setMinimumSize(400, 400) # Set a minimum size for the window

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

    def get_resize_edges(self, pos):
        """Determines which edges are being interacted with for resizing."""
        edges = Qt.Edges()
        # Check within a small margin from the window's physical borders
        on_left = pos.x() < self.RESIZE_BORDER
        on_right = pos.x() > self.width() - self.RESIZE_BORDER
        on_top = pos.y() < self.RESIZE_BORDER
        on_bottom = pos.y() > self.height() - self.RESIZE_BORDER

        if on_left:
            edges |= Qt.LeftEdge
        if on_right:
            edges |= Qt.RightEdge
        if on_top:
            edges |= Qt.TopEdge
        if on_bottom:
            edges |= Qt.BottomEdge
        return edges

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._resize_edges = self.get_resize_edges(event.position().toPoint())
            if self._resize_edges:
                self._resizing = True
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()
            elif self.title_bar.geometry().contains(event.position().toPoint()): # Allow dragging from title bar
                self._resizing = False # Not resizing, but will be dragging
                self._resize_start_pos = event.globalPosition().toPoint()
            else:
                super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing: # We are in a resizing state
            global_pos = event.globalPosition().toPoint()
            delta = global_pos - self._resize_start_pos
            rect = self._resize_start_geometry # Original geometry when resize started

            temp_x, temp_y, temp_w, temp_h = rect.x(), rect.y(), rect.width(), rect.height()

            # --- Horizontal Resizing ---
            if self._resize_edges & Qt.LeftEdge:
                temp_x = rect.x() + delta.x()
                temp_w = rect.width() - delta.x()
            if self._resize_edges & Qt.RightEdge:
                temp_w = rect.width() + delta.x()

            # --- Vertical Resizing ---
            if self._resize_edges & Qt.TopEdge:
                temp_y = rect.y() + delta.y()
                temp_h = rect.height() - delta.y()
            if self._resize_edges & Qt.BottomEdge:
                temp_h = rect.height() + delta.y()

            # Apply minimum size constraints for width
            if temp_w < self.minimumWidth():
                if self._resize_edges & Qt.LeftEdge:
                    # If shrinking from left, adjust x to keep width at min (pin right edge)
                    temp_x = rect.x() + rect.width() - self.minimumWidth()
                temp_w = self.minimumWidth()

            # Apply minimum size constraints for height
            if temp_h < self.minimumHeight():
                if self._resize_edges & Qt.TopEdge:
                    # If shrinking from top, adjust y to keep height at min (pin bottom edge)
                    temp_y = rect.y() + rect.height() - self.minimumHeight()
                temp_h = self.minimumHeight()

            self.setGeometry(temp_x, temp_y, temp_w, temp_h)
        elif event.buttons() == Qt.MouseButton.LeftButton and self._resize_start_pos: # Dragging
            diff = event.globalPosition().toPoint() - self._resize_start_pos
            self.move(self.pos() + diff)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._resizing = False
            self._resize_edges = Qt.Edges()
            self._resize_start_pos = None
            self._resize_start_geometry = None
            self.unsetCursor() # Reset cursor after resizing
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        # Apply rounded corners mask if needed
        # This part assumes a fixed corner radius for the main_widget
        # If the main_widget has a border-radius in CSS, this mask might interfere or be redundant.
        # For now, let's skip explicit mask unless visual issues arise.
        # If rounded corners are desired via mask:
        # path = QPainterPath()
        # path.addRoundedRect(self.rect(), 15, 15) # Assuming 15px radius from CSS
        # self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def start_web_server(self):
        if self.is_web_server_running():
            return

    def start_web_server(self):
        if self.is_web_server_running():
            return
        self.web_server_thread = WebServerThread()
        # Connect the signal from the web server thread to the ScrcpyTab's reload slot
        self.web_server_thread.config_needs_reload.connect(self.scrcpy_tab.on_config_reloaded)
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
                pin, ok = CustomThemedInputDialog.getText(
                    self,
                    "Device Locked",
                    "Enter PIN to unlock:",
                    text_input_mode=QLineEdit.Password
                )
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

        # Propagate theme change to tabs with QML content
        self.apps_tab.update_theme()
        self.winlator_tab.update_theme()

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
            
            # Calculate center position
            parent_rect = self.geometry()
            child_width = self.adb_wifi_window.width()
            child_height = self.adb_wifi_window.height()

            x = parent_rect.x() + (parent_rect.width() - child_width) // 2
            y = parent_rect.y() + (parent_rect.height() - child_height) // 2

            self.adb_wifi_window.move(x, y) # Move to calculated position
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
