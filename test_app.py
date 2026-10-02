"""窗口版的无点击自检：python test_app.py。"""

from datetime import datetime
from io import BytesIO, TextIOWrapper
import os
from pathlib import Path
from queue import SimpleQueue
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call, patch

from app import BookingWindow, TIME_MODES, next_start, validate_settings


def run_tests():
    for old_name in ("晚场", "晚场（先20点、后19点）"):
        assert validate_settings("17", old_name, "07:59:40")["time_mode"] == "19:00-21:00"
        assert old_name not in TIME_MODES
    assert TIME_MODES["19:00-21:00"] == (["19:00-20:00", "20:00-21:00"], False)
    assert TIME_MODES["10:30-12:30"] == (["10:30-11:30", "11:30-12:30"], False)
    assert TIME_MODES["仅10:30-11:30"] == (["10:30-11:30"], False)
    assert TIME_MODES["仅11:30-12:30"] == (["11:30-12:30"], False)
    assert validate_settings("17", "19:00-21:00", None)["start_time"] is None
    morning = "仅07:30-08:30（真实预约）"
    assert morning not in TIME_MODES
    try:
        validate_settings("1", morning, "07:59:40")
    except ValueError:
        pass
    else:
        raise AssertionError("早场不应出现在用户界面中")
    for court in ("0", "18", "abc"):
        try:
            validate_settings(court, "19:00-21:00", "07:59:40")
        except ValueError:
            pass
        else:
            raise AssertionError(f"场地号 {court} 应被拒绝")
    assert next_start(datetime(2026, 9, 28, 7, 59, 39), "07:59:40") == datetime(
        2026, 9, 28, 7, 59, 40
    )
    assert next_start(datetime(2026, 9, 28, 7, 59, 40), "07:59:40") == datetime(
        2026, 9, 29, 7, 59, 40
    )

    os.environ["WECHAT_BOOKING_COURT"] = "1"
    os.environ["WECHAT_BOOKING_TIMES"] = "07:30-08:30"
    os.environ["WECHAT_BOOKING_MORNING_FALLBACK"] = "0"
    import config
    from select_court import booking_order

    assert config.courts == [1]
    assert config.times == ["07:30-08:30"]
    assert booking_order(config.times) == ["07:30-08:30"]
    assert booking_order(["19:00-20:00", "20:00-21:00"]) == [
        "20:00-21:00", "19:00-20:00"
    ]
    assert booking_order(TIME_MODES["10:30-12:30"][0]) == [
        "11:30-12:30", "10:30-11:30"
    ]
    import app
    legacy_profile = {"TIME_Y": {"07:30-08:30": 100, "19:00-20:00": 200,
                                 "20:00-21:00": 300}}
    with patch.object(app, "load_profile", return_value=legacy_profile):
        try:
            app.calibration_warnings(TIME_MODES["10:30-12:30"][0])
        except ValueError as error:
            assert "重新校准" in str(error)
        else:
            raise AssertionError("旧校准缺少新时段时应提示重新校准")

    import resize_wechat
    with (patch.object(resize_wechat, "ENTRY_WINDOW_RECT", (10, 20, 760, 1300)),
          patch.object(resize_wechat.win32gui, "FindWindow", return_value=1),
          patch.object(resize_wechat.win32gui, "GetWindowPlacement",
                       return_value=(0, resize_wechat.win32con.SW_SHOWMAXIMIZED)),
          patch.object(resize_wechat.win32gui, "ShowWindow") as show,
          patch.object(resize_wechat.win32gui, "SetWindowPos") as move,
          patch.object(resize_wechat.win32gui, "SetForegroundWindow"),
          patch.object(resize_wechat.win32gui, "GetForegroundWindow", return_value=1),
          patch.object(resize_wechat.time, "sleep")):
        assert resize_wechat.restore_entry_window()
        show.assert_called_once_with(1, resize_wechat.win32con.SW_RESTORE)
        move.assert_called_once_with(1, None, 10, 20, 760, 1300,
                                     resize_wechat.win32con.SWP_NOZORDER)
        with (patch.object(resize_wechat, "BOOKING_WINDOW_MAXIMIZED", True),
              patch.object(resize_wechat.win32gui, "GetWindowRect", return_value=(0, 0, 760, 1300))):
            assert resize_wechat.resize_wechat()
            show.assert_any_call(1, resize_wechat.win32con.SW_MAXIMIZE)

    with (patch.object(resize_wechat.win32gui, "FindWindow", return_value=1),
          patch.object(resize_wechat.win32gui, "GetForegroundWindow", return_value=2),
          patch.object(resize_wechat.pyautogui, "click") as click):
        try:
            resize_wechat.click_wechat(42, 43)
        except RuntimeError:
            pass
        else:
            raise AssertionError("微信被遮挡时不应执行点击")
        click.assert_not_called()

    import move_mouse
    with (patch.object(move_mouse, "BADMINTON_POS", (42, 43)),
          patch.object(move_mouse, "click_wechat") as click):
        move_mouse.move_mouse()
        click.assert_called_once_with(42, 43)

    import enter_booking
    with (patch.object(enter_booking.keyboard, "is_pressed", return_value=False),
          patch.object(enter_booking, "check_page", return_value=True),
          patch.object(enter_booking, "move_mouse") as click):
        assert enter_booking.enter_booking()
        click.assert_not_called()
    with (patch.object(enter_booking.keyboard, "is_pressed", return_value=False),
          patch.object(enter_booking, "check_page", return_value=False),
          patch.object(enter_booking, "check_entry", return_value=False),
          patch.object(enter_booking, "ENTRY_UNKNOWN_GRACE_SECONDS", 0),
          patch.object(enter_booking, "move_mouse") as click):
        assert not enter_booking.enter_booking()
        click.assert_not_called()

    import main as booking_main
    with (patch.object(booking_main, "refresh_booking", return_value=True),
          patch.object(booking_main, "check_page", return_value=True),
          patch.object(booking_main, "restore_entry_window") as restore,
          patch.object(booking_main, "move_mouse") as click):
        assert booking_main.recover_page()
        restore.assert_not_called()
        click.assert_not_called()
    with (patch.object(booking_main, "refresh_booking", return_value=True),
          patch.object(booking_main, "check_page", side_effect=(False, False, True)),
          patch.object(booking_main, "restore_entry_window", return_value=True) as restore,
          patch.object(booking_main, "move_mouse") as click,
          patch.object(booking_main, "resize_wechat", return_value=True) as resize,
          patch.object(booking_main.keyboard, "is_pressed", return_value=False)):
        assert booking_main.recover_page()
        restore.assert_called_once_with()
        click.assert_called_once_with()
        resize.assert_called_once_with()
    with (patch.object(booking_main, "refresh_booking", return_value=True),
          patch.object(booking_main, "check_page", return_value=False),
          patch.object(booking_main, "restore_entry_window", return_value=True),
          patch.object(booking_main, "move_mouse") as click,
          patch.object(booking_main, "ENTRY_UNKNOWN_GRACE_SECONDS", 0)):
        assert not booking_main.recover_page()
        click.assert_called_once_with()

    window = BookingWindow.__new__(BookingWindow)
    window.armed = False
    window.court = Mock()
    window.court.get.return_value = "17"
    window.time_mode = Mock()
    window.time_mode.get.return_value = "19:00-21:00"
    window.start_time = Mock()
    window.root = Mock()
    window.status = Mock()
    window.tray_actions = SimpleQueue()
    window.tray_icon = Mock(visible=True)
    window.tray_thread = Mock()
    window.tray_thread.is_alive.return_value = True
    window.launch = Mock(return_value=True)
    window.set_active = Mock()
    import app
    with (patch.object(app, "load_profile", return_value={"SLIDER_START_POS": [809, 684]}),
          patch.object(app, "CalibrationWindow") as wizard):
        window.calibrate()
        assert wizard.call_args.kwargs["previous_profile"]["SLIDER_START_POS"] == [809, 684]
    with (patch.object(app, "load_profile", return_value={"SLIDER_START_POS": [809, 684]}) as load,
          patch.object(app, "CalibrationWindow") as wizard):
        window.calibrate_morning()
        load.assert_called_once_with()
        assert wizard.call_args.kwargs["existing_profile"]["SLIDER_START_POS"] == [809, 684]
    with patch("app.messagebox.askyesno", return_value=True):
        window.test_run()
    assert window.settings["court"] == 17 and window.target is None
    window.start_time.get.assert_not_called()
    window.launch.assert_called_once_with()
    window.set_active.assert_called_once_with(True)

    window.armed = True
    window.child = Mock(returncode=0)
    window.child.poll.return_value = 0
    window.log_offset = None
    window.progress = Mock()
    window.status = Mock()
    window.show_warnings = Mock()
    window.set_active.reset_mock()
    window.tick()
    window.set_active.assert_called_once_with(False)
    window.root.deiconify.assert_called_once_with()
    window.status.set.assert_called_with("测试已结束（退出码 0）")

    window.armed = True
    window.child = Mock(returncode=0)
    window.child.poll.return_value = 0
    window.result = "目标时段已抢空，停止今天的预约"
    window.tick()
    window.status.set.assert_called_with("目标时段已抢空，停止今天的预约")

    import app
    with (TemporaryDirectory() as directory,
          patch.object(app, "LOG_FILE", Path(directory) / "test.log"),
          patch.object(app, "calibration_warnings", return_value=[]),
          patch.object(app, "check_license", return_value=True),
          patch.object(app.subprocess, "Popen") as spawn,
          patch.object(app.ctypes.windll.user32, "AllowSetForegroundWindow", return_value=1) as allow):
        window.child = None
        window.log_pending = False
        window.settings = {"court": 17, "time_mode": "19:00-21:00", "start_time": None}
        window.target = None
        spawn.return_value.pid = 12345
        window.launch = BookingWindow.launch.__get__(window, BookingWindow)
        assert window.launch()
        spawn.assert_called_once()
        allow.assert_called_once_with(12345)
        assert spawn.call_args.kwargs["env"]["WECHAT_BOOKING_COURT"] == "17"
        assert spawn.call_args.kwargs["env"]["WECHAT_BOOKING_TIMES"] == "19:00-20:00,20:00-21:00"
        assert spawn.call_args.kwargs["env"]["WECHAT_BOOKING_MORNING_FALLBACK"] == "1"
        assert spawn.call_args.kwargs["env"]["PYTHONUNBUFFERED"] == "1"
        assert spawn.call_args.kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
        assert spawn.call_args.args[0] == [app.sys.executable, str(app.PROJECT / "main.py")]
        window.status.set.assert_called_with("测试运行中")
        window.root.withdraw.assert_called_once_with()
        app.LOG_FILE.write_text("调整窗口\n开始选择第二天\n", encoding="utf-8")
        with patch.object(app, "datetime") as clock:
            clock.now.return_value = datetime(2026, 9, 28, 13, 2, 42)
            window.read_progress()
        assert window.progress.insert.call_args_list == [
            call("end", "[2026-09-28 13:02:42]  ", "timestamp"),
            call("end", "调整窗口\n"),
            call("end", "[2026-09-28 13:02:42]  ", "timestamp"),
            call("end", "开始选择第二天\n"),
        ], window.progress.insert.call_args_list
        window.status.set.assert_called_with("正在执行：开始选择第二天")
        with app.LOG_FILE.open("a", encoding="utf-8") as log:
            log.write("本轮结果：目标时段已抢空，停止今天的预约\n")
        window.read_progress()
        assert window.result == "目标时段已抢空，停止今天的预约"

        window.log_offset = 0
        window.progress.reset_mock()
        app.LOG_FILE.write_bytes("第 1 次点击第二天\n".encode("gbk"))
        window.read_progress()
        window.progress.insert.assert_any_call("end", "第 1 次点击第二天\n")

        window.child = None
        window.target = datetime(2026, 9, 29, 7, 59, 40)
        spawn.reset_mock()
        assert window.launch()
        assert spawn.call_args.kwargs["env"]["WECHAT_BOOKING_MORNING_FALLBACK"] == "0"

    window.armed = False
    window.child = None
    window.license_results = SimpleQueue()
    window.license_checking = True
    window.license_next_check = float("inf")
    window.license_results.put(app.LicenseError("设备已禁用"))
    window.tick()
    window.status.set.assert_called_with("云端许可不可用：设备已禁用")
    window.license_next_check = float("inf")
    window.tray_actions.put("show")
    window.root.deiconify.reset_mock()
    window.tick()
    window.root.deiconify.assert_called_once_with()
    window.root.lift.assert_called_once_with()

    window.root.withdraw.reset_mock()
    window.armed = True
    window.target = datetime(2026, 9, 29, 7, 59, 40)
    window.close()
    window.root.withdraw.assert_called_once_with()
    window.root.destroy.assert_not_called()
    assert window.armed and window.target == datetime(2026, 9, 29, 7, 59, 40)
    window.tray_icon.visible = False
    with patch("app.messagebox.askyesno", return_value=False):
        window.close()
    window.root.destroy.assert_not_called()
    window.tray_icon.visible = True
    window.armed = False
    window.tray_actions.put("quit")
    window.tick()
    window.tray_icon.stop.assert_called_once_with()
    window.root.destroy.assert_called_once_with()

    with (patch.object(resize_wechat.win32gui, "GetForegroundWindow", side_effect=(2, 2, 1)),
          patch.object(resize_wechat.win32gui, "SetForegroundWindow") as activate,
          patch.object(resize_wechat.time, "sleep")):
        assert resize_wechat.wechat_in_front(1, activate=True)
        assert activate.call_count == 2

    output = app.subprocess.check_output(
        [app.sys.executable, "-c", "print('中文步骤')"],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert output.decode("utf-8").strip() == "中文步骤"

    binary = BytesIO()
    legacy_stream = TextIOWrapper(binary, encoding="cp1252", write_through=True)
    with patch.object(app.sys, "stdout", legacy_stream):
        app.configure_child_output()
        print("中文步骤")
    assert binary.getvalue().decode("utf-8").strip() == "中文步骤"

    print("窗口设置与时间顺序自检通过")


if __name__ == "__main__":
    run_tests()
