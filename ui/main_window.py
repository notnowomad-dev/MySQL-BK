from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QSystemTrayIcon, QMenu, QMessageBox, QToolBar, QLabel,
    QAbstractItemView, QProgressBar, QAction,
)
import os
import subprocess
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QFont

from models.job import BackupJob
from ui.job_dialog import JobDialog
from ui.log_viewer import LogViewer
from core.autostart import get_autostart, set_autostart


class MainWindow(QMainWindow):
    # Emitted from background thread when a job finishes — queued to main thread
    _job_finished = pyqtSignal(bool, str, str)   # success, message, job_name

    def __init__(self, database, scheduler):
        super().__init__()
        self.db = database
        self.scheduler = scheduler
        self._jobs: dict[str, BackupJob] = {}

        self.setWindowTitle("MySQL Backup Scheduler")
        self.setMinimumSize(950, 580)

        self._setup_tray()
        self._setup_ui()
        self._refresh_jobs()

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_jobs)
        self._timer.start(30_000)

        # Progress bar wiring
        self._progress_timer = QTimer()
        self._progress_timer.timeout.connect(self._tick_progress)
        self._job_finished.connect(self._on_job_finished)

    # ----------------------------------------------------------------- tray --

    def _setup_tray(self):
        icon = self._make_icon()
        self.setWindowIcon(icon)
        self._tray = QSystemTrayIcon(icon, self)

        menu = QMenu()
        restore_action = menu.addAction("Restore GUI")
        restore_action.triggered.connect(self._restore_window)
        menu.addSeparator()
        self._autostart_action = QAction("Start with Windows", self)
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(get_autostart())
        self._autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction(self._autostart_action)
        menu.addSeparator()
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self._quit)

        self._tray.setContextMenu(menu)
        self._tray.setToolTip("MySQL Backup Scheduler — running in background")
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _make_icon(self) -> QIcon:
        px = QPixmap(32, 32)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#1565C0"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 32, 32, 6, 6)
        p.setPen(QColor("white"))
        f = QFont("Arial", 10, QFont.Bold)
        p.setFont(f)
        p.drawText(px.rect(), Qt.AlignCenter, "DB")
        p.end()
        return QIcon(px)

    # ------------------------------------------------------------------- ui --

    def _setup_ui(self):
        bar = QToolBar("Main")
        bar.setMovable(False)
        self.addToolBar(bar)

        def act(label, slot, tip=""):
            a = QAction(label, self)
            a.triggered.connect(slot)
            if tip:
                a.setToolTip(tip)
            bar.addAction(a)
            return a

        act("＋ Add Job", self._add_job)
        act("✎  Edit", self._edit_job)
        act("✕  Delete", self._delete_job)
        bar.addSeparator()
        act("▶  Run Now", self._run_now)
        bar.addSeparator()
        act("📋  Logs", self._view_logs)
        bar.addSeparator()
        act("🗙 Exit program", self._quit)
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Host", "Schedule", "Output Dir", "Enabled", "Last Run", "Status"]
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.doubleClicked.connect(self._edit_job)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self._table)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

        self._progress = QProgressBar()
        self._progress.setFixedWidth(200)
        self._progress.setFixedHeight(16)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.hide()
        self.statusBar().addPermanentWidget(self._progress)

    # ------------------------------------------------------------- refresh --

    def _refresh_jobs(self):
        jobs = self.db.get_all_jobs()
        self._jobs = {j.id: j for j in jobs}
        self._table.setRowCount(len(jobs))

        for row, job in enumerate(jobs):
            def cell(text, color: QColor = None):
                item = QTableWidgetItem(str(text) if text is not None else "")
                if color:
                    item.setForeground(color)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                return item

            self._table.setItem(row, 0, cell(job.name))
            self._table.setItem(row, 1, cell(f"{job.host}:{job.port}"))
            self._table.setItem(row, 2, cell(self._fmt_schedule(job)))
            self._table.setItem(row, 3, cell(job.output_dir))
            self._table.setItem(
                row, 4,
                cell("Yes" if job.enabled else "No",
                     QColor("#2e7d32") if job.enabled else QColor("#c62828")),
            )
            self._table.setItem(row, 5, cell(job.last_run or "Never"))

            st = job.last_status or ""
            sc = QColor("#2e7d32") if "Success" in st else (QColor("#c62828") if "Failed" in st else None)
            self._table.setItem(row, 6, cell(st, sc))

            # Store job id for lookup
            self._table.item(row, 0).setData(Qt.UserRole, job.id)

    @staticmethod
    def _fmt_schedule(job: BackupJob) -> str:
        if job.schedule_type == "hourly":
            sched = f"Hourly at :{job.schedule_time.split(':')[1]}"
        elif job.schedule_type == "daily":
            sched = f"Daily {job.schedule_time}"
        elif job.schedule_type == "weekly":
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            sched = f"Weekly {days[job.schedule_weekday]} {job.schedule_time}"
        elif job.schedule_type == "monthly":
            sched = f"Monthly day {job.schedule_day} {job.schedule_time}"
        elif job.schedule_type == "cron":
            sched = f"Cron: {job.schedule_cron}"
        else:
            sched = job.schedule_type
        if job.output_type == "daily_overwrite":
            sched += "  [7-day rotate]"
        return sched

    # ----------------------------------------------------------- selection --

    def _selected_job_id(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    # ------------------------------------------------------------ actions --

    def _add_job(self):
        dlg = JobDialog(parent=self)
        if dlg.exec():
            job = dlg.get_job()
            self.db.save_job(job)
            if job.enabled:
                self.scheduler.schedule_job(job)
            self._refresh_jobs()
            self.statusBar().showMessage(f"Job '{job.name}' created.")

    def _edit_job(self):
        job_id = self._selected_job_id()
        if not job_id:
            QMessageBox.information(self, "No selection", "Select a job to edit.")
            return
        job = self.db.get_job(job_id)
        dlg = JobDialog(job=job, parent=self)
        if dlg.exec():
            updated = dlg.get_job()
            self.db.save_job(updated)
            if updated.enabled:
                self.scheduler.schedule_job(updated)
            else:
                self.scheduler.unschedule_job(updated.id)
            self._refresh_jobs()
            self.statusBar().showMessage(f"Job '{updated.name}' saved.")

    def _delete_job(self):
        job_id = self._selected_job_id()
        if not job_id:
            QMessageBox.information(self, "No selection", "Select a job to delete.")
            return
        job = self.db.get_job(job_id)
        if QMessageBox.question(
            self, "Delete job",
            f"Delete job '{job.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            self.scheduler.unschedule_job(job_id)
            self.db.delete_job(job_id)
            self._refresh_jobs()
            self.statusBar().showMessage(f"Job '{job.name}' deleted.")

    def _run_now(self):
        job_id = self._selected_job_id()
        if not job_id:
            QMessageBox.information(self, "No selection", "Select a job to run.")
            return
        job = self.db.get_job(job_id)

        def _done(success: bool, msg: str):
            # Called from background thread — emit signal to cross to main thread
            self._job_finished.emit(success, msg, job.name)

        self.scheduler.register_callback(job_id, _done)
        self.scheduler.run_job_now(job_id)
        self._start_progress(job.name)
        QMessageBox.information(self, "Job started", f"'{job.name}' is running in the background.")

    # --------------------------------------------------------- progress bar --

    def _start_progress(self, job_name: str):
        self._progress.setValue(0)
        self._progress.show()
        self._progress_timer.start(250)   # tick every 250 ms
        self.statusBar().showMessage(f"Running '{job_name}' …")

    def _tick_progress(self):
        v = self._progress.value()
        if v < 90:
            # Decelerate as it approaches 90 % so it never finishes before the job does
            self._progress.setValue(v + max(1, (90 - v) // 12))

    def _on_job_finished(self, success: bool, msg: str, job_name: str):
        self._progress_timer.stop()
        self._progress.setValue(100)
        label = "completed" if success else "FAILED"
        self.statusBar().showMessage(f"'{job_name}' {label}: {msg}")
        self._refresh_jobs()
        self._tray.showMessage(
            "MySQL Backup",
            f"{'✓' if success else '✗'} {job_name}: {msg}",
            QSystemTrayIcon.Information if success else QSystemTrayIcon.Critical,
            4000,
        )
        QTimer.singleShot(2000, self._reset_progress)

    def _reset_progress(self):
        self._progress.setValue(0)
        self._progress.hide()

    def _view_logs(self):
        job_id = self._selected_job_id()
        LogViewer(self.db, job_id, parent=self).exec()

    # --------------------------------------------------------- context menu --

    def _show_context_menu(self, pos):
        job_id = self._selected_job_id()
        menu = QMenu(self)

        if job_id:
            job = self.db.get_job(job_id)
            menu.addAction("✎  Edit Job",        self._edit_job)
            menu.addAction("▶  Run Now",          self._run_now)
            menu.addSeparator()
            open_act = menu.addAction("📁  Open Destination Folder")
            open_act.triggered.connect(lambda: self._open_folder(job.output_dir))
            menu.addSeparator()
            menu.addAction("📋  View Logs",       self._view_logs)
            menu.addSeparator()
            menu.addAction("✕  Delete Job",       self._delete_job)
            menu.addSeparator()
            menu.addAction("🗙 Exit program",       self._quit)
        else:
            menu.addAction("＋  Add Job",         self._add_job)

        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _open_folder(self, path: str):
        if not path:
            QMessageBox.warning(self, "No folder", "This job has no output directory set.")
            return
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "Cannot create folder", str(e))
                return
        subprocess.Popen(["explorer", os.path.normpath(path)])

    # ------------------------------------------------------------ tray/close --

    def _toggle_autostart(self, checked: bool):
        ok, err = set_autostart(checked)
        if not ok:
            QMessageBox.warning(self, "Autostart", f"Could not update registry:\n{err}")
            self._autostart_action.setChecked(not checked)

    def _restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.Trigger,       # single-click
            QSystemTrayIcon.DoubleClick,
        ):
            self._restore_window()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "MySQL Backup Scheduler",
                "Minimized to tray — backups continue running.\n"
                "Right-click the tray icon to restore or exit.",
                QSystemTrayIcon.Information,
                3000,
            )
            return
        super().changeEvent(event)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "MySQL Backup Scheduler",
            "Running in background — backups continue.\n"
            "Right-click the tray icon to restore or exit.",
            QSystemTrayIcon.Information,
            3000,
        )

    def _quit(self):
        self._timer.stop()
        self.scheduler.stop()
        from PyQt5.QtWidgets import QApplication
        QApplication.quit()
