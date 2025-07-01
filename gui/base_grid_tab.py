# FILE: gui/base_grid_tab.py
# PURPOSE: Base class for tabs that display items in a grid.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QGridLayout, QLabel, QStackedWidget
from PySide6.QtCore import Qt

class BaseGridTab(QWidget):
    def __init__(self, app_config, main_window=None):
        super().__init__()
        self.app_config = app_config
        self.main_window = main_window
        self.items = {}

        self.main_layout = QVBoxLayout(self)

        # Create and add top panel in subclasses

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Page 0: Scroll Area for items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_content = QWidget()
        self.scroll_area.setWidget(self.scroll_content)
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.grid_layout.setVerticalSpacing(2) # Espaçamento vertical entre os itens
        self.stacked_widget.addWidget(self.scroll_area)

        # Page 1: Info Label
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: white;")
        self.stacked_widget.addWidget(self.info_label)

    def _clear_grid(self):
        self.items.clear()
        while (item := self.grid_layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater()

    def show_message(self, text):
        self.info_label.setText(text)
        self.stacked_widget.setCurrentWidget(self.info_label)

    def show_grid(self):
        self.stacked_widget.setCurrentWidget(self.scroll_area)

    def on_device_changed(self):
        raise NotImplementedError("Subclasses must implement on_device_changed")
