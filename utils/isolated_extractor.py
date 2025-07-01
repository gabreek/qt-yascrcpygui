# FILE: utils/isolated_extractor.py
# PURPOSE: Extrai ícones de arquivos executáveis (.exe) do Windows em um processo isolado.
#          Este script é chamado por subprocesso para isolar possíveis crashes nativos.

import sys
import os

from PIL import Image

# Adiciona o diretório pai ao sys.path para importar exe_icon_extractor
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import exe_icon_extractor

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python isolated_extractor.py <exe_path> <save_path>", file=sys.stderr)
        sys.exit(1)

    exe_path = sys.argv[1]
    save_path = sys.argv[2]

    try:
        print(f"[Isolated Extractor] Attempting to extract icon from: {exe_path} to {save_path}", flush=True)
        success = exe_icon_extractor.extract_icon_from_exe(exe_path, save_path)
        
        if success:
            # Verifica se o arquivo foi realmente criado e não está vazio
            if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                print(f"[Isolated Extractor] WARNING: Extracted icon file is empty or not created: {save_path}", flush=True)
                sys.exit(2) # Código de erro para arquivo vazio/não criado
            print(f"[Isolated Extractor] Icon extraction successful: {success}", flush=True)
            sys.exit(0) # Sucesso
        else:
            print(f"[Isolated Extractor] Icon extraction failed: {success}", flush=True)
            sys.exit(3) # Falha na extração

    except Exception as e:
        print(f"[Isolated Extractor] UNHANDLED EXCEPTION: {e}", file=sys.stderr, flush=True)
        sys.exit(4) # Erro inesperado
