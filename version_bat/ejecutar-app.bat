@echo off
setlocal
set "BASE_DIR=%~dp0"

set "APP_PY=%BASE_DIR%/../app_escritorio\wordpress_utilidades_app.py"
if not exist "%APP_PY%" (
  echo [ERROR] No se encontro el archivo principal de la app:
  echo %APP_PY%
  pause
  exit /b 1
)

call :TRY_RUN "python"
if "%RUN_OK%"=="1" goto FIN

echo.
echo [ERROR] Python no esta instalado correctamente.
echo Detectado: alias de Microsoft Store ^(WindowsApps^), no un interprete real.
echo.
echo Opciones:
echo   [1] Instalar Python 3.12 ahora con winget
echo   [2] Abrir configuracion de Alias de ejecucion
echo   [0] Salir
echo.
set "OPT="
set /p "OPT=Selecciona una opcion: "

if "%OPT%"=="1" goto INSTALL_PYTHON
if "%OPT%"=="2" goto OPEN_ALIAS_SETTINGS
goto FIN

:INSTALL_PYTHON
where winget >nul 2>&1
if errorlevel 1 (
  echo [ERROR] winget no esta disponible en este sistema.
  echo Instala Python manualmente desde https://www.python.org/downloads/
  pause
  goto FIN
)

echo.
echo Instalando Python 3.12 con winget...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo.
  echo [ERROR] La instalacion fallo o fue cancelada.
  pause
  goto FIN
)

echo.
echo Instalacion completada. Intentando ejecutar la app...
call :TRY_RUN "python"
if "%RUN_OK%"=="1" goto FIN

echo.
echo [WARN] Python se instalo, pero esta terminal aun no lo detecta.
echo Cierra esta ventana y ejecuta de nuevo ejecutar-app.bat.
pause
goto FIN

:OPEN_ALIAS_SETTINGS
start "" ms-settings:advanced-app-settings-app-execution-aliases
echo.
echo Se abrio la configuracion de Alias de ejecucion.
echo Desactiva python.exe y python3.exe de Microsoft Store y vuelve a intentar.
pause
goto FIN

:TRY_RUN
set "RUN_OK=0"
set "PY_CMD=%~1"

where %PY_CMD% >nul 2>&1
if errorlevel 1 exit /b 0

%PY_CMD% -c "import sys; print(sys.version)" >nul 2>&1
if errorlevel 1 exit /b 0

%PY_CMD% "%APP_PY%"
set "RUN_OK=1"
exit /b 0

:FIN
endlocal
