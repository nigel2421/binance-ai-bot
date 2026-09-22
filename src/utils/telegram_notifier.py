"""
Telegram Notifier module for Deriv Crypto AI Bot.

Provides asynchronous and synchronous message dispatches to Telegram chat using bot token
for trading activity, paper execution alerts, settlements, and forward testing session reports.
"""

import os
import json
import logging
import asyncio
import urllib.request
import urllib.parse
from typing import Dict, List, Optional, Any

from src.config import config

logger = logging.getLogger("TELEGRAM_NOTIFIER")


class TelegramNotifier:
    """
    Handles dispatch of notification alerts to Telegram chat.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = config.telegram_bot_token if bot_token is None else bot_token
        self.chat_id = config.telegram_chat_id if chat_id is None else chat_id
        self.enabled = bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Synchronously dispatches text message to configured Telegram chat.
        Returns True on success, False on error.
        """
        if not self.enabled:
            logger.debug("[TELEGRAM_NOTIFIER] Telegram disabled (missing token or chat ID).")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                if res_json.get("ok"):
                    logger.debug("[TELEGRAM_NOTIFIER] Telegram notification dispatched successfully.")
                    return True
                else:
                    logger.warning(f"[TELEGRAM_NOTIFIER] Telegram API error: {res_json}")
                    return False
        except Exception as err:
            logger.error(f"[TELEGRAM_NOTIFIER] Failed to send Telegram message: {err}")
            return False

    async def send_message_async(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Asynchronously dispatches text message to Telegram using thread pool executor.
        """
        if not self.enabled:
            return False
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.send_message, text, parse_mode)

    def notify_startup(self, active_symbols: List[str], config_hash: str) -> bool:
        msg = (
            "🤖 *Deriv Crypto AI Bot Started*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Config Version:* `{config.get_config_fingerprint()['config_version']}`\n"
            f"• *Config Hash:* `{config_hash}`\n"
            f"• *Mode:* `PAPER TRADING (DRY_RUN=True)`\n"
            f"• *Monitored Markets:* {len(active_symbols)} (`{', '.join(active_symbols[:5])}`"
            f"{'...' if len(active_symbols)>5 else ''})\n"
            "• *Telegram Alerts:* `ACTIVE` ✅\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)

    def notify_paper_trade(self, record_id: str, symbol: str, direction: str, contract_type: str, stake: float, payout: float, score: float, ev: float) -> bool:
        emoji = "🟢" if direction == "BULLISH" else "🔴"
        msg = (
            f"{emoji} *PAPER TRADE EXECUTED*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Record ID:* `{record_id}`\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Direction:* `{direction}`\n"
            f"• *Contract:* `{contract_type}`\n"
            f"• *Stake:* `${stake:.2f}` | *Payout:* `${payout:.2f}`\n"
            f"• *Opportunity Score:* `{score:.1f}`\n"
            f"• *Expected Value (EV):* `${ev:.2f}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)

    def notify_settlement(self, record_id: str, symbol: str, status: str, pnl: float, spot_entry: float, spot_exit: float) -> bool:
        emoji = "🎉 WIN" if status == "WON" else "❌ LOSS"
        pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"
        msg = (
            f"📊 *PAPER TRADE SETTLED — {emoji}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Record ID:* `{record_id}`\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Status:* `{status}`\n"
            f"• *Paper PnL:* `{pnl_str}`\n"
            f"• *Spot Entry:* `{spot_entry:.2f}` → *Spot Exit:* `{spot_exit:.2f}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)

    def notify_session_summary(self, session_id: str, duration_sec: int, total_evals: int, qualified: int, pnl: float, balance: float) -> bool:
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        msg = (
            "🏁 *FORWARD TESTING SESSION REPORT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Session ID:* `{session_id}`\n"
            f"• *Duration:* `{duration_sec}s`\n"
            f"• *Evaluations:* `{total_evals}` | *Qualified:* `{qualified}`\n"
            f"• *Realized Paper PnL:* `{pnl_str}`\n"
            f"• *Paper Balance:* `${balance:.2f}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)

    def notify_alert(self, title: str, message: str, level: str = "WARNING") -> bool:
        emoji = "⚠️" if level == "WARNING" else "🚨" if level == "ERROR" else "ℹ️"
        msg = (
            f"{emoji} *BOT ALERT: {title.upper()}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{message}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)
