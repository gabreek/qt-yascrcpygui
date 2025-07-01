import sys
import os
from PySide6.QtCore import Qt, QPoint, QTimer, QThread, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget
from PySide6.QtGui import QIcon

from .scrcpy_tab import ScrcpyTab
from .apps_tab import AppsTab
from .winlator_tab import WinlatorTab
from .workers import DeviceCheckWorker


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
        #self.restart_app_callback = restart_app_callback

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
        self.apps_tab = AppsTab(self.app_config)
        self.winlator_tab = WinlatorTab(self.app_config)
        self.tabs.addTab(self.apps_tab, "Apps")
        self.tabs.addTab(self.winlator_tab, "Winlator")
        self.tabs.addTab(self.scrcpy_tab, "Config")

        content_layout.addWidget(self.tabs)

        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(content_widget)

        self.setCentralWidget(main_widget)
        self.resize(410, 650)

        self.setStyleSheet("""
            #main_widget {
                background-color: #2e2e2e;
                border: 1px solid #424242;
                border-radius: 8px;
            }
            QTabWidget::pane {
                border: 1px solid #424242;
                border-top: none;
            }
            QTabBar::tab {
                background: #424242;
                color: white;
                padding: 8px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #616161;
            }
            QTabBar::tab:!selected:hover {
                background: #515151;
            }
        """)

        self.last_known_device_id = None
        self.device_check_timer = QTimer(self)
        self.device_check_timer.timeout.connect(self.check_device_connection)
        self.device_check_timer.start(2000)
        self.check_device_connection()

        # Connect the new signal to the new slot
        self.device_status_updated.connect(self._handle_device_status_update)

    def closeEvent(self, event):
        """Manipula o evento de fechamento da janela."""
        self.device_check_timer.stop()
        self.scrcpy_tab.stop_all_workers()
        event.accept()

    def minimize(self):
        """Minimizes the main window."""
        self.showMinimized()

    def check_device_connection(self):
        """Inicia a verificação da conexão do dispositivo em um worker thread."""
        self.device_check_worker = DeviceCheckWorker()
        self.device_check_thread = QThread()
        self.device_check_worker.moveToThread(self.device_check_thread)
        self.device_check_worker.finished.connect(self.device_check_thread.quit)
        self.device_check_worker.finished.connect(self.device_check_worker.deleteLater)
        self.device_check_thread.finished.connect(self.device_check_thread.deleteLater)
        self.device_check_worker.result.connect(self._on_device_check_result)
        self.device_check_thread.started.connect(self.device_check_worker.run)
        self.device_check_thread.start()

    def _on_device_check_result(self, current_device_id):
        # This method is called from the worker thread. Emit a signal to the main thread.
        self.device_status_updated.emit(current_device_id)

    def _handle_device_status_update(self, current_device_id):
        # This slot is called from the main thread, safe to update UI and config.
        if current_device_id != self.last_known_device_id:
            print(f"MainWindow: Device ID changed from {self.last_known_device_id} to {current_device_id}. Refreshing...")
            self.last_known_device_id = current_device_id
            self.app_config.set('device_id', current_device_id if current_device_id else "no_device")
            self.app_config.load_config_for_device(current_device_id if current_device_id else None)

            # Notifica todas as abas sobre a mudança de dispositivo
            self.scrcpy_tab.refresh_device_info()
            self.apps_tab.on_device_changed()
            self.winlator_tab.on_device_changed()


