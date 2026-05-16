# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

_vcredist = 'vc_redist.x64.exe'
_datas = [(_vcredist, '.')] if os.path.exists(_vcredist) else []

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        # APScheduler
        'apscheduler',
        'apscheduler.schedulers',
        'apscheduler.schedulers.background',
        'apscheduler.schedulers.base',
        'apscheduler.triggers',
        'apscheduler.triggers.base',
        'apscheduler.triggers.cron',
        'apscheduler.triggers.cron.fields',
        'apscheduler.triggers.interval',
        'apscheduler.triggers.date',
        'apscheduler.executors',
        'apscheduler.executors.base',
        'apscheduler.executors.pool',
        'apscheduler.jobstores',
        'apscheduler.jobstores.base',
        'apscheduler.jobstores.memory',
        'apscheduler.events',
        'apscheduler.job',
        'apscheduler.util',
        # MySQL Connector
        'mysql',
        'mysql.connector',
        'mysql.connector.connection',
        'mysql.connector.cursor',
        'mysql.connector.errors',
        'mysql.connector.plugins',
        'mysql.connector.plugins.mysql_native_password',
        'mysql.connector.plugins.caching_sha2_password',
        'mysql.connector.locales',
        'mysql.connector.locales.eng',
        # Single-instance socket
        'PyQt5.QtNetwork',
        # MSSQL
        'pyodbc',
        # compression
        'pyzipper',
        'zipfile',
        # stdlib used at runtime
        'sqlite3',
        'uuid',
        'json',
        'threading',
        'subprocess',
        'dataclasses',
        # tzlocal used by APScheduler for timezone detection
        'tzlocal',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'PIL', 'PyQt6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MySQL-Backup-Scheduler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # set True if UPX is installed to shrink the exe
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # no black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',           # replace with 'assets/icon.ico' / None if you add one
)
