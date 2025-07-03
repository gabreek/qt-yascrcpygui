from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
    QLabel, QMessageBox, QTextEdit
)
from PySide6.QtGui import QPixmap, QImage, QIcon, QPalette
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QEvent, QPoint

import os
import shlex
import sys
import subprocess
from PIL import Image # Still need PIL for loading various image formats into QImage

from utils import scrcpy_handler


class CustomSessionTitleBar(QWidget):
    """Barra de título customizada para a janela de sessões, sem botão de fechar."""
    def __init__(self, parent, title_text="Active Scrcpy Sessions"):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QLabel(title_text, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: white; padding-left: 10px; font-weight: bold;")

        layout.addWidget(self.title_label)
        layout.addStretch()


class ScrcpySessionManagerWindow(QWidget):
    # Signal to emit when the window is closed
    windowClosed = Signal()

    def __init__(self, app_config, parent_widget, parent_x, parent_y, parent_width, close_callback=None):
        super().__init__()
        self.app_config = app_config
        self.session_data_map = {}
        self.parent_widget = parent_widget
        self.close_callback = close_callback
        self.setWindowTitle("Active Scrcpy Sessions")
        self.setMinimumSize(300, 400)

        # Set window flags for frameless window
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # For rounded corners and shadows

        self.container_widget = QWidget()
        self.container_widget.setObjectName("container_widget")

        main_layout = QVBoxLayout(self.container_widget)
        main_layout.setContentsMargins(0, 0, 0, 0) # Remove margins for frameless window
        main_layout.setSpacing(0)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(self.container_widget)

        self.title_bar = CustomSessionTitleBar(self, title_text="Active Scrcpy Sessions")
        main_layout.addWidget(self.title_bar)

        # Content widget to hold the tree and buttons, with proper margins
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(5)

        # Treeview for sessions
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True) # Only show the tree column
        self.tree.setColumnCount(1)
        self.tree.setIndentation(0) # Remove indentation for cleaner look
        self.tree.setStyleSheet("QTreeWidget::item { height: 32px; }") # Set row height
        content_layout.addWidget(self.tree)

        # Bottom command buttons
        command_layout = QHBoxLayout()
        self.terminate_button = QPushButton("Kill")
        self.terminate_button.setEnabled(False)
        self.terminate_button.setFixedSize(100, 30) # Fixed size for consistency

        self.command_button = QPushButton("Check Command")
        self.command_button.setEnabled(False)
        self.command_button.setFixedSize(120, 30) # Fixed size for consistency

        command_layout.addStretch() # Left stretch
        command_layout.addWidget(self.terminate_button)
        command_layout.addWidget(self.command_button)
        command_layout.addStretch() # Right stretch

        content_layout.addLayout(command_layout)

        main_layout.addWidget(content_widget)

        self._setup_ui() # This method is now redundant, but keeping for now
        self._connect_signals()
        self._position_window(parent_x, parent_y, parent_width)

        # Load default icons before first population
        self.default_icon_pixmap = self._load_icon("gui/placeholder.png")
        self.winlator_icon_pixmap = self._load_icon("gui/winlator_placeholder.png")

        # Start auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.populate_sessions)
        self.refresh_timer.start(5000) # Refresh every 5 seconds

        # Initial population
        self.populate_sessions()

        # Apply theme from parent
        self.setPalette(self.parent_widget.palette())
        self.update_theme()

    def update_theme(self):
        # Get colors from current palette
        main_bg_color = self.palette().color(QPalette.ColorRole.Window).name()
        border_color = self.palette().color(QPalette.ColorRole.Mid).name()
        text_color = self.palette().color(QPalette.ColorRole.WindowText).name()
        button_bg_color = self.palette().color(QPalette.ColorRole.Button).name()
        button_text_color = self.palette().color(QPalette.ColorRole.ButtonText).name()
        button_hover_color = self.palette().color(QPalette.ColorRole.AlternateBase).name()
        button_pressed_color = self.palette().color(QPalette.ColorRole.Mid).name()
        tree_bg_color = self.palette().color(QPalette.ColorRole.Base).name()
        tree_item_selected_bg = self.palette().color(QPalette.ColorRole.Highlight).name()

        style = f"""
            #container_widget {{
                background-color: {main_bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QDialog {{
                background-color: transparent;
            }}
            QLabel {{
                color: {text_color};
            }}
            QPushButton {{
                background-color: {button_bg_color};
                color: {button_text_color};
                border: 1px solid {border_color};
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {button_hover_color};
            }}
            QPushButton:pressed {{
                background-color: {button_pressed_color};
            }}
            QTreeWidget {{
                background-color: {tree_bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 5px;
            }}
            QTreeWidget::item:selected {{
                background-color: {tree_item_selected_bg};
            }}
        """
        self.setStyleSheet(style)

        # Update title bar style
        title_bar_style = f"color: {text_color}; padding-left: 10px; font-weight: bold;"
        self.title_bar.title_label.setStyleSheet(title_bar_style)


    def _load_icon(self, relative_path):
        # Determine the base path for resources
        if getattr(sys, 'frozen', False):
            # Running in a PyInstaller bundle
            base_path = sys._MEIPASS
        else:
            # Running in a normal Python environment
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        full_path = os.path.join(base_path, relative_path)

        try:
            # Use PIL to open and resize, then convert to QPixmap
            img = Image.open(full_path).resize((32, 32), Image.LANCZOS)
            qimage = QImage(img.tobytes(), img.width, img.height, QImage.Format_RGBA8888)
            return QPixmap.fromImage(qimage)
        except Exception as e:
            if not isinstance(e, FileNotFoundError):
                print(f"Error loading icon {full_path}: {e}")
            return None

    def _setup_ui(self):
        # This method is now mostly handled in __init__
        pass

    def _connect_signals(self):
        self.tree.itemSelectionChanged.connect(self._on_tree_select)
        self.tree.itemDoubleClicked.connect(self._focus_selected_session_window)
        self.terminate_button.clicked.connect(self._terminate_selected_session)
        self.command_button.clicked.connect(self._show_command_for_selected_session)
        self.parent_widget.installEventFilter(self) # Install event filter on parent for position tracking

    def eventFilter(self, obj, event):
        # Track parent widget's move and resize events
        if obj == self.parent_widget and (event.type() == QEvent.Type.Move or event.type() == QEvent.Type.Resize):
            self._position_window(self.parent_widget.x(), self.parent_widget.y(), self.parent_widget.width())
        return super().eventFilter(obj, event)

    def _position_window(self, parent_x, parent_y, parent_width):
        # Position the window to the right of the parent
        pos_x = parent_x + parent_width
        pos_y = parent_y
        self.move(pos_x, pos_y)

    def _on_tree_select(self):
        selected_items = self.tree.selectedItems()
        if selected_items:
            self.terminate_button.setEnabled(True)
            self.command_button.setEnabled(True)
        else:
            self.terminate_button.setEnabled(False)
            self.command_button.setEnabled(False)

    def _focus_selected_session_window(self, item):
        """Brings the selected scrcpy window to the foreground using wmctrl."""
        pid = item.data(0, Qt.UserRole)
        session_data = self.session_data_map.get(pid)
        if not session_data:
            return

        window_title = session_data.get('app_name')
        if not window_title:
            return

        try:
            # Use wmctrl to activate the window by its title
            cmd = ['wmctrl', '-a', window_title]
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                # Check if wmctrl is installed
                if "No command 'wmctrl' found" in result.stderr or "not found" in result.stderr:
                    print("Error: 'wmctrl' is not installed. Please install it to use this feature (e.g., 'sudo apt-get install wmctrl').")
                else:
                    print(f"wmctrl error: Could not activate window '{window_title}'.\n{result.stderr}")
        except FileNotFoundError:
            print("Error: 'wmctrl' is not installed. Please install it to use this feature (e.g., 'sudo apt-get install wmctrl').")
        except Exception as e:
            print(f"An error occurred while trying to focus the window: {e}")

    def populate_sessions(self):
        current_selection_id = None
        if self.tree.selectedItems():
            current_selection_id = self.tree.selectedItems()[0].data(0, Qt.UserRole) # Get PID from UserRole

        self.tree.clear()
        self.session_data_map.clear()

        sessions = scrcpy_handler.get_active_scrcpy_sessions()

        if not sessions:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, "No active Scrcpy sessions.")
            self.tree.addTopLevelItem(item)
            self.tree.clearSelection()
            self._on_tree_select() # Update button states
            return

        reselect_item = None
        for session in sessions:
            icon_pixmap = None
            if session.get('icon_path'):
                icon_pixmap = self._load_icon(session['icon_path'])

            if icon_pixmap is None:
                if session.get('session_type') == 'winlator':
                    icon_pixmap = self.winlator_icon_pixmap
                else:
                    icon_pixmap = self.default_icon_pixmap

            item = QTreeWidgetItem(self.tree)
            item.setText(0, session['app_name'])
            item.setIcon(0, QIcon(icon_pixmap))
            item.setData(0, Qt.UserRole, session['pid']) # Store PID in UserRole
            self.tree.addTopLevelItem(item)
            self.session_data_map[session['pid']] = session

            if str(session['pid']) == str(current_selection_id):
                reselect_item = item

        if reselect_item:
            reselect_item.setSelected(True)
            self.tree.setCurrentItem(reselect_item)
        elif self.tree.topLevelItemCount() > 0:
            # Select the first item if no previous selection or previous selection is gone
            first_item = self.tree.topLevelItem(0)
            first_item.setSelected(True)
            self.tree.setCurrentItem(first_item)

        self._on_tree_select() # Update button states after populating

    def _terminate_selected_session(self):
        selected_items = self.tree.selectedItems()
        if not selected_items: return

        selected_item = selected_items[0]
        pid = selected_item.data(0, Qt.UserRole)
        session_data = self.session_data_map.get(pid)
        if not session_data: return

        app_name = session_data['app_name']

        reply = QMessageBox.question(self.parent_widget, "Confirm Termination",
                                     f"Are you sure you want to terminate {app_name} (PID: {pid})?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            if scrcpy_handler.kill_scrcpy_session(pid):
                QMessageBox.information(self.parent_widget, "Success", f"Scrcpy session for {app_name} terminated.")
            else:
                QMessageBox.critical(self.parent_widget, "Error", f"Could not terminate Scrcpy session for {app_name} (PID: {pid}).")
            self.populate_sessions() # Refresh the list after terminating

    def _show_command_for_selected_session(self):
        selected_items = self.tree.selectedItems()
        if not selected_items: return

        selected_item = selected_items[0]
        pid = selected_item.data(0, Qt.UserRole)
        session_data = self.session_data_map.get(pid)
        if not session_data: return

        command_args = session_data.get('command_args', ["N/A"])
        command_str = shlex.join(command_args)

        command_dialog = QDialog(self)
        command_dialog.setWindowTitle(f"Command for {session_data['app_name']}")
        command_dialog.setFixedSize(600, 200)
        command_dialog.setWindowModality(Qt.ApplicationModal) # Make it modal

        layout = QVBoxLayout(command_dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(command_str)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        close_button = QPushButton("Close")
        close_button.clicked.connect(command_dialog.accept)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)

        command_dialog.exec()

    def closeEvent(self, event):
        # Stop the refresh timer when the window is closed
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
        
        # Uninstall event filter from parent
        self.parent_widget.removeEventFilter(self)

        if self.close_callback:
            self.close_callback()
        self.windowClosed.emit() # Emit signal
        super().closeEvent(event)