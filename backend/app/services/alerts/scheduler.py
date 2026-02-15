"""Background scheduler for time-based alert triggers.

Runs a simple asyncio loop that periodically checks for contract expiry,
probation end, and other scheduled triggers.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.database import async_session_factory
from app.services.alerts.alert_engine import run_scheduled_triggers

logger = logging.getLogger(__name__)

# Default interval: check every 6 hours (in seconds)
DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60

_scheduler_task: asyncio.Task | None = None


async def _scheduler_loop(interval: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Run scheduled triggers in a loop."""
    logger.info(
        "Alert scheduler started (interval=%ds / %.1fh)",
        interval,
        interval / 3600,
    )
    while True:
        try:
            async with async_session_factory() as db:
                try:
                    count = await run_scheduled_triggers(db)
                    await db.commit()
                    logger.info("Scheduler tick complete: %d events", count)
                except Exception:
                    await db.rollback()
                    logger.exception("Error during scheduled trigger run")
        except Exception:
            logger.exception("Error creating DB session in scheduler")

        await asyncio.sleep(interval)


def start_scheduler(interval: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Start the background scheduler as an asyncio task.

    Safe to call multiple times — only one scheduler will run.
    """
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        logger.warning("Scheduler already running, skipping start")
        return

    _scheduler_task = asyncio.create_task(
        _scheduler_loop(interval),
        name="alert-scheduler",
    )
    logger.info("Alert scheduler task created")


def stop_scheduler() -> None:
    """Stop the background scheduler if running."""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("Alert scheduler cancelled")
    _scheduler_task = None

