# FILE: gui/scrcpy_tab.py
# PURPOSE: Cria e gerencia a aba de controle do Scrcpy com PySide6.
# VERSION: 3.0 (Configuration Profiles)

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                               QLineEdit, QCheckBox, QSlider, QGroupBox, QMessageBox,
                               QScrollArea, QSizePolicy, QPushButton, QGridLayout)
from PySide6.QtCore import Qt, QThreadPool, Signal

from .workers import DeviceInfoWorker, EncoderListWorker
from . import themes

# --- Custom Widgets to Ignore Scroll Wheel ---
class NoScrollQComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()

class NoScrollQSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()

# --- Constants ---
CODEC_AUTO = "Auto"
DEVICE_NOT_FOUND = "no_device"
PROFILE_ROLE = Qt.UserRole + 1

class ScrcpyTab(QWidget):
    config_updated_on_worker = Signal()
    theme_changed = Signal(str)

    def __init__(self, app_config):
        super().__init__()
        self.app_config = app_config
        self.video_encoders = {}
        self.audio_encoders = {}
        self.last_device_info = {}

        self.general_editors = {}
        self.option_checkboxes = {}
        self.sliders = {}

        self.thread_pool = QThreadPool.globalInstance()
        self.active_workers = []

        self._setup_ui()
        self.update_profile_dropdown()
        self._update_theme_dropdown()

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
        self.yascrcpy_group, layout = self._create_group_box("yaScrcpy")
        
        row_layout = QHBoxLayout()
        label = QLabel("Theme")
        label.setMinimumWidth(100)
        row_layout.addWidget(label)

        self.theme_combo = NoScrollQComboBox()
        self.theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        
        row_layout.addWidget(self.theme_combo)
        layout.addLayout(row_layout)

    def _update_theme_dropdown(self):
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        available_themes = themes.get_available_themes()
        self.theme_combo.addItems(available_themes)
        
        current_theme = self.app_config.get('theme', 'System')
        index = self.theme_combo.findText(current_theme)
        if index != -1:
            self.theme_combo.setCurrentIndex(index)
            
        self.theme_combo.blockSignals(False)

    def _on_theme_selected(self, index):
        if index == -1: return
        theme_name = self.theme_combo.itemText(index)
        self.app_config.set('theme', theme_name)
        self.theme_changed.emit(theme_name)

    def _create_device_status_group(self):
        self.device_info_group, layout = self._create_group_box("Device Status")
        self.device_info_label = QLabel("Checking device status...")
        self.device_info_label.setWordWrap(True)
        layout.addWidget(self.device_info_label)

    def _create_profile_group(self):
        self.profile_group, layout = self._create_group_box("Configuration Profile")
        self.profile_combo = NoScrollQComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        layout.addWidget(self.profile_combo)

    def update_profile_dropdown(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()

        # Add Global Config
        self.profile_combo.addItem("Global Config", userData="global")

        # Add App Configs
        app_configs = self.app_config.get_app_config_keys()
        if app_configs:
            self.profile_combo.insertSeparator(self.profile_combo.count())
            for key, name in app_configs:
                self.profile_combo.addItem(f"{name} (App)", userData=key)

        # Add Winlator Configs
        winlator_configs = self.app_config.get_winlator_config_keys()
        if winlator_configs:
            self.profile_combo.insertSeparator(self.profile_combo.count())
            for key, name in winlator_configs:
                self.profile_combo.addItem(f"{name} (Winlator)", userData=key)

        # Set current item
        active_profile = self.app_config.active_profile
        index = self.profile_combo.findData(active_profile)
        if index != -1:
            self.profile_combo.setCurrentIndex(index)

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
        self.general_settings_group, layout = self._create_group_box("General Settings")

        fields = [
            ("Window Mode", 'windowing_mode', ["Fullscreen", "Freeform"]),
            ("Mouse Mode", 'mouse_mode', ["sdk","uhid","aoa"]),
            ("Gamepad Mode", 'gamepad_mode', ["disabled","uhid","aoa"]),
            ("Keyboard Mode", 'keyboard_mode', ["disabled","sdk","uhid","aoa"]),
            ("Mouse Bind", 'mouse_bind', ["bhsn:++++","++++:bhsn"]),
            ("Max FPS", 'max_fps', ["20","25","30", "45", "60"]),
            ("Virtual Display", 'new_display', ["Disabled", "640x360/120", "854x480/120", "960x550/120", "1280x720/140", "1366x768/140", "1920x1080/140"]),
            ("Max Size", 'max_size', ["0", "640", "854", "960","1280","1366","1080"]),
            ("Extra Args", 'extraargs', None),
        ]
        self.resolution_combo = None
        for label_text, var_key, opts in fields:
            row_layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setMinimumWidth(100)
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

        alt_launch_checkbox = self.option_checkboxes.get('alternate_launch_method')
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
        self.video_settings_group, layout = self._create_group_box("Video Settings")
        self.v_codec_combo = NoScrollQComboBox()
        self.v_codec_combo.currentTextChanged.connect(self._on_video_codec_changed)
        self.v_encoder_combo = NoScrollQComboBox()
        self.v_encoder_combo.currentTextChanged.connect(lambda text: self.app_config.set('video_encoder', text))


        codec_layout = QHBoxLayout()
        codec_label = QLabel("Codec")
        codec_label.setMinimumWidth(100)
        codec_layout.addWidget(codec_label)
        self.v_codec_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.v_codec_combo.setMaximumWidth(300)
        codec_layout.addWidget(self.v_codec_combo)
        layout.addLayout(codec_layout)

        encoder_layout = QHBoxLayout()
        encoder_label = QLabel("Encoder")
        encoder_label.setMinimumWidth(100)
        encoder_layout.addWidget(encoder_label)
        self.v_encoder_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.v_encoder_combo.setMaximumWidth(300)
        encoder_layout.addWidget(self.v_encoder_combo)
        layout.addLayout(encoder_layout)

        self._add_combo_box_row(layout, "Render Driver", 'render_driver', ["opengles2", "opengles", "opengl", "direct3d", "metal", "software"])
        self._add_combo_box_row(layout, "Frame Drop", 'allow_frame_drop', ["Enabled", "Disabled"])
        self._add_combo_box_row(layout, "Low Latency", 'low_latency', ["Enabled", "Disabled"])
        self._add_combo_box_row(layout, "Priority", 'priority_mode', ["Realtime", "Normal"])
        self._add_combo_box_row(layout, "Bitrate Mode", 'bitrate_mode', ["CBR", "VBR"])

        self._create_slider(layout, "Video Buffer", 'video_buffer', 0, 500, 1, "ms")
        self._create_slider_with_buttons(layout, "Video Bitrate", 'video_bitrate_slider', 10, 8000, 10, "K", [1000, 2000, 4000, 6000, 8000])

    def _create_audio_settings_group(self):
        self.audio_settings_group, layout = self._create_group_box("Audio Settings")
        self.a_codec_combo = NoScrollQComboBox()
        self.a_codec_combo.currentTextChanged.connect(self._on_audio_codec_changed)
        self.a_encoder_combo = NoScrollQComboBox()
        self.a_encoder_combo.currentTextChanged.connect(lambda text: self.app_config.set('audio_encoder', text))

        codec_layout = QHBoxLayout()
        codec_label = QLabel("Codec")
        codec_label.setMinimumWidth(100)
        codec_layout.addWidget(codec_label)
        self.a_codec_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.a_codec_combo.setMaximumWidth(300)
        codec_layout.addWidget(self.a_codec_combo)
        layout.addLayout(codec_layout)

        encoder_layout = QHBoxLayout()
        encoder_label = QLabel("Encoder")
        encoder_label.setMinimumWidth(100)
        encoder_layout.addWidget(encoder_label)
        self.a_encoder_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.a_encoder_combo.setMaximumWidth(300)
        encoder_layout.addWidget(self.a_encoder_combo)
        layout.addLayout(encoder_layout)

        self._create_slider(layout, "Audio Buffer", 'audio_buffer', 5, 500, 1, "ms")

    def _create_options_group(self):
        self.options_group, layout = self._create_group_box("Options", QGridLayout)
        config_checkboxes = [
            ("Fullscreen", 'fullscreen'), ("Turn screen off", 'turn_screen_off'),
            ("Stay Awake", 'stay_awake'), ("Disable mipmaps", 'mipmaps'),
            ("No Audio", 'no_audio'), ("No Video", 'no_video'),
            ("Unlock device", 'try_unlock'),
            ("Alternate Launch Method", 'alternate_launch_method'),
        ]
        for i, (text, var_key) in enumerate(config_checkboxes):
            checkbox = QCheckBox(text)
            checkbox.setChecked(self.app_config.get(var_key, False))
            checkbox.stateChanged.connect(lambda state, vk=var_key: self.app_config.set(vk, bool(state)))

            if var_key == 'alternate_launch_method':
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
            button.setStyleSheet("font-size: 10px;")
            button_layout.addWidget(button)
        parent_layout.addLayout(button_layout)
        self.sliders[var_key] = (slider, value_label)

    def refresh_device_info(self, force_encoder_fetch=False):
        self.update_profile_dropdown()
        device_id = self.app_config.get_connection_id()
        if device_id == DEVICE_NOT_FOUND or device_id is None:
            self.device_info_label.setText("Please connect a device.")
            self._load_encoders_from_cache()
            self._set_all_widgets_enabled(False)
            return

        self._set_all_widgets_enabled(True)
        commercial_name = self.app_config.get('device_commercial_name', 'Unknown Device')
        self.device_info_label.setText(f"Connected to {commercial_name} (Battery: ?%)" if commercial_name != 'Unknown Device' else "Fetching device info...")

        worker = DeviceInfoWorker(device_id)
        worker.signals.result.connect(lambda info: self.on_device_info_ready(info, force_encoder_fetch))
        worker.signals.error.connect(self.on_device_info_error)
        self._start_worker(worker)

    def on_device_info_ready(self, info, force_encoder_fetch):
        self.last_device_info = info
        commercial_name = info.get("commercial_name", "Unknown Device")
        if self.app_config.values.get('device_commercial_name') == 'Unknown Device':
            self.app_config.values['device_commercial_name'] = commercial_name
            self.app_config.save_config()

        if default_launcher := info.get('default_launcher'):
            self.app_config.set('default_launcher', default_launcher)

        self.device_info_label.setText(f"Connected to {commercial_name} (Battery: {info.get('battery', '?')}%)")

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
        self.device_info_label.setText("Fetching encoders...")
        worker = EncoderListWorker()
        worker.signals.result.connect(self._on_encoders_ready)
        worker.signals.error.connect(lambda err: QMessageBox.critical(self, "Error", f"Could not fetch encoders: {err}"))
        self._start_worker(worker)

    def _on_encoders_ready(self, result):
        self.video_encoders, self.audio_encoders = result
        self.app_config.save_encoder_cache(self.video_encoders, self.audio_encoders)
        self._populate_encoder_widgets()
        if self.last_device_info:
            commercial_name = self.last_device_info.get("commercial_name", "Unknown Device")
            self.device_info_label.setText(f"Connected to {commercial_name} (Battery: {self.last_device_info.get('battery', '?')}%)")

    def _load_encoders_from_cache(self):
        cached_data = self.app_config.get_encoder_cache()
        self.video_encoders = cached_data.get('video', {})
        self.audio_encoders = cached_data.get('audio', {})
        self._populate_encoder_widgets()

    def _populate_encoder_widgets(self):
        self._update_combo_box(self.v_codec_combo, self._build_codec_options(self.video_encoders), self.app_config.get('video_codec'))
        self._update_combo_box(self.a_codec_combo, self._build_codec_options(self.audio_encoders), self.app_config.get('audio_codec'))

    def _build_codec_options(self, enc_map):
        opts = [CODEC_AUTO]
        if not isinstance(enc_map, dict): return opts
        for codec, entries in sorted(enc_map.items()):
            modes = sorted(list({m for _, m in entries}))
            for mode in modes:
                opts.append(f"{mode.upper()} - {codec}")
        return opts

    def _on_video_codec_changed(self, text):
        self.app_config.set('video_codec', text)
        self._update_encoder_options(self.v_codec_combo, self.v_encoder_combo, self.video_encoders, 'video_encoder')

    def _on_audio_codec_changed(self, text):
        self.app_config.set('audio_codec', text)
        self._update_encoder_options(self.a_codec_combo, self.a_encoder_combo, self.audio_encoders, 'audio_encoder')

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
        if not encoder_combo.signalsBlocked():
            encoder_combo.currentTextChanged.connect(lambda text: self.app_config.set(config_key, text))

    def _update_all_widgets_from_config(self):
        # Block signals to prevent feedback loops
        for editor in self.general_editors.values(): editor.blockSignals(True)
        for checkbox in self.option_checkboxes.values(): checkbox.blockSignals(True)
        for slider, _ in self.sliders.values(): slider.blockSignals(True)
        self.theme_combo.blockSignals(True)
        self.profile_combo.blockSignals(True)
        self.v_codec_combo.blockSignals(True)
        self.v_encoder_combo.blockSignals(True)
        self.a_codec_combo.blockSignals(True)
        self.a_encoder_combo.blockSignals(True)


        # Update General Settings editors
        for var_key, editor in self.general_editors.items():
            value = self.app_config.get(var_key, "")
            if isinstance(editor, QLineEdit):
                editor.setText(str(value))
            elif isinstance(editor, QComboBox):
                editor.setCurrentText(str(value))

        # Update Checkboxes
        for var_key, checkbox in self.option_checkboxes.items():
            checkbox.setChecked(self.app_config.get(var_key, False))

        # Update Sliders
        for var_key, (slider, value_label) in self.sliders.items():
            value = self.app_config.get(var_key, 0)
            slider.setValue(int(value))
            unit = slider.property('unit')
            value_label.setText(f"{value}{unit}")

        # Update Dropdowns that are not in general_editors
        self._update_theme_dropdown()
        self.update_profile_dropdown()
        
        # Update Video/Audio Codec/Encoder Combos
        self._populate_encoder_widgets()
        
        # Update states based on new values
        self._update_resolution_state()
        self._update_launch_control_widgets_state()

        # --- Unblock all signals ---
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
        groups = [self.yascrcpy_group, self.general_settings_group, self.video_settings_group,
                  self.audio_settings_group, self.options_group, self.device_info_group]
        if include_profile:
            groups.append(self.profile_group)
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