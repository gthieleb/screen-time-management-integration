# Screen-Time Management Integration — Design

> Ziel: Ein generischer, technologieoffener **Credit-/Guthaben-Service** für **Zeit** und andere Units (z. B. Spielminuten, App-Nutzung, Aufgaben-Belohnungen), kombiniert mit einem Adapter-Ökosystem für gängige Eltern-/Kinderschutz- und Netzwerkinfrastrukturen.

---

## 1. Zielsetzung

Kinder erhalten **gutschriftenbasierte Freigaben** für digitale Aktivitäten. Ein Guthaben kann in verschiedene "Währungen" gebucht werden:

| Unit | Beispiel |
|------|----------|
| `screen_time` | 30 Minuten Tablet/PC/Internet |
| `game_time` | 60 Minuten Konsolen-/PC-Spiele |
| `app_usage` | Nutzung einer bestimmten App |
| `task_reward` | Erledigte Pflichtaufgabe |

Kernanforderungen:

- **Generisch**: Nicht nur Screen-Time, sondern beliebige Credit-Units.
- **Bonus-fähig**: Gutschriften durch gutes Verhalten, Extra-Aufgaben, Erfolge.
- **Pausierbar/Unterbrechbar**: Ein eingelöster Slot sollte pausiert werden können (Restguthaben erhalten oder verfallen — konfigurierbar).
- **Integrationen**: FRITZ!Box, Pi-hole, AdGuard Home, Google Family Link, Apple Screen Time, Microsoft Family Safety, Linux-/Router-Lösungen.
- **Auth/OIDC**: Eltern- und Kinder-Accounts mit OAuth2/OIDC.
- **Microservice-Architektur**: Lose gekoppelte Services, unabhängig deploybar.

---

## 2. Architekturübersicht

```mermaid
flowchart TB
    subgraph "Clients"
        Parent["Eltern-App / Web"]
        Child["Kinder-App / Web"]
        Assistant["AI Assistant / MCP"]
    end

    subgraph "API Gateway"
        GW["API Gateway (Tailscale / Ingress)"]
        Auth["Auth-Service (Keycloak / OIDC)"]
    end

    subgraph "Core Services"
        CS["Credit-Service"]
        WS["Wallet-Service"]
        RS["Reward-Service"]
        NS["Notification-Service"]
        TS["Task-Service"]
    end

    subgraph "Integration Adapters"
        FB["FritzBox-Adapter"]
        PH["Pi-hole-Adapter"]
        AG["AdGuard-Home-Adapter"]
        FL["Family-Link-Adapter"]
        AP["Apple-Screen-Time-Adapter"]
        MS["Microsoft-Family-Adapter"]
        LX["Linux/Router-Adapter"]
    end

    subgraph "Backends"
        PG[(PostgreSQL)]
        RD[(Redis)]
        MB[(Message Broker / NATS)]
    end

    Parent --> GW
    Child --> GW
    Assistant --> GW

    GW --> Auth
    GW --> CS
    GW --> WS
    GW --> RS
    GW --> TS

    CS --> WS
    CS --> RS
    RS --> NS
    TS --> CS

    CS --> FB
    CS --> PH
    CS --> AG
    CS --> FL
    CS --> AP
    CS --> MS
    CS --> LX

    CS --> PG
    WS --> PG
    RS --> PG
    TS --> PG
    NS --> RD
    CS --> RD
    CS --> MB
```

### Kurzbeschreibung der Services

| Service | Verantwortung |
|---------|---------------|
| **Auth-Service** | OIDC-basierte Eltern-/Kinder-Accounts, Gerätezuordnung, OAuth2-Token |
| **Wallet-Service** | Salden, Währungen, Transaktionshistorie, Guthaben-Reservierungen |
| **Credit-Service** | Kerngeschäftslogik: Guthaben vergeben, einlösen, pausieren, verfallen lassen |
| **Reward-Service** | Belohnungskatalog, Bonus-Regeln, Erledigungsnachweise |
| **Task-Service** | Aufgabenlisten, die in Guthaben umgewandelt werden können |
| **Notification-Service** | WhatsApp, E-Mail, Push — Code-Versand, Erinnerungen, Limits |
| **Integration Adapters** | Adapter für konkrete Systeme (FritzBox, Pi-hole etc.) |

