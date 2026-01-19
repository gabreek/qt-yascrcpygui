# FILE: gui/base_item_widget.py
# PURPOSE: Widget base para itens de aplicativo/jogo, contendo lógica comum de UI e ícones.

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QGridLayout, QGraphicsOpacityEffect
from PySide6.QtGui import QPixmap, QCursor, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PIL import Image

class BaseItemWidget(QWidget):
    # Sinais genéricos que podem ser usados por subclasses
    launch_requested = Signal(str, str) # key, name (key pode ser pkg_name ou game_path)
    icon_dropped = Signal(str, str) # key, filepath

    def __init__(self, item_info, app_config, placeholder_icon, item_type="app"):
        super().__init__()
        self.item_info = item_info
        self.app_config = app_config
        self.item_key = item_info['key']
        self.item_name = item_info['name']
        self.item_type = item_type

        self.setAcceptDrops(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Tamanho ajustado para garantir espaço para o nome e o overlay
        self.setFixedSize(80, 105)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(4)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Área do Ícone com Overlay ---
        self.icon_container = QWidget()
        self.icon_container.setFixedHeight(52)
        icon_layout = QGridLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setScaledContents(True)
        self.icon_label.setPixmap(placeholder_icon)

        # Container para os botões de ação (o overlay)
        self.action_buttons_container = QWidget()
        self.action_buttons_container.setFixedHeight(22)
        self.action_layout = QHBoxLayout(self.action_buttons_container)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(2)

        # Configuração do efeito de opacidade e animação
        self.opacity_effect = QGraphicsOpacityEffect(self.action_buttons_container)
        self.action_buttons_container.setGraphicsEffect(self.opacity_effect)
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(150) # Duração de 150ms
        self.opacity_animation.setEasingCurve(QEasingCurve.InOutQuad)
        # Define os valores de início e fim uma vez
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_effect.setOpacity(0.0) # Começa invisível

        # Adiciona o ícone e os botões, alinhando-os para criar o efeito de sobreposição
        icon_layout.addWidget(self.icon_label, 0, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        icon_layout.addWidget(self.action_buttons_container, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        # --- Fim da Área do Ícone ---

        self.name_label = QLabel(self.item_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setObjectName("item_name_label")
        self.name_label.setWordWrap(True)

        self.main_layout.addWidget(self.icon_container, 0, Qt.AlignmentFlag.AlignHCenter)
        self.main_layout.addWidget(self.name_label)
        self.main_layout.addStretch()

        self.adjust_font_size()

    def adjust_font_size(self):
        font_size = 8 # Start with 8pt
        # Styling for font size is now handled by themes.py using objectName "item_name_label"

        # Calculate available width for the text (widget width - margins)
        available_width = self.width() - self.main_layout.contentsMargins().left() - self.main_layout.contentsMargins().right()

        # Calculate maximum allowed height for the name_label
        # Total widget height (100) - icon_container height (52) - main_layout spacing (4) - top/bottom margins (2+2) = 40
        # This is an approximation, adjust if needed based on visual inspection
        max_name_label_height = self.height() - self.icon_container.height() - self.main_layout.spacing() - self.main_layout.contentsMargins().top() - self.main_layout.contentsMargins().bottom()

        # No need to set font size here, it's controlled by stylesheet.
        # This loop is primarily for logic to determine if text fits.
        while True:
            metrics = self.name_label.fontMetrics()
            # Calculate bounding rect with word wrap enabled
            rect = metrics.boundingRect(0, 0, available_width, 0, Qt.TextWordWrap, self.item_name)
            text_height = rect.height()

            if text_height <= max_name_label_height or font_size <= 6: # Minimum font size
                break
            
            font_size -= 0.8 # Decrease by 0.5pt
            # In a real scenario, you might adjust a font property directly
            # self.name_label.font().setPointSize(font_size)
            # but for stylesheet-driven font-size, this loop primarily determines if text fits.
            # We're relying on the stylesheet to pick up the default font size and scaling.
            # For dynamic font size based on fitting, setFont() would be preferred over stylesheet in a loop.
            # For simplicity, we'll assume the stylesheet provides a reasonable default and `text_height` calculation is enough for layout.


    def _create_action_button(self, icon_text):
        """Cria um botão de ação padronizado."""
        button = QPushButton(icon_text)
        button.setFixedSize(22, 22)
        button.setObjectName("item_action_button")
        return button

    def enterEvent(self, event):
        """Inicia a animação de fade-in."""
        self.opacity_animation.setDirection(QPropertyAnimation.Forward)
        if self.opacity_animation.state() != QPropertyAnimation.Running:
            self.opacity_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Inicia a animação de fade-out."""
        self.opacity_animation.setDirection(QPropertyAnimation.Backward)
        if self.opacity_animation.state() != QPropertyAnimation.Running:
            self.opacity_animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.launch_requested.emit(self.item_key, self.item_name)
            event.accept()

    def set_icon(self, pixmap):
        if not pixmap.isNull():
            self.icon_label.setPixmap(pixmap)

    def clear_icon(self):
        """Clears the icon displayed on the QLabel to free up memory."""
        self.icon_label.setPixmap(QPixmap()) # Set an empty QPixmap

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.ico')):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            source_path = event.mimeData().urls()[0].toLocalFile()
            cache_dir = self.app_config.get_icon_cache_dir()
            icon_filename = f"{os.path.basename(self.item_key)}.png"
            destination_path = os.path.join(cache_dir, icon_filename)
            try:
                img = Image.open(source_path).resize(self.icon_label.size().toTuple(), Image.LANCZOS)
                img.save(destination_path, 'PNG')
                if self.item_type == "app":
                    self.app_config.save_app_metadata(self.item_key, {'has_custom_icon': True, 'icon_fetch_failed': False})
                elif self.item_type == "winlator_game":
                    self.app_config.save_app_metadata(self.item_key, {'custom_icon': True, 'exe_icon_fetch_failed': False})

                self.set_icon(QPixmap(destination_path))
                self.icon_dropped.emit(self.item_key, source_path)
                QMessageBox.information(self, "Ícone Atualizado", f"Ícone personalizado definido para {self.item_name}.")
                event.acceptProposedAction()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao processar o ícone: {e}")
                event.ignore()
