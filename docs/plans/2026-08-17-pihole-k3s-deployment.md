# Plan: Pi-hole als DNS-Filter auf qnap-k3s

**Datum**: 2026-08-17
**Status**: Geplant — wartet auf K3s-Server-Online-Status (Wave 1 Pre-Flight)
**Autor**: gthieleb
**Execution Skill**: `subagent-driven-development`

## Kontext

Ursprüngliche Frage war, ob der Laptop **g14** (ASUS ROG Zephyrus G14, K3s-Agent) als DHCP/DNS-Server mit Pi-hole für das Heimnetz konfiguriert werden kann.

Nach Klärung wurde **g14 als Single Point of Failure für das gesamte Heimnetz verworfen** (Laptop, zeitweise offline, K3s-Abhängigkeit). Stattdessen:

- **Pi-hole läuft als K3s-Pod auf dem K3s-Server** (QNAP-VM, 192.168.50.80, "always online")
- **FRITZ!Box bleibt DHCP-Server**
- **FRITZ!Box dient als DNS-Fallback** (DNS2 in DHCP-Option)

## Architektur

```
┌──────────────────────── Heimnetz 192.168.50.0/24 ────────────────────────┐
│                                                                            │
│  FRITZ!Box (192.168.50.1)                                                  │
│  ├─ DHCP-Server: weiterhin aktiv                                          │
│  ├─ DHCP-Option DNS1 = 192.168.50.80 (Pi-hole)                            │
│  ├─ DHCP-Option DNS2 = 192.168.50.1 (FritzBox, Fallback)                  │
│  └─ Selbst Upstream für Pi-hole                                           │
│                                                                            │
│  K3s-Server (192.168.50.80, always online, 2 Cores/299m frei)             │
│  └─ Namespace: pihole                                                      │
│     ├─ Deployment: pihole-core                                             │
│     │   image: pihole/pihole:v6.x                                          │
│     │   nodeSelector: kubernetes.io/hostname = k3s                         │
│     │   resources: req 1m/64Mi, lim 50m/128Mi                              │
│     │   upstream: 192.168.50.1 (FritzBox)                                  │
│     │   persistence: 1Gi local-path PV für /etc/pihole                     │
│     └─ Service: type: LoadBalancer (K3s ServiceLB)                        │
│        Port 53/UDP, 53/TCP, 80/TCP (Web-UI)                               │
│        externalIP: 192.168.50.80                                           │
│                                                                            │
│  Clients (Tabelle, Switch, Handys, Laptops)                                │
│  └─ DNS → 192.168.50.80 → Pi-hole → FritzBox → Provider                    │
│                                                                            │
│  Fallback-Pfad bei Pi-hole-Ausfall                                         │
│  └─ DNS2 = 192.168.50.1 → FritzBox direkt → Provider                       │
│      (keine Domain-Blockierung, aber Internet bleibt)                      │
└────────────────────────────────────────────────────────────────────────────┘
```

## Recherche-Grundlage

Basiert auf:
- `/home/gun/.hermes/skills/smart-home/dns-filtering-home/SKILL.md`
- `/home/gun/.hermes/skills/smart-home/dns-filtering-home/references/pihole-mcp-research.md`
- `/home/gun/.hermes/skills/smart-home/screen-time-management/SKILL.md`
- `/home/gun/development/kubernetes/qnap-k3s/README.md` (Ressourcen, Architektur)
- Pre-Flight-Recherche via Explorer-Subagent (Session 2026-08-17)

### Kritische Befunde aus Recherche

| Punkt | Befund | Konsequenz |
|---|---|---|
| K3s-Server CPU | 2 Cores, ~99% allokiert, 299m frei nach Burstable-QoS | Pi-hole-Request minimal: 1m Request, 50m Limit |
| K3s-Server RAM | Gesamtkapazität nicht dokumentiert | Wave 1 muss `free -h` prüfen |
| Port 53 Konflikt | systemd-resolved-Status nicht dokumentiert | Wave 1 muss `ss -tulnp` prüfen |
| LoadBalancer | K3s ServiceLB (kein MetalLB), vergibt Node-IP | Pi-hole-Service als LoadBalancer → 192.168.50.80:53 |
| FritzBox DNS-Eintrag | Keine Anleitung in Doku | Wave 3 schreibt Schritt-für-Schritt |
| Bestehende Manifeste | Keine vorhanden | Alles neu zu bauen |
| 24/7 | QNAP-VM gilt als "always online" | Pi-hole-Pod auf k3s-Node vertretbar |

## Execution Strategy

**Execution Skill**: `subagent-driven-development`

Wave 1 muss zuerst laufen und kann Wave 2+3 blockieren. Wave 2+3 können nach Wave 1 parallel laufen.

## Communication Checkpoints

### Channels

| Channel | Purpose | ID/URL |
|---|---|---|
| GitHub Repo | Artefakte | `gthieleb/screen-time-management-integration` |
| Direkt-Chat | Status | Session |

### Checkpoint Schedule

