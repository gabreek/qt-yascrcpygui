# FILE: gui/themes.py
# PURPOSE: Centralizes theme management for the application.

from PySide6.QtGui import QPalette, QColor
import os
import json

_THEMES_DIR = os.path.join(os.path.dirname(__file__), 'themes')

def is_dark_theme(palette):
    """Checks if the provided palette corresponds to a dark theme."""
    return palette.color(QPalette.ColorRole.Window).value() < 128

def _build_stylesheet(colors):
    main_bg_color = colors['main_bg']
    title_text_color = colors['title_text']
    border_color = colors['border']
    base_bg_color = colors['base_bg']
    button_bg_color = colors['button_bg']
    button_text_color = colors['button_text']
    highlight_color = colors['highlight']
    highlighted_text_color = colors['highlighted_text']
    alt_base_color = colors['alt_base']
    mid_color = colors['mid']

    return f"""
        QWidget {{
            font-size: 9pt;
        }}
        #main_widget, #container_widget {{
            background-color: {main_bg_color};
            border: 1px solid {border_color};
            border-radius: 15px;
        }}
        QDialog {{
            background-color: transparent;
        }}
        QTabWidget::pane {{
            border: none;
        }}
        QTabBar::tab {{
            background: {button_bg_color};
            color: {button_text_color};
            padding: 6px 10px;
            border-radius: 8px;
            margin: 2px;
        }}
        QTabBar::tab:selected {{
            background: {highlight_color};
            color: {highlighted_text_color};
        }}
        QTabBar::tab:!selected:hover {{
            background: {alt_base_color};
        }}
        QGroupBox {{
            border: 1px solid {border_color};
            border-radius: 10px;
            margin-top: 12px;
            padding: 14px 8px 8px 8px;
            background-color: {base_bg_color};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: {title_text_color};
            font-weight: bold;
            font-size: 11pt;
        }}
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        #settings_field_label {{
            color: {title_text_color};
            font-size: 8pt;
            padding: 2px 0 0 0;
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {border_color};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {highlight_color};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            height: 0;
            border: none;
            background: none;
        }}
        QPushButton {{
            background-color: {button_bg_color};
            color: {button_text_color};
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 4px 12px;
        }}
        QPushButton:hover {{
            background-color: {alt_base_color};
        }}
        QPushButton:pressed {{
            background-color: {mid_color};
        }}
        QPushButton:disabled {{
            background-color: {main_bg_color};
            color: {border_color};
            border: 1px solid {border_color};
        }}
        #close_button, #minimize_button, #wifi_button, #session_manager_button {{
            background-color: transparent;
            border: none;
            padding: 0;
            border-radius: 4px;
        }}
        #close_button:hover {{
             background-color: #d32f2f;
        }}
        #minimize_button:hover, #wifi_button:hover, #session_manager_button:hover {{
            background-color: {alt_base_color};
        }}
        QLineEdit {{
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 4px;
            background-color: {base_bg_color};
            color: {title_text_color};
        }}
        QLineEdit:focus {{
            border: 1px solid {highlight_color};
        }}
        QSpinBox {{
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 4px;
            background-color: {base_bg_color};
            color: {title_text_color};
            min-height: 22px;
        }}
        QSpinBox:focus {{
            border: 1px solid {highlight_color};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            border: none;
            background: transparent;
            width: 20px;
        }}
        QComboBox {{
            min-width: 6em;
            max-width: 180px;
            min-height: 18px;
        }}
        #profile_combo {{
            min-width: 220px;
            max-width: 220px;
        }}
        #combo-dropdown-view {{
            border: 1px solid {border_color};
            border-radius: 10px;
            background-color: {base_bg_color};
            color: {title_text_color};
            selection-background-color: {highlight_color};
            selection-color: {highlighted_text_color};
            outline: 0px;
        }}
        QComboBox:focus #combo-dropdown-view, QComboBox:on #combo-dropdown-view {{
            border: 1px solid {highlight_color};
        }}
        #combo-dropdown-view::item {{
            padding: 5px 10px;
        }}
        #combo-dropdown-view QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 4px 0 4px 0;
        }}
        #combo-dropdown-view QScrollBar::handle:vertical {{
            background: {border_color};
            border-radius: 4px;
            min-height: 20px;
        }}
        #combo-dropdown-view QScrollBar::handle:vertical:hover {{
            background: {highlight_color};
        }}
        #combo-dropdown-view QScrollBar::add-line:vertical, #combo-dropdown-view QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
            background: none;
        }}
        #combo-dropdown-view QScrollBar::add-page:vertical, #combo-dropdown-view QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QListWidget, QTreeWidget {{
            background-color: {base_bg_color};
            color: {title_text_color};
            border: 1px solid {border_color};
            border-radius: 5px;
        }}
        QListWidget::item:selected, QTreeWidget::item:selected {{
            background-color: {highlight_color};
            color: {highlighted_text_color};
        }}
        QLabel {{
            color: {title_text_color};
            background-color: transparent;
        }}
        #adb_status_label[error="true"] {{
            color: red;
        }}
        #adb_status_label[error="false"] {{
            color: {title_text_color};
        }}
        #item_name_label {{
            font-size: 8pt;
        }}
        #item_action_button {{
            padding: 0;
            padding-top: 2px;
        }}
        #scrcpy_bitrate_button {{
            font-size: 10px;
        }}
        #session_tree_widget::item {{
            height: 32px;
        }}
        #device_selector_btn {{
            background-color: {button_bg_color};
            border: 1px solid {border_color};
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 9pt;
            min-width: 140px;
        }}
        #device_selector_btn:hover {{
            background-color: {alt_base_color};
        }}
        #device_card {{
            background-color: {base_bg_color};
            border: 1px solid {border_color};
            border-radius: 8px;
        }}
        #device_card:hover {{
            background-color: {alt_base_color};
        }}
        #device_name_label {{
            font-size: 10pt;
            font-weight: bold;
            color: {title_text_color};
        }}
        #device_id_label {{
            font-size: 8pt;
            color: {mid_color};
        }}
        #device_battery_label {{
            font-size: 8pt;
            color: {mid_color};
        }}
        #current_device_label {{
            font-size: 9pt;
            font-weight: bold;
            color: #4CAF50;
        }}
        #device_switch_btn {{
            background-color: {highlight_color};
            color: {highlighted_text_color};
            border: none;
            border-radius: 4px;
            padding: 4px 12px;
            font-size: 9pt;
        }}
        #device_switch_btn:hover {{
            background-color: {highlight_color};
        }}
        #device_disconnect_btn {{
            background-color: transparent;
            color: #e74c3c;
            border: 1px solid #e74c3c;
            border-radius: 4px;
            padding: 4px 12px;
            font-size: 9pt;
        }}
        #device_disconnect_btn:hover {{
            background-color: #e74c3c;
            color: white;
        }}
        QCheckBox {{
            color: {title_text_color};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid {border_color};
            background-color: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {highlight_color};
            border: 1px solid {border_color};
            margin: 3px;
        }}
        QCheckBox::indicator:hover {{
            border: 1px solid {highlight_color};
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: {highlight_color};
            border: 1px solid {highlight_color};
            margin: 2px;
        }}
        QSlider::groove:horizontal {{
            border: none;
            height: 4px;
            background: {border_color};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {highlight_color};
            border: none;
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {highlight_color};
        }}
        QSlider::sub-page:horizontal {{
            background: {highlight_color};
            border-radius: 2px;
        }}
    """

