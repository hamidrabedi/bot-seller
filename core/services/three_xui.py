import json
import uuid
from dataclasses import dataclass

import requests


class ThreeXUIError(Exception):
    pass


@dataclass
class ThreeXUICredentials:
    base_url: str
    username: str
    password: str


class ThreeXUIClient:
    def __init__(self, creds: ThreeXUICredentials):
        self.base_url = creds.base_url.rstrip("/")
        self.username = creds.username
        self.password = creds.password
        self.session = requests.Session()

    def _assert_ok(self, response: requests.Response) -> dict:
        response.raise_for_status()
        payload = response.json()
        if payload.get("success") is False:
            raise ThreeXUIError(payload.get("msg") or "3x-ui request failed")
        return payload

    def login(self) -> None:
        response = self.session.post(
            f"{self.base_url}/login",
            data={"username": self.username, "password": self.password},
            timeout=20,
        )
        self._assert_ok(response)

    def _client_payload(
        self,
        *,
        client_id: str,
        email: str,
        expire_time_ms: int,
        total_gb: int,
        enable: bool = True,
    ) -> dict:
        return {
            "id": client_id,
            "email": email,
            "totalGB": total_gb,
            "expiryTime": expire_time_ms,
            "enable": enable,
            "tgId": "",
            "subId": "",
        }

    def create_client(
        self,
        inbound_id: int,
        email: str,
        expire_time_ms: int,
        total_gb: int,
        client_id: str | None = None,
    ) -> dict:
        client_id = client_id or str(uuid.uuid4())
        settings = {
            "clients": [self._client_payload(client_id=client_id, email=email, expire_time_ms=expire_time_ms, total_gb=total_gb)]
        }
        payload = {"id": inbound_id, "settings": json.dumps(settings, ensure_ascii=False)}
        response = self.session.post(f"{self.base_url}/panel/api/inbounds/addClient", json=payload, timeout=20)
        result = self._assert_ok(response)
        result["client_id"] = client_id
        return result

    def update_client(
        self,
        *,
        inbound_id: int,
        client_id: str,
        email: str,
        expire_time_ms: int,
        total_gb: int,
        enable: bool = True,
    ) -> dict:
        settings = {
            "clients": [
                self._client_payload(
                    client_id=client_id,
                    email=email,
                    expire_time_ms=expire_time_ms,
                    total_gb=total_gb,
                    enable=enable,
                )
            ]
        }
        payload = {"id": inbound_id, "settings": json.dumps(settings, ensure_ascii=False)}
        response = self.session.post(
            f"{self.base_url}/panel/api/inbounds/updateClient/{client_id}",
            json=payload,
            timeout=20,
        )
        return self._assert_ok(response)

    def delete_client_by_email(self, inbound_id: int, email: str) -> dict:
        response = self.session.post(
            f"{self.base_url}/panel/api/inbounds/{inbound_id}/delClientByEmail/{email}",
            timeout=20,
        )
        return self._assert_ok(response)

    def reset_client_traffic(self, inbound_id: int, email: str) -> dict:
        response = self.session.post(
            f"{self.base_url}/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}",
            timeout=20,
        )
        return self._assert_ok(response)

    def build_client_link(self, email: str) -> str:
        return f"3xui://client/{email}"
