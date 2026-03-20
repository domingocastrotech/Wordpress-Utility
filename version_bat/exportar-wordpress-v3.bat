@echo off
if /I "%~1"=="__RUN__" (
	shift
) else (
	start "Exportar WordPress" cmd /k ""%~f0" __RUN__"
	exit /b
)

setlocal EnableDelayedExpansion

for /f %%e in ('echo prompt $E^| cmd') do set "ESC=%%e"
set "C_RST=%ESC%[0m"
set "C_TIT=%ESC%[96m"
set "C_OK=%ESC%[92m"
set "C_WARN=%ESC%[93m"
set "C_ERR=%ESC%[91m"
set "C_INFO=%ESC%[94m"

set "DEF_WP_CONTAINER=wordpress"
set "DEF_DB_CONTAINER=mariadb"
set "DEF_DB_USER=admin"
set "DEF_DB_PASS=admin"
set "DEF_DB_NAME=wordpress"
set "DEF_LOCAL_URL=http://localhost:8181"
set "DEF_DOMINIO=https://tudominio.com"

:INICIO
cls
echo !C_TIT!================================================!C_RST!
echo !C_TIT!  EXPORTAR WORDPRESS DE DOCKER AL HOSTING!C_RST!
echo !C_TIT!================================================!C_RST!
echo.

where docker > nul 2>&1
if errorlevel 1 (
	echo !C_ERR!No se encontro el comando docker.!C_RST!
	echo !C_WARN!Abre Docker Desktop y prueba de nuevo.!C_RST!
	goto FIN_ERROR
)

docker info > nul 2>&1
if errorlevel 1 (
	echo !C_ERR!Docker no esta operativo en este momento.!C_RST!
	echo !C_WARN!Arranca Docker Desktop y vuelve a ejecutar este script.!C_RST!
	goto FIN_ERROR
)

call :SELECCIONAR_CONTENEDOR "Selecciona el contenedor de WordPress" "%DEF_WP_CONTAINER%" WP_CONTAINER "WP" "0"
set "_RC=!errorlevel!"
if "!_RC!"=="10" goto FIN_CANCEL
if "!_RC!"=="20" goto INICIO
if not "!_RC!"=="0" goto FIN_ERROR

:SELECCION_DB_CONT
call :SELECCIONAR_CONTENEDOR "Selecciona el contenedor de base de datos" "%DEF_DB_CONTAINER%" DB_CONTAINER "DB" "1"
set "_RC=!errorlevel!"
if "!_RC!"=="10" goto FIN_CANCEL
if "!_RC!"=="20" goto INICIO
if not "!_RC!"=="0" goto FIN_ERROR

set "_RUN="
for /f %%R in ('docker inspect -f "{{.State.Running}}" "!WP_CONTAINER!" 2^>nul') do set "_RUN=%%R"
if /I "!_RUN!"=="true" (
	echo !C_OK!Contenedor !C_INFO!!WP_CONTAINER!!C_OK! ya esta arrancado.!C_RST!
) else (
	echo !C_WARN!El contenedor !C_INFO!!WP_CONTAINER!!C_WARN! esta apagado.!C_RST!
	set "_A="
	set /p "_A=Quieres arrancarlo ahora? [S] Si / [V] Volver / [X] Salir: "
	if /I "!_A!"=="X" goto FIN_CANCEL
	if /I "!_A!"=="V" goto INICIO
	if /I not "!_A!"=="S" goto INICIO

	set "_START_LOG=%TEMP%\docker_start_!RANDOM!.log"
	docker start "!WP_CONTAINER!" > "!_START_LOG!" 2>&1
	if errorlevel 1 (
		echo !C_ERR!No se pudo arrancar !WP_CONTAINER!.!C_RST!
		echo !C_WARN!Motivo reportado por Docker:!C_RST!
		type "!_START_LOG!"
		del /q "!_START_LOG!" > nul 2>&1
		echo.
		echo !C_INFO!Pulsa una tecla para volver al inicio...!C_RST!
		pause > nul
		cls
		goto INICIO
	)
	del /q "!_START_LOG!" > nul 2>&1
	echo !C_OK!Contenedor !WP_CONTAINER! arrancado.!C_RST!
)

