import os
import extract_icon
import subprocess
import shlex
from PIL import Image

def extract_icon_from_exe(exe_path, save_path, device_id=None, size=(128, 128)):
    """
    Extrai o ícone. Se o caminho for remoto (Android), faz o pull temporário.
    """
    temp_exe = None

    try:
        # Se o caminho começa com /storage, ele está no Android
        if exe_path.startswith('/storage/') or exe_path.startswith('/sdcard/'):
            if not device_id:
                return False

            # 1. Checa o tamanho do arquivo no Android primeiro
            quoted_exe_path = shlex.quote(exe_path)
            size_cmd = ['adb', '-s', device_id, 'shell', f'stat -c%s {quoted_exe_path} 2>/dev/null']
            try:
                res = subprocess.check_output(size_cmd, text=True).strip()
                remote_size = int(res) if res.isdigit() else 0
            except:
                remote_size = 0

            # Criamos um arquivo temporário para o extrator ler
            temp_exe = f"{save_path}_temp_exe"

            # 2. Define estratégia de pull:
            # Se o arquivo for "pequeno" (ex: < 100MB), puxamos tudo para garantir 100% de sucesso.
            # Se for grande (jogos de GBs), puxamos apenas os primeiros 100MB.
            pull_limit_mb = 100
            if remote_size > 0 and remote_size < pull_limit_mb * 1024 * 1024:
                # Arquivo pequeno: Puxamos tudo (mais rápido e seguro para o pefile)
                cmd = ['adb', '-s', device_id, 'exec-out', f'cat {quoted_exe_path}']
            else:
                # Arquivo grande: Puxamos apenas o início
                cmd = ['adb', '-s', device_id, 'exec-out', f'dd if={quoted_exe_path} bs=1M count={pull_limit_mb} 2>/dev/null']
            
            try:
                with open(temp_exe, 'wb') as f:
                    subprocess.run(cmd, stdout=f, check=True)
            except subprocess.CalledProcessError:
                return False

            if not os.path.exists(temp_exe) or os.path.getsize(temp_exe) == 0:
                return False

            target_to_read = temp_exe
        else:
            target_to_read = exe_path

        if not os.path.exists(target_to_read) or os.path.getsize(target_to_read) == 0:
            return False

        # Lógica de extração original
        extractor = extract_icon.ExtractIcon(target_to_read)
        group_icons = extractor.get_group_icons()

        if not group_icons:
            return False

        icon_image = extractor.export(group_icons[0])
        if not icon_image:
            return False

        icon_image.resize(size, Image.Resampling.LANCZOS).save(save_path, 'PNG')
        return True

    except Exception as e:
        print(f"[IsolatedExtractor] Erro ao extrair de {exe_path}: {e}")
        return False

    finally:
        # Limpa o "pedaço" de .exe que baixamos
        if temp_exe and os.path.exists(temp_exe):
            try:
                os.remove(temp_exe)
            except:
                pass

def extract_icon_in_process(exe_path, save_path, result_queue, device_id=None):
    """
    Extrai o ícone passando o device_id para o processo isolado.
    """
    try:
        success = extract_icon_from_exe(exe_path, save_path, device_id=device_id)
        if success and os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            result_queue.put((True, save_path))
        else:
            result_queue.put((False, "Extraction failed or file is empty"))
    except Exception as e:
        result_queue.put((False, str(e)))
