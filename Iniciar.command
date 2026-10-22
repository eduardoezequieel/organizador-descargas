#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
shopt -s nullglob

# Finder no hereda necesariamente el PATH de la terminal.
for python in .venv/bin/python3 /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.* /usr/local/bin/python3 /usr/local/bin/python3.* /Library/Frameworks/Python.framework/Versions/Current/bin/python3 python3; do
    if "$python" -c 'import sys, tkinter; sys.exit(not (sys.version_info >= (3, 12) and tkinter.TkVersion >= 8.6))' 2>/dev/null; then
        exec "$python" app.py
    fi
done

echo 'No se encontró Python 3.12 o posterior con Tk 8.6 o posterior.'
echo 'Instalá Python para macOS desde https://www.python.org/downloads/macos/ y volvé a abrir este archivo.'
read -r -p 'Presioná Enter para cerrar…'
exit 1
