"""A small client for Switch: the Gateway (people and setup) and the agent
protocol (Customs).

Agent protocol, as documented in Switch's docs/official/internals/agent-protocol.md:
- one SSE stream down, HTTP up, `Authorization: Bearer <agent API key>`;
- the client picks a connection id and reuses it across reconnects;
- a heartbeat every 2 s keeps the connection alive (TTL 6 s); 404 or 409 on
  the beat means "reopen the stream", never "back off";
- rooms are declared on the stream URL so catch-up covers them.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import httpx

log = logging.getLogger("airlock.switch")


class SwitchError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


def _check(resp: httpx.Response) -> Any:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise SwitchError(resp.status_code, str(detail)[:500])
    if not resp.content:
        return None
    return resp.json()


# ── Gateway: people, rooms, keys ─────────────────────────────────────────────


class Gateway:
    """The operator surface, authenticated with a session cookie."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(base_url=self.base_url + "/gateway", timeout=30)
        self.user: dict[str, Any] | None = None

    def login(self, email: str, password: str) -> dict[str, Any]:
        self.user = _check(
            self.http.post("/auth/login", json={"email": email, "password": password})
        )
        return self.user

    def create_user(self, name: str, email: str, password: str) -> dict[str, Any]:
        return _check(
            self.http.post(
                "/users", json={"name": name, "email": email, "password": password}
            )
        )

    def users(self) -> list[dict[str, Any]]:
        return _check(self.http.get("/users"))

    def create_registration_key(self, label: str) -> str:
        return _check(self.http.post("/api-keys", json={"label": label}))["key"]

    def agents(self) -> list[dict[str, Any]]:
        return _check(self.http.get("/agents"))

    def delete_agent(self, agent_id: str) -> None:
        _check(self.http.delete(f"/agents/{agent_id}"))

    def set_addressing_policy(
        self, agent_id: str, rules: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        policy = None if rules is None else {"rules": rules}
        return _check(
            self.http.put(f"/agents/{agent_id}/addressing-policy", json={"policy": policy})
        )

    def rooms(self) -> Any:
        return _check(self.http.get("/rooms"))

    def create_room(
        self,
        name: str,
        description: str,
        *,
        instructions: str | None = None,
        agent_ids: list[str] | None = None,
        private: bool = True,
        internal_only: bool = True,
        bridge_id: str | None = None,
    ) -> dict[str, Any]:
        visibility = "private" if private else "public"
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "instructions": instructions,
            "agent_ids": agent_ids or [],
            "internal_only": internal_only and bridge_id is None,
            "read_visibility": visibility,
            "write_visibility": visibility,
        }
        if bridge_id:
            body["bridge_id"] = bridge_id
        return _check(self.http.post("/rooms", json=body))

    def room(self, room_id: str) -> dict[str, Any]:
        return _check(self.http.get(f"/rooms/{room_id}"))

    def add_agents(self, room_id: str, agent_ids: list[str]) -> dict[str, Any]:
        return _check(self.http.post(f"/rooms/{room_id}/agents", json={"agent_ids": agent_ids}))

    def add_member(self, room_id: str, user_id: str) -> Any:
        return _check(self.http.post(f"/chats/{room_id}/members", json={"userId": user_id}))

    def members(self, room_id: str) -> Any:
        return _check(self.http.get(f"/chats/{room_id}/members"))

    def post(
        self, room_id: str, body: str, mention_agent_ids: list[str] | None = None
    ) -> Any:
        return _check(
            self.http.post(
                f"/chats/{room_id}/messages",
                json={
                    "requestId": str(uuid.uuid4()),
                    "body": body,
                    "mentionAgentIds": mention_agent_ids or [],
                },
            )
        )

    def messages(self, room_id: str) -> Any:
        return _check(self.http.get(f"/chats/{room_id}/messages"))


# ── Agent protocol ───────────────────────────────────────────────────────────

CUSTOM_PROFILE = {
    "connection_model": "always_on",
    "message_exchange": True,
    "pre_invocation_mediation": [],
    "post_invocation_mediation": [],
    "event_reporting": [],
}


def register_agent(
    base_url: str,
    registration_key: str,
    name: str,
    description: str,
    *,
    display_name: str | None = None,
    connector_type: str = "airlock-customs",
    overwrite: bool = False,
) -> tuple[str, str]:
    """Register a custom agent. The key's user becomes its owner. Returns
    (agent_id, api_key); the API key is shown once, so store it."""
    resp = httpx.post(
        base_url.rstrip("/") + "/agents",
        headers={"Authorization": f"Bearer {registration_key}"},
        json={
            "name": name,
            "description": description,
            "display_name": display_name,
            "connector_type": connector_type,
            "integration_profile": CUSTOM_PROFILE,
            "overwrite": overwrite,
        },
        timeout=30,
    )
    data = _check(resp)
    return data["id"], data["api_key"]


@dataclass
class Event:
    type: str
    room_id: str | None
    payload: dict[str, Any]
    sequence: int | None
    raw: dict[str, Any]


