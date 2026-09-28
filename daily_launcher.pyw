"""登录后在后台等待每天 07:59:40 启动预约脚本。"""

from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
import time


PROJECT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)


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
                    [sys.executable, "--run-now"]
                    if getattr(sys, "frozen", False)
                    else [sys.executable, str(PROJECT / "main.py")],
                    cwd=PROJECT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
        time.sleep(1)


if __name__ == "__main__":
    if sys.argv[1:] == ["--check-package"]:
        # 只检查依赖和资源是否进入打包结果，不会点击微信。
        import main as booking_main  # noqa: F401
        from mouse_recorder import ACTION_FILE

        for file in (Path(__file__).with_name("booking_template.png"), ACTION_FILE):
            if not file.is_file():
                raise FileNotFoundError(file)
        print("打包自检通过")
    elif sys.argv[1:] == ["--run-now"]:
        import pyautogui
        from main import main as run_booking

        try:
            run_booking()
        except (KeyboardInterrupt, pyautogui.FailSafeException):
            print("程序已由用户紧急停止")
    else:
        main()
