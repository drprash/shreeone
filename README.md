# ShreeOne — Family Finance

A private, shared money system for families - with control over what you share and what you don’t.

---

## The Problem

Managing money as a family is genuinely hard:

- **No shared visibility.** One person pays the electricity bill, another handles groceries, and nobody has the full picture at the end of the month.
- **Fragmented tools.** Spreadsheets break, bank apps show only one person's accounts, and commercial apps like Mint or YNAB cost money and store sensitive data on their servers.
- **Privacy within the household.** Not every expense should be visible to every family member — personal medical costs or individual savings goals deserve discretion.
- **Recurring payments are invisible until they hit.** Subscriptions, EMIs, rent, and SIPs silently drain accounts and are only noticed when something bounces.
- **Offline gaps.** Mobile data drops; a finance app that stops working without internet is not reliable enough for daily use.

## The Solution

ShreeOne is a self-hosted web app that runs entirely on your own server or home machine. Your financial data never leaves your network.

| Need | How ShreeOne solves it |
|---|---|
| Shared family view | All members see a unified dashboard across all accounts |
| Role-based privacy | Three privacy levels — Private, Shared (couple), Family — per transaction |
| Recurring payments | Auto-processed daily; bills appear in the ledger without manual entry |
| Offline use | Full PWA with a service worker; transactions queue locally and sync when connectivity returns |
| Install on Android | "Add to Home Screen" from Chrome — launches like a native app |
| Self-hosted | Docker Compose brings up the entire stack in one command |

---

## Features

- **Multi-account tracking** — bank accounts, credit cards, wallets, savings across multiple countries and currencies
- **Income & expense categorisation** with custom categories per family
- **Financial Goals** — savings targets, big purchases, debt payoff, net-worth milestones; manual contributions with history or auto-tracked via a linked account
- **Budget settings** — monthly limits per category with alerts
- **Recurring payments** — subscriptions, EMIs, SIPs auto-posted at midnight daily
- **Net Worth timeline** — daily snapshots charted on the Dashboard
- **Role-based access** — Admin, Member, Viewer with granular permission overrides
- **Transaction privacy** — Private / Shared / Family visibility per entry
- **Passkey / WebAuthn** — passwordless login alongside JWT
- **Offline-first PWA** — IndexedDB queue, auto-sync on reconnect; installable on Android
- **Backup & Restore** — HMAC-signed JSON export/import covering all data including goals and AI preferences

### AI features (optional)

Supports a local Ollama model (no data leaves your server) or cloud providers (OpenAI, Anthropic, Google). The app works fully without any AI configured.

| Feature | Description |
|---|---|
| **Auto-categorisation** | Suggests a category for each transaction as you type |
| **Voice / Smart Entry** | Speak or type a sentence ("spent £45 at Tesco") — fields auto-fill |
| **Receipt OCR** | Photograph a receipt; amount, merchant, date extracted automatically |
| **Bank Statement Import** | Upload a PDF or image statement; expense rows parsed into transactions |
| **Monthly Narrative** | 3–4 sentence plain-English summary of the family's monthly finances |
| **Weekly Digest** | 2-sentence spending summary shown on the Dashboard |