set "_RUN="
for /f %%R in ('docker inspect -f "{{.State.Running}}" "!DB_CONTAINER!" 2^>nul') do set "_RUN=%%R"
if /I "!_RUN!"=="true" (
	echo !C_OK!Contenedor !C_INFO!!DB_CONTAINER!!C_OK! ya esta arrancado.!C_RST!
) else (
	echo !C_WARN!El contenedor !C_INFO!!DB_CONTAINER!!C_WARN! esta apagado.!C_RST!
	set "_A="
	set /p "_A=Quieres arrancarlo ahora? [S] Si / [V] Volver / [X] Salir: "
	if /I "!_A!"=="X" goto FIN_CANCEL
	if /I "!_A!"=="V" goto SELECCION_DB_CONT
	if /I not "!_A!"=="S" goto SELECCION_DB_CONT

	set "_START_LOG=%TEMP%\docker_start_!RANDOM!.log"
	docker start "!DB_CONTAINER!" > "!_START_LOG!" 2>&1
	if errorlevel 1 (
		echo !C_ERR!No se pudo arrancar !DB_CONTAINER!.!C_RST!
		echo !C_WARN!Motivo reportado por Docker:!C_RST!
		type "!_START_LOG!"
		del /q "!_START_LOG!" > nul 2>&1
		echo.
		echo !C_INFO!Pulsa una tecla para volver al inicio...!C_RST!
		pause > nul
		cls
		goto INICIO
	)
	del /q "!_START_LOG!" > nul 2>&1
	echo !C_OK!Contenedor !DB_CONTAINER! arrancado.!C_RST!
)

echo.
set "_I="
set /p "_I=Usuario BD [!DEF_DB_USER!]: "
if "!_I!"=="" (set "DB_USER=!DEF_DB_USER!") else (set "DB_USER=!_I!")

set "_I="
set /p "_I=Password BD [!DEF_DB_PASS!]: "
if "!_I!"=="" (set "DB_PASS=!DEF_DB_PASS!") else (set "DB_PASS=!_I!")

call :SELECCIONAR_BASE_DATOS "!DB_CONTAINER!" "!DB_USER!" "!DB_PASS!" "%DEF_DB_NAME%" DB_NAME
set "_RC=!errorlevel!"
if "!_RC!"=="10" goto FIN_CANCEL
if "!_RC!"=="20" goto SELECCION_DB_CONT
if not "!_RC!"=="0" goto FIN_ERROR

set "_I="
set /p "_I=URL local actual [!DEF_LOCAL_URL!]: "
if "!_I!"=="" (set "LOCAL_URL=!DEF_LOCAL_URL!") else (set "LOCAL_URL=!_I!")

set "_I="
set /p "_I=Dominio real de produccion [!DEF_DOMINIO!]: "
if "!_I!"=="" (set "DOMINIO=!DEF_DOMINIO!") else (set "DOMINIO=!_I!")

echo.
echo !C_TIT!RESUMEN!C_RST!
echo   WordPress    : !WP_CONTAINER!
echo   Contenedor DB: !DB_CONTAINER!
echo   Base de datos: !DB_NAME!
echo   Usuario DB   : !DB_USER!
echo   URL local    : !LOCAL_URL!
echo   Dominio prod : !DOMINIO!
echo.
set "_CONFIRM="
set /p "_CONFIRM=Continuar con la exportacion? [S/N]: "
if /I not "!_CONFIRM!"=="S" goto FIN_CANCEL

set "FECHA_DIR="
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString(''yyyy_MM_dd_HH-mm'')"') do set "FECHA_DIR=%%I"

