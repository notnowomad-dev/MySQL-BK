import threading
from datetime import datetime
from typing import Callable, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.backup import BackupRunner
from models.job import BackupJob


class BackupScheduler:
    def __init__(self, database):
        self.db = database
        self._scheduler = BackgroundScheduler(
            job_defaults={"misfire_grace_time": 3600, "coalesce": True}
        )
        self._callbacks: Dict[str, Callable] = {}

    def start(self):
        self._scheduler.start()
        for job in self.db.get_all_jobs():
            if job.enabled:
                self.schedule_job(job)

    def stop(self):
        self._scheduler.shutdown(wait=False)

    # -------------------------------------------------------------- schedule --

    def schedule_job(self, job: BackupJob):
        self.unschedule_job(job.id)
        trigger = self._build_trigger(job)
        if trigger:
            self._scheduler.add_job(
                func=self._run_backup,
                trigger=trigger,
                args=[job.id],
                id=job.id,
                name=job.name,
                replace_existing=True,
            )

    def unschedule_job(self, job_id: str):
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def run_job_now(self, job_id: str):
        t = threading.Thread(target=self._run_backup, args=[job_id], daemon=True)
        t.start()

    def get_next_run(self, job_id: str) -> Optional[str]:
        try:
            apjob = self._scheduler.get_job(job_id)
            if apjob and apjob.next_run_time:
                return apjob.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------ callbacks --

    def register_callback(self, job_id: str, fn: Callable):
        self._callbacks[job_id] = fn

    def unregister_callback(self, job_id: str):
        self._callbacks.pop(job_id, None)

    # ------------------------------------------------------------ internals --

    def _build_trigger(self, job: BackupJob) -> Optional[CronTrigger]:
        try:
            hour, minute = map(int, job.schedule_time.split(":"))
            if job.schedule_type == "hourly":
                return CronTrigger(minute=minute)
            if job.schedule_type == "daily":
                return CronTrigger(hour=hour, minute=minute)
            if job.schedule_type == "weekly":
                days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                return CronTrigger(day_of_week=days[job.schedule_weekday], hour=hour, minute=minute)
            if job.schedule_type == "monthly":
                return CronTrigger(day=job.schedule_day, hour=hour, minute=minute)
            if job.schedule_type == "cron":
                return CronTrigger.from_crontab(job.schedule_cron)
        except Exception:
            pass
        return None

    def _run_backup(self, job_id: str):
        job = self.db.get_job(job_id)
        if not job:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        runner = BackupRunner(job)
        success, message = runner.run()
        status = "Success" if success else "Failed"

        self.db.update_job_status(job_id, timestamp, f"{status}: {message}")
        self.db.add_log(job_id, job.name, timestamp, status, message)

        cb = self._callbacks.get(job_id)
        if cb:
            try:
                cb(success, message)
            except Exception:
                pass
