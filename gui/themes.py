# FILE: gui/themes.py
# PURPOSE: Centralizes theme management for the application.

from PySide6.QtGui import QPalette

def is_dark_theme(palette):
    """Checks if the provided palette corresponds to a dark theme."""
    return palette.color(QPalette.ColorRole.Window).value() < 128

def get_theme_stylesheet(palette):
    """
    Generates the full application stylesheet based on the system palette.
    """
    # Color derivation
    window_bg_qcolor = palette.color(QPalette.ColorRole.Window)
    main_bg_color = window_bg_qcolor.name()
    title_text_color = palette.color(QPalette.ColorRole.WindowText).name()
    border_color = window_bg_qcolor.darker(140).name() if not is_dark_theme(palette) else window_bg_qcolor.lighter(170).name()

    base_bg_qcolor = palette.color(QPalette.ColorRole.Base)
    base_bg_color = base_bg_qcolor.name()

    button_bg_color = palette.color(QPalette.ColorRole.Button).name()
    button_text_color = palette.color(QPalette.ColorRole.ButtonText).name()

    highlight_color = palette.color(QPalette.ColorRole.Highlight).name()
    highlighted_text_color = palette.color(QPalette.ColorRole.HighlightedText).name()

    alt_base_color = palette.color(QPalette.ColorRole.AlternateBase).name()
    mid_color = palette.color(QPalette.ColorRole.Mid).name()

    # Base stylesheet
    style = f"""
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
            margin-top: 7px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            color: {title_text_color};
            font-weight: bold;
            font-size: 11pt;
        }}
        QScrollArea {{
            border: none;
            background-color: transparent;
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
        QComboBox:focus, QComboBox:on {{
            border: 1px solid {highlight_color};
        }}
        QComboBox {{
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 1px 18px 1px 3px;
            min-width: 6em;
            min-height: 20px; /* Match height with QLineEdit search bar */
        }}
        QComboBox:editable {{
            background: {base_bg_color};
        }}
        QComboBox:!editable, QComboBox::drop-down:editable {{
             background: {base_bg_color};
        }}
        QComboBox:!editable:on, QComboBox::drop-down:editable:on {{
            background: {alt_base_color};
        }}
        QComboBox:on {{ /* shift the text when the popup opens */
            padding-top: 3px;
            padding-left: 4px;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left-width: 1px;
            border-left-color: {border_color};
            border-left-style: solid;
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
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
        /* --- Custom Widget Styles --- */
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
        /* --- End Custom Widget Styles --- */
    """
    return style

def apply_theme_to_custom_title_bar(title_bar, palette):
    """Applies specific styles to a CustomTitleBar."""
    title_text_color = palette.color(QPalette.ColorRole.WindowText).name()
    title_bar.title_label.setStyleSheet(f"color: {title_text_color}; padding-left: 10px; font-weight: bold; background-color: transparent;")


THEMES = {
    "System": get_theme_stylesheet
}

def get_available_themes():
    """Returns a list of available theme names."""
    return list(THEMES.keys())

def apply_theme(app, theme_name):
    """Applies a theme to the entire application."""
    if theme_name in THEMES:
        stylesheet_generator = THEMES[theme_name]
        palette = app.palette()
        stylesheet = stylesheet_generator(palette)
        app.setStyleSheet(stylesheet)
        return palette
    return None

def apply_stylesheet_to_window(window):
    """
    Applies the application's stylesheet and specific title bar styling
    to any given window (QMainWindow, QWidget, QDialog).
    """
    from .common_widgets import CustomTitleBar # Updated import

    app_palette = window.palette()
    app_stylesheet = get_theme_stylesheet(app_palette)
    window.setStyleSheet(app_stylesheet)

    # Find and style the custom title bar if it exists
    title_bar = window.findChild(CustomTitleBar, "CustomTitleBar")
    if title_bar:
        apply_theme_to_custom_title_bar(title_bar, app_palette)