echo(!FECHA_DIR!| findstr /r "^[0-9][0-9][0-9][0-9]_[0-9][0-9]_[0-9][0-9]_[0-9][0-9]-[0-9][0-9]$" > nul
if errorlevel 1 (
	for /f "tokens=2 delims==" %%T in ('wmic os get localdatetime /value 2^>nul ^| find "="') do set "_DT=%%T"
	if defined _DT set "FECHA_DIR=!_DT:~0,4!_!_DT:~4,2!_!_DT:~6,2!_!_DT:~8,2!-!_DT:~10,2!"
)

if not defined FECHA_DIR set "FECHA_DIR=backup_manual"
set "BACKUP_DIR=%USERPROFILE%\Desktop\wordpress-export\!FECHA_DIR!"

echo.
echo !C_INFO!Creando carpeta de backup en !BACKUP_DIR!...!C_RST!
mkdir "!BACKUP_DIR!" 2>nul

echo.
echo !C_INFO![1/4]!C_RST! Corrigiendo URL local por dominio real...
docker exec "!WP_CONTAINER!" wp search-replace "!LOCAL_URL!" "!DOMINIO!" --allow-root --path=/opt/bitnami/wordpress > nul 2>&1
if errorlevel 1 (
	echo !C_ERR![ERROR]!C_RST! Fallo al actualizar URL en WordPress.
	goto FIN_ERROR
)
echo !C_OK![ OK ]!C_RST! URL corregida.

echo.
echo !C_INFO![2/4]!C_RST! Exportando base de datos...
docker exec -u root "!DB_CONTAINER!" sh -c "mysqldump -h 127.0.0.1 -u !DB_USER! -p!DB_PASS! !DB_NAME! > /tmp/export.sql" > nul 2>&1
if errorlevel 1 (
	echo !C_ERR![ERROR]!C_RST! Fallo al generar export.sql dentro del contenedor.
	goto RESTAURAR_URL_ERROR
)
docker cp "!DB_CONTAINER!:/tmp/export.sql" "!BACKUP_DIR!\export.sql" > nul 2>&1
if errorlevel 1 (
	echo !C_ERR![ERROR]!C_RST! Fallo al copiar export.sql al equipo.
	goto RESTAURAR_URL_ERROR
)
echo !C_OK![ OK ]!C_RST! Base de datos exportada en !BACKUP_DIR!\export.sql

echo.
echo !C_INFO![3/4]!C_RST! Exportando wp-content...
docker exec -u root "!WP_CONTAINER!" sh -c "tar chf /tmp/wp-content.tar -C /opt/bitnami/wordpress wp-content" > nul 2>&1
if errorlevel 1 (
	echo !C_ERR![ERROR]!C_RST! Fallo al empaquetar wp-content en el contenedor.
	goto RESTAURAR_URL_ERROR
)
docker cp "!WP_CONTAINER!:/tmp/wp-content.tar" "!BACKUP_DIR!\wp-content.tar" > nul 2>&1
if errorlevel 1 (
	echo !C_ERR![ERROR]!C_RST! Fallo al copiar wp-content.tar al equipo.
	goto RESTAURAR_URL_ERROR
)
tar -xf "!BACKUP_DIR!\wp-content.tar" -C "!BACKUP_DIR!" > nul 2>&1
if errorlevel 1 (
	echo !C_WARN![WARN]!C_RST! No se pudo extraer wp-content.tar automaticamente.
) else (
	echo !C_OK![ OK ]!C_RST! Carpeta wp-content exportada.
)

echo.
echo !C_INFO![4/4]!C_RST! Restaurando URL local...
docker exec "!WP_CONTAINER!" wp search-replace "!DOMINIO!" "!LOCAL_URL!" --allow-root --path=/opt/bitnami/wordpress > nul 2>&1
if errorlevel 1 (
	echo !C_WARN![WARN]!C_RST! No se pudo restaurar la URL local automaticamente.
) else (
	echo !C_OK![ OK ]!C_RST! URL local restaurada.
)

echo.
echo !C_OK!================================================!C_RST!
echo !C_OK!  EXPORTACION COMPLETA!C_RST!
echo !C_OK!================================================!C_RST!
echo.
echo Archivos listos en: !BACKUP_DIR!
echo.
echo   - export.sql       ^(base de datos^)
echo   - wp-content\      ^(carpeta^)
echo   - wp-content.tar   ^(tar^)
echo.
echo PASOS SIGUIENTES:
echo  1. Importar export.sql en phpMyAdmin del hosting
echo  2. Subir wp-content por FTP a public_html/wp-content
echo  3. NO tocar wp-config.php del hosting
echo.
echo Pulsa una tecla para cerrar...
pause > nul
exit

:RESTAURAR_URL_ERROR
echo.
echo !C_WARN!Intentando restaurar URL local tras el error...!C_RST!
docker exec "!WP_CONTAINER!" wp search-replace "!DOMINIO!" "!LOCAL_URL!" --allow-root --path=/opt/bitnami/wordpress > nul 2>&1
goto FIN_ERROR

:SELECCIONAR_CONTENEDOR
set "_TITULO=%~1"
set "_DEFAULT=%~2"
set "_RET=%~3"
set "_FILTER=%~4"
set "_ALLOW_BACK=%~5"

call :CARGAR_CONTENEDORES "!_FILTER!"
if !TOTAL! equ 0 (
	if /I "!_FILTER!"=="WP" (
		echo !C_ERR!No hay contenedores de WordPress detectados.!C_RST!
	) else (
		if /I "!_FILTER!"=="DB" (
			echo !C_ERR!No hay contenedores de base de datos detectados.!C_RST!
		) else (
			echo !C_ERR!No hay contenedores creados en Docker.!C_RST!
		)
	)
	exit /b 1
)

set /a _DEF_IDX=0
echo.
echo !C_TIT!%~1!C_RST!
for /L %%I in (1,1,!TOTAL!) do (
	if /I "!CONT_%%I!"=="!_DEFAULT!" set /a _DEF_IDX=%%I
	if /I "!EST_%%I!"=="ARRANCADO" (
		echo   %%I^) !C_OK![ON ]!C_RST! !CONT_%%I!
	) else (
		echo   %%I^) !C_ERR![OFF]!C_RST! !CONT_%%I!
	)
)

