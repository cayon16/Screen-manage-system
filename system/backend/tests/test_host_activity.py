import asyncio
import sys

import pytest

from app.commands import HostActivityCommand
from app.state import host_activity
from app.state.host_activity import HostActivityMonitor, last_input_tick


@pytest.mark.skipif(sys.platform != "win32", reason="GetLastInputInfo chi co tren Windows")
def test_last_input_tick_reads_a_real_value_on_windows():
    assert isinstance(last_input_tick(), int)


async def test_monitor_reports_only_when_the_tick_actually_changes(monkeypatch):
    ticks = iter([100, 100, 100, 250, 250, 400])
    monkeypatch.setattr(host_activity, "last_input_tick", lambda: next(ticks, 400))

    reported: list[object] = []

    async def submit(command):
        reported.append(command)

    monitor = HostActivityMonitor(submit, poll_sec=0)
    task = asyncio.create_task(monitor.run())
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    # Nguoi dung go phim lien tuc se lam GetLastInputInfo doi moi 2 giay 1 lan; chi duoc bao
    # khi that su co thay doi, khong duoc bom lien tuc lam nghen hang doi command.
    assert all(isinstance(c, HostActivityCommand) for c in reported)
    assert len(reported) >= 2


async def test_monitor_stops_quietly_when_the_platform_is_unsupported(monkeypatch):
    monkeypatch.setattr(host_activity, "last_input_tick", lambda: None)

    async def submit(command):
        raise AssertionError("khong duoc gui command nao khi khong doc duoc input may chu")

    await asyncio.wait_for(HostActivityMonitor(submit, poll_sec=0).run(), timeout=1)
