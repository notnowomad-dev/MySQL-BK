import os
import shutil
import subprocess
import time
import zipfile
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from models.job import BackupJob

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _register_network_credentials(path: str, user: str, password: str) -> None:
    """Store credentials in Windows Credential Manager for the server in path."""
    import re
    resolved = _mapped_drive_to_unc(path) if re.match(r'^[A-Za-z]:[/\\]', path) else os.path.normpath(path)
    m = re.match(r'^\\\\([^\\]+)\\', resolved)
    if not m:
        return
    host = m.group(1)
    subprocess.run(
        ["cmdkey", f"/add:{host}", f"/user:{user}", f"/pass:{password}"],
        capture_output=True, creationflags=_NO_WINDOW,
    )


def _mapped_drive_to_unc(path: str) -> str:
    """Replace a mapped drive letter with its UNC path read from the registry.
    Mapped drives are session-bound and unavailable to scheduled/background runs,
    but the registry entry persists so we can resolve it even when disconnected."""
    import re
    m = re.match(r'^([A-Za-z]):[/\\]', path)
    if not m:
        return path
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, rf"Network\{m.group(1).upper()}"
        )
        unc, _ = winreg.QueryValueEx(key, "RemotePath")
        winreg.CloseKey(key)
        return os.path.normpath(unc + path[2:])
    except Exception:
        return path


def _safe_name(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)


