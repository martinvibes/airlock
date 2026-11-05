"""Just enough of Mattermost's REST API to put each company's engineer in
their own channels. Used by scripts/setup.py --mattermost; Airlock itself
never talks to Mattermost, only to Switch."""

from __future__ import annotations

from typing import Any

import httpx


class Mattermost:
    def __init__(self, url: str):
        self.http = httpx.Client(base_url=url.rstrip("/") + "/api/v4", timeout=20)
        self.token: str | None = None

    def _ok(self, resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            raise RuntimeError(f"Mattermost {resp.request.method} {resp.request.url.path}: "
                               f"{resp.status_code} {resp.text[:300]}")
        return resp.json() if resp.content else None

    def login(self, username: str, password: str) -> dict[str, Any]:
        resp = self.http.post("/users/login", json={"login_id": username, "password": password})
        me = self._ok(resp)
        self.token = resp.headers["token"]
        self.http.headers["Authorization"] = f"Bearer {self.token}"
        return me

    def logout(self) -> None:
        self.http.post("/users/logout")

    def create_user(self, username: str, email: str, password: str, first: str, last: str) -> dict[str, Any]:
        return self._ok(self.http.post("/users", json={
            "username": username, "email": email, "password": password,
            "first_name": first, "last_name": last}))

    def user_by_username(self, username: str) -> dict[str, Any]:
        return self._ok(self.http.get(f"/users/username/{username}"))

    def team(self, name: str) -> dict[str, Any]:
        return self._ok(self.http.get(f"/teams/name/{name}"))

    def add_to_team(self, team_id: str, user_id: str) -> None:
        self._ok(self.http.post(f"/teams/{team_id}/members", json={"team_id": team_id, "user_id": user_id}))

    def channel(self, team_id: str, name: str) -> dict[str, Any]:
        return self._ok(self.http.get(f"/teams/{team_id}/channels/name/{name}"))

    def members(self, channel_id: str) -> list[dict[str, Any]]:
        return self._ok(self.http.get(f"/channels/{channel_id}/members", params={"per_page": 200}))

    def add_to_channel(self, channel_id: str, user_id: str) -> None:
        self._ok(self.http.post(f"/channels/{channel_id}/members", json={"user_id": user_id}))

    def remove_from_channel(self, channel_id: str, user_id: str) -> None:
        self._ok(self.http.delete(f"/channels/{channel_id}/members/{user_id}"))

    def set_avatar(self, user_id: str, png: bytes) -> None:
        self._ok(self.http.post(f"/users/{user_id}/image", files={"image": ("avatar.png", png, "image/png")}))

    def post(self, channel_id: str, message: str) -> dict[str, Any]:
        return self._ok(self.http.post("/posts", json={"channel_id": channel_id, "message": message}))
