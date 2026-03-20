@echo off
if "%~1"=="maximizado" goto INICIO
powershell -command "& {$h=Get-Host;$h.UI.RawUI.WindowSize=New-Object System.Management.Automation.Host.Size(120,40)}" > nul 2>&1
start "" /max "%~f0" maximizado
exit
:INICIO
setlocal enabledelayedexpansion

for /f %%e in ('echo prompt $E^| cmd') do set "ESC=%%e"
set "C_RST=%ESC%[0m"
set "C_TIT=%ESC%[96m"
set "C_OK=%ESC%[92m"
set "C_WARN=%ESC%[93m"
set "C_ERR=%ESC%[91m"
set "C_INFO=%ESC%[94m"

:: ======================================================
:: VALORES POR DEFECTO
:: ======================================================
set _NOMBRE_WORDPRESS=wordpress1
set _NOMBRE_MARIADB=mariadb1
set _NOMBRE_RED=wp-network1
set _VOLUMEN_WORDPRESS=wpdata1
set _VOLUMEN_MARIADB=mariadbdata1
set _PUERTO_HTTP=8182
set _PUERTO_HTTP_CONTENEDOR=8080
set _PUERTO_HTTPS=8445
set _PUERTO_HTTPS_CONTENEDOR=8443
set _PUERTO_MARIADB=3307
set _IP_RED=192.168.200.51
set _DOMINIO_PRODUCCION=https://tudominio.com
set _WP_USUARIO=admin
set _WP_PASSWORD=admin
set _DB_NOMBRE=wordpress
set _DB_USUARIO=admin
set _DB_PASSWORD=admin
set _DB_ROOT_PASSWORD=1234
set _PUERTO_PHPMYADMIN=8181
set _NOMBRE_PHPMYADMIN=phpmyadmin1
set _TIMEOUT_MARIADB=120
set _TIMEOUT_WORDPRESS=180
set _TIMEOUT_RESTART=60

:: ======================================================
:: CONFIGURACION INTERACTIVA
:: ======================================================
cls
echo.
echo   !C_TIT!######################################################!C_RST!
echo   !C_TIT!##                                                  ##!C_RST!
echo   !C_TIT!##         WORDPRESS  +  DOCKER  +  MARIADB         ##!C_RST!
echo   !C_TIT!##                                                  ##!C_RST!
echo   !C_TIT!######################################################!C_RST!
echo.
echo   Configuracion del entorno
echo   Pulsa ENTER para usar el valor por defecto [entre corchetes]
echo.
echo   ------------------------------------------------------
echo.

:: --- Contenedores ---
echo   CONTENEDORES
echo.
echo   Nombre del contenedor Docker para WordPress
echo    Nombre contenedor WordPress [!_NOMBRE_WORDPRESS!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "NOMBRE_WORDPRESS=!_NOMBRE_WORDPRESS!") else (set "NOMBRE_WORDPRESS=!_I!")
echo   Nombre del contenedor Docker para la base de datos
echo    Nombre contenedor MariaDB   [!_NOMBRE_MARIADB!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "NOMBRE_MARIADB=!_NOMBRE_MARIADB!") else (set "NOMBRE_MARIADB=!_I!")
echo.

:: --- Red ---
echo   RED DOCKER
echo.
echo   Red interna de Docker que conecta WordPress con MariaDB
echo    Nombre de la red           [!_NOMBRE_RED!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "NOMBRE_RED=!_NOMBRE_RED!") else (set "NOMBRE_RED=!_I!")
echo.

:: --- Volumenes ---
echo   VOLUMENES
echo.
echo   Volumen donde se guardan los archivos de WordPress (temas, plugins, uploads)
echo    Volumen WordPress           [!_VOLUMEN_WORDPRESS!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "VOLUMEN_WORDPRESS=!_VOLUMEN_WORDPRESS!") else (set "VOLUMEN_WORDPRESS=!_I!")
echo   Volumen donde se guardan los datos de la base de datos
echo    Volumen MariaDB             [!_VOLUMEN_MARIADB!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "VOLUMEN_MARIADB=!_VOLUMEN_MARIADB!") else (set "VOLUMEN_MARIADB=!_I!")
echo.

