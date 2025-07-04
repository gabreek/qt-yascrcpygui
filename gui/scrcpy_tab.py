# FILE: gui/scrcpy_tab.py
# PURPOSE: Cria e gerencia a aba de controle do Scrcpy com PySide6.
# VERSION: 2.3 (Fix for RuntimeError, Config Loading, and Device Name)

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                               QLineEdit, QCheckBox, QSlider, QGroupBox, QMessageBox,
                               QScrollArea, QSizePolicy, QPushButton, QGridLayout)
from PySide6.QtCore import Qt, QThread, QTimer

from .workers import DeviceInfoWorker, EncoderListWorker

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

from PySide6.QtCore import Qt, QThread, Signal

class ScrcpyTab(QWidget):
    config_updated_on_worker = Signal()

    def __init__(self, app_config):
        super().__init__()
        self.app_config = app_config
        self.video_encoders = {}
        self.audio_encoders = {}
        self.last_device_info = {}

        self.general_editors = {}
        self.option_checkboxes = {}
        self.sliders = {}

        self.workers = {
            "device_info": {"worker": None, "thread": None},
            "encoder_list": {"worker": None, "thread": None},
        }

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.scroll_area)

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(scroll_content)

        self._create_device_status_group()
        self._create_general_settings_group()
        self._create_video_settings_group()
        self._create_audio_settings_group()
        self._create_options_group()

    def wheelEvent(self, event):
        # Forward the wheel event to the scroll area
        self.scroll_area.wheelEvent(event)

    def _create_group_box(self, title, layout_class=QVBoxLayout):
        group = QGroupBox(title)
        layout = layout_class(group)
        self.scroll_layout.addWidget(group)
        return group, layout

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
        row_layout.setStretch(0, 0) # Label
        row_layout.setStretch(1, 1) # Editor
        parent_layout.addLayout(row_layout)
        self.general_editors[var_key] = editor

    def _create_device_status_group(self):
        self.device_info_group, layout = self._create_group_box("Device Status")
        self.device_info_label = QLabel("Checking device status...")
        self.device_info_label.setWordWrap(True)
        layout.addWidget(self.device_info_label)

    def _create_general_settings_group(self):
        self.general_settings_group, layout = self._create_group_box("General Settings")
        fields = [
            ("Mouse Mode", 'mouse_mode', ["sdk","uhid","aoa"]),
            ("Gamepad Mode", 'gamepad_mode', ["disabled","uhid","aoa"]),
            ("Keyboard Mode", 'keyboard_mode', ["disabled","sdk","uhid","aoa"]),
            ("Mouse Bind", 'mouse_bind', ["bhsn:++++","++++:bhsn"]),
            ("Render Driver", 'render_driver', ["opengles2", "opengles", "opengl", "direct3d", "metal", "software"]),
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
                if value in opts:
                    editor.setCurrentText(str(value))
                editor.currentTextChanged.connect(lambda text, vk=var_key: self.app_config.set(vk, text))
                if var_key == 'new_display':
                    editor.currentTextChanged.connect(self._update_resolution_state)
                elif var_key == 'max_size':
                    self.resolution_combo = editor

            editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            editor.setMaximumWidth(300)
            row_layout.addWidget(editor)
            layout.addLayout(row_layout)
            self.general_editors[var_key] = editor

        self._update_resolution_state()

    def _create_video_settings_group(self):
        self.video_settings_group, layout = self._create_group_box("Video Settings")
        self.v_codec_combo = NoScrollQComboBox()
        self.v_codec_combo.currentTextChanged.connect(self._on_video_codec_changed)
        self.v_encoder_combo = NoScrollQComboBox()
        
        # Video Codec
        codec_layout = QHBoxLayout()
        codec_label = QLabel("Codec")
        codec_label.setMinimumWidth(100)
        codec_layout.addWidget(codec_label)
        self.v_codec_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.v_codec_combo.setMaximumWidth(300)
        codec_layout.addWidget(self.v_codec_combo)
        codec_layout.setStretch(0, 0)
        codec_layout.setStretch(1, 1)
        layout.addLayout(codec_layout)
        
        # Video Encoder
        encoder_layout = QHBoxLayout()
        encoder_label = QLabel("Encoder")
        encoder_label.setMinimumWidth(100)
        encoder_layout.addWidget(encoder_label)
        self.v_encoder_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.v_encoder_combo.setMaximumWidth(300)
        encoder_layout.addWidget(self.v_encoder_combo)
        encoder_layout.setStretch(0, 0)
        encoder_layout.setStretch(1, 1)
        layout.addLayout(encoder_layout)

        # New video codec options
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
        
        # Audio Codec
        codec_layout = QHBoxLayout()
        codec_label = QLabel("Codec")
        codec_label.setMinimumWidth(100)
        codec_layout.addWidget(codec_label)
        self.a_codec_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.a_codec_combo.setMaximumWidth(300)
        codec_layout.addWidget(self.a_codec_combo)
        codec_layout.setStretch(0, 0)
        codec_layout.setStretch(1, 1)
        layout.addLayout(codec_layout)

        # Audio Encoder
        encoder_layout = QHBoxLayout()
        encoder_label = QLabel("Encoder")
        encoder_label.setMinimumWidth(100)
        encoder_layout.addWidget(encoder_label)
        self.a_encoder_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.a_encoder_combo.setMaximumWidth(300)
        encoder_layout.addWidget(self.a_encoder_combo)
        encoder_layout.setStretch(0, 0)
        encoder_layout.setStretch(1, 1)
        layout.addLayout(encoder_layout)

        self._create_slider(layout, "Audio Buffer", 'audio_buffer', 5, 500, 1, "ms")

    def _create_options_group(self):
        self.options_group, layout = self._create_group_box("Options", QGridLayout)
        checkboxes = [
            ("Fullscreen", 'fullscreen'), ("Turn screen off", 'turn_screen_off'),
            ("Stay Awake", 'stay_awake'), ("Disable mipmaps", 'mipmaps'),
            ("No Audio", 'no_audio'), ("No Video", 'no_video'),
        ]
        for i, (text, var_key) in enumerate(checkboxes):
            checkbox = QCheckBox(text)
            checkbox.setChecked(self.app_config.get(var_key, False))
            checkbox.stateChanged.connect(lambda state, vk=var_key: self.app_config.set(vk, bool(state)))
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

        value_label = QLabel() # Initialize empty, will be set by _setup_slider_common
        value_label.setMinimumWidth(50)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        row_layout.addWidget(slider) # Adiciona o slider ao row_layout
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

        value_label = QLabel() # Initialize empty, will be set by _setup_slider_common
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
        device_id = self.app_config.get('device_id')
        if device_id == DEVICE_NOT_FOUND or device_id is None:
            self.device_info_label.setText("Please connect a device.")
            self._load_encoders_from_cache()
            self._set_all_widgets_enabled(False)
            return

        self._set_all_widgets_enabled(True)
        self.device_info_label.setText("Fetching device info...")

        self._stop_worker("device_info")
        worker = DeviceInfoWorker(device_id)
        worker.result.connect(lambda info: self.on_device_info_ready(info, force_encoder_fetch))
        worker.error.connect(self.on_device_info_error)
        self._start_worker("device_info", worker, worker.run)

    def on_device_info_ready(self, info, force_encoder_fetch):
        self.last_device_info = info
        commercial_name = info.get("commercial_name", "Unknown Device")
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
        if self.app_config.get('device_id') == DEVICE_NOT_FOUND: return
        self.device_info_label.setText("Fetching encoders...")
        self._stop_worker("encoder_list")
        worker = EncoderListWorker()
        worker.result.connect(self._on_encoders_ready)
        worker.error.connect(lambda err: QMessageBox.critical(self, "Error", f"Could not fetch encoders: {err}"))
        self._start_worker("encoder_list", worker, worker.run)

    def _on_encoders_ready(self, result):
        self.video_encoders, self.audio_encoders = result
        self.app_config.save_encoder_cache(self.video_encoders, self.audio_encoders)
        self._populate_encoder_widgets()

        # Restore device info label
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
        """
        FIX: Restored the full functionality of this method.
        It now correctly synchronizes all widgets with the loaded configuration.
        """
        # Update General Settings editors
        for var_key, editor in self.general_editors.items():
            value = self.app_config.get(var_key)
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
            slider.setValue(value)
            unit = slider.property('unit')
            value_label.setText(f"{value}{unit}")

        # Update Video/Audio Codec/Encoder Combos
        self._populate_encoder_widgets()
        self._update_encoder_options(self.v_codec_combo, self.v_encoder_combo, self.video_encoders, 'video_encoder')
        self._update_encoder_options(self.a_codec_combo, self.a_encoder_combo, self.audio_encoders, 'audio_encoder')

        # Update resolution state
        self._update_resolution_state()

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

    def _set_all_widgets_enabled(self, enabled):
        groups = [self.general_settings_group, self.video_settings_group,
                  self.audio_settings_group, self.options_group]
        for group in groups:
            if group:
                group.setEnabled(enabled)

    def _start_worker(self, name, worker_instance, start_method):
        thread = QThread()
        worker_instance.moveToThread(thread)
        worker_instance.finished.connect(thread.quit)
        # FIX: Removed deleteLater connections to prevent RuntimeError on close.
        # The application's main shutdown process will handle object cleanup.
        thread.started.connect(start_method)
        thread.start()
        self.workers[name] = {"worker": worker_instance, "thread": thread}

    def _stop_worker(self, name):
        worker_info = self.workers.get(name)
        if worker_info and worker_info["thread"] and worker_info["thread"].isRunning():
            thread = worker_info["thread"]
            thread.quit()
            if not thread.wait(500):
                thread.terminate()
                thread.wait(500)
        self.workers[name] = {"worker": None, "thread": None}

    def stop_all_workers(self):
        for name in self.workers:
            self._stop_worker(name)

    def set_device_status_message(self, message):
        if message:
            self.device_info_label.setText(message)
            self._set_all_widgets_enabled(False)
        else:
            self.refresh_device_info()



