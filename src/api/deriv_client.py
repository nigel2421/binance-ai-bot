import asyncio
import json
import logging
import threading
import time
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
import websocket

from src.config import config

logger = logging.getLogger("API")

class ConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"

class DerivClient:
    """
    Robust WebSocket client for Deriv API using background websocket-client thread.
    Exposes async request/response matching via req_id correlation and callback streams.
    Implements connection supervision, exponential backoff reconnects, auto-authorization,
    and duplicate-free subscription restoration.
    """

    PRIMARY_ENDPOINT = "wss://red.derivws.com/websockets/v3"

    def __init__(
        self,
        app_id: Optional[str] = None,
        api_token: Optional[str] = None,
        ws_url: Optional[str] = None,
        on_disconnect_cb: Optional[Callable[[], None]] = None
    ):
        self.app_id = str(app_id or config.deriv_app_id).strip()
        self.api_token = (api_token or config.deriv_api_token).strip()
        self.ws_url = ws_url or self.PRIMARY_ENDPOINT
        self._on_disconnect_cb = on_disconnect_cb

        self.state: ConnectionState = ConnectionState.DISCONNECTED
        self.ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._running = False
        self._lock = threading.Lock()
        self._req_id_counter = 1

        # Correlation & Streams
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.active_subscriptions: Dict[str, Dict[str, Any]] = {}  # sub_id -> {request_payload, callback}
        self.symbol_subscriptions: Dict[str, str] = {}            # symbol -> sub_id

        # Liveness metrics
        self.last_message_time: float = 0.0
        self.last_ping_time: float = 0.0
        self.reconnect_attempts: int = 0
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

    def _next_req_id(self) -> int:
        with self._lock:
            req_id = self._req_id_counter
            self._req_id_counter += 1
            return req_id

    async def connect(self):
        """Establish background WebSocket connection."""
        if self.state in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED):
            return

        self._loop = asyncio.get_running_loop()
        self.state = ConnectionState.CONNECTING
        self._running = True

        endpoint = f"{self.ws_url.rstrip('/')}?app_id={self.app_id}"
        logger.info(f"[API] Connecting to Deriv WebSocket: {endpoint}")

        self.ws = websocket.WebSocketApp(
            endpoint,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        self._ws_thread = threading.Thread(target=self._run_ws, daemon=True, name="deriv-ws")
        self._ws_thread.start()

        # Wait up to 10 seconds for on_open to trigger
        for _ in range(50):
            if self.state in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED):
                break
            await asyncio.sleep(0.2)

        if self.state not in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED):
            self.state = ConnectionState.ERROR
            raise ConnectionError(f"Failed to connect to Deriv WebSocket at {endpoint} (state={self.state.value})")

        logger.info(f"[API] Connected to Deriv WebSocket successfully ({endpoint}).")

        # Start heartbeat
        if not self._heartbeat_task or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Authorize if token set
        if self.api_token:
            await self.authorize()

    def _run_ws(self):
        if self.ws:
            self.ws.run_forever(ping_interval=20, ping_timeout=10)

    def _on_open(self, ws):
        logger.info("[API] Deriv WebSocket connection established (on_open).")
        self.state = ConnectionState.CONNECTED
        self.last_message_time = time.time()
        self.reconnect_attempts = 0

    def _on_message(self, ws, raw_msg: str):
        self.last_message_time = time.time()
        try:
            data = json.loads(raw_msg)
        except json.JSONDecodeError:
            return

        # 1. Match req_id for pending asyncio futures
        req_id = data.get("req_id")
        if req_id is not None:
            with self._lock:
                fut = self.pending_requests.pop(req_id, None)
            if fut and not fut.done() and self._loop:
                self._loop.call_soon_threadsafe(self._resolve_future, fut, data)

        # 2. Match subscription streaming callbacks
        sub_info = data.get("subscription", {})
        sub_id = sub_info.get("id")
        msg_type = data.get("msg_type")

        if sub_id and sub_id in self.active_subscriptions:
            self.active_subscriptions[sub_id]["messages_received"] += 1
            cb = self.active_subscriptions[sub_id]["callback"]
            self._dispatch_callback(cb, data)
        elif msg_type == "tick" and "tick" in data:
            tick = data["tick"]
            symbol = tick.get("symbol")
            if symbol and symbol in self.symbol_subscriptions:
                sid = self.symbol_subscriptions[symbol]
                if sid in self.active_subscriptions:
                    self.active_subscriptions[sid]["messages_received"] += 1
                    cb = self.active_subscriptions[sid]["callback"]
                    self._dispatch_callback(cb, data)

    def _resolve_future(self, fut: asyncio.Future, data: Dict[str, Any]):
        if not fut.done():
            fut.set_result(data)

    def _dispatch_callback(self, cb: Callable, data: Dict[str, Any]):
        if self._loop and self._loop.is_running():
            if asyncio.iscoroutinefunction(cb):
                asyncio.run_coroutine_threadsafe(cb(data), self._loop)
            else:
                self._loop.call_soon_threadsafe(cb, data)

    def _on_error(self, ws, error):
        logger.error(f"[API] WebSocket error callback: {error}")

    def _on_close(self, ws, close_status, close_msg):
        logger.info(f"[API] WebSocket closed: {close_status} {close_msg}")
        previous_state = self.state
        self.state = ConnectionState.DISCONNECTED
        if self._on_disconnect_cb and self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._on_disconnect_cb)

        # Trigger automatic reconnection if unexpectedly closed during runtime
        if self._running and previous_state != ConnectionState.RECONNECTING:
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.reconnect(), self._loop)

    async def authorize(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Send authorize request with API token (strictly sanitized, zero credential leakage)."""
        auth_token = token or self.api_token
        if not auth_token:
            logger.info("[API] No API token provided; remaining in PUBLIC_MODE for market-data operations.")
            return {}

        self.state = ConnectionState.AUTHENTICATING
        masked_token = f"{auth_token[:3]}...{auth_token[-3:]}" if len(auth_token) > 6 else "***"
        logger.info(f"[API] Authorizing session with token [{masked_token}]...")
        
        try:
            res = await self.request({"authorize": auth_token})
        except Exception as err:
            self.state = ConnectionState.ERROR
            logger.error("[API] Authorization request failed due to connection error.")
            return {"error": {"message": "Authorization request failed"}}

        if "error" in res:
            self.state = ConnectionState.ERROR
            err_msg = res['error'].get('message', 'Authorization failed')
            logger.error(f"[API] Authorization REJECTED: {err_msg}")
            return res

        self.state = ConnectionState.AUTHENTICATED
        user_email = res.get("authorize", {}).get("email", "OK")
        logger.info(f"[API] Authorized successfully as user: {user_email}")
        return res

    async def request(self, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Send request message with req_id and await response."""
        # Stage 6 Safety Lock: Intercept buy / sell attempts in paper/dry-run mode
        if "buy" in payload or "sell" in payload:
            if config.dry_run or not config.live_trading:
                from src.execution.exceptions import LiveTradingSafetyViolation
                raise LiveTradingSafetyViolation(
                    f"[SAFETY_VIOLATION] Attempted to transmit live order execution payload '{payload}' "
                    f"while DRY_RUN={config.dry_run} and LIVE_TRADING={config.live_trading}."
                )

        if not self._loop:
            self._loop = asyncio.get_running_loop()

        if self.state in (ConnectionState.DISCONNECTED, ConnectionState.ERROR):
            await self.connect()

        req_id = self._next_req_id()
        msg_payload = dict(payload)
        msg_payload["req_id"] = req_id

        fut = self._loop.create_future()
        with self._lock:
            self.pending_requests[req_id] = fut

        try:
            if not self.ws:
                raise ConnectionError("WebSocket is not connected")
            self.ws.send(json.dumps(msg_payload))
            response = await asyncio.wait_for(fut, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            with self._lock:
                self.pending_requests.pop(req_id, None)
            logger.warning(f"[API] Request req_id={req_id} timed out after {timeout}s.")
            return {"error": {"message": f"Request timed out after {timeout}s"}}
        except Exception as err:
            with self._lock:
                self.pending_requests.pop(req_id, None)
            raise err

    async def subscribe(
        self,
        payload: Dict[str, Any],
        callback: Callable[[Dict[str, Any]], None],
        timeout: float = 10.0
    ) -> Optional[str]:
        """Send subscription request (subscribe=1) and register callback."""
        sub_payload = dict(payload)
        sub_payload["subscribe"] = 1

        response = await self.request(sub_payload, timeout=timeout)
        if "error" in response:
            logger.error(f"[API] Subscription failed: {response['error'].get('message')}")
            return None

        sub_info = response.get("subscription", {})
        sub_id = sub_info.get("id")
        if not sub_id:
            return None

        self.active_subscriptions[sub_id] = {
            "request_payload": payload,
            "callback": callback,
            "messages_received": 0,
            "created_at": time.time(),
        }

        if "ticks" in payload:
            self.symbol_subscriptions[payload["ticks"]] = sub_id

        logger.info(f"[API] Subscription established: sub_id={sub_id}")
        return sub_id

    def get_subscription_diagnostics(self) -> Dict[str, Any]:
        """Expose detailed subscription liveness telemetry."""
        now = time.time()
        return {
            "active_subscriptions_count": len(self.active_subscriptions),
            "symbol_subscriptions": dict(self.symbol_subscriptions),
            "active_subscriptions": {
                sid: {
                    "symbol": info.get("request_payload", {}).get("ticks"),
                    "messages_received": info.get("messages_received", 0),
                    "created_at": info.get("created_at", 0.0),
                    "age_seconds": round(now - info.get("created_at", now), 1),
                }
                for sid, info in self.active_subscriptions.items()
            },
            "reconnect_attempts": self.reconnect_attempts,
            "last_message_time": self.last_message_time,
            "seconds_since_last_ws_message": round(now - self.last_message_time, 2) if self.last_message_time else 99999.0,
        }

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Cancel an active subscription."""
        if subscription_id in self.active_subscriptions:
            res = await self.request({"forget": subscription_id})
            self.active_subscriptions.pop(subscription_id, None)
            for sym, sid in list(self.symbol_subscriptions.items()):
                if sid == subscription_id:
                    self.symbol_subscriptions.pop(sym, None)
            logger.info(f"[API] Unsubscribed sub_id={subscription_id}")
            return True
        return False

    async def ping(self) -> Dict[str, Any]:
        """Send ping request."""
        self.last_ping_time = time.time()
        return await self.request({"ping": 1}, timeout=5.0)

    async def _heartbeat_loop(self):
        while self._running:
            await asyncio.sleep(25)
            if self.state in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED):
                try:
                    await self.ping()
                except Exception as e:
                    logger.warning(f"[API] Heartbeat ping failed: {e}")

    async def _restore_subscriptions(self):
        """Re-establish active subscriptions after reconnection without duplicates."""
        if not self.active_subscriptions:
            return

        logger.info(f"[API] Restoring {len(self.active_subscriptions)} active subscriptions after reconnect...")
        old_subscriptions = list(self.active_subscriptions.values())
        self.active_subscriptions.clear()
        self.symbol_subscriptions.clear()

        for sub_data in old_subscriptions:
            payload = sub_data["request_payload"]
            callback = sub_data["callback"]
            await self.subscribe(payload, callback)

    async def reconnect(self):
        """Bounded exponential backoff reconnection and subscription restoration."""
        if self.state == ConnectionState.RECONNECTING:
            return

        self.state = ConnectionState.RECONNECTING
        while self._running:
            self.reconnect_attempts += 1
            backoff = min(2 ** self.reconnect_attempts, 60)
            logger.warning(f"[API] Connection lost. Attempting reconnect #{self.reconnect_attempts} in {backoff}s...")

            if self.ws:
                try:
                    self.ws.close()
                except Exception:
                    pass

            await asyncio.sleep(backoff)

            try:
                # Fail any pending futures from disconnected session
                with self._lock:
                    for req_id, fut in list(self.pending_requests.items()):
                        if not fut.done():
                            fut.set_exception(ConnectionError("WebSocket reconnected; pending request reset."))
                    self.pending_requests.clear()

                await self.connect()
                if self.api_token:
                    await self.authorize()
                await self._restore_subscriptions()
                logger.info("[API] DerivClient reconnected successfully and restored subscriptions.")
                break
            except Exception as e:
                logger.error(f"[API] Reconnect attempt #{self.reconnect_attempts} failed: {e}")

    async def disconnect(self):
        """Clean shutdown of WebSocket."""
        self._running = False
        self.state = ConnectionState.DISCONNECTED
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        logger.info("[API] DerivClient disconnected cleanly.")
