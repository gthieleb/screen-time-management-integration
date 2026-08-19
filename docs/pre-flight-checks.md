# Pre-Flight-Checks (Wave 1) — DEPLOYED

Ergebnisse der Pre-Flight-Checks vor dem Pi-hole-K3s-Deployment.
Datum: 2026-08-17 (Checks), **2026-08-19 (Deployment erfolgreich durchgeführt)**

## Status: ✅ LIVE

Pi-hole läuft produktiv auf dem qnap-k3s-Cluster:

| Endpoint | Adresse | Zweck |
|---|---|---|
| DNS (LAN) | `192.168.50.80:53` | Für alle Heimnetz-Clients (via FritzBox-DHCP zuweisen) |
| DNS (Tailscale) | `100.109.202.81:53` | DNS-Filterung auch im Tailnet |
| Web-UI | `http://192.168.50.80:8080/admin/` | Pi-hole Admin (LAN) |
| Web-UI (Tailscale) | `http://100.109.202.81:8080/admin/` | Pi-hole Admin (Tailnet) |

## Check-Ergebnisse

| # | Check | Soll | Ist | Status |
|---|-------|------|-----|--------|
| 1 | K3s-Node Ready | Ready | Ready | PASS |
| 2 | g14-Node Ready (Worker, optional) | Ready/NotReady | n/a (nur k3s relevant) | INFO |
| 3 | CPU Cores auf k3s | >= 2 | 2 Cores | PASS |
| 4 | freie CPU auf k3s | > 500m | 816m frei | PASS |
| 5 | RAM auf k3s | >= 8 GB | 15.8 GB | PASS |
| 6 | freier RAM auf k3s | > 8 GB | 12.6 GB frei | PASS |
| 7 | CoreDNS im Cluster | ClusterIP, kein Host-Port 53 | ClusterIP 10.43.0.10 | PASS |
| 8 | ServiceLB vergibt Node-IP | 192.168.50.80 | 192.168.50.80 (Traefik: 192.168.50.30, 192.168.50.80) | PASS |
| 9 | Port 53 auf Host | kein Konflikt | systemd-resolved bindet NUR 127.0.0.53/54 (Loopback); ServiceLB nutzt iptables-DNAT, keine Socket-Kollision | PASS (2026-08-19) |
| 10 | Port 80 auf Node | für Web-UI nutzbar | **BELEGT durch traefik svclb** → Web-UI auf 8080 gelegt | FIXED |

## Wichtige Erkenntnisse vom Deployment-Tag (2026-08-19)

### 1. Netzwerk-Topologie weicht von der Doku ab

- **Default-Gateway und DNS der VM ist `192.168.50.3`**, nicht `192.168.50.1`
- **`192.168.50.1` (laut qnap-k3s-Doku die FritzBox) ist vollständig unerreichbar** (kein Ping, kein DNS) — dort existiert wahrscheinlich kein Gerät
- `192.168.50.3` liefert funktionierendes DNS (getestet: heise.de, registry-1.docker.io)
- **Pi-hole Upstream ist daher `192.168.50.3`** (siehe configmap.yaml)
- ✅ **Bestätigt (2026-08-19):** `192.168.50.3` ist die FRITZ!Box (User-verifiziert, abweichend von der dokumentierten `.1`). DHCP-DNS-Umstellung muss auf `http://192.168.50.3` erfolgen.

### 2. Port 80/443 sind durch traefik svclb belegt

Klipper-lb (ServiceLB) advertised die Node-IP nicht für einen zweiten LB-Service mit gleichem Port. Web-UI des Pi-hole läuft daher auf **LB-Port 8080** (Pod-intern Port 80).

### 3. systemd-resolved ist KEIN Problem für DNS-Port 53

svclb-Pods arbeiten mit hostPort-**DNAT (iptables)**, nicht mit Host-Socket-Binds. Der Stub-Listener auf 127.0.0.53:53 kollidiert nicht.

### 4. containerd-Image-Pull-DNS-Problem (Workaround aktiv)

`containerd` auf dem k3s-Node kann `registry-1.docker.io` nicht auflösen (`EAI_AGAIN`), obwohl beide Nameserver der Host-resolv.conf (`192.168.50.3`, `fd00::7eff:...`) einzeln funktionieren. Ursache unklar (vermutlich Go-Resolver + IPv6-Nameserver-Timeout).

**Workaround (angewendet):** Image lokal gepullt, per `kubectl cp` auf den Node transferiert und via `k3s ctr images import` importiert. Bei künftigen Image-Updates wiederholen oder Node-DNS fixen (siehe troubleshooting.md).

### 5. Pi-hole v6 API-Details

- Listen-Endpoint erwartet `type` als **Query-Parameter** (`POST /api/lists?type=block`), nicht im JSON-Body
- Listen werden beim Hinzufügen automatisch heruntergeladen (gravity)

## Aktive Blocklists

| Liste | Zweck |
|---|---|
| StevenBlack hosts | Ads + Malware (Basisliste) |
| AdGuard DNS Filter | Ads (inkl. Mobile) |

## Befehle zum Wiederholen der Checks

```bash
export KUBECONFIG=~/.kube/qnap-k3s

# Pods + Service Status
kubectl get pods,svc -n pihole -o wide

# DNS-Resolutionstest (via Tailscale)
nslookup heise.de 100.109.202.81
nslookup doubleclick.net 100.109.202.81   # erwartet: 0.0.0.0

# Host-Port 53 (via Debug-Pod, kein SSH nötig)
kubectl run portcheck --rm -i --restart=Never --image=busybox:1.36 -n mcp \
  --overrides='{"spec":{"nodeSelector":{"kubernetes.io/hostname":"k3s"},"hostNetwork":true,"tolerations":[{"key":"node-role.kubernetes.io/control-plane","effect":"NoSchedule"}]}}' \
  -- nslookup heise.de
```

## Nächste Schritte

1. ~~Klären, was `192.168.50.3` ist~~ ✅ FRITZ!Box (bestätigt) — WebUI: http://192.168.50.3
2. DHCP/DNS-Umstellung: siehe [fritzbox-dns-setup.md](fritzbox-dns-setup.md) — **an realer Geräte-IP anpassen**
3. Erst Testgerät (z.B. Nepis Tablet), 24h beobachten, dann Rollout
4. Optional: Wave 4 — PiHoleMCP-Adapter für KI-Steuerung
