# MySQL Backup Scheduler

A Windows desktop application for scheduling automated MySQL database backups with a clean GUI. Built as a reliable replacement for brittle `.bat` + Task Scheduler setups.

---

## Features

- **Multiple backup jobs** — create, edit, enable/disable, and delete independent jobs
- **Flexible scheduling** — Hourly, Daily, Weekly, Monthly, or custom Cron expression
- **Selective backup** — pick specific databases and/or individual tables per job
- **Three output modes**
  - Single `.sql` file (all selected DBs merged)
  - Multiple `.sql` files (one per database or table)
  - Daily overwrite — 7 rotating files (`mon.sql` … `sun.sql`) that overwrite each week
- **7-Zip compression** — optional `.7z` archive with optional password per job
- **System tray** — minimizes to tray; backups keep running while the window is hidden
- **Run Now** — trigger any job immediately from the UI
- **Log viewer** — per-job history of every run (timestamp, status, message)
- **Single-instance** — launching a second copy restores the existing window instead

---

## Requirements

| Requirement | Notes |
|---|---|
| Windows 10 / 11 | 64-bit |
| MySQL server | Local or remote |
| `mysqldump.exe` | Comes with MySQL Server or MySQL Shell |
| Python 3.10+ | Only needed when running from source |
| 7-Zip (optional) | Required only if compression is enabled; default path `C:\Program Files\7-Zip\7z.exe` |

---

## Installation

### Option A — Pre-built executable (recommended)

Download `MySQL-Backup-Scheduler.exe` from the `dist/` folder (or the Releases page) and run it directly. No Python installation required.

### Option B — Run from source

```bat
# 1. Clone or download the project
# 2. Open a terminal in the project folder

setup.bat        # installs Python dependencies
```

Then launch with **`run.vbs`** (double-click) — starts the app with no CMD window.

`run.bat` is kept for debugging only; it shows a console so startup errors (e.g. missing imports) are visible.

---

## Building the executable

```bat
build.bat
```

This produces `dist\MySQL-Backup-Scheduler.exe` via PyInstaller. The resulting file is fully self-contained and can be copied anywhere.

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
| **Output** | Destination folder, SQL format, and optional 7-Zip compression |

4. Click **OK** to save. The job appears in the main list and starts running on schedule automatically.

---

## Job settings reference

### Connection tab

| Field | Description |
|---|---|
| Host | MySQL server hostname or IP (default: `localhost`) |
| Port | MySQL port (default: `3306`) |
| Username | MySQL user |
| Password | MySQL password (stored locally in SQLite) |
| mysqldump path | Full path to `mysqldump.exe`, or just `mysqldump` if it is on `PATH` |
| Test Connection | Verifies credentials before saving |

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

**SQL output format**

| Mode | Behaviour |
|---|---|
| Single `.sql` file | All selected databases dumped into one timestamped file |
| Multiple `.sql` files | One file per database, or one per table when specific tables are selected |
| Daily overwrite | Produces `jobname_dbname_mon.sql` … `jobname_dbname_sun.sql`; each weekday's file overwrites the previous week's — capped at 7 files per database |

**Compression**

- Enable **Compress with 7-Zip** to produce `.7z` archives instead of plain `.sql` files.
- Optionally set a **password**; the archive will use AES-256 encryption with header encryption (`-mhe=on`).
- The path to `7z.exe` can be changed if 7-Zip is installed in a non-default location.

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

Right-clicking a row shows the same actions plus **Open Destination Folder**.

---

## System tray

- Closing or minimizing the window hides it to the tray — backups keep running.
- **Single-click** or **double-click** the tray icon to restore the window.
- Right-click the tray icon for **Restore GUI** or **Exit**.

---

## File locations

| Path | Contents |
|---|---|
| `%APPDATA%\MySQLBackup\` | SQLite database (`jobs.db`) storing all jobs and logs |
| Output directory (per job) | Generated `.sql` or `.7z` backup files |

---

## Troubleshooting

**`mysqldump not found`**
Set the full path to `mysqldump.exe` in the Connection tab (e.g. `C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe`), or add the MySQL `bin` folder to your system `PATH`.

**`7-Zip not found`**
Install 7-Zip from [7-zip.org](https://www.7-zip.org/) or set the correct path to `7z.exe` in the Output tab.

**Job shows "Failed" in status**
Open the Logs viewer (toolbar or right-click menu) to read the full error message from the last run.

**Application won't start / database error**
Delete `%APPDATA%\MySQLBackup\jobs.db` to reset all job data and start fresh.

---

## Tech stack

| Component | Library |
|---|---|
| GUI | [PyQt6](https://pypi.org/project/PyQt6/) |
| Scheduler | [APScheduler](https://apscheduler.readthedocs.io/) 3.x |
| MySQL connectivity | [mysql-connector-python](https://pypi.org/project/mysql-connector-python/) |
| Backup engine | `mysqldump` (system binary) |
| Compression | 7-Zip (system binary) |
| Job storage | SQLite via Python `sqlite3` |
| Packaging | [PyInstaller](https://pyinstaller.org/) |

---

## Project structure

```
MySQL-BK/
├── main.py                 # Entry point, single-instance guard
├── requirements.txt
├── mysql_backup.spec       # PyInstaller spec
├── setup.bat               # Install dependencies
├── run.bat                 # Run from source
├── build.bat               # Build standalone .exe
├── core/
│   ├── backup.py           # BackupRunner — calls mysqldump and 7-Zip
│   ├── db_connector.py     # MySQLConnector — lists databases/tables
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