:: --- Puertos ---
echo   PUERTOS
echo.
echo   Puerto interno HTTP del contenedor (no cambiar salvo imagen custom)
echo    Puerto HTTP  (contenedor)   [!_PUERTO_HTTP_CONTENEDOR!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "PUERTO_HTTP_CONTENEDOR=!_PUERTO_HTTP_CONTENEDOR!") else (set "PUERTO_HTTP_CONTENEDOR=!_I!")
echo   Puerto interno HTTPS del contenedor (no cambiar salvo imagen custom)
echo    Puerto HTTPS (contenedor)   [!_PUERTO_HTTPS_CONTENEDOR!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "PUERTO_HTTPS_CONTENEDOR=!_PUERTO_HTTPS_CONTENEDOR!") else (set "PUERTO_HTTPS_CONTENEDOR=!_I!")

:ASK_PUERTO_HTTP
echo   Puerto de tu PC para acceder a WordPress via http://localhost:PUERTO
echo    Puerto HTTP  (host)         [!_PUERTO_HTTP!]:
set "_INPUT="
set /p "_INPUT=   -> "
if "!_INPUT!"=="" set "_INPUT=!_PUERTO_HTTP!"
netstat -ano 2>nul | findstr ":!_INPUT! " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo    !C_WARN![ WARN ]!C_RST!  Puerto !_INPUT! en uso. Elige otro.
    echo.
    goto ASK_PUERTO_HTTP
)
set "PUERTO_HTTP=!_INPUT!"
echo    !C_OK![  OK  ]!C_RST!  Puerto !PUERTO_HTTP! disponible

:ASK_PUERTO_HTTPS
echo   Puerto de tu PC para acceder a WordPress via https://localhost:PUERTO
echo    Puerto HTTPS (host)         [!_PUERTO_HTTPS!]:
set "_INPUT="
set /p "_INPUT=   -> "
if "!_INPUT!"=="" set "_INPUT=!_PUERTO_HTTPS!"
netstat -ano 2>nul | findstr ":!_INPUT! " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo    !C_WARN![ WARN ]!C_RST!  Puerto !_INPUT! en uso. Elige otro.
    echo.
    goto ASK_PUERTO_HTTPS
)
set "PUERTO_HTTPS=!_INPUT!"
echo    !C_OK![  OK  ]!C_RST!  Puerto !PUERTO_HTTPS! disponible

:ASK_PUERTO_MARIADB
echo   Puerto de tu PC para conectar a la base de datos (ej: desde TablePlus o DBeaver)
echo    Puerto MariaDB              [!_PUERTO_MARIADB!]:
set "_INPUT="
set /p "_INPUT=   -> "
if "!_INPUT!"=="" set "_INPUT=!_PUERTO_MARIADB!"
netstat -ano 2>nul | findstr ":!_INPUT! " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo    !C_WARN![ WARN ]!C_RST!  Puerto !_INPUT! en uso. Elige otro.
    echo.
    goto ASK_PUERTO_MARIADB
)
set "PUERTO_MARIADB=!_INPUT!"
echo    !C_OK![  OK  ]!C_RST!  Puerto !PUERTO_MARIADB! disponible

:ASK_PUERTO_PHPMYADMIN
echo   Puerto de tu PC para acceder a phpMyAdmin via http://localhost:PUERTO
echo    Puerto phpMyAdmin           [!_PUERTO_PHPMYADMIN!]:
set "_INPUT="
set /p "_INPUT=   -> "
if "!_INPUT!"=="" set "_INPUT=!_PUERTO_PHPMYADMIN!"
netstat -ano 2>nul | findstr ":!_INPUT! " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo    !C_WARN![ WARN ]!C_RST!  Puerto !_INPUT! en uso. Elige otro.
    echo.
    goto ASK_PUERTO_PHPMYADMIN
)
set "PUERTO_PHPMYADMIN=!_INPUT!"
echo    !C_OK![  OK  ]!C_RST!  Puerto !PUERTO_PHPMYADMIN! disponible
echo.
set "NOMBRE_PHPMYADMIN=!_NOMBRE_PHPMYADMIN!"

:: --- URLs ---
echo   URLS
echo.
echo   IP de tu PC en la red local (para acceder desde otros dispositivos del mismo WiFi)
echo    IP en red local             [!_IP_RED!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "IP_RED=!_IP_RED!") else (set "IP_RED=!_I!")
echo   Dominio real de tu web en produccion (se reemplazara por localhost al importar)
echo    Dominio produccion          [!_DOMINIO_PRODUCCION!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "DOMINIO_PRODUCCION=!_DOMINIO_PRODUCCION!") else (set "DOMINIO_PRODUCCION=!_I!")
echo.

