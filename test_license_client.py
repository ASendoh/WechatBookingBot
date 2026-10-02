"""云端许可客户端离线自检：python test_license_client.py。"""

from io import BytesIO
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