def get_theme_stylesheet(palette):
    colors = {}
    w = palette.color(QPalette.ColorRole.Window)
    colors['main_bg'] = w.name()
    colors['title_text'] = palette.color(QPalette.ColorRole.WindowText).name()
    colors['border'] = w.darker(140).name() if not is_dark_theme(palette) else w.lighter(170).name()
    colors['base_bg'] = palette.color(QPalette.ColorRole.Base).name()
    colors['button_bg'] = palette.color(QPalette.ColorRole.Button).name()
    colors['button_text'] = palette.color(QPalette.ColorRole.ButtonText).name()
    colors['highlight'] = palette.color(QPalette.ColorRole.Highlight).name()
    colors['highlighted_text'] = palette.color(QPalette.ColorRole.HighlightedText).name()
    colors['alt_base'] = palette.color(QPalette.ColorRole.AlternateBase).name()
    colors['mid'] = palette.color(QPalette.ColorRole.Mid).name()
    return _build_stylesheet(colors)

def _load_json_theme_colors(name):
    path = os.path.join(_THEMES_DIR, f'{name}.json')
    with open(path) as f:
        data = json.load(f)
    return data['colors']

def _json_theme_generator(palette, name):
    colors = _load_json_theme_colors(name)
    return _build_stylesheet(colors)

