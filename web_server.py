import uvicorn
from fastapi import FastAPI, Query, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, Any
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

class PinRequest(BaseModel): # New Pydantic model
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

@app.post("/api/adb/connect", summary="Connect to a device via ADB over WiFi")
async def adb_connect(request: AdbConnectRequest):
    """Connects to an ADB device over WiFi."""
    try:
        result = adb_handler.connect_wifi(request.address)
        if "connected" in result or "already connected" in result:
            return {"status": "success", "message": result}
        else:
            return {"status": "error", "message": result or "Failed to connect."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/app/pin", summary="Pin or unpin an application")
async def pin_app(request: PinRequest):
    """Pins or unpins an application for the current device."""
    try:
        app_config = get_config_for_device(request.device_id)
        app_config.save_app_metadata(request.pkg_name, {'pinned': request.pinned})
        return {"status": "success", "message": f"App '{request.pkg_name}' {'pinned' if request.pinned else 'unpinned'}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

@app.post("/api/input/text")
async def text_input(request: TextInputRequest):
    """Types the given text on the device."""
    try:
        adb_handler._run_adb_command(['shell', 'input', 'text', shlex.quote(request.text)], request.device_id)
        return {"status": "success", "message": "Text input command sent."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/input/keyevent")
async def key_event(request: KeyEventRequest):
    """Sends a key event to the device."""
    try:
        keycode = KEY_COMMAND_MAP.get(request.key_command.upper())
        if not keycode:
            return {"status": "error", "message": "Invalid key command."}
        
        adb_handler._run_adb_command(['shell', 'input', 'keyevent', keycode], request.device_id)
        return {"status": "success", "message": f"Key command '{request.key_command}' sent."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/config")
async def get_config(device_id: str, pkg_name: str):
    """Retrieves the configuration for a specific app on a device."""
    try:
        app_config = get_config_for_device(device_id)
        config_to_use = app_config.get_global_values_no_profile()
        app_specific_config = app_config.get_app_metadata(pkg_name).get('config', {})
        if app_specific_config:
            config_to_use.update(app_specific_config)
        return config_to_use
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/config")
async def set_config(request: ConfigRequest):
    """Saves the configuration for a specific app on a device."""
    try:
        app_config = get_config_for_device(request.device_id)
        # We only save the app-specific part. Global settings are not changed here.
        app_config.save_app_scrcpy_config(request.pkg_name, request.config_data)
        return {"status": "success", "message": "Configuration saved."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_all_devices():
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
    except Exception:
        return []

@app.get("/api/devices")
async def list_devices():
    return get_all_devices()

@app.get("/api/apps")
async def list_apps(device_id: str, include_system_apps: bool = False):
    """Lists installed applications for a given device."""
    try:
        app_config = get_config_for_device(device_id) # Get AppConfig instance
        user_apps, system_apps = scrcpy_handler.list_installed_apps(device_id)
        
        all_apps = []
        for name, pkg in user_apps.items():
            metadata = app_config.get_app_metadata(pkg)
            is_pinned = metadata.get('pinned', False)
            all_apps.append({"name": name, "pkg_name": pkg, "icon": f"{pkg}.png", "pinned": is_pinned})
            
        if include_system_apps:
            for name, pkg in system_apps.items():
                metadata = app_config.get_app_metadata(pkg)
                is_pinned = metadata.get('pinned', False)
                all_apps.append({"name": name, "pkg_name": pkg, "icon": f"{pkg}.png", "pinned": is_pinned})

        all_apps.sort(key=lambda x: x['name'].lower())
        
        return all_apps
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

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
        return {"error": str(e)}


@app.post("/api/launch")
async def launch_app(request: LaunchRequest):
    """Launches an application on a device."""
    try:
        app_config = get_config_for_device(request.device_id)
        
        config_to_use = app_config.get_global_values_no_profile()
        app_specific_config = app_config.get_app_metadata(request.pkg_name).get('config', {})
        
        if app_specific_config:
            config_to_use.update(app_specific_config)
            
        print(f"DEBUG: config_to_use for launch: {config_to_use}") # DEBUG PRINT
            
        # The 'start_app' value to be used for the *actual* app launch by ADB later (if alternate)
        # or by scrcpy directly.
        config_to_use['start_app'] = request.pkg_name

        # Determine if alternate launch logic should be triggered
        perform_alt_launch = config_to_use.get('alternate_launch_method', False) and \
                             request.pkg_name not in ('', 'None', 'launcher_shortcut')

        scrcpy_handler.launch_scrcpy(
            config_values=config_to_use,
            window_title=request.app_name,
            device_id=request.device_id,
            session_type='app', # Assuming this endpoint is for regular apps
            perform_alternate_app_launch=perform_alt_launch # Pass the flag
        )
        return {"status": "success", "message": f"Launch command sent for {request.app_name}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Mount the entire web directory for static files (THIS MUST BE LAST)
app.mount("/", StaticFiles(directory="web", html=True), name="web")


def run_server():
    """This function is the entry point for the web server thread."""
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_server()