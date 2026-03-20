@echo off
setlocal EnableDelayedExpansion

set "TOOLS_DIR=%~dp0"

for /f %%e in ('echo prompt $E^| cmd') do set "ESC=%%e"
set "C_RST=%ESC%[0m"
set "C_TIT=%ESC%[96m"
set "C_OK=%ESC%[92m"
set "C_WARN=%ESC%[93m"
set "C_ERR=%ESC%[91m"
set "C_INFO=%ESC%[94m"

:MENU
cls
echo !C_TIT!==================================================!C_RST!
echo !C_TIT!  MENU DE UTILIDADES WORDPRESS + DOCKER!C_RST!
echo !C_TIT!==================================================!C_RST!
echo.
echo   [1] Crear/Recrear entorno ^(docker_mariadb_wordpress.bat^)
echo   [2] Importar backup ^(importar-wordpress.bat^)
echo   [3] Exportar backup ^(exportar-wordpress-v3.bat^)
echo   [4] Gestionar contenedores ^(gestor_contenedores.bat^)
echo   [5] Abrir documentacion ^(docker-wordpress-docs.html^)
echo.
echo   [0] Cerrar CMD
echo.
set "OPT="
set /p "OPT=Selecciona una opcion: "

if "%OPT%"=="1" goto RUN_SETUP
if "%OPT%"=="2" goto RUN_IMPORT
if "%OPT%"=="3" goto RUN_EXPORT
if "%OPT%"=="4" goto RUN_GESTOR
if "%OPT%"=="5" goto RUN_DOCS
if "%OPT%"=="0" goto SALIR

echo.
echo !C_WARN!Opcion no valida.!C_RST!
ping -n 2 127.0.0.1 > nul
goto MENU

:RUN_SETUP
if not exist "%TOOLS_DIR%docker_mariadb_wordpress.bat" (
  call :NO_ENCONTRADO "docker_mariadb_wordpress.bat"
  goto MENU
)
echo.
echo !C_INFO!Abriendo docker_mariadb_wordpress.bat...!C_RST!
start "" /wait cmd /c ""%TOOLS_DIR%docker_mariadb_wordpress.bat" maximizado"
goto MENU

:RUN_IMPORT
if not exist "%TOOLS_DIR%importar-wordpress.bat" (
  call :NO_ENCONTRADO "importar-wordpress.bat"
  goto MENU
)
echo.
echo !C_INFO!Abriendo importar-wordpress.bat...!C_RST!
start "" /wait cmd /c ""%TOOLS_DIR%importar-wordpress.bat""
goto MENU

:RUN_EXPORT
if not exist "%TOOLS_DIR%exportar-wordpress-v3.bat" (
  call :NO_ENCONTRADO "exportar-wordpress-v3.bat"
  goto MENU
)
echo.
echo !C_INFO!Abriendo exportar-wordpress-v3.bat...!C_RST!
start "" /wait cmd /c ""%TOOLS_DIR%exportar-wordpress-v3.bat" __RUN__"
goto MENU

:RUN_GESTOR
if not exist "%TOOLS_DIR%gestor_contenedores.bat" (
  call :NO_ENCONTRADO "gestor_contenedores.bat"
  goto MENU
)
echo.
echo !C_INFO!Abriendo gestor_contenedores.bat...!C_RST!
start "" /wait cmd /c ""%TOOLS_DIR%gestor_contenedores.bat""
goto MENU

:RUN_DOCS
if not exist "%TOOLS_DIR%docker-wordpress-docs.html" (
  call :NO_ENCONTRADO "docker-wordpress-docs.html"
  goto MENU
)
echo.
echo !C_INFO!Abriendo docker-wordpress-docs.html en el navegador...!C_RST!
start "" "%TOOLS_DIR%docker-wordpress-docs.html"
ping -n 2 127.0.0.1 > nul
goto MENU

:NO_ENCONTRADO
echo.
echo !C_ERR![ERROR]!C_RST! No se encontro %~1 en:
echo   %TOOLS_DIR%
echo.
pause
exit /b 0

:SALIR
echo.
echo !C_OK!Cerrando menu...!C_RST!
endlocal
exit
