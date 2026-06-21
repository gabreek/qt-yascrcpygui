import os
from PySide6.QtWidgets import (QHBoxLayout, QLineEdit,
                               QPushButton, QListWidget, QListWidgetItem,
                               QCheckBox, QLabel, QWidget, QMessageBox)
from PySide6.QtCore import Qt

from .common_widgets import CustomThemedDialog

class CreateSessionDialog(CustomThemedDialog):
    def __init__(self, app_config, all_apps, parent=None, session_name=None, selected_apps=None):
        title = app_config.tr('apps_tab', 'create_session_title') if not session_name else app_config.tr('apps_tab', 'edit_session_title')
        super().__init__(parent, title=title)
        self.app_config = app_config
        self.all_apps = all_apps # List of {'key': pkg, 'name': name, 'icon_path': url}
        self.setMinimumSize(400, 450)

        # Session Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(self.app_config.tr('apps_tab', 'session_name_placeholder'))
        if session_name:
            self.name_input.setText(session_name)
        
        self.add_content_widget(QLabel(self.app_config.tr('apps_tab', 'session_name_label')))
        self.add_content_widget(self.name_input)

        # App List with checkboxes
        self.add_content_widget(QLabel(self.app_config.tr('apps_tab', 'select_apps_label')))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setObjectName("session_app_list")
        
        selected_pkgs = set(selected_apps) if selected_apps else set()

        # Filter out launcher shortcut if it exists in all_apps
        apps_to_show = [app for app in all_apps if not app.get('is_launcher_shortcut')]
        # Sort by name
        apps_to_show.sort(key=lambda x: x['name'].lower())

        for app in apps_to_show:
            item = QListWidgetItem(self.list_widget)
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(10, 5, 10, 5)
            
            checkbox = QCheckBox(app['name'])
            checkbox.setProperty('pkg_name', app['key'])
            if app['key'] in selected_pkgs:
                checkbox.setChecked(True)
            
            item_layout.addWidget(checkbox)
            item_layout.addStretch()
            
            item.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)

        self.add_content_widget(self.list_widget)

        # Buttons
        btns = QHBoxLayout()
        self.save_btn = QPushButton(self.app_config.tr('common', 'ok'))
        self.cancel_btn = QPushButton(self.app_config.tr('common', 'cancel'))
        btns.addStretch()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        self.add_content_layout(btns)

        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def accept(self):
        self.session_name, self.selected_apps = self.get_data()
        super().accept()

    def get_data(self):
        selected_pkgs = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox.isChecked():
                selected_pkgs.append(checkbox.property('pkg_name'))
        
        return self.name_input.text().strip(), selected_pkgs

