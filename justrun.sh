#!/bin/bash

# Obtém o diretório onde o script está localizado
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Ativa o ambiente virtual que está no mesmo diretório
source "$DIR/.venv/bin/activate"

# Executa o seu programa Python
python3 "$DIR/main.py"
