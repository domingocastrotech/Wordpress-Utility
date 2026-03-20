@echo off
setlocal EnableDelayedExpansion

for /f %%e in ('echo prompt $E^| cmd') do set "ESC=%%e"
set "C_RST=%ESC%[0m"
set "C_TIT=%ESC%[96m"
set "C_OK=%ESC%[92m"
set "C_ERR=%ESC%[91m"
set "C_WARN=%ESC%[93m"
set "C_INFO=%ESC%[94m"
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%historial_gestor.log"
set "PERFILES_FILE=%SCRIPT_DIR%perfiles_contenedores.ini"

:INICIO
cls
set "SALIR=0"
echo !C_TIT!==================================================!C_RST!
echo !C_TIT!  GESTOR DE CONTENEDORES DOCKER!C_RST!
echo !C_TIT!==================================================!C_RST!
echo.

call :INICIALIZAR_ARCHIVOS

call :ASEGURAR_DOCKER
if errorlevel 1 goto FIN_ERROR

:RECARGAR
call :CARGAR_CONTENEDORES
call :MOSTRAR_MENU
if "!SALIR!"=="1" goto FIN
goto RECARGAR

:INICIALIZAR_ARCHIVOS
if not exist "%LOG_FILE%" (
	> "%LOG_FILE%" echo [!date! !time:~0,8!] Historial del gestor de contenedores
)

if not exist "%PERFILES_FILE%" (
	> "%PERFILES_FILE%" (
		echo ; Formato: nombre_perfil=contenedor1,contenedor2
		echo ; Ejemplo: tienda=wordpress,mariadb
	)
)
exit /b 0

:ASEGURAR_DOCKER
where docker > nul 2>&1
if errorlevel 1 (
	echo !C_ERR!No se encontro el comando docker en el sistema.!C_RST!
	echo !C_WARN!Abre Docker Desktop y verifica que Docker CLI este instalado.!C_RST!
	exit /b 1
)

docker info > nul 2>&1
if !errorlevel! equ 0 (
	echo !C_OK!Docker ya esta arrancado.!C_RST!
	echo.
	exit /b 0
)

echo !C_WARN!Docker no esta listo.!C_RST!
tasklist /FI "IMAGENAME eq Docker Desktop.exe" | find /I "Docker Desktop.exe" > nul
if errorlevel 1 (
	echo !C_INFO!Arrancando Docker Desktop...!C_RST!
	if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
		start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
	) else (
		echo !C_ERR!No se encontro Docker Desktop en la ruta por defecto.!C_RST!
		echo !C_WARN!Ajusta la ruta en este script e intentalo de nuevo.!C_RST!
		exit /b 1
	)
) else (
	echo !C_INFO!Docker Desktop ya estaba abierto, esperando a que termine de iniciar...!C_RST!
)

set /a _INTENTOS=0
echo !C_INFO!Esperando a que Docker quede operativo...!C_RST!
:WAIT_DOCKER
ping -n 4 127.0.0.1 > nul
set /a _INTENTOS+=1
docker info > nul 2>&1
if !errorlevel! equ 0 (
	echo !C_OK!Docker listo.!C_RST!
	echo.
	exit /b 0
)
if !_INTENTOS! geq 45 (
	echo !C_ERR!Tiempo de espera agotado para Docker.!C_RST!
	exit /b 1
)
echo !C_WARN!Esperando... intento !_INTENTOS! de 45!C_RST!
goto WAIT_DOCKER

:CARGAR_CONTENEDORES
set /a TOTAL=0
for /L %%I in (1,1,300) do (
	set "CONT_%%I="
	set "EST_%%I="
	set "SAL_%%I=-"
	set "PRT_%%I=-"
)

for /f "tokens=1,2,* delims=|" %%A in ('docker ps -a --format "{{.Names}}|{{.Status}}|{{.Ports}}" 2^>nul') do (
	set /a TOTAL+=1
	set "CONT_!TOTAL!=%%A"
	set "_RAW_STATUS=%%B"
	set "EST_!TOTAL!=APAGADO"
	set "SAL_!TOTAL!=-"
	set "PRT_!TOTAL!=-"
	for /f "tokens=1" %%S in ("%%B") do (
		if /I "%%S"=="Up" (
			set "EST_!TOTAL!=ARRANCADO"
			set "SAL_!TOTAL!=SIN-CHECK"

			echo %%B | find /I "unhealthy" > nul
			if !errorlevel! equ 0 (
				set "SAL_!TOTAL!=UNHEALTHY"
			) else (
				echo %%B | find /I "healthy" > nul
				if !errorlevel! equ 0 set "SAL_!TOTAL!=HEALTHY"
			)

			echo %%B | find /I "starting" > nul
			if !errorlevel! equ 0 set "SAL_!TOTAL!=STARTING"

			set "_PORT=-"
			if not "%%C"=="" (
				for /f "tokens=1 delims=," %%P in ("%%C") do set "_PORT_ITEM=%%P"
				set "_PORT_ITEM=!_PORT_ITEM: =!"
				set "_LEFT_PART=!_PORT_ITEM!"
				for /f "tokens=1 delims=-" %%X in ("!_PORT_ITEM!") do set "_LEFT_PART=%%X"
				set "_LEFT_PART=!_LEFT_PART:[::]:=!"
				set "_PORT=!_LEFT_PART!"
				for /f "tokens=1,2 delims=:" %%X in ("!_LEFT_PART!") do (
					if not "%%Y"=="" set "_PORT=%%Y"
				)
				for /f "tokens=1 delims=/" %%Z in ("!_PORT!") do set "_PORT=%%Z"
			)
			set "PRT_!TOTAL!=!_PORT!"
		)
	)
)
exit /b 0

:MOSTRAR_MENU
cls
echo !C_TIT!==================================================!C_RST!
echo !C_TIT!  CONTENEDORES DISPONIBLES!C_RST!
echo !C_TIT!==================================================!C_RST!
echo.

if !TOTAL! equ 0 (
	echo !C_WARN!No hay contenedores creados.!C_RST!
) else (
	for /L %%I in (1,1,!TOTAL!) do (
		set "_NOMBRE=!CONT_%%I!"
		set "_ESTADO=!EST_%%I!"
		set "_SALUD=!SAL_%%I!"
		set "_PUERTO=!PRT_%%I!"
		if /I "!_ESTADO!"=="ARRANCADO" (
			echo %%I^) !C_OK![ON ]!C_RST! !_NOMBRE!  -  !_PUERTO!  -  Salud: !_SALUD!  -  !C_OK!ARRANCADO!C_RST!
		) else (
			echo %%I^) !C_ERR![OFF]!C_RST! !_NOMBRE!  -  !C_ERR!APAGADO!C_RST!
		)
	)
)

