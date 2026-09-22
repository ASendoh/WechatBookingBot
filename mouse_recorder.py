"""F8 开始录制，Esc 停止保存；导入 play() 可回放。"""

import json
import time
from pathlib import Path

try:
    from pynput import keyboard, mouse
except ImportError as error:
    raise SystemExit("请先安装依赖：python -m pip install pynput") from error


ACTION_FILE = Path(__file__).with_name("mouse_actions.json")


def record():
    """等待 F8，然后录制鼠标操作，直到按下 Esc。"""
    print("按 F8 开始录制……")
    with keyboard.Listener(
        on_press=lambda key: False if key == keyboard.Key.f8 else None
    ) as listener:
        listener.join()

    events = []
    started = time.perf_counter()

    def now():
        return time.perf_counter() - started

    def on_move(x, y):
        events.append([now(), "move", x, y])

    def on_click(x, y, button, pressed):
        events.append([now(), "click", x, y, button.name, pressed])

    print("正在录制；按 Esc 结束并保存。")
    mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
    mouse_listener.start()
    with keyboard.Listener(
        on_press=lambda key: False if key == keyboard.Key.esc else None
    ) as listener:
        listener.join()
    mouse_listener.stop()
    mouse_listener.join()

    ACTION_FILE.write_text(json.dumps(events), encoding="utf-8")
    print(f"已保存到 {ACTION_FILE}")


def play():
    """回放 record() 保存的鼠标操作，供其他 Python 文件调用。"""
    events = json.loads(ACTION_FILE.read_text(encoding="utf-8"))
    controller = mouse.Controller()
    previous = 0.0

    for event in events:
        recorded_time, event_type, x, y, *details = event
        time.sleep(max(0.0, recorded_time - previous))
        controller.position = (x, y)
        if event_type == "click":
            button_name, pressed = details
            button = getattr(mouse.Button, button_name)
            (controller.press if pressed else controller.release)(button)
        previous = recorded_time


if __name__ == "__main__":
    record()
