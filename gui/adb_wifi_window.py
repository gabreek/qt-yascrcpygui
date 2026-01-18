from PySide6.QtCore import Qt, QPoint, Signal, QRunnable, QObject, QThreadPool
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit)
from PySide6.QtGui import QPalette

from utils import adb_handler
from . import themes

class AdbWorkerSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()

class AdbConnectWorker(QRunnable):
    def __init__(self, address):
        super().__init__()
        self.signals = AdbWorkerSignals()
        self.address = address

    def run(self):
        try:
            output = adb_handler.connect_wifi(self.address)
            if 'connected to' in output or 'already connected' in output:
                self.signals.result.emit(output)
            else:
                self.signals.error.emit(output if output else "Connection failed. Check IP/Port and `adb` command.")
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class CustomTitleBar(QWidget):
    def __init__(self, parent, title="ADB over Wifi"):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(35)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QLabel(title, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("close_button")
        self.close_button.setFixedSize(40, 35)
        self.close_button.clicked.connect(self.parent.close)

        self.minimize_button = QPushButton("_")
        self.minimize_button.setObjectName("minimize_button")
        self.minimize_button.setFixedSize(40, 35)
        self.minimize_button.clicked.connect(self.parent.showMinimized)

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.close_button)

        self.pressing = False
        self.start_pos = QPoint(0, 0)



    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self.pressing = True

            self.start_pos = event.globalPosition().toPoint() - self.parent.window().frameGeometry().topLeft()

            event.accept()



    def mouseMoveEvent(self, event):

        if self.pressing:

            self.parent.window().move(event.globalPosition().toPoint() - self.start_pos)

            event.accept()



    def mouseReleaseEvent(self, event):

        self.pressing = False

        event.accept()



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



        self.title_bar = CustomTitleBar(self)

        container_vbox_layout.addWidget(self.title_bar)



        content_widget = QWidget()

        content_layout = QVBoxLayout(content_widget)

        content_layout.setContentsMargins(10, 10, 10, 10)

        content_layout.setSpacing(10)



        self.ip_input = QLineEdit()

        self.ip_input.setPlaceholderText("Device IP Address")

        self.port_input = QLineEdit("5555")

        self.port_input.setFixedWidth(60)



        input_layout = QHBoxLayout()

        input_layout.addWidget(self.ip_input)

        input_layout.addWidget(self.port_input)



        self.connect_button = QPushButton("Connect")

        self.connect_button.clicked.connect(self.handle_connect)

        

        self.status_label = QLabel("Enter the device IP and port.")

        self.status_label.setWordWrap(True)

        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)



        content_layout.addLayout(input_layout)

        content_layout.addWidget(self.connect_button)

        content_layout.addWidget(self.status_label)

        content_layout.addStretch()



        container_vbox_layout.addWidget(content_widget)



        self.resize(400, 160)

        self.update_theme()



    def set_status(self, text, is_error=False):

        self.status_label.setText(text)

        if is_error:

            self.status_label.setStyleSheet("color: red;")

        else:

            # Reset to theme color

            palette = self.palette()

            text_color = palette.color(QPalette.ColorRole.WindowText).name()

            self.status_label.setStyleSheet(f"color: {text_color};")



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