echo.
echo Opciones:
echo   !C_INFO!N!C_RST! - Arrancar contenedores por numero
echo   !C_INFO!P!C_RST! - Apagar contenedores por numero
echo   !C_INFO!T!C_RST! - Arrancar todos los contenedores apagados
echo   !C_INFO!A!C_RST! - Apagar todos los contenedores arrancados
echo   !C_INFO!F!C_RST! - Arrancar contenedores de un perfil
echo   !C_INFO!O!C_RST! - Apagar contenedores de un perfil
echo   !C_INFO!G!C_RST! - Gestionar perfiles
echo   !C_INFO!W!C_RST! - Gestor de networks
echo   !C_INFO!L!C_RST! - Ver logs de un contenedor
echo   !C_INFO!H!C_RST! - Ver historial de acciones
echo   !C_INFO!R!C_RST! - Refrescar listado
echo   !C_INFO!S!C_RST! - Salir
echo   !C_INFO!Tip!C_RST! - Tambien puedes escribir el nombre exacto de un perfil
echo.
set "_OPCION="
set /p "_OPCION=Selecciona una opcion: "

if /I "!_OPCION!"=="S" (
	set "SALIR=1"
	exit /b 0
)
if /I "!_OPCION!"=="R" exit /b 0
if /I "!_OPCION!"=="T" (
	call :ARRANCAR_TODOS_APAGADOS
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="A" (
	call :APAGAR_TODOS_ARRANCADOS
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="F" (
	call :ARRANCAR_PERFIL
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="O" (
	call :APAGAR_PERFIL
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="G" (
	call :GESTIONAR_PERFILES
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="W" (
	set "_W_VOLVER_INICIO=0"
	call :GESTOR_NETWORKS
	if "!_W_VOLVER_INICIO!"=="1" exit /b 0
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="L" (
	call :VER_LOGS_CONTENEDOR
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="H" (
	call :VER_HISTORIAL
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="N" (
	call :ARRANCAR_POR_NUMEROS
	call :PAUSA_CORTA
	exit /b 0
)
if /I "!_OPCION!"=="P" (
	call :APAGAR_POR_NUMEROS
	call :PAUSA_CORTA
	exit /b 0
)

call :ACCION_RAPIDA_PERFIL "!_OPCION!"
if !errorlevel! equ 0 (
	call :PAUSA_CORTA
	exit /b 0
)

echo !C_WARN!Opcion no valida.!C_RST!
call :PAUSA_CORTA
exit /b 0

:ARRANCAR_POR_NUMEROS
if !TOTAL! equ 0 (
	echo !C_WARN!No hay contenedores para arrancar.!C_RST!
	exit /b 0
)

echo.
echo Escribe numeros separados por espacio. Ejemplo: 1 3 5
set "_SELECCION="
set /p "_SELECCION=Numeros: "

if "!_SELECCION!"=="" (
	echo !C_WARN!No se introdujo ninguna seleccion.!C_RST!
	exit /b 0
)

call :VALIDAR_SELECCION_NUMEROS "!_SELECCION!"
if errorlevel 1 exit /b 0

for %%N in (!_LISTA_VALIDADA!) do (
	set "_NAME=!CONT_%%N!"
	if not defined _NAME (
		echo !C_WARN![WARN]!C_RST! Numero %%N no valido.
	) else (
		set "_EST=!EST_%%N!"
		if /I "!_EST!"=="ARRANCADO" (
			echo !C_OK![OK]!C_RST! !_NAME! ya estaba arrancado.
			call :REGISTRAR_EVENTO "ARRANCAR" "!_NAME!" "OK" "Ya estaba arrancado"
		) else (
			echo !C_INFO!Arrancando !_NAME!...!C_RST!
			docker start "!_NAME!" > nul 2>&1
			if !errorlevel! equ 0 (
				echo !C_OK![OK]!C_RST! !_NAME! arrancado.
				call :REGISTRAR_EVENTO "ARRANCAR" "!_NAME!" "OK" "Arranque manual por numero"
			) else (
				echo !C_ERR![ERROR]!C_RST! No se pudo arrancar !_NAME!.
				call :REGISTRAR_EVENTO "ARRANCAR" "!_NAME!" "ERROR" "Fallo al arrancar por numero"
			)
		)
	)
)
exit /b 0

:ARRANCAR_TODOS_APAGADOS
if !TOTAL! equ 0 (
	echo !C_WARN!No hay contenedores para arrancar.!C_RST!
	exit /b 0
)

set /a _APAGADOS=0
for /L %%I in (1,1,!TOTAL!) do (
	if /I "!EST_%%I!"=="APAGADO" (
		set /a _APAGADOS+=1
		set "_NAME=!CONT_%%I!"
		echo !C_INFO!Arrancando !_NAME!...!C_RST!
		docker start "!_NAME!" > nul 2>&1
		if !errorlevel! equ 0 (
			echo !C_OK![OK]!C_RST! !_NAME! arrancado.
			call :REGISTRAR_EVENTO "ARRANCAR" "!_NAME!" "OK" "Arranque masivo"
		) else (
			echo !C_ERR![ERROR]!C_RST! No se pudo arrancar !_NAME!.
			call :REGISTRAR_EVENTO "ARRANCAR" "!_NAME!" "ERROR" "Fallo en arranque masivo"
		)
	)
)

if !_APAGADOS! equ 0 echo !C_OK!Todos los contenedores ya estaban arrancados.!C_RST!
exit /b 0

:APAGAR_POR_NUMEROS
if !TOTAL! equ 0 (
	echo !C_WARN!No hay contenedores para apagar.!C_RST!
	exit /b 0
)

echo.
echo Escribe numeros separados por espacio. Ejemplo: 1 3 5
set "_SELECCION="
set /p "_SELECCION=Numeros: "

if "!_SELECCION!"=="" (
	echo !C_WARN!No se introdujo ninguna seleccion.!C_RST!
	exit /b 0
)

call :VALIDAR_SELECCION_NUMEROS "!_SELECCION!"
if errorlevel 1 exit /b 0

for %%N in (!_LISTA_VALIDADA!) do (
	set "_NAME=!CONT_%%N!"
	if not defined _NAME (
		echo !C_WARN![WARN]!C_RST! Numero %%N no valido.
	) else (
		set "_EST=!EST_%%N!"
		if /I "!_EST!"=="APAGADO" (
			echo !C_OK![OK]!C_RST! !_NAME! ya estaba apagado.
			call :REGISTRAR_EVENTO "APAGAR" "!_NAME!" "OK" "Ya estaba apagado"
		) else (
			echo !C_INFO!Apagando !_NAME!...!C_RST!
			docker stop "!_NAME!" > nul 2>&1
			if !errorlevel! equ 0 (
				echo !C_OK![OK]!C_RST! !_NAME! apagado.
				call :REGISTRAR_EVENTO "APAGAR" "!_NAME!" "OK" "Apagado manual por numero"
			) else (
				echo !C_ERR![ERROR]!C_RST! No se pudo apagar !_NAME!.
				call :REGISTRAR_EVENTO "APAGAR" "!_NAME!" "ERROR" "Fallo al apagar por numero"
			)
		)
	)
)
exit /b 0

:APAGAR_TODOS_ARRANCADOS
if !TOTAL! equ 0 (
	echo !C_WARN!No hay contenedores para apagar.!C_RST!
	exit /b 0
)

set /a _ARRANCADOS=0
for /L %%I in (1,1,!TOTAL!) do (
	if /I "!EST_%%I!"=="ARRANCADO" (
		set /a _ARRANCADOS+=1
		set "_NAME=!CONT_%%I!"
		echo !C_INFO!Apagando !_NAME!...!C_RST!
		docker stop "!_NAME!" > nul 2>&1
		if !errorlevel! equ 0 (
			echo !C_OK![OK]!C_RST! !_NAME! apagado.
			call :REGISTRAR_EVENTO "APAGAR" "!_NAME!" "OK" "Apagado masivo"
		) else (
			echo !C_ERR![ERROR]!C_RST! No se pudo apagar !_NAME!.
			call :REGISTRAR_EVENTO "APAGAR" "!_NAME!" "ERROR" "Fallo en apagado masivo"
		)
	)
)

if !_ARRANCADOS! equ 0 echo !C_OK!Todos los contenedores ya estaban apagados.!C_RST!
exit /b 0

:CARGAR_PERFILES
set /a TOTAL_PERFILES=0
for /L %%I in (1,1,120) do (
	set "PERF_N_%%I="
	set "PERF_C_%%I="
)

for /f "usebackq tokens=1,* delims==" %%A in ("%PERFILES_FILE%") do (
	set "_PN=%%A"
	set "_PC=%%B"
	if not "!_PN!"=="" (
		if /I not "!_PN:~0,1!"==";" (
			if /I not "!_PN:~0,1!"=="#" (
				set /a TOTAL_PERFILES+=1
				set "PERF_N_!TOTAL_PERFILES!=!_PN!"
				set "PERF_C_!TOTAL_PERFILES!=!_PC!"
			)
		)
	)
)
exit /b 0

:LISTAR_PERFILES
call :CARGAR_PERFILES
if !TOTAL_PERFILES! equ 0 (
	echo !C_WARN!No hay perfiles guardados.!C_RST!
	exit /b 1
)

echo !C_TIT!Perfiles guardados:!C_RST!
for /L %%I in (1,1,!TOTAL_PERFILES!) do (
	echo %%I^) !C_INFO!!PERF_N_%%I!!C_RST! = !PERF_C_%%I!
)
exit /b 0

:GESTIONAR_PERFILES
echo.
echo !C_TIT!Gestion de perfiles!C_RST!
echo   !C_INFO!1!C_RST! - Listar perfiles
echo   !C_INFO!2!C_RST! - Crear perfil desde numeros
echo   !C_INFO!3!C_RST! - Eliminar perfil
echo   !C_INFO!4!C_RST! - Editar perfil existente
set "_GP="
set /p "_GP=Selecciona una opcion: "

if "!_GP!"=="1" (
	call :LISTAR_PERFILES
	exit /b 0
)
if "!_GP!"=="2" (
	call :CREAR_PERFIL_DESDE_NUMEROS
	exit /b 0
)
if "!_GP!"=="3" (
	call :ELIMINAR_PERFIL
	exit /b 0
)
if "!_GP!"=="4" (
	call :EDITAR_PERFIL
	exit /b 0
)

echo !C_WARN!Opcion no valida.!C_RST!
exit /b 0

:CREAR_PERFIL_DESDE_NUMEROS
if !TOTAL! equ 0 (
	echo !C_WARN!No hay contenedores para crear un perfil.!C_RST!
	exit /b 0
)

echo.
echo Escribe nombre de perfil (sin espacios). Ejemplo: tienda
set "_NOMBRE_PERFIL="
set /p "_NOMBRE_PERFIL=Nombre: "
if "!_NOMBRE_PERFIL!"=="" (
	echo !C_WARN!Nombre no valido.!C_RST!
	exit /b 0
)

findstr /I /B /C:"!_NOMBRE_PERFIL!=" "%PERFILES_FILE%" > nul
if !errorlevel! equ 0 (
	echo !C_WARN!Ese perfil ya existe. Eliminalo y vuelvelo a crear si quieres cambiarlo.!C_RST!
	exit /b 0
)

echo.
echo Selecciona numeros separados por espacio. Ejemplo: 1 3
set "_SELECCION="
set /p "_SELECCION=Numeros: "

call :VALIDAR_SELECCION_NUMEROS "!_SELECCION!"
if errorlevel 1 exit /b 0

call :LISTA_CONTENEDORES_DESDE_INDICES "!_LISTA_VALIDADA!"
set "_LISTA_CONT=!_LISTA_CONT_BUILD!"

if "!_LISTA_CONT!"=="" (
	echo !C_WARN!No se seleccionaron contenedores validos.!C_RST!
	exit /b 0
)

>> "%PERFILES_FILE%" echo !_NOMBRE_PERFIL!=!_LISTA_CONT!
echo !C_OK![OK]!C_RST! Perfil !_NOMBRE_PERFIL! creado.
call :REGISTRAR_EVENTO "PERFIL" "!_NOMBRE_PERFIL!" "OK" "Perfil creado: !_LISTA_CONT!"
exit /b 0

:EDITAR_PERFIL
call :LISTAR_PERFILES
if errorlevel 1 exit /b 0

echo.
set "_IDX="
set /p "_IDX=Numero de perfil a editar: "
set "_NOMBRE=!PERF_N_%_IDX%!"
set "_ACTUAL=!PERF_C_%_IDX%!"
if "!_NOMBRE!"=="" (
	echo !C_WARN!Numero no valido.!C_RST!
	exit /b 0
)

echo !C_INFO!Perfil seleccionado: !_NOMBRE!!C_RST!
echo !C_INFO!Contenedores actuales: !_ACTUAL!!C_RST!
echo.
echo Introduce los nuevos numeros de contenedores (sin duplicados). Ejemplo: 1 2 4
set "_SELECCION="
set /p "_SELECCION=Numeros: "

if "!_SELECCION!"=="" (
	echo !C_WARN!No se introdujo ninguna seleccion.!C_RST!
	exit /b 0
)

call :VALIDAR_SELECCION_NUMEROS "!_SELECCION!"
if errorlevel 1 exit /b 0

call :LISTA_CONTENEDORES_DESDE_INDICES "!_LISTA_VALIDADA!"
set "_NUEVA_LISTA=!_LISTA_CONT_BUILD!"

if "!_NUEVA_LISTA!"=="" (
	echo !C_WARN!No se pudo generar la lista de contenedores.!C_RST!
	exit /b 0
)

call :ACTUALIZAR_LINEA_PERFIL "!_NOMBRE!" "!_NUEVA_LISTA!"
if errorlevel 1 (
	echo !C_ERR![ERROR]!C_RST! No se pudo editar el perfil !_NOMBRE!.
	call :REGISTRAR_EVENTO "PERFIL" "!_NOMBRE!" "ERROR" "Fallo al editar perfil"
	exit /b 0
)

echo !C_OK![OK]!C_RST! Perfil !_NOMBRE! actualizado: !_NUEVA_LISTA!
call :REGISTRAR_EVENTO "PERFIL" "!_NOMBRE!" "OK" "Perfil editado: !_NUEVA_LISTA!"
exit /b 0

:ELIMINAR_PERFIL
call :LISTAR_PERFILES
if errorlevel 1 exit /b 0

echo.
set "_IDX="
set /p "_IDX=Numero de perfil a eliminar: "
set "_NOMBRE=!PERF_N_%_IDX%!"
if "!_NOMBRE!"=="" (
	echo !C_WARN!Numero no valido.!C_RST!
	exit /b 0
)

findstr /V /I /B /C:"!_NOMBRE!=" "%PERFILES_FILE%" > "%PERFILES_FILE%.tmp"
move /Y "%PERFILES_FILE%.tmp" "%PERFILES_FILE%" > nul
echo !C_OK![OK]!C_RST! Perfil !_NOMBRE! eliminado.
call :REGISTRAR_EVENTO "PERFIL" "!_NOMBRE!" "OK" "Perfil eliminado"
exit /b 0

:ARRANCAR_PERFIL
call :EJECUTAR_PERFIL ARRANCAR
exit /b 0

:APAGAR_PERFIL
call :EJECUTAR_PERFIL APAGAR
exit /b 0

:EJECUTAR_PERFIL
set "_MODO=%~1"
call :LISTAR_PERFILES
if errorlevel 1 exit /b 0

echo.
set "_IDX="
set /p "_IDX=Numero de perfil: "
set "_NOMBRE=!PERF_N_%_IDX%!"
set "_LISTA=!PERF_C_%_IDX%!"

if "!_NOMBRE!"=="" (
	echo !C_WARN!Numero no valido.!C_RST!
	exit /b 0
)

if "!_LISTA!"=="" (
	echo !C_WARN!Perfil vacio.!C_RST!
	exit /b 0
)

call :EJECUTAR_LISTA_PERFIL "!_MODO!" "!_NOMBRE!" "!_LISTA!"
exit /b 0

:ACCION_RAPIDA_PERFIL
set "_NOMBRE_BUSCADO=%~1"
if "!_NOMBRE_BUSCADO!"=="" exit /b 1

call :CARGAR_PERFILES
if !TOTAL_PERFILES! equ 0 exit /b 1

set "_PERFIL_NOMBRE="
set "_PERFIL_LISTA="
for /L %%I in (1,1,!TOTAL_PERFILES!) do (
	if /I "!PERF_N_%%I!"=="!_NOMBRE_BUSCADO!" (
		set "_PERFIL_NOMBRE=!PERF_N_%%I!"
		set "_PERFIL_LISTA=!PERF_C_%%I!"
	)
)

if "!_PERFIL_NOMBRE!"=="" exit /b 1

echo.
echo !C_TIT!Perfil detectado: !_PERFIL_NOMBRE!!C_RST!
echo   !C_INFO!1!C_RST! - Arrancarlo
echo   !C_INFO!2!C_RST! - Pararlo
echo   !C_INFO!3!C_RST! - Cancelar
set "_ACCION_PERFIL="
set /p "_ACCION_PERFIL=Que deseas hacer: "

if "!_ACCION_PERFIL!"=="1" (
	call :EJECUTAR_LISTA_PERFIL "ARRANCAR" "!_PERFIL_NOMBRE!" "!_PERFIL_LISTA!"
	exit /b 0
)
if "!_ACCION_PERFIL!"=="2" (
	call :EJECUTAR_LISTA_PERFIL "APAGAR" "!_PERFIL_NOMBRE!" "!_PERFIL_LISTA!"
	exit /b 0
)

echo !C_WARN!Operacion cancelada.!C_RST!
exit /b 0

:EJECUTAR_LISTA_PERFIL
set "_MODO=%~1"
set "_NOMBRE=%~2"
set "_LISTA=%~3"

if "!_NOMBRE!"=="" (
	echo !C_WARN!Perfil no valido.!C_RST!
	exit /b 1
)
if "!_LISTA!"=="" (
	echo !C_WARN!Perfil vacio.!C_RST!
	exit /b 1
)

echo.
if /I "!_MODO!"=="ARRANCAR" (
	echo !C_INFO!Arrancando perfil !_NOMBRE!...!C_RST!
) else (
	echo !C_INFO!Apagando perfil !_NOMBRE!...!C_RST!
)

set "_LISTA_ESP=!_LISTA:,= !"
for %%C in (!_LISTA_ESP!) do (
	if /I "!_MODO!"=="ARRANCAR" (
		docker start "%%C" > nul 2>&1
		if !errorlevel! equ 0 (
			echo !C_OK![OK]!C_RST! %%C arrancado.
			call :REGISTRAR_EVENTO "ARRANCAR" "%%C" "OK" "Arranque por perfil !_NOMBRE!"
		) else (
			echo !C_ERR![ERROR]!C_RST! No se pudo arrancar %%C.
			call :REGISTRAR_EVENTO "ARRANCAR" "%%C" "ERROR" "Fallo por perfil !_NOMBRE!"
		)
	) else (
		docker stop "%%C" > nul 2>&1
		if !errorlevel! equ 0 (
			echo !C_OK![OK]!C_RST! %%C apagado.
			call :REGISTRAR_EVENTO "APAGAR" "%%C" "OK" "Apagado por perfil !_NOMBRE!"
		) else (
			echo !C_ERR![ERROR]!C_RST! No se pudo apagar %%C.
			call :REGISTRAR_EVENTO "APAGAR" "%%C" "ERROR" "Fallo por perfil !_NOMBRE!"
		)
	)
)

call :REGISTRAR_EVENTO "PERFIL" "!_NOMBRE!" "OK" "Ejecutado en modo !_MODO!"
exit /b 0

:VALIDAR_SELECCION_NUMEROS
set "_SEL=%~1"
set "_LISTA_VALIDADA="
set "_HAY_VALIDOS=0"

for %%N in (%_SEL%) do (
	set "_ITEM=%%N"
	echo(!_ITEM!| findstr /R "^[0-9][0-9]*$" > nul
	if !errorlevel! neq 0 (
		echo !C_WARN![WARN]!C_RST! "%%N" no es un numero valido.
	) else (
		if %%N lss 1 (
			echo !C_WARN![WARN]!C_RST! Numero %%N fuera de rango.
		) else if %%N gtr !TOTAL! (
			echo !C_WARN![WARN]!C_RST! Numero %%N fuera de rango.
		) else (
			set "_REPETIDO=0"
			for %%U in (!_LISTA_VALIDADA!) do (
				if "%%U"=="%%N" set "_REPETIDO=1"
			)
			if "!_REPETIDO!"=="1" (
				echo !C_WARN![WARN]!C_RST! Numero %%N repetido; se ignora.
			) else (
				set "_LISTA_VALIDADA=!_LISTA_VALIDADA! %%N"
				set "_HAY_VALIDOS=1"
			)
		)
	)
)

if "!_HAY_VALIDOS!"=="0" (
	echo !C_WARN!No hay numeros validos para procesar.!C_RST!
	exit /b 1
)
exit /b 0

:LISTA_CONTENEDORES_DESDE_INDICES
set "_INDICES=%~1"
set "_LISTA_CONT_BUILD="
for %%N in (%_INDICES%) do (
	set "_NAME=!CONT_%%N!"
	if defined _NAME (
		if defined _LISTA_CONT_BUILD (
			set "_LISTA_CONT_BUILD=!_LISTA_CONT_BUILD!,!_NAME!"
		) else (
			set "_LISTA_CONT_BUILD=!_NAME!"
		)
	)
)
exit /b 0

:ACTUALIZAR_LINEA_PERFIL
set "_TARGET=%~1"
set "_NUEVO=%~2"
set "_ENCONTRADO=0"

> "%PERFILES_FILE%.tmp" (
	for /f "usebackq delims=" %%L in ("%PERFILES_FILE%") do (
		set "_LINEA=%%L"
		for /f "tokens=1,* delims==" %%A in ("%%L") do (
			set "_K=%%A"
			if /I "!_K!"=="!_TARGET!" (
				echo !_TARGET!=!_NUEVO!
				set "_ENCONTRADO=1"
			) else (
				echo %%L
			)
		)
	)
)

if "!_ENCONTRADO!"=="0" (
	del "%PERFILES_FILE%.tmp" > nul 2>&1
	exit /b 1
)

move /Y "%PERFILES_FILE%.tmp" "%PERFILES_FILE%" > nul
exit /b 0

:CARGAR_NETWORKS
set /a TOTAL_NETS=0
for /L %%I in (1,1,200) do (
	set "NET_N_%%I="
	set "NET_D_%%I="
)

for /f "tokens=1,2 delims=|" %%A in ('docker network ls --format "{{.Name}}|{{.Driver}}" 2^>nul') do (
	if /I not "%%A"=="bridge" if /I not "%%A"=="host" if /I not "%%A"=="none" (
		set /a TOTAL_NETS+=1
		set "NET_N_!TOTAL_NETS!=%%A"
		set "NET_D_!TOTAL_NETS!=%%B"
	)
)
exit /b 0

:LISTAR_NETWORKS
call :CARGAR_NETWORKS
if !TOTAL_NETS! equ 0 (
	echo !C_WARN!No hay networks creadas por el usuario.!C_RST!
	exit /b 1
)

echo !C_TIT!Networks disponibles (excluye bridge/host/none):!C_RST!
echo !C_OK!Verde=ARRANCADO!C_RST!  !C_ERR!Rojo=APAGADO!C_RST!
for /L %%I in (1,1,!TOTAL_NETS!) do (
	set "_NET_NAME=!NET_N_%%I!"
	set "_NET_CONTS="
	set "_NET_COUNT=0"
	for /L %%J in (1,1,!TOTAL!) do (
		set "_CN=!CONT_%%J!"
		if defined _CN (
			set "_NETS_CONT="
			for /f "tokens=*" %%X in ('docker inspect --format "{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}" "!_CN!" 2^>nul') do set "_NETS_CONT=%%X"
			set "_ESTA_EN_NET=0"
			for %%R in (!_NETS_CONT!) do (
				if /I "%%R"=="!_NET_NAME!" set "_ESTA_EN_NET=1"
			)
			if "!_ESTA_EN_NET!"=="1" (
				set /a _NET_COUNT+=1
				set "_CN_SHOW=!_CN!"
				if /I "!EST_%%J!"=="ARRANCADO" (
					set "_CN_SHOW=!C_OK!!_CN!!C_RST!"
				) else (
					set "_CN_SHOW=!C_ERR!!_CN!!C_RST!"
				)
				if defined _NET_CONTS (
					set "_NET_CONTS=!_NET_CONTS!, !_CN_SHOW!"
				) else (
					set "_NET_CONTS=!_CN_SHOW!"
				)
			)
		)
	)

	if "!_NET_CONTS!"=="" set "_NET_CONTS=ninguno"
	echo %%I^) !C_INFO!!NET_N_%%I!!C_RST!  -  driver: !NET_D_%%I!  -  contenedores: !_NET_COUNT!  -  nombres: !_NET_CONTS!
)
exit /b 0

:GESTOR_NETWORKS
echo.
echo !C_TIT!Gestor de networks!C_RST!
echo   !C_INFO!1!C_RST! - Listar networks
echo   !C_INFO!2!C_RST! - Anadir contenedor a una network
echo   !C_INFO!3!C_RST! - Quitar contenedor de una network
echo   !C_INFO!4!C_RST! - Renombrar network
echo   !C_INFO!5!C_RST! - Crear network
echo   !C_INFO!6!C_RST! - Eliminar network
echo   !C_INFO!0!C_RST! - Volver al inicio
set "_GN="
set /p "_GN=Selecciona una opcion: "

if "!_GN!"=="0" (
	set "_W_VOLVER_INICIO=1"
	exit /b 0
)

if "!_GN!"=="1" (
	call :LISTAR_NETWORKS
	call :PAUSA_CORTA
	goto GESTOR_NETWORKS
)
if "!_GN!"=="2" (
	call :AGREGAR_CONTENEDOR_A_NETWORKS
	exit /b 0
)
if "!_GN!"=="3" (
	call :QUITAR_CONTENEDOR_DE_NETWORK
	exit /b 0
)
if "!_GN!"=="4" (
	call :RENOMBRAR_NETWORK
	exit /b 0
)
if "!_GN!"=="5" (
	call :CREAR_NETWORK
	exit /b 0
)
if "!_GN!"=="6" (
	call :ELIMINAR_NETWORK
	exit /b 0
)

echo !C_WARN!Opcion no valida.!C_RST!
exit /b 0

:VALIDAR_SELECCION_NETWORKS
set "_SEL_NET=%~1"
set "_LISTA_NET_VALIDADA="
set "_HAY_NET_VALIDAS=0"

for %%N in (%_SEL_NET%) do (
	set "_ITEM=%%N"
	echo(!_ITEM!| findstr /R "^[0-9][0-9]*$" > nul
	if !errorlevel! neq 0 (
		echo !C_WARN![WARN]!C_RST! "%%N" no es un numero valido.
	) else (
		if %%N lss 1 (
			echo !C_WARN![WARN]!C_RST! Numero %%N fuera de rango.
		) else if %%N gtr !TOTAL_NETS! (
			echo !C_WARN![WARN]!C_RST! Numero %%N fuera de rango.
		) else (
			set "_REPETIDO=0"
			for %%U in (!_LISTA_NET_VALIDADA!) do (
				if "%%U"=="%%N" set "_REPETIDO=1"
			)
			if "!_REPETIDO!"=="1" (
				echo !C_WARN![WARN]!C_RST! Numero %%N repetido; se ignora.
			) else (
				set "_LISTA_NET_VALIDADA=!_LISTA_NET_VALIDADA! %%N"
				set "_HAY_NET_VALIDAS=1"
			)
		)
	)
)

if "!_HAY_NET_VALIDAS!"=="0" (
	echo !C_WARN!No hay networks validas para procesar.!C_RST!
	exit /b 1
)
exit /b 0

:AGREGAR_CONTENEDOR_A_NETWORKS
call :CARGAR_NETWORKS
if !TOTAL_NETS! equ 0 (
	echo !C_WARN!No hay networks creadas por el usuario para conectar.!C_RST!
	exit /b 0
)

if !TOTAL! equ 0 (
	echo !C_WARN!No hay contenedores disponibles.!C_RST!
	exit /b 0
)

echo.
call :LISTAR_NETWORKS

echo.
set "_IDX_NET="
set /p "_IDX_NET=Numero de network: "
if "!_IDX_NET!"=="" (
	echo !C_WARN!No se introdujo ninguna network.!C_RST!
	exit /b 0
)

call :VALIDAR_SELECCION_NETWORKS "!_IDX_NET!"
if errorlevel 1 exit /b 0
for /f "tokens=1" %%I in ("!_LISTA_NET_VALIDADA!") do set "_IDX_NET=%%I"

set "_NET_NAME=!NET_N_%_IDX_NET%!"
if "!_NET_NAME!"=="" (
	echo !C_WARN!Network no valida.!C_RST!
	exit /b 0
)

set /a TOTAL_DISP=0
for /L %%I in (1,1,300) do (
	set "DISP_N_%%I="
	set "DISP_C_%%I="
	set "DISP_E_%%I="
)

for /L %%I in (1,1,!TOTAL!) do (
	set "_CN=!CONT_%%I!"
	if defined _CN (
		set "_NETS_CONT="
		for /f "tokens=*" %%X in ('docker inspect --format "{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}" "!_CN!" 2^>nul') do set "_NETS_CONT=%%X"
		set "_ESTA_EN_NET=0"
		for %%R in (!_NETS_CONT!) do (
			if /I "%%R"=="!_NET_NAME!" set "_ESTA_EN_NET=1"
		)
		if "!_ESTA_EN_NET!"=="0" (
			set /a TOTAL_DISP+=1
			set "DISP_N_!TOTAL_DISP!=%%I"
			set "DISP_C_!TOTAL_DISP!=!_CN!"
			set "DISP_E_!TOTAL_DISP!=!EST_%%I!"
		)
	)
)

if !TOTAL_DISP! equ 0 (
	echo !C_WARN!No hay contenedores disponibles para agregar a !_NET_NAME!.!C_RST!
	exit /b 0
)

echo.
echo !C_TIT!Contenedores disponibles para !_NET_NAME!!C_RST!
for /L %%I in (1,1,!TOTAL_DISP!) do (
	set "_CN=!DISP_C_%%I!"
	set "_EST=!DISP_E_%%I!"
	if /I "!_EST!"=="ARRANCADO" (
		echo %%I^) !C_OK!!_CN!!C_RST!  -  !C_OK!ARRANCADO!C_RST!
	) else (
		echo %%I^) !C_ERR!!_CN!!C_RST!  -  !C_ERR!APAGADO!C_RST!
	)
)

echo.
set "_SEL_CONT="
set /p "_SEL_CONT=Numeros de contenedores a agregar (ejemplo: 1 3): "
if "!_SEL_CONT!"=="" (
	echo !C_WARN!No se introdujo ninguna seleccion.!C_RST!
	exit /b 0
)

call :VALIDAR_SELECCION_RANGO "!_SEL_CONT!" "!TOTAL_DISP!"
if errorlevel 1 exit /b 0

echo.
for %%I in (!_LISTA_R_VALIDADA!) do (
	set "_CONT_NAME=!DISP_C_%%I!"
	if not defined _CONT_NAME (
		echo !C_WARN![WARN]!C_RST! Contenedor no valido en indice %%I.
	) else (
		docker network connect "!_NET_NAME!" "!_CONT_NAME!" > nul 2>&1
		if !errorlevel! equ 0 (
			echo !C_OK![OK]!C_RST! !_CONT_NAME! conectado a !_NET_NAME!.
			call :REGISTRAR_EVENTO "NETWORK" "!_CONT_NAME!" "OK" "Conectado a !_NET_NAME!"
		) else (
			echo !C_ERR![ERROR]!C_RST! No se pudo conectar !_CONT_NAME! a !_NET_NAME!.
			call :REGISTRAR_EVENTO "NETWORK" "!_CONT_NAME!" "ERROR" "Fallo al conectar a !_NET_NAME!"
		)
	)
)
exit /b 0

:CARGAR_CONTENEDORES_EN_NETWORK
set "_NET_OBJ=%~1"
set /a TOTAL_CONN=0
for /L %%I in (1,1,300) do set "CONN_%%I="

for /L %%I in (1,1,!TOTAL!) do (
	set "_CN=!CONT_%%I!"
	if defined _CN (
		set "_NETS_CONT="
		for /f "tokens=*" %%X in ('docker inspect --format "{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}" "!_CN!" 2^>nul') do set "_NETS_CONT=%%X"
		set "_ESTA_EN_NET=0"
		for %%R in (!_NETS_CONT!) do (
			if /I "%%R"=="!_NET_OBJ!" set "_ESTA_EN_NET=1"
		)
		if "!_ESTA_EN_NET!"=="1" (
		set /a TOTAL_CONN+=1
		set "CONN_!TOTAL_CONN!=!_CN!"
		)
	)
)
exit /b 0

:VALIDAR_SELECCION_RANGO
set "_SEL_R=%~1"
set "_MAX_R=%~2"
set "_LISTA_R_VALIDADA="
set "_HAY_R_VALIDOS=0"

for %%N in (%_SEL_R%) do (
	set "_ITEM=%%N"
	echo(!_ITEM!| findstr /R "^[0-9][0-9]*$" > nul
	if !errorlevel! neq 0 (
		echo !C_WARN![WARN]!C_RST! "%%N" no es un numero valido.
	) else (
		if %%N lss 1 (
			echo !C_WARN![WARN]!C_RST! Numero %%N fuera de rango.
		) else if %%N gtr !_MAX_R! (
			echo !C_WARN![WARN]!C_RST! Numero %%N fuera de rango.
		) else (
			set "_REPETIDO=0"
			for %%U in (!_LISTA_R_VALIDADA!) do (
				if "%%U"=="%%N" set "_REPETIDO=1"
			)
			if "!_REPETIDO!"=="1" (
				echo !C_WARN![WARN]!C_RST! Numero %%N repetido; se ignora.
			) else (
				set "_LISTA_R_VALIDADA=!_LISTA_R_VALIDADA! %%N"
				set "_HAY_R_VALIDOS=1"
			)
		)
	)
)

if "!_HAY_R_VALIDOS!"=="0" (
	echo !C_WARN!No hay numeros validos para procesar.!C_RST!
	exit /b 1
)
exit /b 0

:QUITAR_CONTENEDOR_DE_NETWORK
call :LISTAR_NETWORKS
if errorlevel 1 exit /b 0

echo.
set "_IDX_NET="
set /p "_IDX_NET=Numero de network: "
call :VALIDAR_SELECCION_NETWORKS "!_IDX_NET!"
if errorlevel 1 exit /b 0
for /f "tokens=1" %%I in ("!_LISTA_NET_VALIDADA!") do set "_IDX_NET=%%I"

set "_NET_NAME=!NET_N_%_IDX_NET%!"
if "!_NET_NAME!"=="" (
	echo !C_WARN!Network no valida.!C_RST!
	exit /b 0
)

call :CARGAR_CONTENEDORES_EN_NETWORK "!_NET_NAME!"
if !TOTAL_CONN! equ 0 (
	echo !C_WARN!La network !_NET_NAME! no tiene contenedores conectados del listado actual.!C_RST!
	exit /b 0
)

echo.
echo !C_TIT!Contenedores conectados a !_NET_NAME!!C_RST!
for /L %%I in (1,1,!TOTAL_CONN!) do echo %%I^) !C_INFO!!CONN_%%I!!C_RST!

echo.
echo Escribe numeros de contenedores a quitar. Ejemplo: 1 2
set "_SEL_Q="
set /p "_SEL_Q=Seleccion: "
if "!_SEL_Q!"=="" (
	echo !C_WARN!No se introdujo ninguna seleccion.!C_RST!
	exit /b 0
)

call :VALIDAR_SELECCION_RANGO "!_SEL_Q!" "!TOTAL_CONN!"
if errorlevel 1 exit /b 0

echo.
for %%I in (!_LISTA_R_VALIDADA!) do (
	set "_CN=!CONN_%%I!"
	docker network disconnect "!_NET_NAME!" "!_CN!" > nul 2>&1
	if !errorlevel! equ 0 (
		echo !C_OK![OK]!C_RST! !_CN! desconectado de !_NET_NAME!.
		call :REGISTRAR_EVENTO "NETWORK" "!_CN!" "OK" "Desconectado de !_NET_NAME!"
	) else (
		echo !C_ERR![ERROR]!C_RST! No se pudo desconectar !_CN! de !_NET_NAME!.
		call :REGISTRAR_EVENTO "NETWORK" "!_CN!" "ERROR" "Fallo al desconectar de !_NET_NAME!"
	)
)
exit /b 0

:RENOMBRAR_NETWORK
call :LISTAR_NETWORKS
if errorlevel 1 exit /b 0

echo.
set "_IDX_NET="
set /p "_IDX_NET=Numero de network a renombrar: "
call :VALIDAR_SELECCION_NETWORKS "!_IDX_NET!"
if errorlevel 1 exit /b 0
for /f "tokens=1" %%I in ("!_LISTA_NET_VALIDADA!") do set "_IDX_NET=%%I"

set "_OLD_NET=!NET_N_%_IDX_NET%!"
set "_DRIVER=!NET_D_%_IDX_NET%!"
if "!_OLD_NET!"=="" (
	echo !C_WARN!Network no valida.!C_RST!
	exit /b 0
)

echo.
echo Nombre actual: !C_INFO!!_OLD_NET!!C_RST! (driver !_DRIVER!)
set "_NEW_NET="
set /p "_NEW_NET=Nuevo nombre: "
if "!_NEW_NET!"=="" (
	echo !C_WARN!Nombre no valido.!C_RST!
	exit /b 0
)

docker network inspect "!_NEW_NET!" > nul 2>&1
if !errorlevel! equ 0 (
	echo !C_WARN!Ya existe una network con ese nombre.!C_RST!
	exit /b 0
)

echo !C_INFO!Renombrado tecnico: se crea la nueva network, se migran contenedores y se elimina la anterior.!C_RST!
docker network create --driver "!_DRIVER!" "!_NEW_NET!" > nul 2>&1
if !errorlevel! neq 0 (
	echo !C_ERR![ERROR]!C_RST! No se pudo crear la network !_NEW_NET!.
	call :REGISTRAR_EVENTO "NETWORK" "!_OLD_NET!" "ERROR" "Fallo al crear !_NEW_NET! durante renombrado"
	exit /b 0
)

call :CARGAR_CONTENEDORES_EN_NETWORK "!_OLD_NET!"
for /L %%I in (1,1,!TOTAL_CONN!) do (
	set "_CN=!CONN_%%I!"
	docker network connect "!_NEW_NET!" "!_CN!" > nul 2>&1
	if !errorlevel! equ 0 (
		docker network disconnect "!_OLD_NET!" "!_CN!" > nul 2>&1
	)
)

docker network rm "!_OLD_NET!" > nul 2>&1
if !errorlevel! equ 0 (
	echo !C_OK![OK]!C_RST! Network renombrada de !_OLD_NET! a !_NEW_NET!.
	call :REGISTRAR_EVENTO "NETWORK" "!_OLD_NET!" "OK" "Renombrada a !_NEW_NET!"
) else (
	echo !C_WARN![WARN]!C_RST! Se creo !_NEW_NET!, pero no se pudo eliminar !_OLD_NET!.
	call :REGISTRAR_EVENTO "NETWORK" "!_OLD_NET!" "ERROR" "No se pudo eliminar tras migrar a !_NEW_NET!"
)
exit /b 0

:CREAR_NETWORK
echo.
set "_NEW_NET="
set /p "_NEW_NET=Nombre de la nueva network: "
if "!_NEW_NET!"=="" (
	echo !C_WARN!Nombre no valido.!C_RST!
	exit /b 0
)

set "_DRIVER=bridge"
set /p "_DRIVER=Driver (default bridge): "
if "!_DRIVER!"=="" set "_DRIVER=bridge"

docker network create --driver "!_DRIVER!" "!_NEW_NET!" > nul 2>&1
if !errorlevel! equ 0 (
	echo !C_OK![OK]!C_RST! Network !_NEW_NET! creada con driver !_DRIVER!.
	call :REGISTRAR_EVENTO "NETWORK" "!_NEW_NET!" "OK" "Creada con driver !_DRIVER!"
) else (
	echo !C_ERR![ERROR]!C_RST! No se pudo crear la network !_NEW_NET!.
	call :REGISTRAR_EVENTO "NETWORK" "!_NEW_NET!" "ERROR" "Fallo al crear con driver !_DRIVER!"
)
exit /b 0

:ELIMINAR_NETWORK
call :LISTAR_NETWORKS
if errorlevel 1 exit /b 0

echo.
set "_IDX_NET="
set /p "_IDX_NET=Numero de network a eliminar: "
call :VALIDAR_SELECCION_NETWORKS "!_IDX_NET!"
if errorlevel 1 exit /b 0
for /f "tokens=1" %%I in ("!_LISTA_NET_VALIDADA!") do set "_IDX_NET=%%I"

set "_NET_NAME=!NET_N_%_IDX_NET%!"
if "!_NET_NAME!"=="" (
	echo !C_WARN!Network no valida.!C_RST!
	exit /b 0
)

set "_CONF="
set /p "_CONF=Confirma eliminar !_NET_NAME! (S/N): "
if /I not "!_CONF!"=="S" (
	echo !C_WARN!Operacion cancelada.!C_RST!
	exit /b 0
)

docker network rm "!_NET_NAME!" > nul 2>&1
if !errorlevel! equ 0 (
	echo !C_OK![OK]!C_RST! Network !_NET_NAME! eliminada.
	call :REGISTRAR_EVENTO "NETWORK" "!_NET_NAME!" "OK" "Network eliminada"
) else (
	echo !C_ERR![ERROR]!C_RST! No se pudo eliminar !_NET_NAME!. Revisa si tiene contenedores conectados.
	call :REGISTRAR_EVENTO "NETWORK" "!_NET_NAME!" "ERROR" "Fallo al eliminar network"
)
exit /b 0

:VER_LOGS_CONTENEDOR
if !TOTAL! equ 0 (
	echo !C_WARN!No hay contenedores.!C_RST!
	exit /b 0
)

echo.
echo !C_TIT!Contenedores disponibles para ver logs:!C_RST!
for /L %%I in (1,1,!TOTAL!) do (
	set "_NOMBRE=!CONT_%%I!"
	set "_ESTADO=!EST_%%I!"
	if /I "!_ESTADO!"=="ARRANCADO" (
		echo %%I^) !C_OK!!_NOMBRE!!C_RST!  -  !C_OK!ARRANCADO!C_RST!
	) else (
		echo %%I^) !C_ERR!!_NOMBRE!!C_RST!  -  !C_ERR!APAGADO!C_RST!
	)
)
echo.
set "_IDX="
set /p "_IDX=Numero de contenedor para logs: "
set "_NAME=!CONT_%_IDX%!"
if "!_NAME!"=="" (
	echo !C_WARN!Numero no valido.!C_RST!
	exit /b 0
)

set "_TAIL=100"
set /p "_TAIL=Cuantas lineas mostrar (default 100): "
if "!_TAIL!"=="" set "_TAIL=100"

set "_MODO=L"
set /p "_MODO=Modo [L=ultimas lineas / F=seguir]: "

if /I "!_MODO!"=="F" (
	echo !C_INFO!Mostrando logs en vivo de !_NAME!. Pulsa Ctrl+C para salir.!C_RST!
	call :REGISTRAR_EVENTO "LOGS" "!_NAME!" "OK" "Modo seguimiento"
	docker logs -f --tail !_TAIL! "!_NAME!"
	exit /b 0
)

echo !C_INFO!Mostrando ultimas !_TAIL! lineas de !_NAME!...!C_RST!
call :REGISTRAR_EVENTO "LOGS" "!_NAME!" "OK" "Ultimas !_TAIL! lineas"
docker logs --tail !_TAIL! "!_NAME!"
exit /b 0

:VER_HISTORIAL
echo.
echo !C_TIT!Ultimas acciones registradas!C_RST!
powershell -NoProfile -Command "if (Test-Path '%LOG_FILE%') { Get-Content -Path '%LOG_FILE%' -Tail 60 }"
exit /b 0

:REGISTRAR_EVENTO
set "_L_ACCION=%~1"
set "_L_OBJETO=%~2"
set "_L_RESULTADO=%~3"
set "_L_DETALLE=%~4"
>> "%LOG_FILE%" echo [!date! !time:~0,8!] ACCION=!_L_ACCION! ^| OBJETO=!_L_OBJETO! ^| RESULTADO=!_L_RESULTADO! ^| !_L_DETALLE!
exit /b 0

:PAUSA_CORTA
echo.
echo Pulsa una tecla para volver al listado...
pause > nul
exit /b 0

:FIN
echo.
echo !C_INFO!Cerrando gestor...!C_RST!
endlocal
exit /b 0

:FIN_ERROR
echo.
echo !C_ERR!No se pudo inicializar Docker.!C_RST!
echo !C_WARN!Pulsa una tecla para salir.!C_RST!
pause > nul
endlocal
exit /b 1