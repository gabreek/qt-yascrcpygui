# qt-yaScrcpy

## 🌟 Overview

A modern and robust GUI for `scrcpy` and Winlator, built with **PySide6 (Qt)**. This application provides a user-friendly interface to manage and launch `scrcpy` instances with custom settings for both standard Android apps and Winlator games, offering a more native and polished user experience compared to its predecessor.

## ✨ Features

*   **Qt-Powered Interface:** Rebuilt with PySide6 for a more native, performant, and visually appealing cross-platform user interface.
*   **Tabbed Interface:** Separate, organized tabs for Android Apps, Winlator Games, and Scrcpy configuration.
*   **Android App Launcher:**
    *   Automatically lists all installed applications on your device.
    *   Scrapes app icons from the Google Play Store.
    *   Supports custom icons via drag-and-drop.
    *   Save specific `scrcpy` settings for each app.
*   **Winlator Game Launcher:**
    *   Automatically discovers game shortcuts (`.desktop` files) from your Winlator installation. (You need export shortcut to frontend in winlator app)
    *   **Automatic Icon Extraction:** Fetches and caches game icons directly from the game's `.exe` file.
    *   Supports custom game icons via drag-and-drop.
    *   Save specific `scrcpy` settings for each game, perfect for custom resolutions and performance tuning.
*   **Advanced Scrcpy Configuration:** A dedicated tab to tweak all major `scrcpy` settings, including resolution, bitrate, codecs, and more. All settings are saved automatically.
*   **Custom Window Icons:** The `scrcpy` window will automatically use the game's or app's icon, providing a native look and feel.

---

## 🚀 Installation & Usage

This application is designed for Linux systems (for now).

### Recommended: Download Pre-compiled Executables

For the easiest way to get started, download the latest pre-compiled executable for your system's architecture from the [Releases page](https://github.com/gabreek/qt-yaScrcpy/releases).

### 1. System Dependencies

First, ensure you have `adb` and `scrcpy` installed and available in your system's PATH.

```bash
# On Debian/Ubuntu based systems
sudo apt update
sudo apt install adb scrcpy
```

### 2. Running from Source (Optional, for Developers)

If you prefer to run the application directly from the source code, follow these steps:

#### Clone the Repository

```bash
git clone https://github.com/gabreek/qt-yaScrcpy.git
cd qt-yaScrcpy
```

#### Set Up Python Environment

It is highly recommended to use a Python virtual environment.

```bash
# Create the virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install the required Python packages
pip install -r requirements.txt
```

#### How to Run

A convenience script `run.sh` is provided to automatically activate the virtual environment and start the application.

1.  **Make the script executable (only needs to be done once):**
    ```bash
    chmod +x run.sh
    ```

2.  **Run the application:**
    ```bash
    ./run.sh
    ```

---

## 📦 Building Executables (For Developers)

This project is automatically packaged into standalone executables using PyInstaller via GitHub Actions. Executables for `Linux x86_64` and `Linux ARM64` are built and made available as workflow artifacts on every push to the `master` branch.

To access these builds:

1.  Go to the [Actions tab](https://github.com/gabreek/qt-yaScrcpy/actions) of this repository.
2.  Select the latest successful workflow run.
3.  Download the desired executable artifact (e.g., `qt-yaScrcpy-linux-x86_64` or `qt-yaScrcpy-linux-arm64`).

---

## 🚧 To-Do / Future Features

-   [ ] Multiple windows audio management.
-   [ ] Full support for ADB over WiFi.
-   [ ] Multi-device management interface.
-   [ ] ... any other ideas are welcome!