class AgentClient:
    """One agent's view of Switch. Thread-safe for posting while streaming."""

    def __init__(self, base_url: str, agent_id: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.http = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        self._stream_http = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(30, read=40),
        )
        self.connection_id = str(uuid.uuid4())
        self.cursor: int | None = None
        self.rooms: list[str] = []
        self._stop = threading.Event()
        self._reopen = threading.Event()
        self._response: httpx.Response | None = None

    # -- calls ----------------------------------------------------------------

    def post(self, room_id: str, content: str) -> dict[str, Any]:
        """Post a message. Needs no connection."""
        return _check(
            self.http.post(
                f"/agents/{self.agent_id}/message",
                json={"room_id": room_id, "content": content},
            )
        )

    def ops(self) -> dict[str, Any]:
        return _check(self.http.get(f"/agents/{self.agent_id}/ops"))["operations"]

    def op(self, name: str, connection_id: str | None = None, **args: Any) -> Any:
        headers = {}
        cid = connection_id or self.connection_id
        if cid:
            headers["X-Switch-Connection-Id"] = cid
        return _check(
            self.http.post(f"/agents/{self.agent_id}/ops/{name}", json=args, headers=headers)
        )["result"]

    def history(self, room_id: str) -> Any:
        return _check(self.http.get(f"/agents/{self.agent_id}/rooms/{room_id}/history"))

    # -- stream ---------------------------------------------------------------

    def _open(self, rooms: list[str], scope: str, filter_: str) -> httpx.Response:
        params = {
            "connection_id": self.connection_id,
            "scope": scope,
            "filter": filter_,
            "start_from": "head",
            "client": "airlock",
            "client_version": "0.1.0",
        }
        if rooms:
            params["rooms"] = ",".join(rooms)
        headers = {"Accept": "text/event-stream"}
        if self.cursor is not None:
            headers["Last-Event-ID"] = str(self.cursor)
        req = self._stream_http.build_request(
            "GET", f"/agents/{self.agent_id}/events", params=params, headers=headers
        )
        resp = self._stream_http.send(req, stream=True)
        if resp.status_code >= 400:
            resp.read()
            _check(resp)
        return resp

    def _beat_loop(self) -> None:
        while not self._stop.is_set():
            time.sleep(2)
            if self._response is None:
                continue
            try:
                resp = self.http.post(
                    f"/agents/{self.agent_id}/connection/beat",
                    json={"connection_id": self.connection_id, "cursor": self.cursor or 0},
                )
            except httpx.HTTPError as exc:
                log.warning("heartbeat failed: %s", exc)
                continue
            if resp.status_code in (404, 409):
                log.info("heartbeat %s, reopening stream", resp.status_code)
                self._reopen.set()
                r = self._response
                if r is not None:
                    r.close()

    def events(
        self, rooms: list[str], *, scope: str = "all", filter_: str = "all"
    ) -> Iterator[Event]:
        """Yield domain events forever, reopening the stream as needed."""
        threading.Thread(target=self._beat_loop, daemon=True).start()
        backoff = 0.5
        while not self._stop.is_set():
            try:
                self._response = self._open(rooms, scope, filter_)
                backoff = 0.5
                yield from self._read(self._response)
            except SwitchError:
                raise
            except (httpx.HTTPError, OSError) as exc:
                if self._stop.is_set():
                    return
                log.info("stream dropped (%s), reopening", exc.__class__.__name__)
            finally:
                if self._response is not None:
                    self._response.close()
                self._response = None
            if self._reopen.is_set():
                self._reopen.clear()
                continue
            time.sleep(backoff)
            backoff = min(backoff * 2, 5)

    def _read(self, resp: httpx.Response) -> Iterator[Event]:
        data_lines: list[str] = []
        event_name = None
        for line in resp.iter_lines():
            if self._stop.is_set():
                return
            if line == "":
                if data_lines:
                    ev = self._dispatch(event_name, "\n".join(data_lines))
                    if ev is not None:
                        yield ev
                data_lines, event_name = [], None
                continue
            if line.startswith(":"):
                continue  # keepalive comment
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "data":
                data_lines.append(value)
            elif field == "event":
                event_name = value

    def _dispatch(self, name: str | None, data: str) -> Event | None:
        try:
            frame = json.loads(data)
        except ValueError:
            return None
        kind = frame.get("type") or name
        if kind == "connection_state":
            self.rooms = frame.get("rooms", [])
            if frame.get("cursor") is not None:
                self.cursor = frame["cursor"]
            log.info("connected: rooms=%s cursor=%s", self.rooms, self.cursor)
            return None
        if kind in ("gap", "evicted", "subscription_changed", "room_released"):
            log.info("control frame %s: %s", kind, frame)
            if kind == "subscription_changed":
                self.rooms = frame.get("rooms", self.rooms)
            return None
        seq = frame.get("sequence")
        if seq is not None:
            self.cursor = seq
        return Event(
            type=kind,
            room_id=frame.get("room_id"),
            payload=frame.get("payload") or {},
            sequence=seq,
            raw=frame,
        )

    def stop(self) -> None:
        self._stop.set()
        r = self._response
        if r is not None:
            r.close()


def run_in_thread(
    client: AgentClient,
    rooms: list[str],
    handler: Callable[[Event], None],
    **kwargs: Any,
) -> threading.Thread:
    def loop() -> None:
        for ev in client.events(rooms, **kwargs):
            try:
                handler(ev)
            except Exception:  # a bad message must never kill the agent
                log.exception("handler failed")

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
