# FILE: gui/item_data.py
# PURPOSE: Defines data classes for items to be drawn using QPainter.

from PySide6.QtGui import QPixmap, QColor, QFontMetrics, QPainter, QPen
from PySide6.QtCore import QRect, Qt

class BaseItemData:
    def __init__(self, key: str, name: str, icon: QPixmap = None):
        self.key = key
        self.name = name
        self.icon = icon
        self.is_hovered = False
        self.is_selected = False # For future use if needed

    def set_icon(self, pixmap: QPixmap):
        self.icon = pixmap

    def draw(self, painter: QPainter, rect: QRect, is_hovered: bool, font_metrics: QFontMetrics, placeholder_icon: QPixmap):
        self.is_hovered = is_hovered
        
        # Draw background/hover effect
        if self.is_hovered:
            painter.fillRect(rect, QColor(60, 60, 60, 100)) # Semi-transparent dark background on hover

        # Draw Icon
        icon_size = 64
        icon_rect = QRect(
            rect.center().x() - icon_size // 2,
            rect.top() + (rect.height() - icon_size) // 3, # Position icon higher
            icon_size,
            icon_size
        )

        if self.icon and not self.icon.isNull():
            scaled_icon = self.icon.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(icon_rect.topLeft(), scaled_icon)
        else:
            scaled_placeholder = placeholder_icon.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(icon_rect.topLeft(), scaled_placeholder)

        # Draw Name
        text_rect = QRect(
            rect.left(),
            icon_rect.bottom() + 5, # 5 pixels below icon
            rect.width(),
            rect.height() - icon_rect.bottom() + rect.top() - 5 # Remaining height
        )
        
        # Ensure text is centered and ellipsized if too long
        elided_text = font_metrics.elidedText(self.name, Qt.TextElideMode.ElideMiddle, text_rect.width())
        painter.setPen(QPen(Qt.GlobalColor.white)) # Default text color
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, elided_text)

class AppItemData(BaseItemData):
    def __init__(self, key: str, name: str, pkg_name: str, icon: QPixmap = None, is_launcher_shortcut: bool = False):
        super().__init__(key, name, icon)
        self.pkg_name = pkg_name
        self.is_launcher_shortcut = is_launcher_shortcut
        self.metadata = {} # To store pinned status, custom icon, etc.

class WinlatorItemData(BaseItemData):
    def __init__(self, key: str, name: str, pkg: str, path: str, icon: QPixmap = None):
        super().__init__(key, name, icon)
        self.pkg = pkg # com.winlator.cmod, com.winlator, etc.
        self.path = path # Full path to the shortcut.exe
        self.metadata = {}
