import socket

import pytest

from desktop import run


@pytest.fixture
def listening_port():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    yield server.getsockname()[1]
    server.close()


def test_busy_default_port_switches_to_a_free_one(monkeypatch, listening_port):
    monkeypatch.setattr(run, "DEFAULT_PORT", listening_port)
    monkeypatch.delenv("PENTASYNC_PORT", raising=False)

    run._choose_port()

    chosen = int(run.os.environ["PENTASYNC_PORT"])
    assert chosen != listening_port
    assert not run._port_in_use(chosen)
    monkeypatch.delenv("PENTASYNC_PORT")


def test_free_default_port_is_kept(monkeypatch):
    monkeypatch.setattr(run, "DEFAULT_PORT", run._free_port())
    monkeypatch.delenv("PENTASYNC_PORT", raising=False)

    run._choose_port()

    assert "PENTASYNC_PORT" not in run.os.environ


def test_explicit_port_is_respected(monkeypatch, listening_port):
    monkeypatch.setattr(run, "DEFAULT_PORT", listening_port)
    monkeypatch.setenv("PENTASYNC_PORT", "8123")

    run._choose_port()

    assert run.os.environ["PENTASYNC_PORT"] == "8123"
