# Troubleshooting — Pi-hole auf K3s

Häufige Probleme und Fixes. Reihenfolge: Diagnose → Ursache → Fix.

---

## Port 53 belegt durch `systemd-resolved`

**Symptom:** Pi-hole-Pod startet nicht, in den Logs steht `bind: address already in use` für Port 53. Pre-Flight-Check (Schritt 0 im Runbook) zeigt einen Listener auf `:53`.

### Diagnose

```bash
ssh gun@k3s 'sudo ss -tulnp | grep :53'
```

Output wie `systemd-resolve ... 127.0.0.53:53` bestätigt den Konflikt.

### Fix

`systemd-resolved` deaktivieren und `resolv.conf` neu schreiben — betrifft nur den K3s-Host, nicht den Cluster.

```bash
ssh gun@k3s << 'EOF'
sudo systemctl disable --now systemd-resolved
echo "nameserver 192.168.50.1" | sudo tee /etc/resolv.conf
EOF
```

Anschließend Pi-hole-Pod neu starten:

```bash
kubectl rollout restart deploy -n pihole pihole
```

### Hinweis

- K3s selbst nutzt `kube-dns` (CoreDNS) cluster-intern — nicht betroffen.
- Nach dem Fix DNS-Auflösung des Hosts prüfen: `ssh gun@k3s 'nslookup heise.de'`.
- Falls der Host aus anderen Gründen `127.0.0.53` in der `/etc/resolv.conf` braucht, ist ein anderer DNS-Resolver auf dem Host nötig (z.B. `dnsmasq`), bevor Pi-hole Port 53 übernimmt.

---

## DNS-Antwort langsam

**Symptom:** Seitenauflösung merklich träger, Pi-hole-Query-Log zeigt lange Antwortzeiten (> 200 ms) für Upstream-Anfragen.

### Ursache

Die FRITZ!Box als Upstream-Resolver ist relativ träge und cached schwächer als öffentliche Resolver.

### Fix

Upstream auf schnelle öffentliche Resolver umstellen. ConfigMap anpassen:

```yaml
# deployment/pihole/configmap.yaml
data:
  FTLCONF_DNS_UPSTREAMS: "1.1.1.1 8.8.8.8"
```

Anwenden:
```bash
kubectl apply -f deployment/pihole/configmap.yaml
kubectl rollout restart deploy -n pihole pihole
```

Die FRITZ!Box bleibt als DNS2-Fallback auf den Clients erhalten — nur Pi-hole fragt jetzt direkt bei Cloudflare/Google nach.

> **Privacy-Hinweis:** 1.1.1.1 (Cloudflare) speichert keine IP-Logs länger als 24 h. 8.8.8.8 (Google) ist die ressourcenschonende Alternative.

---

## Mobiles Netz bypass

**Symptom:** Auf dem Tablet/Switch greifen die Blocklisten im WLAN, aber im Mobilfunknetz (LTE/5G) oder fremden WLANs nicht.

### Ursache

DNS-Filterung greift nur, wenn der Pi-hole als DNS-Server genutzt wird — das passiert ausschließlich im heimischen WLAN über die FRITZ!Box-DHCP-Konfiguration. Im Mobilfunknetz verwendet das Gerät den Resolver des Mobilfunkproviders.

### Fix

DNS-Filterung ist nur eine Schicht. Ergänzende Maßnahmen auf Geräte-Ebene:

- **Android:** Google Family Link (Bedingungen, App-Limits)
- **iOS / iPadOS:** Apple Screen Time (Downtime, App Limits)
- **Windows:** Microsoft Family Safety
- **Nintendo Switch:** Parental Controls via Nintendo-App

Siehe auch Hermes Skill `smart-home/screen-time-management` für den Gesamtansatz.

---

## Pi-hole-Pod nicht auf der k3s-Node

**Symptom:** Pod läuft auf Worker-Node oder bleibt `Pending`.

### Diagnose

```bash
kubectl get pods -n pihole -o wide
kubectl describe pod -n pihole <pod-name>
```

### Prüfen

- `nodeSelector: kubernetes.io/hostname: k3s` korrekt im Manifest?
- `tolerations` für den control-plane-Taint vorhanden?
  ```yaml
  tolerations:
    - key: node-role.kubernetes.io/control-plane
      effect: NoSchedule
  ```
- PVC `storageClassName: local-path` — `local-path` ist nur auf Nodes verfügbar, die das `local-path-provisioner`-Verzeichnis haben. Auf dem K3s-Server i.d.R. vorhanden, auf Workern nicht zwingend.

### Fix

Falls `tolerations` fehlen oder falsch sind, nachtragen und neu anwenden:
```bash
kubectl apply -k deployment/pihole/
```

---

## ServiceLB vergibt keine External-IP

**Symptom:** `kubectl get svc -n pihole` zeigt `EXTERNAL-IP: <pending>` oder leer.

### Diagnose

```bash
kubectl get svc -n pihole
kubectl describe svc -n pihole
kubectl get pods -n kube-system | grep svclb
```

### Prüfen

- K3s `ServiceLB` (Controller `svclb-<port>-<random>`) läuft? Pod im Namespace `kube-system`.
- Ist auf dem K3s-Host die Node-IP `192.168.50.80` korrekt gebunden?
- Existiert ein anderer LoadBalancer-Controller (z.B. MetalLB), der konfiguriert werden müsste?

### Fallback

Auf `NodePort` umstellen, falls ServiceLB nicht funktioniert — dann aber keine direkte `192.168.50.80:53`-Anbindung, sondern Port-Mapping:

