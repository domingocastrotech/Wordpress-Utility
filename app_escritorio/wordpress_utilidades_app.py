import os
import io
import json
import math
import queue
import re
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
import tkinter as tk
import unicodedata
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

# ──────────────────────────────────────────────────────────────────────────────
#  VERSIÓN Y ACTUALIZACIÓN AUTOMÁTICA
# ──────────────────────────────────────────────────────────────────────────────
APP_VERSION = "1.0.9"  # <-- actualiza este valor en cada release

# URL pública donde publicas tu version.json (GitHub raw, servidor propio, etc.)
# Ejemplo GitHub: "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/version.json"
# El archivo version.json debe tener este formato:
# {
#   "version": "1.1.0",
#   "download_url": "https://github.com/TU_USUARIO/TU_REPO/releases/download/v1.1.0/wordpress_utilidades_app.py",
#   "notes": "Descripción de los cambios"
# }
_UPDATE_CHECK_URLS = [
    "https://raw.githubusercontent.com/domingocastrotech/Wordpress-Utility/main/version.json",
    "https://raw.githubusercontent.com/domingocastrotech/Wordpress-Utility/main/app_escritorio/version.json",
    "https://raw.githubusercontent.com/domingocastrotech/Wordpress-Utility/master/version.json",
    "https://raw.githubusercontent.com/domingocastrotech/Wordpress-Utility/master/app_escritorio/version.json",
]


def _is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def _current_install_target() -> str:
    """Ruta del archivo que debe reemplazarse al actualizar (.exe o .py)."""
    if _is_frozen_app():
        return os.path.abspath(sys.executable)
    return os.path.abspath(__file__)


def _restart_command_for_target(target_path: str) -> list[str]:
    """Comando para relanzar la app tras aplicar la actualización."""
    if _is_frozen_app():
        return [target_path]
    return [sys.executable, target_path]


def _select_download_url(update_info: dict) -> str:
    """Elige la URL de descarga adecuada según el modo de ejecución."""
    if _is_frozen_app():
        return (
            update_info.get("download_url_exe")
            or update_info.get("download_url")
            or ""
        )
    return (
        update_info.get("download_url_py")
        or update_info.get("download_url")
        or ""
    )


def _parse_version(v: str) -> tuple[int, ...]:
    """Convierte '1.2.3' en (1, 2, 3) para comparar numéricamente."""
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0,)


def _check_for_updates_worker(current_version: str, callback: "Callable[[dict], None]") -> None:
    """Hilo secundario: consulta la URL de versión y dispara callback si hay novedad."""
    try:
        data: dict | None = None
        for check_url in _UPDATE_CHECK_URLS:
            try:
                req = urllib.request.Request(
                    check_url,
                    headers={"User-Agent": f"WPUtilidades-UpdateChecker/{current_version}"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict):
                    break
            except Exception:
                continue

        if not data:
            return

        remote_ver = data.get("version", "")
        if _parse_version(remote_ver) > _parse_version(current_version):
            callback(data)
    except Exception:
        pass  # Sin conexión o URL no configurada → silencioso


def _ps_quote(value: str) -> str:
    """Escapa comillas simples para strings de PowerShell entre comillas simples."""
    return value.replace("'", "''")


def _launch_updater_and_exit(new_file_path: str, current_file_path: str, restart_cmd: list[str]) -> None:
    """
    Lanza un actualizador gráfico (PowerShell + WinForms) que:
      1. Espera cierre de la app
      2. Reemplaza archivo actual (.py/.exe) con reintentos
      3. Relanza la app
    Luego cierra el proceso actual para liberar el ejecutable.
    """
    if not restart_cmd:
        return

    restart_exe = restart_cmd[0]
    restart_args = restart_cmd[1:]
    restart_args_ps = ", ".join(f"'{_ps_quote(a)}'" for a in restart_args)
    if not restart_args_ps:
        restart_args_ps = ""

    ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$pidToWait = {os.getpid()}
$newFile = '{_ps_quote(new_file_path)}'
$currentFile = '{_ps_quote(current_file_path)}'
$restartExe = '{_ps_quote(restart_exe)}'
$restartArgs = @({restart_args_ps})

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Actualizando WordPress Utilidades'
$form.Size = New-Object System.Drawing.Size(460, 170)
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false

$label = New-Object System.Windows.Forms.Label
$label.AutoSize = $false
$label.Size = New-Object System.Drawing.Size(420, 34)
$label.Location = New-Object System.Drawing.Point(18, 14)
$label.Text = 'Preparando actualización...'
$label.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.Controls.Add($label)

$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Location = New-Object System.Drawing.Point(18, 64)
$bar.Size = New-Object System.Drawing.Size(420, 22)
$bar.Minimum = 0
$bar.Maximum = 100
$bar.Style = 'Continuous'
$form.Controls.Add($bar)

$pct = New-Object System.Windows.Forms.Label
$pct.AutoSize = $false
$pct.Size = New-Object System.Drawing.Size(420, 24)
$pct.Location = New-Object System.Drawing.Point(18, 96)
$pct.Text = '0%'
$pct.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$form.Controls.Add($pct)

function Set-Ui([int]$value, [string]$text) {{
    if ($value -lt 0) {{ $value = 0 }}
    if ($value -gt 100) {{ $value = 100 }}
    $bar.Value = $value
    $label.Text = $text
    $pct.Text = "$value%"
    [System.Windows.Forms.Application]::DoEvents()
}}

$form.Show()
Set-Ui 5 'Esperando cierre de la app...'

$waitTicks = 0
while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) {{
    Start-Sleep -Milliseconds 250
    $waitTicks++
    $step = 5 + [int]([Math]::Min(15, $waitTicks / 2))
    Set-Ui $step 'Esperando cierre de la app...'
    if ($waitTicks -ge 120) {{ break }}
}}

