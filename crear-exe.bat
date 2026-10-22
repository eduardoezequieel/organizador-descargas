@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python -m pip install pyinstaller==6.22.0
if errorlevel 1 goto error
.venv\Scripts\python -m unittest -v
if errorlevel 1 goto error
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --name OrganizadorDescargas app.py
if errorlevel 1 goto error
echo Listo: dist\OrganizadorDescargas.exe
pause
exit /b 0
:error
echo No se pudo crear el ejecutable. Revisa el mensaje anterior.
pause
exit /b 1