:: --- Credenciales WordPress ---
echo   CREDENCIALES WORDPRESS
echo.
echo   Usuario para entrar al panel wp-admin
echo    Usuario WordPress           [!_WP_USUARIO!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "WP_USUARIO=!_WP_USUARIO!") else (set "WP_USUARIO=!_I!")
echo   Contrasena para entrar al panel wp-admin
echo    Password WordPress          [!_WP_PASSWORD!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "WP_PASSWORD=!_WP_PASSWORD!") else (set "WP_PASSWORD=!_I!")
echo.

:: --- Credenciales Base de datos ---
echo   CREDENCIALES BASE DE DATOS
echo.
echo   Nombre de la base de datos (bitnami_wordpress es el nombre que espera la imagen Bitnami)
echo    Nombre base de datos        [!_DB_NOMBRE!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "DB_NOMBRE=!_DB_NOMBRE!") else (set "DB_NOMBRE=!_I!")
echo   Usuario con acceso a la base de datos de WordPress
echo    Usuario BD                  [!_DB_USUARIO!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "DB_USUARIO=!_DB_USUARIO!") else (set "DB_USUARIO=!_I!")
echo   Contrasena del usuario de la base de datos
echo    Password BD                 [!_DB_PASSWORD!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "DB_PASSWORD=!_DB_PASSWORD!") else (set "DB_PASSWORD=!_I!")
echo   Contrasena del usuario root de MariaDB (acceso total a la BD)
echo    Password root MariaDB       [!_DB_ROOT_PASSWORD!]:
set "_I="
set /p "_I=   -> "
if "!_I!"=="" (set "DB_ROOT_PASSWORD=!_DB_ROOT_PASSWORD!") else (set "DB_ROOT_PASSWORD=!_I!")
echo.

:: --- Construir URLs derivadas ---
set "URL_LOCAL=http://localhost:!PUERTO_HTTP!"
set "URL_RED=http://!IP_RED!:!PUERTO_HTTP!"
set "WP_PATH=/opt/bitnami/wordpress"

:: --- Resumen ---
cls
echo.
echo   !C_TIT!######################################################!C_RST!
echo   !C_TIT!##                                                  ##!C_RST!
echo   !C_TIT!##         WORDPRESS  +  DOCKER  +  MARIADB         ##!C_RST!
echo   !C_TIT!##                                                  ##!C_RST!
echo   !C_TIT!######################################################!C_RST!
echo.
echo   RESUMEN DE CONFIGURACION
echo   ------------------------------------------------------
echo.
echo   CONTENEDORES
echo     WordPress     :  !NOMBRE_WORDPRESS!
echo     MariaDB       :  !NOMBRE_MARIADB!
echo     phpMyAdmin    :  !NOMBRE_PHPMYADMIN!
echo.
echo   RED Y VOLUMENES
echo     Red           :  !NOMBRE_RED!
echo     Vol. WordPress:  !VOLUMEN_WORDPRESS!
echo     Vol. MariaDB  :  !VOLUMEN_MARIADB!
echo.
echo   PUERTOS
echo     HTTP          :  !PUERTO_HTTP! a !PUERTO_HTTP_CONTENEDOR!
echo     HTTPS         :  !PUERTO_HTTPS! a !PUERTO_HTTPS_CONTENEDOR!
echo     MariaDB       :  !PUERTO_MARIADB!
echo     phpMyAdmin    :  !PUERTO_PHPMYADMIN!
echo.
echo   URLS
echo     Local         :  http://localhost:!PUERTO_HTTP!
echo     Red local     :  http://!IP_RED!:!PUERTO_HTTP!
echo     Dominio prod  :  !DOMINIO_PRODUCCION!
echo     phpMyAdmin    :  http://localhost:!PUERTO_PHPMYADMIN!
echo.
echo   CREDENCIALES WORDPRESS
echo     Usuario       :  !WP_USUARIO!
echo     Password      :  !WP_PASSWORD!
echo.
echo   BASE DE DATOS
echo     Nombre BD     :  !DB_NOMBRE!
echo     Usuario BD    :  !DB_USUARIO!
echo     Password BD   :  !DB_PASSWORD!
echo     Password root :  !DB_ROOT_PASSWORD!
echo.
echo   ------------------------------------------------------
echo.
ping -n 2 127.0.0.1 > nul