---

## 3. Architekturvergleich

| Kriterium | Monolith | Microservices | Event-Driven | Serverless |
|-----------|----------|---------------|--------------|------------|
| **Komplexität** | niedrig | mittel | hoch | mittel |
| **Deploybarkeit** | einfach | unabhängig | unabhängig | vollständig verwaltet |
| **Skalierbarkeit** | vertikal | horizontal | horizontal | automatisch |
| **Wartbarkeit** | bei kleinem Team gut | bei wachsendem Team gut | hoch (Observability) | gut, Vendor-Lock-in |
| **Echtzeitfähigkeit** | gut | gut | sehr gut | gut |
| **Tailscale-tauglich** | ja | ja | ja | eingeschränkt |
| **Empfehlung** | Prototyp/MVP | **Zielarchitektur** | Erweiterung für Echtzeit | Nicht primär |

**Empfehlung:** Microservices auf K3s/QNAP mit event-gesteuerten Ergänzungen (z. B. Kafka/NATS für Limit-Alarme, Einlösungen).

---

## 4. Auth-Flow (OAuth2/OIDC)

```mermaid
sequenceDiagram
    autonumber
    participant P as Eltern-App
    participant GW as API Gateway
    participant KC as Keycloak (OIDC)
    participant CS as Credit-Service
    participant WS as Wallet-Service

    P->>GW: Login-Request
    GW->>KC: Redirect /authorize
    KC-->>P: Login-Seite
    P->>KC: Credentials
    KC-->>GW: ID-Token + Access-Token
    GW->>CS: Request mit Bearer-Token
    CS->>KC: Token introspection
    KC-->>CS: scopes + roles (parent/child)
    CS->>WS: Wallet-Operation (nur für berechtigte User)
    WS-->>CS: Ergebnis
    CS-->>P: Antwort
```

---

## 5. Integrationsdiagramme

### 5.1 FRITZ!Box Zeitkontrolle

```mermaid
sequenceDiagram
    autonumber
    participant P as Eltern-App
    participant CS as Credit-Service
    participant FB as FritzBox-Adapter
    participant FBX as FRITZ!Box (TR-064)
    participant WA as WhatsApp-MCP
    participant C as Kind

    P->>CS: "Nepi bekommt 30 Minuten"
    CS->>FB: redeem(time=30min, device=Nepi)
    FB->>FBX: MarkTicket()
    FBX-->>FB: TicketID / Code
    FB-->>CS: Code + Ablaufzeit
    CS->>WA: sendMessage(code)
    WA-->>C: "Dein Code: 123456"
    C->>FBX: Code eingeben
    FBX-->>FB: Zeit freigeschaltet
    FB->>CS: session active
    CS->>WS: reserve & deduct on expiry
```

### 5.2 Pi-hole

```mermaid
sequenceDiagram
    autonumber
    participant CS as Credit-Service
    participant PH as Pi-hole-Adapter
    participant PI as Pi-hole v6 API

    CS->>PH: block_device(Nepi, until=20:00)
    PH->>PI: POST /clients (group_id=children)
    PI-->>PH: OK
    PH->>PI: POST /groups/children/blocklist (youtube.com)
    PI-->>PH: OK
    CS->>PH: unblock_device(Nepi)
    PH->>PI: DELETE /clients/<id>
    PI-->>PH: OK
```

### 5.3 AdGuard Home

