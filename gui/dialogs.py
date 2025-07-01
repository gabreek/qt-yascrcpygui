# FILE: gui/dialogs.py
# PURPOSE: Contém funções auxiliares para exibir caixas de diálogo QMessageBox.

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

def show_message_box(parent, title, text, icon=QMessageBox.Information, buttons=QMessageBox.Ok, default_button=QMessageBox.Ok):
    """
    Exibe uma caixa de mensagem QMessageBox com configurações comuns.
    """
    msg_box = QMessageBox(parent)
    msg_box.setTextFormat(Qt.RichText)
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStandardButtons(buttons)
    msg_box.setDefaultButton(default_button)
    return msg_box.exec()