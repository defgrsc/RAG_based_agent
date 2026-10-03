import time
from datetime import datetime, timedelta

from config import DAILY_REFRESH_HOUR, DAILY_REFRESH_MINUTE, REFRESH_SLEEP_SECONDS
from ingest import ingest_nthu_docs


def next_refresh_time(now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    scheduled = now.replace(
        hour=DAILY_REFRESH_HOUR,
        minute=DAILY_REFRESH_MINUTE,
        second=0,
        microsecond=0,
    )

    if scheduled <= now:
        scheduled += timedelta(days=1)

    return scheduled


def run_daily_refresh() -> None:
    print(f"Daily Refresh Scheduler Started: {DAILY_REFRESH_HOUR:02d}:{DAILY_REFRESH_MINUTE:02d}")

    while True:
        scheduled = next_refresh_time()
        wait_seconds = max((scheduled - datetime.now()).total_seconds(), 0)
        print(f"Next Refresh: {scheduled.strftime('%Y-%m-%d %H:%M:%S')}")

        while wait_seconds > 0:
            sleep_seconds = min(wait_seconds, REFRESH_SLEEP_SECONDS)
            time.sleep(sleep_seconds)
            wait_seconds = max((scheduled - datetime.now()).total_seconds(), 0)

        print(f"Daily Refresh Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            result = ingest_nthu_docs(replace=True)
            print(f"Daily Refresh Finished: {result}")
        except Exception as exc:
            print(f"Daily Refresh Failed: {exc}")


if __name__ == "__main__":
    run_daily_refresh()