if !_DEF_IDX! gtr 0 (
	set "_PROMPT=Elige numero [!_DEF_IDX!]: "
) else (
	set "_PROMPT=Elige numero: "
)

:ASK_NUM_CONT
echo.
if "!_ALLOW_BACK!"=="1" (
	echo !C_INFO!Opciones: numero ^| V volver atras ^| S salir!C_RST!
) else (
	echo !C_INFO!Opciones: numero ^| S salir!C_RST!
)
set "_SEL="
set /p "_SEL=!_PROMPT!"
if "!_SEL!"=="" if !_DEF_IDX! gtr 0 set "_SEL=!_DEF_IDX!"

if /I "!_SEL!"=="S" exit /b 10
if /I "!_SEL!"=="X" exit /b 10
if /I "!_SEL!"=="V" (
	if "!_ALLOW_BACK!"=="1" (
		exit /b 20
	) else (
		echo !C_WARN!No hay paso anterior desde esta pantalla.!C_RST!
		goto ASK_NUM_CONT
	)
)
if "!_SEL!"=="0" (
	if "!_ALLOW_BACK!"=="1" exit /b 20
)

set "_CHOSEN="
for /L %%I in (1,1,!TOTAL!) do (
	if "!_SEL!"=="%%I" set "_CHOSEN=!CONT_%%I!"
)

if not defined _CHOSEN (
	echo !C_WARN!Seleccion no valida.!C_RST!
	goto ASK_NUM_CONT
)

set "%_RET%=!_CHOSEN!"
echo !C_OK!Seleccionado: !_CHOSEN!!C_RST!
exit /b 0

:CARGAR_CONTENEDORES
set "_FILTER=%~1"
set /a TOTAL=0
for /L %%I in (1,1,300) do (
	set "CONT_%%I="
	set "EST_%%I="
)
for /f "tokens=1,2,3 delims=|" %%A in ('docker ps -a --format "{{.Names}}|{{.Status}}|{{.Image}}" 2^>nul') do (
	set "_ADD=1"
	if /I "!_FILTER!"=="WP" (
		echo %%A %%C | findstr /i "wordpress" > nul 2>&1
		if errorlevel 1 set "_ADD=0"
	)
	if /I "!_FILTER!"=="DB" (
		echo %%A %%C | findstr /i "mariadb mysql" > nul 2>&1
		if errorlevel 1 set "_ADD=0"
	)
	if "!_ADD!"=="1" (
		set /a TOTAL+=1
		set "CONT_!TOTAL!=%%A"
		set "EST_!TOTAL!=APAGADO"
		for /f "tokens=1" %%S in ("%%B") do (
			if /I "%%S"=="Up" set "EST_!TOTAL!=ARRANCADO"
		)
	)
)
exit /b 0

:CHECK_START_CONTAINER
set "_CONT=%~1"
set "_RUN="
for /f %%R in ('docker inspect -f "{{.State.Running}}" "!_CONT!" 2^>nul') do set "_RUN=%%R"
if /I "!_RUN!"=="true" (
	echo !C_OK!Contenedor !C_INFO!!_CONT!!C_OK! ya esta arrancado.!C_RST!
	exit /b 0
)

echo !C_WARN!El contenedor !C_INFO!!_CONT!!C_WARN! esta apagado.!C_RST!
set "_A="
set /p "_A=Quieres arrancarlo ahora? [S] Si / [V] Volver / [X] Salir: "
if /I "!_A!"=="X" exit /b 10
if /I "!_A!"=="V" exit /b 3
if /I not "!_A!"=="S" exit /b 3

