from PySide6.QtCore import Qt, QPoint, Signal, QEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QDialog, QProgressBar) # Added QProgressBar

from . import themes # Assuming themes.py is in the same directory


class CustomTitleBar(QWidget):
    """Custom title bar for frameless windows."""
    def __init__(self, parent_window, title="Window"): # Renamed parent to parent_window for clarity
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(35) # Based on main_window.py

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QLabel(title, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.close_button = QPushButton("✕", self)
        self.close_button.setObjectName("close_button")
        self.close_button.setFixedSize(40, 35)
        self.close_button.clicked.connect(self.parent_window.close) # Connect to parent_window's close

        self.minimize_button = QPushButton("-", self)
        self.minimize_button.setObjectName("minimize_button")
        self.minimize_button.setFixedSize(40, 35)
        self.minimize_button.clicked.connect(self.parent_window.showMinimized) # Connect to parent_window's showMinimized

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.close_button)

        self.pressing = False
        self.start_pos = QPoint(0, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.type() == QEvent.Type.MouseButtonDblClick:
                if self.parent_window.isMaximized():
                    self.parent_window.showNormal()
                else:
                    self.parent_window.showMaximized()
            else:
                self.pressing = True
                self.start_pos = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.pressing:
            self.parent_window.move(event.globalPosition().toPoint() - self.start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.pressing = False
        event.accept()


class CustomThemedDialog(QDialog):
    """A frameless, themed QDialog with a custom title bar."""
    def __init__(self, parent=None, title="Dialog"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.styled_container = QWidget()
        self.styled_container.setObjectName("main_widget") # Use main_widget for consistent styling
        main_layout.addWidget(self.styled_container)

        container_vbox_layout = QVBoxLayout(self.styled_container)
        container_vbox_layout.setContentsMargins(0, 0, 0, 0)
        container_vbox_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self, title)
        container_vbox_layout.addWidget(self.title_bar)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(10, 10, 10, 10) # Content margins from main_window
        self.content_layout.setSpacing(10) # Default spacing

        container_vbox_layout.addLayout(self.content_layout)
        container_vbox_layout.addStretch() # Add stretch to push content up if not enough

        self.update_theme()

    def add_content_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_content_layout(self, layout):
        self.content_layout.addLayout(layout)

    def showMinimized(self):
        """Minimizes the dialog."""
        self.setWindowState(Qt.WindowMinimized)

    def update_theme(self):
        """Applies the current theme to the dialog."""
        themes.apply_stylesheet_to_window(self)
        # apply_stylesheet_to_window already calls apply_theme_to_custom_title_bar if a CustomTitleBar is found


class CustomThemedProgressDialog(CustomThemedDialog):
    canceled = Signal()

    def __init__(self, labelText, cancelButtonText=None, minimum=0, maximum=100, parent=None):
        super().__init__(parent, title="Progress")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(350, 150)

        self._canceled = False

        self.progress_label = QLabel(labelText)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(minimum, maximum)
        self.progress_bar.setValue(minimum)

        self.add_content_widget(self.progress_label)
        self.add_content_widget(self.progress_bar)

        if cancelButtonText:
            self.cancel_button = QPushButton(cancelButtonText)
            self.cancel_button.clicked.connect(self._handle_cancel)
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            button_layout.addWidget(self.cancel_button)
            button_layout.addStretch()
            self.add_content_layout(button_layout)
        else:
            self.cancel_button = None

        # Override minimize button behavior for progress dialog: close
        self.title_bar.minimize_button.clicked.disconnect()
        self.title_bar.minimize_button.clicked.connect(self.close)
        self.title_bar.minimize_button.setText("—")

        # Hide close button if no cancel button is provided to prevent accidental closing
        if not cancelButtonText:
            self.title_bar.close_button.setVisible(False)


    def setLabelText(self, text):
        self.progress_label.setText(text)

    def setRange(self, minimum, maximum):
        self.progress_bar.setRange(minimum, maximum)

    def setValue(self, value):
        self.progress_bar.setValue(value)
        if value >= self.progress_bar.maximum() and not self._canceled:
            self.close()

    def _handle_cancel(self):
        self._canceled = True
        self.canceled.emit()
        self.close()

    def cancel(self):
        self._handle_cancel()

    def wasCanceled(self):
        return self._canceled

    def closeEvent(self, event):
        if not self._canceled: # If closed without explicit cancel, treat as canceled
            self._canceled = True
            self.canceled.emit()
        super().closeEvent(event)