Nach jeder Wave: Statusmeldung im Format
```
📡 Wave [N] Complete — [Titel]
Done: [Dateien/Checks]
Verified: [Ergebnisse]
Next: [nächste Wave]
Blockers: [None / Issues]
```

### Delegation Rule

Commits/Pushes über Subagents via `gh` CLI, nicht direkt durch Plan-Agent.

## Output Commit Policy

- Wave 1: nur Lese-Befehle, kein Commit (bis Server online und Ergebnisse vorliegen)
- Wave 2+3: Commits + Push direkt auf `main` (Repo gehört `gthieleb`, Push vorhanden)
- Vor Statusmeldungen: `gh api repos/gthieleb/screen-time-management-integration/commits --jq '.[0].sha'` verify

---

## Wave 1: Pre-Flight-Checks (read-only, blockierend)

**Voraussetzung**: K3s-Server (192.168.50.80) per SSH erreichbar.
Aktuell offline → Wave 1 muss warten, bis er wieder online ist.

**Subagent** führt aus (nur Lese-Befehle, keine Änderungen):

### 1.1 Port 53 auf Host-Interface

```bash
ssh gun@k3s 'sudo ss -tulnp | grep ":53 "'
ssh gun@k3s 'systemctl is-active systemd-resolved'
ssh gun@k3s 'resolvectl status 2>/dev/null | head -20'
```

Falls `systemd-resolved` aktiv und bindet 127.0.0.53:53 → Notiz: "muss vor Pi-hole-Deployment deaktiviert werden" (in Runbook dokumentieren).

### 1.2 Ressourcen

```bash
ssh gun@k3s 'free -h'
ssh gun@k3s 'nproc && cat /proc/meminfo | head -3'
kubectl --kubeconfig ~/.kube/qnap-k3s describe node k3s | grep -A30 "Allocated resources"
```

### 1.3 CoreDNS-Konflikt

```bash
kubectl --kubeconfig ~/.kube/qnap-k3s get svc -n kube-system | grep dns
kubectl --kubeconfig ~/.kube/qnap-k3s get pods -n kube-system -o wide | grep dns
```

Erwartet: CoreDNS lauscht auf Service-IP aus 10.43.0.0/16, nicht auf Host-Port 53.

### 1.4 ServiceLB-Verhalten verifizieren

```bash
kubectl --kubeconfig ~/.kube/qnap-k3s get svc -A | grep LoadBalancer
```

Prüfen: bekommt ein LoadBalancer-Service mit `externalTrafficPolicy: Local` die Node-IP `192.168.50.80`?

### 1.5 Go/No-Go-Entscheidung

- **Go**: Port 53 auf Host frei, RAM hat ≥256 Mi Kopfreserven, ServiceLB vergibt 192.168.50.80 → weiter zu Wave 2
- **No-Go**: systemd-resolved blockiert 53 / RAM zu eng → Plan anpassen (systemd-resolved deaktivieren ODER Pi-hole doch auf g14)

**Deliverable**: `docs/pre-flight-checks.md` im Repo mit Rohdaten + Go/No-Go-Ergebnis. Wird erst commited, wenn Server wieder online und Wave 1 durchlaufen ist.

---

## Wave 2: K8s-Manifeste schreiben

**Abhängig von**: Wave 1 = Go.

**Subagent** schreibt nach `deployment/pihole/`:

### 2.1 `namespace.yaml`

Namespace `pihole`.

### 2.2 `secret.yaml`

`PIHOLE_WEBPASSWORD` (Placeholder, mit `<kubectl create secret>`-Anleitung im Runbook).

### 2.3 `configmap.yaml`

```yaml
FTLCONF_DNS_UPSTREAMS: "192.168.50.1"
FTLCONF_WEBPORTAL_ADDR: ":80"
TZ: "Europe/Berlin"
FTLCONF_LOCAL_IPV4: "192.168.50.80"
```

### 2.4 `deployment.yaml`

- 1 Replica
- `nodeSelector: { kubernetes.io/hostname: k3s }`
- `tolerations: [{ key: node-role.kubernetes.io/control-plane, effect: NoSchedule }]` falls control-plane tainted
- `resources: { requests: { cpu: 1m, memory: 64Mi }, limits: { cpu: 50m, memory: 128Mi } }`
- `securityContext: { capabilities: { add: [NET_BIND_SERVICE] } }` (für Port 53 < 1024 als non-root)
- `volumeMounts`: `/etc/pihole` → PVC
- `readinessProbe`: TCP 53

### 2.5 `service.yaml`

- `type: LoadBalancer`
- `externalTrafficPolicy: Local` (preserves client IP — wichtig für Pi-hole-Client-Erkennung!)
- Ports: 53/UDP, 53/TCP, 80/TCP

### 2.6 `pvc.yaml`

1Gi `local-path` PV (StorageClass existiert laut Doku) für `/etc/pihole`.

### 2.7 `kustomization.yaml`

Bündelt alle oben.

**Deliverable**: Manifeste committed + gepusht auf `main`.

---