:: ======================================================
:: ADVERTENCIA
:: ======================================================
echo   !C_WARN!/!\  ADVERTENCIA  /!\!C_RST!
echo.
echo   Esta accion DESTRUIRA permanentemente:
echo.
echo     [x]  Contenedor !NOMBRE_WORDPRESS!
echo     [x]  Contenedor !NOMBRE_MARIADB!
echo     [x]  Contenedor !NOMBRE_PHPMYADMIN!
echo     [x]  Volumen !VOLUMEN_WORDPRESS!
echo     [x]  Volumen !VOLUMEN_MARIADB!
echo     [x]  Red !NOMBRE_RED!
echo.
echo   Esta accion NO se puede deshacer.
echo.
echo   ------------------------------------------------------
echo.
set /p CONFIRM="   Continuar? [S] Si  /  [N] No  ->  "

if /i "!CONFIRM!"=="S" goto CONTINUAR
if /i "!CONFIRM!"=="N" goto CANCELAR

echo.
echo   !C_WARN!Opcion no valida. Saliendo...!C_RST!
ping -n 3 127.0.0.1 > nul
exit /b 1

:CANCELAR
cls
echo.
echo   !C_WARN!######################################################!C_RST!
echo   !C_WARN!##                                                  ##!C_RST!
echo   !C_WARN!##              OPERACION CANCELADA                 ##!C_RST!
echo   !C_WARN!##                                                  ##!C_RST!
echo   !C_WARN!######################################################!C_RST!
echo.
echo   No se han realizado cambios.
echo.
pause
exit /b 0

:: ======================================================
:: INSTALACION
:: ======================================================
:CONTINUAR
cls
echo.
echo   !C_TIT!######################################################!C_RST!
echo   !C_TIT!##                                                  ##!C_RST!
echo   !C_TIT!##         WORDPRESS  +  DOCKER  +  MARIADB         ##!C_RST!
echo   !C_TIT!##                                                  ##!C_RST!
echo   !C_TIT!######################################################!C_RST!
echo.

:: PASO 1 - Limpiar
echo   [ 1/7 ]  Limpiando instalacion anterior...
echo   ------------------------------------------------------
docker stop !NOMBRE_WORDPRESS! !NOMBRE_MARIADB! !NOMBRE_PHPMYADMIN! > nul 2>&1
docker rm !NOMBRE_WORDPRESS! !NOMBRE_MARIADB! !NOMBRE_PHPMYADMIN! > nul 2>&1
docker volume rm !VOLUMEN_WORDPRESS! !VOLUMEN_MARIADB! > nul 2>&1
docker network rm !NOMBRE_RED! > nul 2>&1
echo   !C_OK![  OK  ]!C_RST!  Limpieza completada
echo.
ping -n 2 127.0.0.1 > nul

:: PASO 2 - Red y volumenes
echo   [ 2/7 ]  Creando red y volumenes...
echo   ------------------------------------------------------
docker network create !NOMBRE_RED! > nul 2>&1
docker volume create !VOLUMEN_MARIADB! > nul 2>&1
docker volume create !VOLUMEN_WORDPRESS! > nul 2>&1
echo   !C_OK![  OK  ]!C_RST!  Red !NOMBRE_RED! creada
echo   !C_OK![  OK  ]!C_RST!  Volumenes creados
echo.
ping -n 2 127.0.0.1 > nul

:: PASO 3 - Contenedor MariaDB
echo   [ 3/7 ]  Iniciando MariaDB...
echo   ------------------------------------------------------
docker run -d --name !NOMBRE_MARIADB! ^
  --network !NOMBRE_RED! ^
  -v !VOLUMEN_MARIADB!:/bitnami/mariadb ^
  -e MARIADB_ROOT_PASSWORD=!DB_ROOT_PASSWORD! ^
  -e MARIADB_DATABASE=!DB_NOMBRE! ^
  -e MARIADB_USER=!DB_USUARIO! ^
  -e MARIADB_PASSWORD=!DB_PASSWORD! ^
  -p !PUERTO_MARIADB!:3306 ^
  bitnami/mariadb:latest > nul 2>&1
echo   !C_OK![  OK  ]!C_RST!  Contenedor !NOMBRE_MARIADB! iniciado
echo   !C_WARN![ WAIT ]!C_RST!  Esperando a que MariaDB acepte conexiones...
set /a _DB_INTENTOS=0
goto ESPERAR_MARIADB

