# FILE: utils/constants.py
# PURPOSE: Centralizes hardcoded strings, configuration keys, and translations for i18n.

# --- Configuration Keys ---
CONF_DEVICE_ID = 'device_id'
CONF_THEME = 'theme'
CONF_LANGUAGE = 'language'
CONF_DEVICE_COMMERCIAL_NAME = 'device_commercial_name'
CONF_START_APP = 'start_app'
CONF_START_APP_NAME = 'start_app_name'
CONF_DEFAULT_LAUNCHER = 'default_launcher'
CONF_MOUSE_MODE = 'mouse_mode'
CONF_GAMEPAD_MODE = 'gamepad_mode'
CONF_KEYBOARD_MODE = 'keyboard_mode'
CONF_MOUSE_BIND = 'mouse_bind'
CONF_RENDER_DRIVER = 'render_driver'
CONF_MAX_FPS = 'max_fps'
CONF_MAX_SIZE = 'max_size'
CONF_DISPLAY = 'display'
CONF_NEW_DISPLAY = 'new_display'
CONF_VIDEO_CODEC = 'video_codec'
CONF_VIDEO_ENCODER = 'video_encoder'
CONF_AUDIO_CODEC = 'audio_codec'
CONF_AUDIO_ENCODER = 'audio_encoder'
CONF_ALLOW_FRAME_DROP = 'allow_frame_drop'
CONF_LOW_LATENCY = 'low_latency'
CONF_PRIORITY_MODE = 'priority_mode'
CONF_BITRATE_MODE = 'bitrate_mode'
CONF_COLOR_RANGE = 'color_range'
CONF_IFRAME_INTERVAL = 'iframe_interval'
CONF_EXTRAARGS = 'extraargs'
CONF_STAY_AWAKE = 'stay_awake'
CONF_MIPMAPS = 'mipmaps'
CONF_TURN_SCREEN_OFF = 'turn_screen_off'
CONF_FULLSCREEN = 'fullscreen'
CONF_USE_LUDASHI_PKG = 'use_ludashi_pkg'
CONF_NO_AUDIO = 'no_audio'
CONF_NO_VIDEO = 'no_video'
CONF_VIDEO_BITRATE_SLIDER = 'video_bitrate_slider'
CONF_AUDIO_BUFFER = 'audio_buffer'
CONF_AUDIO_BITRATE_SLIDER = 'audio_bitrate_slider'
CONF_VIDEO_BUFFER = 'video_buffer'
CONF_TRY_UNLOCK = 'try_unlock'
ALTERNATE_LAUNCH_METHOD = 'alternate_launch_method'
CONF_WINDOWING_MODE = 'windowing_mode'
CONF_SHOW_SYSTEM_APPS = 'show_system_apps'
CONF_START_WEB_SERVER_ON_LAUNCH = 'start_web_server_on_launch'

# --- Structural Config Keys ---
CONF_GENERAL_CONFIG = 'general_config'
CONF_APP_METADATA = 'app_metadata'
CONF_WINLATOR_GAME_CONFIGS = 'winlator_game_configs'
CONF_ENCODER_CACHE = 'encoder_cache'
CONF_APP_LIST_CACHE = 'app_list_cache'