def apply_theme_to_custom_title_bar(title_bar, palette):
    """Applies specific styles to a CustomTitleBar."""
    title_text_color = palette.color(QPalette.ColorRole.WindowText).name()
    title_bar.title_label.setStyleSheet(f"color: {title_text_color}; padding-left: 10px; font-weight: bold; background-color: transparent;")

def _make_palette_from_colors(colors):
    p = QPalette()
    def role(name, role):
        if name in colors:
            p.setColor(role, QColor(colors[name]))
    role('main_bg', QPalette.ColorRole.Window)
    role('title_text', QPalette.ColorRole.WindowText)
    role('base_bg', QPalette.ColorRole.Base)
    role('button_bg', QPalette.ColorRole.Button)
    role('button_text', QPalette.ColorRole.ButtonText)
    role('highlight', QPalette.ColorRole.Highlight)
    role('highlighted_text', QPalette.ColorRole.HighlightedText)
    role('alt_base', QPalette.ColorRole.AlternateBase)
    role('mid', QPalette.ColorRole.Mid)
    role('title_text', QPalette.ColorRole.Text)
    role('main_bg', QPalette.ColorRole.Dark)
    role('base_bg', QPalette.ColorRole.Light)
    role('mid', QPalette.ColorRole.Midlight)
    role('main_bg', QPalette.ColorRole.Shadow)
    return p


def _discover_json_themes():
    themes = {}
    if not os.path.isdir(_THEMES_DIR):
        return themes
    for fname in os.listdir(_THEMES_DIR):
        if fname.endswith('.json'):
            name = fname[:-5]
            with open(os.path.join(_THEMES_DIR, fname)) as f:
                data = json.load(f)
            display_name = data.get('name', name)
            themes[display_name] = lambda p, n=name: _json_theme_generator(p, n)
    return themes

THEMES = {
    "System": get_theme_stylesheet,
}
THEMES.update(_discover_json_themes())

_current_theme = "System"
_original_system_palette = None

def get_current_theme():
    return _current_theme

def get_available_themes():
    """Returns a list of available theme names. System always first, then alphabetical."""
    themes = sorted(name for name in THEMES if name != "System")
    return ["System"] + themes

def _get_json_colors(theme_name):
    for fname in os.listdir(_THEMES_DIR):
        if fname.endswith('.json'):
            with open(os.path.join(_THEMES_DIR, fname)) as f:
                data = json.load(f)
            if data.get('name') == theme_name or fname[:-5] == theme_name:
                return data['colors']
    return None

def apply_theme(app, theme_name):
    """Applies a theme to the entire application."""
    global _current_theme, _original_system_palette
    if theme_name not in THEMES:
        return None

    # Save original system palette on first call
    if _original_system_palette is None:
        _original_system_palette = app.palette()

    _current_theme = theme_name
    generator = THEMES[theme_name]
    if theme_name == "System":
        palette = QPalette(_original_system_palette)
    else:
        colors = _get_json_colors(theme_name)
        if colors:
            palette = _make_palette_from_colors(colors)
        else:
            palette = QPalette(_original_system_palette)
    app.setPalette(palette)
    stylesheet = generator(palette)
    app.setStyleSheet(stylesheet)
    return palette

def apply_stylesheet_to_window(window, theme_name=None):
    """
    Applies the application's stylesheet and specific title bar styling
    to any given window (QMainWindow, QWidget, QDialog). Uses theme_name
    to pick the correct stylesheet generator from THEMES. Defaults to
    the last applied theme.
    """
    global _current_theme
    from .common_widgets import CustomTitleBar

    name = theme_name or _current_theme
    palette = _make_palette_from_colors(_get_json_colors(name)) if name != "System" and _get_json_colors(name) else window.palette()
    if name in THEMES:
        app_stylesheet = THEMES[name](palette)
    else:
        app_stylesheet = get_theme_stylesheet(palette)
    window.setStyleSheet(app_stylesheet)
    window.setPalette(palette)

    title_bar = window.findChild(CustomTitleBar, "CustomTitleBar")
    if title_bar:
        apply_theme_to_custom_title_bar(title_bar, palette)