```mermaid
sequenceDiagram
    autonumber
    participant CS as Credit-Service
    participant AG as AdGuard-Home-Adapter
    participant AD as AdGuard Home

    CS->>AG: set_child_profile(device=Nepi, schedule=strict)
    AG->>AD: POST /control/clients/update
    AD-->>AG: OK
    AG->>AD: POST /control/filtering/set_rules
    AD-->>AG: OK
    CS->>AG: pause_profile(device=Nepi)
    AG->>AD: POST /control/clients/update (disabled=true)
    AD-->>AG: OK
```

### 5.4 Google Family Link

```mermaid
sequenceDiagram
    autonumber
    participant CS as Credit-Service
    participant FL as Family-Link-Adapter
    participant G as Google Family Link

    Note over FL,G: Keine offizielle API existent. Adapter ist theoretisch oder basiert auf Web-Scraping/Benachrichtigungs-API.

    CS->>FL: query_screen_time(child=Nepi)
    FL->>G: (nicht-offizieller oder manueller Pfad)
    G-->>FL: heutige Nutzung
    FL-->>CS: Nutzungsdaten
    CS->>FL: notify_limit_reached(child=Nepi)
    FL->>G: (nur manuell möglich)
```

### 5.5 Apple Screen Time / Family Sharing

```mermaid
sequenceDiagram
    autonumber
    participant CS as Credit-Service
    participant AP as Apple-Adapter
    participant A as Apple Screen Time

    Note over AP,A: Apple bietet keine öffentliche API für Screen Time. Adapter ist nur als Konzept.

    CS->>AP: request_downtime_extension(child=Nepi, duration=15min)
    AP->>A: (nicht verfügbar)
    A-->>AP: Error: no API
    AP-->>CS: Integration nur lokal/MDM-basiert möglich
```

### 5.6 Microsoft Family Safety

```mermaid
sequenceDiagram
    autonumber
    participant CS as Credit-Service
    participant MS as Microsoft-Adapter
    participant M as Microsoft Family Safety

    Note over MS,M: Keine dokumentierte öffentliche API für Zeitlimits. Eventuell Graph API eingeschränkt nutzbar.

    CS->>MS: query_device_usage(child=Nepi)
    MS->>M: (experimentell / unvollständig)
    M-->>MS: begrenzte Daten
    MS-->>CS: Daten oder Fehler
```

### 5.7 Linux / Router-basierte Lösungen

```mermaid
sequenceDiagram
    autonumber
    participant CS as Credit-Service
    participant LX as Linux/Router-Adapter
    participant R as OpenWrt / Router / PC

    CS->>LX: block_mac(mac=aa:bb:cc, until=20:00)
    LX->>R: SSH / UCI / nftables
    R-->>LX: OK
    LX->>CS: session active
    CS->>LX: unblock_mac(mac=aa:bb:cc)
    LX->>R: remove rule
    R-->>LX: OK
```

**Mögliche Linux-/Router-Lösungen:**

- **OpenWrt** mit `parental-controls`, `timecontrol`, `nftables`
- **Qustodio** (kommerziell, Cross-Platform)
- **KDE Plasma Mobile Parental Controls**
- **GNOME Settings** → Kindersicherung (eingeschränkt)
- **Mandriva Parental Controls** (historisch)
- **Custom Linux PC-Agent** (zeitgesteuertes Lockscreen/Logout)

---

## 6. Credit-/Token-Fluss mit Bonus

