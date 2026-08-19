# Pi-hole / PiHoleMCP Test Suite

Testet die Funktion des Familien-DNS-Filters auf drei Ebenen:

| Datei | Ebene | Tool |
|---|---|---|
| `test_dns.py` | DNS-Protokoll (dig/host-Äquivalent) | dnspython |
| `test_api.py` | Pi-hole v6 REST API | requests (direktes HTTP) |
| `test_mcp.py` | MCP-Server (PiHoleMCP, 73 Tools) | JSON-RPC über Streamable HTTP |
| `test_e2e_block.py` | End-to-End Screen-Time-Szenario | MCP-Tool → DNS → Cleanup |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r tests/requirements-test.txt
```

Secrets (nie committen) — liegen lokal unter:
- `/tmp/opencode/.pihole-pw` (Pi-hole Web-Passwort)
- `/tmp/opencode/.mcp-token` (MCP Bearer Token)

oder als Env-Variablen `PIHOLE_PASSWORD` / `MCP_TOKEN`.

Der MCP-Server (PiHoleMCP) läuft aktuell lokal im Docker (siehe
`docs/troubleshooting.md` — K8s-Deployment hat einen gVisor-Bug):

```bash
docker run -d --name pihole-mcp -p 127.0.0.1:8473:8473 \
  -e PIHOLE_URL=http://100.109.202.81:8080 \
  -e PIHOLE_APP_PASSWORD=<pw> \
  -e MCP_BEARER_TOKEN=<token> \
  -e MCP_HOST=0.0.0.0 \
  pihole-mcp:local
```

## Ausführen

```bash
# von der Verwaltungsmaschine (Tailnet, Standard: PIHOLE_HOST=100.109.202.81)
.venv/bin/python -m pytest tests/ -v

# aus dem Heimnetz gegen die LAN-IP
PIHOLE_HOST=192.168.50.80 PIHOLE_WEB=http://192.168.50.80:8080 \
  .venv/bin/python -m pytest tests/ -v
```

## Konfiguration (Env)

| Var | Default | Bedeutung |
|---|---|---|
| `PIHOLE_HOST` | `100.109.202.81` | DNS-Host (k3s via Tailscale) |
| `PIHOLE_WEB` | `http://$PIHOLE_HOST:8080` | Pi-hole Web-API |
| `MCP_URL` | `http://127.0.0.1:8473/mcp` | MCP-Endpoint |
| `PIHOLE_PASSWORD` | Datei-Fallback | Web-Passwort |
| `MCP_TOKEN` | Datei-Fallback | Bearer Token |

## Cleanup-Garantie

`test_e2e_block.py` nutzt einzigartige `.invalid`-Domains (RFC 6761) und
verifiziert am Ende (`test_08`), dass keine Test-Regeln zurückbleiben.
