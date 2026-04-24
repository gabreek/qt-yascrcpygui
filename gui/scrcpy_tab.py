# FILE: gui/scrcpy_tab.py
# PURPOSE: Cria e gerencia a aba de controle do Scrcpy com PySide6.
# VERSION: 3.1 (Web Server Config)

from PySide6.QtCore import Qt, QThreadPool, Signal, QRect
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                               QLineEdit, QCheckBox, QSlider, QGroupBox, QMessageBox,
                               QScrollArea, QSizePolicy, QPushButton, QGridLayout, QListView, QScrollBar, QStyle)

from .workers import DeviceInfoWorker, EncoderListWorker, DeviceConfigLoaderWorker
from . import themes
from utils import scrcpy_handler, adb_handler
from utils.constants import *
from .web_server_config_window import WebServerConfigWindow


class NoArrowScrollBar(QScrollBar):
    def subControlRect(self, control, option):
        if control == QStyle.SubControl.SC_ScrollBarAddLine or \
           control == QStyle.SubControl.SC_ScrollBarSubLine:
            return QRect()
        return super().subControlRect(control, option)

class NoScrollQComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        self.setView(view)
        view.setObjectName("combo-dropdown-view")
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        old_scrollbar = view.verticalScrollBar()
        custom_scrollbar = NoArrowScrollBar(view)
        custom_scrollbar.setRange(old_scrollbar.minimum(), old_scrollbar.maximum())
        custom_scrollbar.setValue(old_scrollbar.value())
        custom_scrollbar.setSingleStep(old_scrollbar.singleStep())
        custom_scrollbar.setPageStep(old_scrollbar.pageStep())
        view.setVerticalScrollBar(custom_scrollbar)

    def wheelEvent(self, event):
        event.ignore()

    def showPopup(self):
        super().showPopup()
        popup_widget = self.view().parentWidget()
        if popup_widget:
            combo_global_pos = self.mapToGlobal(self.rect().bottomLeft())
            desired_width = self.width()
            model = self.view().model()
            desired_height = self.height()
            if model.rowCount() > 0:
                single_item_height = self.view().sizeHintForRow(0)
                if single_item_height <= 0:
                    single_item_height = self.fontMetrics().height() + 10
                total_content_height = single_item_height * model.rowCount()
                list_view_vertical_margin = 4
                actual_list_view_height = total_content_height + list_view_vertical_margin
                desired_height = min(actual_list_view_height, 250)
            popup_widget.setGeometry(
                combo_global_pos.x(),
                combo_global_pos.y(),
                desired_width,
                desired_height
            )

class NoScrollQSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()

CODEC_AUTO = "Auto"
DEVICE_NOT_FOUND = "no_device"
PROFILE_ROLE = Qt.UserRole + 1

