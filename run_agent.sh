#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ] && [ ! -d "venv_new" ]; then
    echo "Error: No virtual environment found. Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

if [ -d "venv_new" ]; then
    VENV_DIR="venv_new"
elif [ -d "venv" ]; then
    VENV_DIR="venv"
fi

source "$VENV_DIR/bin/activate"

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

python3 -m src.cli "$@"