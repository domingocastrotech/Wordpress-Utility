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
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean "wordpress_utilidades_app.spec"
if errorlevel 1 (
  echo [ERROR] Compilacion fallida.
  popd >nul 2>&1
  exit /b 1
)

set "EXE_PATH=%SCRIPT_DIR%dist\Wordpress_Utilidades.exe"
if not exist "%EXE_PATH%" (
  REM A veces antivirus/indexador retiene temporalmente el archivo.
  set "_TRIES=0"
  :WAIT_EXE
  if exist "%EXE_PATH%" goto EXE_FOUND
  set /a _TRIES+=1
  if %_TRIES% GEQ 6 goto TRY_ALT
  timeout /t 1 /nobreak >nul
  goto WAIT_EXE
)

:TRY_ALT
if not exist "%EXE_PATH%" (
  REM Nombre alternativo si cambia el spec en el futuro.
  if exist "%SCRIPT_DIR%dist\wordpress_utilidades_app.exe" (
    set "EXE_PATH=%SCRIPT_DIR%dist\wordpress_utilidades_app.exe"
  ) else (
    echo [ERROR] PyInstaller finalizo, pero no se encontro el ejecutable esperado en dist.
    echo [ERROR] Revisa el nombre definido en "name=" dentro de wordpress_utilidades_app.spec.
    echo [INFO] Contenido actual de dist:
    dir "%SCRIPT_DIR%dist" /a
    echo [INFO] Si aparece y desaparece, revisa cuarentena del antivirus/Defender.
    popd >nul 2>&1
    exit /b 1
  )
)

:EXE_FOUND

echo [OK] Compilacion completada.
echo [OK] Ejecutable: "%EXE_PATH%"
echo [INFO] Archivos en dist:
dir "%SCRIPT_DIR%dist" /a

popd >nul 2>&1
exit /b 0
