# FILE: gui/winlator_item_widget.py
# PURPOSE: Define o widget para um único item de jogo Winlator na grade, herdando de BaseItemWidget.

import os
from PySide6.QtWidgets import QPushButton, QMessageBox
from PySide6.QtCore import Qt, Signal
from .base_item_widget import BaseItemWidget

class WinlatorItemWidget(BaseItemWidget):
    # Sinais específicos para WinlatorItemWidget
    config_saved = Signal() # Sinal para notificar a aba que uma config foi salva
    config_deleted = Signal() # Sinal para notificar a aba que uma config foi deletada

    def __init__(self, game_info, app_config, placeholder_icon):
        # game_info deve ter 'name' e 'path'
        super().__init__({'key': game_info['path'], 'name': game_info['name']}, app_config, placeholder_icon, item_type="winlator_game")
        self.game_path = self.item_key
        self.game_name = self.item_name

        # Ajustes de estilo para Winlator (removendo sobrescrições de tamanho e negrito)
        # O tamanho do widget e do ícone agora são definidos pelo BaseItemWidget (75x110 e 32x32)
        self.name_label.setStyleSheet("font-size: 8pt;") # Removido font-weight: bold;

        # Adiciona botões específicos para WinlatorItemWidget ao action_layout do BaseItemWidget
        self.settings_button = QPushButton("⚙️")
        self.delete_button = QPushButton("🗑️")

        for btn in [self.settings_button, self.delete_button]:
            btn.setFixedSize(22, 22)

        # Remove os stretchers adicionados pelo BaseItemWidget e adiciona os próprios
        while self.action_layout.count() > 0:
            item = self.action_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                self.action_layout.removeItem(item)

        self.action_layout.addStretch()
        self.action_layout.addWidget(self.settings_button)
        self.action_layout.addWidget(self.delete_button)
        self.action_layout.addStretch()

        # Conexões
        self.settings_button.clicked.connect(self.save_game_config)
        self.delete_button.clicked.connect(self.delete_game_config)

    def save_game_config(self):
        current_scrcpy_config = self.app_config.get_all_values().copy()
        self.app_config.save_winlator_game_config(self.game_path, current_scrcpy_config)
        QMessageBox.information(self, "Configuração Salva", f"Configuração salva para {self.game_name}.")
        self.config_saved.emit()

    def delete_game_config(self):
        reply = QMessageBox.question(self, "Confirmar Exclusão",
                                     f"Tem certeza que deseja excluir a configuração salva para {self.game_name}?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.app_config.delete_winlator_game_config(self.game_path):
                QMessageBox.information(self, "Configuração Excluída", f"Configuração para {self.game_name} foi excluída.")
                self.config_deleted.emit()
            else:
                QMessageBox.warning(self, "Nenhuma Configuração", f"Nenhuma configuração específica foi encontrada para {self.game_name} para excluir.")