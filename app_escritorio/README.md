# App de Escritorio - Utilidades WordPress + Docker

Esta app de escritorio para Windows centraliza las utilidades existentes en BAT y agrega un panel de estado Docker.

## Requisitos

- Windows
- Docker Desktop instalado
- Python 3.10+ (si se ejecuta como script)

## Configurar equipo remoto (Docker 2375/2376 + IPv6)

Esta app puede trabajar en modo remoto. Si el daemon Docker esta en otro equipo, debes exponer el API remoto y abrir firewall.

### 1) Configurar Docker daemon remoto

#### Opcion A - Linux (Docker Engine)

Editar `/etc/docker/daemon.json` en el equipo remoto:

```json
{
  "hosts": [
    "unix:///var/run/docker.sock",
    "tcp://0.0.0.0:2375",
    "tcp://[::]:2375",
    "tcp://0.0.0.0:2376",
    "tcp://[::]:2376"
  ]
}
```

Reiniciar Docker:

```bash
sudo systemctl restart docker
sudo systemctl status docker
```

#### Opcion B - Windows con Docker Desktop

- Activar en Docker Desktop: `Expose daemon on tcp://localhost:2375 without TLS`.
- Para exponer a red LAN/IPv6, crear `portproxy` (Windows no publica 2375 LAN por defecto solo con ese checkbox).

IPv4:

```powershell
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=2375 connectaddress=127.0.0.1 connectport=2375
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=2376 connectaddress=127.0.0.1 connectport=2375
```

IPv6:

```powershell
netsh interface portproxy add v6tov4 listenaddress=:: listenport=2375 connectaddress=127.0.0.1 connectport=2375
netsh interface portproxy add v6tov4 listenaddress=:: listenport=2376 connectaddress=127.0.0.1 connectport=2375
```

### 2) Abrir firewall en equipo remoto

Linux (UFW):

```bash
sudo ufw allow 2375/tcp
sudo ufw allow 2376/tcp
sudo ufw status
```

Windows (PowerShell Admin):

```powershell
New-NetFirewallRule -DisplayName "Docker API 2375" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 2375
New-NetFirewallRule -DisplayName "Docker API 2376" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 2376
```

### 3) Verificar que escucha en remoto

Linux:

```bash
ss -lntp | grep -E ':2375|:2376'
```

Windows:

```powershell
netstat -ano | findstr :2375
netstat -ano | findstr :2376
```

### 4) Probar desde el equipo cliente

IPv4:

```powershell
Test-NetConnection 192.168.X.X -Port 2375
Test-NetConnection 192.168.X.X -Port 2376
```

IPv6:

```powershell
Test-NetConnection -ComputerName "2001:db8::10" -Port 2375
Test-NetConnection -ComputerName "2001:db8::10" -Port 2376
```

### 5) Formato de host remoto en la app

- IPv4: `tcp://192.168.X.X:2375`
- IPv4 con 2376: `tcp://192.168.X.X:2376`
- IPv6: `tcp://[2001:db8::10]:2375`
- IPv6 con 2376: `tcp://[2001:db8::10]:2376`
- SSH: `ssh://usuario@host`

### Seguridad importante

- `2375` sin TLS es inseguro. Usar solo en red de confianza y para pruebas.
- `2376` esta pensado para TLS. Si habilitas 2376 real, configura certificados del daemon/cliente.
- En produccion, preferir `ssh://usuario@host` o `2376` con TLS.

## Configurar perfiles remotos (volumen Docker compartido)

La app soporta dos almacenes de perfiles en la pestaña `Perfiles`:

- `privado`: por usuario local, guardado en `%LOCALAPPDATA%\WordPressUtilidades\private_profiles.json`
- `remoto`: compartido entre clientes conectados al mismo daemon remoto, guardado en volumen Docker `wpu_profiles_remote` dentro de `/data/profiles.json`

### Requisitos para perfiles remotos

- Estar en modo remoto dentro de la app.
- Que el host remoto Docker sea accesible (2375/2376 o SSH).
- Tener disponible la imagen `alpine` en el daemon remoto (la app la usa para leer/escribir el JSON en el volumen).

### 1) Crear volumen remoto

Ejecutar en el equipo cliente (apuntando al daemon remoto configurado en la app):

```powershell
docker volume create wpu_profiles_remote
```

### 2) Inicializar `profiles.json` en el volumen (PowerShell)

Este flujo evita problemas de comillas en PowerShell:

