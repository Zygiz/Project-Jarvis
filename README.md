# 🤖 Jarvis — Personal AI Assistant

> A modular, private, self-hosted personal AI assistant — built from scratch, one phase at a time.

![status](https://img.shields.io/badge/status-v0.1%20shipped-brightgreen)
![phase](https://img.shields.io/badge/phase-5%20tools-blue)
![stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20Postgres%20%7C%20Docker-informational)
![license](https://img.shields.io/badge/license-MIT-green)

Jarvis is a long-term project to build my own personal AI system — the kind that can eventually read email, manage a calendar, track tasks, remember useful facts, and help organize my day. It's built to be **modular, privacy-conscious, Docker-based, and portable** between machines.

This is also a learning project. Every phase teaches me something real about Linux, Docker, backends, databases, and AI.

---

## ✅ v0.1 — what works today

Message the bot from my phone and it:

- **answers questions** using an LLM, with memory of the last 10 messages
- **sets reminders** from natural language — *"remind me tomorrow at 09:00 to call the dentist"* — and actually delivers them
- **ignores everyone else** — only allowlisted Telegram user IDs get a response
- **remembers everything** — every message and reply persisted to PostgreSQL
- **runs 24/7** on a Hostinger VPS, surviving restarts

```
Telegram  →  auth  →  intent parsing  →  ├─ create reminder → Postgres → scheduler → Telegram
                                          └─ LLM reply (with history)
```

---

## 🏗️ Architecture

Same app everywhere — only the host changes. That's the point of the Docker + env-var discipline.

```
DEV (home)                        DEPLOYED (24/7)
Windows                           Hostinger VPS
 └ VirtualBox                      └ Ubuntu
    └ Ubuntu Server VM                └ Docker + Compose
       └ Docker + Compose                ├ api   (FastAPI)
          ├ api   (FastAPI)              ├ bot   (Telegram + scheduler)
          ├ bot   (Telegram)             └ db    (PostgreSQL 16)
          └ db    (PostgreSQL)
```

Migration = `git clone` → create `.env` → `docker compose up -d` → `alembic upgrade head`.

**Already proven:** the whole project was cloned from GitHub onto the VPS and running in minutes.

### Layers

Dependencies point downward only — nothing depends on the transport layer.

```
TRANSPORT       bot.py, main.py          knows Telegram / HTTP
AUTHORIZATION   auth.py                  @require_auth decorator
SERVICE         services.py              knows what Jarvis DOES
                intent_parser, timeparse
PROVIDER        llm/                     external AI, swappable
DATA            models.py, database.py   persistence
```

`services.py` takes plain strings and returns a string — it doesn't import anything from Telegram. That's what makes a future web or voice interface possible without duplicating logic.

### The trust boundary

The LLM **never acts**. It returns JSON, which is validated against a closed set of pydantic schemas before the application decides whether to execute anything.

```
user text → LLM → JSON → pydantic validation → my code executes
                            ^ everything above here is UNTRUSTED
```

Every failure path — bad JSON, unknown action, failed validation, API error — falls back to a plain chat reply. **Fail safe, not open.** This matters more once Jarvis reads email, since an email is untrusted text written by strangers.

---

## 🧰 Tech stack

| Layer            | Choice                                       |
|------------------|----------------------------------------------|
| OS / dev         | Windows + VirtualBox + Ubuntu Server         |
| Deployed on      | Hostinger VPS (Ubuntu, 24/7)                 |
| Language         | Python 3.12                                  |
| Backend          | FastAPI + uvicorn                            |
| Containers       | Docker + Docker Compose                      |
| Database         | PostgreSQL 16 (+ pgvector later)             |
| Config           | pydantic-settings + `.env`                   |
| ORM / migrations | SQLAlchemy 2 + Alembic                       |
| Validation       | pydantic (config **and** LLM output)         |
| Chat             | Telegram (python-telegram-bot, long-polling) |
| Scheduling       | APScheduler                                  |
| Date parsing     | dateparser                                   |
| LLM              | Provider abstraction — Gemini (free tier)    |
| Testing          | pytest + httpx                               |

---

## 📁 Project structure

```
Project-Jarvis/
├── app/
│   ├── main.py            FastAPI app + /health
│   ├── config.py          Settings loaded from .env
│   ├── database.py        engine, session factory, get_session()
│   ├── models.py          Message, Reminder
│   ├── logging_config.py  structured logging + secret-leak fix
│   ├── auth.py            @require_auth allowlist decorator
│   ├── bot.py             Telegram handlers + scheduler startup
│   ├── services.py        handle_message, history, create_reminder
│   ├── intents.py         pydantic schemas for allowed actions
│   ├── intent_parser.py   LLM → JSON → validated Intent
│   ├── timeparse.py       "tomorrow at 09:00" → UTC datetime
│   ├── scheduler.py       delivers due reminders every 60s
│   └── llm/
│       ├── base.py        LLMProvider contract (ABC)
│       ├── gemini.py      Gemini adapter — only google.genai importer
│       └── __init__.py    get_llm() factory
├── alembic/versions/      3 migrations (schema as code)
├── tests/                 pytest
├── docker-compose.yml     api + bot + db
├── Dockerfile             shared image for api and bot
├── .env.example           template (committed)
├── .env                   real secrets (NEVER committed)
├── COMMANDS.md            my command reference + lessons log
└── DOCUMENTATION.md       full technical walkthrough
```

---

## 🖥️ Hardware (dev machine)

| Part   | Spec                     |
|--------|--------------------------|
| Laptop | HP OMEN 16               |
| GPU    | NVIDIA RTX 4080 Laptop   |
| VRAM   | 12 GB                    |

> Strong enough for local models later (7B–14B run fast) — Phase 13, not a blocker.

---

## 📊 Progress

### ✅ Phase 0–4 — Foundation (v0.1 shipped)

<details>
<summary><b>Week 1 — Linux + Docker foundation</b> ✅</summary>

- [x] Create Ubuntu Server VM in VirtualBox
- [x] Linux basics: filesystem, permissions, sudo
- [x] Enable SSH, log in from Windows
- [x] Install Git, SSH keys to GitHub, first push
- [x] Install Docker + Compose, run `hello-world`
- [x] Docker deeper: volumes, networks, port mapping
- [x] First Dockerfile
- [x] Snapshot the VM
</details>

<details>
<summary><b>Week 2 — Backend + database</b> ✅</summary>

- [x] Project skeleton, `.gitignore`, `.env` / `.env.example`
- [x] FastAPI app + `/health` endpoint
- [x] Dockerize the API
- [x] Move into docker-compose
- [x] Add Postgres service, connect from API
- [x] SQLAlchemy models + first Alembic migration
- [x] Structured logging
- [x] First pytest tests
</details>

<details>
<summary><b>Week 3 — Telegram interface</b> ✅</summary>

- [x] BotFather token into `.env`
- [x] Minimal echo bot in compose
- [x] Allowlist my own Telegram user ID (auth)
- [x] Command handling (`/start`, `/help`)
- [x] Persist incoming messages to Postgres
- [x] Clean bot → service → response boundaries
</details>

<details>
<summary><b>Week 4 — LLM + first real tool</b> ✅</summary>

- [x] LLM provider abstraction (Gemini implementation)
- [x] First round-trip: message → LLM → reply
- [x] Prompt + bounded history window
- [x] Structured JSON intent, validated with pydantic
- [x] `create_reminder` tool: validate → store
- [x] APScheduler fires due reminders over Telegram
- [x] Usage/cost + error logging
- [x] 🎉 **Jarvis v0.1 works**
</details>

### Bonus — not in the original plan

- [x] Deployed to Hostinger VPS straight from GitHub — portability proven
- [x] VS Code Remote-SSH workflow across two machines
- [x] Security fix: stopped publishing Postgres to the public internet
- [x] Security fix: revoked a bot token leaked through application logs
- [x] Wrote `COMMANDS.md` — personal command reference and lessons log
- [x] Wrote `DOCUMENTATION.md` — full technical walkthrough

### 🔨 Phase 5 — Tool architecture (next)

- [ ] Tool registry — replace `isinstance` branching with a dispatch table
- [ ] Move `create_reminder` into a `tools/` package
- [ ] `/reminders` — list pending reminders
- [ ] Cancel a reminder
- [ ] Confirmation step for actions (before any destructive tool exists)
- [ ] Tests for `parse_when` and `parse_intent` (fake LLM provider)

### 🩹 Known gaps (deliberate, tracked)

- [ ] **Postgres backups** — highest priority before any personal data arrives
- [ ] Test coverage — 2 tests, both on `/health`; the real logic is untested
- [ ] Pin dependency versions in `requirements.txt`
- [ ] Two LLM calls per message — halves the free-tier budget
- [ ] Non-root container user; remove the dev bind mount from production
- [ ] Linter + formatter (`ruff`), then CI

---

## 🗺️ Long-term roadmap

| Stage | Phases | Status |
|-------|--------|--------|
| **Foundation** — get it running | 0 Hardware · 1 Linux · 2 Backend · 3 Telegram · 4 LLM | ✅ |
| **Core tools & agents** | 5 Tools · 6 Gmail · 7 Calendar · 8 News · 9 Tasks | 🔨 |
| **Intelligence** | 10 Memory (pgvector) · 11 Planner | ⬜ |
| **Documents & local AI** | 12 Documents · 13 Local AI (Ollama) | ⬜ |
| **Deployment & reach** | 14 Remote access · 15 Raspberry Pi | ⬜ |
| **Interfaces & automation** | 16 Voice · 17 Web dashboard · 18 Advanced automation | ⬜ |

---

## 🔒 Security principles

- Never hardcode secrets — everything through `.env`, which is git-ignored
- `.env.example` is committed with blank values as the setup contract
- **Publish a port only if something outside the machine needs it.** Postgres is on the internal Docker network only; the API is bound to loopback; the bot publishes nothing (long-polling is entirely outbound)
- The LLM never gets shell or database access — it emits structured intents the app validates and executes
- Unauthorized users get silence, not "access denied" — a denial confirms the bot is worth attacking
- **Watch your logs for secrets.** A bot token leaked through `httpx` request-URL logging; the loggers are now silenced

---

## 🚀 Running it

```bash
git clone git@github.com:Zygiz/Project-Jarvis.git
cd Project-Jarvis
cp .env.example .env          # fill in real values
docker compose up -d
docker compose exec api alembic upgrade head
curl localhost:8000/health
```

See **`COMMANDS.md`** for the full command reference, and **`DOCUMENTATION.md`** for the architecture walkthrough and design decisions.

---

## 📜 License

MIT