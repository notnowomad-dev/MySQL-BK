# Database Backup Scheduler

A Windows desktop application for scheduling automated **MySQL and Microsoft SQL Server** database backups with a clean GUI. Built as a reliable replacement for brittle `.bat` + Task Scheduler setups.

---

## Features

- **MySQL and MSSQL support** — connect to MySQL/MariaDB servers or Microsoft SQL Server (via ODBC); same scheduling and output options for both
- **Multiple backup jobs** — create, edit, enable/disable, and delete independent jobs
- **Flexible scheduling** — Hourly, Daily, Weekly, Monthly, or custom Cron expression
- **Selective backup** — pick specific databases and/or individual tables per job
- **Three output modes**
  - Single `.sql` file (all selected DBs merged)
  - Multiple `.sql` files (one per database or table)
  - Daily overwrite — 7 rotating files (`mon.sql` … `sun.sql`) that overwrite each week
- **MSSQL backup formats** — T-SQL Script (`.sql`) via pyodbc from any machine, or Native Backup (`.bak`) using SQL Server's `BACKUP DATABASE` command (must run on the server)
- **Alternate destination** — optionally copy completed backup files to a second folder after each run; works with all output formats
- **ZIP compression** — optional `.zip` archive with optional AES-256 password; opens with Windows Explorer — no extra software needed
- **BLOB/BINARY export** — optional `--hex-blob` flag exports binary columns as safe hex strings
- **Start with Windows** — one-click autostart toggle in the system tray menu
- **System tray** — minimizes to tray; backups keep running while the window is hidden
- **Run Now** — trigger any job immediately from the UI
- **Log viewer** — per-job history of every run (timestamp, status, message)
- **Copy to clipboard** — select rows in the job list and press Ctrl+C (or right-click → Copy Row) to copy as tab-separated text
- **Single-instance** — launching a second copy restores the existing window instead
- **VC++ auto-install** — bundles the Microsoft Visual C++ Redistributable and installs it automatically if missing

---

## Requirements

| Requirement | Notes |
|---|---|
| Windows 10 / 11 or Server 2019+ | 64-bit |
| MySQL server | Local or remote (for MySQL jobs) |
| `mysqldump.exe` | Comes with MySQL Server or MySQL Shell (MySQL jobs only) |
| SQL Server / ODBC Driver | "ODBC Driver 17/18 for SQL Server" — free from Microsoft (MSSQL jobs only) |
| Python 3.10+ | Only needed when running from source |

No third-party compression software required — ZIP is handled by Python's built-in `zipfile` module (and `pyzipper` for password-protected archives).

---

## Installation

### Option A — Pre-built executable (recommended)

Download `Database-Backup-Scheduler.exe` from the `dist/` folder (or the Releases page) and run it directly. No Python installation required. The Microsoft Visual C++ Redistributable is bundled and installed automatically if missing.

### Option B — Run from source

```bat
# 1. Clone or download the project
# 2. Open a terminal in the project folder

setup.bat        # installs Python dependencies (including pyzipper for encrypted zips)
```

Then launch with **`run.vbs`** (double-click) — starts the app with no CMD window.

`run.bat` is kept for debugging only; it shows a console so startup errors (e.g. missing imports) are visible.

