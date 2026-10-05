import asyncio

from app.state.timers import ResettableTimer


async def test_timer_fires_after_delay():
    fired = asyncio.Event()

    async def on_fire():
        fired.set()

    timer = ResettableTimer(on_fire)
    timer.reset(0.05)
    assert timer.is_active
    await asyncio.wait_for(fired.wait(), timeout=1)


async def test_timer_cancel_prevents_fire():
    fired = False

    async def on_fire():
        nonlocal fired
        fired = True

    timer = ResettableTimer(on_fire)
    timer.reset(0.05)
    timer.cancel()
    await asyncio.sleep(0.1)
    assert fired is False
    assert not timer.is_active


async def test_timer_reset_restarts_countdown():
    fire_count = 0

    async def on_fire():
        nonlocal fire_count
        fire_count += 1

    timer = ResettableTimer(on_fire)
    timer.reset(0.1)
    await asyncio.sleep(0.05)
    timer.reset(0.1)  # reset truoc khi lan dau kip no
    await asyncio.sleep(0.07)
    assert fire_count == 0
    await asyncio.sleep(0.08)
    assert fire_count == 1
