from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import uuid
import json


@dataclass
class BackupJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    databases: List[str] = field(default_factory=list)
    tables: Dict[str, List[str]] = field(default_factory=dict)  # {db: [] = all tables, db: [t1,t2] = specific}
    schedule_type: str = "daily"   # hourly, daily, weekly, monthly, cron
    schedule_time: str = "00:00"   # HH:MM — minute used for hourly
    schedule_weekday: int = 0      # 0=Mon … 6=Sun for weekly
    schedule_day: int = 1          # 1-28 for monthly
    schedule_cron: str = "0 0 * * *"
    output_dir: str = ""
    output_type: str = "single"    # single | multiple
    use_zip: bool = False
    zip_password: str = ""
    zip_path: str = r"C:\Program Files\7-Zip\7z.exe"
    enabled: bool = True
    last_run: Optional[str] = None
    last_status: str = ""
    mysqldump_path: str = "mysqldump"
    hex_blob: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["databases"] = json.dumps(d["databases"])
        d["tables"] = json.dumps(d["tables"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BackupJob":
        d = d.copy()
        if isinstance(d.get("databases"), str):
            d["databases"] = json.loads(d["databases"])
        if isinstance(d.get("tables"), str):
            d["tables"] = json.loads(d["tables"])
        # Drop unknown columns (DB migration safety)
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        d = {k: v for k, v in d.items() if k in valid}
        return cls(**d)