class FoldersManagerDialog(CustomThemedDialog):
    def __init__(self, app_config, apps_tab, parent=None):
        super().__init__(parent, title=app_config.tr('apps_tab', 'folders_manager_title'))
        self.app_config = app_config
        self.apps_tab = apps_tab
        self.setMinimumSize(400, 350)

        # Folders List
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("folders_list")
        self.add_content_widget(self.list_widget)

        self.load_folders()

        # Action Buttons
        actions = QHBoxLayout()
        self.create_btn = QPushButton(self.app_config.tr('apps_tab', 'create_session_btn'))
        self.close_btn = QPushButton(self.app_config.tr('common', 'close'))
        
        actions.addWidget(self.create_btn)
        actions.addStretch()
        actions.addWidget(self.close_btn)
        self.add_content_layout(actions)

        self.create_btn.clicked.connect(self.on_create_clicked)
        self.close_btn.clicked.connect(self.accept)

    def load_folders(self):
        self.list_widget.clear()
        
        # Get custom sessions and their order
        custom_sessions = self.app_config.get_custom_sessions()
        order = self.app_config.get_custom_sessions_order()
        
        # Exclude 'all' as it is a reserved system section
        existing_folders = set(k for k in custom_sessions.keys() if k != 'all')
        sorted_folders = [f for f in order if f in existing_folders]
        remaining_folders = sorted(list(existing_folders - set(sorted_folders)), key=lambda x: x.lower())
        
        for folder in (sorted_folders + remaining_folders):
            self.add_folder_item(folder, folder, is_system=False)

    def add_folder_item(self, folder_id, display_name, is_system=False):
        item = QListWidgetItem(self.list_widget)
        item_widget = QWidget()
        layout = QHBoxLayout(item_widget)
        layout.setContentsMargins(10, 5, 10, 5)

        name_label = QLabel(display_name)
        layout.addWidget(name_label)
        layout.addStretch()

        # Move Up/Down buttons
        btn_up = QPushButton("↑")
        btn_up.setFixedSize(30, 30)
        btn_up.clicked.connect(lambda: self.move_item(item, -1))
        
        btn_down = QPushButton("↓")
        btn_down.setFixedSize(30, 30)
        btn_down.clicked.connect(lambda: self.move_item(item, 1))

        layout.addWidget(btn_up)
        layout.addWidget(btn_down)

        if not is_system:
            btn_edit = QPushButton("✎")
            btn_edit.setFixedSize(30, 30)
            btn_edit.clicked.connect(lambda: self.on_edit_clicked(folder_id))
            
            btn_delete = QPushButton("✕")
            btn_delete.setFixedSize(30, 30)
            btn_delete.clicked.connect(lambda: self.on_delete_clicked(folder_id))
            
            layout.addWidget(btn_edit)
            layout.addWidget(btn_delete)

        item.setData(Qt.UserRole, folder_id)
        item.setSizeHint(item_widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, item_widget)

    def move_item(self, item, direction):
        row = self.list_widget.row(item)
        new_row = row + direction
        if 0 <= new_row < self.list_widget.count():
            item_to_move = self.list_widget.takeItem(row)
            self.list_widget.insertItem(new_row, item_to_move)
            self.list_widget.setItemWidget(item_to_move, self.list_widget.itemWidget(item)) # Re-set widget? No, takeItem removes widget.
            # Need to re-create the widget or re-add properly.
            self.load_folders_from_current_order() # Simple way: rebuild list based on UI order
            self.save_order()

    def load_folders_from_current_order(self):
        # This is a bit complex due to widgets. Let's just swap in the data model.
        pass

    def move_item(self, item, delta):
        row = self.list_widget.row(item)
        new_row = row + delta
        # Only allow moving within the custom folders range
        if 0 <= new_row < self.list_widget.count():
            # Get current order from IDs
            current_order = []
            for i in range(self.list_widget.count()):
                current_order.append(self.list_widget.item(i).data(Qt.UserRole))
            
            # Swap
            current_order[row], current_order[new_row] = current_order[new_row], current_order[row]
            
            # Save and refresh
            self.app_config.save_custom_sessions_order(current_order)
            self.load_folders()
            self.apps_tab.filter_apps()

    def save_order(self):
        order = []
        for i in range(self.list_widget.count()):
            order.append(self.list_widget.item(i).data(Qt.UserRole))
        self.app_config.save_custom_sessions_order(order)
        self.apps_tab.filter_apps()

    def on_create_clicked(self):
        dialog = CreateSessionDialog(self.app_config, self.apps_tab.all_apps_data, self)
        if dialog.exec():
            name = dialog.session_name
            apps = dialog.selected_apps
            if not name or name == 'all': return
            self.app_config.save_custom_session(name)
            for pkg in apps:
                self.app_config.save_app_metadata(pkg, {'pinned': name})
            self.load_folders()
            self.save_order()
            self.apps_tab._update_folder_list_in_qml()

    def on_edit_clicked(self, folder_id):
        selected_apps = []
        for app in self.apps_tab.all_apps_data:
            metadata = self.app_config.get_app_metadata(app['key'])
            if metadata.get('pinned') == folder_id:
                selected_apps.append(app['key'])
        
        dialog = CreateSessionDialog(self.app_config, self.apps_tab.all_apps_data, self, session_name=folder_id, selected_apps=selected_apps)
        if dialog.exec():
            new_name = dialog.session_name
            new_apps = dialog.selected_apps
            if not new_name or new_name == 'all': return
            
            if new_name != folder_id:
                self.app_config.delete_custom_session(folder_id)
                self.app_config.save_custom_session(new_name)
                for pkg in new_apps:
                    self.app_config.save_app_metadata(pkg, {'pinned': new_name})
            else:
                for pkg_id in selected_apps:
                    self.app_config.save_app_metadata(pkg_id, {'pinned': False})
                for pkg_id in new_apps:
                    self.app_config.save_app_metadata(pkg_id, {'pinned': folder_id})
            
            self.load_folders()
            self.save_order()
            self.apps_tab._update_folder_list_in_qml()

    def on_delete_clicked(self, folder_id):
        confirm = QMessageBox.question(self, self.app_config.tr('common', 'confirm'), 
                                       self.app_config.tr('apps_tab', 'delete_session_confirm', name=folder_id))
        if confirm == QMessageBox.Yes:
            self.app_config.delete_custom_session(folder_id)
            self.load_folders()
            self.save_order()