```yaml
# service.yaml — Fallback
type: NodePort
# ports dann mit nodePort: 30053 etc.
```

Anschließend Clients auf `192.168.50.80:30053` umstellen (nicht mehr Port 53 direkt). Für DNS auf Ports > 1024 sprechen Android/iOS normalerweise nicht an — daher `LoadBalancer` vorziehen, wenn möglich.

---

## CoreDNS-Konflikt

**Symptom:** Verdacht, dass CoreDNS (K3s-intern) mit Pi-hole auf Port 53 kollidiert.

### Diagnose

```bash
kubectl get svc -n kube-system -l k8s-app=kube-dns
# CoreDNS läuft als ClusterIP 10.43.0.10 — nur cluster-intern erreichbar.
```

### Einschätzung

- CoreDNS ist als `ClusterIP` (10.43.0.10) definiert und lauscht **nicht** auf dem Host-Port 53.
- Kollision mit Pi-hole sollte daher **nicht** auftreten.
- Pi-hole dagegen bekommt Port 53 auf dem Host-Interface via `type: LoadBalancer` + ServiceLB.

### Falls doch Konflikt

Pi-hole Service auf eine andere External-IP binden — z.B. eine dedizierte secondary IP auf dem K3s-Host (`192.168.50.81`) und im Service `loadBalancerIP: 192.168.50.81` setzen. Vorab die IP auf dem Host anlegen:

```bash
ssh gun@k3s 'sudo ip addr add 192.168.50.81/24 dev eth0'
```

Dann die FRITZ!Box-DNS-Konfiguration auf `192.168.50.81` statt `192.168.50.80` umstellen.

---

## PVC hängt in `Pending`

**Symptom:** PVC `pihole-config` bleibt dauerhaft `Pending`, Pod startet nicht.

### Diagnose

```bash
kubectl get pvc -n pihole
kubectl describe pvc -n pihole pihole-config
```

### Prüfen

- `storageClassName: local-path` existiert?
  ```bash
  kubectl get storageclass
  ```
- `local-path-provisioner` Pod läuft?
  ```bash
  kubectl get pods -n kube-system | grep local-path
  ```
- Auf der k3s-Node existiert das Provisioner-Verzeichnis (meist `/var/lib/rancher/k3s/storage`) und ist beschreibbar?

### Fix

Falls `local-path` fehlt, alternative `storageClassName` verwenden oder das Verzeichnis auf dem Host anlegen. Siehe K3s-Doku zum local-path-provisioner.
---

## PiHoleMCP (MCP-Adapter)

### K8s-Deployment: intermittierender Socket-Verlust (offen)

**Symptom (2026-08-19):** `pihole-mcp` Pod auf dem k3s-Node startet (Uvicorn
loggt "running on 0.0.0.0:8473"), aber der Listening-Socket verschwindet
nach Sekunden wieder — Readiness/Liveness-Probes (tcpSocket) schlagen
intermittierend fehl, kubelet killt den Container (Exit 137). Im Container
selbst: `/proc/net/tcp` zeigt zeitweise keinen Listener, obwohl der Prozess
läuft. Keine Fehler in den Logs.

**Verdacht:** gVisor-RuntimeClass / CNI-Interaktion mit uvicorn auf dem
k3s-Node. Der identische Container läuft lokal (Docker, bare Ubuntu) stabil.

**Workaround (aktiv):** PiHoleMCP läuft lokal im Docker und erreicht Pi-hole
über Tailscale:

```bash
docker run -d --name pihole-mcp -p 127.0.0.1:8473:8473 \
  -e PIHOLE_URL=http://100.109.202.81:8080 \
  -e PIHOLE_APP_PASSWORD='<pihole-web-pw>' \
  -e MCP_BEARER_TOKEN='<32byte-token>' \
  -e MCP_HOST=0.0.0.0 -e MCP_PORT=8473 -e MCP_PATH=/mcp \
  pihole-mcp:local
```

Image lokal bauen (kein offizielles Registry-Image, Stand 2026-08):
`git clone https://github.com/EthanOrr930/PiHoleMCP && docker build -f docker/Dockerfile -t pihole-mcp:local .`

**Aufräumen des K8s-Versuchs:** Manifeste unter `deployment/pihole-mcp/`
sind lauffähig, aber auf Grund des Bugs aktuell nicht angewendet
(`kubectl delete -k deployment/pihole-mcp/` wurde ausgeführt).
Secret `pihole-mcp-secrets` existiert noch im Namespace `mcp`.

### Pi-hole v6 API-Pfadreferenz (FTL v6.4.3)

| Zweck | Korrekt | Veraltet/nicht vorhanden |
|---|---|---|
| Version | `GET /api/info/version` | ~~`/api/version`~~ (404) |
| Stats-Summary | `GET /api/stats/summary` | ~~`/api/stats`~~ (404) |
| Gravity-Zähler | `summary.gravity.domains_being_blocked` | — |
| Blocking-Status | `GET /api/dns/blocking` | — |
| Domain-Regel anlegen | `POST /api/domains/{allow|deny}/{exact|regex}` | ~~`POST /api/domains?type=block`~~ |
| Domain-Regel löschen | `DELETE /api/domains/{type}/{kind}/{domain}` | — |
| Einzelne Domain lesen | `GET /api/domains/{type}/{kind}/{domain}` → `{"domains":[…]}` (Plural-Key!) | — |
| Listen filtern | client-seitig filtern | `?domain=`-Param filtert NICHT serverseitig |

MCP-Tool `remove_domain_rule` nutzt `type: "deny"` (nicht "block") und
erfordert `confirm: true`.
