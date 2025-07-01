from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
    QLabel, QMessageBox, QWidget, QTextEdit
)
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QEvent

import os
import shlex
import sys
from PIL import Image # Still need PIL for loading various image formats into QImage

from utils import scrcpy_handler

class ScrcpySessionManagerWindow(QDialog):
    # Signal to emit when the window is closed
    windowClosed = Signal()

    def __init__(self, parent_widget, parent_x, parent_y, parent_width, close_callback=None):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.close_callback = close_callback
        self.setWindowTitle("Active Scrcpy Sessions")
        self.setMinimumSize(300, 400)

        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint) # Keep window on top

        self.default_icon_pixmap = self._load_icon("gui/placeholder.png")
        self.winlator_icon_pixmap = self._load_icon("gui/winlator_placeholder.png")

        self.session_data_map = {}

        self._setup_ui()
        self._connect_signals()
        self._position_window(parent_x, parent_y, parent_width)

        # Start auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.populate_sessions)
        self.refresh_timer.start(5000) # Refresh every 5 seconds

        # Initial population
        self.populate_sessions()

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
            print(f"Error loading icon {full_path}: {e}")
            # Create a blank pixmap if loading fails
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.darkGray)
            return pixmap

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # Treeview for sessions
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True) # Only show the tree column
        self.tree.setColumnCount(1)
        self.tree.setIndentation(0) # Remove indentation for cleaner look
        self.tree.setStyleSheet("QTreeWidget::item { height: 32px; }") # Set row height
        main_layout.addWidget(self.tree)

        # Bottom command buttons
        command_layout = QHBoxLayout()
        self.terminate_button = QPushButton("Terminate")
        self.terminate_button.setEnabled(False)
        self.terminate_button.setFixedSize(100, 30) # Fixed size for consistency

        self.command_button = QPushButton("Command Used")
        self.command_button.setEnabled(False)
        self.command_button.setFixedSize(120, 30) # Fixed size for consistency

        command_layout.addWidget(self.terminate_button)
        command_layout.addWidget(self.command_button)
        command_layout.addStretch() # Pushes buttons to the left

        main_layout.addLayout(command_layout)

    def _connect_signals(self):
        self.tree.itemSelectionChanged.connect(self._on_tree_select)
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
            if session['icon_path'] and os.path.exists(session['icon_path']):
                try:
                    icon_pixmap = self._load_icon(session['icon_path'])
                except Exception as e:
                    print(f"Error loading icon {session['icon_path']}: {e}")
            
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
