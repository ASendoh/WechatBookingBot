"""登录后在后台等待每天 07:59:40 启动预约脚本。"""

from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
import time


PROJECT = Path(__file__).resolve().parent


def next_start(now):
    target = now.replace(hour=7, minute=59, second=40, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def main():
    child = None
    while True:
        target = next_start(datetime.now())
        while (remaining := (target - datetime.now()).total_seconds()) > 0:
            time.sleep(min(remaining, 60 if remaining > 1 else 0.05))

        if (datetime.now() - target).total_seconds() <= 20 and (
            child is None or child.poll() is not None
        ):
            with (PROJECT / "scheduled_run.log").open("w", encoding="utf-8") as log:
                child = subprocess.Popen(
                    [sys.executable, str(PROJECT / "main.py")],
                    cwd=PROJECT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
        time.sleep(1)


if __name__ == "__main__":
    main()
