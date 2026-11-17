import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _blocked(*a, **k):
    raise RuntimeError("network access is blocked in tests")


socket.socket.connect = _blocked
socket.create_connection = _blocked
