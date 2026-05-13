from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QComboBox, QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


class LogViewer(QDialog):
    def __init__(self, database, job_id: str = None, parent=None):
        super().__init__(parent)
        self.db = database
        self.job_id = job_id
        self.setWindowTitle("Backup Logs")
        self.setMinimumSize(860, 500)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        vl = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Show last:"))
        self._limit = QComboBox()
        self._limit.addItems(["50", "100", "200", "500"])
        self._limit.setCurrentIndex(1)
        self._limit.currentIndexChanged.connect(self._load)
        top.addWidget(self._limit)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._load)
        top.addWidget(refresh)

        clear = QPushButton("Clear logs")
        clear.clicked.connect(self._clear)
        top.addWidget(clear)
        top.addStretch()
        vl.addLayout(top)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Timestamp", "Job", "Status", "Message"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        vl.addWidget(self._table)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        vl.addWidget(close)

    def _load(self):
        limit = int(self._limit.currentText())
        logs = self.db.get_logs(self.job_id, limit)
        self._table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            def cell(text, color: QColor = None):
                item = QTableWidgetItem(str(text) if text is not None else "")
                if color:
                    item.setForeground(color)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                return item

            self._table.setItem(row, 0, cell(log["timestamp"]))
            self._table.setItem(row, 1, cell(log["job_name"]))
            color = QColor("#2e7d32") if log["status"] == "Success" else QColor("#c62828")
            self._table.setItem(row, 2, cell(log["status"], color))
            self._table.setItem(row, 3, cell(log["message"]))

    def _clear(self):
        who = "selected job" if self.job_id else "all jobs"
        if QMessageBox.question(
            self, "Clear logs",
            f"Delete all log entries for {who}?",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            self.db.clear_logs(self.job_id)
            self._load()
