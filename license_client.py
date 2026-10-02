"""云端许可检查。无配置、断网、待批准或禁用时均不执行预约。"""

import _thread
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import socket
import threading
from urllib.request import Request, urlopen
import uuid


APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WechatBookingBot"
DEVICE_FILE = APP_DIR / "device.json"
# 固定云端许可入口；不能由用户设置文件或环境变量覆盖。
ENDPOINT = "https://booking-bot-d5gzn52le82e572c9-1499668155.ap-shanghai.app.tcloudbase.com/booking-license"
CHECK_INTERVAL_SECONDS = 600  # 运行与空闲时均每 10 分钟检查一次。
REQUEST_TIMEOUT_SECONDS = 5


class LicenseError(RuntimeError):
    pass


def device_identity():
    try:
        device = json.loads(DEVICE_FILE.read_text(encoding="utf-8"))
        uuid.UUID(device["id"])
        if len(bytes.fromhex(device["secret"])) != 32:
            raise ValueError("设备密钥长度错误")
        return device
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise LicenseError(f"本机设备凭据损坏，请联系管理员：{error}") from error

    device = {"id": str(uuid.uuid4()), "secret": secrets.token_hex(32)}
    APP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with DEVICE_FILE.open("x", encoding="utf-8") as file:
            json.dump(device, file)
    except FileExistsError:  # 界面与预约子进程可能同时首次登记。
        return device_identity()
    return device


def check_license(state):
    if not ENDPOINT.startswith("https://"):
        raise LicenseError("云端许可尚未配置，预约已停止")
    device = device_identity()
    payload = json.dumps({
        "id": device["id"], "secret": device["secret"],
        "computer": socket.gethostname()[:100], "state": state,
    }).encode("utf-8")
    request = Request(ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            result = json.load(response)
    except Exception as error:
        raise LicenseError(f"无法取得云端许可，预约已停止：{error}") from error
    if not isinstance(result, dict) or not isinstance(result.get("allowed"), bool):
        raise LicenseError("云端许可响应无效，预约已停止")
    if not result["allowed"]:
        raise LicenseError(f"云端未授权：{result.get('reason', '请联系管理员')}")
    return True


@contextmanager
def booking_guard():
    """开抢前立即检查；此后每十分钟检查，失效时中断主线程。"""
    check_license("booking")
    stop = threading.Event()

    def monitor():
        while not stop.wait(CHECK_INTERVAL_SECONDS):
            try:
                check_license("booking")
            except LicenseError as error:
                print(f"本轮结果：云端许可中断：{error}", flush=True)
                _thread.interrupt_main()
                return

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=REQUEST_TIMEOUT_SECONDS)
