# 🤖 Jarvis — Personal AI Assistant

> A modular, private, self-hosted personal AI assistant — built from scratch, one phase at a time.

![status](https://img.shields.io/badge/status-in%20development-yellow)
![phase](https://img.shields.io/badge/phase-0%20foundation-blue)
![stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20Postgres%20%7C%20Docker-informational)
![license](https://img.shields.io/badge/license-MIT-green)

Jarvis is a long-term project to build my own personal AI system — the kind that can eventually read email, manage a calendar, track tasks, remember useful facts, and help organize my day. It's built to be **modular, privacy-conscious, Docker-based, and portable** between machines (dev VM today, a dedicated 24/7 server later).

This is also a learning project. Every phase teaches me something real about Linux, Docker, backends, databases, and AI.

---

## 🎯 The MVP (v0.1)

The first working version is deliberately tiny:

```
Telegram  →  FastAPI  →  LLM  →  reply
                 ↕
             PostgreSQL   (message log + reminders)
```

**Done = I can message my own bot from my phone, get an intelligent reply, and set a reminder that actually fires.**

---

## 🏗️ Architecture

Same app everywhere — only the host changes. That's the whole point of the Docker + env-var discipline.

```
NOW (development)                 LATER (24/7 production)
Windows                           VPS / Raspberry Pi
 └ VirtualBox                      └ Ubuntu
    └ Ubuntu Server VM                └ Docker + Compose
       └ Docker + Compose                ├ jarvis-api (FastAPI)
          ├ jarvis-api (FastAPI)         ├ postgres
          ├ postgres                     └ scheduler / bot
          └ scheduler / bot
```

Migration = `git clone` → drop in a production `.env` → `docker compose up -d` → restore the Postgres dump.

---

## 🧰 Tech stack

| Layer        | Choice                                   |
|--------------|------------------------------------------|
| OS / dev     | Windows + VirtualBox + Ubuntu Server     |
| Language     | Python 3.12+                             |
| Backend      | FastAPI                                  |
| Containers   | Docker + Docker Compose                  |
| Database     | PostgreSQL (+ pgvector later)            |
| Config       | pydantic-settings + `.env`               |
| ORM / migrations | SQLAlchemy + Alembic                 |
| Chat         | Telegram (python-telegram-bot)           |
| Scheduling   | APScheduler                              |
| LLM          | Provider abstraction (Anthropic first)   |

---

## 🖥️ Hardware (dev machine)

| Part | Spec |
|------|------|
| Laptop | HP OMEN 16 |
| GPU | NVIDIA RTX 4080 Laptop |
| VRAM | 12 GB |

> Strong enough for local AI later (7B–14B models run fast) — but local AI is a Phase 13 concern, not a blocker.

---

## ✅ Progress tracker

Legend: ✅ done · 🔨 in progress · ⬜ not started

### Setup
- [x] Project spec written
- [x] Hardware audit (RTX 4080 Laptop, 12 GB VRAM)
- [x] GitHub repo created (private for now)
- [x] README committed

### Week 1 — Linux + Docker foundation
- [x] Create Ubuntu Server VM in VirtualBox
- [x] Linux basics: filesystem, permissions, sudo
- [x] Enable SSH, log in from Windows
- [x] Install Git, SSH keys to GitHub, first push
- [x] Install Docker + Compose, run `hello-world`
- [x] Docker deeper: volumes, networks, port mapping
- [x] First Dockerfile for a trivial Python script
- [x] Snapshot the VM

### Week 2 — Backend + database
- [x] Project skeleton, `.gitignore`, `.env` / `.env.example`
- [x] FastAPI app + `/health` endpoint
- [ ] Move into docker-compose
- [ ] Add Postgres service, connect from API
- [ ] SQLAlchemy models + first Alembic migration
- [ ] Structured logging
- [ ] First pytest tests

### Week 3 — Telegram interface
- [ ] BotFather token into `.env`
- [ ] Minimal echo bot in compose
- [ ] Allowlist my own Telegram user ID (auth)
- [ ] Command handling (`/start`, `/help`)
- [ ] Persist incoming messages to Postgres
- [ ] Clean bot → service → response boundaries

### Week 4 — LLM + first real tool
- [ ] LLM provider abstraction (Anthropic impl)
- [ ] First round-trip: message → LLM → reply
- [ ] Prompt + bounded history window
- [ ] Structured JSON intent, validated with pydantic
- [ ] `create_reminder` tool: validate → store
- [ ] APScheduler fires due reminders over Telegram
- [ ] Usage/cost + error logging
- [ ] 🎉 **Jarvis v0.1 works** — snapshot + tag a release

---

## 🗺️ Long-term roadmap

| Stage | Phases | Status |
|-------|--------|--------|
| **Foundation** — get it running | 0 Hardware · 1 Linux · 2 Backend · 3 Telegram · 4 LLM | 🔨 |
| **Core tools & agents** | 5 Tools · 6 Gmail · 7 Calendar · 8 News · 9 Tasks | ⬜ |
| **Intelligence** | 10 Memory (pgvector) · 11 Planner | ⬜ |
| **Documents & local AI** | 12 Documents · 13 Local AI (Ollama) | ⬜ |
| **Deployment & reach** | 14 Remote access · 15 Raspberry Pi / VPS 24/7 | ⬜ |
| **Interfaces & automation** | 16 Voice · 17 Web dashboard · 18 Advanced automation | ⬜ |

---

## 🔒 Security principles

- Never hardcode API keys — everything through `.env`
- `.env` is git-ignored; `.env.example` is committed with blank values
- The LLM never gets shell or arbitrary DB access — it emits structured intents that the app validates and executes
- Destructive actions (send/delete email, modify calendar) require confirmation
- Least privilege on all OAuth scopes

---

## 📜 License

MIT