## Wave 3: FritzBox-Anleitung + Deployment-Runbook (parallel zu Wave 2)

**Subagent** schreibt:

### 3.1 `docs/fritzbox-dns-setup.md`

- FRITZ!Box-WebUI → Heimnetz → Netzwerkeinstellungen → IP-Adressen → "Lokaler DNS-Server" auf `192.168.50.80` setzen
- Alternativ: pro Gerät unter Heimnetz → Geräteübersicht → "Bearbeiten" → DNS zuweisen (für gezieltes Rollout an Nepis Tablet/Switch zuerst)
- Fallback DNS2 = 192.168.50.1 sicherstellen
- Hinweis: "Vor der Umstellung 24h beobachten, erst nach Stable auf alle Geräte ausrollen"
- Screenshot-Platzhalter (können später ergänzt werden)

### 3.2 `docs/deployment-runbook.md`

```bash
kubectl create namespace pihole  # falls nicht via kustomize
kubectl create secret generic pihole-webpassword -n pihole \
  --from-literal=PIHOLE_WEBPASSWORD=<strong-pw>
kubectl apply -k deployment/pihole/
```

Smoke-Tests:
```bash
nslookup heise.de 192.168.50.80      # Antwort erwartet
nslookup youtube.com 192.168.50.80   # blockt (nach Blocklist-Setup)
```

Pi-hole-Web-UI: `http://192.168.50.80/admin/`

- Blocklists aktivieren (StevenBlack, etc.)
- Client-Gruppen anlegen (`children`, `adults`)

### 3.3 `docs/troubleshooting.md`

- **Port 53 belegt durch `systemd-resolved`**:
  ```bash
  sudo systemctl disable --now systemd-resolved
  rm /etc/resolv.conf
  echo "nameserver 192.168.50.1" > /etc/resolv.conf
  ```
- **DNS langsam**: upstream direkt auf 1.1.1.1 umstellen, FritzBox als DNS2 im DHCP
- **Mobiles Netz bypass**: Family Link / OS-Level zusätzlich, siehe `screen-time-management` Skill
- **Pi-hole-Pod nicht auf k3s-Node**: tolerations prüfen
- **ServiceLB vergibt keine externe IP**: `kubectl get svc -n pihole`, ggf. `loadBalancerClass`-Feld prüfen

**Deliverable**: Runbook + FritzBox-Anleitung + Troubleshooting committed + gepusht.

---

## Wave 4 (optional, später): PiHoleMCP-Adapter

Nicht Teil dieses Plans. Nur als Folge-Schritt dokumentiert im Deployment-Runbook:

> Nächster Schritt: PiHoleMCP im Namespace `mcp` deployen (analog `dns-filtering-home/references/pihole-mcp-research.md`), Tailscale-Ingress für `pihole-mcp.tail6a9722.ts.net/mcp`.

---

## Offene Punkte / Risiken

| Risiko | Mitigation |
|---|---|
| K3s-Server offline → Wave 1 blockiert | Warten bis online. Alternative: g14 als temporärer Pi-hole-Host via Bare-Metal (suboptimal, nur wenn Server langfristig offline) |
| `systemd-resolved` blockiert Port 53 | In Runbook dokumentiert, Deaktivierung Schritt-für-Schritt |
| RAM-Budget des Servers unbekannt | Wave 1 prüft `free -h`, wenn <256Mi frei → Pi-hole-Resources reduzieren oder andere Lösung |
| FritzBox-DHCP-DNS-Option vielleicht nur pro-Client, nicht global | Runbook deckt beide Wege ab (global + pro-Gerät) |
| `externalTrafficPolicy: Local` könnte Traffic verwerfen, wenn Pi-hole-Pod nicht auf dem Node läuft, den Traffic empfängt | `nodeSelector: k3s` + ServiceLB vergibt Node-IP des k3s-Servers, daher Konsistenz |

---

## Nächste Schritte

1. **Warten**, bis der K3s-Server wieder online ist (192.168.50.80 per SSH/Tailscale erreichbar)
2. **Wave 1 auslösen** — "Server ist online, Wave 1 starten"
3. Nach Wave 1 Go: **Wave 2+3 parallel** auslösen
4. Nach Wave 2+3: **Manuelles Deployment** nach Runbook, **FritzBox-DNS-Umstellung** nach Anleitung
5. Beobachtungsphase 24h, dann Rollout auf alle Geräte

---

## Referenzen

- Hermes Skill `smart-home/dns-filtering-home`: `/home/gun/.hermes/skills/smart-home/dns-filtering-home/SKILL.md`
- Pi-hole MCP Recherche: `/home/gun/.hermes/skills/smart-home/dns-filtering-home/references/pihole-mcp-research.md`
- Screen-Time Management Skill: `/home/gun/.hermes/skills/smart-home/screen-time-management/SKILL.md`
- QNAP K3s Cluster Doku: `/home/gun/development/kubernetes/qnap-k3s/README.md`
- FritzBox MCP Server: `https://github.com/gthieleb/fritzbox-mcp-server`