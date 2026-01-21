import uvicorn
from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from utils import adb_handler, scrcpy_handler
from app_config import AppConfig
import os
import shlex

app = FastAPI()

# Mount the icon cache directory as a static path
try:
    app_config_for_path = AppConfig(None)
    icon_cache_dir = app_config_for_path.get_icon_cache_dir()
    if os.path.exists(icon_cache_dir):
        app.mount("/icons", StaticFiles(directory=icon_cache_dir), name="icons")
except Exception as e:
    print(f"Could not mount icon cache directory: {e}")

# Mount the gui directory for placeholder images
try:
    gui_assets_dir = os.path.join(os.path.dirname(__file__), 'gui')
    if os.path.exists(gui_assets_dir):
        app.mount("/gui_assets", StaticFiles(directory=gui_assets_dir), name="gui_assets")
except Exception as e:
    print(f"Could not mount GUI assets directory: {e}")

class LaunchRequest(BaseModel):
    device_id: str
    pkg_name: str
    app_name: str

class WinlatorLaunchRequest(BaseModel):
    device_id: str
    shortcut_path: str
    app_name: str
    pkg_name: str

class ConfigRequest(BaseModel):
    device_id: str
    pkg_name: str
    config_data: Dict[str, Any]

class TextInputRequest(BaseModel):
    device_id: str
    text: str

class KeyEventRequest(BaseModel):
    device_id: str
    key_command: str

class AdbConnectRequest(BaseModel):
    address: str

class PinRequest(BaseModel):
    device_id: str
    pkg_name: str
    pinned: bool


KEY_COMMAND_MAP = {
    "HOME": "KEYCODE_HOME",
    "BACK": "KEYCODE_BACK",
    "APP_SWITCH": "KEYCODE_APP_SWITCH",
    "VOLUME_UP": "KEYCODE_VOLUME_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN",
    "POWER": "KEYCODE_POWER",
}

def get_config_for_device(device_id: str):
    """Initializes AppConfig and loads the configuration for a specific device."""
    app_config = AppConfig(None)
    configuration_id = device_id
    if ':' in device_id:  # It's a Wi-Fi device
        serial_no = adb_handler.get_serial_from_wifi_device(device_id)
        if serial_no:
            configuration_id = serial_no
    app_config.load_config_for_device(configuration_id)
    app_config.connection_id = device_id  # Ensure connection_id is set for subsequent operations
    return app_config

@app.post("/api/adb/connect", summary="Connect to a device via ADB over WiFi")
async def adb_connect(request: AdbConnectRequest):
    """Connects to an ADB device over WiFi."""
    try:
        result = adb_handler.connect_wifi(request.address)
        if "connected" in result or "already connected" in result:
            return {"status": "success", "message": result}
        else:
            raise HTTPException(status_code=400, detail=result or "Failed to connect.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/app/pin", summary="Pin or unpin an application")
async def pin_app(request: PinRequest):
    """Pins or unpins an application for the current device."""
    try:
        app_config = get_config_for_device(request.device_id)
        app_config.save_app_metadata(request.pkg_name, {'pinned': request.pinned})
        return {"status": "success", "message": f"App '{request.pkg_name}' {'pinned' if request.pinned else 'unpinned'}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/input/text")