$copied = $false
for ($i = 1; $i -le 80; $i++) {{
    try {{
        Copy-Item -LiteralPath $newFile -Destination $currentFile -Force -ErrorAction Stop
        $copied = $true
        break
    }} catch {{}}

    $prog = 20 + [int](($i / 80) * 70)
    Set-Ui $prog "Aplicando actualización... intento $i/80"
    Start-Sleep -Milliseconds 250
}}

    if ($copied) {{
    Set-Ui 95 'Reiniciando aplicación...'
    # Limpiar carpetas temporales de PyInstaller del proceso anterior
    $tempDir = [System.IO.Path]::GetTempPath()
    Get-ChildItem -Path $tempDir -Directory -Filter '_MEI*' -ErrorAction SilentlyContinue | ForEach-Object {{
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }}
    Start-Sleep -Milliseconds 800
    if ($restartArgs.Count -gt 0) {{
        Start-Process -FilePath $restartExe -ArgumentList $restartArgs | Out-Null
    }} else {{
        Start-Process -FilePath $restartExe | Out-Null
    }}

    Set-Ui 100 'Actualización completada'
    Start-Sleep -Milliseconds 700
    Remove-Item -LiteralPath $newFile -Force -ErrorAction SilentlyContinue
}} else {{
    [System.Windows.Forms.MessageBox]::Show(
        'No se pudo reemplazar el archivo porque sigue en uso. Cierra la app y vuelve a intentar.',
        'Error de actualización',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}}

$form.Close()
""".strip()

    fd, ps1_path = tempfile.mkstemp(prefix="wpu_update_", suffix=".ps1")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(ps_script)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        return

    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                ps1_path,
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
    except Exception:
        return

    os._exit(0)


# ──────────────────────────────────────────────────────────────────────────────

try:
    import docker  # type: ignore[import-not-found]
    from docker.errors import APIError, DockerException, NotFound  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    docker = None  # type: ignore[assignment]
    APIError = Exception  # type: ignore[assignment]
    DockerException = Exception  # type: ignore[assignment]
    NotFound = Exception  # type: ignore[assignment]


def _looks_like_container_spec(path_value: str) -> bool:
    if ":" not in path_value:
        return False
    drive, _tail = os.path.splitdrive(path_value)
    return not bool(drive)


def _sdk_create_client(base_url: str | None, timeout_seconds: int | None) -> object:
    if docker is None:
        raise RuntimeError("Docker SDK no disponible. Instala paquete Python 'docker'.")
    if base_url:
        client = docker.DockerClient(base_url=base_url, timeout=timeout_seconds)
    else:
        client = docker.from_env(timeout=timeout_seconds)
    client.ping()
    try:
        client.api.timeout = None
    except Exception:
        pass
    return client


def _sdk_cp_from_container_impl(client: object, container_name: str, src_path: str, local_path: str) -> None:
    container = client.containers.get(container_name)
    stream, _stat = container.get_archive(src_path)
    payload = b"".join(stream)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as tar:
        members = tar.getmembers()
        if not members:
            raise RuntimeError("No se recibieron datos desde contenedor")
        first = members[0]
        extracted = tar.extractfile(first)
        if extracted is None:
            raise RuntimeError("No se pudo extraer archivo")
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(extracted.read())


def _sdk_cp_to_container_impl(client: object, local_path: str, container_name: str, target_path: str) -> None:
    container = client.containers.get(container_name)
    target_norm = target_path.replace("\\", "/")
    parent_dir = os.path.dirname(target_norm.rstrip("/")) or "/"
    target_name = os.path.basename(target_norm.rstrip("/"))
    if not target_name:
        target_name = os.path.basename(local_path.rstrip("\\/"))

    fd, temp_tar_path = tempfile.mkstemp(prefix="wpu_sdk_cp_", suffix=".tar")
    os.close(fd)
    try:
        with tarfile.open(temp_tar_path, mode="w") as tar:
            tar.add(local_path, arcname=target_name)
        with open(temp_tar_path, "rb") as tar_stream:
            ok = container.put_archive(parent_dir, tar_stream.read())
        if not ok:
            raise RuntimeError("No se pudo copiar al contenedor")
    finally:
        try:
            os.remove(temp_tar_path)
        except OSError:
            pass


def _run_sdk_cp_helper(direction: str, base_url: str | None, src: str, dst: str) -> int:
    client = _sdk_create_client(base_url=base_url, timeout_seconds=None)
    if direction == "from":
        container_name, container_path = src.split(":", 1)
        _sdk_cp_from_container_impl(client, container_name, container_path, dst)
        return 0
    if direction == "to":
        container_name, container_path = dst.split(":", 1)
        _sdk_cp_to_container_impl(client, src, container_name, container_path)
        return 0
    raise RuntimeError(f"Direccion de copia no soportada: {direction}")


def _run_helper_cli_from_argv(argv: list[str]) -> int | None:
    if len(argv) >= 2 and argv[1] == "--wpu-sdk-cp":
        if len(argv) != 6:
            print("Uso helper invalido", file=sys.stderr)
            return 2
        _mode = argv[1]
        direction = argv[2]
        base_url = argv[3] or None
        src = argv[4]
        dst = argv[5]
        try:
            return _run_sdk_cp_helper(direction, base_url, src, dst)
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return None


class WordPressUtilitiesApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Utilidades WordPress + Docker")
        self.root.geometry("1280x720")
        self.root.minsize(820, 500)
        self.root.configure(background="#f1f5f9")

        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.tools_dir = os.path.dirname(self.app_dir)
        self.profiles_file = os.path.join(self.app_dir, "perfiles_contenedores.ini")
        self.private_profiles_dir = os.path.join(os.environ.get("LOCALAPPDATA", self.tools_dir), "WordPressUtilidades")
        self.private_profiles_file = os.path.join(self.private_profiles_dir, "private_profiles.json")
        self.remote_profiles_volume = "wpu_profiles_remote"
        self.remote_profiles_path = "/data/profiles.json"
        self.remote_history_volume = "wpu_history_remote"
        self.remote_history_path = "/data/historial_gestor.log"
        self.history_file = os.path.join(self.app_dir, "historial_gestor.log")
        self.audit_actor = self._build_audit_actor()
        self._migrate_legacy_state_files()

        self.status_var = tk.StringVar(value="Docker: comprobando...")
        self.last_refresh_var = tk.StringVar(value="Ultima actualizacion: -")
        self.connection_mode_var = tk.StringVar(value="Modo: local")
        self.profile_name_var = tk.StringVar(value="")
        self.profile_scope_var = tk.StringVar(value="privado")
        self.network_container_var = tk.StringVar(value="")
        self.network_driver_var = tk.StringVar(value="bridge")
        self.volume_driver_var = tk.StringVar(value="local")
        self.history_level_var = tk.StringVar(value="TODOS")
        self.history_search_var = tk.StringVar(value="")
        self.log_container_var = tk.StringVar(value="")
        self.log_lines_var = tk.StringVar(value="100")
        self.log_auto_refresh_var = tk.BooleanVar(value=False)
        self.log_follow_var = tk.BooleanVar(value=False)
        self.docker_mode = "local"
        self.docker_host = ""
        self.discovered_lan_hosts: list[str] = []
        self.docker_cli_available: bool | None = None
        self.docker_sdk_client: object | None = None
        self._sdk_last_fail_at: float = 0.0
        self._sdk_retry_cooldown_sec: float = 5.0
        self.last_docker_error_detail = ""
        self._last_remote_diag_at: float = 0.0
        self._last_remote_diag_text = ""
        self._docker_last_ready = False
        self._docker_last_checked_at = 0.0
        self._docker_check_in_progress = False
        self._docker_check_queue: queue.Queue[tuple[bool, str, str]] = queue.Queue()
        self._docker_check_job_id: str | None = None
        self._history_refresh_in_progress = False
        self._history_refresh_requested = False
        self._history_refresh_queue: queue.Queue[tuple[bool, object]] = queue.Queue()
        self._history_refresh_job_id: str | None = None
        self._history_pending_lines: list[str] = []
        self._history_pending_lock = threading.Lock()
        self._profiles_loading = False
        self._profiles_load_requested = False
        self._profiles_load_queue: queue.Queue[tuple[str, bool, object]] = queue.Queue()
        self._profiles_load_job_id: str | None = None
        self._profiles_load_guard_job_id: str | None = None
        self._profiles_loading_scope: str | None = None
        self._profiles_pending_name: str | None = None
        self._profiles_load_started_at: float = 0.0
        self._profiles_load_timeout_sec: float = 15.0
        self._profiles_remote_retry_cooldown_sec: float = 20.0
        self._profiles_remote_backoff_until: float = 0.0
        self._helper_label_key = "wpu.helper"
        self._helper_label_value = "1"
        self._helper_cleanup_in_progress = False
        self._helper_cleanup_last_at: float = 0.0

        self.refresh_job_id: str | None = None
        self.logs_refresh_job_id: str | None = None
        self.logs_follow_poll_job_id: str | None = None
        self.container_cache: list[str] = []
        self.container_image_cache: dict[str, str] = {}
        self.profiles_data: dict[str, list[str]] = {}
        self.private_profiles_data: dict[str, list[str]] = {}
        self.remote_profiles_data: dict[str, list[str]] = {}
        self.network_data: dict[str, dict[str, object]] = {}
        self.volume_data: dict[str, dict[str, object]] = {}
        self.history_lines: list[str] = []
        self.logs_follow_process: subprocess.Popen | None = None
        self.logs_follow_queue: queue.Queue[str] = queue.Queue()
        self._sdk_follow_stop_event: threading.Event | None = None
        self._sdk_follow_active = False
        self.docker_autostart_attempted = False
        self.tabs: ttk.Notebook | None = None
        self.dynamic_tabs: dict[str, ttk.Frame] = {}
        self.sidebar_frame: tk.Frame | None = None
        self.sidebar_logo_title_label: tk.Label | None = None
        self.sidebar_logo_subtitle_label: tk.Label | None = None
        self.sidebar_status_label: tk.Label | None = None
        self.sidebar_shortcuts_label: tk.Label | None = None
        self.sidebar_quit_button: tk.Button | None = None
        self.sidebar_nav_buttons: list[tuple[tk.Button, str, str]] = []
        self.is_compact_layout = False
        self._layout_reflow_job: str | None = None
        self.spinner_job_id: str | None = None
        self.spinner_index = 0
        self.spinner_base_text = ""
        self.docker_status_dot: tk.Label | None = None
        self.connection_mode_badge: tk.Label | None = None
        self.container_action_btns: list[ttk.Button] = []
        self.profile_action_btns: list[ttk.Button] = []
        self._container_spinner_job: str | None = None
        self._container_spinner_items: list[str] = []
        self._container_spinner_frame: int = 0
        self._container_loading_job: str | None = None
        self._container_loading_frame: int = 0
        self._profile_spinner_job: str | None = None
        self._profile_spinner_name: str = ""
        self._profile_spinner_frame2: int = 0
        self.container_admin_tree: ttk.Treeview | None = None
        self.history_tab_frame: ttk.Frame | None = None
        self.container_tab_frame: ttk.Frame | None = None
        self.volumes_tab_frame: ttk.Frame | None = None
        self.profiles_tab_frame: ttk.Frame | None = None
        self.networks_tab_frame: ttk.Frame | None = None
        self.logs_tab_frame: ttk.Frame | None = None
        self._last_auto_heavy_refresh_at: float = 0.0
        self._auto_heavy_refresh_interval_sec: float = 30.0

        self._configure_styles()
        self._build_ui()
        self._bind_global_shortcuts()
        if not self._prompt_startup_connection_mode():
            self.root.after(10, self.root.destroy)
            return
        self.status_var.trace_add("write", self._update_status_dot)
        self._update_connection_mode_badge()
        self.refresh_everything()

        # Comprobar actualizaciones en segundo plano (2s de retraso para que la UI esté lista)
        self.root.after(2000, self._start_update_check)

    # ── Actualización automática ──────────────────────────────────────────────

    def _start_update_check(self) -> None:
        """Lanza la comprobación de versión en hilo secundario."""
        t = threading.Thread(
            target=_check_for_updates_worker,
            args=(APP_VERSION, self._on_update_available),
            daemon=True,
        )
        t.start()

    def _on_update_available(self, update_info: dict) -> None:
        """Callback ejecutado desde el hilo de red; despacha al hilo principal de Tkinter."""
        self.root.after(0, lambda: self._show_update_dialog(update_info))

    def _show_update_dialog(self, update_info: dict) -> None:
        """Muestra una ventana de actualización con progreso de descarga."""
        remote_ver = update_info.get("version", "?")
        download_url = _select_download_url(update_info)
        notes = update_info.get("notes", "")

        dlg = tk.Toplevel(self.root)
        dlg.title("Actualización disponible")
        dlg.geometry("460x300")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg="#f1f5f9")

        # Centrar sobre la ventana principal
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 460) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 300) // 2
        dlg.geometry(f"+{x}+{y}")

        tk.Label(
            dlg,
            text=f"🆕  Nueva versión disponible: v{remote_ver}",
            font=("Segoe UI Semibold", 13),
            bg="#f1f5f9",
            fg="#0f766e",
        ).pack(pady=(22, 4))

        tk.Label(
            dlg,
            text=f"Versión instalada: v{APP_VERSION}",
            font=("Segoe UI", 10),
            bg="#f1f5f9",
            fg="#6b7f93",
        ).pack()

        if notes:
            tk.Label(
                dlg,
                text=notes,
                font=("Segoe UI", 10),
                bg="#f1f5f9",
                fg="#365066",
                wraplength=400,
                justify="center",
            ).pack(pady=(10, 0))

        status_var = tk.StringVar(value="")
        status_lbl = tk.Label(dlg, textvariable=status_var, bg="#f1f5f9", fg="#6b7f93", font=("Segoe UI", 9))
        status_lbl.pack(pady=(12, 2))

        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(dlg, variable=progress_var, maximum=100, length=380)
        progress_bar.pack(pady=(0, 14))

        btn_frame = tk.Frame(dlg, bg="#f1f5f9")
        btn_frame.pack()

        update_btn = ttk.Button(btn_frame, text="⬇  Descargar e instalar", style="Accent.TButton")
        skip_btn   = ttk.Button(btn_frame, text="Ahora no", style="Ghost.TButton")
        update_btn.pack(side="left", padx=6)
        skip_btn.pack(side="left", padx=6)

        def do_skip() -> None:
            dlg.destroy()

        def do_update() -> None:
            if not download_url:
                mode = ".exe" if _is_frozen_app() else ".py"
                messagebox.showerror(
                    "Error",
                    f"No hay URL de descarga configurada para modo {mode}.",
                    parent=dlg,
                )
                return
            update_btn.configure(state="disabled")
            skip_btn.configure(state="disabled")
            status_var.set("Iniciando descarga...")
            t = threading.Thread(
                target=self._download_and_apply_update,
                args=(download_url, dlg, status_var, progress_var, update_btn, skip_btn),
                daemon=True,
            )
            t.start()

        update_btn.configure(command=do_update)
        skip_btn.configure(command=do_skip)

    def _download_and_apply_update(
        self,
        url: str,
        dlg: tk.Toplevel,
        status_var: tk.StringVar,
        progress_var: tk.DoubleVar,
        update_btn: ttk.Button,
        skip_btn: ttk.Button,
    ) -> None:
        """Descarga la actualización con barra de progreso y luego aplica el reemplazo."""

        def ui(fn: "Callable[[], None]") -> None:
            """Despacha al hilo principal de forma segura."""
            try:
                self.root.after(0, fn)
            except Exception:
                pass

        current_target = _current_install_target()
        restart_cmd = _restart_command_for_target(current_target)

        parsed = urllib.parse.urlparse(url)
        _, ext = os.path.splitext(parsed.path)
        if not ext:
            ext = ".tmp"

        fd, tmp_path = tempfile.mkstemp(prefix="wpu_new_", suffix=ext)
        os.close(fd)

        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"WPUtilidades-Updater/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                chunk_size = 16 * 1024

                with open(tmp_path, "wb") as fh:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded / total * 100
                            _pct = pct  # closure capture
                            ui(lambda p=_pct: progress_var.set(p))
                        kb = downloaded // 1024
                        _kb = kb
                        ui(lambda k=_kb: status_var.set(f"Descargando... {k} KB"))

                if total > 0 and downloaded != total:
                    raise RuntimeError(
                        f"Descarga incompleta ({downloaded} de {total} bytes)."
                    )

            # Verificación mínima: que el archivo no esté vacío
            size = os.path.getsize(tmp_path)
            if size < 100:
                raise RuntimeError("El archivo descargado parece incompleto o inválido.")

            # Validaciones de integridad según tipo de actualización.
            if _is_frozen_app():
                # Un ejecutable PE en Windows debe iniciar con bytes MZ.
                with open(tmp_path, "rb") as fh:
                    magic = fh.read(2)
                if magic != b"MZ":
                    raise RuntimeError(
                        "El archivo descargado no parece un .exe válido (firma PE inválida)."
                    )
            else:
                # Para modo script, validar que el contenido sea texto Python razonable.
                with open(tmp_path, "rb") as fh:
                    head = fh.read(4096)
                try:
                    head_text = head.decode("utf-8", errors="ignore")
                except Exception:
                    head_text = ""
                if not any(tok in head_text for tok in ("import ", "def ", "class ", "#")):
                    raise RuntimeError(
                        "El archivo descargado no parece un script Python válido."
                    )

            ui(lambda: progress_var.set(100))
            ui(lambda: status_var.set("Descarga completada. Aplicando actualización..."))

            # Pequeña pausa para que el usuario vea el mensaje
            time.sleep(1.2)

            # Cerrar diálogo y lanzar el actualizador externo
            def _apply() -> None:
                try:
                    dlg.destroy()
                except Exception:
                    pass
                _launch_updater_and_exit(tmp_path, current_target, restart_cmd)

            ui(_apply)

        except Exception as exc:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

            def _err(msg: str = str(exc), failed_url: str = url) -> None:
                status_var.set(f"Error: {msg}")
                try:
                    update_btn.configure(state="normal")
                    skip_btn.configure(state="normal")
                except Exception:
                    pass
                messagebox.showerror(
                    "Error de actualización",
                    (
                        "No se pudo descargar la actualización:\n\n"
                        f"{msg}\n\n"
                        "URL consultada:\n"
                        f"{failed_url}"
                    ),
                    parent=dlg,
                )

            ui(_err)

    # ── Fin actualización automática ──────────────────────────────────────────

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg        = "#edf3f7"   # main background
        surface   = "#ffffff"   # card / panel
        surface2  = "#f5f9fc"   # secondary surface
        text      = "#0f172a"   # primary text
        text2     = "#365066"   # secondary text
        muted     = "#6b7f93"   # muted text
        accent    = "#0f766e"   # teal-700
        accent_hv = "#115e59"   # teal-800
        border    = "#d7e3ec"   # border
        selected  = "#d1fae5"   # selected rows

        style.configure(".", font=("Segoe UI", 10), background=bg, foreground=text)
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=surface)
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("Surface.TLabel", background=surface, foreground=text)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 14), background=bg, foreground="#0b2a3f")
        style.configure("Muted.TLabel", background=bg, foreground=muted, font=("Segoe UI", 9))

        style.configure("TNotebook", background=bg, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", padding=(16, 10), background="#e3edf3", foreground=text2, font=("Segoe UI Semibold", 10))
        style.map(
            "TNotebook.Tab",
            background=[("selected", surface), ("active", "#d2e4ef")],
            foreground=[("selected", accent)],
        )

        style.configure(
            "TButton",
            padding=(12, 8),
            background="#deebf3",
            foreground="#0f172a",
            borderwidth=1,
            relief="solid",
            bordercolor=border,
        )
        style.map(
            "TButton",
            background=[("active", "#c8dbe8"), ("pressed", "#aac0d0")],
            foreground=[("active", "#0f172a")],
            relief=[("active", "solid")],
        )
        style.configure("Accent.TButton", padding=(13, 8), background=accent, foreground="#ffffff", borderwidth=0, relief="flat")
        style.map("Accent.TButton", background=[("active", accent_hv), ("pressed", "#134e4a")], relief=[("active", "flat")])
        style.configure("Ghost.TButton", padding=(9, 6), background=bg, foreground=text2, borderwidth=0, relief="flat")
        style.map("Ghost.TButton", background=[("active", "#dce8f0")], relief=[("active", "flat")])
        style.configure("Admin.TButton", padding=(10, 7), background="#dce8f0", foreground="#0f172a", borderwidth=1, relief="solid")
        style.map("Admin.TButton", background=[("active", "#c8dbe8"), ("pressed", "#aac0d0")], foreground=[("active", "#0f172a")])
        style.configure("Danger.TButton", padding=(10, 7), background="#fee2e2", foreground="#991b1b", borderwidth=1, relief="solid")
        style.map("Danger.TButton", background=[("active", "#fecaca"), ("pressed", "#fca5a5")], foreground=[("active", "#7f1d1d")])

        style.configure("TLabelframe", background=bg, borderwidth=1, relief="solid", bordercolor=border)
        style.configure("TLabelframe.Label", background=bg, foreground=accent, font=("Segoe UI Semibold", 10))

        style.configure("TEntry", fieldbackground=surface, bordercolor=border, insertcolor="#0b2a3f")
        style.configure("TCombobox", fieldbackground=surface, bordercolor=border)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", surface), ("readonly focus", surface)],
            foreground=[("readonly", text), ("readonly focus", text)],
            selectbackground=[("readonly", surface), ("readonly focus", surface)],
            selectforeground=[("readonly", text), ("readonly focus", text)],
        )

        style.configure("Horizontal.TProgressbar", troughcolor=border, background=accent, borderwidth=0, thickness=8)

        style.configure("TScrollbar", troughcolor=surface2, background="#c4d5e2", relief="flat", arrowsize=13)
        style.map("TScrollbar", background=[("active", "#90a7bb")])

        style.configure(
            "Treeview",
            background=surface,
            fieldbackground=surface,
            foreground=text,
            rowheight=30,
            relief="flat",
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=surface2,
            foreground=text2,
            font=("Segoe UI Semibold", 10),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", selected)], foreground=[("selected", accent)])
        style.map("Treeview.Heading", background=[("active", border)])

        style.configure("TSeparator", background=border)
        style.configure("TCheckbutton", background=bg, foreground=text)

    def _build_ui(self) -> None:
        _SB  = "#0b2537"   # sidebar background
        _SBH = "#123347"   # sidebar hover
        _SHD = "#081b2a"   # sidebar header
        _FG  = "#d6e4ee"   # sidebar foreground
        _FGM = "#7d95a8"   # sidebar muted foreground

        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # ── Sidebar ─────────────────────────────────────────────────────────
        sidebar = tk.Frame(self.root, bg=_SB, width=234)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        self.sidebar_frame = sidebar

        # Logo area
        logo_f = tk.Frame(sidebar, bg=_SHD, padx=18, pady=18)
        logo_f.pack(fill="x")
        self.sidebar_logo_title_label = tk.Label(logo_f, text="\u2726  WordPress", fg="#93c5fd", bg=_SHD,
                             font=("Segoe UI Semibold", 14))
        self.sidebar_logo_title_label.pack(anchor="w")
        self.sidebar_logo_subtitle_label = tk.Label(logo_f, text="Docker Tools", fg="#88a0b2", bg=_SHD,
                                font=("Segoe UI", 9))
        self.sidebar_logo_subtitle_label.pack(anchor="w", pady=(3, 0))
        tk.Frame(logo_f, bg="#14b8a6", height=2).pack(fill="x", pady=(14, 0))

        # Navigation buttons
        nav_items = [
            ("\u2699  Crear / Recrear entorno",   self.open_setup_wizard),
            ("\u2b07  Importar backup",            self.open_import_wizard),
            ("\u2b06  Exportar backup",            self.open_export_wizard),
            ("\u25b6  Gestionar contenedores",     self.open_containers_manager),
            ("\u2139  Ayuda — esta app",           self.open_app_docs),
            ("\u2261  Documentacion scripts",      self.open_docs),
        ]
        nav_f = tk.Frame(sidebar, bg=_SB)
        nav_f.pack(fill="x", pady=(6, 0))
        self.sidebar_nav_buttons = []
        for label, cmd in nav_items:
            compact_label = label.split("  ", 1)[0].strip()
            btn = tk.Button(
                nav_f, text=label, command=cmd, anchor="w",
                padx=18, pady=11, relief="flat", bd=0,
                bg=_SB, fg=_FG,
                activebackground=_SBH, activeforeground="#ffffff",
                font=("Segoe UI", 10), cursor="hand2", highlightthickness=0,
            )
            btn.pack(fill="x")
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=_SBH, fg="#ffffff"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=_SB, fg=_FG))
            self.sidebar_nav_buttons.append((btn, label, compact_label))

        self.sidebar_shortcuts_label = tk.Label(
            sidebar,
            text="Atajos: Ctrl+R refrescar | Ctrl+I importar | Ctrl+E exportar",
            fg="#7d95a8",
            bg=_SB,
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
            padx=18,
            pady=8,
        )
        self.sidebar_shortcuts_label.pack(fill="x")

        # Separator
        tk.Frame(sidebar, bg="#1f3e54", height=1).pack(fill="x", padx=16, pady=(12, 6))

        # Close button
        quit_b = tk.Button(
            sidebar, text="\u00d7  Cerrar aplicacion", command=self.on_close,
            anchor="w", padx=18, pady=10, relief="flat", bd=0,
            bg=_SB, fg=_FGM,
            activebackground="#7f1d1d", activeforeground="#fca5a5",
            font=("Segoe UI", 10), cursor="hand2", highlightthickness=0,
        )
        quit_b.pack(fill="x")
        quit_b.bind("<Enter>", lambda e: quit_b.configure(bg="#7f1d1d", fg="#fca5a5"))
        quit_b.bind("<Leave>", lambda e: quit_b.configure(bg=_SB, fg=_FGM))
        self.sidebar_quit_button = quit_b

        # Docker status at the bottom of the sidebar
        status_f = tk.Frame(sidebar, bg=_SHD, padx=16, pady=12)
        status_f.pack(side="bottom", fill="x")
        dot_row = tk.Frame(status_f, bg=_SHD)
        dot_row.pack(fill="x")
        self.docker_status_dot = tk.Label(dot_row, text="\u25cf", fg="#7d95a8", bg=_SHD,
                                          font=("Segoe UI", 12))
        self.docker_status_dot.pack(side="left")
        self.sidebar_status_label = tk.Label(
            dot_row,
            textvariable=self.status_var,
            fg="#88a0b2",
            bg=_SHD,
            font=("Segoe UI", 9),
            wraplength=160,
            justify="left",
        )
        self.sidebar_status_label.pack(side="left", padx=(6, 0))

        # ── Main content area ────────────────────────────────────────────────
        main = tk.Frame(self.root, bg="#edf3f7")
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        # Header bar (white strip with title + refresh timestamp)
        hdr = tk.Frame(main, bg="#ffffff", padx=22, pady=14)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="Panel de control", fg="#0b2a3f", bg="#ffffff",
                 font=("Segoe UI Semibold", 15)).pack(side="left")
        tk.Label(
            hdr,
            text=f"Version: {APP_VERSION}",
            fg="#6b7f93",
            bg="#ffffff",
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(10, 0))
        self.connection_mode_badge = tk.Label(
            hdr,
            textvariable=self.connection_mode_var,
            fg="#0f4b47",
            bg="#d1fae5",
            font=("Segoe UI Semibold", 9),
            padx=8,
            pady=3,
        )
        self.connection_mode_badge.pack(side="left", padx=(12, 0))
        ttk.Button(
            hdr,
            text="Cambiar modo Docker",
            style="Ghost.TButton",
            command=self.change_connection_mode,
        ).pack(side="right", padx=(0, 12))
        tk.Label(hdr, textvariable=self.last_refresh_var, fg="#6b7f93", bg="#ffffff",
                 font=("Segoe UI", 9)).pack(side="right")

        # Thin separator under header
        tk.Frame(main, bg="#e2e8f0", height=1).grid(row=1, column=0, sticky="ew")

        # Notebook wrapper
        nb_wrap = ttk.Frame(main, padding=(16, 12))
        nb_wrap.grid(row=2, column=0, sticky="nsew")
        nb_wrap.columnconfigure(0, weight=1)
        nb_wrap.rowconfigure(0, weight=1)

        self.tabs = ttk.Notebook(nb_wrap)
        self.tabs.grid(row=0, column=0, sticky="nsew")

        container_tab = ttk.Frame(self.tabs, padding=10)
        volumes_tab  = ttk.Frame(self.tabs, padding=10)
        profiles_tab  = ttk.Frame(self.tabs, padding=10)
        networks_tab  = ttk.Frame(self.tabs, padding=10)
        history_tab   = ttk.Frame(self.tabs, padding=10)
        logs_tab      = ttk.Frame(self.tabs, padding=10)

        self.tabs.add(container_tab, text="  Contenedores  ")
        self.tabs.add(volumes_tab,   text="  Volumenes  ")
        self.tabs.add(profiles_tab,  text="  Perfiles  ")
        self.tabs.add(networks_tab,  text="  Redes  ")
        self.tabs.add(history_tab,   text="  Historial  ")
        self.tabs.add(logs_tab,      text="  Logs  ")

        self.container_tab_frame = container_tab
        self.volumes_tab_frame = volumes_tab
        self.profiles_tab_frame = profiles_tab
        self.networks_tab_frame = networks_tab
        self.logs_tab_frame = logs_tab

        self._build_containers_tab(container_tab)
        self._build_volumes_tab(volumes_tab)
        self._build_profiles_tab(profiles_tab)
        self._build_networks_tab(networks_tab)
        self._build_history_tab(history_tab)
        self._build_logs_tab(logs_tab)
        self.history_tab_frame = history_tab
        self.tabs.bind("<<NotebookTabChanged>>", self._on_history_tab_selected)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Configure>", self._schedule_layout_reflow, add="+")
        self.root.after(120, self._apply_responsive_layout)

    def _create_scrollable_surface(self, parent: ttk.Frame, padding: tuple[int, int] = (10, 10)) -> ttk.Frame:
        host = ttk.Frame(parent, style="Card.TFrame")
        host.pack(fill="both", expand=True)
        host.columnconfigure(0, weight=1)
        host.rowconfigure(0, weight=1)

        canvas = tk.Canvas(
            host,
            background="#edf3f7",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        canvas.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(host, orient="vertical", command=canvas.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(host, orient="horizontal", command=canvas.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        content = ttk.Frame(canvas, padding=padding)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def sync_scroll_region(_event: object = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content_width(event: tk.Event) -> None:
            required_width = content.winfo_reqwidth()
            canvas.itemconfigure(window_id, width=max(event.width, required_width))

        def _on_mouse_wheel(event: tk.Event) -> str:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        content.bind("<Configure>", sync_scroll_region)
        canvas.bind("<Configure>", fit_content_width)
        content.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mouse_wheel))
        content.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        self.root.after(50, sync_scroll_region)
        return content

    def open_containers_manager(self) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return

        window = self._open_or_focus_work_tab("container_admin", "Gestion contenedores")
        if window is None:
            messagebox.showerror("Interfaz", "No se pudo abrir la pestaña de gestión de contenedores.")
            return

        for child in window.winfo_children():
            child.destroy()

        outer = ttk.Frame(window, padding=4)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        self._add_work_tab_header(outer, "Gestión avanzada de contenedores", "container_admin")

        table_frame = ttk.Frame(outer)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=0)

        cols = ("name", "state", "image", "ports", "protection")
        self.container_admin_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.container_admin_tree.heading("name", text="Contenedor")
        self.container_admin_tree.heading("state", text="Estado")
        self.container_admin_tree.heading("image", text="Imagen")
        self.container_admin_tree.heading("ports", text="Puertos")
        self.container_admin_tree.heading("protection", text="Proteccion")
        self.container_admin_tree.column("name", width=200, anchor="w")
        self.container_admin_tree.column("state", width=120, anchor="center")
        self.container_admin_tree.column("image", width=280, anchor="w")
        self.container_admin_tree.column("ports", width=260, anchor="w")
        self.container_admin_tree.column("protection", width=320, anchor="w")
        self.container_admin_tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.container_admin_tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.container_admin_tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.container_admin_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        actions = ttk.Frame(outer)
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Refrescar", command=self._refresh_container_admin_table, style="Admin.TButton").pack(side="left")
        ttk.Button(actions, text="Renombrar", command=self._rename_container_admin, style="Admin.TButton").pack(side="left", padx=6)
        ttk.Button(actions, text="Borrar", command=self._delete_container_admin, style="Danger.TButton").pack(side="left", padx=6)
        ttk.Button(actions, text="Arrancar", command=lambda: self._toggle_container_admin("start"), style="Admin.TButton").pack(side="left", padx=6)
        ttk.Button(actions, text="Apagar", command=lambda: self._toggle_container_admin("stop"), style="Admin.TButton").pack(side="left", padx=6)

        self._refresh_container_admin_table()

    def _refresh_container_admin_table(self) -> None:
        if self.container_admin_tree is None or not self.container_admin_tree.winfo_exists():
            return

        for item in self.container_admin_tree.get_children():
            self.container_admin_tree.delete(item)

        code, out, err = self._run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}|{{.Image}}|{{.Ports}}|{{.Command}}"])
        if code != 0:
            messagebox.showwarning("Contenedores", err or "No se pudieron listar contenedores.")
            return

        if not out.strip():
            self.container_admin_tree.insert("", "end", values=("(sin contenedores)", "-", "-", "-", "-"))
            return

        for line in out.splitlines():
            parts = line.split("|", 4)
            if len(parts) < 5:
                continue
            name = parts[0].strip()
            status_raw = parts[1].strip()
            image = parts[2].strip()
            ports = parts[3].strip() or "-"
            command = parts[4].strip()
            if self._is_hidden_helper_container(name, image, command):
                continue
            state = "ARRANCADO" if status_raw.lower().startswith("up") else "APAGADO"
            protection = self._container_protection_text(name, image)
            tags: list[str] = []
            service_tag = self._container_service_tag(name, image)
            if service_tag:
                tags.append(service_tag)
            self.container_admin_tree.insert("", "end", values=(name, state, image, ports, protection), tags=tuple(tags))

    def _selected_container_admin(self) -> str | None:
        if self.container_admin_tree is None or not self.container_admin_tree.winfo_exists():
            return None
        selected = self.container_admin_tree.selection()
        if not selected:
            return None
        values = self.container_admin_tree.item(selected[0], "values")
        if not values:
            return None
        name = str(values[0]).strip()
        if not name or name == "(sin contenedores)":
            return None
        return name

    def _rename_container_admin(self) -> None:
        container = self._selected_container_admin()
        if not container:
            messagebox.showwarning("Contenedores", "Selecciona un contenedor para renombrar.")
            return

        new_name = simpledialog.askstring("Renombrar contenedor", f"Nuevo nombre para '{container}':", initialvalue=container)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name == container:
            messagebox.showwarning("Contenedores", "Nombre nuevo no válido.")
            return

        code, _, err = self._run(["docker", "rename", container, new_name])
        if code != 0:
            messagebox.showerror("Contenedores", err or "No se pudo renombrar el contenedor.")
            return

        self.log_event("CONTAINER", container, "OK", f"Renombrado a {new_name}")
        self.refresh_everything()
        self._refresh_container_admin_table()
        messagebox.showinfo("Contenedores", f"Contenedor renombrado: {container} -> {new_name}")

    def _delete_container_admin(self) -> None:
        container = self._selected_container_admin()
        if not container:
            messagebox.showwarning("Contenedores", "Selecciona un contenedor para borrar.")
            return

        matches = self._profiles_containing_container(container)
        if matches:
            scope_lines: list[str] = []
            if matches.get("privado"):
                scope_lines.append("Perfiles privados: " + ", ".join(matches["privado"]))
            if matches.get("remoto"):
                scope_lines.append("Perfiles remotos: " + ", ".join(matches["remoto"]))

            confirm_remove = messagebox.askyesno(
                "Contenedores",
                (
                    f"El contenedor '{container}' esta incluido en perfiles.\n\n"
                    + "\n".join(scope_lines)
                    + "\n\nQuieres quitarlo de esos perfiles antes de borrar el contenedor?"
                ),
            )
            if not confirm_remove:
                messagebox.showwarning(
                    "Contenedores",
                    f"No se puede borrar '{container}' sin quitarlo de los perfiles donde esta incluido.",
                )
                return

            removed_ok, remove_error = self._remove_container_from_profile_scopes(container, matches)
            if not removed_ok:
                messagebox.showerror("Contenedores", remove_error or "No se pudo quitar el contenedor de los perfiles.")
                return

            removed_scopes = ", ".join([k for k in ("privado", "remoto") if matches.get(k)])
            self.log_event("CONTAINER", container, "OK", f"Quitado de perfiles antes de borrar ({removed_scopes})")

        if not messagebox.askyesno("Contenedores", f"Eliminar contenedor '{container}'?\n\nSe forzará parada si está arrancado."):
            return

        code, out, err = self._run(["docker", "rm", "-f", container])
        if code != 0:
            details = err or out or f"Docker devolvio codigo {code} sin detalle."
            messagebox.showerror("Contenedores", f"No se pudo borrar el contenedor.\n\n{details}")
            return

        self.log_event("CONTAINER", container, "OK", "Eliminado desde gestor avanzado")
        self.refresh_everything()
        self.refresh_profiles_ui(force=True)
        self._refresh_container_admin_table()
        messagebox.showinfo("Contenedores", f"Contenedor eliminado: {container}")

    def _toggle_container_admin(self, mode: str) -> None:
        container = self._selected_container_admin()
        if not container:
            messagebox.showwarning("Contenedores", "Selecciona un contenedor.")
            return

        action = "start" if mode == "start" else "stop"
        code, _, err = self._run(["docker", action, container])
        if code != 0:
            messagebox.showerror("Contenedores", err or f"No se pudo {action} {container}.")
            return

        estado = "arrancado" if action == "start" else "apagado"
        self.log_event("CONTAINER", container, "OK", f"Contenedor {estado} desde gestor avanzado")
        self.refresh_everything()
        self._refresh_container_admin_table()
        messagebox.showinfo("Contenedores", f"Contenedor {estado}: {container}")

    def _build_containers_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        table_frame = ttk.Frame(parent)
        table_frame.grid(row=0, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=0)

        columns = ("name", "state", "health", "port", "protection")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=14, selectmode="extended")
        self.tree.heading("name", text="Contenedor")
        self.tree.heading("state", text="Estado")
        self.tree.heading("health", text="Salud")
        self.tree.heading("port", text="Puerto")
        self.tree.heading("protection", text="Proteccion")
        self.tree.column("name", width=340, anchor="w")
        self.tree.column("state", width=120, anchor="center")
        self.tree.column("health", width=120, anchor="center")
        self.tree.column("port", width=120, anchor="center")
        self.tree.column("protection", width=320, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("running",   foreground="#059669")
        self.tree.tag_configure("stopped",   foreground="#ef4444")
        self.tree.tag_configure("unhealthy", foreground="#d97706")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        action_row = ttk.Frame(parent)
        action_row.grid(row=1, column=0, sticky="ew", pady=(10, 4))

        ttk.Button(action_row, text="Refrescar", command=self.refresh_everything).pack(side="left", padx=(0, 6))
        self.container_action_btns = []
        for _lbl, _cmd in [
            ("Arrancar seleccionados", self.start_selected),
            ("Apagar seleccionados",   self.stop_selected),
            ("Arrancar todos",          self.start_all),
            ("Apagar todos",            self.stop_all),
        ]:
            _btn = ttk.Button(action_row, text=_lbl, command=_cmd)
            _btn.pack(side="left", padx=6)
            self.container_action_btns.append(_btn)

    def _build_profiles_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(3, weight=1)
        top.columnconfigure(4, weight=1)

        ttk.Label(top, text="Almacen:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        scope_combo = ttk.Combobox(
            top,
            textvariable=self.profile_scope_var,
            values=["privado", "remoto"],
            state="readonly",
            width=12,
        )
        scope_combo.current(0)
        scope_combo.grid(row=0, column=1, sticky="w")
        scope_combo.bind("<<ComboboxSelected>>", self.on_profile_scope_changed)

        ttk.Label(top, text="Nombre perfil:").grid(row=0, column=2, sticky="w", padx=(12, 6))
        ttk.Entry(top, textvariable=self.profile_name_var).grid(row=0, column=3, columnspan=2, sticky="ew")

        ttk.Button(top, text="Guardar/Actualizar", command=self.save_profile).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))
        ttk.Button(top, text="Quitar del perfil", command=self.remove_selected_from_profile).grid(row=1, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(top, text="Eliminar", command=self.delete_profile).grid(row=1, column=2, sticky="ew", padx=6, pady=(8, 0))
        self.copy_profile_btn = ttk.Button(top, text="Copiar a remoto", command=self.copy_selected_profile)
        self.copy_profile_btn.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(6, 0))
        self.profile_action_btns = []
        _btn_start = ttk.Button(top, text="Arrancar perfil", command=lambda: self.run_selected_profile("start"))
        _btn_start.grid(row=2, column=1, sticky="ew", padx=6, pady=(6, 0))
        self.profile_action_btns.append(_btn_start)
        _btn_stop = ttk.Button(top, text="Apagar perfil", command=lambda: self.run_selected_profile("stop"))
        _btn_stop.grid(row=2, column=2, sticky="ew", padx=6, pady=(6, 0))
        self.profile_action_btns.append(_btn_stop)

        body = ttk.Frame(parent)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        self.profiles_header_label = ttk.Label(body, text="Perfiles privados")
        self.profiles_header_label.grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="Contenedores del perfil").grid(row=0, column=1, sticky="w")

        self.profiles_listbox = tk.Listbox(
            body, exportselection=False,
            bg="#ffffff", fg="#0f172a", selectbackground="#dbeafe", selectforeground="#1e40af",
            relief="solid", borderwidth=1, highlightthickness=0, font=("Segoe UI", 10),
            activestyle="none",
        )
        self.profiles_listbox.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.profiles_listbox.bind("<<ListboxSelect>>", self.on_profile_selected)

        self.profile_containers_listbox = tk.Listbox(
            body, selectmode="extended", exportselection=False,
            bg="#ffffff", fg="#0f172a", selectbackground="#dbeafe", selectforeground="#1e40af",
            relief="solid", borderwidth=1, highlightthickness=0, font=("Segoe UI", 10),
            activestyle="none",
        )
        self.profile_containers_listbox.grid(row=1, column=1, sticky="nsew", padx=(6, 0))

        bottom = ttk.Frame(parent)
        bottom.grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Button(bottom, text="Refrescar perfiles", command=lambda: self.refresh_profiles_ui(force=True)).pack(side="left")
        ttk.Button(bottom, text="Limpiar seleccion", command=self.clear_profile_editor).pack(side="left", padx=6)
        self.profiles_loading_label = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.profiles_loading_label.pack(side="left", padx=(10, 0))

    def _build_networks_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(0, weight=1)

        ttk.Button(top, text="Refrescar networks", command=self.refresh_networks).pack(side="left")
        ttk.Label(top, text="Driver:").pack(side="left", padx=(14, 6))
        ttk.Combobox(
            top,
            textvariable=self.network_driver_var,
            values=["bridge", "overlay", "macvlan", "ipvlan"],
            state="readonly",
            width=10,
        ).pack(side="left")
        ttk.Button(top, text="Crear network", command=self.create_network).pack(side="left", padx=6)
        ttk.Button(top, text="Renombrar network", command=self.rename_network).pack(side="left", padx=6)
        ttk.Button(top, text="Eliminar network", command=self.delete_network).pack(side="left", padx=6)

        body = ttk.Frame(parent)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Networks").grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="Contenedores conectados").grid(row=0, column=1, sticky="w")

        self.networks_tree = ttk.Treeview(body, columns=("name", "driver", "count"), show="headings", height=12)
        self.networks_tree.heading("name", text="Network")
        self.networks_tree.heading("driver", text="Driver")
        self.networks_tree.heading("count", text="Contenedores")
        self.networks_tree.column("name", width=240, anchor="w")
        self.networks_tree.column("driver", width=110, anchor="center")
        self.networks_tree.column("count", width=110, anchor="center")
        self.networks_tree.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.networks_tree.bind("<<TreeviewSelect>>", self.on_network_selected)

        networks_y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.networks_tree.yview)
        networks_y_scroll.grid(row=1, column=0, sticky="nse", padx=(0, 6))
        networks_x_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.networks_tree.xview)
        networks_x_scroll.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(4, 0))
        self.networks_tree.configure(yscrollcommand=networks_y_scroll.set, xscrollcommand=networks_x_scroll.set)

        self.network_containers_listbox = tk.Listbox(
            body, exportselection=False,
            bg="#ffffff", fg="#0f172a", selectbackground="#dbeafe", selectforeground="#1e40af",
            relief="solid", borderwidth=1, highlightthickness=0, font=("Segoe UI", 10),
            activestyle="none",
        )
        self.network_containers_listbox.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        self.network_containers_listbox.bind("<Button-1>", lambda _e: "break")
        self.network_containers_listbox.bind("<B1-Motion>", lambda _e: "break")
        self.network_containers_listbox.bind("<ButtonRelease-1>", lambda _e: "break")
        self.network_containers_listbox.bind("<Key>", lambda _e: "break")

        action = ttk.Frame(parent)
        action.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        action.columnconfigure(1, weight=1)

        ttk.Label(action, text="Contenedor objetivo:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.network_container_combo = ttk.Combobox(
            action,
            textvariable=self.network_container_var,
            state="readonly",
            values=[],
        )
        self.network_container_combo.grid(row=0, column=1, sticky="ew")
        ttk.Button(action, text="Conectar", command=self.connect_container_to_network).grid(row=0, column=2, padx=6)
        ttk.Button(action, text="Desconectar", command=self.disconnect_container_from_network).grid(row=0, column=3)

        ttk.Label(action, text="Seleccion multiple:").grid(row=1, column=0, sticky="nw", padx=(0, 6), pady=(8, 0))
        self.network_targets_listbox = tk.Listbox(
            action,
            selectmode="extended",
            exportselection=False,
            height=5,
            bg="#ffffff",
            fg="#0f172a",
            selectbackground="#dbeafe",
            selectforeground="#1e40af",
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self.network_targets_listbox.grid(row=1, column=1, sticky="ew", pady=(8, 0))

    def _build_volumes_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(0, weight=1)

        ttk.Button(top, text="Refrescar volumes", command=self.refresh_volumes).pack(side="left")
        ttk.Label(top, text="Driver:").pack(side="left", padx=(14, 6))
        ttk.Combobox(
            top,
            textvariable=self.volume_driver_var,
            values=["local", "nfs", "tmpfs"],
            state="readonly",
            width=10,
        ).pack(side="left")
        ttk.Button(top, text="Crear volume", command=self.create_volume).pack(side="left", padx=6)
        ttk.Button(top, text="Inspeccionar", command=self.inspect_selected_volumes).pack(side="left", padx=6)
        ttk.Button(top, text="Clonar volume", command=self.clone_volume).pack(side="left", padx=6)
        ttk.Button(top, text="Vaciar volume", command=self.clear_volume_contents).pack(side="left", padx=6)
        ttk.Button(top, text="Eliminar volume", command=self.delete_selected_volumes).pack(side="left", padx=6)
        ttk.Button(top, text="Prune volumes", command=self.prune_volumes).pack(side="left", padx=6)

        body = ttk.Frame(parent)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Volumes").grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="Contenedores que usan el volume").grid(row=0, column=1, sticky="w")

        self.volumes_tree = ttk.Treeview(
            body,
            columns=("name", "driver", "scope", "inuse", "mountpoint"),
            show="headings",
            height=12,
            selectmode="extended",
        )
        self.volumes_tree.heading("name", text="Volume")
        self.volumes_tree.heading("driver", text="Driver")
        self.volumes_tree.heading("scope", text="Scope")
        self.volumes_tree.heading("inuse", text="Uso")
        self.volumes_tree.heading("mountpoint", text="Mountpoint")
        self.volumes_tree.column("name", width=220, anchor="w")
        self.volumes_tree.column("driver", width=110, anchor="center")
        self.volumes_tree.column("scope", width=100, anchor="center")
        self.volumes_tree.column("inuse", width=90, anchor="center")
        self.volumes_tree.column("mountpoint", width=330, anchor="w")
        self.volumes_tree.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.volumes_tree.bind("<<TreeviewSelect>>", self.on_volume_selected)

        volumes_y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.volumes_tree.yview)
        volumes_y_scroll.grid(row=1, column=0, sticky="nse", padx=(0, 6))
        volumes_x_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.volumes_tree.xview)
        volumes_x_scroll.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(4, 0))
        self.volumes_tree.configure(yscrollcommand=volumes_y_scroll.set, xscrollcommand=volumes_x_scroll.set)

        self.volume_containers_listbox = tk.Listbox(
            body,
            exportselection=False,
            bg="#ffffff",
            fg="#0f172a",
            selectbackground="#dbeafe",
            selectforeground="#1e40af",
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self.volume_containers_listbox.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        self.volume_containers_listbox.bind("<Button-1>", lambda _e: "break")
        self.volume_containers_listbox.bind("<B1-Motion>", lambda _e: "break")
        self.volume_containers_listbox.bind("<ButtonRelease-1>", lambda _e: "break")
        self.volume_containers_listbox.bind("<Key>", lambda _e: "break")

    def _build_history_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(3, weight=1)

        ttk.Label(top, text="Nivel:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        level_combo = ttk.Combobox(
            top,
            textvariable=self.history_level_var,
            values=["TODOS", "OK", "ERROR", "WARN", "INFO"],
            state="readonly",
            width=12,
        )
        level_combo.current(0)
        level_combo.grid(row=0, column=1, sticky="w")
        level_combo.bind("<<ComboboxSelected>>", self.apply_history_filter)

        ttk.Label(top, text="Buscar:").grid(row=0, column=2, sticky="w", padx=(12, 6))
        search = ttk.Entry(top, textvariable=self.history_search_var)
        search.grid(row=0, column=3, sticky="ew")
        search.bind("<KeyRelease>", self.apply_history_filter)

        ttk.Button(top, text="Refrescar", command=self.refresh_history).grid(row=0, column=4, padx=6)
        ttk.Button(top, text="Limpiar filtro", command=self.clear_history_filters).grid(row=0, column=5, padx=(0, 6))
        ttk.Button(top, text="Copiar visible", command=self.copy_visible_history).grid(row=0, column=6)

        body = ttk.Frame(parent)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.history_text = tk.Text(
            body,
            wrap="none",
            height=16,
            bg="#ffffff",
            fg="#1f2937",
            insertbackground="#1f2937",
            relief="flat",
            borderwidth=1,
            selectbackground="#bfdbfe",
            highlightthickness=0,
        )
        self.history_text.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.history_text.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.history_text.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.history_text.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.history_text.configure(xscrollcommand=x_scroll.set)

        self.history_text.configure(state="disabled")

    def _build_logs_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Contenedor:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.log_container_combo = ttk.Combobox(
            top,
            textvariable=self.log_container_var,
            state="readonly",
            values=[],
        )
        self.log_container_combo.grid(row=0, column=1, sticky="ew")

        ttk.Label(top, text="Lineas:").grid(row=0, column=2, sticky="w", padx=(12, 6))
        self.log_lines_spinbox = tk.Spinbox(top, from_=10, to=5000, increment=10, textvariable=self.log_lines_var, width=8)
        self.log_lines_spinbox.grid(row=0, column=3, sticky="w")
        self.log_lines_spinbox.configure(
            background="#ffffff",
            foreground="#1f2937",
            insertbackground="#1f2937",
            relief="solid",
            borderwidth=1,
        )

        ttk.Button(top, text="Ver logs", command=self.fetch_logs).grid(row=0, column=4, padx=6)
        ttk.Checkbutton(top, text="Seguir (-f)", variable=self.log_follow_var, command=self.on_follow_mode_toggled).grid(row=0, column=5, padx=6)
        ttk.Checkbutton(top, text="Auto-refresco", variable=self.log_auto_refresh_var, command=self.toggle_logs_auto_refresh).grid(row=0, column=6, padx=6)
        ttk.Button(top, text="Exportar txt", command=self.export_visible_logs).grid(row=0, column=7, padx=(6, 0))
        ttk.Button(top, text="Copiar visible", command=self.copy_visible_logs).grid(row=0, column=8, padx=(6, 0))

        body = ttk.Frame(parent)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.logs_text = tk.Text(
            body,
            wrap="none",
            height=16,
            bg="#ffffff",
            fg="#1f2937",
            insertbackground="#1f2937",
            relief="flat",
            borderwidth=1,
            selectbackground="#bfdbfe",
            highlightthickness=0,
        )
        self.logs_text.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.logs_text.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.logs_text.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.logs_text.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.logs_text.configure(xscrollcommand=x_scroll.set)

        self.logs_text.insert("1.0", "Selecciona un contenedor y pulsa 'Ver logs'.")
        self.logs_text.configure(state="disabled")

    def _run(self, args: list[str]) -> tuple[int, str, str]:
        if args and args[0].lower() == "docker" and self._should_use_docker_sdk():
            return self._run_docker_via_sdk(args)

        final_args = self._build_docker_command(args)
        process = subprocess.run(
            final_args,
            capture_output=True,
            text=True,
            cwd=self.tools_dir,
            shell=False,
            env=self._docker_process_env(),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return process.returncode, process.stdout.strip(), process.stderr.strip()

    def _docker_process_env(self, force_host: str | None = None) -> dict[str, str]:
        env = os.environ.copy()
        host = force_host
        if not host and self.docker_mode == "remote" and self.docker_host:
            host = self.docker_host
        if host:
            env["DOCKER_HOST"] = host
            env.pop("DOCKER_CONTEXT", None)
            # Evita errores de tipo CreateFile cuando quedan rutas TLS invalidas en variables globales.
            env.pop("DOCKER_TLS_VERIFY", None)
            env.pop("DOCKER_CERT_PATH", None)
            env.pop("DOCKER_TLS", None)
        return env

    def _detect_docker_cli(self) -> bool:
        try:
            process = subprocess.run(
                ["where", "docker"],
                capture_output=True,
                text=True,
                cwd=self.tools_dir,
                shell=False,
                env=self._docker_process_env(),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return process.returncode == 0
        except Exception:
            return False

    def _should_use_docker_sdk(self) -> bool:
        if self.docker_cli_available is None:
            self.docker_cli_available = self._detect_docker_cli()
        return not bool(self.docker_cli_available)

    def _get_docker_sdk_client(self, host_override: str | None = None, timeout_seconds: int | None = 5) -> object | None:
        if docker is None:
            return None

        is_short_timeout = timeout_seconds is not None and timeout_seconds <= 5
        now = time.time()
        if (
            host_override is None
            and is_short_timeout
            and self.docker_sdk_client is None
            and self._sdk_last_fail_at > 0
            and (now - self._sdk_last_fail_at) < self._sdk_retry_cooldown_sec
        ):
            return None

        if host_override is None and is_short_timeout and self.docker_sdk_client is not None:
            return self.docker_sdk_client

        base_url = host_override
        if base_url is None and self.docker_mode == "remote" and self.docker_host:
            base_url = self.docker_host

        try:
            if base_url:
                client = docker.DockerClient(base_url=base_url, timeout=timeout_seconds)
            else:
                client = docker.from_env(timeout=timeout_seconds)
            client.ping()
            if host_override is None and is_short_timeout:
                self.docker_sdk_client = client
                self._sdk_last_fail_at = 0.0
            return client
        except Exception:
            if host_override is None and is_short_timeout:
                self._sdk_last_fail_at = time.time()
            return None

    def _ports_mapping_text(self, container: object) -> str:
        try:
            ports = (container.attrs.get("NetworkSettings", {}) or {}).get("Ports", {}) or {}
            parts: list[str] = []
            for cport, bindings in ports.items():
                if not bindings:
                    continue
                for item in bindings:
                    host_ip = item.get("HostIp", "0.0.0.0")
                    host_port = item.get("HostPort", "")
                    parts.append(f"{host_ip}:{host_port}->{cport}")
            return ", ".join(parts)
        except Exception:
            return ""

    def _status_text(self, container: object) -> str:
        status = (getattr(container, "status", "") or "").lower()
        if status == "running":
            return "Up"
        if status == "created":
            return "Created"
        if status == "paused":
            return "Paused"
        if status == "restarting":
            return "Restarting"
        return "Exited"

    def _render_ps_format_line(self, container: object, template: str) -> str:
        image = ""
        command = ""
        try:
            tags = getattr(container.image, "tags", []) or []
            image = tags[0] if tags else (container.attrs.get("Config", {}) or {}).get("Image", "")
        except Exception:
            image = ""

        try:
            cfg = container.attrs.get("Config", {}) or {}
            cmd = cfg.get("Cmd")
            if isinstance(cmd, list):
                command = " ".join(str(x) for x in cmd)
            else:
                command = str(cmd or "")
        except Exception:
            command = ""

        name = getattr(container, "name", "")
        status = self._status_text(container)
        ports = self._ports_mapping_text(container)
        out = template
        out = out.replace("{{.Names}}", name)
        out = out.replace("{{.Status}}", status)
        out = out.replace("{{.Image}}", image)
        out = out.replace("{{.Ports}}", ports)
        out = out.replace("{{.Command}}", command)
        return out

    def _run_sdk_cp_helper_subprocess(self, host_override: str | None, src: str, dst: str) -> tuple[int, str, str]:
        direction = "from" if _looks_like_container_spec(src) else "to"
        # En modo compilado (PyInstaller), argv[1] debe ser --wpu-sdk-cp
        # para evitar que se abra una segunda instancia de la UI.
        helper_args = [sys.executable]
        if not getattr(sys, "frozen", False):
            helper_args.append(os.path.abspath(__file__))
        helper_args.extend([
            "--wpu-sdk-cp",
            direction,
            host_override or "",
            src,
            dst,
        ])
        process = subprocess.run(
            helper_args,
            capture_output=True,
            text=True,
            cwd=self.tools_dir,
            shell=False,
            env=self._docker_process_env(force_host=host_override),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return process.returncode, process.stdout.strip(), process.stderr.strip()

    def _run_docker_via_sdk(self, args: list[str]) -> tuple[int, str, str]:
        docker_args = args[1:]
        host_override: str | None = None
        if len(docker_args) >= 2 and docker_args[0] == "-H":
            host_override = docker_args[1]
            docker_args = docker_args[2:]
        if not docker_args:
            return 1, "", "Comando docker vacio"

        cmd = docker_args[0]
        rest = docker_args[1:]

        # Para operaciones largas (import/export/copia/exec/logs) evitar
        # timeout fijo de lectura, ya que depende del tamano de datos y rendimiento del host remoto.
        if cmd in {"cp", "exec", "run", "logs"}:
            try:
                client.api.timeout = None
            except Exception:
                pass

        op_timeout: int | None = 5
        if cmd in {"cp", "exec", "run", "logs"}:
            op_timeout = None
        elif cmd in {"start", "stop", "restart", "rm", "network", "volume"}:
            op_timeout = 30

        client = self._get_docker_sdk_client(host_override=host_override, timeout_seconds=op_timeout)
        if client is None:
            return 1, "", "Docker SDK no disponible. Instala paquete Python 'docker'."

        try:
            if cmd == "info":
                info = client.api.info()
                return 0, str(info.get("ServerVersion", "OK")), ""

            if cmd == "ps":
                all_flag = "-a" in rest or "-aq" in rest
                quiet = "-q" in rest or "-aq" in rest
                fmt = ""
                if "--format" in rest:
                    idx = rest.index("--format")
                    if idx + 1 < len(rest):
                        fmt = rest[idx + 1]
                containers = client.containers.list(all=all_flag)
                if quiet:
                    return 0, "\n".join(c.id for c in containers), ""
                if fmt:
                    lines = [self._render_ps_format_line(c, fmt) for c in containers]
                    return 0, "\n".join(lines), ""
                return 0, "\n".join(c.name for c in containers), ""

            if cmd in {"start", "stop", "restart"}:
                if not rest:
                    return 1, "", f"docker {cmd}: faltan contenedores"
                for cname in rest:
                    cont = client.containers.get(cname)
                    if cmd == "start":
                        cont.start()
                    elif cmd == "stop":
                        cont.stop(timeout=10)
                    else:
                        cont.restart(timeout=10)
                return 0, "", ""

            if cmd == "rename":
                if len(rest) != 2:
                    return 1, "", "docker rename: argumentos invalidos"
                cont = client.containers.get(rest[0])
                cont.rename(rest[1])
                return 0, "", ""

            if cmd == "rm":
                force = "-f" in rest
                names = [x for x in rest if x != "-f"]
                for cname in names:
                    cont = client.containers.get(cname)
                    cont.remove(force=force)
                return 0, "", ""

            if cmd == "network":
                if not rest:
                    return 1, "", "docker network: falta subcomando"
                sub = rest[0]
                sub_args = rest[1:]
                if sub == "ls":
                    fmt = ""
                    if "--format" in sub_args:
                        idx = sub_args.index("--format")
                        if idx + 1 < len(sub_args):
                            fmt = sub_args[idx + 1]
                    lines: list[str] = []
                    for net in client.networks.list():
                        name = net.name
                        driver = (net.attrs.get("Driver", "") if getattr(net, "attrs", None) else "")
                        if fmt:
                            line = fmt.replace("{{.Name}}", name).replace("{{.Driver}}", driver)
                        else:
                            line = f"{name}|{driver}"
                        lines.append(line)
                    return 0, "\n".join(lines), ""
                if sub == "create":
                    driver = "bridge"
                    name = ""
                    if "--driver" in sub_args:
                        idx = sub_args.index("--driver")
                        if idx + 1 < len(sub_args):
                            driver = sub_args[idx + 1]
                            rem = [x for i, x in enumerate(sub_args) if i not in {idx, idx + 1}]
                            name = rem[-1] if rem else ""
                    else:
                        name = sub_args[-1] if sub_args else ""
                    if not name:
                        return 1, "", "docker network create: falta nombre"
                    net = client.networks.create(name=name, driver=driver)
                    return 0, net.id, ""
                if sub == "rm":
                    for net_name in sub_args:
                        client.networks.get(net_name).remove()
                    return 0, "", ""
                if sub == "connect":
                    if len(sub_args) < 2:
                        return 1, "", "docker network connect: argumentos invalidos"
                    client.networks.get(sub_args[0]).connect(sub_args[1])
                    return 0, "", ""
                if sub == "disconnect":
                    if len(sub_args) < 2:
                        return 1, "", "docker network disconnect: argumentos invalidos"
                    client.networks.get(sub_args[0]).disconnect(sub_args[1])
                    return 0, "", ""
                return 1, "", f"Subcomando network no soportado: {sub}"

            if cmd == "volume":
                if not rest:
                    return 1, "", "docker volume: falta subcomando"
                sub = rest[0]
                sub_args = rest[1:]
                names = [x for x in sub_args if x != "-f"]
                if sub == "ls":
                    fmt = ""
                    if "--format" in sub_args:
                        idx = sub_args.index("--format")
                        if idx + 1 < len(sub_args):
                            fmt = sub_args[idx + 1]
                    lines: list[str] = []
                    for vol in client.volumes.list():
                        attrs = getattr(vol, "attrs", {}) or {}
                        name = getattr(vol, "name", "")
                        driver = str(attrs.get("Driver", ""))
                        scope = str(attrs.get("Scope", ""))
                        mountpoint = str(attrs.get("Mountpoint", ""))
                        if fmt:
                            line = fmt
                            line = line.replace("{{.Name}}", name)
                            line = line.replace("{{.Driver}}", driver)
                            line = line.replace("{{.Scope}}", scope)
                            line = line.replace("{{.Mountpoint}}", mountpoint)
                        else:
                            line = f"{name}|{driver}|{scope}|{mountpoint}"
                        lines.append(line)
                    return 0, "\n".join(lines), ""
                if sub == "create":
                    driver = "local"
                    if "--driver" in sub_args:
                        idx = sub_args.index("--driver")
                        if idx + 1 < len(sub_args):
                            driver = sub_args[idx + 1]
                            names = [x for i, x in enumerate(sub_args) if i not in {idx, idx + 1}]
                    out: list[str] = []
                    for name in names:
                        v = client.volumes.create(name=name, driver=driver)
                        out.append(v.name)
                    return 0, "\n".join(out), ""
                if sub == "rm":
                    for name in names:
                        client.volumes.get(name).remove(force=True)
                    return 0, "", ""
                if sub == "inspect":
                    payload: list[dict[str, object]] = []
                    for name in names:
                        payload.append(client.volumes.get(name).attrs)
                    return 0, json.dumps(payload, ensure_ascii=False, indent=2), ""
                if sub == "prune":
                    remove_all = "--all" in sub_args or "-a" in sub_args
                    if remove_all:
                        pruned = client.api.prune_volumes(filters={"all": True})
                    else:
                        pruned = client.volumes.prune()
                    return 0, json.dumps(pruned, ensure_ascii=False, indent=2), ""
                return 1, "", f"Subcomando volume no soportado: {sub}"

            if cmd == "inspect":
                if len(rest) >= 3 and rest[0] == "--format" and rest[1] == "{{.State.Running}}":
                    cont = client.containers.get(rest[2])
                    cont.reload()
                    running = (cont.attrs.get("State", {}) or {}).get("Running", False)
                    return 0, ("true" if running else "false"), ""
                if len(rest) >= 3 and rest[0] == "--format" and rest[1] == "{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}":
                    cont = client.containers.get(rest[2])
                    cont.reload()
                    nets = ((cont.attrs.get("NetworkSettings", {}) or {}).get("Networks", {}) or {}).keys()
                    return 0, " ".join(str(n) for n in nets), ""
                if len(rest) >= 3 and rest[0] == "--format" and rest[1] == "{{range .Mounts}}{{if eq .Type \"volume\"}}{{.Name}} {{end}}{{end}}":
                    cont = client.containers.get(rest[2])
                    cont.reload()
                    mounts = cont.attrs.get("Mounts", []) or []
                    names: list[str] = []
                    for mount in mounts:
                        if str(mount.get("Type", "")) == "volume":
                            name = str(mount.get("Name", "")).strip()
                            if name:
                                names.append(name)
                    return 0, " ".join(names), ""
                return 1, "", "docker inspect: formato no soportado"

            if cmd == "port":
                if not rest:
                    return 1, "", "docker port: falta contenedor"
                cont = client.containers.get(rest[0])
                ports = (cont.attrs.get("NetworkSettings", {}) or {}).get("Ports", {}) or {}
                if len(rest) >= 2:
                    requested = rest[1]
                    key = requested if "/" in requested else f"{requested}/tcp"
                    binds = ports.get(key) or []
                    lines = [f"{b.get('HostIp', '0.0.0.0')}:{b.get('HostPort', '')}" for b in binds]
                    return 0, "\n".join(lines), ""
                lines: list[str] = []
                for cport, binds in ports.items():
                    if not binds:
                        continue
                    for b in binds:
                        lines.append(f"{cport} -> {b.get('HostIp', '0.0.0.0')}:{b.get('HostPort', '')}")
                return 0, "\n".join(lines), ""

            if cmd == "exec":
                idx = 0
                user = None
                if len(rest) >= 3 and rest[0] == "-u":
                    user = rest[1]
                    idx = 2
                if idx >= len(rest):
                    return 1, "", "docker exec: falta contenedor"
                cont_name = rest[idx]
                exec_cmd = rest[idx + 1 :]
                if not exec_cmd:
                    return 1, "", "docker exec: falta comando"

                cont = client.containers.get(cont_name)
                if exec_cmd == ["env"]:
                    env_list = (cont.attrs.get("Config", {}) or {}).get("Env", []) or []
                    return 0, "\n".join(env_list), ""

                cmd_value: object
                if len(exec_cmd) == 1:
                    cmd_value = exec_cmd[0]
                else:
                    cmd_value = exec_cmd
                result = cont.exec_run(cmd=cmd_value, user=user, stdout=True, stderr=True)
                exit_code = int(result.exit_code)
                output = result.output.decode("utf-8", errors="replace") if isinstance(result.output, (bytes, bytearray)) else str(result.output)
                if exit_code == 0:
                    return 0, output.strip(), ""
                return exit_code, "", output.strip() or "Fallo en docker exec"

            if cmd == "cp":
                if len(rest) != 2:
                    return 1, "", "docker cp: argumentos invalidos"
                src, dst = rest
                if _looks_like_container_spec(src) or _looks_like_container_spec(dst):
                    return self._run_sdk_cp_helper_subprocess(host_override=host_override, src=src, dst=dst)
                return 1, "", "docker cp: direccion no soportada"

            if cmd == "logs":
                tail = 100
                follow = False
                i = 0
                while i < len(rest):
                    token = rest[i]
                    if token == "--tail" and i + 1 < len(rest):
                        tail = int(rest[i + 1])
                        i += 2
                        continue
                    if token == "-f":
                        follow = True
                        i += 1
                        continue
                    break
                if i >= len(rest):
                    return 1, "", "docker logs: falta contenedor"
                cont = client.containers.get(rest[i])
                if follow:
                    return 1, "", "docker logs -f no soportado en este modo"
                data = cont.logs(stdout=True, stderr=True, tail=tail)
                return 0, data.decode("utf-8", errors="replace").strip(), ""

            if cmd == "run":
                detach = False
                auto_remove = False
                name = None
                network = None
                user = None
                entrypoint = None
                environment: dict[str, str] = {}
                volumes: dict[str, dict[str, str]] = {}
                ports: dict[str, object] = {}

                i = 0
                while i < len(rest):
                    token = rest[i]
                    if token == "-d":
                        detach = True
                        i += 1
                        continue
                    if token == "--rm":
                        auto_remove = True
                        i += 1
                        continue
                    if token == "--name" and i + 1 < len(rest):
                        name = rest[i + 1]
                        i += 2
                        continue
                    if token == "--network" and i + 1 < len(rest):
                        network = rest[i + 1]
                        i += 2
                        continue
                    if token in {"-u", "--user"} and i + 1 < len(rest):
                        user = rest[i + 1]
                        i += 2
                        continue
                    if token == "--entrypoint" and i + 1 < len(rest):
                        entrypoint = rest[i + 1]
                        i += 2
                        continue
                    if token == "-e" and i + 1 < len(rest):
                        kv = rest[i + 1]
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            environment[k] = v
                        i += 2
                        continue
                    if token == "-v" and i + 1 < len(rest):
                        vm = rest[i + 1]
                        parts = vm.split(":", 2)
                        if len(parts) >= 2:
                            src, bind = parts[0], parts[1]
                            mode = parts[2] if len(parts) == 3 else "rw"
                            volumes[src] = {"bind": bind, "mode": mode}
                        i += 2
                        continue
                    if token == "-p" and i + 1 < len(rest):
                        pm = rest[i + 1]
                        if ":" in pm:
                            host, cont_port = pm.split(":", 1)
                            key = cont_port if "/" in cont_port else f"{cont_port}/tcp"
                            ports[key] = int(host)
                        i += 2
                        continue
                    break

                if i >= len(rest):
                    return 1, "", "docker run: falta imagen"
                image = rest[i]
                command = rest[i + 1 :] if (i + 1) < len(rest) else None
                if isinstance(command, list) and len(command) == 1:
                    command = command[0]

                result = client.containers.run(
                    image,
                    command=command,
                    detach=detach,
                    remove=auto_remove,
                    name=name,
                    network=network,
                    user=user,
                    entrypoint=entrypoint,
                    environment=environment or None,
                    volumes=volumes or None,
                    ports=ports or None,
                )
                if detach:
                    return 0, getattr(result, "id", ""), ""
                if isinstance(result, (bytes, bytearray)):
                    return 0, result.decode("utf-8", errors="replace").strip(), ""
                return 0, str(result), ""

            return 1, "", f"Comando docker no soportado por SDK: {cmd}"
        except NotFound as exc:
            return 1, "", str(exc)
        except APIError as exc:
            return 1, "", str(exc)
        except DockerException as exc:
            return 1, "", str(exc)
        except Exception as exc:
            return 1, "", str(exc)
        finally:
            self._schedule_helper_container_cleanup()

    def _build_docker_command(self, args: list[str]) -> list[str]:
        if not args:
            return args
        if args[0].lower() != "docker":
            return args
        if self.docker_mode != "remote" or not self.docker_host:
            return args
        return ["docker", "-H", self.docker_host, *args[1:]]

    def _prompt_startup_connection_mode(self) -> bool:
        self.discovered_lan_hosts = self._discover_lan_hosts()

        dialog = tk.Toplevel(self.root)
        dialog.title("Modo Docker")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        initial_mode = self.docker_mode if self.docker_mode in {"local", "remote"} else "local"
        current_host = self.docker_host
        if current_host.startswith("tcp://"):
            current_host = current_host[6:]
        elif current_host.startswith("http://"):
            current_host = current_host[7:]
        elif current_host.startswith("https://"):
            current_host = current_host[8:]

        mode_var = tk.StringVar(value=initial_mode)
        lan_default = ""
        if current_host and current_host in self.discovered_lan_hosts:
            lan_default = current_host
        elif self.discovered_lan_hosts:
            lan_default = self.discovered_lan_hosts[0]
        lan_var = tk.StringVar(value=lan_default)
        manual_var = tk.StringVar(value=current_host if initial_mode == "remote" else "")
        result = {"accepted": False}

        body = ttk.Frame(dialog, padding=14)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        ttk.Label(
            body,
            text="Selecciona como quieres conectar con Docker",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text="Local usa Docker Desktop en este equipo. Remoto permite host LAN o dominio/IP publico.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        mode_box = ttk.Frame(body)
        mode_box.grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(mode_box, text="Modo local", value="local", variable=mode_var).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(mode_box, text="Modo remoto", value="remote", variable=mode_var).grid(row=0, column=1, sticky="w", padx=(16, 0))

        remote_frame = ttk.LabelFrame(body, text="Destino remoto", padding=10)
        remote_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        remote_frame.columnconfigure(1, weight=1)

        ttk.Label(remote_frame, text="Host LAN detectado:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        lan_combo = ttk.Combobox(remote_frame, textvariable=lan_var, state="readonly", values=self.discovered_lan_hosts)
        lan_combo.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        ttk.Label(remote_frame, text="Dominio/IP manual:").grid(row=1, column=0, sticky="w", padx=(0, 8))
        manual_entry = ttk.Entry(remote_frame, textvariable=manual_var)
        manual_entry.grid(row=1, column=1, sticky="ew")

        ttk.Label(
            remote_frame,
            text="Formato: 192.168.1.50, 192.168.1.50:2375, mi-dominio.com o tcp://host:puerto",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, sticky="e", pady=(12, 0))

        def refresh_remote_controls(*_args: object) -> None:
            is_remote = mode_var.get() == "remote"
            lan_state = "readonly" if is_remote and self.discovered_lan_hosts else "disabled"
            lan_combo.configure(state=lan_state)
            manual_entry.configure(state="normal" if is_remote else "disabled")

        def accept_mode() -> None:
            selected_mode = mode_var.get()
            if selected_mode == "local":
                self.docker_mode = "local"
                self.docker_host = ""
                self.docker_sdk_client = None
                self._sdk_last_fail_at = 0.0
            else:
                raw_host = (manual_var.get() or lan_var.get()).strip()
                normalized = self._normalize_docker_host(raw_host)
                if not normalized:
                    messagebox.showwarning(
                        "Modo remoto",
                        "Indica un host remoto valido (LAN, dominio o IP publica).",
                        parent=dialog,
                    )
                    return
                self.docker_mode = "remote"
                self.docker_host = normalized
                self.docker_sdk_client = None
                self._sdk_last_fail_at = 0.0

            result["accepted"] = True
            dialog.destroy()

        def cancel_mode() -> None:
            dialog.destroy()

        ttk.Button(buttons, text="Cancelar", style="Ghost.TButton", command=cancel_mode).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Continuar", style="Accent.TButton", command=accept_mode).grid(row=0, column=1)

        mode_var.trace_add("write", refresh_remote_controls)
        refresh_remote_controls()

        dialog.protocol("WM_DELETE_WINDOW", cancel_mode)
        dialog.update_idletasks()
        self._center_window(dialog)
        self.root.wait_window(dialog)

        if not result["accepted"]:
            return False

        if self.docker_mode == "remote":
            self.status_var.set(f"Docker remoto: {self.docker_host}")
        else:
            self.status_var.set("Docker local: comprobando...")
        self._update_connection_mode_badge()
        return True

    def change_connection_mode(self) -> None:
        old_mode = self.docker_mode
        old_host = self.docker_host

        if not self._prompt_startup_connection_mode():
            return

        if old_mode == self.docker_mode and old_host == self.docker_host:
            return

        self.docker_sdk_client = None
        self._sdk_last_fail_at = 0.0

        if self.docker_mode == "remote":
            detail = f"Modo remoto activo: {self.docker_host}"
            self.log_event("DOCKER", "modo", "INFO", f"Cambio de modo a remoto ({self.docker_host})")
        else:
            detail = "Modo local activo"
            self.log_event("DOCKER", "modo", "INFO", "Cambio de modo a local")

        self.refresh_history()
        self.refresh_everything()
        messagebox.showinfo("Modo Docker", detail)

    def _normalize_docker_host(self, raw_host: str) -> str:
        host = raw_host.strip()
        if not host:
            return ""

        host = host.replace(" ", "")
        if host.startswith("http://"):
            host = f"tcp://{host[7:]}"
        elif host.startswith("https://"):
            host = f"tcp://{host[8:]}"

        if host.startswith("tcp://") or host.startswith("ssh://") or host.startswith("npipe://"):
            return host

        if ":" not in host.rsplit("]", 1)[-1]:
            detected_port = self._pick_remote_docker_port(host)
            host = f"{host}:{detected_port}"

        return f"tcp://{host}"

    def _is_tcp_open(self, host: str, port: int, timeout: float = 0.8) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _pick_remote_docker_port(self, host: str) -> int:
        # Prioriza 2375 por compatibilidad histórica; si no responde y 2376 sí, usa 2376.
        if self._is_tcp_open(host, 2375):
            return 2375
        if self._is_tcp_open(host, 2376):
            return 2376
        return 2375

    def _discover_lan_hosts(self) -> list[str]:
        candidates: set[str] = set()

        try:
            code, output, _ = self._run(["arp", "-a"])
            if code == 0 and output:
                for ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", output):
                    octets = [int(part) for part in ip.split(".")]
                    if len(octets) != 4:
                        continue
                    if any(part > 255 for part in octets):
                        continue
                    if ip.startswith("127.") or ip == "0.0.0.0" or ip == "255.255.255.255":
                        continue
                    candidates.add(ip)
        except Exception:
            pass

        return sorted(candidates)

    def _center_window(self, window: tk.Toplevel) -> None:
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f"+{x}+{y}")

    def _resource_candidates(self, relative_path: str) -> list[str]:
        candidates: list[str] = []

        # Desarrollo: recursos junto al codigo de la app.
        candidates.append(os.path.join(self.app_dir, relative_path))

        # Compatibilidad hacia atras: recursos en carpeta padre (utilidades).
        candidates.append(os.path.join(self.tools_dir, relative_path))

        # Ejecutable PyInstaller onefile: recursos extraidos en _MEIPASS
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(os.path.join(meipass, relative_path))

        # Ejecutable instalado junto a archivos auxiliares
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ""
        if exe_dir:
            candidates.append(os.path.join(exe_dir, relative_path))

        # Fallback adicional: cwd
        candidates.append(os.path.join(os.getcwd(), relative_path))
        return candidates

    def _migrate_legacy_state_files(self) -> None:
        legacy_to_current = [
            (os.path.join(self.tools_dir, "perfiles_contenedores.ini"), self.profiles_file),
            (os.path.join(self.tools_dir, "historial_gestor.log"), self.history_file),
        ]
        for legacy_path, current_path in legacy_to_current:
            try:
                if os.path.isfile(current_path) or not os.path.isfile(legacy_path):
                    continue
                os.replace(legacy_path, current_path)
            except Exception:
                # Si no se puede mover, mantenemos compatibilidad sin bloquear arranque.
                pass

    def _find_first_existing(self, relative_paths: list[str]) -> str:
        for rel in relative_paths:
            for candidate in self._resource_candidates(rel):
                if os.path.isfile(candidate):
                    return candidate
        return ""

    def _extract_host_port_from_docker_host(self, value: str) -> tuple[str, int] | None:
        host = (value or "").strip()
        if not host:
            return None

        if host.startswith("tcp://"):
            host = host[6:]
        elif host.startswith("http://"):
            host = host[7:]
        elif host.startswith("https://"):
            host = host[8:]
        elif host.startswith("ssh://"):
            return None

        if host.startswith("[") and "]" in host:
            # IPv6 con corchetes: [::1]:2375
            end = host.find("]")
            ip6 = host[1:end]
            rest = host[end + 1 :]
            if rest.startswith(":") and rest[1:].isdigit():
                return ip6, int(rest[1:])
            return ip6, 2375

        if ":" in host:
            h, p = host.rsplit(":", 1)
            if p.isdigit():
                return h, int(p)
        return host, 2375

    def _diagnose_remote_docker_host(self) -> str:
        if self.docker_mode != "remote" or not self.docker_host:
            return ""

        now = time.time()
        if (now - self._last_remote_diag_at) < 8.0 and self._last_remote_diag_text:
            return self._last_remote_diag_text

        parsed = self._extract_host_port_from_docker_host(self.docker_host)
        if parsed is None:
            diag = "Host remoto en modo SSH. Verifica que Docker acepte conexiones por SSH y que las credenciales sean validas."
            self._last_remote_diag_at = now
            self._last_remote_diag_text = diag
            return diag

        host, port = parsed
        try:
            resolved = socket.gethostbyname(host)
        except Exception:
            diag = f"No se pudo resolver DNS del host remoto '{host}'."
            self._last_remote_diag_at = now
            self._last_remote_diag_text = diag
            return diag

        try:
            with socket.create_connection((host, port), timeout=2):
                diag = (
                    f"Host remoto responde por TCP ({host}:{port}, {resolved}), "
                    "pero Docker rechazo la conexion. Revisa TLS/credenciales o que el daemon acepte API remota."
                )
        except Exception:
            if port == 2375 and self._is_tcp_open(host, 2376, timeout=1.2):
                diag = (
                    f"El puerto 2375 no responde en {host}, pero 2376 sí esta abierto. "
                    "Prueba conectando como tcp://HOST:2376 (normalmente requiere TLS)."
                )
                self._last_remote_diag_at = now
                self._last_remote_diag_text = diag
                return diag
            diag = (
                f"Host remoto resuelve ({host} -> {resolved}) pero el puerto {port} no responde. "
                "Abre firewall y expone Docker API en ese puerto."
            )

        self._last_remote_diag_at = now
        self._last_remote_diag_text = diag
        return diag

    def _docker_unavailable_message(self) -> str:
        if self._docker_check_in_progress:
            return "Comprobando conexion Docker... espera unos segundos y vuelve a intentarlo."

        details: list[str] = ["Docker no esta disponible."]
        if self.docker_mode == "remote" and self.docker_host:
            details.append(f"Modo remoto: {self.docker_host}")
            diag = self._diagnose_remote_docker_host()
            if diag:
                details.append(diag)
        else:
            if not self._detect_docker_cli() and docker is None:
                details.append("No se encontro docker.exe ni el paquete Python 'docker'.")
                details.append("Instala Docker Desktop o recompila la app incluyendo dependencia 'docker'.")

        if self.last_docker_error_detail:
            details.append(f"Error tecnico: {self.last_docker_error_detail}")
        return "\n\n".join(details)

    def _ensure_profiles_file(self) -> None:
        if os.path.isfile(self.profiles_file):
            return
        with open(self.profiles_file, "w", encoding="utf-8") as fh:
            fh.write("; Formato: nombre_perfil=contenedor1,contenedor2\n")
            fh.write("; Ejemplo: tienda=wordpress,mariadb\n")

    @staticmethod
    def _build_audit_actor() -> str:
        user = (os.environ.get("USERNAME") or os.environ.get("USER") or "desconocido").strip() or "desconocido"
        host = (os.environ.get("COMPUTERNAME") or socket.gethostname() or "equipo-desconocido").strip() or "equipo-desconocido"
        return f"{user}@{host}"

    def _ensure_remote_history_volume(self, client: object) -> None:
        try:
            client.volumes.get(self.remote_history_volume)  # type: ignore[union-attr]
        except Exception:
            client.volumes.create(name=self.remote_history_volume)  # type: ignore[union-attr]

    def _append_remote_history_line(self, line: str) -> None:
        if self.docker_mode != "remote":
            raise RuntimeError("El historial requiere modo remoto activo para registrar auditoria compartida.")

        client = self._get_docker_sdk_client(timeout_seconds=20)
        if client is None:
            raise RuntimeError("No se pudo conectar con Docker remoto para escribir historial.")

        self._ensure_remote_history_volume(client)
        cmd = [
            "sh",
            "-c",
            f"mkdir -p /data && touch {self.remote_history_path} && printf '%s\\n' \"$WPU_HISTORY_LINE\" >> {self.remote_history_path}",
        ]
        client.containers.run(
            "alpine",
            command=cmd,
            remove=True,
            labels={self._helper_label_key: self._helper_label_value, "wpu.role": "history-write"},
            environment={"WPU_HISTORY_LINE": line},
            volumes={self.remote_history_volume: {"bind": "/data", "mode": "rw"}},
        )

    def _read_remote_history_lines(self) -> list[str]:
        if self.docker_mode != "remote":
            raise RuntimeError("Activa modo remoto para consultar historial compartido.")

        client = self._get_docker_sdk_client(timeout_seconds=20)
        if client is None:
            raise RuntimeError("No se pudo conectar con Docker remoto para leer historial.")

        self._ensure_remote_history_volume(client)
        cmd = [
            "sh",
            "-c",
            f"mkdir -p /data && touch {self.remote_history_path} && cat {self.remote_history_path}",
        ]
        data = client.containers.run(
            "alpine",
            command=cmd,
            remove=True,
            labels={self._helper_label_key: self._helper_label_value, "wpu.role": "history-read"},
            volumes={self.remote_history_volume: {"bind": "/data", "mode": "rw"}},
        )
        raw = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
        return [line.rstrip("\n") for line in raw.splitlines()]

    def _on_history_tab_selected(self, _event: object = None) -> None:
        if self.tabs is None or self.history_tab_frame is None:
            return
        selected_id = self.tabs.select()
        if not selected_id:
            return
        selected_widget = self.tabs.nametowidget(selected_id)
        if selected_widget is self.history_tab_frame:
            self.refresh_history()

    def _is_history_tab_visible(self) -> bool:
        if self.tabs is None or self.history_tab_frame is None:
            return False
        selected_id = self.tabs.select()
        if not selected_id:
            return False
        return self.tabs.nametowidget(selected_id) is self.history_tab_frame

    def _refresh_history_if_visible(self) -> None:
        if self._is_history_tab_visible():
            self.refresh_history()

    def _schedule_helper_container_cleanup(self, force: bool = False) -> None:
        now = time.time()
        if self._helper_cleanup_in_progress:
            return
        if not force and (now - self._helper_cleanup_last_at) < 20.0:
            return

        self._helper_cleanup_in_progress = True
        self._helper_cleanup_last_at = now

        def worker() -> None:
            try:
                client = self._get_docker_sdk_client(timeout_seconds=10)
                if client is None:
                    return

                labeled = client.containers.list(  # type: ignore[union-attr]
                    all=True,
                    filters={"status": "exited", "label": f"{self._helper_label_key}={self._helper_label_value}"},
                )
                for cont in labeled:
                    try:
                        cont.remove(force=True)
                    except Exception:
                        pass

                # Cleanup de helpers antiguos sin labels (retrocompatibilidad).
                legacy = client.containers.list(  # type: ignore[union-attr]
                    all=True,
                    filters={"status": "exited", "ancestor": "alpine"},
                )
                for cont in legacy:
                    try:
                        cfg = getattr(cont, "attrs", {}).get("Config", {})
                        cmd = cfg.get("Cmd")
                        cmd_text = " ".join(str(x) for x in cmd) if isinstance(cmd, list) else str(cmd or "")
                        cmd_low = cmd_text.lower()
                        if "/data" in cmd_low and (
                            "profiles" in cmd_low
                            or "historial" in cmd_low
                            or "wpu_batch" in cmd_low
                            or "wpu_history_line" in cmd_low
                        ):
                            cont.remove(force=True)
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                self._helper_cleanup_in_progress = False

        threading.Thread(target=worker, daemon=True).start()

    def _render_history_message(self, message: str) -> None:
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", tk.END)
        self.history_text.insert("1.0", message)
        self.history_text.configure(state="disabled")

    def _history_refresh_worker(self) -> None:
        try:
            if self.docker_mode != "remote":
                raise RuntimeError("Activa modo remoto para consultar historial compartido.")
            client = self._get_docker_sdk_client(timeout_seconds=20)
            if client is None:
                raise RuntimeError("No se pudo conectar con Docker remoto para historial.")
            self._ensure_remote_history_volume(client)

            # Flush lines buffered since last refresh (batch write, one container run)
            with self._history_pending_lock:
                pending = list(self._history_pending_lines)
                self._history_pending_lines.clear()
            if pending:
                batch = "".join(ln + "\n" for ln in pending)
                client.containers.run(  # type: ignore[union-attr]
                    "alpine",
                    command=["sh", "-c", f"printf '%s' \"$WPU_BATCH\" >> {self.remote_history_path}"],
                    remove=True,
                    labels={self._helper_label_key: self._helper_label_value, "wpu.role": "history-batch-write"},
                    environment={"WPU_BATCH": batch},
                    volumes={self.remote_history_volume: {"bind": "/data", "mode": "rw"}},
                )

            # Read the full log
            data = client.containers.run(  # type: ignore[union-attr]
                "alpine",
                command=["sh", "-c", f"cat {self.remote_history_path} 2>/dev/null || true"],
                remove=True,
                labels={self._helper_label_key: self._helper_label_value, "wpu.role": "history-full-read"},
                volumes={self.remote_history_volume: {"bind": "/data", "mode": "rw"}},
            )
            raw = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
            lines = [ln.rstrip("\n") for ln in raw.splitlines()]
            self._history_refresh_queue.put((True, lines))
        except Exception as exc:
            self._history_refresh_queue.put((False, str(exc)))

    def _poll_history_refresh_queue(self) -> None:
        try:
            ok, payload = self._history_refresh_queue.get_nowait()
        except queue.Empty:
            self._history_refresh_job_id = self.root.after(100, self._poll_history_refresh_queue)
            return

        self._history_refresh_in_progress = False
        self._history_refresh_job_id = None

        if ok:
            self.history_lines = list(payload) if isinstance(payload, list) else []
            self.apply_history_filter()
        else:
            self.history_lines = []
            detail = str(payload)
            self._render_history_message(
                "Historial remoto no disponible.\n\n"
                "Activa modo remoto y valida acceso al daemon Docker para auditoria compartida.\n\n"
                f"Detalle: {detail}"
            )

        if self._history_refresh_requested:
            self._history_refresh_requested = False
            self.refresh_history()

    def log_event(self, accion: str, objetivo: str, estado: str, detalle: str) -> None:
        stamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        actor = self.audit_actor
        line = f"[{stamp}] [{estado}] {accion} | {objetivo} | usuario={actor} | {detalle}"
        with self._history_pending_lock:
            self._history_pending_lines.append(line)

    def docker_ready(self) -> bool:
        now = time.time()
        stale = (now - self._docker_last_checked_at) > 6.0

        if stale and not self._docker_check_in_progress:
            self._start_async_docker_check()

        return self._docker_last_ready

    def _start_async_docker_check(self) -> None:
        if self._docker_check_in_progress:
            return

        self._docker_check_in_progress = True
        # Evita parpadeo en UI: si ya sabemos que Docker esta disponible,
        # el re-check periodico ocurre en segundo plano sin cambiar el texto.
        if not self._docker_last_ready:
            self.status_var.set("Docker: comprobando...")

        worker = threading.Thread(target=self._docker_ready_probe_worker, daemon=True)
        worker.start()

        if self._docker_check_job_id is None:
            self._docker_check_job_id = self.root.after(100, self._poll_docker_check_queue)

    def _docker_ready_probe_worker(self) -> None:
        result = self._probe_docker_ready_blocking()
        self._docker_check_queue.put(result)

    def _poll_docker_check_queue(self) -> None:
        was_ready = self._docker_last_ready
        try:
            ready, status_text, detail = self._docker_check_queue.get_nowait()
        except queue.Empty:
            self._docker_check_job_id = self.root.after(100, self._poll_docker_check_queue)
            return

        self._docker_last_ready = ready
        self._docker_last_checked_at = time.time()
        self._docker_check_in_progress = False
        self._docker_check_job_id = None
        self.last_docker_error_detail = detail

        if self.status_var.get() != status_text:
            self.status_var.set(status_text)
        if (not ready) and detail:
            self.log_event("DOCKER", self.docker_host or "local", "ERROR", detail)

        if ready:
            self.refresh_containers(show_errors=False, full_repaint=False)
            if not was_ready:
                # Al recuperar conexion, refrescamos tambien vistas dependientes de Docker.
                self.refresh_volumes()
                self.refresh_networks()
                self.refresh_profiles_ui()
        else:
            self._stop_container_loading_spinner()

    def _probe_docker_ready_blocking(self) -> tuple[bool, str, str]:
        self.docker_cli_available = self._detect_docker_cli()

        if not self.docker_cli_available:
            code, _, err = self._run(["docker", "info"])
            if code == 0:
                if self.docker_mode == "remote":
                    return True, f"Docker remoto: disponible ({self.docker_host})", ""
                return True, "Docker local: disponible (SDK)", ""
            detail = (err or "Sin respuesta de Docker SDK").strip()
            if self.docker_mode == "remote":
                diag = self._diagnose_remote_docker_host()
                status = f"Docker remoto: no disponible ({diag})" if diag else "Docker remoto: no disponible"
            else:
                status = "Docker: no disponible"
            return False, status, detail

        if self.docker_mode == "remote":
            code, _, err = self._run(["docker", "info"])
            if code == 0:
                return True, f"Docker remoto: disponible ({self.docker_host})", ""
            detail = (err or "Fallo de conexion con host remoto").strip()
            diag = self._diagnose_remote_docker_host()
            status = f"Docker remoto: no disponible ({diag})" if diag else "Docker remoto: no disponible"
            return False, status, detail

        code, _, _ = self._run(["docker", "info"])
        if code == 0:
            self.docker_autostart_attempted = False
            return True, "Docker: disponible", ""

        if not self.docker_autostart_attempted:
            self.docker_autostart_attempted = True
            started = self._start_docker_desktop()
            if started and self._wait_for_docker_ready(timeout_seconds=90):
                return True, "Docker: disponible", ""

        return False, "Docker: no disponible", "Docker local no responde a 'docker info'."

    def _start_docker_desktop(self) -> bool:
        candidates = [
            os.path.join(os.environ.get("ProgramFiles", ""), "Docker", "Docker", "Docker Desktop.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Docker", "Docker", "Docker Desktop.exe"),
            os.path.join(os.environ.get("LocalAppData", ""), "Docker", "Docker", "Docker Desktop.exe"),
        ]

        for exe_path in candidates:
            if not exe_path or not os.path.isfile(exe_path):
                continue
            try:
                subprocess.Popen([exe_path], cwd=self.tools_dir, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
                return True
            except Exception:
                continue
        return False

    def _wait_for_docker_ready(self, timeout_seconds: int = 90) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            code, _, _ = self._run(["docker", "info"])
            if code == 0:
                return True
            time.sleep(2)
        return False

    def _start_status_spinner(self, base_text: str) -> None:
        self._stop_status_spinner()
        self.spinner_base_text = base_text
        self.spinner_index = 0
        self._animate_status_spinner()

    def _animate_status_spinner(self) -> None:
        frames = ["|", "/", "-", "\\"]
        frame = frames[self.spinner_index % len(frames)]
        self.status_var.set(f"{self.spinner_base_text}... {frame}")
        self.spinner_index += 1
        self.spinner_job_id = self.root.after(120, self._animate_status_spinner)

    def _stop_status_spinner(self) -> None:
        if self.spinner_job_id is not None:
            self.root.after_cancel(self.spinner_job_id)
            self.spinner_job_id = None

    def _selected_tab_widget(self) -> object | None:
        if self.tabs is None:
            return None
        selected_id = self.tabs.select()
        if not selected_id:
            return None
        try:
            return self.tabs.nametowidget(selected_id)
        except Exception:
            return None

    def refresh_everything(self, auto: bool = False) -> None:
        if auto:
            self.refresh_containers(show_errors=False, full_repaint=False)
            self.refresh_logs_targets()
            self._refresh_history_if_visible()

            now = time.time()
            selected = self._selected_tab_widget()
            if (now - self._last_auto_heavy_refresh_at) >= self._auto_heavy_refresh_interval_sec:
                if selected is self.profiles_tab_frame:
                    self.refresh_profiles_ui()
                elif selected is self.networks_tab_frame:
                    self.refresh_networks()
                elif selected is self.volumes_tab_frame:
                    self.refresh_volumes()
                self._last_auto_heavy_refresh_at = now

            self._schedule_auto_refresh()
            return

        self.refresh_containers(show_errors=False, full_repaint=True)
        self.refresh_volumes()
        self.refresh_profiles_ui()
        self.refresh_networks()
        self._refresh_history_if_visible()
        self.refresh_logs_targets()
        self._last_auto_heavy_refresh_at = time.time()
        self._schedule_auto_refresh()

    def _schedule_auto_refresh(self) -> None:
        if self.refresh_job_id is not None:
            self.root.after_cancel(self.refresh_job_id)
        self.refresh_job_id = self.root.after(7000, lambda: self.refresh_everything(auto=True))

    def get_all_container_names(self) -> list[str]:
        code, out, _ = self._run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Image}}|{{.Command}}"])
        if code != 0 or not out:
            self.container_image_cache = {}
            return []
        names: list[str] = []
        image_cache: dict[str, str] = {}
        for line in out.splitlines():
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            name = parts[0].strip()
            image = parts[1].strip()
            command = parts[2].strip()
            if not name:
                continue
            if self._is_hidden_helper_container(name, image, command):
                continue
            names.append(name)
            image_cache[name] = image
        self.container_image_cache = image_cache
        return names

    @staticmethod
    def _is_hidden_helper_container(name: str, image: str, command: str) -> bool:
        _ = name
        image_l = image.strip().lower()
        if not image_l.startswith("alpine"):
            return False

        cmd_l = command.lower()
        data_markers = (
            "/data",
            "profiles.json",
            "historial_gestor.log",
            "wpu_batch",
            "wpu_history_line",
        )
        if any(marker in cmd_l for marker in data_markers):
            return True

        # Helper temporal para escritura de perfiles remotos
        if "sleep 20" in cmd_l:
            return True

        return False

    def _collect_profile_container_names(self) -> set[str]:
        names: set[str] = set()
        for profiles_map in (self.profiles_data, self.private_profiles_data, self.remote_profiles_data):
            if not isinstance(profiles_map, dict):
                continue
            for containers in profiles_map.values():
                if not isinstance(containers, list):
                    continue
                for item in containers:
                    name = str(item).strip()
                    if name:
                        names.add(name)
        return names

    def _profiles_containing_container(self, container_name: str) -> dict[str, list[str]]:
        container = container_name.strip()
        if not container:
            return {}

        scopes: dict[str, dict[str, list[str]]] = {}

        private_profiles = self.private_profiles_data
        try:
            private_profiles = self.read_private_profiles()
            self.private_profiles_data = private_profiles
        except Exception:
            pass
        scopes["privado"] = private_profiles if isinstance(private_profiles, dict) else {}

        if self.docker_mode == "remote":
            remote_profiles = self.remote_profiles_data
            try:
                remote_profiles = self.read_remote_profiles()
                self.remote_profiles_data = remote_profiles
            except Exception:
                pass
            scopes["remoto"] = remote_profiles if isinstance(remote_profiles, dict) else {}
        elif isinstance(self.remote_profiles_data, dict) and self.remote_profiles_data:
            scopes["remoto"] = self.remote_profiles_data

        matches: dict[str, list[str]] = {}
        for scope_name, profile_map in scopes.items():
            found_profiles: list[str] = []
            for profile_name, containers in profile_map.items():
                if not isinstance(containers, list):
                    continue
                normalized = [str(item).strip() for item in containers if str(item).strip()]
                if container in normalized:
                    found_profiles.append(str(profile_name))
            if found_profiles:
                matches[scope_name] = sorted(found_profiles, key=str.lower)
        return matches

    def _remove_container_from_profile_scopes(self, container_name: str, matches: dict[str, list[str]]) -> tuple[bool, str]:
        container = container_name.strip()
        if not container:
            return False, "Nombre de contenedor vacio."

        for scope_name in ("privado", "remoto"):
            profile_names = matches.get(scope_name, [])
            if not profile_names:
                continue
            try:
                profiles = self._read_profiles_for_scope(scope_name)
            except Exception as exc:
                return False, f"No se pudieron cargar perfiles {scope_name}: {exc}"

            changed = False
            for profile_name in profile_names:
                current = profiles.get(profile_name, [])
                if not isinstance(current, list):
                    continue
                updated = [item for item in current if str(item).strip() != container]
                if len(updated) != len(current):
                    profiles[profile_name] = updated
                    changed = True

            if changed:
                try:
                    self._write_profiles_for_scope(scope_name, profiles)
                except Exception as exc:
                    return False, f"No se pudieron guardar perfiles {scope_name}: {exc}"

        current_scope = self._current_profiles_scope()
        try:
            self.profiles_data = self._read_profiles_for_scope(current_scope)
        except Exception:
            pass
        return True, ""

    @staticmethod
    def _container_service_label(name: str, image: str = "") -> str | None:
        token = f"{name} {image}".lower()
        name_l = name.lower()

        if "phpmyadmin" in token:
            return "Contenedor de phpMyAdmin"

        db_pattern = r"(^|[_\-.])(db|mariadb|mysql)([_\-.]|$)"
        if re.search(db_pattern, name_l) or "mariadb" in token or "mysql" in token:
            return "Contenedor de DB"

        if "wordpress" in token:
            return "Contenedor de WordPress"

        return None

    def _container_protection_text(self, name: str, image: str = "") -> str:
        reasons: list[str] = []
        service_label = self._container_service_label(name, image)
        if service_label:
            reasons.append(service_label)

        log_target = self.log_container_var.get().strip()
        if (not service_label) and log_target and name == log_target:
            reasons.append("Contenedor de logs")

        profiled = self._collect_profile_container_names()
        if name in profiled:
            reasons.append("Incluido en perfiles")

        if not reasons:
            return "-"

        unique_reasons = list(dict.fromkeys(reasons))
        return f"{'; '.join(unique_reasons)}"

    def _container_service_tag(self, name: str, image: str = "") -> str | None:
        service_label = self._container_service_label(name, image)
        if service_label == "Contenedor de WordPress":
            return "svc_wordpress"
        if service_label == "Contenedor de DB":
            return "svc_db"
        if service_label == "Contenedor de phpMyAdmin":
            return "svc_phpmyadmin"

        log_target = self.log_container_var.get().strip()
        if log_target and name == log_target:
            return "svc_logs"
        return None

    def parse_container_rows(self, text: str) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []
        for line in text.splitlines():
            parts = line.split("|", 2)
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            status_raw = parts[1].strip()
            ports = parts[2].strip() if len(parts) == 3 else ""

            state = "ARRANCADO" if status_raw.lower().startswith("up") else "APAGADO"
            health = "Sin healthcheck"
            s = status_raw.lower()
            if "unhealthy" in s:
                health = "\u26a0 Unhealthy"
            elif "healthy" in s:
                health = "\u2714 Healthy"
            elif "starting" in s:
                health = "\u21bb Starting"

            port = self.extract_port(ports) if state == "ARRANCADO" else "-"
            rows.append((name, state, health, port))
        return rows

    @staticmethod
    def extract_port(ports: str) -> str:
        if not ports:
            return "-"

        first = ports.split(",")[0].strip()
        if "->" in first:
            left = first.split("->", 1)[0]
            match = re.search(r":(\d+)$", left)
            if match:
                return match.group(1)
            only = re.search(r"(\d+)", left)
            if only:
                return only.group(1)

        plain = re.search(r"(\d+)", first)
        return plain.group(1) if plain else "-"

    def refresh_containers(self, show_errors: bool = True, full_repaint: bool = True) -> None:
        # Guardar los nombres seleccionados para restaurarlos tras el refresco.
        previously_selected: set[str] = set()
        for item_id in self.tree.selection():
            vals = self.tree.item(item_id, "values")
            if vals:
                previously_selected.add(str(vals[0]))

        if full_repaint:
            # En refresco manual mostramos estado de carga y repintamos toda la tabla.
            self._start_container_loading_spinner()
            self.root.update_idletasks()
        else:
            # En refresco automatico no vaciamos la tabla para evitar parpadeo.
            self._stop_container_loading_spinner()

        if not self.docker_ready():
            self.last_refresh_var.set("Ultima actualizacion: Docker no disponible")
            if full_repaint:
                self.container_cache = []
                self.container_image_cache = {}
            if self._docker_check_in_progress and full_repaint:
                self._start_container_loading_spinner()
            elif full_repaint:
                self._stop_container_loading_spinner()
            return

        code, out, err = self._run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}|{{.Ports}}|{{.Image}}|{{.Command}}"])
        if code != 0:
            self.last_refresh_var.set("Ultima actualizacion: error al listar contenedores")
            if err and show_errors:
                messagebox.showwarning("Docker", f"No se pudo leer contenedores.\n\n{err}")
            if full_repaint:
                self.container_cache = []
                self.container_image_cache = {}
                self._stop_container_loading_spinner()
            return

        rows: list[tuple[str, str, str, str, str]] = []
        for line in out.splitlines():
            parts = line.split("|", 4)
            if len(parts) < 5:
                continue
            name = parts[0].strip()
            status_raw = parts[1].strip()
            ports = parts[2].strip()
            image = parts[3].strip()
            command = parts[4].strip()
            if self._is_hidden_helper_container(name, image, command):
                continue

            state = "ARRANCADO" if status_raw.lower().startswith("up") else "APAGADO"
            health = "Sin healthcheck"
            s = status_raw.lower()
            if "unhealthy" in s:
                health = "\u26a0 Unhealthy"
            elif "healthy" in s:
                health = "\u2714 Healthy"
            elif "starting" in s:
                health = "\u21bb Starting"

            port = self.extract_port(ports) if state == "ARRANCADO" else "-"
            rows.append((name, state, health, port, image))

        self.container_cache = [row[0] for row in rows]
        self.container_image_cache = {row[0]: row[4] for row in rows}
        self._stop_container_loading_spinner()

        display_rows: list[tuple[str, tuple[str, str, str, str, str], tuple[str, ...]]] = []
        for row in rows:
            state_val = row[1]
            health_val = row[2]
            if state_val == "ARRANCADO":
                tag = "unhealthy" if "Unhealthy" in health_val else "running"
            else:
                tag = "stopped"
            protection = self._container_protection_text(row[0], row[4])
            tags: list[str] = [tag]
            service_tag = self._container_service_tag(row[0], row[4])
            if service_tag:
                tags.append(service_tag)
            display_rows.append((row[0], (row[0], row[1], row[2], row[3], protection), tuple(tags)))

        if full_repaint:
            for item_id in self.tree.get_children():
                self.tree.delete(item_id)

            if not display_rows:
                self.tree.insert("", "end", values=("(sin contenedores)", "-", "-", "-", "-"))
            else:
                for name, values, tags in display_rows:
                    iid = self.tree.insert("", "end", values=values, tags=tags)
                    if name in previously_selected:
                        self.tree.selection_add(iid)
            self.last_refresh_var.set("Ultima actualizacion: correcta")
            return

        # Refresco automatico: actualizar filas en sitio para evitar desaparecer/reaparecer.
        placeholder_ids: list[str] = []
        existing_by_name: dict[str, str] = {}
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id, "values")
            if not values:
                continue
            current_name = str(values[0]).strip()
            if current_name == "(sin contenedores)":
                placeholder_ids.append(item_id)
                continue
            if current_name:
                existing_by_name[current_name] = item_id

        desired_names = {name for name, _values, _tags in display_rows}

        for old_name, old_item_id in list(existing_by_name.items()):
            if old_name not in desired_names:
                self.tree.delete(old_item_id)
                existing_by_name.pop(old_name, None)

        if not display_rows:
            for item_id in self.tree.get_children():
                self.tree.delete(item_id)
            self.tree.insert("", "end", values=("(sin contenedores)", "-", "-", "-", "-"))
            self.last_refresh_var.set("Ultima actualizacion: correcta")
            return

        for item_id in placeholder_ids:
            if self.tree.exists(item_id):
                self.tree.delete(item_id)

        for index, (name, values, tags) in enumerate(display_rows):
            item_id = existing_by_name.get(name)
            if item_id and self.tree.exists(item_id):
                self.tree.item(item_id, values=values, tags=tags)
            else:
                item_id = self.tree.insert("", "end", values=values, tags=tags)
                existing_by_name[name] = item_id
            self.tree.move(item_id, "", index)
            if name in previously_selected:
                self.tree.selection_add(item_id)

        self.last_refresh_var.set("Ultima actualizacion: correcta")

    def selected_containers(self) -> list[str]:
        selection = self.tree.selection()
        if not selection:
            return []

        names: list[str] = []
        for item_id in selection:
            values = self.tree.item(item_id, "values")
            if not values:
                continue
            name = str(values[0])
            if name and name != "(sin contenedores)" and name not in names:
                names.append(name)
        return names

    def run_docker_action(
        self,
        args: list[str],
        success_msg: str,
        target_names: list[str] | None = None,
    ) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return

        # Localizar filas del Treeview que se van a ver afectadas
        spinner_items: list[str] = []
        if target_names:
            name_set = set(target_names)
            for iid in self.tree.get_children():
                vals = self.tree.item(iid, "values")
                if vals and str(vals[0]) in name_set:
                    spinner_items.append(iid)

        self._set_container_action_btns_state("disabled")
        self._start_container_spinner(spinner_items)

        result_q: queue.Queue[tuple[str, str]] = queue.Queue()

        def worker() -> None:
            objetivo = " ".join(args[2:]) if len(args) > 2 else "global"
            code, _, err = self._run(args)
            if code == 0:
                result_q.put(("ok", objetivo))
            else:
                result_q.put(("error", err or "Operacion fallida"))

        threading.Thread(target=worker, daemon=True).start()

        def poll() -> None:
            try:
                kind, payload = result_q.get_nowait()
            except queue.Empty:
                self.root.after(200, poll)
                return

            self._stop_container_spinner()
            self._set_container_action_btns_state("normal")

            if kind == "ok":
                self.log_event("DOCKER", payload, "OK", " ".join(args))
                self.refresh_everything()
                messagebox.showinfo("Docker", success_msg)
            else:
                self.log_event("DOCKER", "global", "ERROR", payload)
                self.refresh_everything()
                messagebox.showerror("Docker", payload)

        self.root.after(200, poll)

    def _set_container_action_btns_state(self, state: str) -> None:
        for btn in self.container_action_btns:
            try:
                btn.configure(state=state)
            except tk.TclError:
                pass

    def _start_container_spinner(self, item_ids: list[str]) -> None:
        self._stop_container_spinner()
        self._container_spinner_items = item_ids
        self._container_spinner_frame = 0
        if item_ids:
            self._animate_container_spinner()

    def _animate_container_spinner(self) -> None:
        frames = ["\u29d7", "\u29d6", "\u29d5", "\u29d4"]
        text = frames[self._container_spinner_frame % len(frames)] + " Procesando"
        for iid in self._container_spinner_items:
            try:
                self.tree.set(iid, "state", text)
            except tk.TclError:
                pass
        self._container_spinner_frame += 1
        self._container_spinner_job = self.root.after(250, self._animate_container_spinner)

    def _stop_container_spinner(self) -> None:
        if self._container_spinner_job is not None:
            self.root.after_cancel(self._container_spinner_job)
            self._container_spinner_job = None
        self._container_spinner_items = []

    def _start_container_loading_spinner(self) -> None:
        if not hasattr(self, "tree"):
            return
        if self._container_loading_job is not None:
            return

        self._container_loading_frame = 0
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree.insert("", "end", iid="__loading__", values=("Cargando contenedores...", "-", "-", "-", "-"))
        self._animate_container_loading_spinner()

    def _animate_container_loading_spinner(self) -> None:
        if not hasattr(self, "tree"):
            return

        frames = ["|", "/", "-", "\\"]
        frame = frames[self._container_loading_frame % len(frames)]
        if self.tree.exists("__loading__"):
            self.tree.item("__loading__", values=(f"Cargando contenedores... {frame}", "-", "-", "-", "-"))
        self._container_loading_frame += 1
        self._container_loading_job = self.root.after(140, self._animate_container_loading_spinner)

    def _stop_container_loading_spinner(self) -> None:
        if self._container_loading_job is not None:
            self.root.after_cancel(self._container_loading_job)
            self._container_loading_job = None
        if hasattr(self, "tree") and self.tree.exists("__loading__"):
            self.tree.delete("__loading__")

    # ── Profile spinner helpers ────────────────────────────────────────────

    def _start_profile_spinner(self, profile_name: str) -> None:
        self._stop_profile_spinner()
        self._profile_spinner_name = profile_name
        self._profile_spinner_frame2 = 0
        self._animate_profile_spinner()

    def _animate_profile_spinner(self) -> None:
        frames = ["⧗", "⧖", "⧕", "⧔"]
        text = frames[self._profile_spinner_frame2 % len(frames)] + " Procesando..."
        for i in range(self.profiles_listbox.size()):
            entry = self.profiles_listbox.get(i)
            if entry == self._profile_spinner_name or entry.endswith(" Procesando..."):
                self.profiles_listbox.delete(i)
                self.profiles_listbox.insert(i, text)
                self.profiles_listbox.itemconfig(i, fg="#f59e0b")
                self.profiles_listbox.selection_set(i)
                break
        self._profile_spinner_frame2 += 1
        self._profile_spinner_job = self.root.after(250, self._animate_profile_spinner)

    def _stop_profile_spinner(self) -> None:
        if self._profile_spinner_job is not None:
            self.root.after_cancel(self._profile_spinner_job)
            self._profile_spinner_job = None

    def start_selected(self) -> None:
        names = self.selected_containers()
        if not names:
            messagebox.showwarning("Seleccion", "Selecciona al menos un contenedor.")
            return
        self.run_docker_action(["docker", "start"] + names, f"Contenedores arrancados: {', '.join(names)}", target_names=names)

    def stop_selected(self) -> None:
        names = self.selected_containers()
        if not names:
            messagebox.showwarning("Seleccion", "Selecciona al menos un contenedor.")
            return
        self.run_docker_action(["docker", "stop"] + names, f"Contenedores apagados: {', '.join(names)}", target_names=names)

    def start_all(self) -> None:
        code, out, _ = self._run(["docker", "ps", "-aq"])
        if code != 0 or not out:
            messagebox.showwarning("Docker", "No hay contenedores para arrancar.")
            return
        self.run_docker_action(["docker", "start"] + out.splitlines(), "Contenedores arrancados.", target_names=self.container_cache[:])

    def stop_all(self) -> None:
        code, out, _ = self._run(["docker", "ps", "-q"])
        if code != 0 or not out:
            messagebox.showwarning("Docker", "No hay contenedores en ejecucion para apagar.")
            return
        self.run_docker_action(["docker", "stop"] + out.splitlines(), "Contenedores apagados.", target_names=self.container_cache[:])

    def _read_legacy_ini_profiles(self) -> dict[str, list[str]]:
        self._ensure_profiles_file()
        profiles: dict[str, list[str]] = {}
        with open(self.profiles_file, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith(";") or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                name = key.strip()
                containers = [item.strip() for item in value.split(",") if item.strip()]
                if name:
                    profiles[name] = containers
        return profiles

    def _default_profiles_payload(self) -> dict[str, object]:
        return {
            "version": 1,
            "updated_at": "",
            "updated_by": "",
            "profiles": {},
        }

    def _sanitize_profiles_mapping(self, data: object) -> dict[str, list[str]]:
        if not isinstance(data, dict):
            return {}
        result: dict[str, list[str]] = {}
        for key, value in data.items():
            name = str(key).strip()
            if not name:
                continue
            if isinstance(value, list):
                containers = [str(item).strip() for item in value if str(item).strip()]
            else:
                containers = []
            result[name] = containers
        return result

    def _ensure_private_profiles_file(self) -> None:
        os.makedirs(self.private_profiles_dir, exist_ok=True)
        if os.path.isfile(self.private_profiles_file):
            return

        payload = self._default_profiles_payload()
        legacy = self._read_legacy_ini_profiles()
        if legacy:
            payload["profiles"] = legacy
        with open(self.private_profiles_file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=True, indent=2)

    def read_private_profiles(self) -> dict[str, list[str]]:
        self._ensure_private_profiles_file()
        try:
            with open(self.private_profiles_file, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception:
            payload = self._default_profiles_payload()
        return self._sanitize_profiles_mapping(payload.get("profiles", {}))

    def write_private_profiles(self, profiles: dict[str, list[str]]) -> None:
        self._ensure_private_profiles_file()
        payload = self._default_profiles_payload()
        payload["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        payload["updated_by"] = os.environ.get("COMPUTERNAME", "desconocido")
        payload["profiles"] = dict(sorted(profiles.items(), key=lambda item: item[0].lower()))
        with open(self.private_profiles_file, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=True, indent=2)

    def _ensure_remote_profiles_volume(self, client: object | None = None) -> None:
        if client is None:
            client = self._get_docker_sdk_client(timeout_seconds=20)
        if client is None:
            raise RuntimeError("No se pudo conectar con Docker para perfiles remotos.")
        try:
            client.volumes.get(self.remote_profiles_volume)
        except Exception:
            client.volumes.create(name=self.remote_profiles_volume)

    def read_remote_profiles(self) -> dict[str, list[str]]:
        if self.docker_mode != "remote":
            return {}

        # Ruta de lectura alineada con el comando CLI validado en terminal.
        # Esto evita discrepancias entre SDK y docker CLI en algunos daemons remotos.
        code_v, _out_v, err_v = self._run(["docker", "volume", "create", self.remote_profiles_volume])
        if code_v != 0:
            raise RuntimeError(err_v or "No se pudo asegurar el volumen remoto de perfiles.")

        default_payload = json.dumps(self._default_profiles_payload(), ensure_ascii=True)
        script = (
            "mkdir -p /data; "
            f"if [ ! -f {self.remote_profiles_path} ]; then "
            "printf '%s' \"$WPU_DEFAULT\" > "
            f"{self.remote_profiles_path}; "
            "fi; "
            f"cat {self.remote_profiles_path}"
        )
        code, out, err = self._run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                f"WPU_DEFAULT={default_payload}",
                "-v",
                f"{self.remote_profiles_volume}:/data",
                "alpine",
                "sh",
                "-c",
                script,
            ]
        )
        if code != 0:
            raise RuntimeError(err or "No se pudo leer profiles.json remoto.")

        raw = out.strip()
        if not raw:
            raw = default_payload
        raw = raw.lstrip("\ufeff")
        try:
            payload = json.loads(raw)
        except Exception:
            # Si el JSON remoto esta dañado, se reconstruye la estructura minima
            # para que la UI vuelva a cargar y se pueda guardar de nuevo.
            payload = self._default_profiles_payload()
            try:
                self.write_remote_profiles(self._sanitize_profiles_mapping(payload.get("profiles", {})))
            except Exception:
                pass
        return self._sanitize_profiles_mapping(payload.get("profiles", {}))

    def write_remote_profiles(self, profiles: dict[str, list[str]]) -> None:
        if self.docker_mode != "remote":
            raise RuntimeError("Los perfiles remotos solo estan disponibles en modo remoto.")

        client = self._get_docker_sdk_client(timeout_seconds=20)
        if client is None:
            raise RuntimeError("No se pudo conectar con Docker remoto.")

        self._ensure_remote_profiles_volume(client)

        payload = self._default_profiles_payload()
        payload["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        payload["updated_by"] = os.environ.get("COMPUTERNAME", "desconocido")
        payload["profiles"] = dict(sorted(profiles.items(), key=lambda item: item[0].lower()))
        raw = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")

        helper = client.containers.create(
            "alpine",
            command=["sh", "-c", "sleep 20"],
            labels={self._helper_label_key: self._helper_label_value, "wpu.role": "profiles-write"},
            volumes={self.remote_profiles_volume: {"bind": "/data", "mode": "rw"}},
        )
        try:
            helper.start()
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                info = tarfile.TarInfo(name="profiles.json")
                info.size = len(raw)
                tar.addfile(info, io.BytesIO(raw))
            buf.seek(0)
            ok = helper.put_archive("/data", buf.read())
            if not ok:
                raise RuntimeError("No se pudo guardar profiles.json en el volumen remoto.")
        finally:
            try:
                helper.remove(force=True)
            except Exception:
                pass

    def _current_profiles_scope(self) -> str:
        return self.profile_scope_var.get().strip().lower() or "privado"

    def _current_profiles_label(self) -> str:
        return "Perfiles remotos" if self._current_profiles_scope() == "remoto" else "Perfiles privados"

    def _target_profiles_scope(self) -> str:
        return "privado" if self._current_profiles_scope() == "remoto" else "remoto"

    def _target_profiles_label(self) -> str:
        return "privado" if self._target_profiles_scope() == "privado" else "remoto"

    def _profile_container_display_name(self, container_name: str, in_selected_profile: bool) -> str:
        if in_selected_profile:
            return f"{container_name} (En el perfil seleccionado)"
        return container_name

    def _profile_container_actual_name(self, displayed_name: str) -> str:
        suffix = " (En el perfil seleccionado)"
        if displayed_name.endswith(suffix):
            return displayed_name[:-len(suffix)]
        return displayed_name

    def _render_profile_containers(self, selected_profile_name: str | None = None) -> None:
        selected_containers = set(self.profiles_data.get(selected_profile_name, [])) if selected_profile_name else set()
        self.profile_containers_listbox.delete(0, tk.END)
        for cname in self.container_cache:
            image_ref = self.container_image_cache.get(cname, "").strip().lower()
            if image_ref.startswith("alpine"):
                continue
            self.profile_containers_listbox.insert(
                tk.END,
                self._profile_container_display_name(cname, cname in selected_containers),
            )

        self.profile_containers_listbox.selection_clear(0, tk.END)
        if not selected_profile_name:
            return

        for idx in range(self.profile_containers_listbox.size()):
            item = self._profile_container_actual_name(self.profile_containers_listbox.get(idx))
            if item in selected_containers:
                self.profile_containers_listbox.selection_set(idx)

    def _read_profiles_for_scope(self, scope: str) -> dict[str, list[str]]:
        if scope == "remoto":
            self.remote_profiles_data = self.read_remote_profiles()
            return self.remote_profiles_data
        self.private_profiles_data = self.read_private_profiles()
        return self.private_profiles_data

    def _write_profiles_for_scope(self, scope: str, profiles: dict[str, list[str]]) -> None:
        if scope == "remoto":
            self.remote_profiles_data = profiles
            self.write_remote_profiles(profiles)
            return
        self.private_profiles_data = profiles
        self.write_private_profiles(profiles)

    def _select_profile_in_ui(self, profile_name: str) -> None:
        for idx in range(self.profiles_listbox.size()):
            if self.profiles_listbox.get(idx) == profile_name:
                self.profiles_listbox.selection_clear(0, tk.END)
                self.profiles_listbox.selection_set(idx)
                self.profiles_listbox.see(idx)
                self.profile_name_var.set(profile_name)
                self._render_profile_containers(profile_name)
                return

    def _load_profiles_for_current_scope(self) -> dict[str, list[str]]:
        return self._read_profiles_for_scope(self._current_profiles_scope())

    def _write_profiles_for_current_scope(self, profiles: dict[str, list[str]]) -> None:
        self._write_profiles_for_scope(self._current_profiles_scope(), profiles)

    def on_profile_scope_changed(self, _event: object | None = None) -> None:
        self.clear_profile_editor()
        self.refresh_profiles_ui(force=True)

    def _profiles_load_worker(self, scope: str) -> None:
        try:
            profiles = self._read_profiles_for_scope(scope)
            self._profiles_load_queue.put((scope, True, profiles))
        except Exception as exc:
            self._profiles_load_queue.put((scope, False, str(exc)))

    def _cancel_profiles_load_guard(self) -> None:
        if self._profiles_load_guard_job_id is not None:
            self.root.after_cancel(self._profiles_load_guard_job_id)
            self._profiles_load_guard_job_id = None

    def _clear_profiles_load_queue(self) -> None:
        while True:
            try:
                self._profiles_load_queue.get_nowait()
            except queue.Empty:
                break

    def _fail_profiles_loading(self, message: str) -> None:
        self._profiles_loading = False
        self._profiles_loading_scope = None
        self._profiles_load_started_at = 0.0
        self._profiles_load_job_id = None
        self._cancel_profiles_load_guard()
        self._profiles_remote_backoff_until = time.time() + self._profiles_remote_retry_cooldown_sec
        self._set_profiles_loading_ui(False)
        self.profiles_listbox.delete(0, tk.END)
        self.profiles_listbox.insert(tk.END, message)
        self.profiles_loading_label.configure(text="Pulsa 'Refrescar perfiles' para reintentar")
        self._refresh_profile_containers_cache()

    def _profiles_load_guard_timeout(self) -> None:
        self._profiles_load_guard_job_id = None
        if not self._profiles_loading:
            return
        self._fail_profiles_loading("No se pudo cargar perfiles remotos (timeout).")

    def _set_profiles_loading_ui(self, is_loading: bool) -> None:
        if is_loading:
            self.profiles_loading_label.configure(text="Cargando perfiles...")
            self.profiles_listbox.configure(state="normal")
            self.profiles_listbox.delete(0, tk.END)
            self.profiles_listbox.insert(tk.END, "Cargando perfiles...")
            self.profiles_listbox.configure(state="disabled")
            return

        self.profiles_loading_label.configure(text="")
        self.profiles_listbox.configure(state="normal")

    def _refresh_profile_containers_cache(self) -> None:
        # Los contenedores deben mostrarse siempre en el editor de perfiles.
        if not self.container_cache and self.docker_ready():
            self.container_cache = self.get_all_container_names()

        selected = self.profiles_listbox.curselection()
        selected_name: str | None = None
        if selected:
            selected_name = self.profiles_listbox.get(selected[0])
        self._render_profile_containers(selected_name)

    def _poll_profiles_load_queue(self) -> None:
        try:
            scope, ok, payload = self._profiles_load_queue.get_nowait()
        except queue.Empty:
            # Evita estado de "Cargando perfiles..." infinito si el worker remoto queda bloqueado.
            if self._profiles_loading and self._profiles_load_started_at > 0:
                elapsed = time.time() - self._profiles_load_started_at
                if elapsed >= self._profiles_load_timeout_sec:
                    self._fail_profiles_loading("No se pudo cargar perfiles remotos (timeout).")
                    return
            self._profiles_load_job_id = self.root.after(100, self._poll_profiles_load_queue)
            return

        # Ignorar respuestas obsoletas de cargas anteriores.
        if self._profiles_loading_scope and scope != self._profiles_loading_scope:
            self._profiles_load_job_id = self.root.after(20, self._poll_profiles_load_queue)
            return

        try:
            self._profiles_loading = False
            self._profiles_loading_scope = None
            self._profiles_load_job_id = None
            self._profiles_load_started_at = 0.0
            self._cancel_profiles_load_guard()

            if scope != self._current_profiles_scope():
                self._set_profiles_loading_ui(False)
                if self._profiles_load_requested:
                    self._profiles_load_requested = False
                    self.refresh_profiles_ui(force=True)
                return

            if ok:
                self.profiles_data = payload if isinstance(payload, dict) else {}
                self._profiles_remote_backoff_until = 0.0
                if scope == "remoto":
                    self.profiles_loading_label.configure(text=f"Perfiles remotos cargados: {len(self.profiles_data)}")
            else:
                self.profiles_data = {}
                self._profiles_remote_backoff_until = time.time() + self._profiles_remote_retry_cooldown_sec
                if scope == "remoto":
                    self.last_docker_error_detail = str(payload)
                    self.profiles_loading_label.configure(text="Error remoto. Pulsa 'Refrescar perfiles' para reintentar")

            pending = self._profiles_pending_name
            self._profiles_pending_name = None

            prev_selected: str | None = pending
            if prev_selected is None:
                cur = self.profiles_listbox.curselection()
                if cur:
                    idx = int(cur[0])
                    if 0 <= idx < self.profiles_listbox.size():
                        prev_selected = self._profile_spinner_name if self._profile_spinner_job else self.profiles_listbox.get(idx)

            self.profiles_listbox.configure(state="normal")
            self.profiles_listbox.delete(0, tk.END)
            restore_idx: int | None = None
            for i, name in enumerate(sorted(self.profiles_data.keys(), key=str.lower)):
                self.profiles_listbox.insert(tk.END, name)
                if name == prev_selected:
                    restore_idx = i

            if restore_idx is not None:
                self.profiles_listbox.selection_set(restore_idx)
                self.profiles_listbox.see(restore_idx)
                restored_name = self.profiles_listbox.get(restore_idx)
                self._render_profile_containers(restored_name)
                self.profile_name_var.set(restored_name)
            else:
                self._render_profile_containers()

            # Quitar estado de carga solo cuando la UI final ya esta renderizada.
            self._set_profiles_loading_ui(False)

            if self._profiles_load_requested:
                self._profiles_load_requested = False
                self.refresh_profiles_ui(force=True)
        except Exception as exc:
            self.last_docker_error_detail = f"Error UI perfiles: {exc}"
            self._fail_profiles_loading("No se pudieron pintar perfiles remotos.")

    def refresh_profiles_ui(self, force: bool = False) -> None:
        self.profiles_header_label.configure(text=self._current_profiles_label())
        self.copy_profile_btn.configure(text=f"Copiar a {self._target_profiles_label()}")

        # Mantener visible lista de contenedores aunque perfiles siga cargando.
        self._refresh_profile_containers_cache()

        scope = self._current_profiles_scope()

        if scope == "privado":
            # Carga local inmediata para evitar spinner eterno en almacenamiento privado.
            self._profiles_loading = False
            self._profiles_loading_scope = None
            self._profiles_load_requested = False
            self._profiles_load_started_at = 0.0
            self._profiles_remote_backoff_until = 0.0
            self._set_profiles_loading_ui(False)
            try:
                self.profiles_data = self._read_profiles_for_scope(scope)
            except Exception as exc:
                self.profiles_data = {}
                self.profiles_listbox.delete(0, tk.END)
                self.profiles_listbox.insert(tk.END, f"No se pudieron cargar perfiles privados: {exc}")
                self._refresh_profile_containers_cache()
                return

            self.profiles_listbox.delete(0, tk.END)
            for name in sorted(self.profiles_data.keys(), key=str.lower):
                self.profiles_listbox.insert(tk.END, name)

            self._refresh_profile_containers_cache()
            return

        if (not force) and time.time() < self._profiles_remote_backoff_until:
            self._set_profiles_loading_ui(False)
            self.profiles_listbox.delete(0, tk.END)
            self.profiles_listbox.insert(tk.END, "Reintento remoto en pausa")
            self.profiles_loading_label.configure(text="Pulsa 'Refrescar perfiles' para reintentar")
            return

        # Para almacenamiento remoto intentamos leer siempre; docker_ready puede
        # estar temporalmente desfasado y bloquear una lectura valida.

        if self._profiles_loading:
            if force:
                self._profiles_load_requested = True
            # Si por cualquier motivo se perdio el polling, lo reenganchamos.
            if self._profiles_load_job_id is None:
                self._profiles_load_job_id = self.root.after(100, self._poll_profiles_load_queue)
            if self._profiles_load_guard_job_id is None:
                self._profiles_load_guard_job_id = self.root.after(
                    int((self._profiles_load_timeout_sec + 2) * 1000),
                    self._profiles_load_guard_timeout,
                )
            return

        # Always async so users see loading state in both stores (initial load and scope changes).
        self._cancel_profiles_load_guard()
        self._clear_profiles_load_queue()
        self._set_profiles_loading_ui(True)
        self._profiles_loading = True
        self._profiles_loading_scope = scope
        self._profiles_load_started_at = time.time()
        threading.Thread(target=self._profiles_load_worker, args=(scope,), daemon=True).start()
        if self._profiles_load_job_id is None:
            self._profiles_load_job_id = self.root.after(100, self._poll_profiles_load_queue)
        self._profiles_load_guard_job_id = self.root.after(
            int((self._profiles_load_timeout_sec + 2) * 1000),
            self._profiles_load_guard_timeout,
        )

    def on_profile_selected(self, _event: object) -> None:
        selected = self.profiles_listbox.curselection()
        if not selected:
            return
        name = self.profiles_listbox.get(selected[0])
        self.profile_name_var.set(name)
        self._render_profile_containers(name)

    def clear_profile_editor(self) -> None:
        self.profile_name_var.set("")
        self.profiles_listbox.selection_clear(0, tk.END)
        self._render_profile_containers()

    def save_profile(self) -> None:
        name = self.profile_name_var.get().strip()
        if not name or " " in name:
            messagebox.showwarning("Perfiles", "El nombre del perfil no puede estar vacio ni tener espacios.")
            return

        if self._current_profiles_scope() == "remoto" and self.docker_mode != "remote":
            messagebox.showwarning("Perfiles", "Cambia a modo remoto para guardar perfiles remotos.")
            return

        selected_indexes = self.profile_containers_listbox.curselection()
        if not selected_indexes:
            messagebox.showwarning("Perfiles", "Selecciona al menos un contenedor para el perfil.")
            return

        containers = [self._profile_container_actual_name(self.profile_containers_listbox.get(i)) for i in selected_indexes]
        self.profiles_data[name] = containers
        self._write_profiles_for_current_scope(self.profiles_data)
        scope_name = self._current_profiles_scope().upper()
        self.log_event(f"PERFIL-{scope_name}", name, "OK", f"Guardado/actualizado: {','.join(containers)}")
        self.refresh_profiles_ui(force=True)
        self._select_profile_in_ui(name)
        self.refresh_history()
        messagebox.showinfo("Perfiles", f"Perfil guardado: {name}")

    def remove_selected_from_profile(self) -> None:
        if self._current_profiles_scope() == "remoto" and self.docker_mode != "remote":
            messagebox.showwarning("Perfiles", "Cambia a modo remoto para editar perfiles remotos.")
            return

        selected_profile = self.profiles_listbox.curselection()
        if not selected_profile:
            messagebox.showwarning("Perfiles", "Selecciona un perfil.")
            return

        profile_name = self.profiles_listbox.get(selected_profile[0])
        selected_indexes = self.profile_containers_listbox.curselection()
        if not selected_indexes:
            messagebox.showwarning("Perfiles", "Selecciona uno o varios contenedores para quitar del perfil.")
            return

        to_remove = {self._profile_container_actual_name(self.profile_containers_listbox.get(i)) for i in selected_indexes}
        current = list(self.profiles_data.get(profile_name, []))
        updated = [c for c in current if c not in to_remove]

        if len(updated) == len(current):
            messagebox.showwarning("Perfiles", "Los contenedores seleccionados no pertenecen al perfil.")
            return

        self.profiles_data[profile_name] = updated
        self._write_profiles_for_current_scope(self.profiles_data)
        self.profile_name_var.set(profile_name)
        scope_name = self._current_profiles_scope().upper()
        self.log_event(f"PERFIL-{scope_name}", profile_name, "OK", f"Contenedores quitados: {','.join(sorted(to_remove))}")
        self.refresh_profiles_ui(force=True)
        self._select_profile_in_ui(profile_name)
        self.refresh_history()
        messagebox.showinfo("Perfiles", f"Perfil actualizado: {profile_name}")

    def copy_selected_profile(self) -> None:
        selected = self.profiles_listbox.curselection()
        if not selected:
            messagebox.showwarning("Perfiles", "Selecciona un perfil para copiar.")
            return

        source_scope = self._current_profiles_scope()
        target_scope = self._target_profiles_scope()
        profile_name = self.profiles_listbox.get(selected[0])

        if target_scope == "remoto" and self.docker_mode != "remote":
            messagebox.showwarning("Perfiles", "Cambia a modo remoto para copiar perfiles al almacen remoto.")
            return

        try:
            target_profiles = self._read_profiles_for_scope(target_scope)
        except Exception as exc:
            messagebox.showerror("Perfiles", f"No se pudo cargar el almacen {target_scope}: {exc}")
            return

        if profile_name in target_profiles and not messagebox.askyesno(
            "Perfiles",
            f"El perfil '{profile_name}' ya existe en {target_scope}. Quieres sobrescribirlo?",
        ):
            return

        target_profiles[profile_name] = list(self.profiles_data.get(profile_name, []))
        try:
            self._write_profiles_for_scope(target_scope, target_profiles)
        except Exception as exc:
            messagebox.showerror("Perfiles", f"No se pudo copiar el perfil a {target_scope}: {exc}")
            return

        self.log_event(
            f"PERFIL-{source_scope.upper()}",
            profile_name,
            "OK",
            f"Copiado a {target_scope}",
        )
        self.refresh_history()
        messagebox.showinfo("Perfiles", f"Perfil '{profile_name}' copiado a {target_scope}.")

    def delete_profile(self) -> None:
        if self._current_profiles_scope() == "remoto" and self.docker_mode != "remote":
            messagebox.showwarning("Perfiles", "Cambia a modo remoto para borrar perfiles remotos.")
            return

        selected = self.profiles_listbox.curselection()
        if not selected:
            messagebox.showwarning("Perfiles", "Selecciona un perfil para eliminar.")
            return
        name = self.profiles_listbox.get(selected[0])
        if not messagebox.askyesno("Perfiles", f"Eliminar perfil '{name}'?"):
            return

        if name in self.profiles_data:
            del self.profiles_data[name]
            self._write_profiles_for_current_scope(self.profiles_data)
            scope_name = self._current_profiles_scope().upper()
            self.log_event(f"PERFIL-{scope_name}", name, "OK", "Perfil eliminado")
            self.refresh_profiles_ui(force=True)
            self.clear_profile_editor()
            self.refresh_history()
            messagebox.showinfo("Perfiles", f"Perfil eliminado: {name}")

    def run_selected_profile(self, mode: str) -> None:
        selected = self.profiles_listbox.curselection()
        if not selected:
            messagebox.showwarning("Perfiles", "Selecciona un perfil.")
            return

        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return

        profile_name = self.profiles_listbox.get(selected[0])
        containers = self.profiles_data.get(profile_name, [])
        if not containers:
            messagebox.showwarning("Perfiles", "El perfil esta vacio.")
            return

        action = "start" if mode == "start" else "stop"

        for btn in self.profile_action_btns:
            try:
                btn.configure(state="disabled")
            except tk.TclError:
                pass
        self._start_profile_spinner(profile_name)

        result_q: queue.Queue[tuple[str, list[str]]] = queue.Queue()

        def worker() -> None:
            errors: list[str] = []
            for cname in containers:
                code, _, err = self._run(["docker", action, cname])
                if code != 0:
                    errors.append(f"{cname}: {err or 'error'}")
            result_q.put(("done", errors))

        threading.Thread(target=worker, daemon=True).start()

        def poll() -> None:
            try:
                _, errors = result_q.get_nowait()
            except queue.Empty:
                self.root.after(200, poll)
                return

            self._stop_profile_spinner()
            for btn in self.profile_action_btns:
                try:
                    btn.configure(state="normal")
                except tk.TclError:
                    pass

            self.refresh_everything()
            if errors:
                self.log_event("PERFIL", profile_name, "ERROR", "; ".join(errors))
                messagebox.showwarning("Perfiles", "Algunas acciones fallaron:\n\n" + "\n".join(errors))
                return

            verb = "arrancado" if action == "start" else "apagado"
            self.log_event("PERFIL", profile_name, "OK", f"Perfil {verb}")
            self.refresh_history()
            messagebox.showinfo("Perfiles", f"Perfil {verb}: {profile_name}")

        self.root.after(200, poll)

    def selected_network_name(self) -> str | None:
        selected = self.networks_tree.selection()
        if not selected:
            return None
        values = self.networks_tree.item(selected[0], "values")
        if not values:
            return None
        return str(values[0])

    def refresh_networks(self) -> None:
        prev_net = self.selected_network_name()
        prev_targets_selected: set[str] = set()
        if hasattr(self, "network_targets_listbox"):
            for idx in self.network_targets_listbox.curselection():
                prev_targets_selected.add(self.network_targets_listbox.get(idx))

        for item in self.networks_tree.get_children():
            self.networks_tree.delete(item)
        self.network_containers_listbox.delete(0, tk.END)

        if not self.docker_ready():
            self.network_data = {}
            self.networks_tree.insert("", "end", values=("(Docker no disponible)", "-", "-"))
            self.network_containers_listbox.insert(tk.END, "Docker no disponible")
            self.network_container_combo.configure(values=[])
            self.network_container_var.set("")
            return

        if not self.container_cache:
            self.container_cache = self.get_all_container_names()

        code, out, err = self._run(["docker", "network", "ls", "--format", "{{.Name}}|{{.Driver}}"])
        if code != 0:
            self.networks_tree.insert("", "end", values=("(Error al listar)", "-", "-"))
            self.network_containers_listbox.insert(tk.END, "No se pudieron cargar networks")
            messagebox.showwarning("Networks", err or "No se pudieron listar networks")
            return

        result: dict[str, dict[str, object]] = {}
        for line in out.splitlines():
            parts = line.split("|", 1)
            if len(parts) != 2:
                continue
            name = parts[0].strip()
            driver = parts[1].strip()
            if name in {"bridge", "host", "none"}:
                continue
            result[name] = {"driver": driver, "containers": []}

        for cname in self.container_cache:
            code_i, out_i, _ = self._run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}",
                    cname,
                ]
            )
            if code_i != 0:
                continue
            connected = [x.strip() for x in out_i.split() if x.strip()]
            for net in connected:
                if net in result:
                    containers = result[net]["containers"]
                    if isinstance(containers, list):
                        containers.append(cname)

        self.network_data = result
        if not result:
            self.networks_tree.insert("", "end", values=("(sin networks)", "-", "0"))
        for name in sorted(result.keys(), key=str.lower):
            info = result[name]
            containers = info["containers"]
            count = len(containers) if isinstance(containers, list) else 0
            self.networks_tree.insert("", "end", values=(name, str(info["driver"]), count))

        if prev_net:
            restored_iid: str | None = None
            for iid in self.networks_tree.get_children():
                values = self.networks_tree.item(iid, "values")
                if values and str(values[0]) == prev_net:
                    restored_iid = iid
                    break

            if restored_iid is not None:
                self.networks_tree.selection_set(restored_iid)
                self.networks_tree.focus(restored_iid)
                self.networks_tree.see(restored_iid)

                info = self.network_data.get(prev_net, {})
                containers = info.get("containers", [])
                if isinstance(containers, list):
                    for cname in containers:
                        self.network_containers_listbox.insert(tk.END, cname)

        self.network_container_combo.configure(values=self.container_cache)
        if hasattr(self, "network_targets_listbox"):
            self.network_targets_listbox.delete(0, tk.END)
            for cname in self.container_cache:
                self.network_targets_listbox.insert(tk.END, cname)
            if prev_targets_selected:
                for idx in range(self.network_targets_listbox.size()):
                    cname = self.network_targets_listbox.get(idx)
                    if cname in prev_targets_selected:
                        self.network_targets_listbox.selection_set(idx)
        if self.container_cache and not self.network_container_var.get():
            self.network_container_var.set(self.container_cache[0])

    def on_network_selected(self, _event: object) -> None:
        self.network_containers_listbox.delete(0, tk.END)
        net_name = self.selected_network_name()
        if not net_name:
            return
        info = self.network_data.get(net_name, {})
        containers = info.get("containers", [])
        if isinstance(containers, list):
            for cname in containers:
                self.network_containers_listbox.insert(tk.END, cname)

    def create_network(self) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return
        name = simpledialog.askstring("Crear network", "Nombre de la nueva network:")
        if not name:
            return
        driver = self.network_driver_var.get().strip() or "bridge"
        code, _, err = self._run(["docker", "network", "create", "--driver", driver, name.strip()])
        if code != 0:
            self.log_event("NETWORK", name.strip(), "ERROR", err or "No se pudo crear")
            messagebox.showerror("Networks", err or "No se pudo crear la network")
            return
        self.log_event("NETWORK", name.strip(), "OK", f"Network creada con driver {driver}")
        self.refresh_networks()
        self.refresh_history()
        messagebox.showinfo("Networks", f"Network creada: {name.strip()} (driver: {driver})")

    def delete_network(self) -> None:
        net_name = self.selected_network_name()
        if not net_name:
            messagebox.showwarning("Networks", "Selecciona una network para eliminar.")
            return
        if not messagebox.askyesno("Networks", f"Eliminar network '{net_name}'?"):
            return
        code, _, err = self._run(["docker", "network", "rm", net_name])
        if code != 0:
            self.log_event("NETWORK", net_name, "ERROR", err or "No se pudo eliminar")
            messagebox.showerror("Networks", err or "No se pudo eliminar la network")
            return
        self.log_event("NETWORK", net_name, "OK", "Network eliminada")
        self.refresh_networks()
        self.refresh_history()
        messagebox.showinfo("Networks", f"Network eliminada: {net_name}")

    def rename_network(self) -> None:
        old_name = self.selected_network_name()
        if not old_name:
            messagebox.showwarning("Networks", "Selecciona una network para renombrar.")
            return

        new_name = simpledialog.askstring("Renombrar network", f"Nuevo nombre para '{old_name}':")
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            messagebox.showwarning("Networks", "Nombre nuevo no valido.")
            return

        code, _, err = self._run(["docker", "network", "create", new_name])
        if code != 0:
            self.log_event("NETWORK", new_name, "ERROR", err or "No se pudo crear nueva network")
            messagebox.showerror("Networks", err or "No se pudo crear la nueva network")
            return

        old_containers = self.network_data.get(old_name, {}).get("containers", [])
        if isinstance(old_containers, list):
            for cname in old_containers:
                self._run(["docker", "network", "connect", new_name, cname])
                self._run(["docker", "network", "disconnect", old_name, cname])

        code_rm, _, err_rm = self._run(["docker", "network", "rm", old_name])
        if code_rm != 0:
            self.log_event("NETWORK", old_name, "WARN", f"Creada {new_name}, no se pudo eliminar original")
            messagebox.showwarning(
                "Networks",
                f"Se creo '{new_name}', pero no se pudo eliminar '{old_name}'.\n\n{err_rm or ''}",
            )
        else:
            self.log_event("NETWORK", old_name, "OK", f"Renombrada a {new_name}")
            messagebox.showinfo("Networks", f"Network renombrada: {old_name} -> {new_name}")

        self.refresh_networks()
        self.refresh_history()

    def connect_container_to_network(self) -> None:
        net_name = self.selected_network_name()
        if not net_name:
            messagebox.showwarning("Networks", "Selecciona una network.")
            return

        targets: list[str] = []
        if hasattr(self, "network_targets_listbox"):
            for idx in self.network_targets_listbox.curselection():
                cname = self.network_targets_listbox.get(idx)
                if cname and cname not in targets:
                    targets.append(cname)
        if not targets:
            container = self.network_container_var.get().strip()
            if container:
                targets = [container]

        if not targets:
            messagebox.showwarning("Networks", "Selecciona un contenedor objetivo.")
            return

        errors: list[str] = []
        ok_targets: list[str] = []
        for container in targets:
            code, _, err = self._run(["docker", "network", "connect", net_name, container])
            if code != 0:
                errors.append(f"{container}: {err or 'error'}")
            else:
                ok_targets.append(container)

        self.refresh_networks()
        self.refresh_history()
        if ok_targets:
            self.log_event("NETWORK", net_name, "OK", f"Conectados: {', '.join(ok_targets)}")
        if errors:
            self.log_event("NETWORK", net_name, "ERROR", "; ".join(errors))
            messagebox.showwarning(
                "Networks",
                "Algunas conexiones fallaron.\n\n"
                + (f"Conectados: {', '.join(ok_targets)}\n\n" if ok_targets else "")
                + "Errores:\n"
                + "\n".join(errors),
            )
            return
        messagebox.showinfo("Networks", f"Contenedores conectados: {', '.join(ok_targets)} -> {net_name}")

    def disconnect_container_from_network(self) -> None:
        net_name = self.selected_network_name()
        if not net_name:
            messagebox.showwarning("Networks", "Selecciona una network.")
            return

        targets: list[str] = []
        if hasattr(self, "network_targets_listbox"):
            for idx in self.network_targets_listbox.curselection():
                cname = self.network_targets_listbox.get(idx)
                if cname and cname not in targets:
                    targets.append(cname)
        if not targets:
            container = self.network_container_var.get().strip()
            if container:
                targets = [container]

        if not targets:
            messagebox.showwarning("Networks", "Selecciona uno o varios contenedores objetivo.")
            return

        errors: list[str] = []
        ok_targets: list[str] = []
        for container in targets:
            code, _, err = self._run(["docker", "network", "disconnect", net_name, container])
            if code != 0:
                errors.append(f"{container}: {err or 'error'}")
            else:
                ok_targets.append(container)

        self.refresh_networks()
        self.refresh_history()
        if ok_targets:
            self.log_event("NETWORK", net_name, "OK", f"Desconectados: {', '.join(ok_targets)}")
        if errors:
            self.log_event("NETWORK", net_name, "ERROR", "; ".join(errors))
            messagebox.showwarning(
                "Networks",
                "Algunas desconexiones fallaron.\n\n"
                + (f"Desconectados: {', '.join(ok_targets)}\n\n" if ok_targets else "")
                + "Errores:\n"
                + "\n".join(errors),
            )
            return
        messagebox.showinfo("Networks", f"Contenedores desconectados: {', '.join(ok_targets)} de {net_name}")

    def selected_volume_names(self) -> list[str]:
        names: list[str] = []
        if not hasattr(self, "volumes_tree"):
            return names
        for item_id in self.volumes_tree.selection():
            values = self.volumes_tree.item(item_id, "values")
            if not values:
                continue
            name = str(values[0]).strip()
            if name and name not in names:
                names.append(name)
        return names

    def refresh_volumes(self) -> None:
        if not hasattr(self, "volumes_tree"):
            return

        prev_selected = set(self.selected_volume_names())
        for item in self.volumes_tree.get_children():
            self.volumes_tree.delete(item)
        if hasattr(self, "volume_containers_listbox"):
            self.volume_containers_listbox.delete(0, tk.END)

        if not self.docker_ready():
            self.volume_data = {}
            self.volumes_tree.insert("", "end", values=("(Docker no disponible)", "-", "-", "-", "-"))
            if hasattr(self, "volume_containers_listbox"):
                self.volume_containers_listbox.insert(tk.END, "Docker no disponible")
            return

        if not self.container_cache:
            self.container_cache = self.get_all_container_names()

        code, out, err = self._run(
            ["docker", "volume", "ls", "--format", "{{.Name}}|{{.Driver}}|{{.Scope}}|{{.Mountpoint}}"]
        )
        if code != 0:
            self.volumes_tree.insert("", "end", values=("(Error al listar)", "-", "-", "-", "-"))
            if hasattr(self, "volume_containers_listbox"):
                self.volume_containers_listbox.insert(tk.END, "No se pudieron cargar volumes")
            messagebox.showwarning("Volumes", err or "No se pudieron listar volumes")
            return

        result: dict[str, dict[str, object]] = {}
        for line in out.splitlines():
            parts = line.split("|", 3)
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            if not name:
                continue
            driver = parts[1].strip() if len(parts) >= 2 else ""
            scope = parts[2].strip() if len(parts) >= 3 else ""
            mountpoint = parts[3].strip() if len(parts) >= 4 else ""
            result[name] = {
                "driver": driver,
                "scope": scope,
                "mountpoint": mountpoint,
                "containers": [],
            }

        for cname in self.container_cache:
            code_i, out_i, _ = self._run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{range .Mounts}}{{if eq .Type \"volume\"}}{{.Name}} {{end}}{{end}}",
                    cname,
                ]
            )
            if code_i != 0:
                continue
            for vname in [x.strip() for x in out_i.split() if x.strip()]:
                if vname in result:
                    containers = result[vname]["containers"]
                    if isinstance(containers, list):
                        containers.append(cname)

        self.volume_data = result
        if not result:
            self.volumes_tree.insert("", "end", values=("(sin volumes)", "-", "-", "0", "-"))
        for name in sorted(result.keys(), key=str.lower):
            info = result[name]
            containers = info.get("containers", [])
            in_use = len(containers) if isinstance(containers, list) else 0
            iid = self.volumes_tree.insert(
                "",
                "end",
                values=(
                    name,
                    str(info.get("driver", "")),
                    str(info.get("scope", "")),
                    in_use,
                    str(info.get("mountpoint", "")),
                ),
            )
            if name in prev_selected:
                self.volumes_tree.selection_add(iid)

        self.on_volume_selected(None)

    def on_volume_selected(self, _event: object | None) -> None:
        if not hasattr(self, "volume_containers_listbox"):
            return
        self.volume_containers_listbox.delete(0, tk.END)
        selected = self.selected_volume_names()
        if not selected:
            return
        if len(selected) > 1:
            self.volume_containers_listbox.insert(tk.END, "(Seleccion multiple)")
            return

        info = self.volume_data.get(selected[0], {})
        containers = info.get("containers", [])
        if isinstance(containers, list) and containers:
            for cname in containers:
                self.volume_containers_listbox.insert(tk.END, cname)
        else:
            self.volume_containers_listbox.insert(tk.END, "(No esta siendo usado)")

    def create_volume(self) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return
        name = simpledialog.askstring("Crear volume", "Nombre del nuevo volume:")
        if not name:
            return
        name = name.strip()
        if not name:
            messagebox.showwarning("Volumes", "Nombre no valido.")
            return
        driver = self.volume_driver_var.get().strip() or "local"
        code, _, err = self._run(["docker", "volume", "create", "--driver", driver, name])
        if code != 0:
            self.log_event("VOLUME", name, "ERROR", err or "No se pudo crear")
            messagebox.showerror("Volumes", err or "No se pudo crear el volume")
            return
        self.log_event("VOLUME", name, "OK", f"Volume creado con driver {driver}")
        self.refresh_volumes()
        self.refresh_history()
        messagebox.showinfo("Volumes", f"Volume creado: {name} (driver: {driver})")

    def inspect_selected_volumes(self) -> None:
        names = self.selected_volume_names()
        if not names:
            messagebox.showwarning("Volumes", "Selecciona uno o varios volumes para inspeccionar.")
            return
        code, out, err = self._run(["docker", "volume", "inspect", *names])
        if code != 0:
            self.log_event("VOLUME", ", ".join(names), "ERROR", err or "No se pudo inspeccionar")
            messagebox.showerror("Volumes", err or "No se pudo inspeccionar el volume")
            return
        self._open_text_viewer("Inspeccion de volumes", out.strip() or "(Sin datos)")

    def delete_selected_volumes(self) -> None:
        names = self.selected_volume_names()
        if not names:
            messagebox.showwarning("Volumes", "Selecciona uno o varios volumes para eliminar.")
            return
        if not messagebox.askyesno("Volumes", f"Eliminar {len(names)} volume(s)?\n\n" + "\n".join(names)):
            return

        errors: list[str] = []
        ok_names: list[str] = []
        for name in names:
            code, _, err = self._run(["docker", "volume", "rm", "-f", name])
            if code != 0:
                errors.append(f"{name}: {err or 'error'}")
            else:
                ok_names.append(name)

        self.refresh_volumes()
        self.refresh_history()
        if ok_names:
            self.log_event("VOLUME", ", ".join(ok_names), "OK", "Volume(s) eliminado(s)")
        if errors:
            self.log_event("VOLUME", ", ".join(names), "ERROR", "; ".join(errors))
            messagebox.showwarning(
                "Volumes",
                "Algunas eliminaciones fallaron.\n\n"
                + (f"Eliminados: {', '.join(ok_names)}\n\n" if ok_names else "")
                + "Errores:\n"
                + "\n".join(errors),
            )
            return
        messagebox.showinfo("Volumes", f"Volume(s) eliminados: {', '.join(ok_names)}")

    def prune_volumes(self) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return
        protected = {self.remote_history_volume, self.remote_profiles_volume}

        code, out, err = self._run(["docker", "volume", "ls", "--format", "{{.Name}}"])
        if code != 0:
            self.log_event("VOLUME", "prune", "ERROR", err or "No se pudo listar volumes")
            messagebox.showerror("Volumes", err or "No se pudieron listar volumes")
            return

        all_volumes = [line.strip() for line in out.splitlines() if line.strip()]
        if not all_volumes:
            messagebox.showinfo("Volumes", "No hay volumes para evaluar.")
            return

        if not self.container_cache:
            self.container_cache = self.get_all_container_names()

        used_volumes: set[str] = set()
        for cname in self.container_cache:
            code_i, out_i, _ = self._run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{range .Mounts}}{{if eq .Type \"volume\"}}{{.Name}} {{end}}{{end}}",
                    cname,
                ]
            )
            if code_i != 0:
                continue
            for vname in [x.strip() for x in out_i.split() if x.strip()]:
                used_volumes.add(vname)

        removable = [v for v in all_volumes if v not in protected and v not in used_volumes]

        if not removable:
            messagebox.showinfo(
                "Volumes",
                "No hay volumes sin uso para eliminar.\n\n"
                f"Protegidos siempre: {self.remote_history_volume}, {self.remote_profiles_volume}",
            )
            return

        if not messagebox.askyesno(
            "Volumes",
            "Eliminar volumes sin uso?\n\n"
            f"Se protegeran siempre: {self.remote_history_volume}, {self.remote_profiles_volume}\n\n"
            f"Se intentaran eliminar {len(removable)} volume(s).",
        ):
            return

        removed: list[str] = []
        errors: list[str] = []
        for vname in removable:
            code_rm, _, err_rm = self._run(["docker", "volume", "rm", "-f", vname])
            if code_rm == 0:
                removed.append(vname)
            else:
                errors.append(f"{vname}: {err_rm or 'error'}")

        detail = (
            f"Eliminados={len(removed)}; protegidos={len([v for v in all_volumes if v in protected])}; "
            f"en uso={len(used_volumes)}"
        )
        if errors:
            self.log_event("VOLUME", "prune", "WARN", detail + "; errores=" + " | ".join(errors))
        else:
            self.log_event("VOLUME", "prune", "OK", detail)

        self.refresh_volumes()
        self.refresh_history()

        if errors:
            messagebox.showwarning(
                "Volumes",
                "Prune parcial completado.\n\n"
                f"Eliminados: {len(removed)}\n"
                f"Protegidos: {self.remote_history_volume}, {self.remote_profiles_volume}\n\n"
                "Errores:\n" + "\n".join(errors),
            )
            return

        messagebox.showinfo(
            "Volumes",
            "Prune completado.\n\n"
            f"Eliminados: {len(removed)}\n"
            f"Protegidos: {self.remote_history_volume}, {self.remote_profiles_volume}",
        )

    def clone_volume(self) -> None:
        names = self.selected_volume_names()
        if len(names) != 1:
            messagebox.showwarning("Volumes", "Selecciona un unico volume de origen para clonar.")
            return

        source_name = names[0]
        target_name = simpledialog.askstring("Clonar volume", f"Nuevo nombre para el clon de '{source_name}':")
        if not target_name:
            return
        target_name = target_name.strip()
        if not target_name:
            messagebox.showwarning("Volumes", "Nombre destino no valido.")
            return
        if target_name == source_name:
            messagebox.showwarning("Volumes", "El nombre destino debe ser diferente al origen.")
            return

        code_create, _, err_create = self._run(["docker", "volume", "create", target_name])
        if code_create != 0:
            self.log_event("VOLUME", target_name, "ERROR", err_create or "No se pudo crear volume destino")
            messagebox.showerror("Volumes", err_create or "No se pudo crear el volume destino")
            return

        code_copy, _, err_copy = self._run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{source_name}:/from:ro",
                "-v",
                f"{target_name}:/to",
                "busybox",
                "sh",
                "-c",
                "cd /from && tar cf - . | tar xf - -C /to",
            ]
        )
        if code_copy != 0:
            self.log_event("VOLUME", source_name, "ERROR", err_copy or "Fallo al clonar datos")
            messagebox.showerror("Volumes", err_copy or "No se pudo clonar el volume")
            return

        self.log_event("VOLUME", source_name, "OK", f"Clonado en {target_name}")
        self.refresh_volumes()
        self.refresh_history()
        messagebox.showinfo("Volumes", f"Volume clonado: {source_name} -> {target_name}")

    def clear_volume_contents(self) -> None:
        names = self.selected_volume_names()
        if len(names) != 1:
            messagebox.showwarning("Volumes", "Selecciona un unico volume para vaciar su contenido.")
            return
        vname = names[0]
        if not messagebox.askyesno(
            "Volumes",
            f"Vaciar TODO el contenido de '{vname}'?\n\nEsta accion no se puede deshacer.",
        ):
            return

        code, _, err = self._run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{vname}:/data",
                "busybox",
                "sh",
                "-c",
                "rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true",
            ]
        )
        if code != 0:
            self.log_event("VOLUME", vname, "ERROR", err or "No se pudo vaciar")
            messagebox.showerror("Volumes", err or "No se pudo vaciar el volume")
            return

        self.log_event("VOLUME", vname, "OK", "Contenido eliminado")
        self.refresh_history()
        messagebox.showinfo("Volumes", f"Volume vaciado: {vname}")

    def _open_text_viewer(self, title: str, content: str) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("900x520")
        dialog.minsize(640, 380)
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        text = tk.Text(
            frame,
            wrap="none",
            bg="#ffffff",
            fg="#1f2937",
            insertbackground="#1f2937",
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
            font=("Consolas", 10),
        )
        text.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        text.configure(xscrollcommand=x_scroll.set)

        text.insert("1.0", content)
        text.configure(state="disabled")

        actions = ttk.Frame(dialog, padding=(10, 0, 10, 10))
        actions.pack(fill="x")
        ttk.Button(actions, text="Cerrar", command=dialog.destroy).pack(side="right")

    def refresh_history(self) -> None:
        if not self._is_history_tab_visible():
            return

        if self._history_refresh_in_progress:
            self._history_refresh_requested = True
            return

        self._history_refresh_in_progress = True
        threading.Thread(target=self._history_refresh_worker, daemon=True).start()

        if self._history_refresh_job_id is None:
            self._history_refresh_job_id = self.root.after(100, self._poll_history_refresh_queue)

    def refresh_logs_targets(self) -> None:
        values = self.container_cache[:]
        self.log_container_combo.configure(values=values)
        if values and self.log_container_var.get() not in values:
            self.log_container_var.set(values[0])
        if not values:
            self._stop_follow_logs()
            self.log_container_var.set("")

    def _parse_log_lines(self) -> int:
        raw = self.log_lines_var.get().strip()
        try:
            value = int(raw)
        except ValueError:
            value = 100
        value = max(10, min(5000, value))
        self.log_lines_var.set(str(value))
        return value

    def fetch_logs(self, preserve_scroll: bool = False) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return

        container = self.log_container_var.get().strip()
        if not container:
            messagebox.showwarning("Logs", "Selecciona un contenedor.")
            return

        tail = self._parse_log_lines()

        if self.log_follow_var.get():
            self._start_follow_logs(container, tail)
            return

        saved_x = self.logs_text.xview()[0] if preserve_scroll else 0.0
        saved_y = self.logs_text.yview()[0] if preserve_scroll else None

        self._stop_follow_logs()
        code, out, err = self._run(["docker", "logs", "--tail", str(tail), container])

        content_parts = []
        if out:
            content_parts.append(out)
        if err:
            content_parts.append(err)
        content = "\n".join(content_parts).strip()
        if not content:
            content = "(Sin salida de logs en este momento)"

        self.logs_text.configure(state="normal")
        self.logs_text.delete("1.0", tk.END)
        self.logs_text.insert(tk.END, content)

        if preserve_scroll:
            self.logs_text.xview_moveto(saved_x)
            self.logs_text.yview_moveto(saved_y)
        else:
            self.logs_text.see(tk.END)
            self.logs_text.xview_moveto(0.0)

        self.logs_text.configure(state="disabled")

        if code == 0:
            self.log_event("LOGS", container, "OK", f"Ultimas {tail} lineas")
        else:
            self.log_event("LOGS", container, "ERROR", f"Fallo al leer logs: {err or 'error'}")
        self.refresh_history()

    def _auto_fetch_logs(self) -> None:
        if not self.log_auto_refresh_var.get():
            return
        if self.log_follow_var.get():
            return
        self.fetch_logs(preserve_scroll=True)
        self.logs_refresh_job_id = self.root.after(4000, self._auto_fetch_logs)

    def toggle_logs_auto_refresh(self) -> None:
        if self.logs_refresh_job_id is not None:
            self.root.after_cancel(self.logs_refresh_job_id)
            self.logs_refresh_job_id = None

        if self.log_auto_refresh_var.get() and self.log_follow_var.get():
            self.log_auto_refresh_var.set(False)
            messagebox.showinfo("Logs", "Desactiva 'Seguir (-f)' para usar Auto-refresco.")
            return

        if self.log_auto_refresh_var.get():
            self._auto_fetch_logs()

    def on_follow_mode_toggled(self) -> None:
        if self.log_follow_var.get() and self.log_auto_refresh_var.get():
            self.log_auto_refresh_var.set(False)
            if self.logs_refresh_job_id is not None:
                self.root.after_cancel(self.logs_refresh_job_id)
                self.logs_refresh_job_id = None

        if not self.log_follow_var.get():
            self._stop_follow_logs()

    def _start_follow_logs(self, container: str, tail: int) -> None:
        self._stop_follow_logs()
        if self._should_use_docker_sdk():
            self._start_follow_logs_sdk(container, tail)
            return
        try:
            cmd = self._build_docker_command(["docker", "logs", "-f", "--tail", str(tail), container])
            self.logs_follow_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.tools_dir,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as exc:
            self.log_event("LOGS", container, "ERROR", f"Fallo al iniciar seguimiento: {exc}")
            self.refresh_history()
            messagebox.showerror("Logs", f"No se pudo iniciar seguimiento de logs.\n\n{exc}")
            return

        self.logs_text.configure(state="normal")
        self.logs_text.delete("1.0", tk.END)
        self.logs_text.insert(tk.END, f"Siguiendo logs de {container}... (Ctrl + boton para detener cambiando modo)\n\n")
        self.logs_text.configure(state="disabled")

        reader_thread = threading.Thread(target=self._read_follow_output, daemon=True)
        reader_thread.start()
        self.logs_follow_poll_job_id = self.root.after(150, self._poll_follow_output)
        self.log_event("LOGS", container, "INFO", f"Seguimiento en vivo iniciado (tail={tail})")
        self.refresh_history()

    def _start_follow_logs_sdk(self, container: str, tail: int) -> None:
        client = self._get_docker_sdk_client(timeout_seconds=300)
        if client is None:
            messagebox.showerror("Logs", "Docker SDK no disponible para seguimiento en vivo.")
            return

        try:
            client.api.timeout = None
        except Exception:
            pass

        try:
            cont = client.containers.get(container)
            stream = cont.logs(stream=True, follow=True, tail=tail, stdout=True, stderr=True)
        except Exception as exc:
            self.log_event("LOGS", container, "ERROR", f"Fallo al iniciar seguimiento SDK: {exc}")
            self.refresh_history()
            messagebox.showerror("Logs", f"No se pudo iniciar seguimiento de logs.\n\n{exc}")
            return

        self._sdk_follow_stop_event = threading.Event()
        self._sdk_follow_active = True

        self.logs_text.configure(state="normal")
        self.logs_text.delete("1.0", tk.END)
        self.logs_text.insert(tk.END, f"Siguiendo logs de {container}... (modo SDK)\n\n")
        self.logs_text.configure(state="disabled")

        reader_thread = threading.Thread(target=self._read_follow_output_sdk, args=(stream,), daemon=True)
        reader_thread.start()
        self.logs_follow_poll_job_id = self.root.after(150, self._poll_follow_output)
        self.log_event("LOGS", container, "INFO", f"Seguimiento en vivo iniciado (SDK, tail={tail})")
        self.refresh_history()

    def _read_follow_output_sdk(self, stream: object) -> None:
        try:
            for chunk in stream:
                if self._sdk_follow_stop_event is not None and self._sdk_follow_stop_event.is_set():
                    break
                if isinstance(chunk, (bytes, bytearray)):
                    text = chunk.decode("utf-8", errors="replace")
                else:
                    text = str(chunk)
                if text:
                    self.logs_follow_queue.put(text)
        except Exception as exc:
            self.logs_follow_queue.put(f"\n[seguimiento finalizado con error: {exc}]\n")
        finally:
            self._sdk_follow_active = False

    def _read_follow_output(self) -> None:
        process = self.logs_follow_process
        if process is None or process.stdout is None:
            return

        for line in process.stdout:
            self.logs_follow_queue.put(line)

    def _poll_follow_output(self) -> None:
        chunks: list[str] = []
        while True:
            try:
                chunks.append(self.logs_follow_queue.get_nowait())
            except queue.Empty:
                break

        if chunks:
            self.logs_text.configure(state="normal")
            self.logs_text.insert(tk.END, "".join(chunks))
            self.logs_text.see(tk.END)
            self.logs_text.configure(state="disabled")

        process = self.logs_follow_process
        if process is None:
            if self._sdk_follow_active:
                self.logs_follow_poll_job_id = self.root.after(150, self._poll_follow_output)
                return
            self.logs_follow_poll_job_id = None
            return

        if process.poll() is None:
            self.logs_follow_poll_job_id = self.root.after(150, self._poll_follow_output)
            return

        self.logs_follow_poll_job_id = None
        exit_code = process.returncode
        self.logs_text.configure(state="normal")
        self.logs_text.insert(tk.END, f"\n[seguimiento finalizado, codigo {exit_code}]\n")
        self.logs_text.see(tk.END)
        self.logs_text.configure(state="disabled")
        self.logs_follow_process = None

    def _stop_follow_logs(self) -> None:
        if self.logs_follow_poll_job_id is not None:
            self.root.after_cancel(self.logs_follow_poll_job_id)
            self.logs_follow_poll_job_id = None

        if self._sdk_follow_stop_event is not None:
            self._sdk_follow_stop_event.set()
            self._sdk_follow_stop_event = None
        self._sdk_follow_active = False

        process = self.logs_follow_process
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            self.logs_follow_process = None

        while True:
            try:
                self.logs_follow_queue.get_nowait()
            except queue.Empty:
                break

    def on_close(self) -> None:
        if self.refresh_job_id is not None:
            self.root.after_cancel(self.refresh_job_id)
            self.refresh_job_id = None
        if self.logs_refresh_job_id is not None:
            self.root.after_cancel(self.logs_refresh_job_id)
            self.logs_refresh_job_id = None
        if self._docker_check_job_id is not None:
            self.root.after_cancel(self._docker_check_job_id)
            self._docker_check_job_id = None
        if self._history_refresh_job_id is not None:
            self.root.after_cancel(self._history_refresh_job_id)
            self._history_refresh_job_id = None
        if self._profiles_load_job_id is not None:
            self.root.after_cancel(self._profiles_load_job_id)
            self._profiles_load_job_id = None
        self._stop_status_spinner()
        self._stop_container_spinner()
        self._stop_profile_spinner()
        self._stop_follow_logs()
        self.root.destroy()

    def export_visible_logs(self) -> None:
        content = self.logs_text.get("1.0", tk.END).strip()
        if not content or content == "Selecciona un contenedor y pulsa 'Ver logs'.":
            messagebox.showwarning("Logs", "No hay contenido de logs para exportar.")
            return

        container = self.log_container_var.get().strip() or "contenedor"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"logs_{container}_{stamp}.txt"

        output_path = filedialog.asksaveasfilename(
            title="Guardar logs como",
            initialdir=self.tools_dir,
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Archivo de texto", "*.txt"), ("Todos los archivos", "*.*")],
        )

        if not output_path:
            return

        try:
            with open(output_path, "w", encoding="utf-8", errors="replace") as fh:
                fh.write(content)
            self.log_event("LOGS", container, "OK", f"Exportado a {output_path}")
            self.refresh_history()
            messagebox.showinfo("Logs", f"Logs exportados correctamente.\n\n{output_path}")
        except Exception as exc:
            self.log_event("LOGS", container, "ERROR", f"Fallo al exportar: {exc}")
            self.refresh_history()
            messagebox.showerror("Logs", f"No se pudieron exportar los logs.\n\n{exc}")

    def copy_visible_logs(self) -> None:
        content = self.logs_text.get("1.0", tk.END).strip()
        if not content or content == "Selecciona un contenedor y pulsa 'Ver logs'.":
            messagebox.showwarning("Logs", "No hay contenido visible para copiar.")
            return

        container = self.log_container_var.get().strip() or "contenedor"
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.root.update()
        self.log_event("LOGS", container, "INFO", "Contenido visible copiado al portapapeles")
        self.refresh_history()
        messagebox.showinfo("Logs", "Contenido copiado al portapapeles.")

    def apply_history_filter(self, _event: object = None) -> None:
        level = self.history_level_var.get().strip().upper()
        query = self.history_search_var.get().strip()
        query_tokens = [
            token
            for token in self._normalize_text(query).split()
            if token
        ]

        filtered: list[str] = []
        for line in self.history_lines:
            detected_level = self._detect_history_level(line)
            if level != "TODOS" and detected_level != level:
                continue
            if query_tokens:
                normalized_line = self._normalize_text(line)
                if not all(token in normalized_line for token in query_tokens):
                    continue
            filtered.append(line)

        x_first, _x_last = self.history_text.xview()
        y_first, _y_last = self.history_text.yview()

        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", tk.END)
        if filtered:
            self.history_text.insert(tk.END, "\n".join(filtered))
        else:
            self.history_text.insert(tk.END, "Sin registros para el filtro actual.")
        self.history_text.xview_moveto(x_first)
        self.history_text.yview_moveto(y_first)
        self.history_text.configure(state="disabled")

    @staticmethod
    def _detect_history_level(line: str) -> str:
        upper = line.upper()

        # Formato heredado: ... RESULTADO=OK ...
        match_resultado = re.search(r"\bRESULTADO\s*=\s*(OK|ERROR|WARN|INFO)\b", upper)
        if match_resultado:
            return match_resultado.group(1)

        # Formato GUI actual: [OK] / [ERROR] / [WARN] / [INFO]
        match_brackets = re.search(r"\[(OK|ERROR|WARN|INFO)\]", upper)
        if match_brackets:
            return match_brackets.group(1)

        return "INFO"

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        no_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return no_accents.lower()

    def clear_history_filters(self) -> None:
        self.history_level_var.set("TODOS")
        self.history_search_var.set("")
        self.apply_history_filter()

    def copy_visible_history(self) -> None:
        content = self.history_text.get("1.0", tk.END).strip()
        if not content or content == "Sin registros para el filtro actual.":
            messagebox.showwarning("Historial", "No hay contenido visible para copiar.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.root.update()
        self.log_event("HISTORIAL", "visible", "INFO", "Contenido copiado al portapapeles")
        self.refresh_history()
        messagebox.showinfo("Historial", "Contenido copiado al portapapeles.")

    def launch_bat(self, bat_name: str, args: str = "", maximized: bool = False) -> None:
        bat_path = os.path.join(self.tools_dir, bat_name)
        if not os.path.isfile(bat_path):
            messagebox.showerror("Archivo", f"No se encontro:\n{bat_path}")
            return

        if maximized:
            cmd = f'start "" /wait cmd /c ""{bat_path}" maximizado"'
        elif args:
            cmd = f'start "" /wait cmd /c ""{bat_path}" {args}"'
        else:
            cmd = f'start "" /wait cmd /c ""{bat_path}""'

        try:
            subprocess.Popen(cmd, cwd=self.tools_dir, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.log_event("SCRIPT", bat_name, "INFO", f"Lanzado con args: {args or '-'}")
            self.refresh_history()
        except Exception as exc:  # pragma: no cover
            self.log_event("SCRIPT", bat_name, "ERROR", str(exc))
            messagebox.showerror("Ejecucion", f"No se pudo ejecutar {bat_name}.\n\n{exc}")

    @staticmethod
    def _is_host_port_available(port: int) -> bool:
        if port < 1 or port > 65535:
            return False
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    def _get_running_docker_published_ports(self) -> set[int]:
        code, out, _ = self._run(["docker", "ps", "--format", "{{.Ports}}"])
        if code != 0 or not out:
            return set()

        ports: set[int] = set()
        for line in out.splitlines():
            if not line.strip():
                continue
            # Ejemplos:
            # 0.0.0.0:8181->80/tcp, :::8181->80/tcp
            # [::]:8181->80/tcp
            for match in re.finditer(r":(\d+)->", line):
                try:
                    ports.add(int(match.group(1)))
                except ValueError:
                    continue
        return ports

    def _validate_setup_ports_inputs(
        self,
        http_port: str,
        https_port: str,
        db_port: str,
        pma_port: str,
    ) -> tuple[bool, str]:
        raw_map = {
            "HTTP": http_port.strip(),
            "HTTPS": https_port.strip(),
            "MariaDB": db_port.strip(),
            "phpMyAdmin": pma_port.strip(),
        }

        parsed: dict[str, int] = {}
        for label, raw in raw_map.items():
            if not raw:
                return False, f"Completa el puerto {label}."
            try:
                value = int(raw)
            except ValueError:
                return False, f"El puerto {label} debe ser numerico."
            if value < 1 or value > 65535:
                return False, f"El puerto {label} debe estar entre 1 y 65535."
            parsed[label] = value

        values = list(parsed.values())
        if len(set(values)) != len(values):
            return False, "No se permiten puertos repetidos."

        docker_ports = self._get_running_docker_published_ports()
        busy_labels: list[str] = []
        for label, port in parsed.items():
            # En remoto validamos contra puertos publicados del daemon remoto.
            # En local tambien validamos disponibilidad en host cliente.
            is_busy = port in docker_ports
            if not is_busy and self.docker_mode != "remote":
                is_busy = not self._is_host_port_available(port)
            if is_busy:
                busy_labels.append(label)
        if busy_labels:
            prefix = "Puertos en uso en daemon remoto: " if self.docker_mode == "remote" else "Puertos en uso: "
            return False, prefix + ", ".join(busy_labels)

        return True, "Puertos validados y disponibles."

    def _add_password_entry_with_toggle(
        self,
        parent: tk.Misc,
        textvariable: tk.StringVar,
        row: int,
        column: int,
        padx: int | tuple[int, int] = 0,
        pady: int | tuple[int, int] = 0,
        sticky: str = "ew",
    ) -> ttk.Entry:
        wrapper = ttk.Frame(parent)
        wrapper.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady)
        wrapper.columnconfigure(0, weight=1)

        entry = ttk.Entry(wrapper, textvariable=textvariable, show="*")
        entry.grid(row=0, column=0, sticky="ew")

        toggle_button = ttk.Button(wrapper, text="Ver", width=7)
        toggle_button.grid(row=0, column=1, padx=(6, 0))

        def toggle_password_visibility() -> None:
            hidden = entry.cget("show") == "*"
            entry.configure(show="" if hidden else "*")
            toggle_button.configure(text="Ocultar" if hidden else "Ver")

        toggle_button.configure(command=toggle_password_visibility)
        return entry

    def _open_or_focus_work_tab(self, tab_key: str, title: str) -> ttk.Frame | None:
        if self.tabs is None:
            return None

        existing = self.dynamic_tabs.get(tab_key)
        if existing is not None and existing.winfo_exists():
            self.tabs.select(existing)
            return existing

        frame = ttk.Frame(self.tabs, padding=10)
        self.dynamic_tabs[tab_key] = frame
        self.tabs.add(frame, text=title)
        self.tabs.select(frame)
        return frame

    def _close_work_tab(self, tab_key: str) -> None:
        if self.tabs is None:
            return
        tab = self.dynamic_tabs.get(tab_key)
        if tab is None or not tab.winfo_exists():
            self.dynamic_tabs.pop(tab_key, None)
            return
        try:
            self.tabs.forget(tab)
        except Exception:
            pass
        tab.destroy()
        self.dynamic_tabs.pop(tab_key, None)

    def _update_status_dot(self, *_: object) -> None:
        if self.docker_status_dot is None or not self.docker_status_dot.winfo_exists():
            return
        status = self.status_var.get().lower()
        if "disponible" in status and "no " not in status:
            color = "#10b981"   # green  - available
        elif "no disponible" in status or "no encontrado" in status or "error" in status:
            color = "#ef4444"   # red    - unavailable
        elif "iniciando" in status or "comprobando" in status:
            color = "#f59e0b"   # amber  - in progress
        else:
            color = "#64748b"   # slate  - unknown
        self.docker_status_dot.configure(fg=color)
        self._update_connection_mode_badge()

    def _update_connection_mode_badge(self) -> None:
        host = (self.docker_host or "").strip()
        if host.startswith("tcp://"):
            host = host[6:]
        elif host.startswith("http://"):
            host = host[7:]
        elif host.startswith("https://"):
            host = host[8:]

        if self.docker_mode == "remote":
            short_host = host if len(host) <= 34 else f"{host[:31]}..."
            if self.is_compact_layout:
                mode_text = f"Remoto: {short_host or 'sin host'}"
            else:
                mode_text = f"Modo: remoto ({short_host or 'sin host'})"
            fg = "#7f1d1d"
            bg = "#fee2e2"
        else:
            mode_text = "Local" if self.is_compact_layout else "Modo: local"
            fg = "#1e3a8a"
            bg = "#dbeafe"

        self.connection_mode_var.set(mode_text)
        if self.connection_mode_badge is not None and self.connection_mode_badge.winfo_exists():
            self.connection_mode_badge.configure(fg=fg, bg=bg)

    def _bind_global_shortcuts(self) -> None:
        def bind_shortcut(sequence: str, action: Callable[[], None]) -> None:
            def handler(_event: object) -> str:
                try:
                    action()
                except Exception:
                    pass
                return "break"

            self.root.bind_all(sequence, handler)

        bind_shortcut("<Control-r>", self.refresh_everything)
        bind_shortcut("<Control-i>", self.open_import_wizard)
        bind_shortcut("<Control-e>", self.open_export_wizard)
        bind_shortcut("<Control-l>", self.open_setup_wizard)
        bind_shortcut("<Control-b>", self._toggle_compact_layout)
        bind_shortcut("<Control-q>", self.on_close)

    def _schedule_layout_reflow(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        if self._layout_reflow_job is not None:
            try:
                self.root.after_cancel(self._layout_reflow_job)
            except Exception:
                pass
        self._layout_reflow_job = self.root.after(90, self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> None:
        self._layout_reflow_job = None
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        compact = width < 1040 or height < 620
        self._set_compact_layout(compact)

    def _toggle_compact_layout(self) -> None:
        self._set_compact_layout(not self.is_compact_layout)

    def _set_compact_layout(self, compact: bool) -> None:
        if self.is_compact_layout == compact:
            return
        self.is_compact_layout = compact

        if self.sidebar_frame is not None and self.sidebar_frame.winfo_exists():
            self.sidebar_frame.configure(width=84 if compact else 234)

        if self.sidebar_logo_title_label is not None and self.sidebar_logo_title_label.winfo_exists():
            self.sidebar_logo_title_label.configure(text="\u2726" if compact else "\u2726  WordPress")

        if self.sidebar_logo_subtitle_label is not None and self.sidebar_logo_subtitle_label.winfo_exists():
            if compact:
                self.sidebar_logo_subtitle_label.pack_forget()
            else:
                if not self.sidebar_logo_subtitle_label.winfo_manager():
                    self.sidebar_logo_subtitle_label.pack(anchor="w", pady=(3, 0))

        if self.sidebar_shortcuts_label is not None and self.sidebar_shortcuts_label.winfo_exists():
            if compact:
                self.sidebar_shortcuts_label.pack_forget()
            else:
                if not self.sidebar_shortcuts_label.winfo_manager():
                    self.sidebar_shortcuts_label.pack(fill="x")

        for btn, full_label, compact_label in self.sidebar_nav_buttons:
            if not btn.winfo_exists():
                continue
            if compact:
                btn.configure(text=compact_label, anchor="center", padx=0)
            else:
                btn.configure(text=full_label, anchor="w", padx=18)

        if self.sidebar_quit_button is not None and self.sidebar_quit_button.winfo_exists():
            if compact:
                self.sidebar_quit_button.configure(text="\u00d7", anchor="center", padx=0)
            else:
                self.sidebar_quit_button.configure(text="\u00d7  Cerrar aplicacion", anchor="w", padx=18)

        if self.sidebar_status_label is not None and self.sidebar_status_label.winfo_exists():
            if compact:
                self.sidebar_status_label.pack_forget()
            else:
                if not self.sidebar_status_label.winfo_manager():
                    self.sidebar_status_label.pack(side="left", padx=(6, 0))

        style = ttk.Style(self.root)
        if compact:
            style.configure("TNotebook.Tab", padding=(10, 6), font=("Segoe UI", 9))
        else:
            style.configure("TNotebook.Tab", padding=(16, 9), font=("Segoe UI", 10))

        self._update_connection_mode_badge()

    def _add_work_tab_header(self, parent: ttk.Frame, title: str, tab_key: str) -> None:
        header = tk.Frame(parent, bg="#eff6ff", padx=16, pady=10)
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 14))
        tk.Label(header, text=title, font=("Segoe UI Semibold", 12),
                 fg="#1e40af", bg="#eff6ff").pack(side="left")
        ttk.Button(header, text="Cerrar ×", command=lambda: self._close_work_tab(tab_key),
                   style="Ghost.TButton").pack(side="right")

    def open_setup_wizard(self) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return

        default_ip_red = "192.168.200.51"
        if self.docker_mode == "remote" and self.docker_host:
            parsed = self._extract_host_port_from_docker_host(self.docker_host)
            if parsed is not None:
                host, _port = parsed
                if host:
                    default_ip_red = host

        window = self._open_or_focus_work_tab("setup", "Crear/Recrear")
        if window is None:
            messagebox.showerror("Interfaz", "No se pudo abrir la pestaña de Crear/Recrear.")
            return

        for child in window.winfo_children():
            child.destroy()

        outer = self._create_scrollable_surface(window, padding=(8, 8))
        outer.columnconfigure(1, weight=1)
        self._add_work_tab_header(outer, "Asistente Crear/Recrear entorno", "setup")

        wp_name_var = tk.StringVar(value="wordpress1")
        db_name_container_var = tk.StringVar(value="mariadb1")
        pma_name_var = tk.StringVar(value="phpmyadmin1")
        network_var = tk.StringVar(value="wp-network1")
        wp_volume_var = tk.StringVar(value="wpdata1")
        db_volume_var = tk.StringVar(value="mariadbdata1")
        http_port_var = tk.StringVar(value="8182")
        https_port_var = tk.StringVar(value="8445")
        http_container_port_var = tk.StringVar(value="8080")
        https_container_port_var = tk.StringVar(value="8443")
        db_port_var = tk.StringVar(value="3307")
        pma_port_var = tk.StringVar(value="8181")
        ip_red_var = tk.StringVar(value=default_ip_red)
        dominio_var = tk.StringVar(value="https://tudominio.com")
        wp_user_var = tk.StringVar(value="admin")
        wp_password_var = tk.StringVar(value="admin")
        db_name_var = tk.StringVar(value="wordpress")
        db_user_var = tk.StringVar(value="admin")
        db_password_var = tk.StringVar(value="admin")
        db_root_password_var = tk.StringVar(value="1234")
        status_var = tk.StringVar(value="Completa la configuracion y pulsa Crear/Recrear.")
        progress_var = tk.DoubleVar(value=0)
        stop_event = threading.Event()

        row = 1
        ttk.Label(outer, text="Contenedor WordPress:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=wp_name_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Contenedor MariaDB:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=db_name_container_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Contenedor phpMyAdmin:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=pma_name_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Network Docker:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=network_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Volumen WordPress:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=wp_volume_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Volumen MariaDB:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=db_volume_var).grid(row=row, column=1, sticky="ew", pady=4)

        ports_frame = ttk.LabelFrame(outer, text="Puertos host")
        row += 1
        ports_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        for i in range(8):
            ports_frame.columnconfigure(i, weight=1)

        ttk.Label(ports_frame, text="HTTP").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ports_frame, textvariable=http_port_var, width=8).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(ports_frame, text="HTTPS").grid(row=0, column=2, sticky="w", padx=6)
        ttk.Entry(ports_frame, textvariable=https_port_var, width=8).grid(row=0, column=3, sticky="w", padx=6)
        ttk.Label(ports_frame, text="MariaDB").grid(row=0, column=4, sticky="w", padx=6)
        ttk.Entry(ports_frame, textvariable=db_port_var, width=8).grid(row=0, column=5, sticky="w", padx=6)
        ttk.Label(ports_frame, text="phpMyAdmin").grid(row=0, column=6, sticky="w", padx=6)
        ttk.Entry(ports_frame, textvariable=pma_port_var, width=8).grid(row=0, column=7, sticky="w", padx=6)
        ttk.Label(ports_frame, text="HTTP contenedor").grid(row=1, column=0, sticky="w", padx=6, pady=(6, 4))
        ttk.Entry(ports_frame, textvariable=http_container_port_var, width=8).grid(row=1, column=1, sticky="w", padx=6, pady=(6, 4))
        ttk.Label(ports_frame, text="HTTPS contenedor").grid(row=1, column=2, sticky="w", padx=6, pady=(6, 4))
        ttk.Entry(ports_frame, textvariable=https_container_port_var, width=8).grid(row=1, column=3, sticky="w", padx=6, pady=(6, 4))

        row += 1
        ttk.Label(outer, text="IP en red local:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=ip_red_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Dominio produccion:").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=dominio_var).grid(row=row, column=1, sticky="ew", pady=4)

        creds_wp = ttk.LabelFrame(outer, text="Credenciales WordPress")
        row += 1
        creds_wp.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        creds_wp.columnconfigure(1, weight=1)
        creds_wp.columnconfigure(3, weight=1)
        ttk.Label(creds_wp, text="Usuario").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(creds_wp, textvariable=wp_user_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(creds_wp, text="Password").grid(row=0, column=2, sticky="w", padx=6)
        self._add_password_entry_with_toggle(creds_wp, wp_password_var, row=0, column=3, padx=6)

        creds_db = ttk.LabelFrame(outer, text="Credenciales Base de Datos")
        row += 1
        creds_db.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        creds_db.columnconfigure(1, weight=1)
        creds_db.columnconfigure(3, weight=1)
        ttk.Label(creds_db, text="Nombre DB").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(creds_db, textvariable=db_name_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(creds_db, text="Usuario DB").grid(row=0, column=2, sticky="w", padx=6)
        ttk.Entry(creds_db, textvariable=db_user_var).grid(row=0, column=3, sticky="ew", padx=6)
        ttk.Label(creds_db, text="Password DB").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self._add_password_entry_with_toggle(creds_db, db_password_var, row=1, column=1, padx=6)
        ttk.Label(creds_db, text="Root Password").grid(row=1, column=2, sticky="w", padx=6)
        self._add_password_entry_with_toggle(creds_db, db_root_password_var, row=1, column=3, padx=6)

        row += 1
        ttk.Separator(outer, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 10))

        row += 1
        ttk.Label(outer, textvariable=status_var).grid(row=row, column=0, columnspan=2, sticky="w")

        row += 1
        ttk.Progressbar(outer, orient="horizontal", mode="determinate", maximum=100, variable=progress_var).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )

        row += 1
        actions = ttk.Frame(outer)
        actions.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        cancel_button = ttk.Button(actions, text="Cancelar", command=window.destroy)
        cancel_button.pack(side="right")
        stop_button = ttk.Button(
            actions,
            text="Detener",
            state="disabled",
            command=lambda: self._request_import_cancel(status_var, stop_event, stop_button),
        )
        stop_button.pack(side="right", padx=(0, 8))
        run_button = ttk.Button(
            actions,
            text="Crear/Recrear ahora",
            command=lambda: self._run_setup_from_wizard(
                window=window,
                status_var=status_var,
                progress_var=progress_var,
                run_button=run_button,
                cancel_button=cancel_button,
                stop_button=stop_button,
                stop_event=stop_event,
                wp_container=wp_name_var.get().strip(),
                db_container=db_name_container_var.get().strip(),
                pma_container=pma_name_var.get().strip(),
                network_name=network_var.get().strip(),
                wp_volume=wp_volume_var.get().strip(),
                db_volume=db_volume_var.get().strip(),
                http_port=http_port_var.get().strip(),
                https_port=https_port_var.get().strip(),
                http_container_port=http_container_port_var.get().strip(),
                https_container_port=https_container_port_var.get().strip(),
                db_port=db_port_var.get().strip(),
                pma_port=pma_port_var.get().strip(),
                ip_red=ip_red_var.get().strip(),
                dominio_produccion=dominio_var.get().strip(),
                wp_user=wp_user_var.get().strip(),
                wp_password=wp_password_var.get(),
                db_name=db_name_var.get().strip(),
                db_user=db_user_var.get().strip(),
                db_password=db_password_var.get(),
                db_root_password=db_root_password_var.get(),
            ),
        )
        run_button.pack(side="right", padx=(0, 8))

        def refresh_ports_validation(*_args: object) -> None:
            valid, msg = self._validate_setup_ports_inputs(
                http_port=http_port_var.get(),
                https_port=https_port_var.get(),
                db_port=db_port_var.get(),
                pma_port=pma_port_var.get(),
            )
            if valid:
                run_button.configure(state="normal")
                status_var.set("Completa la configuracion y pulsa Crear/Recrear.")
            else:
                run_button.configure(state="disabled")
                status_var.set(f"Validacion de puertos: {msg}")

        for var in (http_port_var, https_port_var, db_port_var, pma_port_var):
            var.trace_add("write", refresh_ports_validation)
        refresh_ports_validation()

    def _run_setup_from_wizard(
        self,
        window: tk.Toplevel,
        status_var: tk.StringVar,
        progress_var: tk.DoubleVar,
        run_button: ttk.Button,
        cancel_button: ttk.Button,
        stop_button: ttk.Button,
        stop_event: threading.Event,
        wp_container: str,
        db_container: str,
        pma_container: str,
        network_name: str,
        wp_volume: str,
        db_volume: str,
        http_port: str,
        https_port: str,
        http_container_port: str,
        https_container_port: str,
        db_port: str,
        pma_port: str,
        ip_red: str,
        dominio_produccion: str,
        wp_user: str,
        wp_password: str,
        db_name: str,
        db_user: str,
        db_password: str,
        db_root_password: str,
    ) -> None:
        required = {
            "Contenedor WordPress": wp_container,
            "Contenedor MariaDB": db_container,
            "Contenedor phpMyAdmin": pma_container,
            "Network": network_name,
            "Volumen WordPress": wp_volume,
            "Volumen MariaDB": db_volume,
            "IP red": ip_red,
            "Dominio produccion": dominio_produccion,
            "Usuario WP": wp_user,
            "Password WP": wp_password,
            "Nombre DB": db_name,
            "Usuario DB": db_user,
            "Password DB": db_password,
            "Root password DB": db_root_password,
        }
        for label, value in required.items():
            if not value:
                messagebox.showwarning("Crear/Recrear", f"El campo '{label}' es obligatorio.")
                return

        try:
            http_port_i = int(http_port)
            https_port_i = int(https_port)
            http_container_port_i = int(http_container_port)
            https_container_port_i = int(https_container_port)
            db_port_i = int(db_port)
            pma_port_i = int(pma_port)
        except ValueError:
            messagebox.showwarning("Crear/Recrear", "Los puertos deben ser numeros enteros.")
            return

        internal_ports = [http_container_port_i, https_container_port_i]
        if any(p < 1 or p > 65535 for p in internal_ports):
            messagebox.showwarning("Crear/Recrear", "Los puertos internos deben estar entre 1 y 65535.")
            return

        ports = [http_port_i, https_port_i, db_port_i, pma_port_i]
        if len(set(ports)) != len(ports):
            messagebox.showwarning("Crear/Recrear", "Los puertos no pueden repetirse.")
            return

        if self.docker_mode == "remote":
            remote_published = self._get_running_docker_published_ports()
            busy_ports = [p for p in ports if p in remote_published]
        else:
            busy_ports = [p for p in ports if not self._is_host_port_available(p)]
        if busy_ports:
            messagebox.showwarning(
                "Crear/Recrear",
                (
                    "Estos puertos ya estan publicados en el daemon remoto: "
                    if self.docker_mode == "remote"
                    else "Estos puertos estan en uso en el host: "
                )
                + ", ".join(str(p) for p in busy_ports),
            )
            return

        existing_containers = [
            cname
            for cname in (wp_container, db_container, pma_container)
            if self._container_exists(cname)
        ]

        recreate_existing = True
        if existing_containers:
            existing_text = ", ".join(existing_containers)
            delete_existing = messagebox.askyesno(
                "Crear/Recrear",
                (
                    "Se detectaron contenedores ya creados:\n\n"
                    f"{existing_text}\n\n"
                    "Quieres borrarlos para crearlos de nuevo?"
                ),
            )
            if not delete_existing:
                continue_without_delete = messagebox.askyesno(
                    "Crear/Recrear",
                    (
                        "No se borraran los contenedores existentes.\n\n"
                        "Quieres avanzar con el resto del proceso (crear solo lo que falte)?\n\n"
                        "Si eliges No, se cancelara la operacion."
                    ),
                )
                if not continue_without_delete:
                    return
                recreate_existing = False

        if recreate_existing:
            warning = (
                "Esta accion destruira el entorno anterior con los mismos nombres.\n\n"
                f"Contenedores: {wp_container}, {db_container}, {pma_container}\n"
                f"Volumenes: {wp_volume}, {db_volume}\n"
                f"Network: {network_name}\n\n"
                "Deseas continuar?"
            )
        else:
            warning = (
                "Se conservaran los contenedores ya existentes y se intentara crear/arrancar lo que falte.\n\n"
                f"Contenedores objetivo: {wp_container}, {db_container}, {pma_container}\n"
                f"Volumenes objetivo: {wp_volume}, {db_volume}\n"
                f"Network objetivo: {network_name}\n\n"
                "Deseas continuar?"
            )
        if not messagebox.askyesno("Confirmar Crear/Recrear", warning):
            return

        run_button.configure(state="disabled")
        cancel_button.configure(state="disabled")
        stop_button.configure(state="normal")
        stop_event.clear()
        progress_var.set(0)
        status_var.set("Iniciando creacion del entorno...")

        events: queue.Queue[tuple[str, object]] = queue.Queue()
        worker = threading.Thread(
            target=self._run_setup_worker,
            args=(
                events,
                stop_event,
                wp_container,
                db_container,
                pma_container,
                network_name,
                wp_volume,
                db_volume,
                http_port_i,
                https_port_i,
                http_container_port_i,
                https_container_port_i,
                db_port_i,
                pma_port_i,
                ip_red,
                dominio_produccion,
                wp_user,
                wp_password,
                db_name,
                db_user,
                db_password,
                db_root_password,
                recreate_existing,
            ),
            daemon=True,
        )
        worker.start()

        self._poll_setup_worker_queue(
            window=window,
            status_var=status_var,
            progress_var=progress_var,
            run_button=run_button,
            cancel_button=cancel_button,
            stop_button=stop_button,
            events=events,
            wp_container=wp_container,
            db_container=db_container,
            pma_container=pma_container,
            http_port=http_port_i,
            https_port=https_port_i,
            http_container_port=http_container_port_i,
            https_container_port=https_container_port_i,
            db_port=db_port_i,
            pma_port=pma_port_i,
            wp_user=wp_user,
            wp_password=wp_password,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            db_root_password=db_root_password,
            ip_red=ip_red,
        )

    def _run_setup_worker(
        self,
        events: queue.Queue[tuple[str, object]],
        stop_event: threading.Event,
        wp_container: str,
        db_container: str,
        pma_container: str,
        network_name: str,
        wp_volume: str,
        db_volume: str,
        http_port: int,
        https_port: int,
        http_container_port: int,
        https_container_port: int,
        db_port: int,
        pma_port: int,
        ip_red: str,
        dominio_produccion: str,
        wp_user: str,
        wp_password: str,
        db_name: str,
        db_user: str,
        db_password: str,
        db_root_password: str,
        recreate_existing: bool,
    ) -> None:
        try:
            def check_cancel() -> None:
                if stop_event.is_set():
                    raise RuntimeError("SETUP_CANCELLED_BY_USER")

            def run_checked(args: list[str], error_message: str) -> None:
                code, _out, err = self._run(args)
                if code != 0:
                    raise RuntimeError(err or error_message)

            def ensure_started(container_name: str) -> None:
                self._run(["docker", "start", container_name])

            wp_exists = self._container_exists(wp_container)
            db_exists = self._container_exists(db_container)
            pma_exists = self._container_exists(pma_container)

            if recreate_existing:
                events.put(("progress", (8.0, "[1/8] Limpiando instalacion anterior...")))
                for cname in (wp_container, db_container, pma_container):
                    if self._container_exists(cname):
                        run_checked(["docker", "rm", "-f", cname], f"No se pudo eliminar contenedor {cname}")

                leftovers = [
                    cname
                    for cname in (wp_container, db_container, pma_container)
                    if self._container_exists(cname)
                ]
                if leftovers:
                    raise RuntimeError(
                        "No se pudieron eliminar estos contenedores: " + ", ".join(leftovers)
                    )

                self._run(["docker", "volume", "rm", wp_volume, db_volume])
                self._run(["docker", "network", "rm", network_name])
            else:
                events.put(("progress", (8.0, "[1/8] Revisando recursos existentes (sin borrar)...")))

            check_cancel()
            events.put(("progress", (18.0, "[2/8] Creando network y volumenes...")))
            if recreate_existing or not self._network_exists(network_name):
                run_checked(["docker", "network", "create", network_name], "No se pudo crear la network")
            if recreate_existing or not self._volume_exists(db_volume):
                run_checked(["docker", "volume", "create", db_volume], "No se pudo crear volumen MariaDB")
            if recreate_existing or not self._volume_exists(wp_volume):
                run_checked(["docker", "volume", "create", wp_volume], "No se pudo crear volumen WordPress")

            check_cancel()
            events.put(("progress", (30.0, "[3/8] Iniciando MariaDB...")))
            db_created_now = False
            if recreate_existing or not db_exists:
                run_checked(
                    [
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        db_container,
                        "--network",
                        network_name,
                        "-v",
                        f"{db_volume}:/bitnami/mariadb",
                        "-e",
                        f"MARIADB_ROOT_PASSWORD={db_root_password}",
                        "-e",
                        f"MARIADB_DATABASE={db_name}",
                        "-e",
                        f"MARIADB_USER={db_user}",
                        "-e",
                        f"MARIADB_PASSWORD={db_password}",
                        "-p",
                        f"{db_port}:3306",
                        "bitnami/mariadb:latest",
                    ],
                    "No se pudo iniciar contenedor MariaDB",
                )
                db_created_now = True
            else:
                ensure_started(db_container)

            check_cancel()
            events.put(("progress", (42.0, "[4/8] Esperando MariaDB...")))
            self._wait_mariadb_ready(stop_event, db_container, db_user, db_password)

            check_cancel()
            events.put(("progress", (66.0, "[6/8] Iniciando WordPress...")))
            wp_created_now = False
            if recreate_existing or not wp_exists:
                events.put(("progress", (52.0, "[5/8] Preparando permisos del volumen WordPress...")))
                run_checked(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-u",
                        "root",
                        "-v",
                        f"{wp_volume}:/bitnami/wordpress",
                        "--entrypoint",
                        "sh",
                        "bitnami/wordpress:latest",
                        "-c",
                        "chmod -R 777 /bitnami/wordpress && chown -R 1001:1001 /bitnami/wordpress",
                    ],
                    "No se pudieron preparar permisos de WordPress",
                )

                check_cancel()
                events.put(("progress", (66.0, "[6/8] Iniciando WordPress...")))
                run_checked(
                    [
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        wp_container,
                        "--network",
                        network_name,
                        "-v",
                        f"{wp_volume}:/bitnami/wordpress",
                        "-e",
                        f"WORDPRESS_DATABASE_HOST={db_container}",
                        "-e",
                        f"WORDPRESS_DATABASE_USER={db_user}",
                        "-e",
                        f"WORDPRESS_DATABASE_NAME={db_name}",
                        "-e",
                        f"WORDPRESS_DATABASE_PASSWORD={db_password}",
                        "-e",
                        f"WORDPRESS_USERNAME={wp_user}",
                        "-e",
                        f"WORDPRESS_PASSWORD={wp_password}",
                        "-p",
                        f"{http_port}:{http_container_port}",
                        "-p",
                        f"{https_port}:{https_container_port}",
                        "bitnami/wordpress:latest",
                    ],
                    "No se pudo iniciar contenedor WordPress",
                )
                wp_created_now = True
            else:
                ensure_started(wp_container)

            check_cancel()
            events.put(("progress", (78.0, "[7/8] Esperando WordPress y ajustando URLs...")))
            access_host = self._access_host_for_urls()
            local_url = f"http://{access_host}:{http_port}"
            red_host = ip_red.strip()
            if ":" in red_host and not red_host.startswith("["):
                red_host = f"[{red_host}]"
            red_url = f"http://{red_host}:{http_port}"
            wp_path = "/opt/bitnami/wordpress"
            self._wait_wordpress_ready(stop_event, wp_container, local_url)

            if recreate_existing or wp_created_now:
                # Replica el flujo del .bat: dominio->local, luego local->red.
                if dominio_produccion:
                    self._run(
                        [
                            "docker",
                            "exec",
                            wp_container,
                            "wp",
                            "search-replace",
                            dominio_produccion,
                            local_url,
                            "--allow-root",
                            f"--path={wp_path}",
                            "--quiet",
                        ]
                    )
                if local_url != red_url:
                    self._run(
                        [
                            "docker",
                            "exec",
                            wp_container,
                            "wp",
                            "search-replace",
                            local_url,
                            red_url,
                            "--allow-root",
                            f"--path={wp_path}",
                            "--quiet",
                        ]
                    )

                check_cancel()
                events.put(("progress", (86.0, "[7/8] Reiniciando WordPress y esperando...")))
                self._run(["docker", "restart", wp_container])
                self._wait_wordpress_ready(stop_event, wp_container, local_url)
            else:
                events.put(("progress", (86.0, "[7/8] WordPress existente detectado: se omite reconfiguracion de URL.")))

            check_cancel()
            events.put(("progress", (92.0, "[8/8] Iniciando phpMyAdmin...")))
            if recreate_existing or not pma_exists:
                run_checked(
                    [
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        pma_container,
                        "--network",
                        network_name,
                        "-e",
                        f"PMA_HOST={db_container}",
                        "-e",
                        "PMA_PORT=3306",
                        "-p",
                        f"{pma_port}:80",
                        "phpmyadmin:latest",
                    ],
                    "No se pudo iniciar contenedor phpMyAdmin",
                )
            else:
                ensure_started(pma_container)

            events.put(("done", None))
        except Exception as exc:
            events.put(("error", str(exc)))

    def _wait_mariadb_ready(
        self,
        stop_event: threading.Event,
        db_container: str,
        db_user: str,
        db_password: str,
        max_attempts: int | None = None,
    ) -> None:
        u = self._sh_single_quote(db_user)
        p = self._sh_single_quote(db_password)
        probe_cmd = (
            "if [ -x /opt/bitnami/mariadb/bin/mariadb ]; then "
            f"/opt/bitnami/mariadb/bin/mariadb -h 127.0.0.1 -u {u} -p{p} -e 'SELECT 1;'; "
            "else "
            f"mysql -h 127.0.0.1 -u {u} -p{p} -e 'SELECT 1;'; "
            "fi"
        )
        attempts = 0
        while True:
            if stop_event.is_set():
                raise RuntimeError("SETUP_CANCELLED_BY_USER")
            code, _out, _err = self._run(
                [
                    "docker",
                    "exec",
                    db_container,
                    "sh",
                    "-c",
                    probe_cmd,
                ]
            )
            if code == 0:
                return
            attempts += 1
            if max_attempts is not None and attempts >= max_attempts:
                raise RuntimeError("MariaDB no respondio dentro del tiempo esperado")
            time.sleep(3)

    def _wait_http_ready(self, stop_event: threading.Event, url: str, timeout_seconds: int | None = None) -> None:
        deadline = (time.time() + timeout_seconds) if timeout_seconds is not None else None
        while True:
            if deadline is not None and time.time() >= deadline:
                break
            if stop_event.is_set():
                raise RuntimeError("SETUP_CANCELLED_BY_USER")
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=4) as response:
                    if 200 <= int(response.status) < 400:
                        return
            except urllib.error.URLError:
                pass
            except Exception:
                pass
            time.sleep(3)
        raise RuntimeError("WordPress no respondio dentro del tiempo esperado")

    def _wait_wordpress_ready(
        self,
        stop_event: threading.Event,
        wp_container: str,
        url: str,
        timeout_seconds: int | None = None,
    ) -> None:
        # En remoto, localhost del cliente no representa al daemon remoto.
        # Validamos disponibilidad con wp-cli dentro del propio contenedor.
        if self.docker_mode == "remote":
            deadline = (time.time() + timeout_seconds) if timeout_seconds is not None else None
            while True:
                if deadline is not None and time.time() >= deadline:
                    break
                if stop_event.is_set():
                    raise RuntimeError("SETUP_CANCELLED_BY_USER")
                code, _out, _err = self._run(
                    [
                        "docker",
                        "exec",
                        wp_container,
                        "wp",
                        "core",
                        "is-installed",
                        "--allow-root",
                        "--path=/opt/bitnami/wordpress",
                    ]
                )
                if code == 0:
                    return
                time.sleep(3)
            raise RuntimeError("WordPress no estuvo listo dentro del tiempo esperado (modo remoto).")

        self._wait_http_ready(stop_event, url, timeout_seconds=timeout_seconds)

    def _poll_setup_worker_queue(
        self,
        window: tk.Toplevel,
        status_var: tk.StringVar,
        progress_var: tk.DoubleVar,
        run_button: ttk.Button,
        cancel_button: ttk.Button,
        stop_button: ttk.Button,
        events: queue.Queue[tuple[str, object]],
        wp_container: str,
        db_container: str,
        pma_container: str,
        http_port: int,
        https_port: int,
        http_container_port: int,
        https_container_port: int,
        db_port: int,
        pma_port: int,
        wp_user: str,
        wp_password: str,
        db_name: str,
        db_user: str,
        db_password: str,
        db_root_password: str,
        ip_red: str,
    ) -> None:
        if not window.winfo_exists():
            return

        completed = False
        failed: str | None = None

        while True:
            try:
                kind, payload = events.get_nowait()
            except queue.Empty:
                break

            if kind == "progress":
                value, text = payload  # type: ignore[misc]
                progress_var.set(float(value))
                status_var.set(str(text))
            elif kind == "done":
                completed = True
            elif kind == "error":
                failed = str(payload)

        if completed:
            stop_button.configure(state="disabled")
            progress_var.set(100)
            status_var.set("Entorno creado correctamente.")
            self.log_event("SETUP", wp_container, "OK", "Entorno recreado desde asistente GUI")
            self.refresh_everything()
            access_host = self._access_host_for_urls()
            messagebox.showinfo(
                "Crear/Recrear",
                (
                    "Entorno creado correctamente.\n\n"
                    f"WordPress: http://{access_host}:{http_port}\n"
                    f"WordPress HTTPS: https://{access_host}:{https_port}\n"
                    f"WordPress red: http://{ip_red}:{http_port}\n"
                    f"WordPress red HTTPS: https://{ip_red}:{https_port}\n"
                    f"phpMyAdmin: http://{access_host}:{pma_port}\n"
                    f"phpMyAdmin red: http://{ip_red}:{pma_port}\n"
                    f"Mapeo HTTP: {http_port}->{http_container_port}\n"
                    f"Mapeo HTTPS: {https_port}->{https_container_port}\n"
                    f"DB: {access_host}:{db_port}\n\n"
                    f"Contenedores: {wp_container}, {db_container}, {pma_container}\n"
                    f"Usuario WP: {wp_user}\n"
                    f"Password WP: {wp_password}\n"
                    f"Nombre DB: {db_name}\n"
                    f"Usuario DB: {db_user}\n"
                    f"Password DB: {db_password}\n"
                    f"Root password DB: {db_root_password}"
                ),
            )
            ask_import = messagebox.askyesno("Crear/Recrear", "Deseas importar un backup ahora?")
            self._close_work_tab("setup")
            if ask_import:
                self.open_import_wizard()
            return

        if failed is not None:
            stop_button.configure(state="disabled")
            run_button.configure(state="normal")
            cancel_button.configure(state="normal")
            if failed == "SETUP_CANCELLED_BY_USER":
                status_var.set("Operacion cancelada por el usuario.")
                messagebox.showinfo("Crear/Recrear", "Operacion cancelada por el usuario.")
                return
            self.log_event("SETUP", wp_container or "global", "ERROR", failed)
            self.refresh_history()
            status_var.set(f"Error: {failed}")
            messagebox.showerror("Crear/Recrear", f"No se pudo completar el entorno.\n\n{failed}")
            return

        window.after(
            150,
            lambda: self._poll_setup_worker_queue(
                window=window,
                status_var=status_var,
                progress_var=progress_var,
                run_button=run_button,
                cancel_button=cancel_button,
                stop_button=stop_button,
                events=events,
                wp_container=wp_container,
                db_container=db_container,
                pma_container=pma_container,
                http_port=http_port,
                https_port=https_port,
                http_container_port=http_container_port,
                https_container_port=https_container_port,
                db_port=db_port,
                pma_port=pma_port,
                wp_user=wp_user,
                wp_password=wp_password,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                db_root_password=db_root_password,
                ip_red=ip_red,
            ),
        )

    def _list_containers_details(self) -> list[tuple[str, str, str]]:
        code, out, _ = self._run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}|{{.Image}}"])
        if code != 0 or not out:
            return []

        result: list[tuple[str, str, str]] = []
        for line in out.splitlines():
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            name = parts[0].strip()
            status = parts[1].strip()
            image = parts[2].strip()
            if name:
                result.append((name, status, image))
        return result

    def _is_container_running(self, container: str) -> bool:
        code, out, _ = self._run(["docker", "inspect", "--format", "{{.State.Running}}", container])
        return code == 0 and out.strip().lower() == "true"

    def _container_exists(self, container_name: str) -> bool:
        code, out, _ = self._run(["docker", "ps", "-a", "--format", "{{.Names}}"])
        if code != 0 or not out:
            return False
        target = container_name.strip().lstrip("/").casefold()
        return any(line.strip().lstrip("/").casefold() == target for line in out.splitlines())

    def _network_exists(self, network_name: str) -> bool:
        code, out, _ = self._run(["docker", "network", "ls", "--format", "{{.Name}}"])
        if code != 0 or not out:
            return False
        target = network_name.strip().lstrip("/").casefold()
        return any(line.strip().lstrip("/").casefold() == target for line in out.splitlines())

    def _volume_exists(self, volume_name: str) -> bool:
        code, out, _ = self._run(["docker", "volume", "ls", "--format", "{{.Name}}"])
        if code != 0 or not out:
            return False
        target = volume_name.strip().lstrip("/").casefold()
        return any(line.strip().lstrip("/").casefold() == target for line in out.splitlines())

    @staticmethod
    def _extract_host_port(port_output: str) -> str | None:
        for line in port_output.splitlines():
            match = re.search(r":(\d+)\s*$", line.strip())
            if match:
                return match.group(1)
        return None

    def _access_host_for_urls(self) -> str:
        if self.docker_mode == "remote" and self.docker_host:
            parsed = self._extract_host_port_from_docker_host(self.docker_host)
            if parsed is not None:
                host, _port = parsed
                if ":" in host and not host.startswith("["):
                    return f"[{host}]"
                return host
        return "localhost"

    def _detect_wordpress_local_url(self, wp_container: str) -> str | None:
        access_host = self._access_host_for_urls()
        for internal_port in ("8080", "80"):
            code, out, _ = self._run(["docker", "port", wp_container, internal_port])
            if code == 0 and out.strip():
                port = self._extract_host_port(out)
                if port:
                    return f"http://{access_host}:{port}"

        code, out, _ = self._run(["docker", "port", wp_container])
        if code == 0 and out.strip():
            port = self._extract_host_port(out)
            if port:
                return f"http://{access_host}:{port}"
        return None

    def _detect_db_credentials(self, db_container: str) -> tuple[str, str]:
        code, out, _ = self._run(["docker", "exec", db_container, "env"])
        if code != 0 or not out:
            return "admin", "admin"

        env_map: dict[str, str] = {}
        for line in out.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_map[k.strip()] = v.strip()

        # Prioriza root si existe; si no, usuario normal.
        root_pass = env_map.get("MARIADB_ROOT_PASSWORD") or env_map.get("MYSQL_ROOT_PASSWORD")
        if root_pass:
            return "root", root_pass

        user = env_map.get("MARIADB_USER") or env_map.get("MYSQL_USER") or "admin"
        pwd = env_map.get("MARIADB_PASSWORD") or env_map.get("MYSQL_PASSWORD") or "admin"
        return user, pwd

    def _list_databases(self, db_container: str, db_user: str, db_password: str) -> list[str]:
        u = self._sh_single_quote(db_user)
        p = self._sh_single_quote(db_password)
        list_cmd = (
            "if [ -x /opt/bitnami/mariadb/bin/mariadb ]; then "
            f"/opt/bitnami/mariadb/bin/mariadb -h 127.0.0.1 -u {u} -p{p} -N -e 'SHOW DATABASES;'; "
            "else "
            f"mysql -h 127.0.0.1 -u {u} -p{p} -N -e 'SHOW DATABASES;'; "
            "fi"
        )
        code, out, _ = self._run(
            [
                "docker",
                "exec",
                db_container,
                "sh",
                "-c",
                list_cmd,
            ]
        )
        if code != 0 or not out:
            return []

        ignored = {"information_schema", "performance_schema", "mysql", "sys", "test"}
        return [line.strip() for line in out.splitlines() if line.strip() and line.strip().lower() not in ignored]

    @staticmethod
    def _sh_single_quote(value: str) -> str:
        return "'" + value.replace("'", "'\"'\"'") + "'"

    def _set_import_status(self, status_var: tk.StringVar, window: tk.Toplevel, text: str) -> None:
        status_var.set(text)
        window.update_idletasks()

    def _ensure_running_for_import(self, container: str, role_label: str) -> bool:
        if self._is_container_running(container):
            return True

        if not messagebox.askyesno(
            "Importar",
            f"El contenedor {role_label} '{container}' esta apagado.\n\nQuieres arrancarlo ahora?",
        ):
            return False

        code, _, err = self._run(["docker", "start", container])
        if code != 0:
            messagebox.showerror("Importar", err or f"No se pudo arrancar {container}.")
            return False
        return True

    def open_import_wizard(self) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return

        access_host = self._access_host_for_urls()

        details = self._list_containers_details()
        if not details:
            messagebox.showwarning("Importar", "No hay contenedores disponibles.")
            return

        wp_candidates = [name for (name, _status, image) in details if "wordpress" in (name + " " + image).lower()]
        db_candidates = [
            name
            for (name, _status, image) in details
            if any(token in (name + " " + image).lower() for token in ("mariadb", "mysql"))
        ]
        all_names = [name for (name, _status, _image) in details]

        if not wp_candidates:
            wp_candidates = all_names[:]
        if not db_candidates:
            db_candidates = all_names[:]

        window = self._open_or_focus_work_tab("import", "Importar")
        if window is None:
            messagebox.showerror("Interfaz", "No se pudo abrir la pestaña de Importar.")
            return

        for child in window.winfo_children():
            child.destroy()

        outer = self._create_scrollable_surface(window, padding=(8, 8))
        outer.columnconfigure(1, weight=1)
        self._add_work_tab_header(outer, "Asistente de importacion WordPress", "import")

        wp_container_var = tk.StringVar(value=wp_candidates[0] if wp_candidates else "")
        db_container_var = tk.StringVar(value=db_candidates[0] if db_candidates else "")
        db_user_var = tk.StringVar(value="admin")
        db_password_var = tk.StringVar(value="admin")
        db_name_var = tk.StringVar(value="wordpress")
        local_url_var = tk.StringVar(value=f"http://{access_host}:8181")
        domain_var = tk.StringVar(value="https://tudominio.com")
        wp_content_path_var = tk.StringVar(value="")
        sql_path_var = tk.StringVar(value="")
        status_var = tk.StringVar(value="Configura los datos y pulsa Importar.")

        row = 1
        ttk.Label(outer, text="Contenedor WordPress:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        wp_combo = ttk.Combobox(outer, textvariable=wp_container_var, values=wp_candidates, state="readonly")
        wp_combo.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(outer, text="Detectar URL local", command=lambda: self._detect_local_url_in_wizard(wp_container_var, local_url_var)).grid(row=row, column=2, padx=(8, 0), pady=4)

        row += 1
        ttk.Label(outer, text="Contenedor MariaDB/MySQL:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        db_combo = ttk.Combobox(outer, textvariable=db_container_var, values=db_candidates, state="readonly")
        db_combo.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(
            outer,
            text="Detectar credenciales",
            command=lambda: self._detect_db_credentials_in_wizard(db_container_var, db_user_var, db_password_var),
        ).grid(row=row, column=2, padx=(8, 0), pady=4)

        row += 1
        ttk.Label(outer, text="Usuario DB:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=db_user_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Password DB:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        self._add_password_entry_with_toggle(outer, db_password_var, row=row, column=1, pady=4)

        row += 1
        ttk.Label(outer, text="Base de datos:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        db_name_combo = ttk.Combobox(outer, textvariable=db_name_var, values=[db_name_var.get()])
        db_name_combo.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(
            outer,
            text="Cargar bases",
            command=lambda: self._load_databases_in_wizard(db_container_var, db_user_var, db_password_var, db_name_combo),
        ).grid(row=row, column=2, padx=(8, 0), pady=4)

        row += 1
        ttk.Label(outer, text="URL local actual:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=local_url_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Dominio del backup:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=domain_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="wp-content (carpeta/.tar/.zip):").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=wp_content_path_var).grid(row=row, column=1, sticky="ew", pady=4)
        wp_pick = ttk.Frame(outer)
        wp_pick.grid(row=row, column=2, padx=(8, 0), pady=4)
        ttk.Button(wp_pick, text="Archivo", command=lambda: self._pick_wp_content_file(wp_content_path_var)).pack(side="left")
        ttk.Button(wp_pick, text="Carpeta", command=lambda: self._pick_wp_content_folder(wp_content_path_var)).pack(side="left", padx=(6, 0))

        row += 1
        ttk.Label(outer, text="SQL (*.sql):").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=sql_path_var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(outer, text="Examinar", command=lambda: self._pick_sql_file(sql_path_var)).grid(row=row, column=2, padx=(8, 0), pady=4)

        row += 1
        skip_wp_var = tk.BooleanVar(value=False)
        skip_db_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            outer,
            text="Omitir subida de wp-content (importar solo DB)",
            variable=skip_wp_var,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 0))

        row += 1
        ttk.Checkbutton(
            outer,
            text="Omitir importacion SQL (importar solo wp-content)",
            variable=skip_db_var,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 0))

        row += 1
        import_debug_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            outer,
            text="Abrir consola debug durante importacion",
            variable=import_debug_var,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 0))

        row += 1
        ttk.Separator(outer, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 10))

        row += 1
        ttk.Label(outer, textvariable=status_var).grid(row=row, column=0, columnspan=3, sticky="w")

        row += 1
        import_progress_var = tk.DoubleVar(value=0)
        phase_status_var = tk.StringVar(value="Fase 0: Esperando inicio")
        import_progress = ttk.Progressbar(
            outer,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=import_progress_var,
        )
        import_progress.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        row += 1
        ttk.Label(outer, textvariable=phase_status_var, style="Muted.TLabel").grid(
            row=row,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(6, 0),
        )

        row += 1
        actions = ttk.Frame(outer)
        actions.grid(row=row, column=0, columnspan=3, sticky="e", pady=(10, 0))
        cancel_button = ttk.Button(actions, text="Cancelar", command=window.destroy)
        cancel_button.pack(side="right")
        stop_event = threading.Event()
        stop_button = ttk.Button(
            actions,
            text="Detener importacion",
            state="disabled",
            command=lambda: self._request_import_cancel(status_var, stop_event, stop_button),
        )
        stop_button.pack(side="right", padx=(0, 8))
        import_button = ttk.Button(
            actions,
            text="Importar ahora",
            command=lambda: self._run_import_from_wizard(
                window=window,
                status_var=status_var,
                phase_status_var=phase_status_var,
                progress_var=import_progress_var,
                import_button=import_button,
                cancel_button=cancel_button,
                stop_button=stop_button,
                stop_event=stop_event,
                wp_container=wp_container_var.get().strip(),
                db_container=db_container_var.get().strip(),
                db_user=db_user_var.get().strip(),
                db_password=db_password_var.get(),
                db_name=db_name_var.get().strip(),
                local_url=local_url_var.get().strip(),
                backup_domain=domain_var.get().strip(),
                wp_content_path=wp_content_path_var.get().strip(),
                sql_file_path=sql_path_var.get().strip(),
                skip_wp_upload=skip_wp_var.get(),
                skip_db_import=skip_db_var.get(),
                debug_enabled=import_debug_var.get(),
            ),
        )
        import_button.pack(side="right", padx=(0, 8))

        self._detect_local_url_in_wizard(wp_container_var, local_url_var, quiet=True)
        self._detect_db_credentials_in_wizard(db_container_var, db_user_var, db_password_var, quiet=True)

    def _detect_local_url_in_wizard(
        self,
        wp_container_var: tk.StringVar,
        local_url_var: tk.StringVar,
        quiet: bool = False,
    ) -> None:
        wp_container = wp_container_var.get().strip()
        if not wp_container:
            if not quiet:
                messagebox.showwarning("Importar", "Selecciona contenedor WordPress.")
            return

        if not self._ensure_running_for_import(wp_container, "WordPress"):
            return

        detected = self._detect_wordpress_local_url(wp_container)
        if detected:
            local_url_var.set(detected)
            if not quiet:
                messagebox.showinfo("Importar", f"URL local detectada: {detected}")
        elif not quiet:
            messagebox.showwarning("Importar", "No se pudo detectar URL local automaticamente.")

    def _detect_db_credentials_in_wizard(
        self,
        db_container_var: tk.StringVar,
        db_user_var: tk.StringVar,
        db_password_var: tk.StringVar,
        quiet: bool = False,
    ) -> None:
        db_container = db_container_var.get().strip()
        if not db_container:
            if not quiet:
                messagebox.showwarning("Importar", "Selecciona contenedor de base de datos.")
            return

        if not self._ensure_running_for_import(db_container, "Base de datos"):
            return

        user, pwd = self._detect_db_credentials(db_container)
        db_user_var.set(user)
        db_password_var.set(pwd)
        if not quiet:
            messagebox.showinfo("Importar", f"Credenciales detectadas: usuario={user}")

    def _load_databases_in_wizard(
        self,
        db_container_var: tk.StringVar,
        db_user_var: tk.StringVar,
        db_password_var: tk.StringVar,
        db_name_combo: ttk.Combobox,
    ) -> None:
        db_container = db_container_var.get().strip()
        db_user = db_user_var.get().strip()
        db_password = db_password_var.get()
        if not db_container or not db_user:
            messagebox.showwarning("Importar", "Completa contenedor DB y usuario.")
            return

        if not self._ensure_running_for_import(db_container, "Base de datos"):
            return

        dbs = self._list_databases(db_container, db_user, db_password)
        if not dbs:
            messagebox.showwarning("Importar", "No se pudieron listar bases de datos con esas credenciales.")
            return

        db_name_combo.configure(values=dbs)
        db_name_combo.set(dbs[0])

    def _pick_wp_content_file(self, target_var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar wp-content (.tar/.zip)",
            initialdir=self.tools_dir,
            filetypes=[("Archivo TAR/ZIP", "*.tar *.zip"), ("Todos los archivos", "*.*")],
        )
        if path:
            target_var.set(path)

    def _pick_wp_content_folder(self, target_var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Seleccionar carpeta wp-content", initialdir=self.tools_dir)
        if path:
            target_var.set(path)

    def _pick_sql_file(self, target_var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar archivo SQL",
            initialdir=self.tools_dir,
            filetypes=[("SQL", "*.sql"), ("Todos los archivos", "*.*")],
        )
        if path:
            target_var.set(path)

    def _pick_export_directory(self, target_var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Seleccionar carpeta de salida", initialdir=self.tools_dir)
        if path:
            target_var.set(path)

    @staticmethod
    def _default_export_folder() -> str:
        return os.path.join(os.path.expanduser("~"), "Desktop", "wordpress-export")

    @staticmethod
    def _build_timestamped_export_folder(base_dir: str) -> str:
        base = os.path.abspath(base_dir)
        stamp = datetime.now().strftime("%Y_%m_%d_%H-%M")
        candidate = os.path.join(base, stamp)
        if not os.path.exists(candidate):
            return candidate

        suffix = 1
        while True:
            candidate_with_suffix = os.path.join(base, f"{stamp}_{suffix:02d}")
            if not os.path.exists(candidate_with_suffix):
                return candidate_with_suffix
            suffix += 1

    def open_export_wizard(self) -> None:
        if not self.docker_ready():
            messagebox.showerror("Docker", self._docker_unavailable_message())
            return

        access_host = self._access_host_for_urls()

        details = self._list_containers_details()
        if not details:
            messagebox.showwarning("Exportar", "No hay contenedores disponibles.")
            return

        wp_candidates = [name for (name, _status, image) in details if "wordpress" in (name + " " + image).lower()]
        db_candidates = [
            name
            for (name, _status, image) in details
            if any(token in (name + " " + image).lower() for token in ("mariadb", "mysql"))
        ]
        all_names = [name for (name, _status, _image) in details]

        if not wp_candidates:
            wp_candidates = all_names[:]
        if not db_candidates:
            db_candidates = all_names[:]

        window = self._open_or_focus_work_tab("export", "Exportar")
        if window is None:
            messagebox.showerror("Interfaz", "No se pudo abrir la pestaña de Exportar.")
            return

        for child in window.winfo_children():
            child.destroy()

        outer = self._create_scrollable_surface(window, padding=(8, 8))
        outer.columnconfigure(1, weight=1)
        self._add_work_tab_header(outer, "Asistente de exportacion WordPress", "export")

        wp_container_var = tk.StringVar(value=wp_candidates[0] if wp_candidates else "")
        db_container_var = tk.StringVar(value=db_candidates[0] if db_candidates else "")
        db_user_var = tk.StringVar(value="admin")
        db_password_var = tk.StringVar(value="admin")
        db_name_var = tk.StringVar(value="wordpress")
        local_url_var = tk.StringVar(value=f"http://{access_host}:8181")
        domain_var = tk.StringVar(value="https://tudominio.com")
        output_dir_var = tk.StringVar(value=self._default_export_folder())
        skip_url_replace_var = tk.BooleanVar(value=False)
        status_var = tk.StringVar(value="Configura los datos y pulsa Exportar.")
        progress_var = tk.DoubleVar(value=0)
        phase_status_var = tk.StringVar(value="Fase 0: Esperando inicio")
        stop_event = threading.Event()

        row = 1
        ttk.Label(outer, text="Contenedor WordPress:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(outer, textvariable=wp_container_var, values=wp_candidates, state="readonly").grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(outer, text="Detectar URL local", command=lambda: self._detect_local_url_in_wizard(wp_container_var, local_url_var)).grid(row=row, column=2, padx=(8, 0), pady=4)

        row += 1
        ttk.Label(outer, text="Contenedor MariaDB/MySQL:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(outer, textvariable=db_container_var, values=db_candidates, state="readonly").grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(
            outer,
            text="Detectar credenciales",
            command=lambda: self._detect_db_credentials_in_wizard(db_container_var, db_user_var, db_password_var),
        ).grid(row=row, column=2, padx=(8, 0), pady=4)

        row += 1
        ttk.Label(outer, text="Usuario DB:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=db_user_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Password DB:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        self._add_password_entry_with_toggle(outer, db_password_var, row=row, column=1, pady=4)

        row += 1
        ttk.Label(outer, text="Base de datos:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        db_name_combo = ttk.Combobox(outer, textvariable=db_name_var, values=[db_name_var.get()])
        db_name_combo.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(
            outer,
            text="Cargar bases",
            command=lambda: self._load_databases_in_wizard(db_container_var, db_user_var, db_password_var, db_name_combo),
        ).grid(row=row, column=2, padx=(8, 0), pady=4)

        row += 1
        ttk.Label(outer, text="URL local actual:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=local_url_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Dominio produccion:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=domain_var).grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        ttk.Label(outer, text="Carpeta destino:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=output_dir_var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(outer, text="Examinar", command=lambda: self._pick_export_directory(output_dir_var)).grid(row=row, column=2, padx=(8, 0), pady=4)

        row += 1
        ttk.Checkbutton(
            outer,
            text="No tocar URLs (omitir search-replace)",
            variable=skip_url_replace_var,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 4))

        row += 1
        ttk.Separator(outer, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 10))

        row += 1
        ttk.Label(outer, textvariable=status_var).grid(row=row, column=0, columnspan=3, sticky="w")

        row += 1
        ttk.Progressbar(outer, orient="horizontal", mode="determinate", maximum=100, variable=progress_var).grid(
            row=row,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )

        row += 1
        ttk.Label(outer, textvariable=phase_status_var, style="Muted.TLabel").grid(
            row=row,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(6, 0),
        )

        row += 1
        actions = ttk.Frame(outer)
        actions.grid(row=row, column=0, columnspan=3, sticky="e", pady=(10, 0))
        cancel_button = ttk.Button(actions, text="Cancelar", command=lambda: self._close_work_tab("export"))
        cancel_button.pack(side="right")
        stop_button = ttk.Button(
            actions,
            text="Detener exportacion",
            state="disabled",
            command=lambda: self._request_import_cancel(status_var, stop_event, stop_button),
        )
        stop_button.pack(side="right", padx=(0, 8))
        export_button = ttk.Button(
            actions,
            text="Exportar ahora",
            command=lambda: self._run_export_from_wizard(
                status_var=status_var,
                phase_status_var=phase_status_var,
                progress_var=progress_var,
                export_button=export_button,
                cancel_button=cancel_button,
                stop_button=stop_button,
                stop_event=stop_event,
                wp_container=wp_container_var.get().strip(),
                db_container=db_container_var.get().strip(),
                db_user=db_user_var.get().strip(),
                db_password=db_password_var.get(),
                db_name=db_name_var.get().strip(),
                local_url=local_url_var.get().strip(),
                backup_domain=domain_var.get().strip(),
                output_dir=output_dir_var.get().strip(),
                skip_url_replace=skip_url_replace_var.get(),
            ),
        )
        export_button.pack(side="right", padx=(0, 8))

        self._detect_local_url_in_wizard(wp_container_var, local_url_var, quiet=True)
        self._detect_db_credentials_in_wizard(db_container_var, db_user_var, db_password_var, quiet=True)

    def _run_export_from_wizard(
        self,
        status_var: tk.StringVar,
        phase_status_var: tk.StringVar,
        progress_var: tk.DoubleVar,
        export_button: ttk.Button,
        cancel_button: ttk.Button,
        stop_button: ttk.Button,
        stop_event: threading.Event,
        wp_container: str,
        db_container: str,
        db_user: str,
        db_password: str,
        db_name: str,
        local_url: str,
        backup_domain: str,
        output_dir: str,
        skip_url_replace: bool,
    ) -> None:
        if not wp_container or not db_container:
            messagebox.showwarning("Exportar", "Selecciona contenedor WordPress y contenedor DB.")
            return
        if not db_user or not db_name:
            messagebox.showwarning("Exportar", "Completa usuario y base de datos.")
            return
        if not local_url or not backup_domain:
            messagebox.showwarning("Exportar", "Completa URL local y dominio de produccion.")
            return
        if not output_dir:
            messagebox.showwarning("Exportar", "Selecciona carpeta de destino.")
            return

        final_output_dir = self._build_timestamped_export_folder(output_dir)

        summary = (
            "Se exportara WordPress a una carpeta local.\n\n"
            f"WordPress: {wp_container}\n"
            f"Base de datos: {db_container}\n"
            f"BD: {db_name}\n"
            f"Carpeta base elegida: {output_dir}\n"
            f"Carpeta final del export: {final_output_dir}\n"
            f"Cambio URL temporal: {'NO (omitido)' if skip_url_replace else f'{local_url} -> {backup_domain}'}\n"
        )
        if not messagebox.askyesno("Confirmar exportacion", summary):
            return

        if not self._ensure_running_for_import(wp_container, "WordPress"):
            return
        if not self._ensure_running_for_import(db_container, "Base de datos"):
            return

        export_button.configure(state="disabled")
        cancel_button.configure(state="disabled")
        stop_button.configure(state="normal")
        stop_event.clear()
        progress_var.set(0)
        status_var.set("Iniciando exportacion...")
        phase_state = {"base": "Fase 1: Preparando exportacion", "dots": 0, "step_pct": 0}
        phase_status_var.set(f"{phase_state['base']} (0%)")

        events: queue.Queue[tuple[str, object]] = queue.Queue()
        worker = threading.Thread(
            target=self._run_export_worker,
            args=(
                events,
                stop_event,
                wp_container,
                db_container,
                db_user,
                db_password,
                db_name,
                local_url,
                backup_domain,
                final_output_dir,
                skip_url_replace,
            ),
            daemon=True,
        )
        worker.start()

        self._poll_export_worker_queue(
            status_var=status_var,
            phase_status_var=phase_status_var,
            phase_state=phase_state,
            progress_var=progress_var,
            export_button=export_button,
            cancel_button=cancel_button,
            stop_button=stop_button,
            events=events,
            wp_container=wp_container,
        )

    def _run_export_worker(
        self,
        events: queue.Queue[tuple[str, object]],
        stop_event: threading.Event,
        wp_container: str,
        db_container: str,
        db_user: str,
        db_password: str,
        db_name: str,
        local_url: str,
        backup_domain: str,
        output_dir: str,
        skip_url_replace: bool,
    ) -> None:
        restore_needed = False
        try:
            def check_cancel() -> None:
                if stop_event.is_set():
                    raise RuntimeError("EXPORT_CANCELLED_BY_USER")

            total_steps = 4

            os.makedirs(output_dir, exist_ok=True)

            check_cancel()
            events.put(("phase", "Fase 1: Ajustando URL temporal para exportar"))
            if not skip_url_replace and local_url != backup_domain:
                code, _, err = self._run_import_progress_task(
                    events=events,
                    step_index=1,
                    total_steps=total_steps,
                    label="Ajustando URL temporal para exportar...",
                    start_pct=2.0,
                    end_pct=15.0,
                    expected_seconds=6.0,
                    task=lambda: self._run(
                        [
                            "docker",
                            "exec",
                            wp_container,
                            "wp",
                            "search-replace",
                            local_url,
                            backup_domain,
                            "--allow-root",
                            "--path=/opt/bitnami/wordpress",
                        ]
                    ),
                )
                if code != 0:
                    raise RuntimeError(err or "No se pudo ajustar URL para exportar")
                restore_needed = True
            elif skip_url_replace:
                events.put(("progress", (15.0, "[1/4] Omitido cambio de URL (segun seleccion)... (100% - omitido)")))
            else:
                events.put(("progress", (15.0, "[1/4] URL temporal ya coincide con destino... (100% - sin cambios)")))

            check_cancel()
            events.put(("phase", "Fase 2: Exportando base de datos"))
            dump_cmd = f"mysqldump -h 127.0.0.1 -u {self._sh_single_quote(db_user)} -p{self._sh_single_quote(db_password)} {self._sh_single_quote(db_name)} > /tmp/export.sql"
            code, _, err = self._run_import_progress_task(
                events=events,
                step_index=2,
                total_steps=total_steps,
                label="Exportando base de datos...",
                start_pct=15.0,
                end_pct=45.0,
                expected_seconds=12.0,
                task=lambda: self._run(["docker", "exec", "-u", "root", db_container, "sh", "-c", dump_cmd]),
            )
            if code != 0:
                raise RuntimeError(err or "No se pudo crear dump SQL")
            sql_target = os.path.join(output_dir, "export.sql")
            copy_sql_seconds = self._estimate_transfer_seconds(sql_target, min_seconds=5.0, max_seconds=120.0)
            code, _, err = self._run_import_progress_task(
                events=events,
                step_index=2,
                total_steps=total_steps,
                label="Copiando export.sql al equipo local...",
                start_pct=45.0,
                end_pct=60.0,
                expected_seconds=copy_sql_seconds,
                task=lambda: self._run(["docker", "cp", f"{db_container}:/tmp/export.sql", sql_target]),
            )
            if code != 0:
                raise RuntimeError(err or "No se pudo copiar export.sql")

            check_cancel()
            events.put(("phase", "Fase 3: Exportando wp-content"))
            code, _, err = self._run_import_progress_task(
                events=events,
                step_index=3,
                total_steps=total_steps,
                label="Empaquetando wp-content...",
                start_pct=60.0,
                end_pct=75.0,
                expected_seconds=10.0,
                task=lambda: self._run(
                    [
                        "docker",
                        "exec",
                        "-u",
                        "root",
                        wp_container,
                        "sh",
                        "-c",
                        "tar chf /tmp/wp-content.tar -C /opt/bitnami/wordpress wp-content",
                    ]
                ),
            )
            if code != 0:
                raise RuntimeError(err or "No se pudo empaquetar wp-content")

            tar_path = os.path.join(output_dir, "wp-content.tar")
            wp_copy_seconds = self._estimate_transfer_seconds(tar_path, min_seconds=8.0, max_seconds=240.0)
            code, _, err = self._run_import_progress_task(
                events=events,
                step_index=3,
                total_steps=total_steps,
                label="Exportando wp-content...",
                start_pct=75.0,
                end_pct=92.0,
                expected_seconds=wp_copy_seconds,
                task=lambda: self._run(["docker", "cp", f"{wp_container}:/tmp/wp-content.tar", tar_path]),
            )
            if code != 0:
                raise RuntimeError(err or "No se pudo copiar wp-content.tar")

            try:
                with tarfile.open(tar_path, "r") as tar:
                    try:
                        tar.extractall(path=output_dir, filter="data")
                    except TypeError:
                        tar.extractall(path=output_dir)
            except Exception:
                # Mantener compatibilidad: el tar queda disponible aunque no se extraiga.
                pass

            check_cancel()
            events.put(("phase", "Fase 4: Restaurando URL local"))
            if restore_needed and not skip_url_replace:
                self._run_import_progress_task(
                    events=events,
                    step_index=4,
                    total_steps=total_steps,
                    label="Restaurando URL local...",
                    start_pct=92.0,
                    end_pct=99.0,
                    expected_seconds=6.0,
                    task=lambda: self._run(
                        [
                            "docker",
                            "exec",
                            wp_container,
                            "wp",
                            "search-replace",
                            backup_domain,
                            local_url,
                            "--allow-root",
                            "--path=/opt/bitnami/wordpress",
                        ]
                    ),
                )
            else:
                events.put(("progress", (99.0, "[4/4] Restaurando URL local... (100% - omitido)")))

            events.put(("done", output_dir))
        except Exception as exc:
            if restore_needed and not skip_url_replace:
                self._run(
                    [
                        "docker",
                        "exec",
                        wp_container,
                        "wp",
                        "search-replace",
                        backup_domain,
                        local_url,
                        "--allow-root",
                        "--path=/opt/bitnami/wordpress",
                    ]
                )
            events.put(("error", str(exc)))

    def _poll_export_worker_queue(
        self,
        status_var: tk.StringVar,
        phase_status_var: tk.StringVar,
        phase_state: dict[str, object],
        progress_var: tk.DoubleVar,
        export_button: ttk.Button,
        cancel_button: ttk.Button,
        stop_button: ttk.Button,
        events: queue.Queue[tuple[str, object]],
        wp_container: str,
    ) -> None:
        completed_output: str | None = None
        failed: str | None = None
        latest_progress: tuple[float, str] | None = None
        latest_phase: str | None = None
        processed = 0
        batch_limit = 120

        while processed < batch_limit:
            try:
                kind, payload = events.get_nowait()
            except queue.Empty:
                break
            processed += 1

            if kind == "progress":
                value, text = payload  # type: ignore[misc]
                latest_progress = (float(value), str(text))
                latest_phase = self._extract_export_phase_from_progress_text(str(text))
                phase_state["step_pct"] = self._extract_step_percent_from_progress_text(str(text))
            elif kind == "phase":
                latest_phase = str(payload)
                phase_state["step_pct"] = None
            elif kind == "done":
                completed_output = str(payload)
            elif kind == "error":
                failed = str(payload)

        if latest_phase:
            phase_state["base"] = latest_phase

        if latest_progress is not None:
            value, text = latest_progress
            progress_var.set(value)
            status_var.set(text)

        base_phase = str(phase_state.get("base") or "Fase activa: Ejecutando subproceso")
        step_pct = phase_state.get("step_pct")
        if isinstance(step_pct, int):
            phase_status_var.set(f"{base_phase} ({step_pct}%)")
        else:
            dots_count = int(phase_state.get("dots") or 0)
            phase_text, next_dots = self._next_phase_text_dots(base_phase, dots_count)
            phase_state["dots"] = next_dots
            phase_status_var.set(phase_text)

        if completed_output is not None:
            stop_button.configure(state="disabled")
            progress_var.set(100)
            status_var.set("Exportacion completada correctamente.")
            phase_status_var.set("Fase 4: Completado (100%)")
            self.log_event("EXPORT", wp_container, "OK", f"Exportado en {completed_output}")
            self.refresh_history()
            messagebox.showinfo(
                "Exportar",
                (
                    "Exportacion completada correctamente.\n\n"
                    f"Carpeta: {completed_output}\n"
                    "Archivos esperados: export.sql, wp-content.tar y carpeta wp-content (si se pudo extraer)."
                ),
            )
            return

        if failed is not None:
            stop_button.configure(state="disabled")
            export_button.configure(state="normal")
            cancel_button.configure(state="normal")
            if failed == "EXPORT_CANCELLED_BY_USER":
                status_var.set("Exportacion cancelada por el usuario.")
                phase_status_var.set("Fase cancelada por el usuario")
                messagebox.showinfo("Exportar", "Exportacion cancelada por el usuario.")
                return
            self.log_event("EXPORT", wp_container or "global", "ERROR", failed)
            self.refresh_history()
            status_var.set(f"Error: {failed}")
            phase_status_var.set("Fase finalizada con error")
            messagebox.showerror("Exportar", f"La exportacion fallo.\n\n{failed}")
            return

        next_delay_ms = 40 if processed >= batch_limit else 150
        self.root.after(
            next_delay_ms,
            lambda: self._poll_export_worker_queue(
                status_var=status_var,
                phase_status_var=phase_status_var,
                phase_state=phase_state,
                progress_var=progress_var,
                export_button=export_button,
                cancel_button=cancel_button,
                stop_button=stop_button,
                events=events,
                wp_container=wp_container,
            ),
        )

    def _run_import_from_wizard(
        self,
        window: tk.Toplevel,
        status_var: tk.StringVar,
        phase_status_var: tk.StringVar,
        progress_var: tk.DoubleVar,
        import_button: ttk.Button,
        cancel_button: ttk.Button,
        stop_button: ttk.Button,
        stop_event: threading.Event,
        wp_container: str,
        db_container: str,
        db_user: str,
        db_password: str,
        db_name: str,
        local_url: str,
        backup_domain: str,
        wp_content_path: str,
        sql_file_path: str,
        skip_wp_upload: bool,
        skip_db_import: bool,
        debug_enabled: bool,
    ) -> None:
        import_wp = not skip_wp_upload
        import_db = not skip_db_import

        if not import_wp and not import_db:
            messagebox.showwarning("Importar", "Debes importar al menos wp-content o SQL.")
            return

        if not wp_container:
            messagebox.showwarning("Importar", "Selecciona contenedor WordPress.")
            return
        if import_db and not db_container:
            messagebox.showwarning("Importar", "Selecciona contenedor DB para importar SQL.")
            return
        if import_db and (not db_user or not db_name):
            messagebox.showwarning("Importar", "Completa usuario y nombre de base de datos.")
            return
        if import_db and (not local_url or not backup_domain):
            messagebox.showwarning("Importar", "Completa URL local y dominio del backup.")
            return
        if import_wp and (not wp_content_path or not os.path.exists(wp_content_path)):
            messagebox.showwarning("Importar", "Ruta de wp-content no valida.")
            return
        if import_db and (not sql_file_path or not os.path.isfile(sql_file_path)):
            messagebox.showwarning("Importar", "Archivo SQL no valido.")
            return

        wp_is_dir = os.path.isdir(wp_content_path)
        wp_lower = wp_content_path.lower()
        if import_wp and not wp_is_dir and not (wp_lower.endswith(".tar") or wp_lower.endswith(".zip")):
            messagebox.showwarning("Importar", "wp-content debe ser carpeta, .tar o .zip.")
            return

        summary = (
            "Se importaran datos y se sobrescribira contenido actual.\n\n"
            f"WordPress: {wp_container}\n"
            f"Base de datos: {db_container or '(omitida)'}\n"
            f"BD destino: {db_name or '(omitida)'}\n"
            f"wp-content: {wp_content_path if import_wp else '(omitido)'}\n"
            f"SQL: {sql_file_path if import_db else '(omitido)'}\n"
            f"Reemplazo URL: {f'{backup_domain} -> {local_url}' if import_db else '(omitido)'}\n"
        )
        if not messagebox.askyesno("Confirmar importacion", summary):
            return

        if not self._ensure_running_for_import(wp_container, "WordPress"):
            return
        if import_db and not self._ensure_running_for_import(db_container, "Base de datos"):
            return

        import_button.configure(state="disabled")
        cancel_button.configure(state="disabled")
        stop_button.configure(state="normal")
        stop_event.clear()
        progress_var.set(0)
        status_var.set("Iniciando importacion...")
        phase_state = {"base": "Fase 1: Preparando importacion", "dots": 0, "step_pct": 0}
        phase_status_var.set(f"{phase_state['base']} (0%)")
        debug_window: tk.Toplevel | None = None
        debug_text: tk.Text | None = None
        if debug_enabled:
            debug_window, debug_text = self._open_import_debug_console(window)
            self._append_import_debug(debug_window, debug_text, "DEBUG habilitado.")
            self._append_import_debug(debug_window, debug_text, f"WordPress: {wp_container}")
            self._append_import_debug(debug_window, debug_text, f"Base de datos: {db_container or '(omitida)'} ({db_name or '(omitida)'})")
            self._append_import_debug(debug_window, debug_text, f"wp-content: {wp_content_path if import_wp else '(omitido)'}")
            self._append_import_debug(debug_window, debug_text, f"SQL: {sql_file_path if import_db else '(omitido)'}")

        events: queue.Queue[tuple[str, object]] = queue.Queue()
        worker = threading.Thread(
            target=self._run_import_worker,
            args=(
                events,
                stop_event,
                wp_container,
                db_container,
                db_user,
                db_password,
                db_name,
                local_url,
                backup_domain,
                wp_content_path,
                sql_file_path,
                skip_wp_upload,
                skip_db_import,
            ),
            daemon=True,
        )
        worker.start()

        self._poll_import_worker_queue(
            window=window,
            status_var=status_var,
            phase_status_var=phase_status_var,
            phase_state=phase_state,
            progress_var=progress_var,
            import_button=import_button,
            cancel_button=cancel_button,
            stop_button=stop_button,
            events=events,
            wp_container=wp_container,
            db_name=db_name,
            debug_window=debug_window,
            debug_text=debug_text,
        )

    @staticmethod
    def _request_import_cancel(status_var: tk.StringVar, stop_event: threading.Event, stop_button: ttk.Button) -> None:
        stop_event.set()
        stop_button.configure(state="disabled")
        status_var.set("Cancelando importacion... esperando fin del paso actual")

    @staticmethod
    def _debug_timestamp() -> str:
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def _short_debug_text(value: str, max_len: int = 900) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def _open_import_debug_console(self, parent: tk.Toplevel) -> tuple[tk.Toplevel, tk.Text]:
        debug_window = tk.Toplevel(parent)
        debug_window.title("Debug importacion")
        debug_window.geometry("900x360")
        debug_window.transient(parent)

        body = ttk.Frame(debug_window, padding=8)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        debug_text = tk.Text(
            body,
            wrap="word",
            bg="#0b1220",
            fg="#cbd5e1",
            insertbackground="#cbd5e1",
            relief="flat",
            borderwidth=1,
            font=("Consolas", 10),
        )
        debug_text.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(body, orient="vertical", command=debug_text.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        debug_text.configure(yscrollcommand=y_scroll.set)

        actions = ttk.Frame(body)
        actions.grid(row=1, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(actions, text="Copiar log", command=lambda: self._copy_debug_text_to_clipboard(debug_window, debug_text)).pack(side="right", padx=(0, 8))
        ttk.Button(actions, text="Limpiar", command=lambda: self._clear_debug_text(debug_text)).pack(side="right")

        self._append_import_debug(debug_window, debug_text, "Consola de debug iniciada.")
        return debug_window, debug_text

    @staticmethod
    def _clear_debug_text(debug_text: tk.Text) -> None:
        if not debug_text.winfo_exists():
            return
        debug_text.configure(state="normal")
        debug_text.delete("1.0", "end")
        debug_text.configure(state="disabled")

    def _copy_debug_text_to_clipboard(self, debug_window: tk.Toplevel, debug_text: tk.Text) -> None:
        if not debug_window.winfo_exists() or not debug_text.winfo_exists():
            return
        content = debug_text.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Debug importacion", "No hay contenido para copiar.", parent=debug_window)
            return
        debug_window.clipboard_clear()
        debug_window.clipboard_append(content)
        messagebox.showinfo("Debug importacion", "Log copiado al portapapeles.", parent=debug_window)

    def _append_import_debug(self, debug_window: tk.Toplevel | None, debug_text: tk.Text | None, message: str) -> None:
        if debug_window is None or debug_text is None:
            return
        if not debug_window.winfo_exists() or not debug_text.winfo_exists():
            return
        line = f"[{self._debug_timestamp()}] {message.strip()}\n"
        debug_text.configure(state="normal")
        debug_text.insert("end", line)
        debug_text.see("end")
        debug_text.configure(state="disabled")

    @staticmethod
    def _next_phase_text_dots(base_text: str, dots: int) -> tuple[str, int]:
        next_dots = (dots + 1) % 3
        return f"{base_text}{'.' * (next_dots + 1)}", next_dots

    @staticmethod
    def _extract_step_percent_from_progress_text(progress_text: str) -> int | None:
        text = (progress_text or "").strip()
        if not text:
            return None
        match = re.search(r"\((\d{1,3})%(?:[^)]*)\)$", text)
        if not match:
            return None
        try:
            value = int(match.group(1))
        except Exception:
            return None
        return max(0, min(100, value))

    @staticmethod
    def _extract_phase_from_progress_text(progress_text: str) -> str:
        text = (progress_text or "").strip()
        if not text:
            return "Fase activa: Ejecutando subproceso"
        text = re.sub(r"^\[\d+/\d+\]\s*", "", text)
        text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
        lowered = text.lower()

        if "preparando contenedores" in lowered:
            return "Fase 1: Preparando contenedores"
        if "copiando wp-content" in lowered or "subiendo wp-content" in lowered:
            return "Fase 2: Enviando archivos a remoto"
        if "extrayendo wp-content" in lowered or "aplicando wp-content" in lowered or "permisos de wp-content" in lowered:
            return "Fase 3: Aplicando wp-content en WordPress"
        if "copiando sql" in lowered or "importando base de datos" in lowered:
            return "Fase 4: Importando base de datos"
        if "ajustando urls" in lowered:
            return "Fase 5: Ajustando URLs"
        if "reiniciando wordpress" in lowered:
            return "Fase 6: Reiniciando servicios y finalizando"
        return f"Fase activa: {text}"

    @staticmethod
    def _extract_export_phase_from_progress_text(progress_text: str) -> str:
        text = (progress_text or "").strip()
        if not text:
            return "Fase activa: Ejecutando subproceso"
        text = re.sub(r"^\[\d+/\d+\]\s*", "", text)
        text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
        lowered = text.lower()

        if "ajustando url temporal" in lowered or "omitido cambio de url" in lowered:
            return "Fase 1: Ajustando URL temporal para exportar"
        if "exportando base de datos" in lowered or "copiando export.sql" in lowered:
            return "Fase 2: Exportando base de datos"
        if "exportando wp-content" in lowered or "empaquetando wp-content" in lowered:
            return "Fase 3: Exportando wp-content"
        if "restaurando url local" in lowered:
            return "Fase 4: Restaurando URL local"
        return f"Fase activa: {text}"

    @staticmethod
    def _estimate_path_size_bytes(path: str) -> int:
        if not path:
            return 0
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            if os.path.isdir(path):
                total = 0
                for root, _dirs, files in os.walk(path):
                    for name in files:
                        file_path = os.path.join(root, name)
                        try:
                            total += os.path.getsize(file_path)
                        except OSError:
                            continue
                return total
        except OSError:
            return 0
        return 0

    @staticmethod
    def _estimate_transfer_seconds(path: str, min_seconds: float = 6.0, max_seconds: float = 180.0) -> float:
        size_bytes = WordPressUtilitiesApp._estimate_path_size_bytes(path)
        if size_bytes <= 0:
            return min_seconds
        # Estimacion conservadora para que el progreso no quede plano en ficheros grandes.
        estimated = size_bytes / (8.0 * 1024 * 1024)
        return max(min_seconds, min(max_seconds, estimated))

    @staticmethod
    def _format_gb(value_bytes: int) -> str:
        gb = max(0.0, float(value_bytes) / float(1024 ** 3))
        return f"{gb:.1f}".replace(".", ",")

    @staticmethod
    def _format_mbps(value_bps: float) -> str:
        mbps = max(0.0, float(value_bps) / float(1024 ** 2))
        return f"{mbps:.1f}".replace(".", ",")

    @staticmethod
    def _format_eta(seconds: float) -> str:
        secs = max(0, int(round(seconds)))
        mins, sec = divmod(secs, 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{sec:02d}"
        return f"{mins:02d}:{sec:02d}"

    def _run_import_upload_with_real_progress(
        self,
        events: queue.Queue[tuple[str, object]],
        step_index: int,
        total_steps: int,
        label: str,
        start_pct: float,
        end_pct: float,
        local_path: str,
        container_name: str,
        target_path: str,
    ) -> tuple[int, str, str]:
        client = self._get_docker_sdk_client(timeout_seconds=None)
        if client is None:
            return 1, "", "Docker SDK no disponible para progreso real de subida"

        status_prefix = f"[{step_index}/{total_steps}] {label}"
        events.put(("progress", (start_pct, f"{status_prefix} (0%)")))
        events.put(("phase", "Fase 2: Enviando archivos a remoto"))
        events.put(("debug", f"{status_prefix} | origen: {local_path}"))
        events.put(("debug", f"{status_prefix} | destino: {container_name}:{target_path}"))
        events.put(("debug", f"{status_prefix} preparando paquete TAR local..."))

        fd, temp_tar_path = tempfile.mkstemp(prefix="wpu_import_upload_", suffix=".tar")
        os.close(fd)
        try:
            target_norm = target_path.replace("\\", "/")
            parent_dir = os.path.dirname(target_norm.rstrip("/")) or "/"
            target_name = os.path.basename(target_norm.rstrip("/"))
            if not target_name:
                target_name = os.path.basename(local_path.rstrip("\\/"))

            source_total_bytes = max(1, self._estimate_path_size_bytes(local_path))
            full_span = max(0.0, end_pct - start_pct)
            pack_span = min(full_span * 0.45, 12.0)
            pack_end_pct = start_pct + pack_span
            pack_start_at = time.time()

            packed_bytes = 0
            last_pack_emit_at = 0.0
            last_pack_debug_at = 0.0

            def emit_pack_progress(force: bool = False) -> None:
                nonlocal last_pack_emit_at, last_pack_debug_at
                now = time.time()
                if (not force) and (now - last_pack_emit_at) < 0.8:
                    return
                last_pack_emit_at = now
                ratio = min(0.995, float(packed_bytes) / float(source_total_bytes))
                step_pct = min(99, int(ratio * 100))
                overall_pct = start_pct + (pack_span * ratio)
                phase_text = (
                    "Fase 2: Empaquetando localmente "
                    f"{self._format_gb(packed_bytes)}/{self._format_gb(source_total_bytes)} GB"
                )
                events.put(("progress", (overall_pct, f"{status_prefix} ({step_pct}%)")))
                events.put(("phase", phase_text))
                if force or (now - last_pack_debug_at) >= 5.0:
                    last_pack_debug_at = now
                    events.put(("debug", phase_text))

            with tarfile.open(temp_tar_path, mode="w") as tar:
                if os.path.isdir(local_path):
                    for root, _dirs, files in os.walk(local_path):
                        rel_root = os.path.relpath(root, local_path)
                        base_arc = target_name if rel_root == "." else f"{target_name}/{rel_root.replace('\\', '/')}"
                        for name in files:
                            file_path = os.path.join(root, name)
                            rel_file = name if rel_root == "." else f"{rel_root}/{name}"
                            arcname = f"{target_name}/{rel_file.replace('\\', '/')}"
                            try:
                                file_size = os.path.getsize(file_path)
                            except OSError:
                                file_size = 0
                            tar.add(file_path, arcname=arcname, recursive=False)
                            packed_bytes += max(0, file_size)
                            emit_pack_progress(force=False)
                    # Garantiza 100% de la subfase de empaquetado.
                    packed_bytes = source_total_bytes
                    emit_pack_progress(force=True)
                else:
                    tar.add(local_path, arcname=target_name, recursive=False)
                    packed_bytes = source_total_bytes
                    emit_pack_progress(force=True)

            pack_elapsed = max(0.1, time.time() - pack_start_at)
            events.put(("debug", f"{status_prefix} paquete TAR listo en {self._format_eta(pack_elapsed)}"))

            total_bytes = max(1, os.path.getsize(temp_tar_path))
            span = max(0.0, end_pct - pack_end_pct)
            last_sent = 0
            last_emit_at = 0.0
            upload_started_at = time.time()
            speed_anchor_sent = 0
            speed_anchor_at = upload_started_at
            avg_speed_bps = 0.0
            last_debug_emit_at = 0.0
            last_bytes_change_at = upload_started_at
            last_stall_report_at = 0.0

            class _ProgressReader:
                def __init__(self, file_obj: io.BufferedReader) -> None:
                    self.file_obj = file_obj
                    self.sent = 0

                def read(self, size: int = -1) -> bytes:
                    data = self.file_obj.read(size)
                    if data:
                        self.sent += len(data)
                    return data

            with open(temp_tar_path, "rb") as fh:
                reader = _ProgressReader(fh)
                container = client.containers.get(container_name)
                upload_done = threading.Event()
                upload_result: dict[str, object] = {"ok": False, "exc": None}

                events.put(("phase", f"Fase 2: Enviando archivos a remoto 0,0/{self._format_gb(total_bytes)} GB | 0,0 MB/s | ETA --:--"))

                def emit_progress(force: bool = False) -> None:
                    nonlocal last_sent, last_emit_at, speed_anchor_sent, speed_anchor_at, avg_speed_bps, last_debug_emit_at, last_bytes_change_at
                    sent = min(total_bytes, max(0, reader.sent))
                    now = time.time()
                    if not force:
                        if sent == last_sent and (now - last_emit_at) < 1.2:
                            return
                        if sent != last_sent and (now - last_emit_at) < 5.0:
                            return

                    delta_bytes = max(0, sent - speed_anchor_sent)
                    delta_time = max(0.0, now - speed_anchor_at)
                    if delta_bytes > 0 and delta_time > 0:
                        inst_bps = float(delta_bytes) / delta_time
                        if avg_speed_bps <= 0:
                            avg_speed_bps = inst_bps
                        else:
                            # Suaviza picos para mostrar una velocidad estable al usuario.
                            avg_speed_bps = (avg_speed_bps * 0.7) + (inst_bps * 0.3)
                        speed_anchor_sent = sent
                        speed_anchor_at = now
                        last_bytes_change_at = now

                    last_sent = sent
                    last_emit_at = now
                    ratio = min(0.999, sent / total_bytes)
                    step_pct = min(99, int(ratio * 100))
                    overall_pct = pack_end_pct + (span * ratio)
                    progress_text = f"{status_prefix} ({step_pct}%)"
                    elapsed_total = max(0.1, now - upload_started_at)
                    effective_speed = avg_speed_bps if avg_speed_bps > 0 else (float(sent) / elapsed_total)
                    remaining_bytes = max(0, total_bytes - sent)
                    eta_seconds = (remaining_bytes / effective_speed) if effective_speed > 0 else 0.0
                    phase_text = (
                        "Fase 2: Enviando archivos a remoto "
                        f"{self._format_gb(sent)}/{self._format_gb(total_bytes)} GB "
                        f"| {self._format_mbps(effective_speed)} MB/s "
                        f"| ETA {self._format_eta(eta_seconds)}"
                    )
                    events.put(("progress", (overall_pct, progress_text)))
                    # Enviamos fase despues para que no quede sobreescrita por el parser de progreso.
                    events.put(("phase", phase_text))
                    if force or (now - last_debug_emit_at) >= 5.0:
                        last_debug_emit_at = now
                        events.put(("debug", phase_text))

                def upload_worker() -> None:
                    try:
                        upload_result["ok"] = bool(container.put_archive(parent_dir, reader))
                    except Exception as ex:
                        upload_result["exc"] = ex
                    finally:
                        upload_done.set()

                uploader = threading.Thread(target=upload_worker, daemon=True)
                uploader.start()
                emit_progress(force=True)
                while not upload_done.wait(0.8):
                    emit_progress(force=False)
                    now = time.time()
                    stalled_for = now - last_bytes_change_at
                    if stalled_for >= 10.0 and (now - last_stall_report_at) >= 10.0:
                        last_stall_report_at = now
                        events.put(("debug", f"{status_prefix} esperando envio de datos... ({int(stalled_for)}s sin avance de bytes)"))
                emit_progress(force=True)
                uploader.join(timeout=1.0)

            upload_exc = upload_result.get("exc")
            if isinstance(upload_exc, Exception):
                raise upload_exc
            ok = bool(upload_result.get("ok", False))

            if not ok:
                return 1, "", "No se pudo copiar al contenedor"

            events.put(("progress", (end_pct, f"{status_prefix} (100%)")))
            total_elapsed = max(0.1, time.time() - upload_started_at)
            final_speed = float(total_bytes) / total_elapsed
            events.put(("phase", f"Fase 2: Enviando archivos a remoto {self._format_gb(total_bytes)}/{self._format_gb(total_bytes)} GB | {self._format_mbps(final_speed)} MB/s | ETA 00:00"))
            events.put(("debug", f"{status_prefix} finalizado en {self._format_eta(total_elapsed)}"))
            return 0, "", ""
        except Exception as exc:
            events.put(("debug", f"{status_prefix} ERROR: {exc}"))
            return 1, "", str(exc)
        finally:
            try:
                os.remove(temp_tar_path)
            except OSError:
                pass

    def _run_import_progress_task(
        self,
        events: queue.Queue[tuple[str, object]],
        step_index: int,
        total_steps: int,
        label: str,
        start_pct: float,
        end_pct: float,
        expected_seconds: float,
        task: Callable[[], tuple[int, str, str]],
        debug_command: str | None = None,
    ) -> tuple[int, str, str]:
        status_prefix = f"[{step_index}/{total_steps}] {label}"
        events.put(("progress", (start_pct, f"{status_prefix} (0%)")))
        events.put(("phase", self._extract_phase_from_progress_text(status_prefix)))
        if debug_command:
            events.put(("debug", f"{status_prefix} CMD: {debug_command}"))

        stop_progress = threading.Event()
        span = max(0.0, end_pct - start_pct)
        expected = max(1.0, expected_seconds)
        start_time = time.time()

        def pump_progress() -> None:
            last_step_pct = -1
            last_heartbeat_step = -1
            while not stop_progress.wait(0.35):
                elapsed = max(0.0, time.time() - start_time)
                heartbeat_step = int(elapsed // 10)
                if heartbeat_step > 0 and heartbeat_step != last_heartbeat_step:
                    last_heartbeat_step = heartbeat_step
                    events.put(("debug", f"{status_prefix} sigue en ejecucion ({int(elapsed)}s)"))
                if elapsed <= expected:
                    ratio = 0.92 * (elapsed / expected)
                else:
                    # Sigue avanzando lentamente hasta 99% para evitar sensacion de bloqueo.
                    extra = elapsed - expected
                    tail_window = max(8.0, expected * 0.35)
                    ratio = 0.92 + (0.075 * (1.0 - math.exp(-extra / tail_window)))
                ratio = min(0.995, ratio)
                overall_pct = start_pct + (span * ratio)
                step_pct = min(99, int(ratio * 100))
                if step_pct == last_step_pct:
                    continue
                last_step_pct = step_pct
                events.put(("progress", (overall_pct, f"{status_prefix} ({step_pct}%)")))

        progress_thread = threading.Thread(target=pump_progress, daemon=True)
        progress_thread.start()
        try:
            code, out, err = task()
        finally:
            stop_progress.set()
            progress_thread.join(timeout=1.0)

        events.put(("progress", (end_pct, f"{status_prefix} (100%)")))
        events.put(("debug", f"{status_prefix} finalizado con codigo {code}"))
        if out:
            events.put(("debug", f"{status_prefix} stdout: {self._short_debug_text(out)}"))
        if err:
            events.put(("debug", f"{status_prefix} stderr: {self._short_debug_text(err)}"))
        return code, out, err

    def _run_import_worker(
        self,
        events: queue.Queue[tuple[str, object]],
        stop_event: threading.Event,
        wp_container: str,
        db_container: str,
        db_user: str,
        db_password: str,
        db_name: str,
        local_url: str,
        backup_domain: str,
        wp_content_path: str,
        sql_file_path: str,
        skip_wp_upload: bool,
        skip_db_import: bool,
    ) -> None:
        try:
            total_steps = 6
            events.put(("debug", "Worker de importacion iniciado."))
            import_wp = not skip_wp_upload
            import_db = not skip_db_import

            if not import_wp and not import_db:
                raise RuntimeError("No hay tareas seleccionadas para importar.")

            def check_cancel() -> None:
                if stop_event.is_set():
                    raise RuntimeError("IMPORT_CANCELLED_BY_USER")

            wp_is_dir = os.path.isdir(wp_content_path)
            wp_lower = wp_content_path.lower()

            if import_wp:
                check_cancel()
                events.put(("phase", "Fase 1: Preparando contenedores"))
                self._run_import_progress_task(
                    events=events,
                    step_index=1,
                    total_steps=total_steps,
                    label="Preparando contenedores...",
                    start_pct=4.0,
                    end_pct=10.0,
                    expected_seconds=4.0,
                    debug_command=f"docker exec -u root {wp_container} sh -c rm -rf /tmp/wp-content /tmp/wp-content.tar /tmp/wp-content.zip",
                    task=lambda: self._run(
                        ["docker", "exec", "-u", "root", wp_container, "sh", "-c", "rm -rf /tmp/wp-content /tmp/wp-content.tar /tmp/wp-content.zip"]
                    ),
                )

                check_cancel()
                copy_seconds = self._estimate_transfer_seconds(wp_content_path, min_seconds=8.0, max_seconds=240.0)
                events.put(("phase", "Fase 2: Enviando archivos a remoto"))
                if wp_is_dir:
                    code, _, err = self._run_import_upload_with_real_progress(
                        events=events,
                        step_index=2,
                        total_steps=total_steps,
                        label="Copiando wp-content al contenedor...",
                        start_pct=10.0,
                        end_pct=38.0,
                        local_path=wp_content_path,
                        container_name=wp_container,
                        target_path="/tmp/wp-content",
                    )
                    if code != 0:
                        events.put(("phase", "Fase 2: Enviando archivos a remoto (sin telemetria, reintentando)"))
                        code, _, err = self._run_import_progress_task(
                            events=events,
                            step_index=2,
                            total_steps=total_steps,
                            label="Copiando wp-content al contenedor...",
                            start_pct=10.0,
                            end_pct=38.0,
                            expected_seconds=copy_seconds,
                            debug_command=f"docker cp {wp_content_path} {wp_container}:/tmp/wp-content",
                            task=lambda: self._run(["docker", "cp", wp_content_path, f"{wp_container}:/tmp/wp-content"]),
                        )
                    if code != 0:
                        raise RuntimeError(err or "No se pudo copiar carpeta wp-content")
                elif wp_lower.endswith(".tar"):
                    code, _, err = self._run_import_upload_with_real_progress(
                        events=events,
                        step_index=2,
                        total_steps=total_steps,
                        label="Subiendo wp-content.tar...",
                        start_pct=10.0,
                        end_pct=30.0,
                        local_path=wp_content_path,
                        container_name=wp_container,
                        target_path="/tmp/wp-content.tar",
                    )
                    if code != 0:
                        events.put(("phase", "Fase 2: Enviando archivos a remoto (sin telemetria, reintentando)"))
                        code, _, err = self._run_import_progress_task(
                            events=events,
                            step_index=2,
                            total_steps=total_steps,
                            label="Subiendo wp-content.tar...",
                            start_pct=10.0,
                            end_pct=30.0,
                            expected_seconds=copy_seconds,
                            debug_command=f"docker cp {wp_content_path} {wp_container}:/tmp/wp-content.tar",
                            task=lambda: self._run(["docker", "cp", wp_content_path, f"{wp_container}:/tmp/wp-content.tar"]),
                        )
                    if code != 0:
                        raise RuntimeError(err or "No se pudo copiar wp-content.tar")
                    code, _, err = self._run_import_progress_task(
                        events=events,
                        step_index=2,
                        total_steps=total_steps,
                        label="Extrayendo wp-content.tar...",
                        start_pct=30.0,
                        end_pct=38.0,
                        expected_seconds=max(8.0, copy_seconds * 0.45),
                        debug_command=f"docker exec -u root {wp_container} sh -c cd /tmp && tar xf wp-content.tar",
                        task=lambda: self._run(["docker", "exec", "-u", "root", wp_container, "sh", "-c", "cd /tmp && tar xf wp-content.tar"]),
                    )
                    if code != 0:
                        raise RuntimeError(err or "No se pudo extraer wp-content.tar")
                else:
                    code, _, err = self._run_import_upload_with_real_progress(
                        events=events,
                        step_index=2,
                        total_steps=total_steps,
                        label="Subiendo wp-content.zip...",
                        start_pct=10.0,
                        end_pct=30.0,
                        local_path=wp_content_path,
                        container_name=wp_container,
                        target_path="/tmp/wp-content.zip",
                    )
                    if code != 0:
                        events.put(("phase", "Fase 2: Enviando archivos a remoto (sin telemetria, reintentando)"))
                        code, _, err = self._run_import_progress_task(
                            events=events,
                            step_index=2,
                            total_steps=total_steps,
                            label="Subiendo wp-content.zip...",
                            start_pct=10.0,
                            end_pct=30.0,
                            expected_seconds=copy_seconds,
                            debug_command=f"docker cp {wp_content_path} {wp_container}:/tmp/wp-content.zip",
                            task=lambda: self._run(["docker", "cp", wp_content_path, f"{wp_container}:/tmp/wp-content.zip"]),
                        )
                    if code != 0:
                        raise RuntimeError(err or "No se pudo copiar wp-content.zip")
                    code, _, err = self._run_import_progress_task(
                        events=events,
                        step_index=2,
                        total_steps=total_steps,
                        label="Extrayendo wp-content.zip...",
                        start_pct=30.0,
                        end_pct=38.0,
                        expected_seconds=max(8.0, copy_seconds * 0.45),
                        debug_command=f"docker exec -u root {wp_container} sh -c cd /tmp && unzip -q wp-content.zip",
                        task=lambda: self._run(["docker", "exec", "-u", "root", wp_container, "sh", "-c", "cd /tmp && unzip -q wp-content.zip"]),
                    )
                    if code != 0:
                        raise RuntimeError(err or "No se pudo extraer wp-content.zip")

                copy_cmd = "cp -rf /tmp/wp-content/. /opt/bitnami/wordpress/wp-content/ 2>/dev/null || cp -rf /tmp/wp-content/* /opt/bitnami/wordpress/wp-content/"
                events.put(("phase", "Fase 3: Aplicando wp-content en WordPress"))
                code, _, err = self._run_import_progress_task(
                    events=events,
                    step_index=3,
                    total_steps=total_steps,
                    label="Aplicando wp-content en WordPress...",
                    start_pct=38.0,
                    end_pct=55.0,
                    expected_seconds=max(8.0, copy_seconds * 0.6),
                    debug_command=f"docker exec -u root {wp_container} sh -c {copy_cmd}",
                    task=lambda: self._run(["docker", "exec", "-u", "root", wp_container, "sh", "-c", copy_cmd]),
                )
                if code != 0:
                    raise RuntimeError(err or "No se pudo copiar contenido de wp-content")
                self._run_import_progress_task(
                    events=events,
                    step_index=3,
                    total_steps=total_steps,
                    label="Ajustando permisos de wp-content...",
                    start_pct=55.0,
                    end_pct=60.0,
                    expected_seconds=8.0,
                    debug_command=f"docker exec -u root {wp_container} sh -c chown -R 1001:1001 /opt/bitnami/wordpress/wp-content",
                    task=lambda: self._run(["docker", "exec", "-u", "root", wp_container, "sh", "-c", "chown -R 1001:1001 /opt/bitnami/wordpress/wp-content"]),
                )
            else:
                events.put(("debug", "Omitida importacion de wp-content por seleccion del usuario."))
                events.put(("phase", "Fase 3: Aplicando wp-content en WordPress (omitido)"))
                events.put(("progress", (60.0, "[3/6] Aplicando wp-content en WordPress... (100% - omitido)")))

            if import_db:
                check_cancel()
                sql_copy_seconds = self._estimate_transfer_seconds(sql_file_path, min_seconds=5.0, max_seconds=180.0)
                events.put(("phase", "Fase 4: Importando base de datos"))
                code, _, err = self._run_import_progress_task(
                    events=events,
                    step_index=4,
                    total_steps=total_steps,
                    label="Copiando SQL al contenedor DB...",
                    start_pct=60.0,
                    end_pct=70.0,
                    expected_seconds=sql_copy_seconds,
                    debug_command=f"docker cp {sql_file_path} {db_container}:/tmp/export.sql",
                    task=lambda: self._run(["docker", "cp", sql_file_path, f"{db_container}:/tmp/export.sql"]),
                )
                if code != 0:
                    raise RuntimeError(err or "No se pudo copiar export.sql al contenedor DB")

                u = self._sh_single_quote(db_user)
                p = self._sh_single_quote(db_password)
                d = self._sh_single_quote(db_name)
                import_cmd = f"mysql -h 127.0.0.1 -u {u} -p{p} {d} < /tmp/export.sql"
                code, _, err = self._run_import_progress_task(
                    events=events,
                    step_index=4,
                    total_steps=total_steps,
                    label="Importando base de datos...",
                    start_pct=70.0,
                    end_pct=82.0,
                    expected_seconds=max(12.0, sql_copy_seconds * 1.2),
                    debug_command=f"docker exec {db_container} sh -c {import_cmd}",
                    task=lambda: self._run(["docker", "exec", db_container, "sh", "-c", import_cmd]),
                )
                if code != 0:
                    raise RuntimeError(err or "Fallo al importar SQL")

                check_cancel()
                events.put(("phase", "Fase 5: Ajustando URLs"))
                events.put(("progress", (82.0, f"[5/{total_steps}] Ajustando URLs en WordPress... (0%)")))
                if backup_domain != local_url:
                    code, _, err = self._run_import_progress_task(
                        events=events,
                        step_index=5,
                        total_steps=total_steps,
                        label="Ajustando URLs en WordPress...",
                        start_pct=82.0,
                        end_pct=92.0,
                        expected_seconds=10.0,
                        debug_command=(
                            "docker exec "
                            f"{wp_container} wp search-replace {backup_domain} {local_url} --allow-root --path=/opt/bitnami/wordpress"
                        ),
                        task=lambda: self._run(
                            [
                                "docker",
                                "exec",
                                wp_container,
                                "wp",
                                "search-replace",
                                backup_domain,
                                local_url,
                                "--allow-root",
                                "--path=/opt/bitnami/wordpress",
                            ]
                        ),
                    )
                    if code != 0:
                        raise RuntimeError(err or "Fallo al ajustar URLs")
                else:
                    events.put(("progress", (92.0, f"[5/{total_steps}] Ajustando URLs en WordPress... (100% - omitido)")))
            else:
                events.put(("debug", "Omitida importacion SQL por seleccion del usuario."))
                events.put(("phase", "Fase 5: Ajustando URLs (omitido)"))
                events.put(("progress", (92.0, "[5/6] Ajustando URLs en WordPress... (100% - omitido)")))

            check_cancel()
            events.put(("phase", "Fase 6: Reiniciando servicios y finalizando"))
            code, _, err = self._run_import_progress_task(
                events=events,
                step_index=6,
                total_steps=total_steps,
                label="Reiniciando WordPress...",
                start_pct=92.0,
                end_pct=99.0,
                expected_seconds=8.0,
                debug_command=f"docker restart {wp_container}",
                task=lambda: self._run(["docker", "restart", wp_container]),
            )
            if code != 0:
                raise RuntimeError(err or "No se pudo reiniciar contenedor WordPress")

            events.put(("debug", "Importacion completada correctamente."))
            events.put(("done", None))
        except Exception as exc:
            events.put(("debug", f"ERROR en worker: {exc}"))
            events.put(("debug", traceback.format_exc()))
            events.put(("error", str(exc)))

    def _poll_import_worker_queue(
        self,
        window: tk.Toplevel,
        status_var: tk.StringVar,
        phase_status_var: tk.StringVar,
        phase_state: dict[str, object],
        progress_var: tk.DoubleVar,
        import_button: ttk.Button,
        cancel_button: ttk.Button,
        stop_button: ttk.Button,
        events: queue.Queue[tuple[str, object]],
        wp_container: str,
        db_name: str,
        debug_window: tk.Toplevel | None,
        debug_text: tk.Text | None,
    ) -> None:
        if not window.winfo_exists():
            return

        completed = False
        failed: str | None = None
        latest_progress: tuple[float, str] | None = None
        latest_phase: str | None = None
        debug_lines: list[str] = []
        processed = 0
        batch_limit = 120

        while processed < batch_limit:
            try:
                kind, payload = events.get_nowait()
            except queue.Empty:
                break
            processed += 1

            if kind == "progress":
                value, text = payload  # type: ignore[misc]
                latest_progress = (float(value), str(text))
                latest_phase = self._extract_phase_from_progress_text(str(text))
                phase_state["step_pct"] = self._extract_step_percent_from_progress_text(str(text))
            elif kind == "phase":
                latest_phase = str(payload)
                phase_state["step_pct"] = None
            elif kind == "debug":
                debug_lines.append(str(payload))
            elif kind == "done":
                completed = True
            elif kind == "error":
                failed = str(payload)

        for line in debug_lines:
            self._append_import_debug(debug_window, debug_text, line)

        if latest_phase:
            phase_state["base"] = latest_phase

        if latest_progress is not None:
            value, text = latest_progress
            progress_var.set(value)
            status_var.set(text)

        base_phase = str(phase_state.get("base") or "Fase activa: Ejecutando subproceso")
        step_pct = phase_state.get("step_pct")
        if isinstance(step_pct, int):
            phase_status_var.set(f"{base_phase} ({step_pct}%)")
        else:
            dots_count = int(phase_state.get("dots") or 0)
            phase_text, next_dots = self._next_phase_text_dots(base_phase, dots_count)
            phase_state["dots"] = next_dots
            phase_status_var.set(phase_text)

        if completed:
            stop_button.configure(state="disabled")
            progress_var.set(100)
            status_var.set("Importacion completada correctamente.")
            phase_status_var.set("Fase 6: Completado (100%)")
            self._append_import_debug(debug_window, debug_text, "Importacion finalizada OK.")
            self.log_event("IMPORT", wp_container, "OK", f"Importacion completada ({db_name})")
            self.refresh_everything()
            messagebox.showinfo("Importar", "Importacion completada correctamente.")
            if window.winfo_exists():
                window.destroy()
            return

        if failed is not None:
            stop_button.configure(state="disabled")
            import_button.configure(state="normal")
            cancel_button.configure(state="normal")
            if failed == "IMPORT_CANCELLED_BY_USER":
                status_var.set("Importacion cancelada por el usuario.")
                phase_status_var.set("Fase cancelada por el usuario")
                self._append_import_debug(debug_window, debug_text, "Importacion cancelada por el usuario.")
                messagebox.showinfo("Importar", "Importacion cancelada por el usuario.")
                return
            self.log_event("IMPORT", wp_container or "global", "ERROR", failed)
            self.refresh_history()
            status_var.set(f"Error: {failed}")
            phase_status_var.set("Fase finalizada con error")
            self._append_import_debug(debug_window, debug_text, f"Importacion fallo: {failed}")
            messagebox.showerror("Importar", f"La importacion fallo.\n\n{failed}")
            return

        # Si quedaron eventos en cola, seguir drenando pronto para no bloquear la UI.
        next_delay_ms = 40 if processed >= batch_limit else 150
        window.after(
            next_delay_ms,
            lambda: self._poll_import_worker_queue(
                window=window,
                status_var=status_var,
                phase_status_var=phase_status_var,
                phase_state=phase_state,
                progress_var=progress_var,
                import_button=import_button,
                cancel_button=cancel_button,
                stop_button=stop_button,
                events=events,
                wp_container=wp_container,
                db_name=db_name,
                debug_window=debug_window,
                debug_text=debug_text,
            ),
        )

    def open_docs(self) -> None:
        docs = self._find_first_existing([
            "docker-wordpress-docs.html",
            os.path.join("version_bat", "docker-wordpress-docs.html"),
        ])
        if not os.path.isfile(docs):
            messagebox.showerror("Archivo", "No se encontro docker-wordpress-docs.html")
            return
        try:
            os.startfile(docs)  # type: ignore[attr-defined]
            self.log_event("DOCS", "docker-wordpress-docs.html", "INFO", "Documentacion abierta")
            self.refresh_history()
        except Exception as exc:  # pragma: no cover
            self.log_event("DOCS", "docker-wordpress-docs.html", "ERROR", str(exc))
            messagebox.showerror("Documento", f"No se pudo abrir la documentacion.\n\n{exc}")

    def open_app_docs(self) -> None:
        docs = self._find_first_existing(["app-docs.html"])
        if not os.path.isfile(docs):
            messagebox.showerror("Archivo", "No se encontro app-docs.html")
            return
        try:
            os.startfile(docs)  # type: ignore[attr-defined]
            self.log_event("DOCS", "app-docs.html", "INFO", "Documentacion app abierta")
            self.refresh_history()
        except Exception as exc:  # pragma: no cover
            self.log_event("DOCS", "app-docs.html", "ERROR", str(exc))
            messagebox.showerror("Documento", f"No se pudo abrir la documentacion.\n\n{exc}")


def main() -> None:
    if sys.platform != "win32":
        print("Esta app esta pensada para Windows.")

    root = tk.Tk()
    app = WordPressUtilitiesApp(root)
    root.mainloop()


if __name__ == "__main__":
    helper_exit_code = _run_helper_cli_from_argv(sys.argv)
    if helper_exit_code is None:
        main()
    else:
        raise SystemExit(helper_exit_code)
