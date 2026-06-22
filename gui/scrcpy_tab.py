from PySide6.QtCore import Qt, QThreadPool, Signal, QRect, QPoint
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                               QLineEdit, QCheckBox, QSlider, QMessageBox,
                               QScrollArea, QSizePolicy, QPushButton, QGridLayout,
                               QListView, QScrollBar, QStyle, QGroupBox)
from PySide6.QtGui import QPainter, QPalette, QPolygonF, QPen, QBrush, QColor

from .flow_layout import FlowLayout

from .workers import DeviceInfoWorker, EncoderListWorker, DeviceConfigLoaderWorker
from . import themes
from utils.constants import *
from .web_server_config_window import WebServerConfigWindow
from .common_widgets import CustomThemedConfirmationDialog
from .dialogs import show_message_box


class NoArrowScrollBar(QScrollBar):
    def subControlRect(self, control, option):
        if control == QStyle.SubControl.SC_ScrollBarAddLine or \
           control == QStyle.SubControl.SC_ScrollBarSubLine:
            return QRect()
        return super().subControlRect(control, option)

class NoScrollQComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(180)
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        text_color = palette.color(QPalette.ColorRole.Text)
        highlight_color = palette.color(QPalette.ColorRole.Highlight)
        r = self.rect()

        painter.fillRect(r, palette.color(QPalette.ColorRole.Base))

        is_open = self.view().isVisible()
        if self.hasFocus() or is_open:
            line_color = highlight_color
        else:
            line_color = QColor(highlight_color)
            line_color.setAlpha(80)
        pen = QPen(line_color)
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.drawLine(r.bottomLeft() - QPoint(0, 1), r.bottomRight() - QPoint(0, 1))

        painter.setPen(text_color)
        painter.drawText(r.adjusted(4, 0, -22, 0), Qt.AlignmentFlag.AlignCenter, self.currentText())

        arrow_color = highlight_color if is_open else text_color
        painter.setPen(QPen(arrow_color, 1.5))
        painter.setBrush(QBrush(arrow_color))
        cx = r.width() - 12
        cy = r.center().y()
        if is_open:
            points = QPolygonF([
                QPoint(cx - 4, cy + 2),
                QPoint(cx + 4, cy + 2),
                QPoint(cx, cy - 5),
            ])
        else:
            points = QPolygonF([
                QPoint(cx - 4, cy - 2),
                QPoint(cx + 4, cy - 2),
                QPoint(cx, cy + 5),
            ])
        painter.drawPolygon(points)

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
    update_apps_setting_changed = Signal()

    def __init__(self, app_config, main_window=None):
        super().__init__()
        self.app_config = app_config
        self.main_window = main_window
        self.video_encoders = {}
        self.audio_encoders = {}
        self.last_device_info = {}
        self.general_editors = {}
        self.general_labels = {}
        self.option_checkboxes = {}
        self.sliders = {}
        self.section_cards = {}
        self.thread_pool = QThreadPool.globalInstance()
        self.active_workers = []
        self._setup_ui()
        self.app_config.load_profile(self.app_config.active_profile)
        self.update_profile_dropdown()
        self._update_all_widgets_from_config()
        self._update_theme_dropdown()

    def on_config_reloaded(self):
        device_id = self.app_config.get_connection_id()
        if not device_id or device_id == DEVICE_NOT_FOUND:
            self._update_all_widgets_from_config()
            self.update_profile_dropdown()
            return

        self._pending_profile_restore_key = self.profile_combo.currentData()
        self._set_all_widgets_enabled(False)

        worker = DeviceConfigLoaderWorker(device_id, self.app_config)
        worker.signals.result.connect(self._on_device_cache_refreshed)
        worker.signals.error.connect(self._on_cache_refresh_error)
        worker.signals.finished.connect(lambda: self._set_all_widgets_enabled(True))
        self._start_worker(worker)

    def _on_device_cache_refreshed(self, result_data, installed_apps_packages, winlator_shortcuts_on_device):
        self.update_profile_dropdown()
        self._update_all_widgets_from_config()

        if hasattr(self, '_pending_profile_restore_key') and self._pending_profile_restore_key:
            index = self.profile_combo.findData(self._pending_profile_restore_key)
            if index != -1:
                self.profile_combo.setCurrentIndex(index)
            else:
                self.profile_combo.setCurrentIndex(0)
            del self._pending_profile_restore_key
        else:
            self.profile_combo.setCurrentIndex(0)

    def _on_cache_refresh_error(self, error_message):
        device_id = self.app_config.get_connection_id()
        if device_id and device_id != DEVICE_NOT_FOUND:
            show_message_box(self, self.app_config.tr('common', 'error'),
                             f"Failed to refresh app list: {error_message}",
                             icon=QMessageBox.Critical)
        self.app_config.device_app_cache['installed_apps'] = set()
        self.app_config.device_app_cache['winlator_shortcuts'] = set()
        self.update_profile_dropdown()
        self._update_all_widgets_from_config()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Fixed profile bar at top (outside scroll)
        profile_bar = QHBoxLayout()
        profile_bar.setSpacing(8)
        profile_bar.setContentsMargins(0, 0, 0, 4)
        profile_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='configuration_profile'))
        profile_label.setObjectName("settings_field_label")
        profile_bar.addWidget(profile_label)
        self.profile_combo = NoScrollQComboBox()
        self.profile_combo.setObjectName("profile_combo")
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        profile_bar.addWidget(self.profile_combo, 1)
        main_layout.addLayout(profile_bar)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.verticalScrollBar().setSingleStep(15)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.scroll_area)

        scroll_content = QWidget()
        self.scroll_layout = FlowLayout(scroll_content, margin=2, spacing=6)
        self.scroll_area.setWidget(scroll_content)

        # Cards in FlowLayout
        self._create_yascrcpy_card()
        self._create_general_settings_card()
        self._create_video_settings_card()
        self._create_audio_settings_card()
        self._create_options_card()

        for key in ['yascrcpy', 'general', 'video', 'audio', 'options']:
            card = self.section_cards[key][0]
            card.setFixedWidth(480)
            self.scroll_layout.addWidget(card)

    def wheelEvent(self, event):
        self.scroll_area.wheelEvent(event)

    def _create_section_card(self, section_key):
        card = QGroupBox()
        card.setObjectName("settings_card")
        title = self.app_config.tr('scrcpy_tab', 'groups', key=section_key)
        card.setTitle(title)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 14, 8, 8)
        layout.setSpacing(4)
        self.section_cards[section_key] = (card, layout)
        return card, layout

    def _on_rendering_option_changed(self, var_key, state):
        self.app_config.set(var_key, state)
        if self.main_window:
            self.main_window.apps_tab.update_theme()
            self.main_window.winlator_tab.update_theme()

    def _create_yascrcpy_card(self):
        card, layout = self._create_section_card('yascrcpy')

        # Theme + Language in grid (label above combo)
        duo_grid = QGridLayout()
        duo_grid.setSpacing(6)
        label_theme = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='theme'))
        label_theme.setObjectName("settings_field_label")
        duo_grid.addWidget(label_theme, 0, 0)
        self.theme_combo = NoScrollQComboBox()
        self.theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        duo_grid.addWidget(self.theme_combo, 1, 0)
        label_lang = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='language'))
        label_lang.setObjectName("settings_field_label")
        duo_grid.addWidget(label_lang, 0, 1)
        self.lang_combo = NoScrollQComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Português", "pt")
        current_lang = self.app_config.get(CONF_LANGUAGE, 'en')
        index = self.lang_combo.findData(current_lang)
        if index != -1:
            self.lang_combo.setCurrentIndex(index)
        self.lang_combo.currentIndexChanged.connect(self._on_language_selected)
        duo_grid.addWidget(self.lang_combo, 1, 1)
        duo_grid.setColumnStretch(0, 1)
        duo_grid.setColumnStretch(1, 1)
        layout.addLayout(duo_grid)

        # Checkboxes
        checkbox_font = self.font()
        checkbox_font.setPointSize(checkbox_font.pointSize() - 1)

        check_row1 = QHBoxLayout()
        check_row1.setSpacing(8)

        self.show_system_apps_checkbox = QCheckBox(self.app_config.tr('scrcpy_tab', 'labels', key='show_system_apps'))
        self.show_system_apps_checkbox.setFont(checkbox_font)
        self.show_system_apps_checkbox.setChecked(self.app_config.get(CONF_SHOW_SYSTEM_APPS, False))
        self.show_system_apps_checkbox.stateChanged.connect(self._on_show_system_apps_changed)
        check_row1.addWidget(self.show_system_apps_checkbox)

        self.hq_rendering_checkbox = QCheckBox(self.app_config.tr('scrcpy_tab', 'rendering', key='hq_icon_rendering'))
        self.hq_rendering_checkbox.setFont(checkbox_font)
        self.hq_rendering_checkbox.setChecked(self.app_config.get(CONF_HQ_ICON_RENDERING, True))
        self.hq_rendering_checkbox.stateChanged.connect(lambda state: self._on_rendering_option_changed(CONF_HQ_ICON_RENDERING, bool(state)))
        check_row1.addWidget(self.hq_rendering_checkbox)
        self.option_checkboxes[CONF_HQ_ICON_RENDERING] = self.hq_rendering_checkbox

        self.hover_effect_checkbox = QCheckBox(self.app_config.tr('scrcpy_tab', 'rendering', key='web_hover_effect'))
        self.hover_effect_checkbox.setFont(checkbox_font)
        self.hover_effect_checkbox.setChecked(self.app_config.get(CONF_WEB_HOVER_EFFECT, True))
        self.hover_effect_checkbox.stateChanged.connect(lambda state: self._on_rendering_option_changed(CONF_WEB_HOVER_EFFECT, bool(state)))
        check_row1.addWidget(self.hover_effect_checkbox)
        self.option_checkboxes[CONF_WEB_HOVER_EFFECT] = self.hover_effect_checkbox

        check_row1.addStretch()
        layout.addLayout(check_row1)

        check_row2 = QHBoxLayout()
        check_row2.setSpacing(8)

        self.update_apps_on_startup_checkbox = QCheckBox(self.app_config.tr('scrcpy_tab', 'labels', key='update_apps_on_startup'))
        self.update_apps_on_startup_checkbox.setFont(checkbox_font)
        self.update_apps_on_startup_checkbox.setChecked(self.app_config.get(CONF_UPDATE_APPS_ON_STARTUP, True))
        self.update_apps_on_startup_checkbox.stateChanged.connect(self._on_update_apps_on_startup_changed)
        check_row2.addWidget(self.update_apps_on_startup_checkbox)
        self.option_checkboxes[CONF_UPDATE_APPS_ON_STARTUP] = self.update_apps_on_startup_checkbox

        check_row2.addStretch()
        layout.addLayout(check_row2)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.web_server_config_button = QPushButton(self.app_config.tr('scrcpy_tab', 'labels', key='web_server'))
        self.web_server_config_button.clicked.connect(self._open_web_server_config)
        btn_row.addWidget(self.web_server_config_button)
        self.redownload_icons_button = QPushButton(self.app_config.tr('apps_tab', 'redownload_icons_btn'))
        self.redownload_icons_button.clicked.connect(self._redownload_all_icons)
        btn_row.addWidget(self.redownload_icons_button)
        layout.addLayout(btn_row)

    def _redownload_all_icons(self):
        dialog = CustomThemedConfirmationDialog(self,
            title=self.app_config.tr('apps_tab', 'redownload_icons_btn'),
            message=self.app_config.tr('apps_tab', 'confirm_redownload_msg'))

        if dialog.exec():
            if self.main_window and hasattr(self.main_window, 'apps_tab'):
                self.main_window.apps_tab.trigger_icon_redownload()

    def _update_card_header(self, section_key):
        if section_key in self.section_cards:
            card, _ = self.section_cards[section_key]
            card.setTitle(self.app_config.tr('scrcpy_tab', 'groups', key=section_key))

    def retranslate_ui(self):
        for section in ['yascrcpy', 'general', 'video', 'audio', 'options']:
            self._update_card_header(section)

        self.show_system_apps_checkbox.setText(self.app_config.tr('scrcpy_tab', 'labels', key='show_system_apps'))
        self.update_apps_on_startup_checkbox.setText(self.app_config.tr('scrcpy_tab', 'labels', key='update_apps_on_startup'))
        self.hq_rendering_checkbox.setText(self.app_config.tr('scrcpy_tab', 'rendering', key='hq_icon_rendering'))
        self.hover_effect_checkbox.setText(self.app_config.tr('scrcpy_tab', 'rendering', key='web_hover_effect'))
        self.web_server_config_button.setText(self.app_config.tr('scrcpy_tab', 'labels', key='web_server'))
        self.redownload_icons_button.setText(self.app_config.tr('apps_tab', 'redownload_icons_btn'))

        translations = {
            CONF_WINDOWING_MODE: 'window_mode', CONF_MOUSE_MODE: 'mouse_mode',
            CONF_GAMEPAD_MODE: 'gamepad_mode', CONF_KEYBOARD_MODE: 'keyboard_mode',
            CONF_MOUSE_BIND: 'mouse_bind', CONF_MAX_FPS: 'max_fps',
            CONF_NEW_DISPLAY: 'virtual_display', CONF_MAX_SIZE: 'max_size',
            CONF_EXTRAARGS: 'extra_args', CONF_IFRAME_INTERVAL: 'iframe_interval',
            CONF_VIDEO_BUFFER: 'video_buffer', CONF_VIDEO_BITRATE_SLIDER: 'video_bitrate',
            CONF_AUDIO_BUFFER: 'audio_buffer', CONF_AUDIO_BITRATE_SLIDER: 'audio_bitrate',
        }
        for var_key, label_key in translations.items():
            if var_key in self.general_labels:
                self.general_labels[var_key].setText(self.app_config.tr('scrcpy_tab', 'labels', key=label_key))

        self.v_codec_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='codec'))
        self.v_encoder_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='encoder'))
        self.a_codec_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='codec'))
        self.a_encoder_label.setText(self.app_config.tr('scrcpy_tab', 'labels', key='encoder'))

        opt_trans = {
            CONF_FULLSCREEN: 'fullscreen', CONF_TURN_SCREEN_OFF: 'turn_screen_off',
            CONF_STAY_AWAKE: 'stay_awake', CONF_MIPMAPS: 'disable_mipmaps',
            CONF_NO_AUDIO: 'no_audio', CONF_NO_VIDEO: 'no_video',
            CONF_TRY_UNLOCK: 'unlock_device', CONF_FORCE_ADB_FORWARD: 'force_adb_forward',
            ALTERNATE_LAUNCH_METHOD: 'alternate_launch',
        }
        for var_key, label_key in opt_trans.items():
            if var_key in self.option_checkboxes:
                self.option_checkboxes[var_key].setText(self.app_config.tr('scrcpy_tab', 'options', key=label_key))

        self._update_all_widgets_from_config()
        self.update_profile_dropdown()

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

        if self.main_window.web_config_window is None:
            self.main_window.web_config_window = WebServerConfigWindow(self.app_config, self.main_window)
            self.main_window.web_config_window.destroyed.connect(lambda: setattr(self.main_window, 'web_config_window', None))
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

    def _on_update_apps_on_startup_changed(self, state):
        self.app_config.set(CONF_UPDATE_APPS_ON_STARTUP, bool(state))
        self.update_apps_setting_changed.emit()

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

    def update_profile_dropdown(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem(self.app_config.tr('scrcpy_tab', 'labels', key='global_config'), "global")
        device_id = self.app_config.get_connection_id()
        if device_id == DEVICE_NOT_FOUND or device_id is None:
            self.profile_combo.blockSignals(False)
            return

        installed_apps_packages = self.app_config.device_app_cache.get('installed_apps', set())
        winlator_shortcuts_on_device = self.app_config.device_app_cache.get('winlator_shortcuts', set())
        launcher_pkg = self.app_config.get(CONF_DEFAULT_LAUNCHER)

        app_configs_from_settings = self.app_config.get_app_config_keys()
        filtered_apps = [
            (key, name) for key, name in app_configs_from_settings
            if key in installed_apps_packages or key == launcher_pkg
        ]

        if filtered_apps:
            self.profile_combo.insertSeparator(self.profile_combo.count())
            for key, name in sorted(filtered_apps, key=lambda x: x[1].lower()):
                self.profile_combo.addItem(f"{name} (App)", key)

        winlator_configs_from_settings = self.app_config.get_winlator_config_keys()
        filtered_winlator = [
            (key, name) for key, name in winlator_configs_from_settings
            if key in winlator_shortcuts_on_device
        ]

        if filtered_winlator:
            self.profile_combo.insertSeparator(self.profile_combo.count())
            for key, name in sorted(filtered_winlator, key=lambda x: x[1].lower()):
                self.profile_combo.addItem(f"{name} (Winlator)", key)

        active_profile = self.app_config.active_profile
        index = self.profile_combo.findData(active_profile)
        if index != -1:
            self.profile_combo.setCurrentIndex(index)
        else:
            self.app_config.load_profile("global")
            self.profile_combo.setCurrentIndex(0)

        self.profile_combo.blockSignals(False)

    def _on_profile_selected(self, index):
        if index == -1: return
        profile_key = self.profile_combo.itemData(index)
        self.app_config.load_profile(profile_key)
        self._update_all_widgets_from_config()
        self._update_launch_control_widgets_state()

    def _add_row(self, parent_layout, label_text, editor_widget):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setMinimumWidth(90)
        row.addWidget(label)
        editor_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(editor_widget, 1)
        parent_layout.addLayout(row)

    def _create_general_settings_card(self):
        card, layout = self._create_section_card('general')
        grid = QGridLayout()
        grid.setSpacing(6)

        combo_fields = [
            (self.app_config.tr('scrcpy_tab', 'labels', key='window_mode'), CONF_WINDOWING_MODE, ["Fullscreen", "Freeform"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='mouse_mode'), CONF_MOUSE_MODE, ["sdk","uhid","aoa"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='gamepad_mode'), CONF_GAMEPAD_MODE, ["disabled","uhid","aoa"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='keyboard_mode'), CONF_KEYBOARD_MODE, ["disabled","sdk","uhid","aoa"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='mouse_bind'), CONF_MOUSE_BIND, ["bhsn:++++","++++:bhsn"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='max_fps'), CONF_MAX_FPS, ["20","25","30", "45", "60"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='virtual_display'), CONF_NEW_DISPLAY, ["Disabled", "640x360/120", "854x480/120", "960x550/120", "1280x720/140", "1366x768/140", "1920x1080/140"]),
            (self.app_config.tr('scrcpy_tab', 'labels', key='max_size'), CONF_MAX_SIZE, ["0", "640", "854", "960","1280","1366","1080"]),
        ]
        self.resolution_combo = None
        for i, (label_text, var_key, opts) in enumerate(combo_fields):
            col = i % 2
            row_idx = (i // 2) * 2

            lbl = QLabel(label_text)
            lbl.setObjectName("settings_field_label")
            self.general_labels[var_key] = lbl
            grid.addWidget(lbl, row_idx, col)

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
            grid.addWidget(editor, row_idx + 1, col)
            self.general_editors[var_key] = editor

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.extra_args_edit = QLineEdit(str(self.app_config.get(CONF_EXTRAARGS, "")))
        self.extra_args_edit.textChanged.connect(lambda text: self.app_config.set(CONF_EXTRAARGS, text))
        self.extra_args_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        extra_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='extra_args'))
        extra_label.setObjectName("settings_field_label")
        self.general_labels[CONF_EXTRAARGS] = extra_label
        layout.addWidget(extra_label)
        layout.addWidget(self.extra_args_edit)
        self.general_editors[CONF_EXTRAARGS] = self.extra_args_edit

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

    def _create_video_settings_card(self):
        card, layout = self._create_section_card('video')
        grid = QGridLayout()
        grid.setSpacing(6)

        self.v_codec_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='codec'))
        self.v_codec_label.setObjectName("settings_field_label")
        grid.addWidget(self.v_codec_label, 0, 0)
        self.v_codec_combo = NoScrollQComboBox()
        self.v_codec_combo.currentTextChanged.connect(self._on_video_codec_changed)
        self.v_codec_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        grid.addWidget(self.v_codec_combo, 1, 0)

        self.v_encoder_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='encoder'))
        self.v_encoder_label.setObjectName("settings_field_label")
        grid.addWidget(self.v_encoder_label, 0, 1)
        self.v_encoder_combo = NoScrollQComboBox()
        self.v_encoder_combo.currentTextChanged.connect(lambda text: self.app_config.set(CONF_VIDEO_ENCODER, text))
        self.v_encoder_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        grid.addWidget(self.v_encoder_combo, 1, 1)

        combo_fields = [
            ('render_driver', CONF_RENDER_DRIVER, ["opengles2", "opengles", "opengl", "direct3d", "metal", "software"]),
            ('color_range', CONF_COLOR_RANGE, ["Auto", "Full", "Limited"]),
            ('frame_drop', CONF_ALLOW_FRAME_DROP, ["Enabled", "Disabled"]),
            ('low_latency', CONF_LOW_LATENCY, ["Enabled", "Disabled"]),
            ('priority', CONF_PRIORITY_MODE, ["Realtime", "Normal"]),
            ('bitrate_mode', CONF_BITRATE_MODE, ["Constant", "Variable"]),
        ]
        for i, (label_key, var_key, opts) in enumerate(combo_fields):
            col = i % 2
            row_idx = (i // 2) * 2 + 2
            lbl = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key=label_key))
            lbl.setObjectName("settings_field_label")
            grid.addWidget(lbl, row_idx, col)
            combo = NoScrollQComboBox()
            combo.addItems(opts)
            saved = self.app_config.get(var_key, opts[0])
            combo.setCurrentText(str(saved))
            combo.currentTextChanged.connect(lambda text, vk=var_key: self.app_config.set(vk, text))
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            grid.addWidget(combo, row_idx + 1, col)
            self.general_editors[var_key] = combo

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self._create_iframe_interval_slider(layout, self.app_config.tr('scrcpy_tab', 'labels', key='iframe_interval'), CONF_IFRAME_INTERVAL, 0, 30, 1, 0)
        self._create_slider(layout, self.app_config.tr('scrcpy_tab', 'labels', key='video_buffer'), CONF_VIDEO_BUFFER, 0, 500, 1, "ms")
        self._create_slider_with_buttons(layout, self.app_config.tr('scrcpy_tab', 'labels', key='video_bitrate'), CONF_VIDEO_BITRATE_SLIDER, 10, 25000, 10, "K", [1000, 2000, 4000, 6000, 8000])

    def _create_audio_settings_card(self):
        card, layout = self._create_section_card('audio')
        grid = QGridLayout()
        grid.setSpacing(6)

        self.a_codec_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='codec'))
        self.a_codec_label.setObjectName("settings_field_label")
        grid.addWidget(self.a_codec_label, 0, 0)
        self.a_codec_combo = NoScrollQComboBox()
        self.a_codec_combo.currentTextChanged.connect(self._on_audio_codec_changed)
        self.a_codec_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        grid.addWidget(self.a_codec_combo, 1, 0)

        self.a_encoder_label = QLabel(self.app_config.tr('scrcpy_tab', 'labels', key='encoder'))
        self.a_encoder_label.setObjectName("settings_field_label")
        grid.addWidget(self.a_encoder_label, 0, 1)
        self.a_encoder_combo = NoScrollQComboBox()
        self.a_encoder_combo.currentTextChanged.connect(lambda text: self.app_config.set(CONF_AUDIO_ENCODER, text))
        self.a_encoder_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        grid.addWidget(self.a_encoder_combo, 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self._create_slider(layout, self.app_config.tr('scrcpy_tab', 'labels', key='audio_buffer'), CONF_AUDIO_BUFFER, 5, 500, 1, "ms")
        self._create_slider(layout, self.app_config.tr('scrcpy_tab', 'labels', key='audio_bitrate'), CONF_AUDIO_BITRATE_SLIDER, 64, 320, 16, "K")

    def _create_options_card(self):
        card, layout = self._create_section_card('options')
        grid = QGridLayout()
        grid.setSpacing(6)

        config_checkboxes = [
            (self.app_config.tr('scrcpy_tab', 'options', key='fullscreen'), CONF_FULLSCREEN),
            (self.app_config.tr('scrcpy_tab', 'options', key='turn_screen_off'), CONF_TURN_SCREEN_OFF),
            (self.app_config.tr('scrcpy_tab', 'options', key='stay_awake'), CONF_STAY_AWAKE),
            (self.app_config.tr('scrcpy_tab', 'options', key='disable_mipmaps'), CONF_MIPMAPS),
            (self.app_config.tr('scrcpy_tab', 'options', key='no_audio'), CONF_NO_AUDIO),
            (self.app_config.tr('scrcpy_tab', 'options', key='no_video'), CONF_NO_VIDEO),
            (self.app_config.tr('scrcpy_tab', 'options', key='unlock_device'), CONF_TRY_UNLOCK),
            (self.app_config.tr('scrcpy_tab', 'options', key='force_adb_forward'), CONF_FORCE_ADB_FORWARD),
            (self.app_config.tr('scrcpy_tab', 'options', key='alternate_launch'), ALTERNATE_LAUNCH_METHOD),
        ]
        for i, (text, var_key) in enumerate(config_checkboxes):
            checkbox = QCheckBox(text)
            checkbox.setChecked(self.app_config.get(var_key, False))
            checkbox.stateChanged.connect(lambda state, vk=var_key: self.app_config.set(vk, bool(state)))
            if var_key == ALTERNATE_LAUNCH_METHOD:
                checkbox.stateChanged.connect(self._update_launch_control_widgets_state)
            grid.addWidget(checkbox, i // 3, i % 3)
            self.option_checkboxes[var_key] = checkbox
        for col in range(3):
            grid.setColumnStretch(col, 1)
        layout.addLayout(grid)

    def _setup_slider_common(self, slider, value_label, var_key, unit, min_val):
        slider.valueChanged.connect(lambda value: value_label.setText(f"{value}{unit}"))
        slider.valueChanged.connect(lambda value: self.app_config.set(var_key, value))
        slider.setValue(self.app_config.get(var_key, min_val))
        value_label.setText(f"{self.app_config.get(var_key, min_val)}{unit}")

    def _create_slider(self, parent_layout, label_text, var_key, min_val, max_val, step, unit):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setMinimumWidth(90)
        self.general_labels[var_key] = label
        row.addWidget(label)

        slider = NoScrollQSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setSingleStep(step)
        slider.setPageStep(step * 10)
        slider.setProperty('unit', unit)
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        value_label = QLabel()
        value_label.setMinimumWidth(50)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        parent_layout.addLayout(row)
        self.sliders[var_key] = (slider, value_label)
        self._setup_slider_common(slider, value_label, var_key, unit, min_val)

    def _create_slider_with_buttons(self, parent_layout, label_text, var_key, min_val, max_val, step, unit, button_values):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setMinimumWidth(90)
        self.general_labels[var_key] = label
        row.addWidget(label)

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
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        parent_layout.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_row.addStretch()
        for btn_val in button_values:
            button = QPushButton(f"{btn_val}{unit}")
            button.clicked.connect(lambda checked, val=btn_val: slider.setValue(val))
            button.setFixedWidth(50)
            button.setObjectName("scrcpy_bitrate_button")
            btn_row.addWidget(button)
        btn_row.addStretch()
        parent_layout.addLayout(btn_row)
        self.sliders[var_key] = (slider, value_label)

    def _create_iframe_interval_slider(self, parent_layout, label_text, var_key, min_val, max_val, step, default_val):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setMinimumWidth(90)
        self.general_labels[var_key] = label
        row.addWidget(label)

        slider = NoScrollQSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
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
        slider.valueChanged.connect(lambda value: self.app_config.set(var_key, value))

        current_value = self.app_config.get(var_key, default_val)
        slider.setValue(int(current_value))
        update_label(int(current_value))

        row.addWidget(slider, 1)
        row.addWidget(value_label)
        parent_layout.addLayout(row)
        self.sliders[var_key] = (slider, value_label)

    def refresh_device_info(self, force_encoder_fetch=False):
        self.update_profile_dropdown()
        device_id = self.app_config.get_connection_id()
        if device_id == DEVICE_NOT_FOUND or device_id is None:
            self._load_encoders_from_cache()
            self._set_all_widgets_enabled(False)
            return
        self._set_all_widgets_enabled(True)
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
        if force_encoder_fetch or not self.app_config.has_encoder_cache():
            self._fetch_and_update_encoders()
        else:
            self._load_encoders_from_cache()
        self.config_updated_on_worker.emit()

    def on_device_info_error(self, error_msg):
        self._load_encoders_from_cache()

    def _fetch_and_update_encoders(self):
        device_id = self.app_config.get_connection_id()
        if device_id == DEVICE_NOT_FOUND or device_id is None: return
        worker = EncoderListWorker(device_id)
        worker.signals.result.connect(self._on_encoders_ready)
        worker.signals.error.connect(self._on_encoder_fetch_error)
        self._start_worker(worker)

    def _on_encoder_fetch_error(self, err):
        device_id = self.app_config.get_connection_id()
        if device_id and device_id != DEVICE_NOT_FOUND:
            show_message_box(self, self.app_config.tr('common', 'error'),
                             self.app_config.tr('scrcpy_tab', 'labels', key='fetch_encoders_error', error=err),
                             icon=QMessageBox.Critical)

    def _on_encoders_ready(self, result):
        self.video_encoders, self.audio_encoders = result
        self.app_config.save_encoder_cache(self.video_encoders, self.audio_encoders)
        self._populate_encoder_widgets()

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
        for slider_tuple in self.sliders.values(): slider_tuple[0].blockSignals(True)
        self.theme_combo.blockSignals(True)
        self.profile_combo.blockSignals(True)
        self.v_codec_combo.blockSignals(True)
        self.v_encoder_combo.blockSignals(True)
        self.a_codec_combo.blockSignals(True)
        self.a_encoder_combo.blockSignals(True)

        for var_key, editor in self.general_editors.items():
            value = self.app_config.get(var_key, "")
            if value is None: value = ""
            if isinstance(editor, QLineEdit):
                editor.setText(str(value))
            elif isinstance(editor, QComboBox):
                editor.setCurrentText(str(value))

        for var_key, checkbox in self.option_checkboxes.items():
            value = self.app_config.get(var_key, False)
            checkbox.setChecked(bool(value))

        for var_key, (slider, value_label) in self.sliders.items():
            value = self.app_config.get(var_key)
            if value is None:
                if var_key == 'iframe_interval': value = 0
                elif 'bitrate' in var_key: value = 3000 if 'video' in var_key else 128
                else: value = 0

            try:
                slider.setValue(int(value))
            except (ValueError, TypeError):
                slider.setValue(0)

            if var_key == 'iframe_interval':
                if int(value) == 0:
                    value_label.setText("Auto")
                else:
                    value_label.setText(f"{value}s")
            else:
                unit = slider.property('unit') or ""
                value_label.setText(f"{value}{unit}")

        self._update_theme_dropdown()
        self.update_profile_dropdown()
        self._populate_encoder_widgets()
        self._update_resolution_state()
        self._update_launch_control_widgets_state()

        for editor in self.general_editors.values(): editor.blockSignals(False)
        for checkbox in self.option_checkboxes.values(): checkbox.blockSignals(False)
        for slider_tuple in self.sliders.values(): slider_tuple[0].blockSignals(False)
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
        sections_to_toggle = ['general', 'video', 'audio', 'options']
        for section in sections_to_toggle:
            if section in self.section_cards:
                card, _ = self.section_cards[section]
                card.setEnabled(enabled)
        if include_profile:
            self.profile_combo.setEnabled(enabled)

    def _start_worker(self, worker):
        self.active_workers.append(worker)
        worker.signals.finished.connect(lambda: self._on_worker_finished(worker))
        self.thread_pool.start(worker)

    def _on_worker_finished(self, worker):
        if worker in self.active_workers:
            self.active_workers.remove(worker)

    def stop_all_workers(self):
        for worker in self.active_workers:
            try:
                worker.signals.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                worker.signals.result.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                worker.signals.error.disconnect()
            except (TypeError, RuntimeError):
                pass
        self.active_workers.clear()

    def select_profile(self, profile_key):
        self.update_profile_dropdown()
        index = self.profile_combo.findData(profile_key)
        if index != -1:
            self.profile_combo.setCurrentIndex(index)
