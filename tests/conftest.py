"""Shared fixtures & clients for Pi-hole / PiHoleMCP test suite.

Configuration via environment variables (all optional, sensible defaults):

  PIHOLE_HOST      DNS host to query            (default: 100.109.202.81, k3s via Tailscale)
  PIHOLE_WEB       Pi-hole web API base URL     (default: http://$PIHOLE_HOST:8080)
  MCP_URL          PiHoleMCP streamable-http URL (default: http://127.0.0.1:8473/mcp)
  PIHOLE_PASSWORD  web/API password             (fallback: /tmp/opencode/.pihole-pw file)
  MCP_TOKEN        MCP bearer token             (fallback: /tmp/opencode/.mcp-token file)

Secrets are never hardcoded; they come from env or local secret files.
"""
from __future__ import annotations

import json
import os
import time
import uuid

import dns.resolver
import pytest
import requests

# ---------------------------------------------------------------- config ----

PIHOLE_HOST = os.environ.get("PIHOLE_HOST", "100.109.202.81")
PIHOLE_WEB = os.environ.get("PIHOLE_WEB", f"http://{PIHOLE_HOST}:8080")
MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8473/mcp")


def _secret(env_name: str, fallback_path: str) -> str | None:
    val = os.environ.get(env_name)
    if val:
        return val
    try:
        with open(fallback_path, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except FileNotFoundError:
        return None


PIHOLE_PASSWORD = _secret("PIHOLE_PASSWORD", "/tmp/opencode/.pihole-pw")
MCP_TOKEN = _secret("MCP_TOKEN", "/tmp/opencode/.mcp-token")

# Domains that must resolve normally / must be blocked by the shipped lists.
NORMAL_DOMAIN = os.environ.get("TEST_NORMAL_DOMAIN", "heise.de")
BLOCKED_DOMAIN = os.environ.get("TEST_BLOCKED_DOMAIN", "doubleclick.net")


# ---------------------------------------------------------------- clients ---


class PiHoleAPI:
    """Minimal Pi-hole v6 REST API client (X-FTL-SID session auth)."""

    def __init__(self, base_url: str, password: str):
        self.base = base_url.rstrip("/")
        self.password = password
        self.sid: str | None = None

    def login(self) -> str:
        r = requests.post(
            f"{self.base}/api/auth",
            json={"password": self.password},
            timeout=10,
        )
        r.raise_for_status()
        session = r.json()["session"]
        if not session.get("valid"):
            raise RuntimeError("Pi-hole auth returned invalid session")
        self.sid = session["sid"]
        return self.sid

    def _headers(self) -> dict:
        if not self.sid:
            raise RuntimeError("not logged in")
        return {"X-FTL-SID": self.sid}

    def get(self, path: str, **kw) -> dict:
        r = requests.get(f"{self.base}{path}", headers=self._headers(), timeout=15, **kw)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None, expect: tuple = (200, 201)):
        r = requests.post(
            f"{self.base}{path}", headers=self._headers(), json=body, timeout=30
        )
        assert r.status_code in expect, f"POST {path} -> {r.status_code}: {r.text[:200]}"
        return r

    def delete(self, path: str, expect: tuple = (200, 204)):
        r = requests.delete(f"{self.base}{path}", headers=self._headers(), timeout=30)
        assert r.status_code in expect, f"DELETE {path} -> {r.status_code}: {r.text[:200]}"
        return r

    # convenience: exact deny/allow rules -----------------------------------

    def add_deny_exact(self, domain: str, comment: str = "") -> dict:
        r = self.post("/api/domains/deny/exact", {"domain": domain, "comment": comment})
        return r.json()["domains"][0]

    def remove_deny_exact(self, domain: str) -> None:
        self.delete(f"/api/domains/deny/exact/{domain}")