async def text_input(request: TextInputRequest):
    """Types the given text on the device."""
    try:
        adb_handler._run_adb_command(['shell', 'input', 'text', shlex.quote(request.text)], request.device_id)
        return {"status": "success", "message": "Text input command sent."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/input/keyevent")
async def key_event(request: KeyEventRequest):
    """Sends a key event to the device."""
    try:
        keycode = KEY_COMMAND_MAP.get(request.key_command.upper())
        if not keycode:
            raise HTTPException(status_code=400, detail="Invalid key command.")

        adb_handler._run_adb_command(['shell', 'input', 'keyevent', keycode], request.device_id)
        return {"status": "success", "message": f"Key command '{request.key_command}' sent."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import base64

@app.get("/api/config")
async def get_config(device_id: str, profile_key: str, b64: bool = False):
    """Retrieves the configuration for a specific app on a device."""
    try:
        decoded_key = profile_key
        if b64:
            decoded_key = base64.b64decode(profile_key).decode('utf-8')

        app_config = get_config_for_device(device_id)
        
        # Use the AppConfig's internal profile loading mechanism, which is known to work
        app_config.load_profile(decoded_key)

        # Define all keys that the frontend form uses
        config_keys = [
            'windowing_mode', 'mouse_mode', 'gamepad_mode', 'keyboard_mode', 'mouse_bind', 
            'max_fps', 'new_display', 'max_size', 'extraargs', 'video_codec', 
            'video_encoder', 'render_driver', 'allow_frame_drop', 'low_latency', 
            'priority_mode', 'bitrate_mode', 'video_buffer', 'video_bitrate_slider',
            'audio_codec', 'audio_encoder', 'audio_buffer', 'fullscreen', 
            'turn_screen_off', 'stay_awake', 'mipmaps', 'no_audio', 'no_video', 
            'try_unlock', 'alternate_launch_method'
        ]
        
        config_to_use = {}
        for key in config_keys:
            # By calling get() for each key, we get the final value after the
            # profile (global + specific) has been loaded internally by AppConfig.
            value = app_config.get(key)
            if value is not None:
                config_to_use[key] = value
            
        return config_to_use
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
async def set_config(request: ConfigRequest):
    """Saves the configuration for a specific app on a device."""
    try:
        app_config = get_config_for_device(request.device_id)
        app_config.save_app_scrcpy_config(request.pkg_name, request.config_data)
        if web_thread:
            web_thread.config_needs_reload.emit()
        return {"status": "success", "message": "Configuration saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices")
async def list_devices():
    """Returns a list of all connected ADB devices with their info."""
    try:
        output = adb_handler._run_adb_command(['devices'], ignore_errors=True)
        lines = output.strip().split('\n')
        devices = []
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) == 2:
                    device_id = parts[0].strip()
                    state = parts[1].strip()
                    if device_id and state == 'device':
                        device_info = adb_handler.get_device_info(device_id)
                        devices.append({
                            "id": device_id,
                            "name": device_info.get("commercial_name", "Unknown") if device_info else "Unknown",
                            "battery": device_info.get("battery", "?") if device_info else "?"
                        })
        return devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/devices/{device_id}/info", summary="Get detailed device information")
async def get_device_details(device_id: str):
    try:
        info = adb_handler.get_device_info(device_id)
        if not info:
            raise HTTPException(status_code=404, detail="Device not found or info not available.")

        launcher = adb_handler.get_default_launcher(device_id)
        info['default_launcher'] = launcher
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get device details: {e}")


@app.get("/api/profiles", summary="List profiles with existing configurations for a device")
async def list_profiles(device_id: str):
    """
    Lists app and Winlator profiles that have a saved configuration and are currently installed on the device.
    """
    try:
        app_config = get_config_for_device(device_id)

        # Get installed apps
        user_apps, system_apps = scrcpy_handler.list_installed_apps(device_id)
        installed_apps_packages = set(user_apps.values()) | set(system_apps.values())

        # Get winlator shortcuts
        shortcuts = adb_handler.list_winlator_shortcuts_with_names(device_id)
        winlator_shortcuts_on_device = {path for name, path in shortcuts}

        # Filter app configs
        app_configs_from_settings = app_config.get_app_config_keys()
        filtered_app_configs = []
        for key, name in app_configs_from_settings:
            if key in installed_apps_packages:
                filtered_app_configs.append({"key": key, "name": name})

        # Filter winlator configs
        winlator_configs_from_settings = app_config.get_winlator_config_keys()
        filtered_winlator_configs = []
        for key, name in winlator_configs_from_settings:
            if key in winlator_shortcuts_on_device:
                filtered_winlator_configs.append({"key": key, "name": name})

        return {
            "apps": sorted(filtered_app_configs, key=lambda x: x['name'].lower()),
            "winlator": sorted(filtered_winlator_configs, key=lambda x: x['name'].lower())
        }
    except Exception:
        # Gracefully fail if device disconnects or other ADB errors occur during fetch
        return {"apps": [], "winlator": []}


@app.get("/api/apps")
async def list_apps(device_id: str, include_system_apps: bool = False):
    """Lists installed applications for a given device."""
    try:
        app_config = get_config_for_device(device_id)
        user_apps, system_apps = scrcpy_handler.list_installed_apps(device_id)

        all_apps = []
        app_list = user_apps.items()
        if include_system_apps:
            app_list = list(user_apps.items()) + list(system_apps.items())

        for name, pkg in app_list:
            metadata = app_config.get_app_metadata(pkg)
            is_pinned = metadata.get('pinned', False)
            all_apps.append({"name": name, "pkg_name": pkg, "icon": f"{pkg}.png", "pinned": is_pinned})

        all_apps.sort(key=lambda x: x['name'].lower())
        return all_apps
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.get("/api/winlator/apps", summary="List Winlator shortcuts/games")
async def list_winlator_apps(device_id: str):
    """Lists Winlator shortcuts found on the device."""
    try:
        shortcuts = adb_handler.list_winlator_shortcuts_with_names(device_id)
        if not shortcuts:
            return []

        games = []
        for name, path in shortcuts:
            pkg = adb_handler.get_package_name_from_shortcut(path, device_id)
            icon_filename = f"{os.path.basename(path)}.png"
            games.append({"name": name, "path": path, "pkg": pkg, "icon": icon_filename})

        return sorted(games, key=lambda x: x['name'].lower())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/launch", summary="Launch a standard Android application")
async def launch_app(request: LaunchRequest):
    """Launches an application on a device and tracks the session."""
    try:
        app_config = get_config_for_device(request.device_id)
        config_to_use = app_config.get_global_values_no_profile()
        app_specific_config = app_config.get_app_metadata(request.pkg_name).get('config', {})
        if app_specific_config:
            config_to_use.update(app_specific_config)

        config_to_use['start_app'] = request.pkg_name
        perform_alt_launch = config_to_use.get('alternate_launch_method', False)

        icon_path = os.path.join(app_config.get_icon_cache_dir(), f"{request.pkg_name}.png")

        process = scrcpy_handler.launch_scrcpy(
            config_values=config_to_use,
            window_title=request.app_name,
            device_id=request.device_id,
            icon_path=icon_path,
            session_type='app',
            perform_alternate_app_launch=perform_alt_launch
        )
        
        scrcpy_handler.add_active_scrcpy_session(
            pid=process.pid,
            app_name=request.app_name,
            command_args=process.args,
            icon_path=icon_path,
            session_type='app'
        )
        return {"status": "success", "message": f"Launch command sent for {request.app_name}.", "pid": process.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/winlator/launch", summary="Launch a Winlator application")
async def launch_winlator_app(request: WinlatorLaunchRequest):
    """Launches a Winlator app on a device and tracks the session."""
    try:
        app_config = get_config_for_device(request.device_id)
        config_to_use = app_config.get_global_values_no_profile()
        
        # Winlator apps might have specific configs stored by shortcut path
        app_specific_config = app_config.get_app_metadata(request.shortcut_path).get('config', {})
        if app_specific_config:
            config_to_use.update(app_specific_config)
            
        # This is for the alternate launch logic inside scrcpy_handler
        config_to_use['package_name_for_alt_launch'] = request.pkg_name
        config_to_use['shortcut_path'] = request.shortcut_path
        
        icon_path = os.path.join(app_config.get_icon_cache_dir(), f"{os.path.basename(request.shortcut_path)}.png")

        process = scrcpy_handler.launch_scrcpy(
            config_values=config_to_use,
            window_title=request.app_name,
            device_id=request.device_id,
            icon_path=icon_path,
            session_type='winlator',
            perform_alternate_app_launch=True # Necessary for display ID detection and app start
        )
        
        scrcpy_handler.add_active_scrcpy_session(
            pid=process.pid,
            app_name=request.app_name,
            command_args=process.args,
            icon_path=icon_path,
            session_type='winlator'
        )
        return {"status": "success", "message": f"Launch command sent for {request.app_name}.", "pid": process.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scrcpy/encoders", summary="List available scrcpy encoders")
async def list_encoders(device_id: str = None):
    try:
        if not device_id:
            return {"video_encoders": {}, "audio_encoders": {}}

        app_config = get_config_for_device(device_id)

        # Use cache if available, similar to the desktop app
        cached_data = app_config.get_encoder_cache()
        if cached_data and cached_data.get('video'):
            return {
                "video_encoders": cached_data.get('video', {}),
                "audio_encoders": cached_data.get('audio', {})
            }
        
        # Fallback to live fetch and save to cache
        video_encoders, audio_encoders = scrcpy_handler.list_encoders()
        app_config.save_encoder_cache(video_encoders, audio_encoders)
        return {"video_encoders": video_encoders, "audio_encoders": audio_encoders}

    except Exception as e:
        print(f"Error fetching/loading encoders: {e}")
        return {"video_encoders": {}, "audio_encoders": {}}

@app.get("/api/scrcpy/sessions", summary="List active scrcpy sessions")
async def get_active_sessions():
    """Returns a list of active (running) scrcpy sessions."""
    try:
        return scrcpy_handler.get_active_scrcpy_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/scrcpy/sessions/{pid}", summary="Kill a scrcpy session by PID")
async def kill_session(pid: int):
    """Terminates a scrcpy session by its Process ID (PID)."""
    try:
        if scrcpy_handler.kill_scrcpy_session(pid):
            return {"status": "success", "message": f"Session with PID {pid} terminated."}
        else:
            raise HTTPException(status_code=404, detail=f"Session with PID {pid} not found or could not be terminated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount the entire web directory for static files (THIS MUST BE LAST)
app.mount("/", StaticFiles(directory="web", html=True), name="web")


web_thread = None

def run_server(thread=None):
    """This function is the entry point for the web server thread."""
    global web_thread
    if thread:
        web_thread = thread
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_server()