```powershell
$json = '{"version":1,"updated_at":"","updated_by":"","profiles":{}}'
$tmp = Join-Path $env:TEMP 'profiles.json'
Set-Content -Path $tmp -Value $json -Encoding UTF8
Get-Content $tmp -Raw | docker run --rm -i -v wpu_profiles_remote:/data alpine sh -c "cat > /data/profiles.json"
```

### 3) Verificar contenido del volumen

```powershell
docker run --rm -v wpu_profiles_remote:/data alpine cat /data/profiles.json
```

Resultado esperado:

```json
{"version":1,"updated_at":"","updated_by":"","profiles":{}}
```

Validacion opcional de JSON en PowerShell:

```powershell
docker run --rm -v wpu_profiles_remote:/data alpine cat /data/profiles.json | ConvertFrom-Json
```

### 4) Uso desde la app

1. Ir a pestaña `Perfiles`.
2. En `Almacen`, seleccionar `remoto`.
3. Crear/editar/eliminar perfiles normalmente.
4. Para compartir perfiles entre almacenes, usar `Copiar a remoto` o `Copiar a privado` segun el almacén activo.

### 5) Solucion de problemas

- Si no conecta en remoto: revisar la seccion de puertos 2375/2376 de este README.
- Si falla lectura/escritura de perfiles remotos: verificar que `alpine` exista en el daemon remoto (`docker image ls alpine`).
- Si el volumen no aparece: comprobar con `docker volume ls` y recrearlo si hace falta.
- Si el JSON esta corrupto: reinicializar con el paso 2.

## Ejecutar

Desde `utilidades`:

```bat
ejecutar-app.bat
```

Si Python no esta instalado, el lanzador ofrece:

- instalar Python automaticamente con `winget`
- abrir la configuracion de alias de ejecucion de aplicaciones

O directamente desde `app_escritorio`:

```bat
python wordpress_utilidades_app.py
```

## Empaquetar a EXE (opcional)

Desde `app_escritorio`:

```bat
pip install pyinstaller
pyinstaller --noconfirm wordpress_utilidades_app.spec
```

El ejecutable quedara en:

```text
utilidades\app_escritorio\dist\wordpress_utilidades_app.exe
```

Archivos de estado locales de la app:

```text
utilidades\app_escritorio\perfiles_contenedores.ini
```

Historial de auditoria compartido (remoto):

```text
Volumen Docker: wpu_history_remote
Ruta en volumen: /data/historial_gestor.log
```

## Funciones actuales

- Lanzadores de utilidades existentes:
  - `docker_mariadb_wordpress.bat`
  - `importar-wordpress.bat`
  - `exportar-wordpress-v3.bat`
  - `gestor_contenedores.bat`
  - `docker-wordpress-docs.html`
- Pestaña `Contenedores`:
  - estado de Docker
  - listado de contenedores (estado, salud, puerto)
  - refrescar, arrancar/apagar seleccionado, arrancar/apagar todos
- Pestaña `Perfiles`:
  - almacenes `privado` y `remoto`
  - privado: `%LOCALAPPDATA%\WordPressUtilidades\private_profiles.json`
  - remoto: volumen `wpu_profiles_remote` en `/data/profiles.json`
  - crear/actualizar/eliminar perfiles
  - copiar perfil entre almacenes (`Copiar a remoto` / `Copiar a privado`)
  - quitar contenedores seleccionados del perfil
  - marcado visual de contenedores ya incluidos en el perfil seleccionado
  - ejecutar perfil para arrancar o apagar sus contenedores
- Pestaña `Networks`:
  - listar networks de usuario (excluye `bridge`, `host`, `none`)
  - ver contenedores conectados por network
  - crear, eliminar y renombrar networks
  - conectar o desconectar contenedores
- Pestaña `Historial`:
  - lectura/escritura de historial remoto compartido
  - requiere modo Docker `remoto` para auditoria centralizada
  - filtros por nivel (`OK`, `ERROR`, `WARN`, `INFO`)
  - busqueda por texto libre
  - recarga manual y limpieza de filtros
  - copia del contenido visible al portapapeles
- Pestaña `Logs`:
  - selector de contenedor
  - lectura de ultimas N lineas de logs
  - auto-refresco para seguimiento continuo
  - exportacion de logs visibles a archivo `.txt`
  - copia del contenido visible al portapapeles
- Registro unificado de acciones GUI:
  - operaciones de Docker
  - operaciones de perfiles
  - operaciones de networks
  - consulta de logs de contenedores
  - apertura de scripts y documentacion

## Nota

Esta version mantiene compatibilidad con tus scripts actuales y ya incorpora gestion GUI de perfiles y networks para usar menos consola.
