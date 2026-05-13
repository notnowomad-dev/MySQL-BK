from typing import List, Tuple
import mysql.connector
from mysql.connector import Error

_SYSTEM_DBS = {"information_schema", "performance_schema", "mysql", "sys"}


class MySQLConnector:
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def _connect(self, database: str = None):
        kwargs = dict(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            connection_timeout=5,
            use_pure=True,  # avoid C-extension crash on Server 2016 / older Windows
        )
        if database:
            kwargs["database"] = database
        return mysql.connector.connect(**kwargs)

    def test_connection(self) -> Tuple[bool, str]:
        try:
            conn = self._connect()
            conn.close()
            return True, "Connection successful"
        except Error as e:
            return False, str(e)

    def get_databases(self) -> List[str]:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            dbs = [row[0] for row in cursor.fetchall()]
            conn.close()
            return [db for db in dbs if db not in _SYSTEM_DBS]
        except Error:
            return []

    def get_tables(self, database: str) -> List[str]:
        try:
            conn = self._connect(database)
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except Error:
            return []
