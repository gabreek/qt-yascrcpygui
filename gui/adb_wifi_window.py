from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QTabWidget)

from . import themes
from .common_widgets import CustomTitleBar
from .workers import AdbConnectWorker, AdbPairWorker

class AdbWifiWindow(QWidget):
    def __init__(self, app_config, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self.thread_pool = QThreadPool.globalInstance()

        self.setWindowTitle(self.app_config.tr('adb_wifi', 'title'))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose) # Ensure window is destroyed on close

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

        # --- Connect Tab ---
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

        # --- Pair Tab ---
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
        self.status_label.setProperty("error", is_error) # Set a dynamic property
        self.style().polish(self.status_label) # Repolish to apply stylesheet changes

    def retranslate_ui(self):
        """Updates all labels and UI texts in the window."""
        self.setWindowTitle(self.app_config.tr('adb_wifi', 'title'))
        self.title_bar.title_label.setText(self.app_config.tr('adb_wifi', 'title'))

        self.tabs.setTabText(0, self.app_config.tr('adb_wifi', 'tabs', key='connect'))
        self.tabs.setTabText(1, self.app_config.tr('adb_wifi', 'tabs', key='pair'))

        self.address_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'placeholder'))
        self.connect_button.setText(self.app_config.tr('adb_wifi', 'connect_btn'))

        self.pair_address_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'pair_placeholder'))
        self.pair_code_input.setPlaceholderText(self.app_config.tr('adb_wifi', 'code_placeholder'))
        self.pair_button.setText(self.app_config.tr('adb_wifi', 'pair_btn'))

        # Update initial msg based on current tab
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
        # If it was a pair, we don't necessarily want to close the window,
        # as the user might want to connect next (connect uses a different port than pair)
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