:ESPERAR_MARIADB
ping -n 6 127.0.0.1 > nul
set /a _DB_INTENTOS+=1
docker exec !NOMBRE_MARIADB! mysql -h 127.0.0.1 -u !DB_USUARIO! -p!DB_PASSWORD! -e "SELECT 1;" > nul 2>&1
if !errorlevel! equ 0 goto MARIADB_LISTO
if !_DB_INTENTOS! geq 40 goto MARIADB_TIMEOUT
set /a _DB_DOTS=!_DB_INTENTOS! %% 4
if !_DB_DOTS!==0 echo   !C_WARN![ WAIT ]!C_RST!  Aun esperando... ^(!_DB_INTENTOS! intentos^)
goto ESPERAR_MARIADB

:MARIADB_TIMEOUT
echo   !C_ERR![ ERROR ]!C_RST!  MariaDB no respondio tras 2 minutos. Revisa el contenedor.
pause
exit /b 1

:MARIADB_LISTO
echo   !C_OK![  OK  ]!C_RST!  MariaDB listo ^(intento !_DB_INTENTOS!^)
echo.

:: PASO 4 - Permisos volumen WordPress
echo   [ 4/7 ]  Configurando permisos del volumen...
echo   ------------------------------------------------------
docker run --rm ^
  -u root ^
  -v !VOLUMEN_WORDPRESS!:/bitnami/wordpress ^
  --entrypoint sh ^
  bitnami/wordpress:latest ^
  -c "chmod -R 777 /bitnami/wordpress && chown -R 1001:1001 /bitnami/wordpress" > nul 2>&1
echo   !C_OK![  OK  ]!C_RST!  Permisos configurados
echo.
ping -n 2 127.0.0.1 > nul

:: PASO 5 - Contenedor WordPress
echo   [ 5/7 ]  Iniciando WordPress...
echo   ------------------------------------------------------
docker run -d --name !NOMBRE_WORDPRESS! ^
  --network !NOMBRE_RED! ^
  -v !VOLUMEN_WORDPRESS!:/bitnami/wordpress ^
  -e WORDPRESS_DATABASE_HOST=!NOMBRE_MARIADB! ^
  -e WORDPRESS_DATABASE_USER=!DB_USUARIO! ^
  -e WORDPRESS_DATABASE_NAME=!DB_NOMBRE! ^
  -e WORDPRESS_DATABASE_PASSWORD=!DB_PASSWORD! ^
  -e WORDPRESS_USERNAME=!WP_USUARIO! ^
  -e WORDPRESS_PASSWORD=!WP_PASSWORD! ^
  -p !PUERTO_HTTP!:!PUERTO_HTTP_CONTENEDOR! -p !PUERTO_HTTPS!:!PUERTO_HTTPS_CONTENEDOR! ^
  bitnami/wordpress:latest > nul 2>&1
echo   !C_OK![  OK  ]!C_RST!  Contenedor !NOMBRE_WORDPRESS! iniciado
echo   !C_WARN![ WAIT ]!C_RST!  Esperando a que WordPress termine la instalacion...
set /a _WP_INTENTOS=0
goto ESPERAR_WORDPRESS

:ESPERAR_WORDPRESS
ping -n 4 127.0.0.1 > nul
set /a _WP_INTENTOS+=1
set "_HTTP_CODE="
for /f %%i in ('curl -s -o NUL -w "%%{http_code}" http://localhost:!PUERTO_HTTP! 2^>NUL') do set "_HTTP_CODE=%%i"
echo !_HTTP_CODE! | findstr /r "^[23]" > nul 2>&1
if !errorlevel! equ 0 goto WP_LISTO
if !_WP_INTENTOS! geq 45 goto WP_TIMEOUT
set /a _WP_DOTS=!_WP_INTENTOS! %% 5
if !_WP_DOTS!==0 echo   !C_WARN![ WAIT ]!C_RST!  Aun instalando... ^(!_WP_INTENTOS! intentos^)
goto ESPERAR_WORDPRESS

:WP_TIMEOUT
echo   !C_ERR![ ERROR ]!C_RST!  WordPress no respondio tras 3 minutos. Revisa el contenedor.
pause
exit /b 1

:WP_LISTO
echo   !C_OK![  OK  ]!C_RST!  WordPress instalado correctamente ^(intento !_WP_INTENTOS!^)
echo.

