from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QPushButton, QLineEdit, QSpinBox, QComboBox, QCheckBox, QTreeWidget,
    QTreeWidgetItem, QFileDialog, QLabel, QMessageBox, QDialogButtonBox,
    QGroupBox, QRadioButton, QButtonGroup, QTimeEdit, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTime, QTimer

from core.db_connector import MySQLConnector
from models.job import BackupJob


class JobDialog(QDialog):
    def __init__(self, job: Optional[BackupJob] = None, parent=None):
        super().__init__(parent)
        self._job = job or BackupJob()
        self.setWindowTitle("Add Backup Job" if job is None else "Edit Backup Job")
        self.setMinimumSize(720, 560)
        self._connector: Optional[MySQLConnector] = None
        self._setup_ui()
        if job:
            self._load_job(job)
            # Auto-load databases after dialog is shown; status label shows result, no popup on failure
            QTimer.singleShot(200, lambda: self._load_databases(silent=True))
        self._update_schedule_widgets()

    # ------------------------------------------------------------------- ui --

    def _setup_ui(self):
        root = QVBoxLayout(self)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Job Name:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. nightly_prod_backup")
        name_row.addWidget(self._name)
        root.addLayout(name_row)

        tabs = QTabWidget()
        tabs.addTab(self._tab_connection(), "Connection")
        tabs.addTab(self._tab_databases(), "Databases")
        tabs.addTab(self._tab_schedule(), "Schedule")
        tabs.addTab(self._tab_output(), "Output")
        root.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # --------------------------------------------------------- connection tab --

    def _tab_connection(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._host = QLineEdit("localhost")
        form.addRow("Host:", self._host)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(3306)
        form.addRow("Port:", self._port)

        self._user = QLineEdit("root")
        form.addRow("Username:", self._user)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        form.addRow("Password:", self._password)

        self._dump_path = QLineEdit("mysqldump")
        browse = QPushButton("Browse…")
        browse.setFixedWidth(80)
        browse.clicked.connect(self._browse_dump)
        row_w = QWidget()
        QHBoxLayout(row_w).addWidget(self._dump_path)
        row_w.layout().addWidget(browse)
        row_w.layout().setContentsMargins(0, 0, 0, 0)
        form.addRow("mysqldump:", row_w)

        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_conn)
        self._conn_label = QLabel()
        row2 = QWidget()
        hl = QHBoxLayout(row2)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(test_btn)
        hl.addWidget(self._conn_label)
        hl.addStretch()
        form.addRow("", row2)
        return w

    # --------------------------------------------------------- databases tab --

    def _tab_databases(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)

        info = QLabel(
            "Check the databases/tables to include. "
            "Leave everything unchecked to back up all databases."
        )
        info.setWordWrap(True)
        vl.addWidget(info)

        hl = QHBoxLayout()
        load_btn = QPushButton("↻  Reload Databases")
        load_btn.clicked.connect(lambda: self._load_databases(silent=False))
        hl.addWidget(load_btn)
        self._db_status = QLabel("")
        self._db_status.setStyleSheet("color: grey; font-style: italic;")
        hl.addWidget(self._db_status)
        hl.addStretch()
        vl.addLayout(hl)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name"])
        self._tree.header().setStretchLastSection(True)
        self._tree.itemChanged.connect(self._tree_item_changed)
        vl.addWidget(self._tree)
        return w

    # ---------------------------------------------------------- schedule tab --

    def _tab_schedule(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)

        type_box = QGroupBox("Frequency")
        type_lay = QHBoxLayout(type_box)

        self._sched_group = QButtonGroup(self)
        self._sched_radios: dict[str, QRadioButton] = {}
        for key, label in [
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("cron", "Custom Cron"),
        ]:
            rb = QRadioButton(label)
            self._sched_radios[key] = rb
            self._sched_group.addButton(rb)
            type_lay.addWidget(rb)
            rb.toggled.connect(self._update_schedule_widgets)
        vl.addWidget(type_box)

        time_box = QGroupBox("When")
        form = QFormLayout(time_box)

        self._time_edit = QTimeEdit(QTime(0, 0))
        self._time_edit.setDisplayFormat("HH:mm")
        form.addRow("Time (HH:MM):", self._time_edit)

        self._weekday = QComboBox()
        self._weekday.addItems(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"])
        form.addRow("Day of week:", self._weekday)

        self._month_day = QSpinBox()
        self._month_day.setRange(1, 28)
        form.addRow("Day of month:", self._month_day)

        self._cron_expr = QLineEdit("0 0 * * *")
        self._cron_expr.setPlaceholderText("min hour day month weekday")
        form.addRow("Cron expression:", self._cron_expr)

        vl.addWidget(time_box)
        vl.addStretch()

        # Set default AFTER all widgets exist so the toggled signal fires safely
        self._sched_radios["daily"].setChecked(True)
        return w

    def _update_schedule_widgets(self):
        if not hasattr(self, "_weekday"):
            return
        st = self._schedule_type()
        self._weekday.setVisible(st == "weekly")
        self._month_day.setVisible(st == "monthly")
        self._cron_expr.setVisible(st == "cron")
        self._time_edit.setVisible(st != "cron")

    def _schedule_type(self) -> str:
        for k, rb in self._sched_radios.items():
            if rb.isChecked():
                return k
        return "daily"

    # ----------------------------------------------------------- output tab --

    def _tab_output(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._out_dir = QLineEdit()
        self._out_dir.setPlaceholderText("Select output folder…")
        br = QPushButton("Browse…")
        br.setFixedWidth(80)
        br.clicked.connect(self._browse_outdir)
        dw = QWidget()
        dh = QHBoxLayout(dw)
        dh.setContentsMargins(0, 0, 0, 0)
        dh.addWidget(self._out_dir)
        dh.addWidget(br)
        form.addRow("Output directory:", dw)

        fmt_box = QGroupBox("SQL output format")
        fmt_lay = QVBoxLayout(fmt_box)
        self._single_rb = QRadioButton("Single .sql file  (all selected DBs/tables merged)")
        self._multi_rb = QRadioButton("Multiple .sql files  (one file per database or table)")
        self._daily_rb = QRadioButton(
            "Daily overwrite  —  7 rotating files per database\n"
            "    e.g. jobname_dbname_mon.sql … jobname_dbname_sun.sql\n"
            "    Each weekday overwrites last week's file (max 7 files per DB)"
        )
        self._fmt_group = QButtonGroup(self)
        for rb in (self._single_rb, self._multi_rb, self._daily_rb):
            self._fmt_group.addButton(rb)
            fmt_lay.addWidget(rb)
        self._single_rb.setChecked(True)
        form.addRow(fmt_box)

        zip_box = QGroupBox("Compression")
        zip_form = QFormLayout(zip_box)

        self._use_zip = QCheckBox("Compress output as .zip  (open with Windows Explorer — no extra software needed)")
        zip_form.addRow(self._use_zip)

        self._zip_pass = QLineEdit()
        self._zip_pass.setEchoMode(QLineEdit.Password)
        self._zip_pass.setPlaceholderText("Leave empty for no password  (requires pyzipper for encrypted zips)")
        zip_form.addRow("Password:", self._zip_pass)
        form.addRow(zip_box)

        self._hex_blob = QCheckBox("Use --hex-blob  (dump BLOB/BINARY columns as hex — safer for binary data)")
        self._hex_blob.setChecked(True)
        form.addRow(self._hex_blob)

        self._enabled = QCheckBox("Enable this job (run on schedule)")
        self._enabled.setChecked(True)
        form.addRow(self._enabled)
        return w

    # ------------------------------------------------------- browse helpers --

    def _browse_dump(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select mysqldump.exe", "", "Executables (*.exe)")
        if p:
            self._dump_path.setText(p)

    def _browse_outdir(self):
        p = QFileDialog.getExistingDirectory(self, "Select output directory")
        if p:
            self._out_dir.setText(p)

    # ------------------------------------------------------- connection test --

    def _test_conn(self):
        c = MySQLConnector(self._host.text(), self._port.value(),
                           self._user.text(), self._password.text())
        ok, msg = c.test_connection()
        self._conn_label.setText(msg)
        self._conn_label.setStyleSheet("color: green" if ok else "color: red")
        if ok:
            self._connector = c

    # ---------------------------------------------------- database tree load --

    def _load_databases(self, silent: bool = False):
        self._db_status.setStyleSheet("color: grey; font-style: italic;")
        self._db_status.setText("Connecting…")

        c = MySQLConnector(self._host.text(), self._port.value(),
                           self._user.text(), self._password.text())
        ok, msg = c.test_connection()
        if not ok:
            self._db_status.setStyleSheet("color: red;")
            self._db_status.setText(f"Connection failed: {msg}")
            if not silent:
                QMessageBox.warning(self, "Connection failed", msg)
            return
        self._connector = c

        self._tree.blockSignals(True)
        self._tree.clear()
        databases = c.get_databases()
        for db in databases:
            db_item = QTreeWidgetItem([db])
            db_item.setCheckState(0, Qt.Unchecked)
            db_item.setData(0, Qt.UserRole, ("db", db))
            for table in c.get_tables(db):
                t_item = QTreeWidgetItem([table])
                t_item.setCheckState(0, Qt.Unchecked)
                t_item.setData(0, Qt.UserRole, ("table", db, table))
                db_item.addChild(t_item)
            self._tree.addTopLevelItem(db_item)
        self._tree.expandAll()
        self._tree.blockSignals(False)
        self._apply_saved_selections()

        self._db_status.setStyleSheet("color: green;")
        self._db_status.setText(f"{len(databases)} database(s) loaded")

        # Switch to Databases tab so user sees the result
        self.findChild(QTabWidget).setCurrentIndex(1)

    def _apply_saved_selections(self):
        if not self._job.databases:
            return
        self._tree.blockSignals(True)
        for i in range(self._tree.topLevelItemCount()):
            db_item = self._tree.topLevelItem(i)
            db_name = db_item.text(0)
            if db_name not in self._job.databases:
                continue
            selected_tables = self._job.tables.get(db_name, [])
            if not selected_tables:
                # Check all children
                db_item.setCheckState(0, Qt.Checked)
                for j in range(db_item.childCount()):
                    db_item.child(j).setCheckState(0, Qt.Checked)
            else:
                for j in range(db_item.childCount()):
                    ch = db_item.child(j)
                    state = Qt.Checked if ch.text(0) in selected_tables else Qt.Unchecked
                    ch.setCheckState(0, state)
                self._update_parent_state(db_item)
        self._tree.blockSignals(False)

    def _tree_item_changed(self, item: QTreeWidgetItem, col: int):
        self._tree.blockSignals(True)
        state = item.checkState(0)
        # Propagate down to children
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, state)
        # Update parent partial check
        parent = item.parent()
        if parent:
            self._update_parent_state(parent)
        self._tree.blockSignals(False)

    @staticmethod
    def _update_parent_state(parent: QTreeWidgetItem):
        checked = sum(
            1 for i in range(parent.childCount())
            if parent.child(i).checkState(0) == Qt.Checked
        )
        total = parent.childCount()
        if checked == 0:
            parent.setCheckState(0, Qt.Unchecked)
        elif checked == total:
            parent.setCheckState(0, Qt.Checked)
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)

    # ----------------------------------------------------------- load/save --

    def _load_job(self, job: BackupJob):
        self._name.setText(job.name)
        self._host.setText(job.host)
        self._port.setValue(job.port)
        self._user.setText(job.username)
        self._password.setText(job.password)
        self._dump_path.setText(job.mysqldump_path)

        if job.schedule_type in self._sched_radios:
            self._sched_radios[job.schedule_type].setChecked(True)
        h, m = map(int, job.schedule_time.split(":"))
        self._time_edit.setTime(QTime(h, m))
        self._weekday.setCurrentIndex(job.schedule_weekday)
        self._month_day.setValue(job.schedule_day)
        self._cron_expr.setText(job.schedule_cron)

        self._out_dir.setText(job.output_dir)
        if job.output_type == "multiple":
            self._multi_rb.setChecked(True)
        elif job.output_type == "daily_overwrite":
            self._daily_rb.setChecked(True)
        else:
            self._single_rb.setChecked(True)

        self._use_zip.setChecked(job.use_zip)
        self._zip_pass.setText(job.zip_password)
        self._hex_blob.setChecked(job.hex_blob)
        self._enabled.setChecked(job.enabled)

    def _accept(self):
        if not self._name.text().strip():
            QMessageBox.warning(self, "Validation", "Please enter a job name.")
            return
        if not self._out_dir.text().strip():
            QMessageBox.warning(self, "Validation", "Please select an output directory.")
            return
        self.accept()

    def get_job(self) -> BackupJob:
        job = self._job
        job.name = self._name.text().strip()
        job.host = self._host.text().strip()
        job.port = self._port.value()
        job.username = self._user.text().strip()
        job.password = self._password.text()
        job.mysqldump_path = self._dump_path.text().strip() or "mysqldump"

        job.schedule_type = self._schedule_type()
        job.schedule_time = self._time_edit.time().toString("HH:mm")
        job.schedule_weekday = self._weekday.currentIndex()
        job.schedule_day = self._month_day.value()
        job.schedule_cron = self._cron_expr.text().strip()

        job.output_dir = self._out_dir.text().strip()
        if self._multi_rb.isChecked():
            job.output_type = "multiple"
        elif self._daily_rb.isChecked():
            job.output_type = "daily_overwrite"
        else:
            job.output_type = "single"
        job.use_zip = self._use_zip.isChecked()
        job.zip_password = self._zip_pass.text()
        job.hex_blob = self._hex_blob.isChecked()
        job.enabled = self._enabled.isChecked()

        # Collect selected databases / tables from tree
        job.databases = []
        job.tables = {}
        for i in range(self._tree.topLevelItemCount()):
            db_item = self._tree.topLevelItem(i)
            if db_item.checkState(0) == Qt.Unchecked:
                continue
            db_name = db_item.text(0)
            job.databases.append(db_name)
            sel_tables = [
                db_item.child(j).text(0)
                for j in range(db_item.childCount())
                if db_item.child(j).checkState(0) == Qt.Checked
            ]
            all_checked = (db_item.checkState(0) == Qt.Checked
                           and db_item.childCount() > 0
                           and len(sel_tables) == db_item.childCount())
            job.tables[db_name] = [] if all_checked else sel_tables
        return job
