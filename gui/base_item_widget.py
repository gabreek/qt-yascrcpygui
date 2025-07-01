# FILE: gui/base_item_widget.py
# PURPOSE: Widget base para itens de aplicativo/jogo, contendo lógica comum de UI e ícones.

import os
import shutil
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtGui import QPixmap, QCursor, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, Signal
from PIL import Image

class BaseItemWidget(QWidget):
    # Sinais genéricos que podem ser usados por subclasses
    launch_requested = Signal(str, str) # key, name (key pode ser pkg_name ou game_path)
    icon_dropped = Signal(str, str) # key, filepath

    def __init__(self, item_info, app_config, placeholder_icon, item_type="app"):
        super().__init__()
        self.item_info = item_info
        self.app_config = app_config
        self.item_key = item_info['key'] # Pode ser pkg_name ou game_path
        self.item_name = item_info['name']
        self.item_type = item_type # "app" ou "winlator_game"

        self.setAcceptDrops(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Tamanho e layout base
        self.setFixedSize(75, 110) # Tamanho padrão, subclasses podem ajustar
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 4, 2, 4)
        main_layout.setSpacing(4)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32) # Tamanho padrão, subclasses podem ajustar
        self.icon_label.setScaledContents(True)
        self.icon_label.setPixmap(placeholder_icon)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel(self.item_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("font-size: 8pt;") # Estilo padrão, subclasses podem ajustar
        self.name_label.setWordWrap(True)

        # Layout para botões de ação (subclasses adicionarão os botões específicos)
        self.action_layout = QHBoxLayout()

        main_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.name_label, 1)
        main_layout.addLayout(self.action_layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.launch_requested.emit(self.item_key, self.item_name)
            event.accept()

    def set_icon(self, pixmap):
        if not pixmap.isNull():
            self.icon_label.setPixmap(pixmap)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.ico')):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            source_path = event.mimeData().urls()[0].toLocalFile()
            cache_dir = self.app_config.get_icon_cache_dir()
            # Use o basename para evitar problemas com caminhos completos como item_key
            icon_filename = f"{os.path.basename(self.item_key)}.png"
            destination_path = os.path.join(cache_dir, icon_filename)
            try:
                img = Image.open(source_path).resize(self.icon_label.size().toTuple(), Image.LANCZOS)
                img.save(destination_path, 'PNG')
                # Salva metadados para o tipo de item correto
                if self.item_type == "app":
                    self.app_config.save_app_metadata(self.item_key, {'has_custom_icon': True, 'icon_fetch_failed': False})
                elif self.item_type == "winlator_game":
                    self.app_config.save_app_metadata(self.item_key, {'custom_icon': True, 'exe_icon_fetch_failed': False})

                self.set_icon(QPixmap(destination_path))
                self.icon_dropped.emit(self.item_key, source_path)
                QMessageBox.information(self, "Ícone Atualizado", f"Ícone personalizado definido para {self.item_name}.")
                event.acceptProposedAction()
            except Exception as e:
                print(f"Erro ao copiar ícone personalizado: {e}")
                QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao processar o ícone: {e}")
                event.ignore()