> **Python auto-detection** — `setup.bat`, `run.bat`, and `build.bat` find Python automatically without requiring it to be on `PATH`. They first check the system `python` command but only accept it if `pip` is functional (this filters out embedded Pythons such as the one bundled with Inkscape). If that check fails, they scan the following locations in order, newest version first:
>
> | Location pattern | Example |
> |---|---|
> | `%LOCALAPPDATA%\Programs\Python\PythonXXX\` | Standard Python installer (per-user) |
> | `C:\PythonXXX\` | Custom root-level install |
> | `C:\Program Files\PythonXXX\` | System-wide install |
>
> Versions checked: 3.13, 3.12, 3.11, 3.10. If none are found an error message is shown with a link to python.org.

---

## Building the executable

```bat
build.bat
```

This produces `dist\Database-Backup-Scheduler.exe` via PyInstaller. The resulting file is fully self-contained — no Python, VC++ runtime, or compression software needed on the target machine. `build.bat` also downloads `vc_redist.x64.exe` automatically (if not already present) so it can be bundled into the exe.

---

## Quick Start

1. Launch the application.
2. Click **+ Add Job** in the toolbar.
3. Fill in the four tabs:

| Tab | What to configure |
|---|---|
| **Connection** | MySQL host, port, username, password, and path to `mysqldump.exe` |
| **Databases** | Click **Reload Databases**, then check the databases (and optionally specific tables) to include |
| **Schedule** | Choose frequency (Hourly / Daily / Weekly / Monthly / Cron) and the time |
| **Output** | Destination folder, SQL format, optional ZIP compression, and mysqldump options |

4. Click **OK** to save. The job appears in the main list and starts running on schedule automatically.

---

## Job settings reference

### Connection tab

Select **MySQL** or **Microsoft SQL Server (MSSQL)** at the top — the form updates to show only the relevant fields.

**MySQL fields**

| Field | Description |
|---|---|
| Host | MySQL server hostname or IP (default: `localhost`) |
| Port | MySQL port (default: `3306`) |
| Username | MySQL user |
| Password | MySQL password (stored locally in SQLite) |
| mysqldump path | Full path to `mysqldump.exe`, or just `mysqldump` if it is on `PATH` |
| Test Connection | Verifies credentials before saving |

**MSSQL fields**

| Field | Description |
|---|---|
| Host | SQL Server hostname or IP (default: `localhost`) |
| Port | SQL Server port (default: `1433`) |
| Username | SQL login (leave blank when using Windows Auth) |
| Password | SQL login password |
| Windows Authentication | Use the current Windows user's credentials (Trusted Connection) |
| ODBC Driver | Select an installed SQL Server ODBC driver; the dropdown is populated from drivers already installed on this machine |
| Test Connection | Verifies credentials before saving |

> **MSSQL backup methods:** two formats are available — select in the Output tab when an MSSQL job is configured.
> - **T-SQL Script (.sql)** — exports CREATE TABLE + INSERT statements via `pyodbc`. Works from any machine on the network. No server-side tools required. System databases (`master`, `tempdb`, `model`, `msdb`) are excluded automatically.
> - **Native Backup (.bak)** — runs `BACKUP DATABASE [db] TO DISK` directly on SQL Server. **This tool must run on the SQL Server machine itself** (or the output path must be a UNC share the SQL Server service account can write to). Running remotely from a client PC will fail with a path-not-found error.

### Databases tab

- Leave everything **unchecked** to back up all databases on the server.
- Check a **database** to back up all its tables.
- Expand a database and check individual **tables** for a partial backup.
- Click **Reload Databases** any time to refresh the list from the server.

### Schedule tab

| Frequency | Extra setting |
|---|---|
| Hourly | Uses the minute portion of the time field |
| Daily | Runs every day at the specified time |
| Weekly | Choose a day of the week and a time |
| Monthly | Choose a day of the month (1–28) and a time |
| Custom Cron | Enter a standard 5-field cron expression (e.g. `30 2 * * 1-5`) |

### Output tab

**Output file structure**

| Mode | Behaviour |
|---|---|
| Single file | All selected databases dumped into one timestamped file |
| Multiple files | One file per database, or one per table when specific tables are selected |
| Daily overwrite | Produces `jobname_dbname_mon.*` … `jobname_dbname_sun.*`; each weekday's file overwrites the previous week's — capped at 7 files per database |

**MSSQL Backup Format** *(visible only for MSSQL jobs)*

| Format | Behaviour |
|---|---|
| T-SQL Script (.sql) | Exports CREATE TABLE + INSERT via pyodbc; runs from any machine |
| Native Backup (.bak) | Uses `BACKUP DATABASE TO DISK`; tool must run on the SQL Server machine; enabling Compress adds `WITH COMPRESSION` (no .zip created) |

**Compression**

- Enable **Compress output as .zip** to produce a `.zip` archive instead of plain `.sql` files.
- The archive opens directly in Windows Explorer — no extra software needed.
- Optionally set a **password**; the archive will use AES-256 encryption via `pyzipper` (installed by `setup.bat`).
- For `.bak` format, this option adds SQL Server native compression (`WITH COMPRESSION`) instead of creating a zip.

**Use --hex-blob** — when checked (MySQL jobs only), BLOB and BINARY columns are exported as hexadecimal strings (e.g. `0x89504e47…`) instead of raw binary. Prevents encoding issues when the dump is opened as UTF-8 text. Enabled by default.

**Alternate Destination** — optionally copy all backup files produced by the job to a second folder immediately after each successful run. Works with every output format and compression mode. If the copy fails the job is marked Failed so you are notified.

**Enable job** — uncheck to save the job without scheduling it.

---

## Main window toolbar

| Button | Action |
|---|---|
| **+ Add Job** | Open dialog to create a new backup job |
| **Edit** | Edit the selected job |
| **Delete** | Permanently delete the selected job |
| **Run Now** | Execute the selected job immediately in the background |
| **Logs** | Open the log viewer for the selected job (or all jobs if none selected) |
| **Exit** | Quit the application |

Right-clicking a row shows the same actions plus **Open Destination Folder** and **Copy Row**.

**Copying job data** — select one or more rows and press **Ctrl+C** (or right-click → Copy Row) to copy the job details as tab-separated text, ready to paste into Excel or Notepad.

---

## System tray

- Closing or minimizing the window hides it to the tray — backups keep running.
- **Single-click** or **double-click** the tray icon to restore the window.
- Right-click the tray icon for:
  - **Restore GUI** — bring the window back
  - **Start with Windows** — toggle autostart on login (writes to `HKCU\...\Run` registry key)
  - **Exit** — quit the application

---

## File locations

| Path | Contents |
|---|---|
| `%USERPROFILE%\.database_backup_scheduler\jobs.db` | SQLite database storing all jobs and logs |
| Output directory (per job) | Generated `.sql`, `.zip`, or `.bak` backup files |
| Alternate destination (per job) | Copy of the above files, if alternate destination is configured |
| Next to the `.exe` | `startup_error.log` — written automatically if the app fails to start |

---

## Troubleshooting

**`mysqldump not found`**
Set the full path to `mysqldump.exe` in the Connection tab (e.g. `C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe`), or add the MySQL `bin` folder to your system `PATH`. This only applies to MySQL jobs — MSSQL jobs do not use `mysqldump`.

**MSSQL .bak backup fails with "cannot open backup device" / path not found**
`BACKUP DATABASE TO DISK` runs on the SQL Server, not on this PC. The output directory must exist on the SQL Server machine and the SQL Server service account must have write permission to it. If running this tool remotely, either switch to T-SQL Script (.sql) format, or use a UNC path (e.g. `\\server\share\backups`) that the SQL Server service account can reach.

**MSSQL connection fails / no drivers listed**
Install the [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server). Driver 17 or 18 is recommended. After installing, reopen the job dialog — the driver dropdown is populated at dialog open time.

**Application fails to start with a DLL error**
The pre-built `.exe` bundles `vc_redist.x64.exe` and installs it automatically. If the error persists:
1. Check `startup_error.log` next to the `.exe` — it lists which specific DLLs are missing.
2. Install the Microsoft Visual C++ 2015–2022 Redistributable (x64) manually: `https://aka.ms/vs/17/release/vc_redist.x64.exe`
3. Reboot and try again.

