"""云端许可客户端离线自检：python test_license_client.py。"""

from io import BytesIO
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import license_client as client


def run_tests():
    with TemporaryDirectory() as folder:
        with (patch.object(client, "APP_DIR", Path(folder)),
              patch.object(client, "DEVICE_FILE", Path(folder) / "device.json"),
              patch.object(client, "ENDPOINT", "https://example.invalid/license")):
            first = client.device_identity()
            assert client.device_identity() == first
            assert len(first["secret"]) == 64

            def response(allowed):
                return BytesIO(json.dumps({"allowed": allowed, "reason": "待批准"}).encode())

            with patch.object(client, "urlopen", return_value=response(True)) as send:
                assert client.check_license("booking")
                assert json.loads(send.call_args.args[0].data)["id"] == first["id"]
                assert json.loads(send.call_args.args[0].data)["version"] == client.APP_VERSION
            executable = b"example executable"
            update = {
                "version": "1.2.0", "url": "https://example.invalid/new.exe",
                "sha256": hashlib.sha256(executable).hexdigest(),
            }
            payload = BytesIO(json.dumps({"allowed": False, "update": update}).encode())
            with patch.object(client, "urlopen", return_value=payload):
                try:
                    client.check_license("idle")
                except client.UpdateRequired as error:
                    assert error.version == "1.2.0"
                    with patch.object(client, "urlopen", return_value=BytesIO(executable)):
                        downloaded = client.download_update(error)
                    assert downloaded.read_bytes() == executable
                else:
                    raise AssertionError("旧版本不应继续使用")
            invalid = client.UpdateRequired("1.2.0", update["url"], "0" * 64)
            with patch.object(client, "urlopen", return_value=BytesIO(executable)):
                try:
                    client.download_update(invalid)
                except client.LicenseError:
                    assert not list((Path(folder) / "updates").glob("*.part"))
                else:
                    raise AssertionError("校验失败的更新文件不应保留")
            with patch.object(client, "urlopen", return_value=response(False)):
                try:
                    client.check_license("booking")
                except client.LicenseError as error:
                    assert "待批准" in str(error)
                else:
                    raise AssertionError("待批准设备不应执行预约")
            with patch.object(client, "urlopen", side_effect=OSError("offline")):
                try:
                    client.check_license("booking")
                except client.LicenseError as error:
                    assert "预约已停止" in str(error)
                else:
                    raise AssertionError("断网后不应执行预约")
    print("许可客户端自检通过")


if __name__ == "__main__":
    run_tests()