class MCPClient:
    """Minimal MCP streamable-http client (JSON-RPC over POST, SSE responses)."""

    def __init__(self, url: str, bearer_token: str):
        self.url = url
        self.token = bearer_token
        self.sid: str | None = None
        self._id = 0

    def _headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        return h

    def _send(self, method: str, params=None, notify: bool = False):
        self._id += 1
        msg: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            msg["id"] = self._id
        r = requests.post(self.url, headers=self._headers(), json=msg, timeout=30)
        r.raise_for_status()
        new_sid = r.headers.get("mcp-session-id")
        if new_sid:
            self.sid = new_sid
        if notify:
            return None
        return self._parse(r)

    @staticmethod
    def _parse(r: requests.Response) -> dict:
        if "text/event-stream" in r.headers.get("content-type", ""):
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[len("data:") :].strip())
            raise RuntimeError(f"no data event in SSE body: {r.text[:200]}")
        return r.json()

    # high-level ------------------------------------------------------------

    def initialize(self) -> dict:
        result = self._send(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest-pihole-suite", "version": "1.0"},
            },
        )["result"]
        self._send("notifications/initialized", notify=True)
        return result

    def list_tools(self) -> list[dict]:
        return self._send("tools/list")["result"]["tools"]

    def call(self, name: str, arguments: dict | None = None) -> dict | str:
        res = self._send("tools/call", {"name": name, "arguments": arguments or {}})
        if res.get("error"):
            raise RuntimeError(f"MCP error calling {name}: {res['error']}")
        result = res["result"]
        if result.get("isError"):
            text = next(
                (c["text"] for c in result.get("content", []) if c.get("type") == "text"),
                "<no text>",
            )
            raise RuntimeError(f"tool {name} returned isError: {text}")
        if "structuredContent" in result:
            return result["structuredContent"]
        text = next(
            (c["text"] for c in result.get("content", []) if c.get("type") == "text"), ""
        )
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text


# --------------------------------------------------------------- fixtures ---


@pytest.fixture(scope="session")
def resolver() -> dns.resolver.Resolver:
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = [PIHOLE_HOST]
    r.lifetime = 5.0
    r.timeout = 5.0
    return r


def resolve_with_retry(resolver, qname, rdtype="A", expect_nxdomain=False,
                       tries=12, delay=0.5):
    """Poll DNS until the expected state appears (rules apply instantly, but
    negative caching of a previous answer can lag a second)."""
    last_exc = None
    for _ in range(tries):
        try:
            ans = resolver.resolve(qname, rdtype)
            if not expect_nxdomain:
                return ans
            last_exc = RuntimeError(f"{qname} still resolving, NXDOMAIN expected")
        except dns.resolver.NXDOMAIN:
            if expect_nxdomain:
                return None
            last_exc = RuntimeError(f"{qname} NXDOMAIN but should resolve")
        except dns.resolver.NoAnswer:
            if expect_nxdomain:
                return None
            last_exc = RuntimeError(f"{qname} NoAnswer")
        time.sleep(delay)
    raise last_exc or RuntimeError("resolve_with_retry exhausted")


@pytest.fixture(scope="session")
def api() -> PiHoleAPI:
    if not PIHOLE_PASSWORD:
        pytest.skip("PIHOLE_PASSWORD not set (env or /tmp/opencode/.pihole-pw)")
    client = PiHoleAPI(PIHOLE_WEB, PIHOLE_PASSWORD)
    client.login()
    return client


@pytest.fixture(scope="session")
def mcp() -> MCPClient:
    if not MCP_TOKEN:
        pytest.skip("MCP_TOKEN not set (env or /tmp/opencode/.mcp-token)")
    client = MCPClient(MCP_URL, MCP_TOKEN)
    client.initialize()
    return client


@pytest.fixture(scope="session")
def unique_domain() -> str:
    """Unique, guaranteed-nonexistent domain (RFC 6761 .invalid TLD)."""
    return f"pytest-e2e-{uuid.uuid4().hex[:10]}.invalid"