```mermaid
sequenceDiagram
    autonumber
    participant P as Eltern / Task-Service
    participant CS as Credit-Service
    participant WS as Wallet-Service
    participant RS as Reward-Service
    participant C as Kind

    P->>CS: grant_credit(child=Nepi, unit=screen_time, amount=30, reason=Hausaufgaben)
    CS->>WS: credit_wallet(wallet=Nepi, +30)
    WS-->>CS: balance=45
    CS->>RS: check_bonus_eligibility(child=Nepi)
    RS-->>CS: bonus=+5 (Streak 3 Tage)
    CS->>WS: credit_wallet(wallet=Nepi, +5)
    WS-->>CS: balance=50
    CS-->>P: Guthaben 50 Min

    C->>CS: redeem(unit=screen_time, amount=30)
    CS->>WS: reserve(wallet=Nepi, 30)
    WS-->>CS: reserved
    CS->>CS: activate session (FritzBox/Pi-hole etc.)
    CS-->>C: Code / Freigabe

    Note over CS,WS: Unterbrechung optional
    C->>CS: pause()
    CS->>WS: release remaining (15)
    WS-->>CS: balance=35
    CS-->>C: "Restguthaben zurückgebucht"

    C->>CS: resume()
    CS->>WS: reserve(wallet=Nepi, 15)
    WS-->>CS: reserved
    CS-->>C: Fortsetzen
```

---

## 7. Datenmodell

```mermaid
erDiagram
    ACCOUNT ||--o{ USER : contains
    USER ||--o{ WALLET : has
    USER ||--o{ DEVICE : owns
    USER ||--o{ SESSION : starts
    WALLET ||--o{ TRANSACTION : records
    CREDIT_PACKAGE ||--o{ TRANSACTION : creates
    REWARD ||--o{ REDEMPTION : redeemed
    USER ||--o{ REDEMPTION : redeems
    INTEGRATION ||--o{ USER : configures

    ACCOUNT {
        uuid id
        string name
        string subscription_tier
        timezone timezone
    }

    USER {
        uuid id
        uuid account_id
        string display_name
        enum role "parent | child | admin"
        string email
        string oidc_sub
        date birthdate
    }

    WALLET {
        uuid id
        uuid user_id
        json balances
        datetime updated_at
    }

    TRANSACTION {
        uuid id
        uuid wallet_id
        enum type "credit | debit | reserve | release | expire"
        string unit
        int amount
        string reason
        uuid reference_id
        datetime created_at
    }

    CREDIT_PACKAGE {
        uuid id
        string name
        string unit
        int base_amount
        int bonus_amount
        json rules
    }

    REWARD {
        uuid id
        string name
        string unit
        int cost
        json metadata
        bool active
    }

    REDEMPTION {
        uuid id
        uuid user_id
        uuid reward_id
        int amount_used
        datetime redeemed_at
        enum status "pending | fulfilled | cancelled"
    }

    SESSION {
        uuid id
        uuid user_id
        string integration
        string external_session_id
        enum status "active | paused | completed | expired"
        int duration_minutes
        int used_minutes
        datetime started_at
        datetime expires_at
    }

    DEVICE {
        uuid id
        uuid user_id
        string name
        string mac_address
        string ip_address
        string platform
    }

    INTEGRATION {
        uuid id
        uuid account_id
        string provider
        json credentials
        string endpoint
        bool active
    }
```

---

## 8. API-Entwurf

### 8.1 Wallets

```
GET    /api/v1/wallets/{user_id}
POST   /api/v1/wallets/{user_id}/credit
POST   /api/v1/wallets/{user_id}/debit
POST   /api/v1/wallets/{user_id}/reserve
POST   /api/v1/wallets/{user_id}/release
GET    /api/v1/wallets/{user_id}/transactions
```

### 8.2 Credits

```
POST   /api/v1/credits/grant
POST   /api/v1/credits/redeem
POST   /api/v1/credits/pause
POST   /api/v1/credits/resume
POST   /api/v1/credits/cancel
GET    /api/v1/credits/sessions
```

### 8.3 Rewards

```
GET    /api/v1/rewards
POST   /api/v1/rewards
POST   /api/v1/rewards/{id}/redeem
GET    /api/v1/rewards/redemptions
```

### 8.4 Tasks

```
GET    /api/v1/tasks
POST   /api/v1/tasks
POST   /api/v1/tasks/{id}/complete
```

### 8.5 Integrations