set "_START_LOG=%TEMP%\docker_start_!RANDOM!.log"
docker start "!_CONT!" > "!_START_LOG!" 2>&1
if errorlevel 1 (
	echo !C_ERR!No se pudo arrancar !_CONT!.!C_RST!
	echo !C_WARN!Motivo reportado por Docker:!C_RST!
	type "!_START_LOG!"
	del /q "!_START_LOG!" > nul 2>&1
	echo.
	echo !C_INFO!Pulsa una tecla para volver al inicio...!C_RST!
	pause > nul
	cls
	exit /b 2
)
del /q "!_START_LOG!" > nul 2>&1
echo !C_OK!Contenedor !_CONT! arrancado.!C_RST!
exit /b 0

:SELECCIONAR_BASE_DATOS
set "_DB_CONT=%~1"
set "_DB_USER=%~2"
set "_DB_PASS=%~3"
set "_DB_DEF=%~4"
set "_RET=%~5"

set /a DB_TOTAL=0
for /L %%I in (1,1,300) do set "DB_%%I="

for /f "delims=" %%D in ('docker exec -u root "!_DB_CONT!" sh -c "mysql -h 127.0.0.1 -u !_DB_USER! -p!_DB_PASS! -N -e \"SHOW DATABASES;\"" 2^>nul') do (
	set "_DBNAME=%%D"
	if /I not "!_DBNAME!"=="information_schema" (
	if /I not "!_DBNAME!"=="performance_schema" (
	if /I not "!_DBNAME!"=="mysql" (
	if /I not "!_DBNAME!"=="sys" (
	if /I not "!_DBNAME!"=="test" (
		set /a DB_TOTAL+=1
		set "DB_!DB_TOTAL!=!_DBNAME!"
	)))))
)

if !DB_TOTAL! equ 0 (
	echo !C_WARN!No se pudo listar bases por SQL ^(credenciales o cliente mysql^).!C_RST!
	set "_DB_MANUAL="
	echo !C_INFO!Opciones: escribe nombre ^| V volver atras ^| S salir!C_RST!
	set /p "_DB_MANUAL=Nombre de base de datos [!_DB_DEF!]: "
	if /I "!_DB_MANUAL!"=="S" exit /b 10
	if /I "!_DB_MANUAL!"=="X" exit /b 10
	if /I "!_DB_MANUAL!"=="V" exit /b 20
	if "!_DB_MANUAL!"=="0" exit /b 20
	if "!_DB_MANUAL!"=="" (set "_DB_MANUAL=!_DB_DEF!")
	set "%_RET%=!_DB_MANUAL!"
	echo !C_OK!Base de datos seleccionada: !_DB_MANUAL!!C_RST!
	exit /b 0
)

set /a _DB_DEF_IDX=0
echo.
echo !C_TIT!Selecciona la base de datos!C_RST!
for /L %%I in (1,1,!DB_TOTAL!) do (
	if /I "!DB_%%I!"=="!_DB_DEF!" set /a _DB_DEF_IDX=%%I
	echo   %%I^) !DB_%%I!
)

if !_DB_DEF_IDX! gtr 0 (
	set "_PROMPT_DB=Elige numero [!_DB_DEF_IDX!]: "
) else (
	set "_PROMPT_DB=Elige numero: "
)

:ASK_NUM_DB
echo.
echo !C_INFO!Opciones: numero ^| V volver atras ^| S salir!C_RST!
set "_DB_SEL="
set /p "_DB_SEL=!_PROMPT_DB!"
if "!_DB_SEL!"=="" if !_DB_DEF_IDX! gtr 0 set "_DB_SEL=!_DB_DEF_IDX!"

if /I "!_DB_SEL!"=="S" exit /b 10
if /I "!_DB_SEL!"=="X" exit /b 10
if /I "!_DB_SEL!"=="V" exit /b 20
if "!_DB_SEL!"=="0" exit /b 20

set "_DB_CHOSEN="
for /L %%I in (1,1,!DB_TOTAL!) do (
	if "!_DB_SEL!"=="%%I" set "_DB_CHOSEN=!DB_%%I!"
)

if not defined _DB_CHOSEN (
	echo !C_WARN!Seleccion no valida.!C_RST!
	goto ASK_NUM_DB
)

set "%_RET%=!_DB_CHOSEN!"
echo !C_OK!Base de datos seleccionada: !_DB_CHOSEN!!C_RST!
exit /b 0

:FIN_CANCEL
echo.
echo !C_WARN!Operacion cancelada por usuario.!C_RST!
echo Pulsa una tecla para cerrar...
pause > nul
exit

:FIN_ERROR
echo.
echo !C_ERR!Exportacion finalizada con errores.!C_RST!
echo Pulsa una tecla para cerrar...
pause > nul
exit