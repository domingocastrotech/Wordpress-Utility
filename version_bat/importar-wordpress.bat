@echo off
setlocal enabledelayedexpansion

for /f %%e in ('echo prompt $E^| cmd') do set "ESC=%%e"
set "C_RST=%ESC%[0m"
set "C_TIT=%ESC%[96m"
set "C_OK=%ESC%[92m"
set "C_WARN=%ESC%[93m"
set "C_ERR=%ESC%[91m"
set "C_INFO=%ESC%[94m"

cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  IMPORTAR WORDPRESS A DOCKER!C_RST!
echo !C_TIT!================================================!C_RST!
echo(

:: Directorio base - carpeta padre del bat
set BAT_DIR=%~dp0
set BAT_DIR=%BAT_DIR:~0,-1%
set BASE_DIR=%BAT_DIR%/../

:: ================================================
:: LISTAR CONTENEDORES DOCKER
:: ================================================
cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  SELECCIONAR CONTENEDORES!C_RST!
echo !C_TIT!================================================!C_RST!
echo(

where docker > nul 2>&1
if errorlevel 1 (
    echo   !C_ERR![ ERROR ]!C_RST!  No se encontro el comando Docker.
    echo              Instala/inicia Docker Desktop y vuelve a intentarlo.
    echo(
    pause
    exit /b 1
)

:: ------------------------------------------------
:: ELEGIR CONTENEDOR WORDPRESS
:: ------------------------------------------------
:ELEGIR_WP
cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  CONTENEDOR WORDPRESS - Selecciona uno!C_RST!
echo !C_TIT!================================================!C_RST!
echo(

set WPCOUNT=0
for /f "tokens=*" %%C in ('docker ps -a --format "{{.Names}}|{{.Status}}|{{.Image}}" 2^>nul ^| findstr /i "wordpress"') do (
    set /a WPCOUNT+=1
    set "WP_!WPCOUNT!=%%C"
)

if "!WPCOUNT!"=="0" (
    echo   !C_ERR![ ERROR ]!C_RST!  No se detectaron contenedores de WordPress.
    echo              Se busca por nombre/imagen que contenga "wordpress".
    echo(
    pause
    exit /b 1
)

for /l %%I in (1,1,!WPCOUNT!) do (
    for /f "tokens=1,2,3 delims=|" %%A in ("!WP_%%I!") do (
        echo %%B | findstr /i "Up" > nul 2>&1
        if !errorlevel! equ 0 (
            echo   [%%I] !C_OK!%%A!C_RST!  ^(En ejecucion^)  [%%C]
        ) else (
            echo   [%%I] !C_WARN!%%A!C_RST!  ^(Parado^)  [%%C]
        )
    )
)

echo(
set /p "WP_SEL=   Contenedor de WordPress [numero]: "

set "_VAL=!WP_%WP_SEL%!"
if "!_VAL!"=="" (
    echo   !C_WARN![ WARN ]!C_RST!  Seleccion invalida, intentalo de nuevo.
    ping -n 2 127.0.0.1 > nul
    goto ELEGIR_WP
)

for /f "tokens=1,3 delims=|" %%A in ("!_VAL!") do (
    set "CONT_WORDPRESS=%%A"
    set "CONT_WP_IMAGE=%%B"
)

echo(
echo   !C_OK![  OK  ]!C_RST!  Contenedor WordPress: !CONT_WORDPRESS!  [!CONT_WP_IMAGE!]

:: ------------------------------------------------
:: ELEGIR CONTENEDOR MARIADB
:: ------------------------------------------------
:ELEGIR_DB
cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  CONTENEDOR BASE DE DATOS - Selecciona uno!C_RST!
echo !C_TIT!================================================!C_RST!
echo(

set DBCONTCOUNT=0
for /f "tokens=*" %%C in ('docker ps -a --format "{{.Names}}|{{.Status}}|{{.Image}}" 2^>nul ^| findstr /i "mariadb mysql"') do (
    set /a DBCONTCOUNT+=1
    set "DBCONT_!DBCONTCOUNT!=%%C"
)

if "!DBCONTCOUNT!"=="0" (
    echo   !C_ERR![ ERROR ]!C_RST!  No se detectaron contenedores de base de datos.
    echo              Se busca por nombre/imagen que contenga "mariadb" o "mysql".
    echo(
    pause
    exit /b 1
)

for /l %%I in (1,1,!DBCONTCOUNT!) do (
    for /f "tokens=1,2,3 delims=|" %%A in ("!DBCONT_%%I!") do (
        echo %%B | findstr /i "Up" > nul 2>&1
        if !errorlevel! equ 0 (
            echo   [%%I] !C_OK!%%A!C_RST!  ^(En ejecucion^)  [%%C]
        ) else (
            echo   [%%I] !C_WARN!%%A!C_RST!  ^(Parado^)  [%%C]
        )
    )
)

echo(
set /p "DB_SEL=   Contenedor de MariaDB/MySQL [numero]: "

set "_VAL=!DBCONT_%DB_SEL%!"
if "!_VAL!"=="" (
    echo   !C_WARN![ WARN ]!C_RST!  Seleccion invalida, intentalo de nuevo.
    ping -n 2 127.0.0.1 > nul
    goto ELEGIR_DB
)

for /f "tokens=1,3 delims=|" %%A in ("!_VAL!") do (
    set "CONT_MARIADB=%%A"
    set "CONT_DB_IMAGE=%%B"
)

echo(
echo   !C_OK![  OK  ]!C_RST!  Contenedor MariaDB: !CONT_MARIADB!  [!CONT_DB_IMAGE!]
ping -n 2 127.0.0.1 > nul

:: ================================================
:: VERIFICAR Y ARRANCAR CONTENEDORES SI ES NECESARIO
:: ================================================
cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  VERIFICANDO CONTENEDORES!C_RST!
echo !C_TIT!================================================!C_RST!
echo(

:: Verificar estado WordPress
for /f "tokens=*" %%S in ('docker inspect --format "{{.State.Status}}" "!CONT_WORDPRESS!" 2^>nul') do set "WP_STATUS=%%S"
if /i "!WP_STATUS!" neq "running" (
    echo   !C_WARN![ WARN ]!C_RST!  !CONT_WORDPRESS! no esta en ejecucion ^(estado: !WP_STATUS!^)
    echo            Intentando arrancarlo...
    docker start "!CONT_WORDPRESS!" > nul 2>&1
    ping -n 5 127.0.0.1 > nul
    echo   !C_OK![  OK  ]!C_RST!  !CONT_WORDPRESS! arrancado
) else (
    echo   !C_OK![  OK  ]!C_RST!  !CONT_WORDPRESS! esta en ejecucion
)

:: Verificar estado MariaDB
for /f "tokens=*" %%S in ('docker inspect --format "{{.State.Status}}" "!CONT_MARIADB!" 2^>nul') do set "DB_STATUS=%%S"
if /i "!DB_STATUS!" neq "running" (
    echo   !C_WARN![ WARN ]!C_RST!  !CONT_MARIADB! no esta en ejecucion ^(estado: !DB_STATUS!^)
    echo            Intentando arrancarlo...
    docker start "!CONT_MARIADB!" > nul 2>&1
    ping -n 8 127.0.0.1 > nul
    echo   !C_OK![  OK  ]!C_RST!  !CONT_MARIADB! arrancado
) else (
    echo   !C_OK![  OK  ]!C_RST!  !CONT_MARIADB! esta en ejecucion
)

echo(

:: ================================================
:: AUTO-DETECTAR PUERTO DEL CONTENEDOR WORDPRESS
:: ================================================
echo   Detectando puerto del contenedor WordPress...

set "WP_PORT="

for /f "tokens=3 delims=:" %%P in ('docker port "!CONT_WORDPRESS!" 8080 2^>nul') do (
    if "!WP_PORT!"=="" set "WP_PORT=%%P"
)
if "!WP_PORT!"=="" (
    for /f "tokens=3 delims=:" %%P in ('docker port "!CONT_WORDPRESS!" 80 2^>nul') do (
        if "!WP_PORT!"=="" set "WP_PORT=%%P"
    )
)
if "!WP_PORT!"=="" (
    for /f "tokens=3 delims=:" %%P in ('docker port "!CONT_WORDPRESS!" 2^>nul') do (
        if "!WP_PORT!"=="" set "WP_PORT=%%P"
    )
)
if defined WP_PORT for /f "tokens=1" %%C in ("!WP_PORT!") do set "WP_PORT=%%C"

if "!WP_PORT!"=="" (
    echo   !C_WARN![ WARN ]!C_RST!  No se pudo detectar el puerto automaticamente.
    set /p "WP_PORT=   Introduce el puerto manualmente ^(ej: 8181^): "
) else (
    echo   !C_OK![  OK  ]!C_RST!  Puerto detectado: !WP_PORT!
)

set "LOCAL_URL=http://localhost:!WP_PORT!"
echo   !C_OK![  OK  ]!C_RST!  URL local detectada: !LOCAL_URL!
set "DOMINIO_REAL=https://tudominio.com"
set /p "_IN_DOM=   Dominio real del backup [!DOMINIO_REAL!]: "
if not "!_IN_DOM!"=="" set "DOMINIO_REAL=!_IN_DOM!"
echo   !C_OK![  OK  ]!C_RST!  Dominio del backup: !DOMINIO_REAL!
echo(

:: ================================================
:: AUTO-DETECTAR CREDENCIALES MYSQL
:: ================================================
echo   Detectando credenciales MySQL de !CONT_MARIADB!...

set "DB_USER="
set "DB_PASS="

for /f "tokens=1* delims==" %%A in ('docker exec !CONT_MARIADB! env 2^>nul') do (
    if /i "%%A"=="MARIADB_ROOT_PASSWORD" if "!DB_USER!"=="" (
        set "DB_USER=root"
        set "DB_PASS=%%B"
    )
    if /i "%%A"=="MYSQL_ROOT_PASSWORD" if "!DB_USER!"=="" (
        set "DB_USER=root"
        set "DB_PASS=%%B"
    )
)
if "!DB_USER!"=="" (
    for /f "tokens=1* delims==" %%A in ('docker exec !CONT_MARIADB! env 2^>nul') do (
        if /i "%%A"=="MARIADB_USER"     if "!DB_USER!"=="" set "DB_USER=%%B"
        if /i "%%A"=="MYSQL_USER"       if "!DB_USER!"=="" set "DB_USER=%%B"
        if /i "%%A"=="MARIADB_PASSWORD" if "!DB_PASS!"=="" set "DB_PASS=%%B"
        if /i "%%A"=="MYSQL_PASSWORD"   if "!DB_PASS!"=="" set "DB_PASS=%%B"
    )
)
if "!DB_USER!"=="" set "DB_USER=admin"
if "!DB_PASS!"=="" set "DB_PASS=admin"

echo   !C_OK![  OK  ]!C_RST!  Credenciales detectadas: usuario=!DB_USER!
echo(

:: ================================================
:: LISTAR Y ELEGIR BBDD DEL CONTENEDOR MARIADB
:: ================================================
:BBDD_LISTAR
cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  BASES DE DATOS EN: !CONT_MARIADB!!C_RST!
echo !C_TIT!================================================!C_RST!
echo(

set DBCOUNT=0

for /f "skip=1 tokens=*" %%D in ('docker exec !CONT_MARIADB! mysql -h 127.0.0.1 -u !DB_USER! -p!DB_PASS! -N -e "SHOW DATABASES;" 2^>nul') do (
    set "DBNAME=%%D"
    if /i "!DBNAME!" neq "information_schema" (
    if /i "!DBNAME!" neq "performance_schema" (
    if /i "!DBNAME!" neq "mysql" (
    if /i "!DBNAME!" neq "sys" (
        set /a DBCOUNT+=1
        set "DB_!DBCOUNT!=!DBNAME!"
        echo   [!DBCOUNT!] !DBNAME!
    ))))
)

if "!DBCOUNT!"=="0" (
    echo   !C_WARN![ WARN ]!C_RST!  No se pudo listar bases de datos.
    echo            Credenciales incorrectas o contenedor aun iniciando.
    echo(
    set /p "DB_USER=   Usuario MySQL -> "
    set /p "DB_PASS=   Password MySQL -> "
    echo(
    set DBCOUNT=0
    for /f "skip=1 tokens=*" %%D in ('docker exec !CONT_MARIADB! mysql -h 127.0.0.1 -u !DB_USER! -p!DB_PASS! -N -e "SHOW DATABASES;" 2^>nul') do (
        set "DBNAME=%%D"
        if /i "!DBNAME!" neq "information_schema" (
        if /i "!DBNAME!" neq "performance_schema" (
        if /i "!DBNAME!" neq "mysql" (
        if /i "!DBNAME!" neq "sys" (
            set /a DBCOUNT+=1
            set "DB_!DBCOUNT!=!DBNAME!"
            echo   [!DBCOUNT!] !DBNAME!
        ))))
    )
)

if "!DBCOUNT!"=="0" (
    echo   !C_ERR![ ERROR ]!C_RST!  No se pudo conectar a MySQL. Introduce el nombre manualmente:
    set /p "DB_NOMBRE=   -> Nombre BBDD: "
    goto BBDD_OK
)

if "!DBCOUNT!"=="1" (
    set "DB_NOMBRE=!DB_1!"
    echo(
    echo   !C_OK![  OK  ]!C_RST!  Unica base de datos disponible, seleccionada: !DB_NOMBRE!
    goto BBDD_OK
)

:BBDD_ELEGIR
echo(
set /p "DBSEL=   Selecciona la base de datos [numero]: "
set "_VAL=!DB_%DBSEL%!"
if "!_VAL!"=="" (
    echo   Seleccion invalida, intentalo de nuevo.
    goto BBDD_ELEGIR
)
set "DB_NOMBRE=!_VAL!"
echo   !C_OK![  OK  ]!C_RST!  Base de datos seleccionada: !DB_NOMBRE!

:BBDD_OK
echo(

:: ================================================
:: NAVEGADOR DE CARPETAS
:: ================================================
:NAVEGAR
cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  SELECCIONAR BACKUP!C_RST!
echo !C_TIT!================================================!C_RST!
echo(
echo Ubicacion actual: !BASE_DIR!
echo(

set DIRCOUNT=0
set ITEMCOUNT=0

echo [Carpetas]
for /f "delims=" %%F in ('dir /b /ad "!BASE_DIR!" 2^>nul') do (
    set /a DIRCOUNT+=1
    set "DIR_!DIRCOUNT!=%%F"

    set HAS_CONTENT=
    if exist "!BASE_DIR!\%%F\wp-content\" set HAS_CONTENT= ^[wp-content^]
    if exist "!BASE_DIR!\%%F\*.tar" set HAS_CONTENT=!HAS_CONTENT! ^[tar^]
    if exist "!BASE_DIR!\%%F\*.zip" set HAS_CONTENT=!HAS_CONTENT! ^[zip^]
    if exist "!BASE_DIR!\%%F\*.sql" set HAS_CONTENT=!HAS_CONTENT! ^[sql^]

    echo   [!DIRCOUNT!] %%F!HAS_CONTENT!
)

echo(
echo [Archivos]
set HASFILES=0
for /f "delims=" %%F in ('dir /b "!BASE_DIR!\*.tar" "!BASE_DIR!\*.zip" "!BASE_DIR!\*.sql" 2^>nul') do (
    set /a ITEMCOUNT+=1
    set /a NUM=!DIRCOUNT!+!ITEMCOUNT!
    set "ITEM_!NUM!=%%F"
    set HASFILES=1
    echo   [!NUM!] %%F
)
if exist "!BASE_DIR!\wp-content\" (
    set /a ITEMCOUNT+=1
    set /a NUM=!DIRCOUNT!+!ITEMCOUNT!
    set "ITEM_!NUM!=wp-content"
    set HASFILES=1
    echo   [!NUM!] wp-content ^(carpeta^)
)
if "!HASFILES!"=="0" echo   (ninguno)

echo(
if not "!BASE_DIR!"=="!BAT_DIR!" echo   [0] .. Volver atras
echo(
set /p NAV="Selecciona carpeta o archivo: "

if /i "!NAV!"=="0" (
    for %%I in ("!BASE_DIR!\..") do set "BASE_DIR=%%~fI"
    goto NAVEGAR
)

set "_VAL=!DIR_%NAV%!"
if defined _VAL (
    if !NAV! leq !DIRCOUNT! (
        set "SELECTED_DIR=!_VAL!"
        set "BASE_DIR=!BASE_DIR!\!SELECTED_DIR!"
        set FOUND_CONTENT=0
        if exist "!BASE_DIR!\wp-content\" set FOUND_CONTENT=1
        for /f "delims=" %%F in ('dir /b "!BASE_DIR!\*.tar" "!BASE_DIR!\*.zip" 2^>nul') do set FOUND_CONTENT=1
        if "!FOUND_CONTENT!"=="1" goto SELECCIONAR_ARCHIVOS
        goto NAVEGAR
    )
)

set /a MAXNUM=!DIRCOUNT!+!ITEMCOUNT!
if !NAV! gtr 0 if !NAV! leq !MAXNUM! goto SELECCIONAR_ARCHIVOS

echo Seleccion invalida.
ping -n 2 127.0.0.1 > nul
goto NAVEGAR

:: ================================================
:: SELECCIONAR WP-CONTENT Y SQL
:: ================================================
:SELECCIONAR_ARCHIVOS
cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  ARCHIVOS EN: !BASE_DIR!!C_RST!
echo !C_TIT!================================================!C_RST!
echo(

echo [wp-content disponible]
echo(
set COUNT=0

for /f "delims=" %%F in ('dir /b "!BASE_DIR!\*.tar" 2^>nul') do (
    set /a COUNT+=1
    set "FILE_!COUNT!=TAR|%%F"
    echo   [!COUNT!] %%F
)
for /f "delims=" %%F in ('dir /b "!BASE_DIR!\*.zip" 2^>nul') do (
    set /a COUNT+=1
    set "FILE_!COUNT!=ZIP|%%F"
    echo   [!COUNT!] %%F
)
if exist "!BASE_DIR!\wp-content\" (
    set /a COUNT+=1
    set "FILE_!COUNT!=CARPETA|wp-content"
    echo   [!COUNT!] wp-content ^(carpeta^)
)

if "!COUNT!"=="0" (
    echo No se encontro ningun wp-content tar, zip o carpeta.
    echo Volviendo al navegador...
    ping -n 3 127.0.0.1 > nul
    goto NAVEGAR
)

echo(
echo   [0] .. Volver atras
echo(
set /p SELECCION="Selecciona wp-content [numero]: "

if "!SELECCION!"=="0" goto NAVEGAR

set "WP_ENTRY=!FILE_%SELECCION%!"
if "!WP_ENTRY!"=="" (
    echo Seleccion invalida.
    ping -n 2 127.0.0.1 > nul
    goto SELECCIONAR_ARCHIVOS
)
for /f "tokens=1,2 delims=|" %%A in ("!WP_ENTRY!") do (
    set WP_TYPE=%%A
    set WP_NAME=%%B
)
set "WP_PATH=!BASE_DIR!\!WP_NAME!"
echo Seleccionado: !WP_NAME!
echo(

echo [SQL disponible]
echo(
set SQLCOUNT=0
for /f "delims=" %%F in ('dir /b "!BASE_DIR!\*.sql" 2^>nul') do (
    set /a SQLCOUNT+=1
    set "SQL_!SQLCOUNT!=%%F"
    echo   [!SQLCOUNT!] %%F
)

if "!SQLCOUNT!"=="0" (
    echo No se encontro ningun archivo .sql en esta carpeta.
    echo Volviendo al navegador...
    ping -n 3 127.0.0.1 > nul
    goto NAVEGAR
)

echo(
echo   [0] .. Volver atras
echo(
set /p SQLSEL="Selecciona SQL [numero]: "

if "!SQLSEL!"=="0" goto SELECCIONAR_ARCHIVOS

set "_VAL_SQL=!SQL_%SQLSEL%!"
if "!_VAL_SQL!"=="" (
    echo Seleccion invalida.
    ping -n 2 127.0.0.1 > nul
    goto SELECCIONAR_ARCHIVOS
)

set "SQL_FILE=!BASE_DIR!\!_VAL_SQL!"
echo Seleccionado: !_VAL_SQL!
echo(

echo ------------------------------------------------
echo  Contenedor WP  : !CONT_WORDPRESS!
echo  Contenedor BD  : !CONT_MARIADB!
echo  Base de datos  : !DB_NOMBRE!
echo  wp-content     : !WP_NAME! ^(!WP_TYPE!^)
echo  SQL            : !_VAL_SQL!
echo  URL local      : !LOCAL_URL!
echo  Dominio backup : !DOMINIO_REAL!
echo ------------------------------------------------
echo(
echo     ------------------ ADVERTENCIA
echo(
echo   Esta accion SOBREESCRIBIRA permanentemente:
echo(
echo     [x]  Todo el wp-content del contenedor !CONT_WORDPRESS!
echo     [x]  Toda la base de datos !DB_NOMBRE! en !CONT_MARIADB!
echo(
echo   Los cambios actuales del entorno local se PERDERAN.
echo   Esta accion NO se puede deshacer.
echo(
echo ------------------------------------------------
echo(
set /p "_CONFIRM=   Continuar? [S] Si  /  [N] No  ->  "
if /i "!_CONFIRM!"=="N" (
    echo(
    echo   Importacion cancelada. No se han realizado cambios.
    echo(
    pause
    exit /b 0
)
if /i "!_CONFIRM!" neq "S" (
    echo(
    echo   Opcion no valida. Saliendo...
    pause
    exit /b 1
)

:: ================================================
:: PASO 1 - Copiar wp-content al contenedor
:: ================================================
echo(
echo [1/4] Copiando wp-content al contenedor...
docker exec -u root !CONT_WORDPRESS! sh -c "rm -rf /tmp/wp-content /tmp/wp-content.tar /tmp/wp-content.zip"

if "!WP_TYPE!"=="TAR" goto ES_TAR
if "!WP_TYPE!"=="ZIP" goto ES_ZIP
goto ES_CARPETA

:ES_TAR
echo Procesando TAR...
docker cp "!WP_PATH!" !CONT_WORDPRESS!:/tmp/wp-content.tar
docker exec -u root !CONT_WORDPRESS! sh -c "cd /tmp && tar xf wp-content.tar"
goto COPIAR_CONTENIDO

:ES_ZIP
echo Procesando ZIP...
docker cp "!WP_PATH!" !CONT_WORDPRESS!:/tmp/wp-content.zip
docker exec -u root !CONT_WORDPRESS! sh -c "cd /tmp && unzip -q wp-content.zip"
goto COPIAR_CONTENIDO

:ES_CARPETA
echo Procesando carpeta...
docker cp "!WP_PATH!" !CONT_WORDPRESS!:/tmp/wp-content
goto COPIAR_CONTENIDO

:COPIAR_CONTENIDO
docker exec -u root !CONT_WORDPRESS! sh -c "cp -rf /tmp/wp-content/. /opt/bitnami/wordpress/wp-content/ 2>/dev/null || cp -rf /tmp/wp-content/* /opt/bitnami/wordpress/wp-content/"
docker exec -u root !CONT_WORDPRESS! sh -c "chown -R 1001:1001 /opt/bitnami/wordpress/wp-content"
echo wp-content copiado!

:: ================================================
:: PASO 2 - Importar base de datos
:: ================================================
echo(
echo [2/4] Importando base de datos...
docker cp "!SQL_FILE!" !CONT_MARIADB!:/tmp/export.sql
docker exec !CONT_MARIADB! sh -c "mysql -h 127.0.0.1 -u !DB_USER! -p!DB_PASS! !DB_NOMBRE! < /tmp/export.sql"
echo Base de datos importada!

:: ================================================
:: PASO 3 - Corregir URL
:: ================================================
echo(
echo [3/4] Corrigiendo URL del dominio a localhost...
if /i "!DOMINIO_REAL!"=="!LOCAL_URL!" (
    echo Dominio backup y URL local son iguales; se omite search-replace.
) else (
    docker exec !CONT_WORDPRESS! wp search-replace "!DOMINIO_REAL!" "!LOCAL_URL!" --allow-root --path=/opt/bitnami/wordpress
)
echo URL corregida!

:: ================================================
:: PASO 4 - Reiniciar WordPress
:: ================================================
echo(
echo [4/4] Reiniciando WordPress...
docker restart !CONT_WORDPRESS!
ping -n 15 127.0.0.1 > nul

echo(
echo !C_OK!================================================!C_RST!
echo !C_OK!  IMPORTACION COMPLETADA!C_RST!
echo !C_OK!================================================!C_RST!
echo(
echo Abre !LOCAL_URL!
echo Las credenciales son las del sitio original
echo(
pause