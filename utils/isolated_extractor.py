# FILE: utils/isolated_extractor.py
# PURPOSE: Extrai ícones de arquivos executáveis (.exe) do Windows em um processo isolado.

import os
from utils import exe_icon_extractor

def extract_icon_in_process(exe_path, save_path, result_queue):
    """
    Extrai o ícone de um .exe em um processo separado e coloca o resultado em uma fila.
    """
    try:
        success = exe_icon_extractor.extract_icon_from_exe(exe_path, save_path)
        if success and os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            result_queue.put((True, save_path))
        else:
            result_queue.put((False, "Extraction failed or file is empty"))
    except Exception as e:
        result_queue.put((False, str(e)))