class ScrcpyTab(QWidget):
    config_updated_on_worker = Signal()
    theme_changed = Signal(str)

    def __init__(self, app_config, main_window=None):
        super().__init__()
        self.app_config = app_config
        self.main_window = main_window
        self.video_encoders = {}
        self.audio_encoders = {}
        self.last_device_info = {}
        self.general_editors = {}
        self.general_labels = {} # Store labels for retranslation
        self.option_checkboxes = {}
        self.sliders = {}
        self.thread_pool = QThreadPool.globalInstance()
        self.active_workers = []
        self._setup_ui()
        self.update_profile_dropdown()
        self._update_theme_dropdown()

    def on_config_reloaded(self):
        print("Reloading GUI config due to external change (in worker thread)...")
        
        device_id = self.app_config.get_connection_id()
        if not device_id or device_id == DEVICE_NOT_FOUND:
            print("No device connected, skipping cache refresh.")
            self._update_all_widgets_from_config() # Still update widgets if device status changed.
            self.update_profile_dropdown()
            return
        
        # Store current profile to restore later
        self._pending_profile_restore_key = self.profile_combo.currentData()

        # Disable UI elements to prevent interaction while loading
        self._set_all_widgets_enabled(False) # Temporarily disable all widgets

        # Launch worker to load config and refresh cache in background
        worker = DeviceConfigLoaderWorker(device_id, self.app_config)
        worker.signals.result.connect(self._on_device_cache_refreshed)
        worker.signals.error.connect(self._on_cache_refresh_error)
        worker.signals.finished.connect(lambda: self._set_all_widgets_enabled(True)) # Re-enable on finish
        self._start_worker(worker)


    def _on_device_cache_refreshed(self, result_data, installed_apps_packages, winlator_shortcuts_on_device):
        print("Device cache refreshed by worker, updating GUI.")
        # DeviceConfigLoaderWorker already populates app_config.device_app_cache
        # So we just need to update the UI
        self.update_profile_dropdown()
        self._update_all_widgets_from_config()

        # Restore profile selection after UI update
        if hasattr(self, '_pending_profile_restore_key') and self._pending_profile_restore_key:
            index = self.profile_combo.findData(self._pending_profile_restore_key)
            if index != -1:
                self.profile_combo.setCurrentIndex(index)
            else:
                self.profile_combo.setCurrentIndex(0) # Default to global if not found
            del self._pending_profile_restore_key
        else:
            self.profile_combo.setCurrentIndex(0) # Default to global

    def _on_cache_refresh_error(self, error_message):
        print(f"ERROR: Cache refresh failed: {error_message}")
        show_message_box(self, "Error", f"Failed to refresh app list: {error_message}", icon=QMessageBox.Critical)
        # Fallback to showing only global config if an error occurs
        self.app_config.device_app_cache['installed_apps'] = set()
        self.app_config.device_app_cache['winlator_shortcuts'] = set()
        self.update_profile_dropdown()
        self._update_all_widgets_from_config()


    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.verticalScrollBar().setSingleStep(15)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.scroll_area)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(scroll_content)
        self._create_yascrcpy_group()
        self._create_device_status_group()
        self._create_profile_group()
        self._create_general_settings_group()
        self._create_video_settings_group()
        self._create_audio_settings_group()
        self._create_options_group()

    def wheelEvent(self, event):
        self.scroll_area.wheelEvent(event)

    def _create_group_box(self, title, layout_class=QVBoxLayout):
        group = QGroupBox(title)
        layout = layout_class(group)
        self.scroll_layout.addWidget(group)
        return group, layout

    def _create_yascrcpy_group(self):
        self.yascrcpy_group, layout = self._create_group_box(self.app_config.tr('scrcpy_tab', 'groups', key='yascrcpy'))
        
        # Theme
        row_theme = QHBoxLayout()
        label_theme = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='theme'))
        label_theme.setMinimumWidth(100)
        row_theme.addWidget(label_theme)
        self.theme_combo = NoScrollQComboBox()
        self.theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        row_theme.addWidget(self.theme_combo)
        layout.addLayout(row_theme)

        # Language
        row_lang = QHBoxLayout()
        label_lang = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='language'))
        label_lang.setMinimumWidth(100)
        row_lang.addWidget(label_lang)
        self.lang_combo = NoScrollQComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Português", "pt")
        current_lang = self.app_config.get(CONF_LANGUAGE, 'en')
        index = self.lang_combo.findData(current_lang)
        if index != -1:
            self.lang_combo.setCurrentIndex(index)
        self.lang_combo.currentIndexChanged.connect(self._on_language_selected)
        row_lang.addWidget(self.lang_combo)
        layout.addLayout(row_lang)

        self.show_system_apps_checkbox = QCheckBox(self.app_config.tr('scrcpy_tab', 'labels', key='show_system_apps'))
        self.show_system_apps_checkbox.setChecked(self.app_config.get(CONF_SHOW_SYSTEM_APPS, False))
        self.show_system_apps_checkbox.stateChanged.connect(self._on_show_system_apps_changed)
        layout.addWidget(self.show_system_apps_checkbox)
        
        # Add Configure Web Server button
        self.web_server_config_button = QPushButton(self.app_config.tr('scrcpy_tab', 'labels', key='web_server'))
        self.web_server_config_button.clicked.connect(self._open_web_server_config)
        layout.addWidget(self.web_server_config_button)

    def retranslate_ui(self):
        """Updates all labels and group titles in the tab."""
        self.yascrcpy_group.setTitle(self.app_config.tr('scrcpy_tab', 'groups', key='yascrcpy'))
        self.device_info_group.setTitle(self.app_config.tr('scrcpy_tab', 'groups', key='device_status'))
        self.profile_group.setTitle(self.app_config.tr('scrcpy_tab', 'groups', key='profile'))
        self.general_settings_group.setTitle(self.app_config.tr('scrcpy_tab', 'groups', key='general'))
        self.video_settings_group.setTitle(self.app_config.tr('scrcpy_tab', 'groups', key='video'))
        self.audio_settings_group.setTitle(self.app_config.tr('scrcpy_tab', 'groups', key='audio'))
        self.options_group.setTitle(self.app_config.tr('scrcpy_tab', 'groups', key='options'))

        self.show_system_apps_checkbox.setText(self.app_config.tr('scrcpy_tab', 'labels', key='show_system_apps'))
        self.web_server_config_button.setText(self.app_config.tr('scrcpy_tab', 'labels', key='web_server'))

        # Update general fields labels
        translations = {
            CONF_WINDOWING_MODE: 'window_mode',
            CONF_MOUSE_MODE: 'mouse_mode',
            CONF_GAMEPAD_MODE: 'gamepad_mode',
            CONF_KEYBOARD_MODE: 'keyboard_mode',
            CONF_MOUSE_BIND: 'mouse_bind',
            CONF_MAX_FPS: 'max_fps',
            CONF_NEW_DISPLAY: 'virtual_display',
            CONF_MAX_SIZE: 'max_size',
            CONF_EXTRAARGS: 'extra_args',
            CONF_IFRAME_INTERVAL: 'iframe_interval',
            CONF_VIDEO_BUFFER: 'video_buffer',
            CONF_VIDEO_BITRATE_SLIDER: 'video_bitrate',
            CONF_AUDIO_BUFFER: 'audio_buffer',
            CONF_AUDIO_BITRATE_SLIDER: 'audio_bitrate',
        }
        for var_key, label_key in translations.items():
            if var_key in self.general_labels:
                self.general_labels[var_key].setText(self.app_config.tr('scrcpy_tab', 'labels', key=label_key))

        # Video/Audio specific labels
        self.v_codec_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='codec'))
        self.v_encoder_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='encoder'))
        self.a_codec_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='codec'))
        self.a_encoder_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='encoder'))

        # Options checkboxes
        opt_trans = {
            CONF_FULLSCREEN: 'fullscreen',
            CONF_TURN_SCREEN_OFF: 'turn_screen_off',
            CONF_STAY_AWAKE: 'stay_awake',
            CONF_MIPMAPS: 'disable_mipmaps',
            CONF_NO_AUDIO: 'no_audio',
            CONF_NO_VIDEO: 'no_video',
            CONF_TRY_UNLOCK: 'unlock_device',
            ALTERNATE_LAUNCH_METHOD: 'alternate_launch',
        }
        for var_key, label_key in opt_trans.items():
            if var_key in self.option_checkboxes:
                self.option_checkboxes[var_key].setText(self.app_config.tr('scrcpy_tab', 'options', key=label_key))

        self._update_all_widgets_from_config() # This already blocks signals
        self.refresh_device_info() # Updates device status label

    def _on_language_selected(self, index):
        if index == -1: return
        lang_code = self.lang_combo.itemData(index)
        self.app_config.set(CONF_LANGUAGE, lang_code)
        if self.main_window:
            self.main_window.retranslate_ui()

    def _open_web_server_config(self):
        if not self.main_window:
            QMessageBox.warning(self, "Error", "Main window reference not available.")
            return

        if self.main_window.web_config_window is None or not self.main_window.web_config_window.isVisible():
            self.main_window.web_config_window = WebServerConfigWindow(self.app_config, self.main_window)
            self.main_window.web_config_window.start_server_requested.connect(self.main_window.start_web_server)
            self.main_window.web_config_window.stop_server_requested.connect(self.main_window.stop_web_server)
            self.main_window.web_server_status_changed.connect(self.main_window.web_config_window.update_status)
        
        self.main_window.web_config_window.show()
        self.main_window.web_config_window.raise_()
        self.main_window.web_config_window.activateWindow()
        self.main_window.web_config_window.update_status(self.main_window.is_web_server_running())

    def _on_show_system_apps_changed(self, state):
        self.app_config.set(CONF_SHOW_SYSTEM_APPS, bool(state))
        self.config_updated_on_worker.emit()

    def _update_theme_dropdown(self):
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        available_themes = themes.get_available_themes()
        self.theme_combo.addItems(available_themes)
        current_theme = self.app_config.get(CONF_THEME, 'System')
        index = self.theme_combo.findText(current_theme)
        if index != -1:
            self.theme_combo.setCurrentIndex(index)
        self.theme_combo.blockSignals(False)

    def _on_theme_selected(self, index):
        if index == -1: return
        theme_name = self.theme_combo.itemText(index)
        self.app_config.set(CONF_THEME, theme_name)
        self.theme_changed.emit(theme_name)

    def _create_device_status_group(self):
        self.device_info_group, layout = self._create_group_box(self.app_config.tr('scrcpy_tab', 'groups', key='device_status'))
        self.device_info_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='checking_status'))
        self.device_info_label.setWordWrap(True)
        layout.addWidget(self.device_info_label)

    def _create_profile_group(self):
        self.profile_group, layout = self._create_group_box(self.app_config.tr('scrcpy_tab', 'groups', key='profile'))
        self.profile_combo = NoScrollQComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        layout.addWidget(self.profile_combo)

    def update_profile_dropdown(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem(self.app_config.tr('scrcpy_tab', 'labels', key='global_config'), userData="global")
        device_id = self.app_config.get_connection_id()
        if device_id == DEVICE_NOT_FOUND or device_id is None:
            active_profile = self.app_config.active_profile
            index = self.profile_combo.findData(active_profile)
            if index != -1:
                self.profile_combo.setCurrentIndex(index)
            self.profile_combo.blockSignals(False)
            return
        installed_apps_packages = self.app_config.device_app_cache.get('installed_apps', set())
        winlator_shortcuts_on_device = self.app_config.device_app_cache.get('winlator_shortcuts', set())
        filtered_app_configs = []
        app_configs_from_settings = self.app_config.get_app_config_keys()
        for key, name in app_configs_from_settings:
            if key in installed_apps_packages:
                filtered_app_configs.append((key, name))
        if filtered_app_configs:
            self.profile_combo.insertSeparator(self.profile_combo.count())
            for key, name in sorted(filtered_app_configs, key=lambda x: x[1].lower()):
                self.profile_combo.addItem(f"{name} (App)", userData=key)
        filtered_winlator_configs = []
        winlator_configs_from_settings = self.app_config.get_winlator_config_keys()
        for key, name in winlator_configs_from_settings:
            if key in winlator_shortcuts_on_device:
                filtered_winlator_configs.append((key, name))
        if filtered_winlator_configs:
            self.profile_combo.insertSeparator(self.profile_combo.count())
            for key, name in sorted(filtered_winlator_configs, key=lambda x: x[1].lower()):
                self.profile_combo.addItem(f"{name} (Winlator)", userData=key)
        active_profile = self.app_config.active_profile
        index = self.profile_combo.findData(active_profile)
        if index != -1:
            self.profile_combo.setCurrentIndex(index)
        else:
            self.app_config.load_profile("global")
            self.profile_combo.setCurrentIndex(0)
            self._update_all_widgets_from_config()
        self.profile_combo.blockSignals(False)

    def _on_profile_selected(self, index):
        if index == -1: return
        profile_key = self.profile_combo.itemData(index)
        self.app_config.load_profile(profile_key)
        self._update_all_widgets_from_config()
        self._update_launch_control_widgets_state()

    def _add_combo_box_row(self, parent_layout, label_text, var_key, options):
        row_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(100)
        row_layout.addWidget(label)
        editor = NoScrollQComboBox()
        editor.addItems(options)
        value = self.app_config.get(var_key, options[0])
        if value in options:
            editor.setCurrentText(str(value))
        editor.currentTextChanged.connect(lambda text, vk=var_key: self.app_config.set(vk, text))
        editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        editor.setMaximumWidth(300)
        row_layout.addWidget(editor)
        row_layout.setStretch(0, 0)
        row_layout.setStretch(1, 1)
        parent_layout.addLayout(row_layout)
        self.general_editors[var_key] = editor

    def _create_general_settings_group(self):
        self.general_settings_group, layout = self._create_group_box(self.app_config.tr('scrcpy_tab', 'groups', key='general'))
        fields = [
            (self.app_config.tr('scrcpy_tab', 'labels', key='window_mode'), CONF_WINDOWING_MODE, ["Fullscreen", "Freeform"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='mouse_mode'), CONF_MOUSE_MODE, ["sdk","uhid","aoa"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='gamepad_mode'), CONF_GAMEPAD_MODE, ["disabled","uhid","aoa"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='keyboard_mode'), CONF_KEYBOARD_MODE, ["disabled","sdk","uhid","aoa"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='mouse_bind'), CONF_MOUSE_BIND, ["bhsn:++++","++++:bhsn"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='max_fps'), CONF_MAX_FPS, ["20","25","30", "45", "60"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='virtual_display'), CONF_NEW_DISPLAY, ["Disabled", "640x360/120", "854x480/120", "960x550/120", "1280x720/140", "1366x768/140", "1920x1080/140"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='max_size'), CONF_MAX_SIZE, ["0", "640", "854", "960","1280","1366","1080"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='extra_args'), CONF_EXTRAARGS, None),
        ]
        self.resolution_combo = None
        for label_text, var_key, opts in fields:
            row_layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setMinimumWidth(100)
            self.general_labels[var_key] = label # Store reference
            row_layout.addWidget(label)
            value = self.app_config.get(var_key, "")
            if opts is None:
                editor = QLineEdit(str(value))
                editor.textChanged.connect(lambda text, vk=var_key: self.app_config.set(vk, text))
            else:
                editor = NoScrollQComboBox()
                editor.addItems(opts)
                if var_key in ['mouse_bind', 'max_fps', 'new_display', 'max_size']:
                    editor.setEditable(True)
                saved_value = self.app_config.get(var_key, opts[0] if opts else "")
                editor.setCurrentText(str(saved_value))
                editor.currentTextChanged.connect(lambda text, vk=var_key: self.app_config.set(vk, text))
                if var_key == 'new_display':
                    editor.currentTextChanged.connect(self._update_resolution_state)
                    editor.currentTextChanged.connect(self._update_launch_control_widgets_state)
                elif var_key == 'max_size':
                    self.resolution_combo = editor
                elif var_key == 'windowing_mode':
                    self.windowing_mode_combo = editor
            editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            editor.setMaximumWidth(300)
            row_layout.addWidget(editor)
            layout.addLayout(row_layout)
            self.general_editors[var_key] = editor
        self._update_resolution_state()
        self._update_launch_control_widgets_state()

    def _update_launch_control_widgets_state(self):
        if not hasattr(self, 'option_checkboxes') or not hasattr(self, 'windowing_mode_combo') or not hasattr(self, 'general_editors'):
            return
        alt_launch_checkbox = self.option_checkboxes.get(ALTERNATE_LAUNCH_METHOD)
        virtual_display_combo = self.general_editors.get('new_display')
        if not alt_launch_checkbox or not virtual_display_combo:
            return
        is_virtual_display_active = virtual_display_combo.currentText() != 'Disabled'
        active_profile_key = self.app_config.active_profile
        is_winlator_profile = active_profile_key in self.app_config.get_winlator_config_keys(include_name=False)
        alt_launch_checkbox.setDisabled(is_winlator_profile or not is_virtual_display_active)
        if is_winlator_profile:
            alt_launch_checkbox.setChecked(True)
        alt_launch_enabled = alt_launch_checkbox.isChecked()
        self.windowing_mode_combo.setEnabled((is_winlator_profile or alt_launch_enabled) and is_virtual_display_active)

    def _create_video_settings_group(self):
        self.video_settings_group, layout = self._create_group_box(self.app_config.tr('scrcpy_tab', 'groups', key='video'))
        self.v_codec_combo = NoScrollQComboBox()
        self.v_codec_combo.currentTextChanged.connect(self._on_video_codec_changed)
        self.v_encoder_combo = NoScrollQComboBox()
        self.v_encoder_combo.currentTextChanged.connect(lambda text: self.app_config.set(CONF_VIDEO_ENCODER, text))
        codec_layout = QHBoxLayout()
        self.v_codec_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='codec'))
        self.v_codec_label.setMinimumWidth(100)
        codec_layout.addWidget(self.v_codec_label)
        self.v_codec_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.v_codec_combo.setMaximumWidth(300)
        codec_layout.addWidget(self.v_codec_combo)
        layout.addLayout(codec_layout)
        encoder_layout = QHBoxLayout()
        self.v_encoder_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='encoder'))
        self.v_encoder_label.setMinimumWidth(100)
        encoder_layout.addWidget(self.v_encoder_label)
        self.v_encoder_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.v_encoder_combo.setMaximumWidth(300)
        encoder_layout.addWidget(self.v_encoder_combo)
        layout.addLayout(encoder_layout)
        self._add_combo_box_row(layout, self.app_config.tr('scrcpy_tab', 'labels', key='render_driver'), CONF_RENDER_DRIVER, ["opengles2", "opengles", "opengl", "direct3d", "metal", "software"])
        self._add_combo_box_row(layout, self.app_config.tr('scrcpy_tab', 'labels', key='color_range'), CONF_COLOR_RANGE, ["Auto", "Full", "Limited"])
        self._add_combo_box_row(layout, self.app_config.tr('scrcpy_tab', 'labels', key='frame_drop'), CONF_ALLOW_FRAME_DROP, ["Enabled", "Disabled"])
        self._add_combo_box_row(layout, self.app_config.tr('scrcpy_tab', 'labels', key='low_latency'), CONF_LOW_LATENCY, ["Enabled", "Disabled"])
        self._add_combo_box_row(layout, self.app_config.tr('scrcpy_tab', 'labels', key='priority'), CONF_PRIORITY_MODE, ["Realtime", "Normal"])
        self._add_combo_box_row(layout, self.app_config.tr('scrcpy_tab', 'labels', key='bitrate_mode'), CONF_BITRATE_MODE, ["Constant", "Variable"])
        self._create_iframe_interval_slider(layout, self.app_config.tr('scrcpy_tab', 'labels', key='iframe_interval'), CONF_IFRAME_INTERVAL, 0, 30, 1, 0) # 0 for Auto, 1-30 seconds
        self._create_slider(layout, self.app_config.tr('scrcpy_tab', 'labels', key='video_buffer'), CONF_VIDEO_BUFFER, 0, 500, 1, "ms")
        self._create_slider_with_buttons(layout, self.app_config.tr('scrcpy_tab', 'labels', key='video_bitrate'), CONF_VIDEO_BITRATE_SLIDER, 10, 8000, 10, "K", [1000, 2000, 4000, 6000, 8000])

    def _create_audio_settings_group(self):
        self.audio_settings_group, layout = self._create_group_box(self.app_config.tr('scrcpy_tab', 'groups', key='audio'))
        self.a_codec_combo = NoScrollQComboBox()
        self.a_codec_combo.currentTextChanged.connect(self._on_audio_codec_changed)
        self.a_encoder_combo = NoScrollQComboBox()
        self.a_encoder_combo.currentTextChanged.connect(lambda text: self.app_config.set(CONF_AUDIO_ENCODER, text))
        codec_layout = QHBoxLayout()
        self.a_codec_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='codec'))
        self.a_codec_label.setMinimumWidth(100)
        codec_layout.addWidget(self.a_codec_label)
        self.a_codec_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.a_codec_combo.setMaximumWidth(300)
        codec_layout.addWidget(self.a_codec_combo)
        layout.addLayout(codec_layout)
        encoder_layout = QHBoxLayout()
        self.a_encoder_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='encoder'))
        self.a_encoder_label.setMinimumWidth(100)
        encoder_layout.addWidget(self.a_encoder_label)
        self.a_encoder_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.a_encoder_combo.setMaximumWidth(300)
        encoder_layout.addWidget(self.a_encoder_combo)
        layout.addLayout(encoder_layout)
        self._create_slider(layout, self.app_config.tr('scrcpy_tab', 'labels', key='audio_buffer'), CONF_AUDIO_BUFFER, 5, 500, 1, "ms")
        self._create_slider(layout, self.app_config.tr('scrcpy_tab', 'labels', key='audio_bitrate'), CONF_AUDIO_BITRATE_SLIDER, 64, 320, 16, "K")

    def _create_options_group(self):
        self.options_group, layout = self._create_group_box(self.app_config.tr('scrcpy_tab', 'groups', key='options'), QGridLayout)
        config_checkboxes = [
            (self.app_config.tr('scrcpy_tab', 'options', key='fullscreen'), CONF_FULLSCREEN),
            (self.app_config.tr('scrcpy_tab', 'options', key='turn_screen_off'), CONF_TURN_SCREEN_OFF),
            (self.app_config.tr('scrcpy_tab', 'options', key='stay_awake'), CONF_STAY_AWAKE),
            (self.app_config.tr('scrcpy_tab', 'options', key='disable_mipmaps'), CONF_MIPMAPS),
            (self.app_config.tr('scrcpy_tab', 'options', key='no_audio'), CONF_NO_AUDIO),
            (self.app_config.tr('scrcpy_tab', 'options', key='no_video'), CONF_NO_VIDEO),
            (self.app_config.tr('scrcpy_tab', 'options', key='unlock_device'), CONF_TRY_UNLOCK),
            (self.app_config.tr('scrcpy_tab', 'options', key='alternate_launch'), ALTERNATE_LAUNCH_METHOD),
        ]
        for i, (text, var_key) in enumerate(config_checkboxes):
            checkbox = QCheckBox(text)
            checkbox.setChecked(self.app_config.get(var_key, False))
            checkbox.stateChanged.connect(lambda state, vk=var_key: self.app_config.set(vk, bool(state)))
            if var_key == ALTERNATE_LAUNCH_METHOD:
                checkbox.stateChanged.connect(self._update_launch_control_widgets_state)
            layout.addWidget(checkbox, i // 2, i % 2)
            self.option_checkboxes[var_key] = checkbox
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    def _setup_slider_common(self, slider, value_label, var_key, unit, min_val):
        slider.valueChanged.connect(lambda value: value_label.setText(f"{value}{unit}"))
        slider.valueChanged.connect(lambda value: self.app_config.set(var_key, value))
        slider.setValue(self.app_config.get(var_key, min_val))
        value_label.setText(f"{self.app_config.get(var_key, min_val)}{unit}")

    def _create_slider(self, parent_layout, label_text, var_key, min_val, max_val, step, unit):
        row_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(100)
        self.general_labels[var_key] = label # Store reference
        row_layout.addWidget(label)
        slider = NoScrollQSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setSingleStep(step)
        slider.setPageStep(step * 10)
        slider.setProperty('unit', unit)
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        value_label = QLabel()
        value_label.setMinimumWidth(50)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(slider)
        row_layout.addWidget(value_label)
        parent_layout.addLayout(row_layout)
        self.sliders[var_key] = (slider, value_label)
        self._setup_slider_common(slider, value_label, var_key, unit, min_val)

    def _create_slider_with_buttons(self, parent_layout, label_text, var_key, min_val, max_val, step, unit, button_values):
        row_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(100)
        self.general_labels[var_key] = label # Store reference
        row_layout.addWidget(label)
        slider = NoScrollQSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setSingleStep(step)
        slider.setPageStep(step * 10)
        slider.setProperty('unit', unit)
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        value_label = QLabel()
        value_label.setMinimumWidth(50)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._setup_slider_common(slider, value_label, var_key, unit, min_val)
        row_layout.addWidget(slider)
        row_layout.addWidget(value_label)
        parent_layout.addLayout(row_layout)
        button_layout = QHBoxLayout()
        for btn_val in button_values:
            button = QPushButton(f"{btn_val}{unit}")
            button.clicked.connect(lambda checked, val=btn_val: slider.setValue(val))
            button.setFixedWidth(50)
            button.setObjectName("scrcpy_bitrate_button")
            button_layout.addWidget(button)
        parent_layout.addLayout(button_layout)
        self.sliders[var_key] = (slider, value_label)

    def _create_iframe_interval_slider(self, parent_layout, label_text, var_key, min_val, max_val, step, default_val):
        row_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(100)
        self.general_labels[var_key] = label # Store reference
        row_layout.addWidget(label)
        slider = NoScrollQSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val) # min_val will be 0 for "Auto"
        slider.setSingleStep(step)
        slider.setPageStep(step * 10)
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        value_label = QLabel()
        value_label.setMinimumWidth(50)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def update_label(value):
            if value == 0:
                value_label.setText("Auto")
            else:
                value_label.setText(f"{value}s")

        slider.valueChanged.connect(update_label)
        slider.valueChanged.connect(lambda value: self.app_config.set(var_key, value)) # Store the raw value (0 for auto)
        
        # Set initial value and update label
        current_value = self.app_config.get(var_key, default_val)
        slider.setValue(int(current_value))
        update_label(int(current_value)) # Initialize label

        row_layout.addWidget(slider)
        row_layout.addWidget(value_label)
        parent_layout.addLayout(row_layout)
        self.sliders[var_key] = (slider, value_label) # Store for update_all_widgets_from_config


    def refresh_device_info(self, force_encoder_fetch=False):
        self.update_profile_dropdown()
        device_id = self.app_config.get_connection_id()
        if device_id == DEVICE_NOT_FOUND or device_id is None:
            self.device_info_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='please_connect'))
            self._load_encoders_from_cache()
            self._set_all_widgets_enabled(False)
            return
        self._set_all_widgets_enabled(True)
        commercial_name = self.app_config.get(CONF_DEVICE_COMMERCIAL_NAME, "Unknown Device")
        self.device_info_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='connected_to', name=commercial_name, battery='?') if commercial_name != 'Unknown Device' else self.app_config.tr('scrcpy_tab', 'labels', key='fetching_info'))
        worker = DeviceInfoWorker(device_id)
        worker.signals.result.connect(lambda info: self.on_device_info_ready(info, force_encoder_fetch))
        worker.signals.error.connect(self.on_device_info_error)
        self._start_worker(worker)

    def on_device_info_ready(self, info, force_encoder_fetch):
        self.last_device_info = info
        commercial_name = info.get("commercial_name", "Unknown Device")
        if self.app_config.values.get(CONF_DEVICE_COMMERCIAL_NAME) == 'Unknown Device':
            self.app_config.values[CONF_DEVICE_COMMERCIAL_NAME] = commercial_name
            self.app_config.save_config()
        if default_launcher := info.get('default_launcher'):
            self.app_config.set(CONF_DEFAULT_LAUNCHER, default_launcher)
        self.device_info_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='connected_to', name=commercial_name, battery=info.get('battery', '?')))
        if force_encoder_fetch or not self.app_config.has_encoder_cache():
            self._fetch_and_update_encoders()
        else:
            self._load_encoders_from_cache()
        self.config_updated_on_worker.emit()

    def on_device_info_error(self, error_msg):
        self.device_info_label.setText(f"Device not connected or ADB error: {error_msg}")
        self._load_encoders_from_cache()

    def _fetch_and_update_encoders(self):
        if self.app_config.get_connection_id() == DEVICE_NOT_FOUND: return
        self.device_info_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='fetching_encoders'))
        worker = EncoderListWorker()
        worker.signals.result.connect(self._on_encoders_ready)
        worker.signals.error.connect(lambda err: show_message_box(self, self.app_config.tr('common', 'error'), self.app_config.tr('scrcpy_tab', 'labels', key='fetch_encoders_error', error=err), icon=QMessageBox.Critical))
        self._start_worker(worker)

    def _on_encoders_ready(self, result):
        self.video_encoders, self.audio_encoders = result
        self.app_config.save_encoder_cache(self.video_encoders, self.audio_encoders)
        self._populate_encoder_widgets()
        if self.last_device_info:
            commercial_name = self.last_device_info.get("commercial_name", "Unknown Device")
            battery = self.last_device_info.get('battery', '?')
            self.device_info_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='connected_to', name=commercial_name, battery=battery))

    def _load_encoders_from_cache(self):
        cached_data = self.app_config.get_encoder_cache()
        self.video_encoders = cached_data.get('video', {})
        self.audio_encoders = cached_data.get('audio', {})
        self._populate_encoder_widgets()

    def _populate_encoder_widgets(self):
        self._update_combo_box(self.v_codec_combo, self._build_codec_options(self.video_encoders), self.app_config.get('video_codec'))
        self._update_encoder_options(self.v_codec_combo, self.v_encoder_combo, self.video_encoders, 'video_encoder')
        self._update_combo_box(self.a_codec_combo, self._build_codec_options(self.audio_encoders), self.app_config.get('audio_codec'))
        self._update_encoder_options(self.a_codec_combo, self.a_encoder_combo, self.audio_encoders, 'audio_encoder')

    def _build_codec_options(self, enc_map):
        opts = [CODEC_AUTO]
        if not isinstance(enc_map, dict): return opts
        for codec, entries in sorted(enc_map.items()):
            modes = sorted(list({m for _, m in entries}))
            for mode in modes:
                opts.append(f"{mode.upper()} - {codec}")
        return opts

    def _on_video_codec_changed(self, text):
        self.app_config.set(CONF_VIDEO_CODEC, text)
        self._update_encoder_options(self.v_codec_combo, self.v_encoder_combo, self.video_encoders, CONF_VIDEO_ENCODER)

    def _on_audio_codec_changed(self, text):
        self.app_config.set(CONF_AUDIO_CODEC, text)
        self._update_encoder_options(self.a_codec_combo, self.a_encoder_combo, self.audio_encoders, CONF_AUDIO_ENCODER)

    def _update_encoder_options(self, codec_combo, encoder_combo, encoder_map, config_key):
        selected_codec = codec_combo.currentText()
        saved_encoder = self.app_config.get(config_key)
        vals = [CODEC_AUTO]
        if selected_codec != CODEC_AUTO and " - " in selected_codec:
            mode, codec = selected_codec.split(" - ")
            if codec in encoder_map:
                encs = [e for e in encoder_map[codec] if e[1] == mode.lower()]
                unique_encs = dict.fromkeys(map(tuple, encs))
                vals.extend(sorted([f"{e} ({m})" for e, m in unique_encs]))
        self._update_combo_box(encoder_combo, vals, saved_encoder)

    def _update_all_widgets_from_config(self):
        for editor in self.general_editors.values(): editor.blockSignals(True)
        for checkbox in self.option_checkboxes.values(): checkbox.blockSignals(True)
        for slider, _ in self.sliders.values(): slider.blockSignals(True)
        self.theme_combo.blockSignals(True)
        self.profile_combo.blockSignals(True)
        self.v_codec_combo.blockSignals(True)
        self.v_encoder_combo.blockSignals(True)
        self.a_codec_combo.blockSignals(True)
        self.a_encoder_combo.blockSignals(True)
        for var_key, editor in self.general_editors.items():
            value = self.app_config.get(var_key, "")
            if isinstance(editor, QLineEdit):
                editor.setText(str(value))
            elif isinstance(editor, QComboBox):
                editor.setCurrentText(str(value))
        for var_key, checkbox in self.option_checkboxes.items():
            checkbox.setChecked(self.app_config.get(var_key, False))
        for var_key, (slider, value_label) in self.sliders.items():
            value = self.app_config.get(var_key, 0)
            slider.setValue(int(value))
            if var_key == 'iframe_interval':
                if value == 0:
                    value_label.setText("Auto")
                else:
                    value_label.setText(f"{value}s")
            else:
                unit = slider.property('unit')
                value_label.setText(f"{value}{unit}")
        self._update_theme_dropdown()
        self.update_profile_dropdown()
        self._populate_encoder_widgets()
        self._update_resolution_state()
        self._update_launch_control_widgets_state()
        for editor in self.general_editors.values(): editor.blockSignals(False)
        for checkbox in self.option_checkboxes.values(): checkbox.blockSignals(False)
        for slider, _ in self.sliders.values(): slider.blockSignals(False)
        self.theme_combo.blockSignals(False)
        self.profile_combo.blockSignals(False)
        self.v_codec_combo.blockSignals(False)
        self.v_encoder_combo.blockSignals(False)
        self.a_codec_combo.blockSignals(False)
        self.a_encoder_combo.blockSignals(False)

    def _update_resolution_state(self):
        if hasattr(self, 'resolution_combo') and self.resolution_combo:
            is_disabled = self.general_editors['new_display'].currentText() != 'Disabled'
            self.resolution_combo.setDisabled(is_disabled)

    def _update_combo_box(self, combo, items, current_value):
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        if current_value in items:
            combo.setCurrentText(current_value)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _set_all_widgets_enabled(self, enabled, include_profile=True):
        # The yascrcpy_group contains non-device-specific settings, so it should not be disabled.
        groups = [self.general_settings_group, self.video_settings_group,
                  self.audio_settings_group, self.options_group, self.device_info_group]
        if include_profile:
            groups.append(self.profile_combo)
        for group in groups:
            if group:
                group.setEnabled(enabled)

    def _start_worker(self, worker):
        self.active_workers.append(worker)
        worker.signals.finished.connect(lambda: self._on_worker_finished(worker))
        self.thread_pool.start(worker)

    def _on_worker_finished(self, worker):
        if worker in self.active_workers:
            self.active_workers.remove(worker)

    def stop_all_workers(self):
        pass

    def set_device_status_message(self, message):
        if message:
            self.device_info_label.setText(message)
            self._set_all_widgets_enabled(False)
        else:
            self.refresh_device_info()