class BackupRunner:
    def __init__(self, job: BackupJob):
        self.job = job

    def run(self, progress: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        try:
            os.makedirs(self.job.output_dir, exist_ok=True)
            since = time.time()

            if self.job.db_type == "mssql":
                from core.mssql_backup import MSSQLBackupRunner
                ok, msg = MSSQLBackupRunner(self.job).run(progress)
            else:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                if self.job.output_type == "daily_overwrite":
                    ok, msg = self._run_daily_overwrite(progress)
                elif self.job.output_type == "multiple" and self.job.databases:
                    ok, msg = self._run_multiple(ts, progress)
                else:
                    ok, msg = self._run_single(ts, progress)

            if ok and self.job.alt_dest_enabled and self.job.alt_dest:
                alt_ok, alt_msg = self._copy_to_alt_dest(since, progress)
                msg = f"{msg} | {alt_msg}"
                if not alt_ok:
                    return False, msg

            return ok, msg
        except Exception as e:
            return False, f"Unexpected error: {e}"

    # ---------------------------------------------------------------- single --

    def _run_single(self, ts: str, progress: Optional[Callable]) -> Tuple[bool, str]:
        name = _safe_name(self.job.name)
        sql_path = os.path.join(self.job.output_dir, f"{name}_{ts}.sql")

        cmd = self._base_cmd()
        if not self.job.databases:
            cmd.append("--all-databases")
        else:
            cmd.append("--databases")
            cmd.extend(self.job.databases)

        if progress:
            progress(f"Running mysqldump → {sql_path}")

        ok, msg = self._exec_dump(cmd, sql_path)
        if not ok:
            return False, msg

        if self.job.use_zip:
            return self._zip_files([sql_path], ts, progress)
        return True, f"Saved: {sql_path}"

    # --------------------------------------------------------------- multiple --

    def _run_multiple(self, ts: str, progress: Optional[Callable]) -> Tuple[bool, str]:
        output_files: List[str] = []
        name = _safe_name(self.job.name)

        for db in self.job.databases:
            tables = self.job.tables.get(db, [])
            if tables:
                for table in tables:
                    sql_path = os.path.join(self.job.output_dir, f"{name}_{db}_{table}_{ts}.sql")
                    cmd = self._base_cmd() + [db, table]
                    if progress:
                        progress(f"Dumping {db}.{table} …")
                    ok, msg = self._exec_dump(cmd, sql_path)
                    if not ok:
                        return False, msg
                    output_files.append(sql_path)
            else:
                sql_path = os.path.join(self.job.output_dir, f"{name}_{db}_{ts}.sql")
                cmd = self._base_cmd() + [db]
                if progress:
                    progress(f"Dumping {db} …")
                ok, msg = self._exec_dump(cmd, sql_path)
                if not ok:
                    return False, msg
                output_files.append(sql_path)

        if self.job.use_zip and output_files:
            return self._zip_files(output_files, ts, progress)
        return True, f"Backup complete — {len(output_files)} file(s) in {self.job.output_dir}"

    # ---------------------------------------------------- daily overwrite --

    _DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    def _run_daily_overwrite(self, progress: Optional[Callable]) -> Tuple[bool, str]:
        day = self._DAYS[datetime.now().weekday()]   # mon … sun
        name = _safe_name(self.job.name)
        output_files: List[str] = []

        if not self.job.databases:
            # No specific DB selected — dump everything into one rotating file
            sql_path = os.path.join(self.job.output_dir, f"{name}_{day}.sql")
            cmd = self._base_cmd() + ["--all-databases"]
            if progress:
                progress(f"Daily overwrite → {sql_path}")
            ok, msg = self._exec_dump(cmd, sql_path)
            if not ok:
                return False, msg
            output_files.append(sql_path)
        else:
            for db in self.job.databases:
                sql_path = os.path.join(self.job.output_dir, f"{name}_{db}_{day}.sql")
                tables = self.job.tables.get(db, [])
                cmd = self._base_cmd() + ([db] + tables if tables else [db])
                if progress:
                    progress(f"Daily overwrite {db} → {sql_path}")
                ok, msg = self._exec_dump(cmd, sql_path)
                if not ok:
                    return False, msg
                output_files.append(sql_path)

        if self.job.use_zip and output_files:
            return self._zip_daily_overwrite(output_files, day, progress)

        return True, f"Daily overwrite ({day}) — {len(output_files)} file(s) saved"

    def _zip_daily_overwrite(
        self, sql_paths: List[str], day: str, progress: Optional[Callable]
    ) -> Tuple[bool, str]:
        if progress:
            progress("Compressing …")
        arc_paths: List[str] = []
        for sql_path in sql_paths:
            arc_path = sql_path.replace(".sql", ".zip")
            try:
                self._compress([sql_path], arc_path)
                if os.path.exists(sql_path):
                    os.remove(sql_path)
                arc_paths.append(arc_path)
            except Exception as e:
                return False, f"Compression error: {e}"
        return True, f"Daily overwrite ({day}) compressed — {len(arc_paths)} file(s)"

    # --------------------------------------------------------------- helpers --

    def _base_cmd(self) -> List[str]:
        cmd = [
            self.job.mysqldump_path,
            f"--host={self.job.host}",
            f"--port={self.job.port}",
            f"--user={self.job.username}",
            "--single-transaction",
            "--routines",
            "--triggers",
        ]
        if self.job.hex_blob:
            cmd.append("--hex-blob")
        if self.job.password:
            cmd.append(f"--password={self.job.password}")
        return cmd

    def _exec_dump(self, cmd: List[str], out_path: str) -> Tuple[bool, str]:
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                proc = subprocess.run(
                    cmd,
                    stdout=fh,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=_NO_WINDOW,
                )
            stderr = proc.stderr or ""
            # mysqldump prints a password warning to stderr even on success
            real_errors = [
                ln for ln in stderr.splitlines()
                if ln.strip() and "Using a password on the command line" not in ln
            ]
            if proc.returncode != 0 or real_errors:
                if os.path.exists(out_path):
                    os.remove(out_path)
                return False, "\n".join(real_errors) or f"Exit code {proc.returncode}"
            return True, out_path
        except FileNotFoundError:
            return False, (
                f"mysqldump not found at '{cmd[0]}'. "
                "Install MySQL tools and add to PATH, or set the path in job settings."
            )
        except Exception as e:
            return False, str(e)

    def _zip_files(
        self, sql_paths: List[str], ts: str, progress: Optional[Callable]
    ) -> Tuple[bool, str]:
        if progress:
            progress("Compressing …")
        name = _safe_name(self.job.name)
        arc_path = os.path.join(self.job.output_dir, f"{name}_{ts}.zip")
        try:
            self._compress(sql_paths, arc_path)
            for p in sql_paths:
                if os.path.exists(p):
                    os.remove(p)
            return True, f"Compressed: {arc_path}"
        except Exception as e:
            return False, f"Compression error: {e}"

    def _copy_to_alt_dest(
        self, since: float, progress: Optional[Callable]
    ) -> Tuple[bool, str]:
        if getattr(self.job, "alt_dest_user", ""):
            _register_network_credentials(
                self.job.alt_dest, self.job.alt_dest_user, self.job.alt_dest_pass
            )
        base = _mapped_drive_to_unc(self.job.alt_dest)
        if base == self.job.alt_dest:
            base = os.path.normpath(base)

        # Dated subfolder: \YYYY\MM\Ddd  e.g. \2026\05\Sun
        now = datetime.now()
        alt = os.path.join(base, now.strftime("%Y"), now.strftime("%m"), now.strftime("%a"))

        last_err = None
        for attempt in range(3):
            try:
                os.makedirs(alt, exist_ok=True)
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(10)
        if last_err:
            return False, f"Cannot create alternate destination '{alt}': {last_err}"
        try:
            copied = []
            for fname in os.listdir(self.job.output_dir):
                fpath = os.path.join(self.job.output_dir, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) >= since - 1:
                    shutil.copy2(fpath, os.path.join(alt, fname))
                    copied.append(fname)
                    if progress:
                        progress(f"Alt dest: copied {fname} → {alt}")
            if not copied:
                return True, f"Alt dest: no new files found in {self.job.output_dir}"
            return True, f"Alt dest: {len(copied)} file(s) copied to {alt}"
        except Exception as e:
            return False, f"Alt dest copy failed: {e}"


    def _compress(self, sql_paths: List[str], arc_path: str):
        """Write a .zip archive. Uses pyzipper for AES-256 when a password is set."""
        password = self.job.zip_password.encode() if self.job.zip_password else None
        if password:
            try:
                import pyzipper
                with pyzipper.AESZipFile(arc_path, "w",
                                         compression=pyzipper.ZIP_DEFLATED,
                                         encryption=pyzipper.WZ_AES) as zf:
                    zf.setpassword(password)
                    for p in sql_paths:
                        zf.write(p, os.path.basename(p))
                return
            except ImportError:
                pass  # fall through to standard zipfile without password
        with zipfile.ZipFile(arc_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sql_paths:
                zf.write(p, os.path.basename(p))
