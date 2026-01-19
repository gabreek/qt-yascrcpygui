from PySide6.QtWidgets import (QApplication, QMessageBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QStyle)
from PySide6.QtGui import QPixmap, QColor, QPainter, QPalette
from PySide6.QtCore import Qt, QSize
import os
from .common_widgets import CustomThemedDialog # Import the custom themed dialog
from . import themes # For palette if needed, and apply_stylesheet_to_window

def _get_standard_icon_pixmap(icon_type):
    # Use QApplication to get the current style and its standard pixmaps
    app = QApplication.instance()
    if not app:
        # If no app instance, create a dummy one for style access (not ideal but works for standalone script testing)
        # In a real app, QApplication should always be running.
        app = QApplication([])
    
    style = app.style()
    pixmap = QPixmap(QSize(32, 32))
    
    # Map QMessageBox icon types to QStyle.StandardPixmap
    if icon_type == QMessageBox.Information:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
    elif icon_type == QMessageBox.Warning:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
    elif icon_type == QMessageBox.Critical:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
    elif icon_type == QMessageBox.Question:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
    else:
        return QPixmap() # Return empty pixmap for NoIcon

    # Render the icon to a pixmap of the desired size
    return icon.pixmap(pixmap.size())


class CustomMessageBox(CustomThemedDialog):
    def __init__(self, parent=None, title="Message", text="", icon_type=QMessageBox.NoIcon, buttons=QMessageBox.Ok, app_icon_path=None):
        super().__init__(parent, title)

        # We don't want the dialog itself to be minimized, only its parent window
        # So we override the minimize button to close the dialog instead
        self.title_bar.minimize_button.clicked.disconnect()
        self.title_bar.minimize_button.clicked.connect(self.close)
        self.title_bar.minimize_button.setText("—") # Change button text to a dash or similar if desired


        self.setWindowTitle(title)
        self.setMinimumWidth(300) # Ensure some minimum width for readability

        # Content for the message box
        message_content_layout = QHBoxLayout()
        message_content_layout.setSpacing(10)

        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32) # Ensure consistent icon size
        self.icon_label.setScaledContents(True)

        if app_icon_path:
            self.set_app_icon(app_icon_path)
        else:
            self.set_icon_type(icon_type)
        
        message_content_layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignVCenter) # Align vertically centered

        # Text
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextFormat(Qt.RichText) # Allow rich text
        message_content_layout.addWidget(self.text_label, alignment=Qt.AlignmentFlag.AlignVCenter) # Align vertically centered

        # Add message content to the dialog's content layout
        self.add_content_layout(message_content_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Push buttons to the right
        self.added_buttons = []
        self.add_buttons(buttons, button_layout)
        button_layout.addStretch() # Center buttons

        self.add_content_layout(button_layout)
        
        self.result = QMessageBox.NoButton # Default result

    def set_icon_type(self, icon_type):
        if icon_type != QMessageBox.NoIcon:
            self.icon_label.setPixmap(_get_standard_icon_pixmap(icon_type))
        else:
            self.icon_label.clear() # Clear any existing pixmap

    def set_app_icon(self, icon_path):
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap)
                return
        self.icon_label.clear() # Clear if path is invalid or pixmap is null

    def add_buttons(self, buttons, layout):
        # This part requires mapping QMessageBox standard buttons to QPushButtons
        # and connecting them to set the dialog's result and accept/reject
        if buttons & QMessageBox.Ok:
            ok_button = QPushButton("OK")
            ok_button.clicked.connect(lambda: self._set_result_and_accept(QMessageBox.Ok))
            layout.addWidget(ok_button)
            self.added_buttons.append(ok_button)
        if buttons & QMessageBox.Cancel:
            cancel_button = QPushButton("Cancel")
            cancel_button.clicked.connect(lambda: self._set_result_and_accept(QMessageBox.Cancel))
            layout.addWidget(cancel_button)
            self.added_buttons.append(cancel_button)
        if buttons & QMessageBox.Yes:
            yes_button = QPushButton("Yes")
            yes_button.clicked.connect(lambda: self._set_result_and_accept(QMessageBox.Yes))
            layout.addWidget(yes_button)
            self.added_buttons.append(yes_button)
        if buttons & QMessageBox.No:
            no_button = QPushButton("No")
            no_button.clicked.connect(lambda: self._set_result_and_accept(QMessageBox.No))
            layout.addWidget(no_button)
            self.added_buttons.append(no_button)
        # Add other buttons as needed

    def _set_result_and_accept(self, result):
        self.result = result
        self.accept()

    def exec(self):
        super().exec()
        return self.result

# Refactor the original show_message_box to use CustomMessageBox
def show_message_box(parent, title, text, icon=QMessageBox.Information, buttons=QMessageBox.Ok, default_button=QMessageBox.Ok, app_icon_path=None):
    """
    Exibe uma caixa de mensagem customizada com configurações comuns.
    """
    msg_box = CustomMessageBox(parent, title, text, icon, buttons, app_icon_path=app_icon_path)
    
    # If a default button is specified, attempt to set focus to it
    for btn in msg_box.added_buttons:
        if (btn.text().lower() == "ok" and default_button == QMessageBox.Ok) or \
           (btn.text().lower() == "yes" and default_button == QMessageBox.Yes) or \
           (btn.text().lower() == "no" and default_button == QMessageBox.No) or \
           (btn.text().lower() == "cancel" and default_button == QMessageBox.Cancel):
            btn.setDefault(True) # Mark as default button
            btn.setFocus()
            break
            
    return msg_box.exec()