:: PASO 6 - Configurar URLs
echo   [ 6/7 ]  Configurando URLs...
echo   ------------------------------------------------------
docker exec !NOMBRE_WORDPRESS! wp search-replace "!DOMINIO_PRODUCCION!" "!URL_LOCAL!" --allow-root --path=!WP_PATH! --quiet > nul 2>&1
docker exec !NOMBRE_WORDPRESS! wp search-replace "!URL_LOCAL!" "!URL_RED!" --allow-root --path=!WP_PATH! --quiet > nul 2>&1
docker restart !NOMBRE_WORDPRESS! > nul 2>&1
echo   !C_WARN![ WAIT ]!C_RST!  Esperando a que WordPress vuelva tras el reinicio...
set /a _RS_INTENTOS=0
goto ESPERAR_RESTART

:ESPERAR_RESTART
ping -n 3 127.0.0.1 > nul
set /a _RS_INTENTOS+=1
set "_HTTP_CODE="
for /f %%i in ('curl -s -o NUL -w "%%{http_code}" http://localhost:!PUERTO_HTTP! 2^>NUL') do set "_HTTP_CODE=%%i"
echo !_HTTP_CODE! | findstr /r "^[23]" > nul 2>&1
if !errorlevel! equ 0 goto RESTART_LISTO
if !_RS_INTENTOS! geq 20 goto RESTART_TIMEOUT
goto ESPERAR_RESTART

:RESTART_TIMEOUT
echo   !C_WARN![ WARN ]!C_RST!  Tiempo de espera agotado, continuando de todas formas.

:RESTART_LISTO
echo   !C_OK![  OK  ]!C_RST!  URLs configuradas
echo.

:: PASO 7 - phpMyAdmin
echo   [ 7/7 ]  Iniciando phpMyAdmin...
echo   ------------------------------------------------------
docker run -d --name !NOMBRE_PHPMYADMIN! ^
  --network !NOMBRE_RED! ^
  -e PMA_HOST=!NOMBRE_MARIADB! ^
  -e PMA_PORT=3306 ^
  -p !PUERTO_PHPMYADMIN!:80 ^
  phpmyadmin:latest > nul 2>&1
echo   !C_OK![  OK  ]!C_RST!  Contenedor !NOMBRE_PHPMYADMIN! iniciado
echo.

:: ======================================================
:: RESULTADO FINAL
:: ======================================================
echo   !C_OK!######################################################!C_RST!
echo   !C_OK!##                                                  ##!C_RST!
echo   !C_OK!##          INSTALACION COMPLETADA                  ##!C_RST!
echo   !C_OK!##                                                  ##!C_RST!
echo   !C_OK!######################################################!C_RST!
echo.
echo   Acceso local:
echo     !URL_LOCAL!
echo     !URL_LOCAL!/wp-admin
echo.
echo   Acceso en red:
echo     !URL_RED!
echo     !URL_RED!/wp-admin
echo.
echo   Credenciales wp-admin:
echo     Usuario   :  !WP_USUARIO!
echo     Password  :  !WP_PASSWORD!
echo.
echo   Base de datos:
echo     Host      :  localhost:!PUERTO_MARIADB!
echo     BD        :  !DB_NOMBRE!
echo     Usuario   :  !DB_USUARIO!
echo     Password  :  !DB_PASSWORD!
echo     Root pass :  !DB_ROOT_PASSWORD!
echo.
echo   phpMyAdmin:
echo     URL       :  http://localhost:!PUERTO_PHPMYADMIN!
echo     Usuario   :  root
echo     Password  :  !DB_ROOT_PASSWORD!
echo.
echo   ######################################################
echo.

:: ======================================================
:: IMPORTACION
:: ======================================================
echo   ------------------------------------------------------
echo.
set /p IMPORTAR="   Deseas importar un backup ahora? [S] Si  /  [N] No  ->  "

if /i "!IMPORTAR!"=="S" goto LANZAR_IMPORTAR
if /i "!IMPORTAR!"=="N" goto FIN

echo.
echo   !C_WARN!Opcion no valida. Saliendo...!C_RST!
ping -n 3 127.0.0.1 > nul
goto FIN

:LANZAR_IMPORTAR
echo.
echo   Abriendo importar-wordpress.bat...
ping -n 2 127.0.0.1 > nul
call "%~dp0importar-wordpress.bat"
goto FIN

:FIN
echo.
echo   Presiona cualquier tecla para cerrar...
pause > nul
exit