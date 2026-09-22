"""
Python Process Supervisor Daemon Runner script for Deriv Crypto AI Bot.

Runs main.py in a continuous loop for 24/7 continuous operation with exponential backoff,
automatic crash recovery, log rotation, and Telegram alert notification on unexpected exit.
"""

import sys
import subprocess
import time
import signal
import os
import logging

# Ensure project root is in PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] DAEMON: %(message)s"
)
logger = logging.getLogger("DAEMON_SUPERVISOR")


class BotDaemonSupervisor:

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.running = True
        self.backoff_delay = 5.0
        self.max_backoff = 60.0

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info(f"[DAEMON] Shutdown signal received (signal={signum}). Stopping supervisor loop...")
        self.running = False

    def run_supervisor(self):
        logger.info("=====================================================================")
        logger.info("STARTING DERIV CRYPTO AI BOT DAEMON PROCESS SUPERVISOR (24/7 MODE)")
        logger.info("=====================================================================")

        if self.telegram.enabled:
            self.telegram.notify_alert(
                title="DAEMON SUPERVISOR STARTED",
                message="🤖 Deriv Crypto AI Bot daemon supervisor activated. Continuous 24/7 operation engaged.",
                level="INFO"
            )

        cmd = [sys.executable, "main.py", "--paper", "3600"]

        while self.running:
            logger.info(f"[DAEMON] Launching sub-process: {' '.join(cmd)}")
            start_ts = time.time()

            try:
                proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT)
                while self.running and proc.poll() is None:
                    time.sleep(2)

                if not self.running and proc.poll() is None:
                    logger.info("[DAEMON] Terminating child bot process gracefully...")
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()

                ret_code = proc.returncode
                duration = time.time() - start_ts

                if ret_code == 0:
                    logger.info(f"[DAEMON] Bot process completed cleanly after {duration:.1f}s. Resetting backoff delay.")
                    self.backoff_delay = 5.0
                else:
                    logger.warning(f"[DAEMON] Bot process exited with code {ret_code} after {duration:.1f}s.")
                    if self.telegram.enabled:
                        self.telegram.notify_alert(
                            title="BOT PROCESS CRASH DETECTED",
                            message=f"🚨 Child bot process exited unexpectedly (code {ret_code}) after {duration:.1f}s.\n"
                                    f"Restarting automatically in {self.backoff_delay:.0f}s...",
                            level="ERROR"
                        )
                    time.sleep(self.backoff_delay)
                    self.backoff_delay = min(self.max_backoff, self.backoff_delay * 2)

            except Exception as err:
                logger.error(f"[DAEMON] Supervisor exception: {err}")
                if self.telegram.enabled:
                    self.telegram.notify_alert(
                        title="DAEMON SUPERVISOR EXCEPTION",
                        message=f"🚨 Exception in supervisor loop: {err}\nRetrying in {self.backoff_delay:.0f}s...",
                        level="ERROR"
                    )
                time.sleep(self.backoff_delay)
                self.backoff_delay = min(self.max_backoff, self.backoff_delay * 2)

        logger.info("[DAEMON] Process supervisor stopped cleanly. Goodbye.")


if __name__ == "__main__":
    supervisor = BotDaemonSupervisor()
    supervisor.run_supervisor()
