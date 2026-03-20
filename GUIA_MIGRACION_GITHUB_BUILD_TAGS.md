# Guia de migracion, tags y build

## 1) Flujo actual del proyecto (resumen rapido)

- La version fuente esta en `app_escritorio/version.json`.
- El workflow `Auto Tag From Version` crea el tag `vX.Y.Z` cuando haces push a `main`.
- El workflow `Build Windows EXE` compila `Wordpress_Utilidades.exe` y lo publica en Release.

Archivos clave:
- `.github/workflows/auto-tag-from-version.yml`
- `.github/workflows/build-windows-exe.yml`
- `app_escritorio/version.json`

---

## 2) Cambiar version, tag y build (paso a paso)

### Paso 1: Subir version

Edita `app_escritorio/version.json` y cambia:
- `version`: por ejemplo `1.1.5`
- `download_url_exe`: debe apuntar al nuevo tag/release
- `download_url_py` y `download_url`: deben apuntar al repo correcto

Ejemplo:

```json
{
  "version": "1.1.5",
  "download_url_exe": "https://github.com/TU_USUARIO/TU_REPO/releases/download/v1.1.5/Wordpress_Utilidades.exe",
  "download_url_py": "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/app_escritorio/wordpress_utilidades_app.py",
  "download_url": "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/app_escritorio/wordpress_utilidades_app.py",
  "notes": "Notas de la version"
}
```

### Paso 2: Commit y push

```powershell
git add app_escritorio/version.json
git commit -m "Bump version to 1.1.5"
git push origin main
```

### Paso 3: Que ocurre automaticamente

1. `auto-tag-from-version.yml` lee `version.json`.
2. Si no existe, crea y sube `v1.1.5`.
3. `build-windows-exe.yml` compila en Windows.
4. Publica `Wordpress_Utilidades.exe` en Release del tag.

### Paso 4: Verificacion

- Revisa en Actions que ambos workflows terminen en verde.
- Revisa en Releases que exista `v1.1.5` con el asset `Wordpress_Utilidades.exe`.
- Prueba la actualizacion desde una version anterior de la app.

---

## 3) Configuracion Git para usuario nuevo

Ejecutar una sola vez en el equipo nuevo:

```powershell
git config --global user.name "Tu Nombre"
git config --global user.email "tu_correo@dominio.com"
git config --global init.defaultBranch main
```

Opcional recomendado:

```powershell
git config --global core.autocrlf true
git config --global pull.rebase false
```

Verificar configuracion:

```powershell
git config --global --list
```

---

## 4) Migrar de un GitHub a otro GitHub

## 4.1 Cambiar remoto del repo local

```powershell
git remote -v
git remote rename origin old-origin
git remote add origin https://github.com/NUEVO_USUARIO/NUEVO_REPO.git
git push -u origin main
git push origin --tags
```

## 4.2 Ajustar URLs de actualizacion

Actualiza en `app_escritorio/version.json`:
- dominio/repo en `download_url_exe`
- dominio/repo en `download_url_py`
- dominio/repo en `download_url`

## 4.3 Crear secret para auto-tag

En el repo nuevo:
- Settings > Secrets and variables > Actions
- crear secret `GH_PAT`
- el token debe tener al menos permiso `contents: write`

Sin ese secret, `auto-tag-from-version.yml` no podra crear tags.

## 4.4 Verificar permisos de Actions

En el repo nuevo:
- Settings > Actions > General
- Workflow permissions: `Read and write permissions`

---

## 5) Migracion completa del historial (opcional)

Si quieres mover TODO (branches, tags, historial):

```powershell
git clone --mirror https://github.com/VIEJO_USUARIO/VIEJO_REPO.git
cd VIEJO_REPO.git
git remote set-url origin https://github.com/NUEVO_USUARIO/NUEVO_REPO.git
git push --mirror
```

Luego clona normalmente para trabajar:

```powershell
cd ..
git clone https://github.com/NUEVO_USUARIO/NUEVO_REPO.git
```

---

## 6) Como seria en un servidor propio

Hay 2 escenarios comunes.

## Escenario A: GitHub Enterprise Server

Si tu servidor propio es GitHub Enterprise Server:
- mantienes casi igual los workflows de `.github/workflows/`.
- cambias el remoto a tu dominio enterprise.
- mantienes `GH_PAT` (generado en enterprise) con `contents: write`.

Remoto ejemplo:

```powershell
git remote set-url origin https://github.tuempresa.com/area/wordpress-utility.git
```

Tambien debes actualizar `version.json` para apuntar a tu dominio enterprise (raw + releases).

## Escenario B: Gitea/GitLab/Forgejo u otro Git server

En este caso GitHub Actions no siempre aplica igual. Tienes 2 alternativas:

### Opcion 1: CI del servidor

- GitLab CI: usa `.gitlab-ci.yml` con runner Windows para PyInstaller.
- Gitea/Forgejo Actions: usar sintaxis compatible y runner disponible.

Flujo minimo necesario:
1. leer version desde `app_escritorio/version.json`
2. crear tag `vX.Y.Z` si no existe
3. compilar EXE en Windows
4. publicar EXE como release asset

### Opcion 2: Build externo (runner propio)

Si tu server no tiene CI Windows:
- ejecuta build en una maquina Windows propia
- publica release por API del servidor
- actualiza `version.json` con la URL final del asset

---

## 7) Checklist rapido antes de liberar

- `version` incrementada en `app_escritorio/version.json`
- URLs del repo correctas (usuario, repo, dominio)
- Secret `GH_PAT` creado (si aplica)
- Actions con permisos de escritura
- Release creada con `Wordpress_Utilidades.exe`
- Prueba de update real desde una version anterior

---

## 8) Comandos utiles de soporte

Ver remotos:

```powershell
git remote -v
```

Ver tags locales:

```powershell
git tag
```

Crear tag manual (si desactivas auto-tag):

```powershell
git tag -a v1.1.5 -m "Release v1.1.5"
git push origin v1.1.5
```

Forzar re-ejecucion manual de workflows:
- En GitHub, pestaña Actions > seleccionar workflow > Run workflow.
