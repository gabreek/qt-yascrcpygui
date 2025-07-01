# FILE: utils/isolated_extractor.py
# PURPOSE: Extrai ícones de arquivos executáveis (.exe) do Windows em um processo isolado.

import os
import extract_icon
from PIL import Image

def extract_icon_from_exe(exe_path, save_path, size=(48, 48)):
    """
    Extrai o ícone de melhor qualidade de um arquivo .exe.
    """
    try:
        extractor = extract_icon.ExtractIcon(exe_path)
        group_icons = extractor.get_group_icons()
        if not group_icons:
            return False
        icon_image = extractor.export(group_icons[0])
        if not icon_image:
            return False
        icon_image.resize(size, Image.LANCZOS).save(save_path, 'PNG')
        return True
    except Exception:
        return False

def extract_icon_in_process(exe_path, save_path, result_queue):
    """
    Extrai o ícone de um .exe em um processo separado e coloca o resultado em uma fila.
    """
    try:
        success = extract_icon_from_exe(exe_path, save_path)
        if success and os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            result_queue.put((True, save_path))
        else:
            result_queue.put((False, "Extraction failed or file is empty"))
    except Exception as e:
        result_queue.put((False, str(e)))
