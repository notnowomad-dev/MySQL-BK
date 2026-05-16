from typing import List, Tuple

try:
    import pyodbc
    _PYODBC_OK = True
except ImportError:
    _PYODBC_OK = False

_SYSTEM_DBS = {"master", "tempdb", "model", "msdb"}


class MSSQLConnector:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        driver: str = "ODBC Driver 17 for SQL Server",
        windows_auth: bool = False,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.driver = driver
        self.windows_auth = windows_auth

    def _conn_str(self, database: str = "master") -> str:
        server = f"{self.host},{self.port}" if self.port != 1433 else self.host
        base = f"DRIVER={{{self.driver}}};SERVER={server};DATABASE={database};TrustServerCertificate=yes;"
        if self.windows_auth:
            return base + "Trusted_Connection=yes;"
        return base + f"UID={self.username};PWD={self.password};"

    def _connect(self, database: str = "master"):
        if not _PYODBC_OK:
            raise RuntimeError("pyodbc is not installed. Run: pip install pyodbc")
        return pyodbc.connect(self._conn_str(database), timeout=5)

    def test_connection(self) -> Tuple[bool, str]:
        try:
            conn = self._connect()
            conn.close()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)

    def get_databases(self) -> List[str]:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sys.databases "
                "WHERE state_desc = 'ONLINE' AND name NOT IN "
                "('master','tempdb','model','msdb') ORDER BY name"
            )
            dbs = [row[0] for row in cursor.fetchall()]
            conn.close()
            return dbs
        except Exception:
            return []

    def get_tables(self, database: str) -> List[str]:
        try:
            conn = self._connect(database)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT TABLE_SCHEMA + '.' + TABLE_NAME "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_SCHEMA, TABLE_NAME"
            )
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except Exception:
            return []

    @staticmethod
    def available_drivers() -> List[str]:
        if not _PYODBC_OK:
            return []
        return [d for d in pyodbc.drivers() if "SQL Server" in d]
