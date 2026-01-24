#!/bin/bash

# Script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_DIR="$DIR/.venv"
PYTHON_EXEC="$VENV_DIR/bin/python"
PIP_EXEC="$VENV_DIR/bin/pip"

# Log function
log() {
    echo "-----------------------------------------------------"
    echo "$1"
    echo "-----------------------------------------------------"
}

# --- Git Check and Update ---
if [ -d "$DIR/.git" ]; then
    log "Checking for Git updates..."
    git remote update > /dev/null
    LOCAL=$(git rev-parse @)
    REMOTE=$(git rev-parse @{u})

    if [ "$LOCAL" != "$REMOTE" ]; then
        log "Your repository is outdated. Pulling latest changes..."
        git pull --rebase
        log "Repository updated."
    else
        log "Your repository is up-to-date."
    fi
else
    log ".git directory not found. Skipping Git check."
fi

# --- Build Option ---
echo "Press any key within 2 seconds to see build options..."
if read -r -n 1 -t 2; then
    echo
    read -p "Do you want to build the project with PyInstaller? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "Starting build..."
        
        # Activate venv
        if [ ! -f "$PYTHON_EXEC" ]; then
            log "Virtual environment not found. Creating..."
            python3 -m venv "$VENV_DIR"
        fi
        source "$VENV_DIR/bin/activate"

        # Install build dependencies
        log "Installing build dependencies..."
        "$PIP_EXEC" install -r "$DIR/requirements.txt"
        "$PIP_EXEC" install pyinstaller

        # Build
        log "Building with PyInstaller..."
        cd "$DIR" # Ensure pyinstaller runs in the correct directory
        "$VENV_DIR/bin/pyinstaller" main.spec --noconfirm
        
        log "Build finished. Artifacts are in the 'dist' folder."
        exit 0
    fi
fi

# --- Virtual Environment and Dependencies Setup ---
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        log "Failed to create virtual environment. Please check if 'python3' and 'python3-venv' are installed."
        exit 1
    fi
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Check and install dependencies
log "Checking dependencies..."
if [ ! -f "$DIR/requirements.txt" ]; then
    log "requirements.txt not found. Skipping dependency check."
else
    REQ_HASH_FILE="$VENV_DIR/.req-hash"
    CURRENT_HASH=$(sha256sum "$DIR/requirements.txt" | awk '{print $1}')

    if [ -f "$REQ_HASH_FILE" ] && [ "$(cat "$REQ_HASH_FILE")" == "$CURRENT_HASH" ]; then
        log "Dependencies are up-to-date."
    else
        log "Installing/updating dependencies (this may take a moment)..."
        "$PIP_EXEC" install -r "$DIR/requirements.txt" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            log "Dependencies installed successfully."
            echo "$CURRENT_HASH" > "$REQ_HASH_FILE"
        else
            log "Error installing dependencies. Please check requirements.txt and your internet connection."
        fi
    fi
fi

# --- Run Program ---
log "Starting yaScrcpy GUI..."
cd "$DIR" # Ensure the program runs in the correct directory
"$PYTHON_EXEC" main.py "$@"