> **Windows Server 2016 is not supported.** Qt 5 (PyQt5) requires Windows 10 build 1607 or later / Server 2019+. Server 2016 (build 14393 = Windows 10 1607) may work but is not officially supported.

**Job shows "Failed" in status**
Open the Logs viewer (toolbar or right-click menu) to read the full error message from the last run.

**Password-protected zip not working**
Ensure `pyzipper` is installed by running `setup.bat`. For the pre-built exe it is bundled automatically. Without `pyzipper`, zips are created without a password.

**Application won't start / database error**
Delete `%USERPROFILE%\.database_backup_scheduler\jobs.db` to reset all job data and start fresh.

**`setup.bat` / `build.bat` picks the wrong Python**
The scripts skip any Python that does not have `pip` available and scan a fixed list of common install paths. If your Python is in a non-standard location, either add it to your system `PATH` (and ensure `pip` is installed) or run the install command manually:
```bat
C:\your\python\path\python.exe -m pip install -r requirements.txt
```

---

## Tech stack

| Component | Library |
|---|---|
| GUI | [PyQt5](https://pypi.org/project/PyQt5/) |
| Scheduler | [APScheduler](https://apscheduler.readthedocs.io/) 3.x |
| MySQL connectivity | [mysql-connector-python](https://pypi.org/project/mysql-connector-python/) |
| MySQL backup engine | `mysqldump` (system binary) |
| MSSQL connectivity | [pyodbc](https://pypi.org/project/pyodbc/) via ODBC Driver for SQL Server |
| MSSQL backup engine | T-SQL scripting via `pyodbc` (.sql) or native `BACKUP DATABASE` (.bak) |
| Compression | Python `zipfile` (built-in) + [pyzipper](https://pypi.org/project/pyzipper/) for AES-256 passwords |
| Job storage | SQLite via Python `sqlite3` |
| Packaging | [PyInstaller](https://pyinstaller.org/) |

---

## Project structure

```
MySQL-BK/
├── main.py                 # Entry point, single-instance guard, VC++ auto-install
├── requirements.txt
├── mysql_backup.spec       # PyInstaller spec
├── setup.bat               # Install dependencies
├── run.bat                 # Run from source (with console)
├── run.vbs                 # Run from source (no console)
├── build.bat               # Build standalone .exe
├── core/
│   ├── autostart.py        # Windows registry autostart helper
│   ├── backup.py           # BackupRunner — mysqldump + ZIP compression (dispatches to MSSQL runner)
│   ├── db_connector.py     # MySQLConnector — lists databases/tables
│   ├── mssql_connector.py  # MSSQLConnector — lists databases/tables via pyodbc
│   ├── mssql_backup.py     # MSSQLBackupRunner — T-SQL scripting via pyodbc
│   └── scheduler.py        # BackupScheduler — APScheduler wrapper
├── models/
│   └── job.py              # BackupJob dataclass
├── storage/
│   └── database.py         # SQLite persistence layer
└── ui/
    ├── main_window.py      # Main window and system tray
    ├── job_dialog.py       # Add/Edit job dialog
    └── log_viewer.py       # Log history dialog
```
