import os
import subprocess
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from models.job import BackupJob

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _safe_name(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)


class BackupRunner:
    def __init__(self, job: BackupJob):
        self.job = job

    def run(self, progress: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        try:
            os.makedirs(self.job.output_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.job.output_type == "daily_overwrite":
                return self._run_daily_overwrite(progress)
            if self.job.output_type == "multiple" and self.job.databases:
                return self._run_multiple(ts, progress)
            return self._run_single(ts, progress)
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
            progress("Compressing with 7-Zip …")
        arc_paths: List[str] = []
        for sql_path in sql_paths:
            arc_path = sql_path.replace(".sql", ".7z")
            cmd = [self.job.zip_path, "a"]
            if self.job.zip_password:
                cmd += [f"-p{self.job.zip_password}", "-mhe=on"]
            cmd += [arc_path, sql_path]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      creationflags=_NO_WINDOW)
                if proc.returncode != 0:
                    return False, f"7-Zip error: {proc.stderr.strip()}"
                if os.path.exists(sql_path):
                    os.remove(sql_path)
                arc_paths.append(arc_path)
            except FileNotFoundError:
                return True, (
                    f"7-Zip not found at '{self.job.zip_path}'. "
                    f"SQL files kept in {self.job.output_dir}"
                )
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
            "--hex-blob",
        ]
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
            progress("Compressing with 7-Zip …")

        name = _safe_name(self.job.name)
        arc_path = os.path.join(self.job.output_dir, f"{name}_{ts}.7z")

        cmd = [self.job.zip_path, "a"]
        if self.job.zip_password:
            cmd += [f"-p{self.job.zip_password}", "-mhe=on"]
        cmd.append(arc_path)
        cmd.extend(sql_paths)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=_NO_WINDOW,
            )
            if proc.returncode != 0:
                return False, f"7-Zip error: {proc.stderr.strip()}"
            for p in sql_paths:
                if os.path.exists(p):
                    os.remove(p)
            return True, f"Compressed: {arc_path}"
        except FileNotFoundError:
            # 7-Zip not installed — keep SQL files and warn
            return True, (
                f"7-Zip not found at '{self.job.zip_path}'. "
                f"SQL file(s) kept in {self.job.output_dir}"
            )
        except Exception as e:
            return False, str(e)
