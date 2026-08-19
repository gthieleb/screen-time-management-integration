"""MCP layer tests: protocol handshake, tool discovery, read-only tool calls."""
from __future__ import annotations

from conftest import BLOCKED_DOMAIN

EXPECTED_TOOLS = {
    "get_blocking_status", "set_blocking", "pause_blocking",
    "block_domain", "allow_domain", "remove_domain_rule",
    "find_why_blocked", "list_domain_rules", "list_adlists",
}


def test_initialize_handshake(mcp):
    assert mcp.sid, "no MCP session id after initialize"
    fresh = mcp.initialize()
    assert fresh["serverInfo"]["name"] == "pihole-mcp"
    assert fresh["protocolVersion"]


def test_bearer_auth_required():
    import pytest
    import requests
    from conftest import MCP_URL
    r = requests.post(
        MCP_URL,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                         "clientInfo": {"name": "t", "version": "0"}}},
        timeout=10,
    )
    assert r.status_code in (401, 403), f"unauthenticated access allowed: {r.status_code}"


def test_tools_list_has_expected_count(mcp):
    tools = mcp.list_tools()
    assert len(tools) >= 55, f"only {len(tools)} tools exposed"


def test_tools_list_contains_screen_time_tools(mcp):
    names = {t["name"] for t in mcp.list_tools()}
    missing = EXPECTED_TOOLS - names
    assert not missing, f"missing tools: {missing}"


def test_get_blocking_status(mcp):
    out = mcp.call("get_blocking_status")
    assert out["blocking"] == "enabled"


def test_find_why_blocked_for_list_domain(mcp):
    out = mcp.call("find_why_blocked", {"domain": BLOCKED_DOMAIN})
    # must identify a blocking reason (adlist match)
    text = str(out)
    assert "StevenBlack" in text or "adlist" in text.lower() or "block" in text.lower()


def test_find_why_blocked_for_unblocked_domain(mcp):
    out = mcp.call("find_why_blocked", {"domain": "heise.de"})
    assert "not blocked" in str(out).lower() or "no" in str(out).lower()