# --- Translations ---
TRANSLATIONS = {
    'en': {
        'common': {
            'ok': 'OK', 'cancel': 'Cancel', 'yes': 'Yes', 'no': 'No',
            'success': 'Success', 'error': 'Error', 'warning': 'Warning',
            'info': 'Information', 'close': 'Close', 'confirm': 'Confirm',
            'loading': 'Loading...',
            'adb_missing': "Command 'adb' not found. Please install Android Platform Tools and add it to your system's PATH.",
            'scrcpy_missing': "Command 'scrcpy' not found. Please install scrcpy and ensure it is in your system's PATH.",
        },
        'main': {
            'title': 'yaScrcpy',
            'tabs': {'apps': 'Apps', 'winlator': 'Winlator', 'config': 'Config'},
            'wifi_btn_tooltip': 'ADB over WiFi',
            'session_manager_tooltip': 'Session Manager',
            'loading_msg': 'Please wait, loading...',
            'device_error_title': 'Device Error',
            'no_device_msg': 'No device connected.',
            'device_locked': 'Device Locked',
            'enter_pin': 'Enter PIN to unlock:',
            'unlock_skipped': 'No PIN entered. Attempting to launch on locked device.',
            'launch_cancelled': 'Unlock process was cancelled by the user.',
        },
        'scrcpy_tab': {
            'groups': {
                'yascrcpy': 'yaScrcpy',
                'device_status': 'Device Status',
                'profile': 'Configuration Profile',
                'general': 'General Settings',
                'video': 'Video Settings',
                'audio': 'Audio Settings',
                'options': 'Options',
            },
            'labels': {
                'theme': 'Theme',
                'language': 'Language',
                'show_system_apps': 'Show System Apps',
                'web_server': 'Web Server',
                'checking_status': 'Checking device status...',
                'please_connect': 'Please connect a device.',
                'connected_to': 'Connected to {name} (Battery: {battery}%)',
                'fetching_info': 'Fetching device info...',
                'fetching_encoders': 'Fetching encoders...',
                'global_config': 'Global Config',
                'window_mode': 'Window Mode',
                'mouse_mode': 'Mouse Mode',
                'gamepad_mode': 'Gamepad Mode',
                'keyboard_mode': 'Keyboard Mode',
                'mouse_bind': 'Mouse Bind',
                'max_fps': 'Max FPS',
                'virtual_display': 'Virtual Display',
                'max_size': 'Max Size',
                'extra_args': 'Extra Args',
                'codec': 'Codec',
                'encoder': 'Encoder',
                'render_driver': 'Render Driver',
                'color_range': 'Color Range',
                'frame_drop': 'Frame Drop',
                'low_latency': 'Low Latency',
                'priority': 'Priority',
                'bitrate_mode': 'Bitrate Mode',
                'iframe_interval': 'I-frame Interval',
                'video_buffer': 'Video Buffer',
                'video_bitrate': 'Video Bitrate',
                'audio_buffer': 'Audio Buffer',
                'audio_bitrate': 'Audio Bitrate',
                'fetch_encoders_error': 'Could not fetch encoders: {error}',
            },
            'options': {
                'fullscreen': 'Fullscreen',
                'turn_screen_off': 'Turn screen off',
                'stay_awake': 'Stay Awake',
                'disable_mipmaps': 'Disable mipmaps',
                'no_audio': 'No Audio',
                'no_video': 'No Video',
                'unlock_device': 'Unlock device',
                'alternate_launch': 'Alternate Launch Method',
            }
        },
        'apps_tab': {
            'search_placeholder': 'Search apps...',
            'refresh_btn': 'Refresh Apps',
            'loading_from_device': 'Loading apps from device...',
            'no_apps': 'No applications to display.',
            'empty_list': "App list is empty. Click 'Refresh Apps'.",
            'pinned_section': 'Pinned Apps',
            'all_section': 'All Apps',
            'delete_config_title': 'Delete Configuration',
            'delete_config_msg': 'Are you sure you want to delete the specific configuration for<br><b>{name}</b>?',
            'delete_success': 'Specific configuration for {name} has been deleted.',
            'delete_not_found': 'No specific configuration was found for {name}.',
            'settings_saved': 'Current settings have been saved as a specific configuration for <b>{name}</b>.',
            'virtual_display_warn_title': 'Virtual Display Incompatibility',
            'virtual_display_warn_msg': "Saving a specific configuration for the Launcher while a global virtual display is active is not recommended.\n\nWould you like to save a specific configuration for the Launcher with 'Max Size' set to 0 (native resolution) instead?",
            'action_cancelled_title': 'Action Cancelled',
            'action_cancelled_msg': "No specific configuration was saved for the Launcher.\n\nTo use the Launcher without a virtual display, please go to the 'Scrcpy' tab, set 'Virtual Display' to 'Disabled', and select a desired 'Max Size'.",
            'downloading_icons': 'Downloading missing app icons...',
            'custom_icon_success_title': 'Success',
            'custom_icon_success_msg': 'Custom icon has been set.',
            'custom_icon_error_title': 'Error',
            'custom_icon_error_msg': 'Could not save the icon for {pkg}: {error}',
            'invalid_image_error': 'Invalid file. Please drop a valid image file (PNG, JPG, BMP, GIF).',
            'virtual_display_error': 'Virtual display not found for alternate launch.',
            'app_launch_error_title': 'App Launch Error',
            'scrcpy_error_title': 'Scrcpy Error',
            'winlator_launch_error_title': 'Winlator Launch Error',
        },
        'winlator_tab': {
            'refresh_btn': 'Refresh Apps',
            'refresh_icons_btn': 'Refresh Icons',
            'searching_games': 'Searching for games...',
            'no_shortcuts': 'No Winlator shortcut found on device.\nPlease export to frontend in Winlator app.',
            'extracting_icons': 'Extracting Icons',
            'processing_icons': 'Processing {current} of {total}...',
            'extraction_finished': 'Icons extraction finished!',
            'search_icons_title': 'Search missing icons?',
            'search_icons_msg': '{count} games without icons.\n\nThis process may take several minutes.\n\nWish to continue?',
            'delete_config_title': 'Confirm Deletion',
            'delete_config_msg': 'Are you sure you want to delete the saved configuration for {name}?',
            'config_saved': 'Configuration saved for {name}.',
        },
        'adb_wifi': {
             'title': 'ADB over Wifi',
             'placeholder': 'IP:Port (e.g., 192.168.1.100:5555)',
             'connect_btn': 'Connect',
             'initial_msg': 'Enter the device IP and port.',
             'empty_error': 'IP:Port cannot be empty.',
             'connecting': 'Connecting to {address}...',
        },
        'session_manager': {
            'title': 'Active Scrcpy Sessions',
            'kill_btn': 'Kill',
            'check_command_btn': 'Check Command',
            'no_sessions': 'No active Scrcpy sessions.',
            'confirm_kill_title': 'Confirm Termination',
            'confirm_kill_msg': 'Are you sure you want to terminate {name} (PID: {pid})?',
            'kill_success': 'Scrcpy session for {name} terminated.',
            'kill_error': 'Could not terminate Scrcpy session for {name} (PID: {pid}).',
            'command_title': 'Command for {name}',
        },
        'web_server_config': {
            'title': 'Web Server Configuration',
            'start_on_launch': 'Start web server on application launch',
            'server_status': 'Server Status:',
            'stopped': 'Stopped',
            'running': 'Running',
            'start_btn': 'Start Server',
            'stop_btn': 'Stop Server',
            'address_label': 'Server Address:',
            'not_running': 'Not Running',
        },
        'api': {
            'config_saved': 'Configuration saved.',
            'text_input_sent': 'Text input command sent.',
            'key_event_sent': "Key command '{key}' sent.",
            'app_pinned': "App '{pkg}' pinned.",
            'app_unpinned': "App '{pkg}' unpinned.",
            'launch_sent': "Launch command sent for {name}.",
            'session_killed': "Session with PID {pid} terminated.",
            'session_not_found': "Session with PID {pid} not found or could not be terminated.",
            'error_adb_connect': 'Internal error while connecting via ADB.',
            'error_pin': 'Internal error while pinning/unpinning app.',
            'error_text_input': 'Internal error while sending text input.',
            'error_key_event': 'Internal error while sending key event.',
            'error_get_config': 'Internal error while retrieving configuration.',
            'error_set_config': 'Internal error while saving configuration.',
            'error_list_devices': 'Internal error while listing devices.',
            'error_device_details': 'Internal error while getting device details.',
            'error_list_apps': 'Internal error while listing apps.',
            'error_list_winlator': 'Internal error while listing Winlator apps.',
            'error_launch': 'Internal error while launching application.',
            'error_launch_winlator': 'Internal error while launching Winlator application.',
            'error_kill_session': 'Internal error while killing scrcpy session.',
        }
    },
    'pt': {
        'common': {
            'ok': 'OK', 'cancel': 'Cancelar', 'yes': 'Sim', 'no': 'Não',
            'success': 'Sucesso', 'error': 'Erro', 'warning': 'Aviso',
            'info': 'Informação', 'close': 'Fechar', 'confirm': 'Confirmar',
            'loading': 'Carregando...',
            'adb_missing': "Comando 'adb' não encontrado. Por favor, instale o Android Platform Tools e adicione-o ao PATH do seu sistema.",
            'scrcpy_missing': "Comando 'scrcpy' não encontrado. Por favor, instale o scrcpy e certifique-se de que ele esteja no PATH do seu sistema.",
        },
        'main': {
            'title': 'yaScrcpy',
            'tabs': {'apps': 'Apps', 'winlator': 'Winlator', 'config': 'Config'},
            'wifi_btn_tooltip': 'ADB via WiFi',
            'session_manager_tooltip': 'Gerenciador de Sessões',
            'loading_msg': 'Por favor aguarde, carregando...',
            'device_error_title': 'Erro de Dispositivo',
            'no_device_msg': 'Nenhum dispositivo conectado.',
            'device_locked': 'Dispositivo Bloqueado',
            'enter_pin': 'Digite o PIN para desbloquear:',
            'unlock_skipped': 'Nenhum PIN inserido. Tentando iniciar no dispositivo bloqueado.',
            'launch_cancelled': 'O processo de desbloqueio foi cancelado pelo usuário.',
        },
        'scrcpy_tab': {
            'groups': {
                'yascrcpy': 'yaScrcpy',
                'device_status': 'Status do Dispositivo',
                'profile': 'Perfil de Configuração',
                'general': 'Configurações Gerais',
                'video': 'Configurações de Vídeo',
                'audio': 'Configurações de Áudio',
                'options': 'Opções',
            },
            'labels': {
                'theme': 'Tema',
                'language': 'Idioma',
                'show_system_apps': 'Mostrar Apps de Sistema',
                'web_server': 'Servidor Web',
                'checking_status': 'Verificando status do dispositivo...',
                'please_connect': 'Por favor, conecte um dispositivo.',
                'connected_to': 'Conectado a {name} (Bateria: {battery}%)',
                'fetching_info': 'Buscando informações do dispositivo...',
                'fetching_encoders': 'Buscando encoders...',
                'global_config': 'Configuração Global',
                'window_mode': 'Modo de Janela',
                'mouse_mode': 'Modo do Mouse',
                'gamepad_mode': 'Modo do Gamepad',
                'keyboard_mode': 'Modo do Teclado',
                'mouse_bind': 'Vínculo do Mouse',
                'max_fps': 'FPS Máximo',
                'virtual_display': 'Display Virtual',
                'max_size': 'Tamanho Máximo',
                'extra_args': 'Args Extras',
                'codec': 'Codec',
                'encoder': 'Encoder',
                'render_driver': 'Driver de Renderização',
                'color_range': 'Faixa de Cores',
                'frame_drop': 'Pular Quadros',
                'low_latency': 'Baixa Latência',
                'priority': 'Prioridade',
                'bitrate_mode': 'Modo de Bitrate',
                'iframe_interval': 'Intervalo de I-frame',
                'video_buffer': 'Buffer de Vídeo',
                'video_bitrate': 'Bitrate de Vídeo',
                'audio_buffer': 'Buffer de Áudio',
                'audio_bitrate': 'Bitrate de Áudio',
                'fetch_encoders_error': 'Não foi possível buscar encoders: {error}',
            },
            'options': {
                'fullscreen': 'Tela Cheia',
                'turn_screen_off': 'Desligar tela',
                'stay_awake': 'Manter Acordado',
                'disable_mipmaps': 'Desativar mipmaps',
                'no_audio': 'Sem Áudio',
                'no_video': 'Sem Vídeo',
                'unlock_device': 'Desbloquear dispositivo',
                'alternate_launch': 'Método de Lançamento Alternativo',
            }
        },
        'apps_tab': {
            'search_placeholder': 'Pesquisar apps...',
            'refresh_btn': 'Atualizar Apps',
            'loading_from_device': 'Carregando apps do dispositivo...',
            'no_apps': 'Nenhum aplicativo para exibir.',
            'empty_list': "A lista de apps está vazia. Clique em 'Atualizar Apps'.",
            'pinned_section': 'Apps Fixados',
            'all_section': 'Todos os Apps',
            'delete_config_title': 'Excluir Configuração',
            'delete_config_msg': 'Tem certeza que deseja excluir a configuração específica para<br><b>{name}</b>?',
            'delete_success': 'Configuração específica para {name} foi excluída.',
            'delete_not_found': 'Nenhuma configuração específica foi encontrada para {name}.',
            'settings_saved': 'As configurações atuais foram salvas como uma configuração específica para <b>{name}</b>.',
            'virtual_display_warn_title': 'Incompatibilidade de Display Virtual',
            'virtual_display_warn_msg': "Salvar uma configuração específica para o Launcher enquanto um display virtual global está ativo não é recomendado.\n\nDeseja salvar uma configuração específica para o Launcher com 'Tamanho Máximo' definido como 0 (resolução nativa) em vez disso?",
            'action_cancelled_title': 'Ação Cancelada',
            'action_cancelled_msg': "Nenhuma configuração específica foi salva para o Launcher.\n\nPara usar o Launcher sem um display virtual, vá para a aba 'Scrcpy', defina 'Display Virtual' como 'Desativado' e selecione o 'Tamanho Máximo' desejado.",
            'downloading_icons': 'Baixando ícones de apps ausentes...',
            'custom_icon_success_title': 'Sucesso',
            'custom_icon_success_msg': 'O ícone personalizado foi definido.',
            'custom_icon_error_title': 'Erro',
            'custom_icon_error_msg': 'Não foi possível salvar o ícone para {pkg}: {error}',
            'invalid_image_error': 'Arquivo inválido. Por favor, arraste um arquivo de imagem válido (PNG, JPG, BMP, GIF).',
            'virtual_display_error': 'Display virtual não encontrado para lançamento alternativo.',
            'app_launch_error_title': 'Erro de Lançamento de App',
            'scrcpy_error_title': 'Erro do Scrcpy',
            'winlator_launch_error_title': 'Erro de Lançamento do Winlator',
        },
        'winlator_tab': {
            'refresh_btn': 'Atualizar Apps',
            'refresh_icons_btn': 'Atualizar Ícones',
            'searching_games': 'Buscando jogos...',
            'no_shortcuts': 'Nenhum atalho do Winlator encontrado no dispositivo.\nPor favor, exporte para o frontend no app Winlator.',
            'extracting_icons': 'Extraindo Ícones',
            'processing_icons': 'Processando {current} de {total}...',
            'extraction_finished': 'Extração de ícones finalizada!',
            'search_icons_title': 'Buscar ícones ausentes?',
            'search_icons_msg': '{count} jogos sem ícones.\n\nEste processo pode levar alguns minutos.\n\nDeseja continuar?',
            'delete_config_title': 'Confirmar Exclusão',
            'delete_config_msg': 'Tem certeza que deseja excluir a configuração salva para {name}?',
            'config_saved': 'Configuração salva para {name}.',
        },
        'adb_wifi': {
             'title': 'ADB via Wifi',
             'placeholder': 'IP:Porta (ex: 192.168.1.100:5555)',
             'connect_btn': 'Conectar',
             'initial_msg': 'Insira o IP e a porta do dispositivo.',
             'empty_error': 'IP:Porta não pode estar vazio.',
             'connecting': 'Conectando a {address}...',
        },
        'session_manager': {
            'title': 'Sessões Ativas do Scrcpy',
            'kill_btn': 'Finalizar',
            'check_command_btn': 'Verificar Comando',
            'no_sessions': 'Nenhuma sessão ativa do Scrcpy.',
            'confirm_kill_title': 'Confirmar Encerramento',
            'confirm_kill_msg': 'Tem certeza que deseja encerrar {name} (PID: {pid})?',
            'kill_success': 'Sessão do Scrcpy para {name} encerrada.',
            'kill_error': 'Não foi possível encerrar a sessão do Scrcpy para {name} (PID: {pid}).',
            'command_title': 'Comando para {name}',
        },
        'web_server_config': {
            'title': 'Configuração do Servidor Web',
            'start_on_launch': 'Iniciar servidor web ao abrir o aplicativo',
            'server_status': 'Status do Servidor:',
            'stopped': 'Parado',
            'running': 'Executando',
            'start_btn': 'Iniciar Servidor',
            'stop_btn': 'Parar Servidor',
            'address_label': 'Endereço do Servidor:',
            'not_running': 'Não está em execução',
        },
        'api': {
            'config_saved': 'Configuração salva.',
            'text_input_sent': 'Comando de entrada de texto enviado.',
            'key_event_sent': "Comando de tecla '{key}' enviado.",
            'app_pinned': "App '{pkg}' fixado.",
            'app_unpinned': "App '{pkg}' desfixado.",
            'launch_sent': "Comando de lançamento enviado para {name}.",
            'session_killed': "Sessão com PID {pid} encerrada.",
            'session_not_found': "Sessão com PID {pid} não encontrada ou não pôde ser encerrada.",
            'error_adb_connect': 'Erro interno ao conectar via ADB.',
            'error_pin': 'Erro interno ao fixar/desfixar app.',
            'error_text_input': 'Erro interno ao enviar entrada de texto.',
            'error_key_event': 'Erro interno ao enviar evento de tecla.',
            'error_get_config': 'Erro interno ao recuperar configuração.',
            'error_set_config': 'Erro interno ao salvar configuração.',
            'error_list_devices': 'Erro interno ao listar dispositivos.',
            'error_device_details': 'Erro interno ao buscar detalhes do dispositivo.',
            'error_list_apps': 'Erro interno ao listar apps.',
            'error_list_winlator': 'Erro interno ao listar apps Winlator.',
            'error_launch': 'Erro interno ao lançar aplicativo.',
            'error_launch_winlator': 'Erro interno ao lançar aplicativo Winlator.',
            'error_kill_session': 'Erro interno ao encerrar sessão scrcpy.',
        }
    }
}
