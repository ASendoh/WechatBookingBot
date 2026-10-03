"""运行此文件，将当前项目打包为可分享的单文件 Windows EXE。"""

from datetime import datetime
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

from license_client import APP_VERSION


PROJECT = Path(__file__).resolve().parent
APP_NAME = f"羽约助手V{APP_VERSION}"
ASSETS = ("booking_template.png", "mouse_actions.json")


def main():
    if os.name != "nt":
        raise RuntimeError("请在 Windows 上打包 Windows EXE")
    if importlib.util.find_spec("PyInstaller") is None:
        raise RuntimeError("未安装 PyInstaller，请先运行：python -m pip install pyinstaller")
    for filename in ("app.py", *ASSETS):
        if not (PROJECT / filename).is_file():
            raise FileNotFoundError(f"打包缺少文件：{filename}")

    output = PROJECT / "dist" / f"{APP_NAME}-{datetime.now():%Y%m%d-%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable, "-m", "PyInstaller", "--onefile", "--windowed",
        "--noconfirm", "--name", APP_NAME,
        "--hidden-import", "pystray._win32",
        "--distpath", str(output),
        "--workpath", str(PROJECT / "build" / APP_NAME),
        "--specpath", str(PROJECT / "build"),
    ]
    for filename in ASSETS:
        command.extend(("--add-data", f"{PROJECT / filename}:."))
    command.append("app.py")
    subprocess.run(command, cwd=PROJECT, check=True)
    exe = output / f"{APP_NAME}.exe"
    subprocess.run([str(exe), "--check-package"], check=True, timeout=60)
    print(f"打包并自检完成：{exe}")
    with exe.open("rb") as file:
        print(f"SHA-256：{hashlib.file_digest(file, 'sha256').hexdigest()}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, OSError, RuntimeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as error:
        raise SystemExit(f"打包失败：{error}") from error
