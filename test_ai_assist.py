import queue
import threading
import time
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from PIL import Image

import ai_assist
import main
import enter_booking


class AiRecoveryTests(unittest.TestCase):
    def setUp(self):
        enable = patch.object(ai_assist, "ENABLE_AI_ASSIST", True)
        enable.start()
        self.addCleanup(enable.stop)
        payment_check = patch.object(main, "payment_appeared_during_recovery", return_value=False)
        payment_check.start()
        self.addCleanup(payment_check.stop)

    def test_disabled_ai_never_starts_connects_or_captures(self):
        client = ai_assist.AiAssist()
        capture = Mock()
        with (patch.object(ai_assist, "ENABLE_AI_ASSIST", False),
              patch.object(ai_assist.threading, "Thread") as thread,
              patch.object(ai_assist.subprocess, "Popen") as popen,
              patch.object(ai_assist, "find_codex") as find):
            client.start()
            self.assertIsNone(client.decide("test", capture, lambda: False))
            self.assertIn("未启动 Codex", ai_assist.check_connection())
            with self.assertRaises(RuntimeError):
                client._connect("C:/test")
            thread.assert_not_called()
            popen.assert_not_called()
            find.assert_not_called()
            capture.assert_not_called()

    def test_disabled_main_and_recovery_skip_ai_and_waiting(self):
        with (patch.object(ai_assist, "ENABLE_AI_ASSIST", False),
              patch.object(main, "booking_guard", return_value=nullcontext()),
              patch.object(main, "run_booking") as booking,
              patch.object(main.ai_assistant, "start") as start,
              patch.object(main.ai_assistant, "close") as close,
              patch.object(main.ai_assistant, "decide") as decide,
              patch.object(main.keyboard, "is_pressed", return_value=False),
              patch.object(main, "resize_wechat", return_value=True),
              patch.object(main, "recover_page", return_value=True) as recover,
              patch.object(main.time, "sleep") as sleep):
            main.main()
            booking.assert_called_once()
            self.assertTrue(main.recover_with_ai("test"))
            recover.assert_called_once()
            start.assert_not_called()
            close.assert_not_called()
            decide.assert_not_called()
            sleep.assert_not_called()

    def test_answers_are_strictly_limited(self):
        self.assertEqual(ai_assist.parse_action('{"action":"resize"}'), "resize")
        for text in ('{}', '[]', '{"action":"click"}', '{"action":"refresh","x":10}', 'invalid'):
            with self.assertRaises((ValueError, TypeError)):
                ai_assist.parse_action(text)

    def test_tool_overrides_do_not_create_invalid_servers(self):
        client = ai_assist.AiAssist()
        config = '[mcp_servers.node_repl]\ncommand="node"\n[plugins."code-review@openai-bundled"]\nenabled=true\n'
        responses = [{}, {"account": {"type": "chatgpt"}},
                     {"data": [{"model": "gpt-6-luna"}, {"model": "gpt-5.6-luna"}]},
                     {"thread": {"id": "test"}, "model": "gpt-5.6-luna", "reasoningEffort": "low", "serviceTier": "priority"}]
        with (patch.object(ai_assist, "find_codex", return_value="codex.exe"),
              patch.object(ai_assist.Path, "read_text", return_value=config),
              patch.object(ai_assist.subprocess, "Popen") as popen,
              patch.object(ai_assist.threading, "Thread"),
              patch.object(client, "_rpc", side_effect=responses)):
            client._connect("C:/test")
        command = popen.call_args.args[0]
        settings = [command[index + 1] for index, value in enumerate(command) if value == "-c"]
        self.assertEqual([value for value in settings if value.startswith("mcp_servers")], ["mcp_servers={}"])
        plugins = next(value for value in settings if value.startswith("plugins="))
        self.assertEqual(ai_assist.tomllib.loads(plugins)["plugins"], {"code-review@openai-bundled": {"enabled": False}})

    def test_server_must_confirm_selected_model_low_and_fast(self):
        client = ai_assist.AiAssist()
        response = {"thread": {"id": "test"}, "model": "gpt-5.6-luna", "reasoningEffort": "low", "serviceTier": "priority"}
        with patch.object(client, "_rpc", return_value=response) as rpc:
            self.assertEqual(client._new_thread("C:/test", time.monotonic() + 1), "test")
            params = rpc.call_args.args[1]
            self.assertEqual(params["model"], "gpt-5.6-luna")
            self.assertEqual(params["serviceTier"], "fast")
            self.assertEqual(params["config"]["model_reasoning_effort"], "low")
        for key, value in (("model", "gpt-6-luna"), ("reasoningEffort", "medium"), ("serviceTier", "default")):
            with patch.object(client, "_rpc", return_value={**response, key: value}):
                with self.assertRaises(RuntimeError):
                    client._new_thread("C:/test", time.monotonic() + 1)

    def test_unavailable_model_does_not_silently_switch(self):
        client = ai_assist.AiAssist()
        with (patch.object(ai_assist, "find_codex", return_value="codex.exe"),
              patch.object(ai_assist.Path, "read_text", return_value=""),
              patch.object(ai_assist.subprocess, "Popen"),
              patch.object(ai_assist.threading, "Thread"),
              patch.object(client, "_rpc", side_effect=[{}, {"account": {"type": "chatgpt"}}, {"data": [{"model": "gpt-6-luna"}]}]),
              patch.object(client, "_new_thread") as new_thread):
            with self.assertRaises(RuntimeError):
                client._connect("C:/test")
            new_thread.assert_not_called()

    def test_unavailable_connection_does_not_wait_or_capture(self):
        client = ai_assist.AiAssist()
        capture = Mock()
        with patch.object(client, "start"):
            started = time.monotonic()
            self.assertIsNone(client.decide("unknown", capture, lambda: False))
            self.assertLess(time.monotonic() - started, 0.1)
        capture.assert_not_called()

    def test_timeout_and_late_answer_do_not_execute(self):
        client = ai_assist.AiAssist()
        client.ready.set()
        image = Image.new("RGB", (80, 80), "white")
        def answer_late():
            task = client.requests.get(timeout=1)
            time.sleep(0.08)
            task[3].put(("resize", image.resize((32, 32)).tobytes()))
        worker = threading.Thread(target=answer_late)
        worker.start()
        with patch.object(client, "start"), patch.object(ai_assist, "AI_TIMEOUT_SECONDS", 0.04):
            started = time.monotonic()
            self.assertIsNone(client.decide("unknown", lambda: image, lambda: False))
            self.assertLess(time.monotonic() - started, 0.075)
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())

    def test_changed_screen_discards_decision(self):
        client = ai_assist.AiAssist()
        client.ready.set()
        before = Image.new("RGB", (80, 80), "white")
        after = Image.new("RGB", (80, 80), "black")
        def reply():
            task = client.requests.get(timeout=1)
            task[3].put(("refresh", before.resize((32, 32)).tobytes()))
        worker = threading.Thread(target=reply)
        worker.start()
        with patch.object(client, "start"):
            self.assertIsNone(client.decide("unknown", lambda: after, lambda: False))
        worker.join(timeout=1)

    def test_completed_turn_and_invalid_turn(self):
        client = ai_assist.AiAssist()
        client.model = {"supportedReasoningEfforts": [{"reasoningEffort": "low"}]}
        client.thread_id = "thread"
        notifications = [
            {"method": "item/completed", "params": {"threadId": "old", "turnId": "turn", "item": {"type": "agentMessage", "text": '{"action":"resize"}'}}},
            {"method": "item/completed", "params": {"threadId": "thread", "turnId": "turn", "item": {"type": "agentMessage", "text": '{"action":"refresh"}'}}},
            {"method": "turn/completed", "params": {"threadId": "thread", "turn": {"id": "turn", "status": "completed"}}},
        ]
        image = Image.new("RGB", (80, 80), "white")
        with (patch.object(client, "_rpc", return_value={"turn": {"id": "turn"}}) as rpc,
              patch.object(client, "_receive", side_effect=notifications), patch.object(image, "save")):
            result = client._ask("test", lambda: image, time.monotonic() + 1, "C:/test")
        self.assertEqual(result[0], "refresh")
        self.assertEqual(rpc.call_args.args[1]["effort"], "low")
        self.assertEqual(rpc.call_args.args[1]["serviceTier"], "fast")

    def test_deadline_expires_even_with_queued_notifications(self):
        client = ai_assist.AiAssist()
        client.messages = queue.Queue()
        client.messages.put({"method": "progress"})
        with self.assertRaises(queue.Empty):
            client._receive(time.monotonic() - 1)

    def test_no_answer_refreshes_and_esc_stops(self):
        with (patch.object(main.ai_assistant, "decide", return_value=None),
              patch.object(main.keyboard, "is_pressed", return_value=False),
              patch.object(main, "resize_wechat", return_value=True),
              patch.object(main, "recover_page", return_value=True) as recover):
            self.assertTrue(main.recover_with_ai("page unknown"))
            recover.assert_called_once_with()
        with (patch.object(main.keyboard, "is_pressed", return_value=True),
              patch.object(main.ai_assistant, "decide") as decide,
              patch.object(main, "recover_page") as recover):
            self.assertFalse(main.recover_with_ai("page unknown"))
            decide.assert_not_called()
            recover.assert_not_called()

    def test_exception_in_ai_also_refreshes(self):
        with (patch.object(main.ai_assistant, "decide", side_effect=OSError("offline")),
              patch.object(main.keyboard, "is_pressed", return_value=False),
              patch.object(main, "resize_wechat", return_value=True),
              patch.object(main, "recover_page", return_value=True) as recover):
            self.assertTrue(main.recover_with_ai("test"))
            recover.assert_called_once()

    def test_payment_that_appears_while_ai_waits_is_not_refreshed(self):
        with (patch.object(main.ai_assistant, "decide", return_value=None),
              patch.object(main.keyboard, "is_pressed", return_value=False),
              patch.object(main, "payment_appeared_during_recovery", return_value=True),
              patch.object(main, "recover_page") as recover):
            self.assertEqual(main.recover_with_ai("payment delayed"), main.PAYMENT_READY)
            recover.assert_not_called()

    def test_unknown_page_does_not_click_entry(self):
        with (patch.object(main, "refresh_booking", return_value=True),
              patch.object(main, "check_page", return_value=False),
              patch.object(main, "restore_entry_window", return_value=True),
              patch.object(main, "check_entry", return_value=False),
              patch.object(main, "move_mouse") as click):
            self.assertFalse(main.recover_page())
            click.assert_not_called()

    def test_recoverable_exception_retries_existing_booking(self):
        with (patch.object(main, "CALIBRATION_PATH", None),
              patch.object(main, "restore_entry_window", return_value=True),
              patch.object(main, "enter_booking", return_value=True),
              patch.object(main, "resize_wechat", return_value=True),
              patch.object(main.keyboard, "is_pressed", return_value=False),
              patch.object(main, "select_tomorrow", side_effect=[RuntimeError("微信不在首页"), main.SOLD_OUT]) as select,
              patch.object(main, "recover_with_ai", return_value=True) as recover):
            main.run_booking()
            self.assertEqual(select.call_count, 2)
            recover.assert_called_once()

    def test_normal_booking_never_asks_ai(self):
        with (patch.object(main, "CALIBRATION_PATH", None),
              patch.object(main, "restore_entry_window", return_value=True),
              patch.object(main, "enter_booking", return_value=True),
              patch.object(main, "resize_wechat", return_value=True),
              patch.object(main.keyboard, "is_pressed", return_value=False),
              patch.object(main, "select_tomorrow", return_value=True),
              patch.object(main, "select_court", return_value=[("19:00-20:00", 1)]),
              patch.object(main, "submit_booking", return_value=True),
              patch.object(main, "wait_verify", return_value=True),
              patch.object(main, "wait_payment", return_value=True),
              patch.object(main.ai_assistant, "decide") as decide):
            main.run_booking()
            decide.assert_not_called()

    def test_stuck_entry_returns_to_ai_instead_of_looping_forever(self):
        with (patch.object(enter_booking.keyboard, "is_pressed", return_value=False),
              patch.object(enter_booking, "check_page", return_value=False),
              patch.object(enter_booking, "check_entry", return_value=True),
              patch.object(enter_booking, "PAGE_LOAD_SECONDS", 0),
              patch.object(enter_booking, "move_mouse") as click):
            self.assertFalse(enter_booking.enter_booking())
            self.assertEqual(click.call_count, 5)


if __name__ == "__main__":
    unittest.main()