```
GET    /api/v1/integrations
POST   /api/v1/integrations
PUT    /api/v1/integrations/{id}
DELETE /api/v1/integrations/{id}
POST   /api/v1/integrations/{id}/test
```

---

## 9. Technologie-Vorschläge

| Schicht | Vorschlag | Begründung |
|---------|-----------|------------|
| API-Backend | Python / FastAPI | Moderne, schnelle, OpenAPI |
| Datenbank | PostgreSQL | ACID, JSON-Felder, gut skalierbar |
| Cache | Redis | Sessions, Reservierungen, Rate-Limits |
| Task-Queue | Celery + Redis | Hintergrundjobs, Ablaufzeit, Erinnerungen |
| Message Broker | NATS | Leichtgewichtig, K3s-freundlich |
| Auth | Keycloak | OIDC, OAuth2, Social Logins |
| Netzwerk | Tailscale | Sicherer Zugriff ohne öffentliche Ports |
| Orchestration | K3s (qnap-k3s) | Leichtgewichtiges Kubernetes |
| Monitoring | Prometheus + Grafana | Observability für Microservices |

---

## 10. Referenzen & Inspiration

| Projekt | URL | Relevanz |
|---------|-----|----------|
| BlessedCow/TokenEconomy | <https://github.com/BlessedCow/TokenEconomy> | Einfache Münz-/Belohnungslogik |
| thim81/kids-screen-time | <https://github.com/thim81/kids-screen-time> | Kinder-UI, Quota, Rewards |
| EthanOrr930/PiHoleMCP | <https://github.com/EthanOrr930/PiHoleMCP> | Pi-hole v6 MCP-Adapter |
| fcannizzaro/mcp-adguard-home | <https://github.com/fcannizzaro/mcp-adguard-home> | AdGuard Home MCP-Adapter |
| vahidkaargar/laravel-wallet | <https://github.com/vahidkaargar/laravel-wallet> | Generisches Wallet-Pattern |
| mohamedkaram400/rewards-system | <https://github.com/mohamedkaram400/rewards-system> | Credit-Packages + Redemption |

---

## 11. Offene Punkte & Risiken

| Thema | Status | Risiko |
|-------|--------|--------|
| Google Family Link API | ❌ Nicht öffentlich | Keine direkte Steuerung möglich |
| Apple Screen Time API | ❌ Nicht öffentlich | Nur MDM oder lokale Workarounds |
| Microsoft Family Safety API | ⚠️ Experimentell | Wenig dokumentiert, instabil |
| FRITZ!Box TR-064 | ✅ Verfügbar | Stabile Basis für Zeitkontrolle |
| Pi-hole v6 API | ✅ Verfügbar | Sehr flexibel für DNS-Blocking |
| AdGuard Home API | ✅ Verfügbar | Gute REST-API |
| Linux PC-Steuerung | ⚠️ Eigenbau | Plattformabhängig |
| Unterbrechung/Restzeit | ⚠️ Konzept | Muss je nach Integration definiert werden |

---

## 12. Nächste Schritte

1. **MVP-Scope festlegen**: Zeitguthaben + FRITZ!Box + WhatsApp-Benachrichtigung.
2. **Credit-Service prototypen**: Wallet, Transaction, Session.
3. **FritzBox-Adapter finalisieren**: `MarkTicket`, `GetTicketIDStatus`, automatische Session-Erfassung.
4. **Pi-hole-Adapter bauen**: Block/Unblock per Gerät.
5. **Eltern-UI**: Guthaben vergeben, Rewards konfigurieren, Sessions überwachen.
6. **Kinder-UI**: Guthaben einsehen, Code einlösen, Aufgaben erledigen.
7. **Integrationen mit fehlenden APIs** nur als Dokumentation/Platzhalter behandeln, bis sich APIs ändern.

---

*Letzte Aktualisierung: 2026-07-16*