AI is controlled via a **master on/off switch** in **Settings → AI Features**. Turning it on triggers a live connection test against all API keys configured in `.env`; the best responding provider is selected automatically. Individual features (categorisation, narratives, receipt OCR, etc.) can be toggled separately once AI is enabled.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, React Query v5, Zustand |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Auth | JWT (30 min access / 7 day refresh) + WebAuthn passkeys |
| Database | PostgreSQL 16 |
| Scheduler | APScheduler (recurring payments at 00:00, token pruning at 01:00, exchange rates at 06:00) |
| AI | Ollama + Gemma 4 E4B (local, `--profile ollama`) or OpenAI / Anthropic / Google (cloud); master toggle + per-provider test in Settings |
| PDF/OCR | pdfplumber (text PDFs), pymupdf (scanned image fallback) |
| Infrastructure | Docker + Docker Compose, Nginx |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+ and [Docker Compose](https://docs.docker.com/compose/) v2+
- `curl` (used by the installer health check; pre-installed on most Linux distros)

> The installer can set Docker up for you automatically on Linux (Ubuntu/Debian, Fedora/RHEL, Arch).

## Deployment

### Option A — Automated installer (recommended)

```bash
git clone https://github.com/drprash/shreeone.git shreeone && cd shreeone
bash install.sh
```

The script will:

1. **Check / install Docker and Docker Compose** — detects your Linux distro and installs via the appropriate package manager if needed.
2. **Configure environment variables interactively** — for each sensitive value you can choose between entering it manually or letting the script auto-generate a cryptographically secure value:
   - `DB_PASSWORD` — auto-generate or enter your own
   - `SECRET_KEY` — auto-generate (64 hex chars) or enter your own (min 32 chars)
   - `FRONTEND_URL` — choose localhost, your detected LAN IP, or a custom URL
3. **Optionally configure AI** — choose local Ollama (pulls Gemma 4 E4B, ~4.7 GB, no data leaves your server) or a cloud provider (OpenAI / Anthropic / Google — API key only, no extra service). The app works fully without AI.
4. **Build and start all services** — runs `docker compose up -d --build` (or `--profile ollama` for local AI).
5. **Health check** — polls the API until it responds, then prints the app URL.

Open the printed URL and register the first admin account. The first user to register automatically becomes the family Admin and creates the family — no separate setup step is needed.

### Option B — Manual setup (core, no AI)

```bash
git clone https://github.com/drprash/shreeone.git shreeone && cd shreeone
cp .env.example .env          # edit DB_PASSWORD, SECRET_KEY, and FRONTEND_URL
docker compose up -d --build
```

The `.env.example` file contains:

```dotenv
DB_HOST=db
DB_PORT=5432
DB_NAME=shreeone
DB_USER=postgres
DB_PASSWORD=change_me_to_a_strong_db_password

SECRET_KEY=change_me_to_a_long_random_secret

FRONTEND_URL=http://localhost:5173
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

Open `http://localhost:5173` and register the first admin account. The first user to register automatically becomes the family Admin and creates the family.

**Verify:** `curl http://localhost:5173/api/health`

### Option C — Manual setup with AI

**Local AI (Ollama)** — pulls `gemma4:e4b` automatically on first start (~4.7 GB, no data leaves your server):

```bash
docker compose --profile ollama up -d --build
```

**Cloud AI (OpenAI / Anthropic / Google)** — no extra service; add the relevant keys to `.env` and start normally:

```dotenv
# .env — uncomment and fill ONE provider block
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o-mini        # optional override

# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-...

# LLM_PROVIDER=google
# GOOGLE_AI_API_KEY=...
```

```bash
docker compose up -d --build
```

### Accessing from other devices on your LAN

The installer detects your LAN IP and offers it as a one-step option. For manual setup:

1. Find your server IP: `ip addr show | grep "inet " | grep -v 127.0.0.1`
2. Set `FRONTEND_URL=http://<your-ip>:5173` in `.env`
3. `docker compose up -d` to reload CORS config
4. Browse to `http://<your-ip>:5173` from any device on the network

### Installing as a PWA on Android

Open Chrome → navigate to the app URL → three-dot menu → **Add to Home screen**.

> Chrome requires HTTPS for service workers on public domains. LAN `http://` addresses work fine for home deployments.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_PASSWORD` | Yes | — | PostgreSQL password |
| `SECRET_KEY` | Yes | — | JWT signing key (min 32 chars) |
| `FRONTEND_URL` | Yes | `http://localhost:5173` | Base URL of the app; used for CORS and WebAuthn origin/RP-ID validation. Comma-separate multiple origins for CORS (e.g. `http://localhost:5173,http://192.168.1.10:5173`). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | JWT refresh token lifetime |
| `LLM_BASE_URL` | No | `http://llm:11434` | Ollama server URL (used with `--profile ollama`) |
| `LLM_MODEL` | No | `gemma4:e4b` | Ollama model name |
| `LLM_TIMEOUT_SECONDS` | No | `90` | LLM inference timeout in seconds |
| `LLM_PROVIDER` | No | `local` | AI provider: `local` (Ollama), `openai`, `anthropic`, `google` |
| `OPENAI_API_KEY` | No | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model name |
| `ANTHROPIC_API_KEY` | No | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-haiku-4-5-20251001` | Anthropic model name |
| `GOOGLE_AI_API_KEY` | No | — | Google AI API key |
| `GOOGLE_AI_MODEL` | No | `gemini-2.0-flash` | Google AI model name |

## Upgrading

```bash
git pull
docker compose up -d --build
```

The app applies any new columns automatically on startup — no manual migration step is needed.

## Database Backup

```bash
# Manual backup — run from the project root; retains last 7 days in ./backups/
bash scripts/backup.sh

# Restore a backup
gunzip -c backups/shreeone_backup_YYYYMMDD_HHMMSS.sql.gz \
  | docker compose exec -T db psql -U postgres shreeone

# Cron example — daily at 2 am (edit the path to match your installation)
0 2 * * * bash /path/to/shreeone/scripts/backup.sh >> /path/to/shreeone/backups/backup.log 2>&1
```

## Project Structure

```
shreeone/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app, scheduler, CORS, DB migrations
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── schemas.py          # Pydantic request/response schemas
│   │   ├── crud.py
│   │   ├── auth.py             # JWT + WebAuthn
│   │   ├── financial_logic.py  # Balance calculations, exchange rate engine
│   │   ├── config.py
│   │   └── routers/
│   │       ├── ai.py           # AI endpoints (categorise, receipt, voice, statement, narrative)
│   │       ├── goals.py        # Financial goals + contributions
│   │       ├── accounts.py
│   │       ├── transactions.py
│   │       ├── categories.py
│   │       ├── dashboard.py
│   │       ├── settings.py
│   │       ├── backup.py       # Backup & restore
│   │       └── ...
│   ├── services/
│   │   └── ai_service.py       # Ollama HTTP client (categorise, OCR, voice, narrative)
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Transactions.jsx
│   │   │   ├── Accounts.jsx
│   │   │   ├── Goals.jsx
│   │   │   ├── Settings.jsx
│   │   │   └── ...
│   │   ├── components/
│   │   │   ├── Dashboard/NetWorthChart.jsx
│   │   │   ├── Transactions/QuickAdd.jsx   # voice / smart-entry
│   │   │   └── Settings/
│   │   ├── services/
│   │   │   ├── aiAPI.js        # AI feature calls
│   │   │   ├── goalsAPI.js
│   │   │   └── ...
│   │   ├── store/              # Zustand (auth, theme)
│   │   └── lib/               # IndexedDB offline queue
│   ├── public/
│   ├── nginx.conf
│   ├── package.json
│   └── Dockerfile
├── scripts/
│   └── backup.sh
├── docker-compose.yml          # Full stack; use --profile ollama to add local AI
├── install.sh                  # automated one-step installer
└── .env.example
```

## License

MIT — see [LICENSE](LICENSE).
