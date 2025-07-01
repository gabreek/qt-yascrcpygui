# FILE: utils/exe_icon_extractor.py
# PURPOSE: Extrai ícones de arquivos executáveis (.exe) do Windows.
# DEPENDENCIES: pip install extract-icon

import os
import extract_icon
from PIL import Image
from io import BytesIO


def extract_icon_from_exe(exe_path, save_path, size=(48, 48)):
    """
    Usa a classe ExtractIcon para extrair o ícone de melhor qualidade,
    conforme a estrutura da biblioteca instalada.
    """
    try:
        # 1. Instancia a classe ExtractIcon com o caminho do executável.
        extractor = extract_icon.ExtractIcon(exe_path)

        # 2. Obtém as informações sobre os grupos de ícones disponíveis.
        group_icons = extractor.get_group_icons()
        if not group_icons:
            print(f"Nenhum grupo de ícones encontrado em {os.path.basename(exe_path)}")
            return False

        # 3. Exporta o primeiro grupo de ícones.
        #    Isso retorna um objeto de imagem, não bytes.
        icon_image = extractor.export(group_icons[0])

        if not icon_image:
            print(f"Não foi possível exportar dados do ícone para {os.path.basename(exe_path)}")
            return False


        icon_image.resize(size, Image.LANCZOS).save(save_path, 'PNG')

        print(f"Ícone extraído com sucesso de {os.path.basename(exe_path)}")
        return True

    except Exception as e:
        print(f"Falha ao extrair ícone de {os.path.basename(exe_path)}: {e}")
        return False
