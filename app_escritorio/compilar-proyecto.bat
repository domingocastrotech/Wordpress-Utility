@echo off
setlocal

REM Compila la app desde app_escritorio usando el spec oficial.
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] No se pudo cambiar al directorio de la app.
  exit /b 1
)

set "PYTHON_EXE="
if exist "..\.venv\Scripts\python.exe" (
  set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] No se encontro Python. Instala Python o crea .venv en la carpeta padre.
    popd >nul 2>&1
    exit /b 1
  )
  set "PYTHON_EXE=python"
)

echo [INFO] Verificando PyInstaller...
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo [INFO] PyInstaller no esta instalado. Instalando...
  "%PYTHON_EXE%" -m pip install pyinstaller
  if errorlevel 1 (
    echo [ERROR] No se pudo instalar PyInstaller.
    popd >nul 2>&1
    exit /b 1
  )
)

echo [INFO] Compilando proyecto con wordpress_utilidades_app.spec...
"%PYTHON_EXE%" -m PyInstaller --noconfirm "wordpress_utilidades_app.spec"
if errorlevel 1 (
  echo [ERROR] Compilacion fallida.
  popd >nul 2>&1
  exit /b 1
)

echo [OK] Compilacion completada.
echo [OK] Ejecutable: "%SCRIPT_DIR%dist\Wordpress_Utilidades.exe"

popd >nul 2>&1
exit /b 0
