# Project-Jarvis — Complete Technical Documentation & Learning Analysis

> **Provenance and honesty statement.** This document was **not** produced by scanning the
> repository. It is reconstructed from the guided build sessions during which every file in
> this project was written, plus the terminal output, error messages, and database queries
> captured during those sessions.
>
> **What that means for you:**
> - The architecture, design decisions, bug history, and learning progression are
>   first-hand and reliable — they were observed as they happened.
> - Exact line numbers, current file contents, and any edits made outside those sessions
>   are **not** verified. Check them before relying on specifics.
> - Sections that depend on data I could not access (full Git history, CI config, GitHub
>   metadata) are explicitly marked as **NOT INSPECTED**.
>
> See the **Coverage Report** at the end for a precise accounting.

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [Technology Stack](#2-technology-stack)
3. [Repository Inventory](#3-repository-inventory)
4. [File-by-File Documentation](#4-file-by-file-documentation)
5. [Architecture Deep Dive](#5-architecture-deep-dive)
6. [Database Architecture](#6-database-architecture)
7. [Dependency Analysis](#7-dependency-analysis)
8. [Configuration Analysis](#8-configuration-analysis)
9. [Git & GitHub Analysis](#9-git--github-analysis)
10. [Testing Documentation](#10-testing-documentation)
11. [Security Analysis](#11-security-analysis)
12. [Performance Analysis](#12-performance-analysis)
13. [Code Quality Analysis](#13-code-quality-analysis)
14. [Important Design Decisions](#14-important-design-decisions)
15. [Important Code Patterns](#15-important-code-patterns)
16. [Confirmed Bugs & Issues](#16-confirmed-bugs--issues)
17. [What I Would Improve](#17-what-i-would-improve)
18. [Difficult Concepts, Explained Three Ways](#18-difficult-concepts-explained-three-ways)
19. [How Everything Connects](#19-how-everything-connects)
20. [Learning Map](#20-learning-map)
21. [Learning Timeline](#21-learning-timeline)
22. [Skills Demonstrated](#22-skills-demonstrated)
23. [Complexity Analysis](#23-complexity-analysis)
24. [Glossary](#24-glossary)
25. [Interview Questions & Answers](#25-interview-questions--answers)
26. [Final Reflection](#26-final-reflection)
27. [Coverage Report](#27-coverage-report)

---

# 1. Project Summary

## What it is

Project-Jarvis is a **self-hosted personal AI assistant**. You send it a message on
Telegram; it either answers conversationally using a large language model, or recognises
that you asked for an action and performs it. Currently the one implemented action is
setting a reminder, which is stored durably and delivered back to you over Telegram at
the right time.

## The problem it solves

Two problems, one practical and one educational.

**Practical:** commercial assistants are cloud-hosted, closed, and own your data. This
one runs on hardware you control, stores data in your own database, and can eventually be
pointed at a locally-hosted model so no personal data leaves the machine at all.

**Educational — and this is the honest primary driver:** the project is a vehicle for
learning Linux, Docker, backend development, databases, migrations, and LLM integration by
building something real and useful rather than following tutorials. Almost every
architectural decision was made and explained deliberately rather than copied.

## Who it is for

A single user (the author). Authentication is a hardcoded allowlist of one Telegram user
ID. It is not multi-tenant, and nothing about the current design assumes it should be —
though the data model would tolerate a handful of users without change.

## Main functionality (as built)

- Receives Telegram messages via long-polling
- Rejects anyone not on an explicit allowlist, silently
- Persists every message and every reply to PostgreSQL
- Maintains a bounded conversation history window so replies have context
- Classifies each message into a **validated structured intent** before acting
- Answers conversationally via the Gemini API
- Creates reminders from natural language ("remind me tomorrow at 09:00 to call the
  dentist"), storing them in UTC
- Delivers due reminders via a polling scheduler that survives restarts
- Logs token usage per call, labelled by call type
- Exposes a `/health` HTTP endpoint

## Apparent goals

From the original project brief and the way it was built: **modular, maintainable,
privacy-conscious, self-hosted, inexpensive, Docker-based, portable between machines,
secure, easy to extend.** The stated ultimate goal is deployment to a Raspberry Pi as a
24/7 server — currently it runs 24/7 on a Hostinger VPS instead, which was an unplanned
but reasonable substitution made mid-project.

## Overall architecture in one line

A **modular monolith** in Python, split into transport / authorization / service /
provider layers, running as three Docker containers (API, bot+scheduler, database) managed
by Docker Compose.

---

# 2. Technology Stack

## Languages

### Python 3.12

**Why:** the ecosystem for LLM SDKs, web frameworks, and ORMs is strongest here, and it
was already the author's most familiar language. **Where:** all application code under
`app/`. **Concept to understand:** Python's type hints (`str | None`, `list[dict]`) are
used throughout but are *not enforced at runtime* — they document intent and enable editor
tooling. Pydantic is what actually enforces types where it matters.

**What I learned:** decorators, abstract base classes, context managers, `async`/`await`,
the difference between Python-side and database-side defaults, and how a package (`app/`,
`app/llm/`) is defined by `__init__.py`.

### SQL (PostgreSQL dialect)

**Why:** unavoidable when inspecting or debugging a database, even with an ORM.
**Where:** interactive `psql` sessions, and generated by SQLAlchemy at runtime.
**What I learned:** `SELECT`/`WHERE`/`ORDER BY`/`LIMIT`, `COUNT`, `GROUP BY`, `DELETE`,
`ALTER TABLE`, what an index is for, and psql meta-commands (`\dt`, `\d`, `\q`).

### YAML

**Where:** `docker-compose.yml`. **Concept:** whitespace-significant, no tabs. A
mis-indented key is silently ignored rather than rejected — which caused a real bug (see
§16).

### Bash

**Where:** every command in the project. **What I learned:** `cd`/`ls`/`grep`/`sed`/
`cat`/heredocs, redirection, and that `python -c "..."` must be one line or the shell tries
to execute line two.

## Frameworks & major libraries

### FastAPI + uvicorn

**Why:** FastAPI for a modern, typed, minimal web framework; uvicorn because FastAPI is an
ASGI app and needs an ASGI server to run it. **Where:** `app/main.py`; the `api` service's
`CMD`. **Role:** currently only serves `/health`. This is deliberate — the HTTP surface
exists as a foundation for a future web dashboard, not because it's needed now.

**Concept:** FastAPI is the *router and framework*; uvicorn is the *process that listens on
a port*. Two distinct jobs that beginners routinely conflate.

**What I learned:** decorator-based routing (`@app.get("/health")`), that returning a dict
produces JSON automatically, and that a "health endpoint" is a universal convention for
"is this service alive?"

### python-telegram-bot

**Why:** handles the Telegram API, the long-polling loop, and message routing. **Where:**
`app/bot.py`. **Role:** the entire transport layer.

**Key concept — long-polling vs webhooks.** Long-polling means the bot repeatedly asks
Telegram "anything new?" All connections are **outbound**. Webhooks would require Telegram
to reach *in*, needing a public HTTPS endpoint and an open port. Choosing long-polling
means the `bot` container needs **no published ports at all**, and the same code works
behind home NAT or on a public VPS unchanged. This is one of the better decisions in the
project.

**What I learned:** async handlers, handler registration, filters
(`filters.TEXT & ~filters.COMMAND`), the `post_init` lifecycle hook, and that the library
transparently retries transient network failures.

### SQLAlchemy 2.x (ORM)

**Why:** the application reads and writes the database constantly; hand-written SQL strings
would be repetitive and injection-prone. **Where:** `app/database.py`, `app/models.py`, and
every query.

**Concept:** models are Python classes that describe tables. `session.add(Message(...))`
becomes an `INSERT`. You never write SQL for application logic — but you still write it by
hand for *inspection*, and knowing both is valuable.

**What I learned:** engine vs session, the `select()` construct, `.scalars().all()`, and —
painfully — that ORM objects are **bound to their session** and go stale when it closes
(see `DetachedInstanceError`, §16 and §18).

### Alembic

**Why:** the database schema changes over time and must rebuild identically on any machine.
**Where:** `alembic/`, `alembic.ini`, three migration files.

**Concept:** Alembic diffs your models against the real database and writes the SQL needed
to close the gap into a versioned file. That file is committed to Git, so the schema is
code. The `alembic_version` table records which migrations have run, per database.

**What I learned:** the full chain (models → autogenerate → read → upgrade), that
autogenerate produces a *first draft* not a finished product (its own generated comment
literally says `please adjust!`), that migrations run in a transaction and roll back
cleanly on failure, and the `default=` vs `server_default=` distinction that caused a real
failed migration.

### google-genai (Gemini SDK)

**Why:** free tier with no credit card, which removed cost as a barrier to learning.
**Where:** `app/llm/gemini.py` **only** — deliberately quarantined.

**Concept:** the newer SDK; the older `google-generativeai` package is deprecated, so most
tutorials found online are wrong.

**What I learned:** building multi-turn `contents` lists, system instructions via
`GenerateContentConfig`, reading `usage_metadata` for token counts, and how to tell a
server-side failure (5xx) from a client-side one (4xx).

### pydantic + pydantic-settings

**Why:** two distinct jobs. `pydantic-settings` loads and validates configuration from
`.env`. `pydantic` validates **LLM output**, which is the security-critical use.
**Where:** `app/config.py`, `app/intents.py`.

**Concept:** pydantic turns untrusted text into either a verified object or a clear error.
That's what makes it suitable as a trust boundary.

**What I learned:** typed settings classes, that `.env` overrides class defaults, that a
field with no default makes the app refuse to start when misconfigured (fail fast), the
`extra="ignore"` option, and — most importantly — `Literal[...]` as a way to constrain a
field to known values, which is what prevents the LLM inventing actions.

### APScheduler

**Why:** something must wake up periodically to deliver due reminders. **Where:**
`app/scheduler.py`, started from `app/bot.py`.

**Concept:** `AsyncIOScheduler` attaches to a running asyncio event loop. It cannot be
started from synchronous code before the loop exists — this caused a real crash loop.

**What I learned:** interval jobs, the `post_init` workaround, and the broader rule that
*anything asyncio-based must be created inside a running event loop*.

### dateparser

**Why:** converting "tomorrow at 09:00" to a timestamp is genuinely hard, and the LLM is
unreliable at date arithmetic. **Where:** `app/timeparse.py`.

**Concept:** it accepts a timezone and a preference for future dates, which is exactly what
reminder parsing needs.

**What I learned:** that libraries have undocumented gaps — this one fails on the word
"next" — and that **probing a library with four quick tests beats assuming it works**.

### pytest + httpx

**Where:** `tests/`. **Concept:** FastAPI's `TestClient` calls the app in-process, so tests
need no running server, no port, and no network.

**What I learned:** test discovery by naming convention, `assert`, and that a test suite
you've never watched *fail* is one you don't yet trust.

### psycopg2-binary

**Role:** the low-level driver SQLAlchemy uses to actually speak to PostgreSQL. Invisible
in the code; required in `requirements.txt`.

## Database

### PostgreSQL 16

**Why:** robust, free, the standard choice, and supports `pgvector` later for semantic
memory — avoiding a separate vector database. **Where:** the `db` container.

**What I learned:** what a real database engine running *empty* looks like (it exists but
has no tables), auto-increment via sequences, `NOT NULL` enforcement at the database level,
indexes, and that the password is only read when the data directory is first initialised.

## Infrastructure

### Docker + Docker Compose

**Why:** the whole portability thesis. **Where:** `Dockerfile`, `.dockerignore`,
`docker-compose.yml`.

**Concept:** images are recipes, containers are running instances, volumes make data
survive container destruction, and the private network lets containers find each other by
service name.

**What I learned:** layer caching (copy `requirements.txt` before the app code so
dependency installs are cached), host-port vs container-port mapping, that `0.0.0.0` means
*every* interface including the public one, that `down -v` destroys your data, and that
two services can share one image with different `command` overrides.

### Ubuntu Server (VirtualBox VM + Hostinger VPS)

**Concept:** the same Docker Compose stack runs on both. The VM was for learning; the VPS
became the real 24/7 host.

**What I learned:** SSH, key-based auth, `systemctl enable --now`, port forwarding through
NAT, file permissions, and that a public IP gets scanned by strangers continuously.

### Git + GitHub

**What I learned:** the add/commit/push loop, SSH keys per machine, `.gitignore` as a
security mechanism, that per-machine `git config` identity matters (early commits are
attributed to `root`), that history rewriting is possible but rarely worth the risk, and
commit-message discipline.

---

# 3. Repository Inventory

Reconstructed from the build sessions. **Not verified against the current repository.**

```
Project-Jarvis/
├── app/
│   ├── __init__.py              package marker
│   ├── main.py                  FastAPI app, /health endpoint
│   ├── config.py                Settings (pydantic-settings) — all config
│   ├── database.py              engine, SessionLocal, Base, get_session()
│   ├── models.py                Message, Reminder (SQLAlchemy models)
│   ├── logging_config.py        setup_logging(), noisy-logger silencing
│   ├── auth.py                  @require_auth decorator (allowlist)
│   ├── bot.py                   Telegram handlers + scheduler startup
│   ├── services.py              handle_message, save_message,
│   │                            get_recent_history, create_reminder, SYSTEM_PROMPT
│   ├── intents.py               ChatIntent, CreateReminderIntent, Intent union
│   ├── intent_parser.py         INTENT_PROMPT, _strip_fences, parse_intent
│   ├── timeparse.py             parse_when() — natural language → UTC
│   ├── scheduler.py             send_due_reminders()
│   └── llm/
│       ├── __init__.py          get_llm() factory
│       ├── base.py              LLMProvider ABC — the contract
│       └── gemini.py            GeminiProvider — the only google.genai importer
├── alembic/
│   ├── env.py                   modified: reads DATABASE_URL from settings
│   ├── script.py.mako           migration template (untouched)
│   ├── README                   Alembic's own (untouched)
│   └── versions/
│       ├── 15acf0cb38e8_create_messages_table.py
│       ├── c4d84d2142c5_add_role_and_indexes_to_messages.py
│       └── c7e1b69254bd_add_reminders_table.py
├── tests/
│   ├── __init__.py
│   └── test_health.py           two tests against /health
├── docker-practice/             LEARNING ARTIFACT — see note below
│   ├── hello.py
│   └── Dockerfile
├── alembic.ini                  Alembic config (URL overridden in env.py)
├── docker-compose.yml           three services: api, bot, db
├── Dockerfile                   builds the shared api/bot image
├── .dockerignore                excludes .venv, .env, .git, __pycache__
├── .gitignore                   excludes .env, .venv, __pycache__, keys
├── .env                         NEVER COMMITTED — real secrets
├── .env.example                 committed template, secrets blank
├── requirements.txt             unpinned dependency list
├── README.md                    project overview + progress tracker
└── COMMANDS.md                  personal command reference / lessons log
```

**On `docker-practice/`:** this was a deliberate Week-1 exercise (a one-line Python script
in a container) that taught the Dockerfile mechanics before they mattered. It is dead code
now. Keeping it is defensible as a learning record; deleting it is defensible as hygiene.
It should at minimum be mentioned in the README so a reader knows it isn't part of the app.

**Files notably absent** (each is a genuine gap, discussed in §17):
- No `.github/` directory — no CI, no Actions, no PR/issue templates
- No linting or formatting config (no `ruff`, `black`, `flake8`, `pre-commit`)
- No `pyproject.toml` — dependencies are managed by a bare `requirements.txt`
- No `LICENSE` file, despite the README claiming MIT
- No database backup script

---

# 4. File-by-File Documentation

## `app/config.py`

**Purpose.** The single source of truth for every configuration value in the application.

**Contents.** A `Settings` class inheriting `pydantic_settings.BaseSettings`, a
`model_config` declaring `.env` as the source with `extra="ignore"`, a computed
`allowed_user_ids` property, and a module-level `settings = Settings()` instance.

**How it works.** Instantiating `Settings()` triggers machinery inherited from
`BaseSettings`: it looks for the reserved attribute name `model_config`, reads its
instruction to load `.env`, and populates each declared field. **Precedence: `.env` values
override the class defaults.** Fields declared without a default (`database_url`,
`telegram_bot_token`) make instantiation *fail* if absent — the application refuses to
start rather than running misconfigured.

**The `allowed_user_ids` property.** `.env` files hold only text, so a list of user IDs is
stored as a comma-separated string and parsed on access into `set[int]`. A set because
membership testing is the only operation needed; ints because Telegram IDs are numeric.

**Depends on:** `pydantic-settings`, the `.env` file.
**Depended on by:** almost everything — `database.py`, `bot.py`, `auth.py`, `services.py`,
`llm/__init__.py`, `timeparse.py`, `alembic/env.py`.

**Design decisions.** (a) No secrets in code, ever. (b) Fail fast on missing critical
config. (c) `extra="ignore"` so `.env` can hold keys this class doesn't declare — necessary
because `POSTGRES_USER`/`PASSWORD`/`DB` are consumed by the *database container*, not the
app.

**What could go wrong.** Adding a `.env` key without declaring it here means it is silently
ignored. Conversely, declaring a field without a default and forgetting the `.env` entry
crashes every service at startup.

**Concepts demonstrated.** Class inheritance; reserved-name configuration conventions;
`@property` as computed state; typed configuration; fail-fast design.

**What I learned.** That `extra="ignore"` was needed only became apparent when a Docker
volume mount made `.env` visible inside the container for the first time and pydantic
rejected the three `POSTGRES_*` keys. A configuration change in one layer surfaced a latent
assumption in another — a good lesson in how coupling hides until something shifts.

## `app/database.py`

**Purpose.** Own all database connection machinery so no other module constructs its own.

**Contents.** Three module-level objects and one context manager:
- `engine = create_engine(settings.database_url)` — the connection pool, created once
- `SessionLocal = sessionmaker(...)` — a factory producing sessions
- `Base = declarative_base()` — the registry every model inherits from
- `get_session()` — a `@contextmanager` wrapping commit/rollback/close

**Why `Base` matters beyond inheritance.** It maintains `Base.metadata`, a registry of
every table defined by a subclass. Alembic reads that registry to know what *should* exist.
Critically, a model only enters the registry if its module has been **imported** — which is
why `alembic/env.py` imports `app.models` with a `# noqa` comment despite appearing unused.

**`get_session()` — the important part.** Sessions carry three obligations, each easy to
forget:
1. **commit** — until you commit, changes exist only in memory. Forgetting this fails
   *silently*, which is the worst failure mode.
2. **rollback on exception** — a multi-write operation that fails halfway must not leave
   partial data.
3. **close, always** — in a `finally` block. Leaked connections stay checked out of the
   pool; leak enough and the application hangs with no obvious cause.

Wrapping all three once means callers cannot get it wrong.

**The trap this creates.** `commit()` **expires** all loaded ORM attributes (marks them
"must reload"), and `close()` detaches them from the session. So reading an attribute of an
object loaded inside the block, *after* the block, raises `DetachedInstanceError`. This bit
the project twice — see §16.

**Concepts demonstrated.** Connection pooling; the session/unit-of-work pattern; context
managers; `try/except/finally`; resource lifecycle management.

**What I learned.** That a convenience wrapper can *create* a subtle failure mode while
removing an obvious one, and that understanding *why* commit expires attributes lets you
predict the error rather than memorise a rule.

## `app/models.py`

**Purpose.** Declare the database schema as Python classes.

### `Message`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | Integer | PK, indexed | Postgres sequence, auto-increment |
| `text` | String | NOT NULL | message body |
| `sender` | String | NOT NULL, indexed | Telegram user ID as a string |
| `role` | String | NOT NULL, default `"user"` | `"user"` or `"assistant"` |
| `created_at` | DateTime | default `utcnow` | UTC by convention |

### `Reminder`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | Integer | PK, indexed | |
| `task` | String | NOT NULL | what to remind about |
| `recipient` | String | NOT NULL, indexed | Telegram chat/user ID |
| `due_at` | DateTime | NOT NULL, indexed | **UTC** |
| `sent` | Boolean | NOT NULL, default `False`, indexed | delivery state |
| `created_at` | DateTime | default `utcnow` | audit trail |

**Why the indexes exist, specifically.** Not decoration — each backs a real query.
`sender` because history is always filtered by user. `created_at` because history is always
sorted by it. `due_at` and `sent` because the scheduler queries
`WHERE due_at <= now AND sent = false` **every sixty seconds, forever**. Without those two,
that query would scan the whole table on every tick.

**The `role` column's history.** It didn't exist initially. Only messages *from* the user
were stored; replies weren't. When conversation history was added, that became untenable —
history needs both halves — so `role` was added by migration. Its addition caused the
project's most instructive migration failure (§16).

**Concepts demonstrated.** Declarative ORM mapping; column types and constraints; primary
keys; indexes as query-driven decisions; database-level vs application-level validation.

**What I learned.** That the *schema is the specification* — `nullable=False` is enforced
by Postgres itself, not merely hoped for by application code. And that adding a column to a
table with existing rows is a fundamentally different operation from creating a table.

## `app/logging_config.py`

**Purpose.** Configure logging once, at startup, with a consistent format.

**Contents.** `setup_logging(level="INFO")` calling `logging.basicConfig` with a
pipe-delimited format (`timestamp | LEVEL | module | message`), `stream=sys.stdout`,
`force=True`; then two `setLevel(WARNING)` calls to silence noisy libraries.

**Why stdout, not a file.** Docker captures a container's stdout — that *is* what
`docker compose logs` replays. Logging to a file inside a container means the logs vanish
the next time the container is recreated, which happens constantly during development.

**Why those two loggers are silenced — a real security fix.** The `httpx` library logs full
request URLs at INFO level, and **Telegram embeds the bot token in the URL path**. So the
application's own logs contained the bot token in plaintext. Those logs were then pasted
into a chat, the token was exposed, and it had to be revoked and reissued via BotFather.
Silencing `httpx` and `telegram.ext.Application` is the fix.

**Why `force=True`.** An imported library may have configured the root logger first;
`force=True` overrides whatever it did.

**Concepts demonstrated.** Hierarchical loggers; log levels as a filtering mechanism;
structured logging; the twelve-factor principle of treating logs as a stream.

**What I learned.** The single most valuable security lesson in the project: **your own
logs are an exfiltration channel.** Secrets leak through observability tooling, not just
through code. This is also why LLM output is truncated (`raw[:200]`) before logging.

## `app/auth.py`

**Purpose.** Enforce the allowlist exactly once, in a form that cannot be forgotten.

**Contents.** `require_auth(handler)` — a decorator wrapping an async Telegram handler. It
reads `update.effective_user.id`, checks membership in `settings.allowed_user_ids`, and on
failure logs at WARNING and **returns without replying**. On success it awaits the wrapped
handler.

**Why a decorator.** Before this existed, the identical check was copy-pasted into three
handlers. That's not merely ugly — it means every future handler requires *remembering* to
add it, and forgetting once ships an unprotected command. **Security that depends on memory
is not security.** A decorator makes the check declarative: `@require_auth` above the
function.

**Why silence rather than "access denied".** A denial message confirms the bot exists, is
alive, and has something worth attacking. Silence gives a stranger no information — they
cannot distinguish rejection from a dead bot. Denials are logged at WARNING (not INFO)
because a rejected access attempt is a security event that should stand out.

**Why long-polling makes this necessary.** The bot fetches *all* messages sent to it from
Telegram. There is no upstream filter. Authorization must happen in application code.

**`@wraps`.** Preserves the wrapped function's name and docstring, so tracebacks and
introspection stay useful instead of every handler appearing as `wrapper`.

**Concepts demonstrated.** Decorators as cross-cutting concerns; higher-order functions;
closures over module state; security by obscurity used *appropriately* (as a supplement to
a real control, not a replacement for one); defence in depth.

**What I learned.** That noticing duplication is a design signal, not a style preference —
and that the right response to "this check appears three times" is to make it impossible to
omit rather than to be careful.

## `app/intents.py`

**Purpose.** Declare, as data, every action the LLM is permitted to request.

**Contents.** `ChatIntent` (just `action: Literal["chat"]`), `CreateReminderIntent`
(`action: Literal["create_reminder"]`, `task` with length bounds, `when` as a raw string),
and `Intent = Union[...]`.

**Why `Literal[...]` is the load-bearing construct.** It constrains the field to one exact
string. Combined with the dispatch map in `intent_parser.py`, this means **an action that
isn't declared here cannot be requested.** If the model emits
`{"action": "delete_everything"}`, no schema matches and it's rejected. The set of possible
actions is closed by construction, not by hoping the prompt was obeyed.

**Why `Field(min_length=1, max_length=500)`.** Cheap constraints that eliminate whole
categories of nonsense: an empty task, or a runaway ten-thousand-character generation.

**Why `when` is a raw string, not a parsed date.** A deliberate division of labour. LLMs
are good at extracting *language* ("tomorrow at 09:00") from a sentence and unreliable at
*arithmetic* (what date that is, in which timezone). So the phrase is captured verbatim and
converted by `timeparse.py`. **Keep the model on language; keep your code on logic.**

**Concepts demonstrated.** Schema-as-specification; tagged unions / discriminated unions;
`Literal` types; declarative validation; allowlisting over blocklisting.

**What I learned.** That the safest way to constrain an LLM is not a better prompt but a
schema it must fit through.

## `app/intent_parser.py`

**Purpose.** Convert a user message into a **validated** `Intent`, or fail safely.

**Contents.** `INTENT_PROMPT` (the classification instructions), `_INTENT_MODELS` (action
string → pydantic model), `_strip_fences()`, and `parse_intent()`.

**Control flow — five sequential failure gates, one destination:**

```
LLM call ──── raises? ──────────────────→ ChatIntent
    ↓
strip fences, json.loads ── invalid? ───→ ChatIntent
    ↓
isinstance dict? ────────── no? ────────→ ChatIntent
    ↓
action in _INTENT_MODELS? ─ no? ────────→ ChatIntent
    ↓
model.model_validate() ──── raises? ────→ ChatIntent
    ↓
                                          validated Intent
```

**Why every path returns `ChatIntent`.** This is the central safety property. The worst
thing a confused, overloaded, or manipulated LLM can cause is **a conversation**. It cannot
fall through into an action by accident. Fail safe, not fail open.

**`_strip_fences()`.** Models wrap JSON in markdown code fences despite explicit
instructions not to. Rather than fight it with more prompt engineering, handle it in code —
a practical lesson about working *with* model behaviour instead of against it.

**Why the prompt forbids the word "next".** Empirical: `dateparser` fails on
`next Friday`. The prompt was amended to steer the model toward formats that parse. This is
a nice illustration of a constraint from one layer (a library gap) propagating into another
(prompt design).

**Why `raw[:200]` in the log line.** A runaway generation shouldn't flood the logs, and the
first 200 characters are enough to diagnose malformed output.

**Concepts demonstrated.** Defensive parsing; validation at a trust boundary; dispatch
tables over `if/elif` chains; graceful degradation; prompt engineering as an engineering
concern with testable behaviour.

**What I learned.** That "the LLM might return garbage" is not a hypothetical to handle
later — it's the normal case that the design must assume.

## `app/timeparse.py`

**Purpose.** Convert a natural-language time phrase into a naive UTC `datetime`, or `None`.

**Contents.** `parse_when(phrase)` — strips a leading `"next "`, calls `dateparser.parse`
with three settings, converts to UTC, strips tzinfo, and rejects past times.

**The three dateparser settings, and why each matters:**

- `"TIMEZONE": settings.timezone` — interprets "14:00" as 14:00 **in Vilnius**. Without
  this, every timed reminder would be off by the UTC offset (three hours in summer) with no
  visible cause.
- `"RETURN_AS_TIMEZONE_AWARE": True` — needed so the conversion to UTC is meaningful rather
  than a no-op.
- `"PREFER_DATES_FROM": "future"` — bare "Friday" is ambiguous; reminders are always
  forward-looking. This is also what makes stripping "next" safe, since bare "Friday"
  already resolves to the upcoming one.

**`.replace(tzinfo=None)`.** The columns are `timestamp without time zone`. The value is
UTC *by convention*, consistently with `created_at` using `utcnow`. Documented rather than
enforced by the type — a real weakness, noted in §17.

**The past check.** If a phrase resolves to a time already gone, return `None`. Storing a
reminder that can never sensibly fire is worse than refusing it.

**How the "next" bug was found.** Four one-line probes established that `tomorrow`,
`tomorrow at 09:00`, `Friday 14:00`, and `in 2 hours` all work while both `next Friday` and
`next Friday at 14:00` return `None`. The fix was applied in **two** places — the prompt and
the code — because an LLM will not reliably follow instructions.

**Concepts demonstrated.** Timezone-correct datetime handling (store UTC, convert at the
boundaries); defensive input normalisation; returning `None` as an explicit failure signal;
defence in depth.

**What I learned.** Probe a library's actual behaviour rather than trusting its
documentation or reputation. Four commands found the exact boundary.

## `app/services.py`

**Purpose.** The application's core logic — **the layer that knows what Jarvis does,
without knowing anything about Telegram.**

**Contents.** `SYSTEM_PROMPT`, `HISTORY_LIMIT = 10`, `save_message()`,
`get_recent_history()`, `handle_message()`, `create_reminder()`.

**Why this layer exists.** `handle_message(text, sender) -> str` takes plain strings and
returns a plain string. No `Update` object, no Telegram types. That boundary means a future
web dashboard or voice interface calls the *same* function rather than duplicating the
logic. This was created by a deliberate refactor — and paid off immediately: replacing echo
with LLM replies was a two-line change touching one file.

**`get_recent_history()` — two subtleties.**

1. **The ordering trick.** To get the ten *most recent* messages you must sort
   newest-first and take ten, then reverse in Python for chronological order. Sorting
   ascending with a limit would return the *oldest* ten — the opposite of what's wanted.
2. **The plain-dict conversion happens inside the `with` block.** Non-negotiable: the ORM
   objects are detached once the session closes.

**`handle_message()` — ordering matters twice.**

- History is fetched **before** the new message is saved, otherwise the current message
  appears both in the history and as the prompt.
- The assistant reply is saved **only on success**. A `return` inside the `except` prevents
  "Sorry, I couldn't reach my brain" entering history as something Jarvis said, which would
  poison subsequent context.

**`create_reminder()`.** Parses the phrase; on `None` returns an honest message suggesting
working formats; otherwise stores the reminder and confirms using **local** time converted
back from UTC. Confirming "11:00" when the user said "14:00" would look broken — hence
convert at the boundary.

**Concepts demonstrated.** Service-layer architecture; dependency direction (services know
nothing about transport); the LLM as a swappable dependency; ordering as correctness;
honest failure over silent failure.

**What I learned.** That a refactor which felt like tidying made the *next* feature
trivial. Good boundaries are not aesthetics — they're leverage.

## `app/llm/base.py`

**Purpose.** Define the contract every LLM provider must satisfy.

**Contents.** `LLMProvider(ABC)` with a single `@abstractmethod`:
`complete(prompt, system=None, history=None, label="chat") -> str`.

**Why an ABC rather than a convention.** `@abstractmethod` means Python **refuses to
instantiate** a subclass that omits `complete()`. The error arrives at construction, not at
2am when something calls a missing method. The contract is enforced, not documented.

**Why the interface says `"assistant"`.** Gemini calls the AI's turn `"model"`; Anthropic
calls it `"assistant"`. The interface picks a neutral name and **providers adapt to it**.
If provider vocabulary leaked into the service layer, the abstraction would be broken while
appearing to exist.

**Concepts demonstrated.** Abstract base classes; interface segregation; dependency
inversion (high-level code depends on the abstraction, not the concrete provider);
vocabulary normalisation at a boundary.

**What I learned.** An interface is a *decision about vocabulary* as much as about method
signatures.

## `app/llm/gemini.py`

**Purpose.** The only file in the project that knows Gemini exists.

**Contents.** `_ROLE_MAP` (`assistant → model`), `GeminiProvider.__init__` (client +
model), and `complete()`.

**How `complete()` works.** Builds a list of `types.Content` objects — one per history turn
with its mapped role, then the current prompt as a final `user` turn. Wraps the system
prompt in `GenerateContentConfig`. Calls `generate_content`. Logs usage. Returns
`response.text`.

**Why usage metadata is read with `getattr(..., None)`.** SDK response field names change
between versions. **A logging line must never break a working API call.** This is
defensive coding aimed squarely at observability code, which is easy to forget can itself
fail.

**The `label` parameter.** Distinguishes the two calls per message in the logs
(`label=intent` vs `label=chat`) so token spend is attributable. Without it, both calls log
identically and the data is useless.

**Concepts demonstrated.** The adapter pattern; encapsulating vendor quirks; defensive
attribute access; observability as a first-class concern.

**What I learned.** How to distinguish "my bug" from "their outage" — a 503 saying *high
demand* is their servers; a 404 is my model name; a `TypeError` is my code. And that
availability varies *per model*: `gemini-3.5-flash` returned 503 for every request while
`gemini-3.5-flash-lite` worked fine, making the fix a one-line `.env` change.

## `app/llm/__init__.py`

**Purpose.** The factory — the single place mapping a config string to a provider class.

**Contents.** `get_llm() -> LLMProvider`, reading `settings.llm_provider`, returning a
constructed provider, raising `ValueError` on an unknown name. Plus `__all__`.

**Why the return type is `LLMProvider`, not `GeminiProvider`.** Callers see only the
interface, so nothing downstream can accidentally depend on Gemini-specific behaviour. The
type annotation enforces the architectural intent.

**Known inefficiency.** `get_llm()` is called on every message, constructing a new client
each time. Wasteful but irrelevant at single-user volume. Left simple deliberately —
premature optimisation is its own failure mode.

**Concepts demonstrated.** Factory pattern; configuration-driven instantiation;
programming to an interface; `__all__` as an explicit public API.

## `app/scheduler.py`

**Purpose.** Deliver due reminders.

**Contents.** `async def send_due_reminders()` — queries reminders where
`due_at <= now AND sent = false`, extracts plain tuples inside the session, constructs a
`Bot`, sends each message, marks each sent in a *separate* session, and `continue`s past
failures.

**Why polling instead of one scheduled job per reminder.** The decisive argument: scheduled
jobs live in **memory**. A container restart would silently discard every pending reminder,
and the failure would be invisible — reminders simply stop arriving. Polling puts the
**database as the source of truth**, so a restart loses nothing; the next tick picks up
whatever is due.

**Why `due_at <= now` and not `== now`.** If the container was down when a reminder came
due, `<=` catches it on the next tick after startup. Late beats never.

**Why `sent` is set only after a successful send, in its own session.** If Telegram is
unreachable, `continue` leaves `sent=False` and the next tick retries. A failed reminder is
delayed, not lost. Using a separate session per update means one failure doesn't roll back
the others.

**Why plain tuples.** Sending takes network time; the ORM objects would be detached long
before the loop finishes.

**Concepts demonstrated.** Polling vs event-driven trade-offs; idempotent-ish delivery via
a state flag; durable state over in-memory state; partial-failure handling; at-least-once
delivery semantics.

**What I learned.** That "what happens when this restarts?" is a design question to ask
*before* choosing a mechanism, not after.

## `app/bot.py`

**Purpose.** The transport layer — Telegram in, Telegram out, and nothing else.

**Contents.** Three decorated handlers (`start`, `help_command`, `echo`),
`_start_scheduler()` as a `post_init` hook, and `main()`.

**What each handler does now.** Receives, logs, delegates to the service layer, replies.
No authorization logic (the decorator handles it), no database code, no LLM calls. Compare
to its pre-refactor state, which did all four.

**`filters.TEXT & ~filters.COMMAND`.** Route plain text to `echo`, but not commands —
those have dedicated `CommandHandler`s. The `~` is negation.

**`_start_scheduler` and the `post_init` hook — a real bug and its fix.**
`AsyncIOScheduler.start()` calls `asyncio.get_running_loop()`. Inside the *synchronous*
`main()`, no loop exists yet — it's created by `run_polling()`. So starting the scheduler in
`main()` raised `RuntimeError: no running event loop` in a crash loop. `post_init` is a
python-telegram-bot lifecycle hook invoked after the loop starts but before polling begins:
exactly the right window.

**Why `help_command` and not `help`.** `help` is a Python builtin. Shadowing it works but
is poor practice.

**Concepts demonstrated.** Thin transport layers; async handlers; framework lifecycle
hooks; the event-loop model; decorator-based cross-cutting concerns.

**What I learned.** The generalisable rule: **anything asyncio-based must be created inside
a running event loop, not before it.** The same shape of fix applies to async database
engines and HTTP clients.

## `app/main.py`

**Purpose.** The HTTP surface. Currently just a health check.

**Contents.** `setup_logging()`, a module logger, `app = FastAPI(title=settings.app_name)`,
a startup log line, and `GET /health` returning status, app name, and environment.

**Why it exists at all.** The bot doesn't need HTTP. This is scaffolding for a future web
dashboard, plus a conventional liveness probe. Reasonable, though it does mean a container
runs continuously for a single endpoint — noted in §17.

**Concepts demonstrated.** Decorator routing; automatic JSON serialisation; health-check
conventions; configuration reaching the response layer.

## `alembic/env.py` (modified)

**Purpose.** Tell Alembic how to connect and what the target schema is.

**The three edits made, and why each is necessary:**

1. `config.set_main_option("sqlalchemy.url", settings.database_url)` — reads the URL from
   `.env` **instead of hardcoding it in `alembic.ini`**, which would put the database
   password in a committed file.
2. `target_metadata = Base.metadata` — gives autogenerate the "what should exist" side of
   the diff.
3. `from app import models  # noqa: F401` — the subtle one. `Base.metadata` is only
   populated by models that have been *imported*. Without this line the registry is empty
   and Alembic detects nothing to create.

**A related gotcha this file creates.** `DATABASE_URL` uses the hostname `db`, which only
resolves **inside** the Docker network. Alembic must therefore run via
`docker compose exec api alembic ...`, not from the host. Running it on the host fails to
resolve `db`.

**What I learned.** That an "unused" import can be load-bearing, and that `# noqa` comments
exist to tell both linters and future readers that the oddity is intentional.

## `alembic/versions/15acf0cb38e8_create_messages_table.py`

The first migration: `create_table('messages', ...)` with four columns, primary key, and an
index on `id`. `down_revision = None` marks it as the chain's root.

**The instructive history.** The *first* attempt at this migration generated
`alter_column` statements instead of `create_table` — because the `messages` table had been
created **by hand** in psql while experimenting with raw SQL. Alembic diffs against
reality, so a hand-made table made it produce a migration that would fail on any clean
database.

**Why that matters beyond the immediate fix.** A migration that assumes something already
exists is unreproducible, which defeats the entire purpose. The rule learned: **never
create or alter tables by hand; let Alembic own the schema.** The fix was to drop the
hand-made table, delete the bad migration, and regenerate.

## `alembic/versions/c4d84d2142c5_add_role_and_indexes_to_messages.py`

Adds the `role` column and indexes on `sender` and `created_at`.
`down_revision = '15acf0cb38e8'`.

**The project's most instructive failure.** Autogenerate produced:

```python
op.add_column('messages', sa.Column('role', sa.String(), nullable=False))
```

Applied against a table containing eleven rows, this failed with
`NotNullViolation: column "role" of relation "messages" contains null values`. Existing
rows need a value, and none was supplied.

**Why autogenerate missed it.** The model declares `default="user"`, but that is a
**Python-side** default — SQLAlchemy applies it when *you* construct an object. Alembic does
not translate Python defaults into SQL. What existing rows need is `server_default`, applied
by Postgres itself:

```python
op.add_column('messages', sa.Column('role', sa.String(), nullable=False, server_default='user'))
```

**Two things worth noting.** First, Alembic's own generated comment says
`# ### commands auto generated by Alembic - please adjust! ###` — the tool tells you it's a
draft. Second, the failure **rolled back cleanly**: `\d messages` afterwards showed no
`role` column and no new indexes. Migrations run in a transaction, so a failure leaves no
half-applied state.

**A downstream consequence.** All eleven existing rows were backfilled to `role='user'`.
The history window then looked like ten consecutive unanswered questions, and the model
tried to address them all — including an old pizza-recipe request. Not a bug; a data
artifact. Diagnosing it required knowing what the migration had done to the data.

## `alembic/versions/c7e1b69254bd_add_reminders_table.py`

Creates `reminders` with six columns and four indexes.
`down_revision = 'c4d84d2142c5'`.

**Clean this time** — a new table has no rows to backfill, so no `server_default` was
needed. But note the asymmetry: `sent` has no server-side default, so a hand-written
`INSERT` in psql omitting it would fail. All reminders are created through application code,
so this is acceptable — but it's an implicit assumption worth knowing about.

## `tests/test_health.py`

**Contents.** `TestClient(app)` at module level; `test_health_returns_ok` (asserts status
200 and `status == "ok"`); `test_health_reports_app_name`.

**Why `TestClient` matters.** It calls the ASGI app in-process — no uvicorn, no port, no
network. Which is why the suite runs in ~0.5s.

**Why two small tests instead of one big one.** A focused failure tells you what broke. A
test asserting six things tells you only that something did.

**What I learned.** That deliberately breaking an assertion to *watch* a test fail is worth
doing once — a suite you've never seen fail is one you're only assuming works.

**Honest assessment.** This is the project's weakest area. Two tests cover one trivial
endpoint. Nothing tests intent parsing, time parsing, the auth decorator, history
ordering, or reminder delivery — all of which contain the actual logic and all of which
broke at least once during development. See §17.

## `docker-compose.yml`

**Purpose.** Describe the entire runtime as one file.

**Three services:**

| Service | Image source | Ports | Notes |
|---|---|---|---|
| `db` | `postgres:16` | **none published** | named volume for data |
| `api` | `build: .` | `127.0.0.1:8000:8000` | loopback only |
| `bot` | `build: .` | **none** | `command: python -m app.bot`, `restart: unless-stopped` |

**Why `api` and `bot` share one image.** Same code, same dependencies; only the startup
command differs. `build: .` twice with a `command:` override on one. No second Dockerfile.

**Why `db` publishes nothing.** The security fix. The `api` reaches Postgres at `db:5432`
over the **private Docker network** — it never used a host port. Publishing 5432 exposed the
database to the public internet for no functional benefit. Removing it cost nothing.

**Why `api` binds `127.0.0.1` explicitly.** Omitting the interface makes Docker default to
`0.0.0.0` — *every* interface, including the public IP. On a VPS that means the whole
internet. `127.0.0.1:` restricts it to the host itself. Worth knowing: **a `ufw` firewall
does not reliably block Docker-published ports**, because Docker writes its rules ahead of
yours. Not binding the port is the reliable fix.

**Why `bot` publishes nothing at all.** Long-polling is entirely outbound.

**The named volume.** `jarvis_db_data:/var/lib/postgresql/data`. Postgres writes there
*inside* the container; the volume moves that data outside so it survives container
destruction. Without it, every recreate is a clean wipe.

**A production concern.** The `.:/app` bind mount was added so Alembic could write
migration files to the host. It also means the running code comes from the **host
filesystem, not the image** — a development pattern deployed to a 24/7 host. Discussed in
§17.

**What I learned.** That the *same compose file* is safe on the home VM (behind NAT) and
risky on the VPS (public IP). Same config, different exposure — because the machine's
network position changed, not the code.

## `Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**The layer-caching decision.** Copying `requirements.txt` and installing **before**
copying application code is deliberate. Docker caches layers; since code changes far more
often than dependencies, this ordering means editing a Python file doesn't trigger a full
reinstall. Observable in the build output as `CACHED` steps.

**`--no-cache-dir`.** Skips pip's download cache, keeping the image smaller.

**`--host 0.0.0.0` here is correct**, and does *not* contradict the security discussion.
Inside the container it means "accept connections from outside this container" — necessary
for the port mapping to work at all. Exposure is controlled at the compose layer.

**No `--reload`.** That's a development convenience, deliberately absent from the image.

## `.dockerignore` and `.gitignore`

`.dockerignore` excludes `.venv`, `__pycache__`, `*.pyc`, `.env`, `.git` — keeping the build
context small and secrets out of the image.

`.gitignore` excludes `.env`, `*.key`, `*.pem`, Python bytecode, virtualenvs, and editor
files. **This is a security control, not housekeeping.** It makes committing `.env`
structurally difficult rather than merely inadvisable — which matters because `git status`
was checked before every single commit and `.env` never once appeared.

## `requirements.txt`

`fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlalchemy`, `alembic`,
`psycopg2-binary`, `python-telegram-bot`, `google-genai`, `dateparser`, `apscheduler`,
`pytest`, `httpx`.

**Two honest problems.** (a) **No version pins.** A rebuild months from now may pull
incompatible versions, producing failures with no code change to blame. (b) **Test
dependencies are mixed with runtime dependencies**, so `pytest` and `httpx` ship in the
production image. Both discussed in §17.

## `README.md` and `COMMANDS.md`

`README.md` — project overview, MVP definition, architecture diagrams, tech stack, hardware
notes, a checkbox progress tracker, roadmap, structure tree, security principles, quickstart.

`COMMANDS.md` — a personal reference that grew organically into something more valuable
than a command list: a **lessons-learned log**. It records not just *what* commands to run
but the gotchas behind them (the httpx token leak, the `next` parsing gap, the
`DetachedInstanceError` rule, `0.0.0.0` vs `127.0.0.1`, `default=` vs `server_default=`, the
error-type triage table).

**Why this file is genuinely good practice.** Documentation written *by* the person who hit
the problem, *in their own words*, at the moment of understanding, is far more durable than
documentation copied from elsewhere. It is also the single best artifact in the repository
for demonstrating engineering maturity to another reader.

---

# 5. Architecture Deep Dive

## Architectural pattern

**Modular monolith.** One codebase, one deployable image, internally divided by
responsibility. Explicitly *not* microservices — the original brief ruled out Kubernetes,
Kafka, and distributed systems, correctly for a single-user project.

The three containers are not microservices. `api` and `bot` are the **same image** with
different entry points; `db` is third-party infrastructure.

## Layers and dependency direction

```
┌─────────────────────────────────────────────┐
│ TRANSPORT      bot.py, main.py              │  knows Telegram / HTTP
├─────────────────────────────────────────────┤
│ AUTHORIZATION  auth.py                      │  cross-cutting decorator
├─────────────────────────────────────────────┤
│ SERVICE        services.py                  │  knows what Jarvis DOES
│                intent_parser.py, timeparse.py│
├─────────────────────────────────────────────┤
│ PROVIDER       llm/ (base, gemini, factory) │  external AI, swappable
├─────────────────────────────────────────────┤
│ DATA           models.py, database.py       │  persistence
└─────────────────────────────────────────────┘
                    ↑
              scheduler.py cuts across
              (transport + service + data)
```

**Dependencies point downward only.** `services.py` imports from `llm/`, `models`,
`database`, `timeparse`, `intent_parser` — but **never** from `bot.py`. That single
constraint is what makes a future web interface possible without duplication.

`scheduler.py` is the one layer violation: it touches the database *and* constructs a
Telegram `Bot` directly. Defensible for a background job, but noted in §17.

## The request lifecycle

```
Telegram user sends a message
    ↓
Telegram servers hold it
    ↓
bot container's long-poll (getUpdates) retrieves it     [OUTBOUND ONLY]
    ↓
python-telegram-bot matches a handler by filter
    ↓
@require_auth checks user_id ∈ allowed_user_ids
    │
    ├── not allowed → log WARNING, return. No reply. END.
    ↓
echo() logs, delegates to handle_message(text, sender)
    ↓
get_recent_history(sender)  → SELECT ... ORDER BY created_at DESC LIMIT 10
    ↓                          (converted to dicts INSIDE the session)
save_message(role="user")   → INSERT
    ↓
parse_intent(text)          → LLM CALL #1  [label=intent, no history]
    ↓                          strip fences → json.loads → dispatch → validate
    │                          ANY failure → ChatIntent
    ↓
    ├── CreateReminderIntent ──→ create_reminder(task, when, recipient)
    │                              ↓ parse_when(when) → UTC or None
    │                              ↓ None → honest failure message
    │                              ↓ INSERT reminder
    │                              ↓ confirm in LOCAL time
    │                            save_message(role="assistant"); RETURN
    │
    └── ChatIntent ────────────→ LLM CALL #2  [label=chat, WITH history]
                                   ↓ try/except → friendly message on failure
                                 save_message(role="assistant")
    ↓
reply string returns to bot.py
    ↓
await update.message.reply_text(reply)      [OUTBOUND]
    ↓
Telegram delivers to the user's phone
```

## The scheduler lifecycle (independent, every 60s)

```
APScheduler interval trigger fires
    ↓
send_due_reminders()
    ↓
SELECT * FROM reminders WHERE due_at <= utcnow() AND sent = false
    ↓
extract (id, recipient, task) tuples INSIDE the session
    ↓
none? → return
    ↓
construct Bot(token)
    ↓
for each: await bot.send_message(...)
    │
    ├── raises → log exception, continue    [sent stays false → retries next tick]
    ↓
new session: reminder.sent = True; commit
```

## Data flow: two independent paths

Notice the asymmetry. **Inbound** messages arrive because the bot asked for them (pull).
**Outbound** reminders leave because the scheduler decided to send them (push). Both are
outbound TCP connections, which is why nothing needs to be exposed.

---

# 6. Database Architecture

## Schema

Two application tables plus Alembic's bookkeeping.

```
messages                          reminders
─────────────────────             ─────────────────────
id          PK, idx               id          PK, idx
text        NOT NULL              task        NOT NULL
sender      NOT NULL, idx         recipient   NOT NULL, idx
role        NOT NULL, def 'user'  due_at      NOT NULL, idx   ← UTC
created_at  def utcnow, idx       sent        NOT NULL, idx
                                  created_at  def utcnow

alembic_version
───────────────
version_num   ← which migration has been applied
```

## Relationships — deliberately none

There are **no foreign keys**. `messages.sender` and `reminders.recipient` both hold
Telegram user IDs as strings, but there is no `users` table to reference.

**Is that wrong?** For a single-user system, no. Adding a `users` table would be
speculative structure serving no current need. But it does mean:
- no referential integrity between the two tables
- the same identifier is duplicated as a string in two places
- a `users` table becomes a migration later if multi-user is ever wanted

The honest framing: correct for now, with a known migration path.

## Query patterns and their indexes

| Query | Where it runs | Index used | Frequency |
|---|---|---|---|
| `WHERE sender = ? ORDER BY created_at DESC LIMIT 10` | `get_recent_history` | `sender`, `created_at` | every message |
| `WHERE due_at <= ? AND sent = false` | `send_due_reminders` | `due_at`, `sent` | **every 60s forever** |
| `session.get(Reminder, id)` | marking sent | primary key | per delivery |

Every index backs a real query. The scheduler query is the one that matters most — without
its indexes, a full table scan every minute would degrade as the table grows.

## Timezone convention

**All stored datetimes are UTC.** Columns are `timestamp without time zone`, so this is
convention rather than enforcement — a real weakness. Conversion happens at the boundaries:
`parse_when` converts local→UTC on the way in, `create_reminder` converts UTC→local for the
confirmation message.

Verified empirically: `tomorrow at 09:00` stored as `06:00` UTC with Vilnius at UTC+3.

## Migration chain

```
None → 15acf0cb38e8 (messages) → c4d84d2142c5 (role + indexes) → c7e1b69254bd (reminders)
```

Linear, correctly chained by `down_revision`. On a fresh machine,
`alembic upgrade head` builds all three in order — proven when `docker compose down -v`
destroyed the database and one command rebuilt the schema.

## What is missing

**No backup strategy.** The data lives in a Docker named volume on a single VPS. No dumps,
no off-machine copy. Currently low-stakes (test messages), but the roadmap has email and
personal memory arriving — at which point this becomes the highest-priority gap.

---

# 7. Dependency Analysis

## Runtime dependencies

| Package | Purpose | Alternatives considered | Why this |
|---|---|---|---|
| `fastapi` | web framework | Flask, Django, Starlette | modern, typed, minimal, auto docs |
| `uvicorn[standard]` | ASGI server | hypercorn, daphne | the standard pairing |
| `pydantic-settings` | typed config from `.env` | `os.environ`, `python-decouple` | validation + fail-fast |
| `sqlalchemy` | ORM | raw psycopg2, Django ORM, Tortoise | injection safety, Alembic pairing |
| `alembic` | migrations | hand-written SQL, sqlalchemy-migrate | reads the models directly |
| `psycopg2-binary` | Postgres driver | `psycopg` (v3), `asyncpg` | widely documented |
| `python-telegram-bot` | Telegram API | `aiogram`, raw HTTP | mature, handles polling |
| `google-genai` | Gemini SDK | `google-generativeai` (**deprecated**) | current SDK |
| `dateparser` | NL date parsing | `parsedatetime`, `arrow` | timezone + future-preference settings |
| `apscheduler` | job scheduling | cron, celery beat | in-process, no extra infra |

## Test dependencies (currently unseparated)

`pytest`, `httpx`. Both ship in the production image. Should move to a separate file or a
`pyproject.toml` extras group.

## Risks identified

**Unpinned versions — the significant one.** No package has a version constraint. A rebuild
in six months may pull a breaking major release, producing a failure with no code change to
explain it. This nearly bit the project already: the Gemini SDK's response field names were
read via `getattr(..., None)` *specifically* because they change between versions.

**`psycopg2-binary` in production.** Convenient (precompiled), but the maintainers
recommend the source package for production. Low risk here.

**No dependency scanning.** No Dependabot, no `pip-audit`.

---

# 8. Configuration Analysis

## `.env` — never committed

Contains: `APP_NAME`, `ENVIRONMENT`, `POSTGRES_USER`/`PASSWORD`/`DB`, `DATABASE_URL`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS`, `GEMINI_API_KEY`, `LLM_PROVIDER`,
`LLM_MODEL`, `TIMEZONE`.

**Three genuinely secret values:** the Postgres password, the Telegram bot token (full
control of the bot — read every message, impersonate it), and the Gemini API key (billable,
and scanners actively hunt leaked keys on GitHub).

**Two subtleties worth noting:**

1. `DATABASE_URL` uses hostname **`db`**, not `localhost` or an IP. That name resolves only
   inside the Docker network. This is what makes the config portable — no machine-specific
   addresses — but it also means host-run Alembic commands fail.
2. The Postgres password is **only read when the data directory is first initialised**.
   Changing it in `.env` has no effect on an existing volume; a `down -v` reset is required.
   This is unintuitive and was learned the hard way.

**A remaining weakness:** the password was left as the placeholder
`change_this_to_something` for a period while port 5432 was published to a public IP. Both
have since been fixed. The lesson stands: placeholder credentials are a real vulnerability,
not a TODO.

## `.env.example` — committed

The same keys with secrets blanked and non-secret defaults filled in (`LLM_MODEL`,
`TIMEZONE`, `LLM_PROVIDER`). Non-secret defaults are useful documentation; secrets must be
empty.

**Why this file matters.** Since `.env` is git-ignored, a fresh clone has no configuration
at all. `.env.example` is the contract telling future-you what must be supplied. It must be
updated whenever a setting is added — a discipline that held throughout.

## `alembic.ini`

Largely default. The critical point is what it **doesn't** contain: the
`sqlalchemy.url` is overridden at runtime in `env.py` from settings, so the database
password never enters a committed file.

## Configuration not present

No linting config, no formatting config, no `pyproject.toml`, no pre-commit hooks, no CI
config. All would be reasonable next additions.

---

# 9. Git & GitHub Analysis

> **NOT FULLY INSPECTED.** I could not access the repository's Git history, branch list,
> or GitHub metadata. What follows is what was observed during the build sessions.

## Observed facts

- Repository: `github.com/Zygiz/Project-Jarvis`, **private**, intended to go public later
- Single branch: `main`. No branching workflow was used.
- Created via GitHub's web UI with a README; `.gitignore` was added manually afterwards
- Commits are frequent and small, one per completed task, with descriptive present-tense
  messages (`Add Telegram user ID allowlist for bot authorization`)
- **First five commits are attributed to `root <root@srv1867218.hstgr.cloud>`** — the VPS
  had no `git config` identity. These don't link to the GitHub account or count toward the
  contribution graph.
- A **deliberate decision was made not to rewrite history** to fix that attribution, after
  weighing force-push risk and VM/VPS divergence against a cosmetic gain on five commits
- `.env` **never appeared** in `git status` before any commit — verified every time
- Development happened on **two machines** (VirtualBox VM, then the Hostinger VPS), each
  with its own SSH key registered to GitHub, synchronised via push-before-stop /
  pull-before-start

## What is absent

No `.github/` directory, no CI, no Actions, no PR or issue templates, no
`CONTRIBUTING.md`. No tags observed yet (a `v0.1` tag was planned).

## The attribution incident as a lesson

Worth recording because the *decision* is more interesting than the mistake. The
`root@srv...hstgr.cloud` address is auto-generated and unverifiable, so GitHub's
"add a secondary email" route was closed. The alternative — `git filter-branch` or
`filter-repo` plus a force push — was declined because it would overwrite remote history and
leave the other machine's clone incompatible, for a purely cosmetic benefit. **Knowing when
not to reach for a powerful tool is a real engineering skill.**

---

# 10. Testing Documentation

## What exists

Two tests, both against `/health`: one asserting HTTP 200 and `status == "ok"`, one
asserting the app name. Runtime ~0.5s. Run via `docker compose exec api pytest`.

## What is not tested — the honest list

Every piece of actual logic:

| Untested | Why it matters | Broke during development? |
|---|---|---|
| `parse_intent` | the security boundary | yes (fence handling) |
| `parse_when` | timezone + "next" bug | **yes** |
| `require_auth` | the only authentication | never verified denying |
| `get_recent_history` ordering | correctness of context | **yes** (`DetachedInstanceError`) |
| `send_due_reminders` | delivery + retry | **yes** (event loop) |
| `create_reminder` failure path | honest failure | no |
| `Settings` validation | fail-fast behaviour | **yes** (missing field) |

That third column is the argument. **Five of seven untested areas broke at least once**,
and each was caught manually by sending a Telegram message and reading logs.

## Concepts the existing tests do demonstrate

- **In-process testing.** `TestClient` calls the ASGI app directly — no server, no port, no
  network. That's why it's fast.
- **Discovery by convention.** `test_*.py` files, `test_*` functions. No registration.
- **Focused assertions.** Two small tests rather than one checking everything, so a failure
  identifies itself.
- **Package marker.** `tests/__init__.py` makes imports resolve.

## Recommended tests, in priority order

1. **`parse_when`** — highest value. Pure function, no I/O, and it has a known bug class.
   Table-driven: each working format, the "next" cases, past times, garbage input.
2. **`parse_intent`** with a **fake `LLMProvider`** — this is what the ABC was *for*. Feed
   it canned responses: valid reminder JSON, valid chat JSON, fenced JSON, malformed JSON, a
   JSON array, an unknown action, a task exceeding 500 chars. Assert every failure path
   yields `ChatIntent`. No API calls, no cost, deterministic.
3. **`require_auth`** — assert an allowlisted ID reaches the handler and a non-allowlisted
   one does not, and that no reply is sent.
4. **`get_recent_history` ordering** — insert known rows, assert oldest-first output and
   that the limit is respected.
5. **`send_due_reminders`** — with a stub bot: due-and-unsent is sent and marked; future is
   untouched; already-sent is skipped; a send failure leaves `sent=False`.

A `conftest.py` with a transactional test-database fixture would be needed for 4 and 5.

**What I learned.** That the test suite is thin *because* manual testing via Telegram was
immediate and satisfying — a real and common trap. The habit of deliberately breaking an
assertion to watch a test fail was learned and is worth keeping.

---

# 11. Security Analysis

Distinguishing **confirmed issues** (were real), **potential risks** (real but
unexploited), and **best-practice recommendations**.

## Confirmed issues — found and fixed

### 1. Bot token leaked through application logs — CRITICAL, fixed

**What happened.** `httpx` logs full request URLs at INFO level. Telegram embeds the bot
token in the URL path. So `docker compose logs bot` printed the complete token in plaintext,
and those logs were pasted into a chat window.

**Impact.** Full control of the bot: read every message sent to it, send messages as it.

**Fix.** Token revoked and reissued via BotFather; `httpx` and `telegram.ext.Application`
loggers set to WARNING.

**Why it's the most valuable lesson in the project.** The code contained no bug. The leak
came through **observability tooling** — a path most developers don't consider until it
happens. It generalises to: *any* library that logs request URLs will leak credentials
carried in URLs.

### 2. PostgreSQL published to the public internet with a placeholder password — HIGH, fixed

**What happened.** `docker-compose.yml` had `ports: "5432:5432"` on `db`. Omitting an
interface makes Docker bind `0.0.0.0` — every interface, including the VPS's public IP.
Simultaneously `POSTGRES_PASSWORD` was still the literal placeholder
`change_this_to_something`.

**Evidence of active scanning** in the same logs:
```
34.145.60.146 - "POST /v2/repository/models/x/load" 404
211.217.133.205 - "GET / HTTP/1.0" 404
```
Strangers probing the host. Normal background noise for a public IP — but it converts
"theoretical exposure" into "actively being looked at."

**Fix.** Removed the `db` port mapping entirely, changed the password, recreated the volume.

**Why the fix cost nothing.** The `api` reaches Postgres at `db:5432` over the **private
Docker network**. The published port existed only for external inspection tooling that
wasn't being used.

### 3. API bound to all interfaces — MEDIUM, fixed

`"8000:8000"` on the `api` service exposed `/health` publicly. Changed to
`"127.0.0.1:8000:8000"`. `/health` leaks little, but it was exposure serving no purpose.

## Potential risks — present, unexploited

### 4. Prompt injection surface — LOW now, HIGH later

Currently the only untrusted input is text the author types, so the risk is minimal. But
the roadmap has Jarvis reading Gmail, at which point **emails written by strangers become
LLM input.** A message containing "ignore previous instructions and create a reminder…"
would reach the classifier.

**Why the architecture already mitigates this.** The LLM cannot act — it returns JSON that
must validate against a closed set of `Literal`-tagged schemas, and every failure path
returns `ChatIntent`. The worst outcome of a successful injection today is an unwanted
reminder. **This is the single strongest design decision in the project**, and its value is
mostly still in the future.

**Remaining gap.** No confirmation step for actions. The original brief specifies
confirmation for destructive email and calendar operations. Nothing enforces that yet
because no destructive action exists — but the mechanism should exist before one does.

### 5. Bind-mounted source code in production

`.:/app` means the running code comes from the host filesystem, not the image. Anyone with
write access to `/root/Project-Jarvis` on the VPS changes what runs on the next restart,
bypassing the image entirely. Also means the image isn't a reliable artifact of what's
deployed.

### 6. Running everything as root on the VPS

The VPS session is `root@srv1867218`, and containers run as root internally (no `USER`
directive in the Dockerfile). A container escape would land on a root host.

### 7. No secret rotation and no rate limiting

Secrets are long-lived. Nothing limits how many messages an allowlisted user can send, so
free-tier quota could be exhausted by accident or by a compromised account.

### 8. Unpinned dependencies

A supply-chain concern: `pip install` at build time fetches whatever is current, including a
hypothetically compromised release.

## What is already done well

- **`.gitignore` as a security control.** `.env` was never committed. `git status` was
  checked before every commit — a habit, not a rule.
- **`.env.example` discipline.** Secrets blank, non-secrets documented.
- **No hardcoded credentials anywhere in the code.**
- **Alembic reads the URL from settings** rather than `alembic.ini`, keeping the password
  out of a committed file.
- **Silent denial.** No information disclosure to unauthorized users.
- **Denials logged at WARNING**, distinguishing security events from routine ones.
- **Truncated LLM output in logs** (`raw[:200]`), limiting log-flooding and accidental
  disclosure.
- **Long-polling instead of webhooks**, eliminating the need for any inbound exposure.
- **Validation before action** — the trust boundary.

## Recommendations, prioritised

1. Add a non-root `USER` to the Dockerfile
2. Remove the `.:/app` bind mount from the production configuration
3. Pin dependency versions
4. Add a confirmation step for actions before any destructive tool exists
5. Add basic per-user rate limiting
6. Add a Postgres backup routine **before** email or personal memory arrives
7. Stop using `root` for routine VPS work

---

# 12. Performance Analysis

## Already good

**Every index backs a real query.** Not decorative. The scheduler's
`WHERE due_at <= ? AND sent = false` runs every sixty seconds indefinitely; both columns are
indexed.

**Bounded history.** `HISTORY_LIMIT = 10` caps per-message token cost. Unbounded history
would grow linearly forever — message 500 would carry 499 predecessors.

**Docker layer caching.** Dependencies install before code copy, so code edits don't
trigger reinstalls.

**In-process tests.** No network or server, hence sub-second runs.

**Early return in the scheduler.** `if not payloads: return` avoids constructing a `Bot`
object on the majority of ticks when nothing is due.

## Genuine inefficiencies

### 1. Two LLM calls per message — the significant one

Every message triggers a classification call *and* a reply call. Consequences:
- **Halves the effective free-tier request budget**
- Roughly doubles latency
- Doubles token spend on a paid tier

**Fix options:** (a) a single call using the provider's structured-output or tool-calling
support, letting one response contain both classification and reply; (b) classify with a
cheaper/faster model — trivial given the abstraction; (c) skip classification for messages
that obviously aren't commands, e.g. a cheap keyword prefilter.

Left unoptimised deliberately, which is defensible at single-user volume — but it *is* the
current binding constraint.

### 2. `get_llm()` called per message

Constructs a new `genai.Client` on every call. Wasteful (connection setup, no pooling),
irrelevant at this volume, trivially fixed with module-level caching or
`functools.lru_cache`.

### 3. Synchronous database calls inside async handlers

`handle_message` is called from an `async` handler but does blocking database I/O and a
blocking HTTP call. This **blocks the event loop** for the duration. With one user, nobody
notices. With concurrent users, throughput collapses. The proper fix is async SQLAlchemy
plus an async LLM client, or offloading to a thread executor.

This is the most architecturally significant performance issue, and it's invisible at
current scale — a good example of a problem that only appears under load.

### 4. Scheduler constructs a `Bot` per tick

Only when reminders are due, so mostly harmless. Could be created once.

### 5. `SELECT *` via the ORM

Loads all columns when the scheduler needs three. Immaterial at this row count.

## Scaling notes

Current design assumes **one bot container**. Two would both poll Telegram (conflicting) and
both run the scheduler (double-sending reminders — `sent` is checked and set in separate
transactions, so there's a race window). Fine as-is; worth knowing before ever scaling
horizontally.

---

# 13. Code Quality Analysis

## Strengths

**Consistent, purposeful module boundaries.** Each file has one job, and the names say what
it is. `timeparse.py` parses time; `auth.py` authorizes. No `utils.py` grab-bag.

**Comments explain *why*, not *what*.** This was a deliberate habit. From `config.py`:

```python
# model_config = a reserved settings slot that BaseSettings reads
# automatically when Settings() is created below. We never call it
# ourselves — pydantic hunts for this exact name.
```

That comment captures something genuinely confusing. A comment saying
`# the app name` above `app_name` would add nothing. The distinction was understood and
applied.

**Type hints throughout**, including meaningful ones: `-> datetime | None` documents the
failure mode in the signature.

**Duplication was noticed and removed.** The auth check existed three times before becoming
a decorator. That's the correct trigger and the correct response.

**Error handling is deliberate rather than reflexive.** `except Exception` appears in
exactly the places where an external system can fail (LLM calls, Telegram sends), always
with `logger.exception` to preserve the traceback, and always with a considered fallback.

**Naming avoids shadowing builtins** (`help_command`, not `help`).

**Private helpers are marked** with a leading underscore (`_strip_fences`, `_ROLE_MAP`,
`_INTENT_MODELS`, `_start_scheduler`).

## Weaknesses

**Test coverage is the clearest one.** Two tests, both trivial. §10 has the detail.

**`services.py` is becoming a grab-bag.** It currently holds the system prompt, message
persistence, history retrieval, orchestration, *and* reminder creation. As tools multiply,
`create_reminder` and its successors belong in a `tools/` package with a registry, so adding
a tool doesn't mean editing `handle_message`'s branching.

**The intent branch will not scale as an `isinstance` chain.** Three tools means three
`elif`s. A dispatch dict mapping intent type → handler function would mirror
`_INTENT_MODELS` and keep `handle_message` constant-size.

**Naive datetimes as a convention.** "All datetimes are UTC" is documented, not enforced.
Timezone-aware columns (`DateTime(timezone=True)`) would make it structural.

**Duplicated identifier semantics.** `sender` in `messages` and `recipient` in `reminders`
hold the same kind of value, and `recipient` is used as a Telegram `chat_id`. For direct
messages user ID and chat ID coincide; **in a group they don't.** Latent bug if group
support is ever added.

**No linter or formatter.** Import ordering was inconsistent at one point (a duplicate
`from app.models import Message` existed alongside
`from app.models import Message, Reminder`). `ruff` would catch that, plus unused imports
and undefined names, in milliseconds.

**Unpinned dependencies.** Covered in §7.

**Magic values.** `HISTORY_LIMIT = 10` is named (good), but the scheduler's `minutes=1` and
`raw[:200]` are inline literals.

## An observation about how the code was written

Three separate file-corruption incidents occurred from pasting multi-line Python into a
terminal: wiped imports in `config.py` (`NameError: BaseSettings is not defined`), mangled
indentation in `services.py` (`IndentationError`), and lost docstring quotes in
`intent_parser.py` (`invalid character '—' (U+2014)`, then
`unterminated triple-quoted string`).

**Worth recording** because the response was correct: switch tooling. VS Code Remote-SSH
preserves indentation and surfaces syntax errors before running anything. The diagnostic
habit that emerged — `grep` the file to confirm an edit saved, then
`python -c "import app.services"` to check it parses, *before* restarting a container — is
faster than reading a crash loop and is a genuinely transferable practice.

---

# 14. Important Design Decisions

## Decision 1 — The LLM returns validated intents; it never acts

**Context.** An assistant that only chats is a toy. Acting requires converting natural
language into machine instructions. The obvious shortcut is giving the model database or
shell access.

**Reasoning.** The original brief ruled that out explicitly. LLMs hallucinate, get
confused, and are steerable by whatever text they're fed. Once Jarvis reads email, its input
includes text written by strangers.

**Implementation.** `intents.py` declares `Literal`-tagged pydantic schemas.
`intent_parser.py` prompts for JSON, strips fences, parses, dispatches on the action
string, validates. **Every failure path returns `ChatIntent`.**

**Alternatives.** Direct database access (unsafe); native function-calling/tool APIs
(cleaner, provider-specific, would weaken the abstraction); regex/keyword parsing (brittle,
no language understanding).

**Trade-offs.** Gained: a closed set of possible actions, guaranteed-shaped data
downstream, no defensive checks after the gate. Sacrificed: an extra LLM call per message,
and prompt-following brittleness (mitigated by `_strip_fences` and the "next" workaround).

**Lesson.** **The safest way to constrain an LLM is a schema, not a better prompt.** A
prompt is a request; a schema is a gate.

## Decision 2 — Provider abstraction before a second provider existed

**Context.** Gemini's free tier removed cost as a barrier, but local models on the RTX 4080
are a stated goal (Phase 13), and free-tier privacy terms conflict with the project's own
privacy principle.

**Implementation.** `base.py` (ABC), `gemini.py` (adapter), `__init__.py` (factory).
Neutral role vocabulary (`assistant`) with per-provider translation (`_ROLE_MAP`).

**Trade-offs.** Cost: ~40 extra lines and one indirection before any second provider
existed. Gained: **it paid off within the hour, twice.** `gemini-2.5-flash` turned out to be
retired for new keys → one `.env` line. Later `gemini-3.5-flash` returned 503 on every
request while `flash-lite` worked → one `.env` line.

**Lesson.** Abstractions are cheapest to build before you need them and most expensive to
retrofit. But the justification must be a *concrete* anticipated change, not "flexibility"
in the abstract — here it was a specific, named future requirement.

## Decision 3 — Long-polling, not webhooks

**Reasoning.** Webhooks need a public HTTPS endpoint, an open port, TLS certificates, and a
stable address — impossible behind home NAT, and a security surface on a VPS. Long-polling
is entirely outbound.

**Trade-offs.** Gained: zero published ports on the bot, identical behaviour on VM and VPS,
no TLS management. Sacrificed: a continuous outbound connection, marginally higher latency,
and it doesn't scale to multiple instances.

**Lesson.** **The right architecture can eliminate a security requirement rather than
satisfy it.** Nothing to secure beats something secured well.

## Decision 4 — Scheduler polls the database instead of scheduling per-reminder jobs

**Reasoning.** Per-reminder jobs live in memory. A container restart discards them, and the
failure is **silent** — reminders simply stop arriving with no error.

**Implementation.** One interval job every 60s querying `due_at <= now AND sent = false`;
`sent` set only after a successful send, in a separate session.

**Trade-offs.** Gained: restart-safe, automatic catch-up for missed reminders, automatic
retry on send failure. Sacrificed: up to 60s delivery imprecision, and a query every minute
forever.

**Lesson.** Ask **"what happens when this restarts?"** *before* choosing a mechanism. Also:
the 60s imprecision was initially mistaken for a bug — checking `created_at` versus `due_at`
in the database showed the timing was exactly right. **Verify against data before assuming
a bug.**

## Decision 5 — Store UTC, convert at the boundaries

**Context.** Author in Lithuania (UTC+3 in summer). "Remind me at 14:00" means local time.

**Implementation.** `parse_when` interprets in `settings.timezone` and converts to UTC;
`create_reminder` converts back for the confirmation message.

**Trade-offs.** Gained: unambiguous storage, DST-correct, portable across server locations.
Sacrificed: conversion at every boundary, and stored values that aren't human-readable
without conversion.

**Lesson.** Timezone bugs are silent and hard to trace — a reminder firing three hours late
looks like a scheduler fault, not a parsing fault. Cheap to get right up front, painful to
retrofit once real data exists.

## Decision 6 — The service layer knows nothing about Telegram

**Context.** Pre-refactor, `bot.py` did authorization, persistence, formatting, and
transport. The auth check was copy-pasted three times.

**Trade-offs.** Cost: one refactor session producing no user-visible change. Gained: the
*next* feature — replacing echo with LLM replies — was a two-line change in one file. A
future web or voice interface calls the same function.

**Lesson.** **A refactor that felt like tidying made the next feature trivial.** Boundaries
are leverage, not aesthetics. Also: noticing the same check three times is a *design*
signal, not a style preference.

## Decision 7 — Keep `when` as a raw phrase; parse it in code

**Reasoning.** LLMs extract language reliably and compute dates unreliably, especially
across timezones and DST.

**Trade-offs.** Gained: deterministic, testable, timezone-correct date logic. Sacrificed: a
dependency on a parser with its own gaps — discovered immediately (`next`).

**Lesson.** **Keep the model on language; keep your code on logic.** Draw the line at what
each is actually good at.

## Decision 8 — Two containers from one image

`api` and `bot` share a Dockerfile, differing only by `command:`. Gained: one build, no
duplication, guaranteed identical dependencies. Sacrificed: a slightly larger image for
each (both contain everything). Lesson: **container boundaries are about process lifecycle,
not about code separation.**

## Decision 9 — Declining to rewrite Git history

Five commits attributed to `root`. The fix required a force push plus re-cloning on the
other machine, risking work loss for a cosmetic gain.

**Lesson.** Knowing when *not* to use a powerful tool is a real skill. The mistake was
cheap; the fix was expensive; the correct answer was to configure identity going forward and
move on.

---

# 15. Important Code Patterns

## Adapter pattern — `llm/gemini.py`

Wraps a third-party interface to satisfy a local one. `_ROLE_MAP` translates
`assistant → model` so provider vocabulary never escapes the file. **Advantage:** vendor
quirks are contained. **Disadvantage:** an indirection to read through, and the interface
must be general enough for every provider.

## Factory pattern — `llm/__init__.py`

`get_llm()` maps a config string to a concrete class. **Advantage:** one place to change
when adding providers; callers never name a concrete class. **Alternative:** a plugin
registry with entry points — more flexible, unnecessary here.

## Abstract base class as contract — `llm/base.py`

`@abstractmethod` makes an incomplete implementation *un-instantiable*. **Advantage:**
errors at construction, not at call time. **Alternative:** duck typing or `typing.Protocol`
(structural rather than nominal — arguably a better fit, since it doesn't require
inheritance).

## Decorator for cross-cutting concerns — `auth.py`

`@require_auth` applies authorization declaratively. **Advantage:** written once, cannot be
forgotten. **Disadvantage:** control flow is less obvious to a reader who doesn't know the
decorator exists.

## Context manager for resource lifecycle — `database.py`

`get_session()` guarantees commit/rollback/close. **Advantage:** callers can't leak
connections or forget to commit. **Disadvantage:** it *creates* the
`DetachedInstanceError` trap, since commit expires attributes before close detaches them.

## Service layer — `services.py`

Business logic isolated from transport. **Advantage:** reusable across interfaces,
testable without Telegram. **Disadvantage:** an extra layer for trivial operations; and
this one is starting to accumulate unrelated responsibilities.

## Dispatch table over conditionals — `_INTENT_MODELS`

`{"chat": ChatIntent, "create_reminder": CreateReminderIntent}` replaces an `if/elif`
chain. **Advantage:** adding an action is a dict entry; the lookup is the validation
(unknown key → `None` → safe fallback). **Note:** the *consumer* side in `handle_message`
still uses `isinstance` branching and should adopt the same pattern.

## Fail-safe fallback — `parse_intent`

Every failure converges on the least-privileged outcome. **Advantage:** no failure mode
escalates into an action. **Disadvantage:** genuine bugs can hide as "just chatting" —
mitigated by logging each fallback reason at WARNING.

## Polling with a state flag — `scheduler.py`

Durable queue semantics using a boolean column. **Advantage:** restart-safe, self-retrying,
no message broker. **Disadvantage:** up to 60s latency, a periodic query forever, and a race
window if two instances ever ran. **Alternative at scale:** a real queue (Redis, RabbitMQ)
or Postgres `SELECT ... FOR UPDATE SKIP LOCKED`.

## Layer-cache-aware Dockerfile ordering

Dependencies before code. **Advantage:** fast rebuilds. **Disadvantage:** none meaningful —
this is simply correct.

---

# 16. Confirmed Bugs & Issues

Bugs that actually occurred, with their diagnoses. Included because the diagnostic reasoning
is the transferable part.

## Bug 1 — `NotNullViolation` adding `role` to a populated table

**File.** `alembic/versions/c4d84d2142c5_...py`
**Error.** `column "role" of relation "messages" contains null values`
**Cause.** Autogenerate emitted `nullable=False` with no server-side default. Eleven
existing rows had nothing to put there. The model's `default="user"` is **Python-side** —
SQLAlchemy applies it when constructing objects, not during DDL.
**Fix.** Add `server_default='user'` to the `add_column` call.
**Severity.** Medium — blocked the migration, no data loss (transactional rollback).
**Lesson.** `default=` ≠ `server_default=`. Read generated migrations before applying them;
Alembic's own comment says `please adjust!`.

## Bug 2 — `DetachedInstanceError` reading ORM attributes after session close

**File.** `app/services.py`, `get_recent_history` (and later the same class of issue in
`scheduler.py`)
**Error.** `Instance <Message> is not bound to a Session; attribute refresh operation
cannot proceed`
**Cause.** The list comprehension building plain dicts sat **outside** the
`with get_session()` block. `get_session()` commits on exit — which *expires* all loaded
attributes — then closes, detaching them. Reading `r.role` then tried to reload from a dead
session.
**Fix.** Move the conversion inside the `with` block.
**Severity.** High — crashed every message handler.
**Secondary lesson, arguably more valuable.** The crash produced **silence**, not an error
reply, because it happened in `get_recent_history` — *before* the `try/except` around the
LLM call. **Error handling only protects the code it wraps.** And silence is
indistinguishable from an authorization denial, which makes it a genuinely confusing failure
mode.

## Bug 3 — `RuntimeError: no running event loop` starting APScheduler

**File.** `app/bot.py`, `main()`
**Cause.** `AsyncIOScheduler.start()` calls `asyncio.get_running_loop()`. In the
synchronous `main()`, no loop exists — `run_polling()` creates it later.
**Fix.** Start the scheduler from a `post_init` hook, which runs after the loop exists but
before polling begins.
**Severity.** High — crash loop, bot completely down.
**Lesson.** Anything asyncio-based must be created **inside** a running event loop. The
same fix shape applies to async DB engines and HTTP clients.

## Bug 4 — Alembic generated `alter_column` instead of `create_table`

**Cause.** The `messages` table had been created **by hand** in psql while experimenting
with raw SQL. Alembic diffs models against *reality*, so it produced a migration to modify
the existing table.
**Why it mattered.** That migration would fail on any clean database — the table wouldn't
exist to alter. Unreproducible migrations defeat the whole purpose.
**Fix.** Drop the hand-made table, delete the migration, regenerate.
**Lesson.** **Let Alembic own the schema.** Never create or alter tables by hand.

## Bug 5 — `dateparser` returns `None` for phrases containing "next"

**File.** `app/timeparse.py`
**Cause.** A library limitation, not a code error. `next Friday` and
`next Friday at 14:00` both fail; `Friday 14:00` works.
**Fix, in two places.** `INTENT_PROMPT` instructs the model to avoid "next";
`parse_when` strips a leading `"next "` defensively. Safe because
`PREFER_DATES_FROM: "future"` already resolves bare "Friday" forward.
**Lesson.** Probe libraries with quick empirical tests. And defend in two layers, because
an LLM won't reliably follow instructions.

## Bug 6 — `extra_forbidden` validation error after adding a volume mount

**Cause.** `.dockerignore` excluded `.env`, so the container had never *seen* the file —
config arrived as environment variables via `env_file`. Adding `.:/app` made the real
`.env` visible, pydantic read every key, and rejected the three `POSTGRES_*` keys that
`Settings` doesn't declare (they belong to the database container).
**Fix.** `extra="ignore"` in `model_config`.
**Lesson.** A change in one layer (a volume mount) surfaced a latent assumption in another
(what the app can see). Coupling hides until something shifts.

## Bug 7 — Docker Compose silently ignored a mis-indented `ports:` key

**Symptom.** `docker compose ps` showed the `api` container running with **no PORTS
value**, and `curl` couldn't connect.
**Cause.** YAML indentation. A mis-indented key isn't an error — it's simply not read as
belonging to that service.
**Lesson.** Verify *observed state* (`docker compose ps`), not just that a command exited
zero. Silent misconfiguration is worse than a crash.

## Bug 8 — Three file-corruption incidents from terminal pastes

`NameError: BaseSettings is not defined` (imports wiped), `IndentationError` (function
pasted at the wrong indent level, nested inside another function), and
`invalid character '—' (U+2014)` followed by `unterminated triple-quoted string` (docstring
quotes lost, so prose was parsed as code).

**Lesson.** Use a real editor over SSH rather than terminal heredocs. And build the habit:
`grep` to confirm the edit saved → `python -c "import app.x"` to confirm it parses →
*then* restart.

## Non-bugs correctly diagnosed as external

Worth listing, because correctly *not* fixing your own code is a skill.

- **`telegram.error.NetworkError: Bad Gateway`** — Telegram's servers; the library retried
  and recovered.
- **`503 UNAVAILABLE — This model is currently experiencing high demand`** — Gemini's
  servers. Confirmed by running the LLM call in isolation (three lines, touching none of
  the day's edits) and seeing it fail identically. Resolved by switching model.
- **Reminders appearing to fire "almost immediately."** Checking `created_at` versus
  `due_at` showed exactly the requested interval; the ≤60s scheduler slop plus the
  expectation of waiting made it *feel* instant.
- **Repeated old questions after the `role` migration.** All backfilled rows were
  `role='user'`, so the window looked like ten unanswered questions.
- **`Direct use of automatic function calling (AFC) ... is not recommended`** — an SDK
  advisory, not an error.

**The generalisable triage.** Isolate the failing piece and re-run it. Then: `5xx` → their
servers; `4xx` → my request or quota; `TypeError`/`NameError` → my code.

---

# 17. What I Would Improve

## Critical

### 1. Postgres backups

**Now:** data lives in one Docker named volume on one VPS. No dumps, no off-machine copy.
`docker compose down -v` has already destroyed the database once (deliberately).
**Why it matters:** currently only test data — but Phase 6 (email) and Phase 10 (personal
memory) make this catastrophic. **Fix:** a cron'd `pg_dump` to a separate location, plus a
*tested* restore. **Difficulty:** low. **Learning:** backup strategy, cron, the discipline
that an untested backup is not a backup.

### 2. Tests for the logic that actually breaks

**Now:** two tests on `/health`; five of seven untested areas have already broken once.
**Fix:** the priority list in §10, starting with `parse_when` (pure function) and
`parse_intent` with a fake provider. **Difficulty:** low to medium. **Learning:** test
doubles, table-driven tests, and *why* the ABC makes fakes trivial — the abstraction's
second payoff.

### 3. Pin dependency versions

**Now:** every package unpinned. **Why:** a future rebuild can break with no code change to
blame. **Fix:** `pip freeze` into pinned requirements, or adopt `pyproject.toml` with a
lockfile. Separate test dependencies from runtime. **Difficulty:** low.

## Important

### 4. Reduce to one LLM call per message

The binding constraint on the free tier. Options in §12. **Learning:** structured-output /
tool-calling APIs, and how to add a capability to the abstraction without breaking it.

### 5. Reminder management commands

**Now:** reminders can only be created. No listing, no cancelling, no editing. If the LLM
misparses something, it's stuck in the database until removed via psql. **Fix:** `/reminders`
to list and a cancel path — plus new intents, which will immediately expose the
`isinstance` scaling problem.

### 6. Remove the production bind mount, add a non-root container user

`.:/app` means deployed code comes from the host filesystem, not the image. And no `USER`
directive means containers run as root. **Fix:** separate compose override files for dev
and production; add a `USER` line. **Learning:** compose overrides, container user
namespaces, dev/prod parity.

### 7. Add a linter and formatter

`ruff` plus `ruff format`, ideally via pre-commit. Would have caught the duplicate import
instantly. **Difficulty:** very low. **Benefit:** disproportionate.

### 8. A tool registry instead of `isinstance` branching

**Now:** `handle_message` branches on intent type; three tools means three `elif`s. **Fix:**
a dict mapping intent type → handler, mirroring `_INTENT_MODELS`, so adding a tool touches
no orchestration code. **Learning:** the open/closed principle made concrete.

## Nice to have

### 9. Timezone-aware datetime columns

Replace naive UTC-by-convention with `DateTime(timezone=True)`. Migration required.
Makes the convention structural.

### 10. Cache the LLM client

Module-level or `lru_cache` instead of constructing per message.

### 11. A registered PTB error handler

The logs showed `No error handlers are registered, logging exception`. Registering one gives
central handling for unexpected handler failures.

### 12. Delete or clearly label `docker-practice/`

Dead code. Either remove it or note in the README that it's a learning artifact.

### 13. Add the missing `LICENSE` file

The README claims MIT; no license file was observed.

## Long-term

### 14. Async database and LLM access

The current synchronous I/O inside async handlers blocks the event loop. Invisible at one
user, fatal under concurrency. Would mean async SQLAlchemy and an async LLM client.
**Learning:** the async ecosystem properly, and how to recognise event-loop blocking.

### 15. Confirmation flow for actions before any destructive tool exists

The brief requires confirmation for destructive email/calendar operations. Build the
mechanism (inline keyboards, pending-action state) *before* the first destructive tool, not
after.

### 16. A `users` table

Needed for genuine multi-user support, and it would fix the `sender`/`recipient`/`chat_id`
conflation.

### 17. CI on GitHub Actions

Run `pytest` and `ruff` on every push. **Learning:** CI/CD, YAML workflows, and the
discipline of a green build.

---

# 18. Difficult Concepts, Explained Three Ways

## Ports and port mapping

**Simple.** An IP address is a building's street address; a port is the office number
inside it. One machine runs many programs, so the port says *which program* the traffic is
for. Port numbers like 22 (SSH) or 5432 (Postgres) are conventions everyone agreed on so
nobody has to ask.

**Technical.** In this project the concept appears at three nested levels. VirtualBox
forwards Windows port 2222 → VM port 22, so `ssh -p 2222 localhost` reaches the VM. Docker
forwards host port 8000 → container port 8000, so `curl localhost:8000` reaches uvicorn.
And within the Docker network, the `api` container reaches Postgres at `db:5432` **without
any host port at all**, because Docker provides internal DNS. The left side of `X:Y`
defaults to `0.0.0.0` — every interface, public IP included — which is why the explicit
`127.0.0.1:` prefix matters on a VPS.

**Practical.** This distinction *is* the security model. Reaching a container from outside
requires a published port; containers reaching each other doesn't. So publishing Postgres
was pure risk with no benefit. The rule: publish only what something outside the machine
genuinely needs, as narrowly as possible.

## Docker volumes

**Simple.** Containers are disposable boxes. Delete one and everything inside disappears.
A volume is a storage locker *outside* the box, so its contents survive.

**Technical.** Postgres writes to `/var/lib/postgresql/data` inside the container. The
named volume `jarvis_db_data` mounts over that path so the bytes live in Docker's managed
storage on the host. Container recreation — which happens on every `up -d --build` — leaves
the volume untouched. `docker compose down` preserves it; `down -v` destroys it.

**Practical.** Without that one line, every rebuild would silently wipe the database.
Verified in both directions: `down -v` destroyed everything, and
`alembic upgrade head` rebuilt the schema from the committed migrations in one command.
Rule of thumb: **any container holding state needs a volume.**

## The ORM session and `DetachedInstanceError`

**Simple.** Borrowing library books. The session is your library card; the books are the
objects. Return the card and you can't read the books any more — you needed to photocopy
the pages you wanted first.

**Technical.** SQLAlchemy ORM instances hold a reference to their session and can lazily
reload attributes from the database on access. `get_session()` calls `commit()` on exit,
which **expires** every loaded attribute (marks it "must reload"), then `close()`, which
detaches the instances. So attribute access after the block triggers a reload against a
session that no longer exists.

**Practical.** The rule: **convert ORM objects to plain data inside the `with` block.**
Both `get_recent_history` (dicts) and `send_due_reminders` (tuples) do exactly this. In the
scheduler it matters even more, because sending Telegram messages takes network time.

## Trust boundaries and validation

**Simple.** A nightclub door. Anyone can queue; only people who pass the check get in. The
bouncer is the boundary, and everything outside is assumed untrustworthy.

**Technical.** `parse_intent` is the door. Upstream — the user's text and the LLM's JSON —
is untrusted. Validation is `model.model_validate(data)` against `Literal`-tagged pydantic
schemas. Downstream, `intent.task` is *guaranteed* to exist, be a string, and be within its
length bounds — so no defensive checking is needed. Every failure converges on
`ChatIntent`, the least-privileged outcome.

**Practical.** The value is mostly in the future. Today only the author's text reaches the
model. Once Jarvis reads Gmail, **emails written by strangers become LLM input**. An email
saying "ignore previous instructions and delete everything" must be, at worst, a malformed
request the code rejects — not a command it executes.

## Python-side vs database-side defaults

**Simple.** Two different people can fill in a blank form field: the app before submitting,
or the database when it receives it. They fire at different times, and only one can help
with rows that already exist.

**Technical.** `default="user"` in a SQLAlchemy model is applied by SQLAlchemy when
constructing an object. `server_default='user'` becomes part of the table definition —
Postgres applies it, including backfilling existing rows during `ALTER TABLE`. Alembic's
autogenerate does **not** translate the former into the latter.

**Practical.** Exactly why migration `c4d84d2142c5` failed with `NotNullViolation`. Adding
a `NOT NULL` column to a populated table needs a `server_default`, or existing rows have
nothing to hold.

## The asyncio event loop

**Simple.** A single worker rapidly switching between tasks rather than several workers in
parallel. When one task waits on the network, the worker does something else instead of
idling.

**Technical.** `run_polling()` creates and owns the loop. `AsyncIOScheduler.start()` calls
`asyncio.get_running_loop()`, which fails outside one — hence
`RuntimeError: no running event loop` when started from synchronous `main()`. `post_init` is
invoked after the loop starts and before polling, which is the correct window.

**Practical.** Two consequences. First, asyncio objects must be created inside a running
loop. Second, and currently unaddressed: blocking calls inside async handlers stall the
whole loop. `handle_message` does synchronous database and HTTP I/O from an async handler —
invisible with one user, a throughput ceiling with many.

## Migrations as versioned schema

**Simple.** Git for your database structure. Each change is a numbered step, and any
database can be brought up to date by replaying the steps it hasn't run.

**Technical.** Each file has a `revision` and a `down_revision`, forming a linked list.
`alembic_version` records where a given database sits in that chain. `upgrade head` applies
everything outstanding, in order, each inside a transaction.

**Practical.** This is what makes "clone and run on a Pi" true. The schema is code in Git,
not manual steps in someone's memory. Demonstrated when the volume was destroyed and one
command rebuilt three migrations' worth of structure.

---

# 19. How Everything Connects

## If I change this file, what breaks?

### `app/config.py`

**Impact: total.** Imported by `database.py`, `bot.py`, `auth.py`, `services.py`,
`llm/__init__.py`, `timeparse.py`, `scheduler.py`, and `alembic/env.py`. A syntax error
takes down all three containers *and* Alembic. Removing a field breaks every consumer.
Adding one is safe; adding one *without a default* breaks every service until `.env` is
updated on every machine.

### `app/database.py`

**Impact: high.** `Base` feeds `models.py` and therefore Alembic's autogenerate.
`get_session` is used by `services.py` and `scheduler.py`. Changing `get_session`'s
commit/close semantics would change where `DetachedInstanceError` appears.

### `app/models.py`

**Impact: high, and it extends beyond code into the database.** A change here makes the
models disagree with the live schema until a migration is generated *and* applied on **every
machine**. Consumers: `services.py`, `scheduler.py`, all migrations, Alembic autogenerate.

### `app/llm/base.py`

**Impact: medium, but it's a contract change.** Every provider must satisfy it. Adding a
parameter with a default is backward-compatible; adding a required one breaks
implementations. Demonstrated when `label` was added — `base.py` was updated first and the
other three sites lagged, so the parameter silently defaulted and the logs were useless
until all four files agreed.

### `app/services.py`

**Impact: medium.** The orchestration hub. `bot.py` depends on `handle_message`'s signature.
Everything else it touches, it touches downward — so changes here don't ripple *up* except
through that one function's contract.

### `app/bot.py`

**Impact: low — and that's the point.** Nothing imports it; it's an entry point. Breaking it
breaks the bot but leaves the API, the service layer, and the database untouched. **A thin
transport layer at the top of the dependency graph is a deliberate property**, not an
accident.

### `docker-compose.yml`

**Impact: infrastructure-wide.** Governs exposure, data persistence, and startup order.
The two most dangerous edits: removing the volume (data loss) and widening a port binding
(public exposure).

### `.env`

**Impact: total, and per-machine.** Not in Git, so every machine has its own and they can
silently drift. Changes need `up -d`, not `restart`.

## Dependency chains

**Inbound message:**
```
Telegram → bot.py → auth.py → services.py → intent_parser.py → llm/ → Gemini
                                    ↓              ↓
                              timeparse.py    intents.py
                                    ↓
                              database.py → models.py → Postgres
```

**Outbound reminder:**
```
APScheduler → scheduler.py → database.py → models.py → Postgres
                    ↓
              telegram.Bot → Telegram → phone
```

**Schema change:**
```
models.py → Base.metadata → alembic/env.py → autogenerate → versions/*.py
                                                                ↓
                                                     upgrade head → Postgres
                                                                ↓
                                              (repeat on EVERY machine)
```

**Configuration:**
```
.env → config.py::Settings → everything
  ↓
.env.example (must be kept in sync, committed)
```

## The one-line summary

**Dependencies point downward.** Transport depends on services; services depend on
providers and data; nothing depends on transport. That single property is why swapping echo
for an LLM was two lines, and why a web dashboard would require no changes to existing
logic.

---

# 20. Learning Map

## Beginner concepts

| Concept | Where |
|---|---|
| Linux filesystem, navigation, permissions | VM/VPS sessions |
| `sudo` and privilege | Docker install |
| SSH and key-based auth | both machines |
| Text editing (`nano`, then VS Code Remote-SSH) | throughout |
| Reading terminal output and error messages | every debugging round |
| Python modules, imports, packages | `app/`, `app/llm/` |
| Functions, classes, inheritance | all models and providers |
| Dictionaries, lists, sets, comprehensions | history, intents, allowlist |
| f-strings and `%s` log formatting | throughout |
| Git add/commit/push | every session |

## Intermediate concepts

| Concept | Where |
|---|---|
| Decorators | `auth.py`, FastAPI routes, `@contextmanager` |
| Context managers | `get_session()` |
| Abstract base classes | `llm/base.py` |
| Type hints, including unions and `Optional` | throughout |
| Environment-based configuration | `config.py` |
| ORM modelling | `models.py` |
| Database indexes as query-driven decisions | both tables |
| Migrations | `alembic/versions/` |
| Structured logging and log levels | `logging_config.py` |
| REST endpoints and JSON | `main.py` |
| Docker images, containers, volumes, networks | Dockerfile, compose |
| Multi-container orchestration | `docker-compose.yml` |
| Unit testing and in-process test clients | `tests/` |
| Exception handling with deliberate fallbacks | `services.py`, `scheduler.py` |
| `.gitignore` as a security control | `.gitignore` |

## Advanced concepts

| Concept | Where |
|---|---|
| Trust boundaries and validation gates | `intent_parser.py` |
| Schema-constrained LLM output (`Literal` tagging) | `intents.py` |
| Provider abstraction / dependency inversion | `llm/` |
| Async event loops and lifecycle hooks | `bot.py` `post_init` |
| ORM session identity, expiry, and detachment | the `DetachedInstanceError` bug |
| Timezone-correct datetime handling | `timeparse.py` |
| Durable job scheduling via database state | `scheduler.py` |
| Fail-safe vs fail-open design | every `ChatIntent` fallback |
| Python-side vs server-side defaults | migration `c4d84d2142c5` |
| Layer-cache-aware image builds | `Dockerfile` ordering |
| Observability as an exfiltration channel | the httpx token leak |

## Framework-specific knowledge

**FastAPI:** decorator routing, automatic JSON serialisation, ASGI, `TestClient`, `/docs`.
**SQLAlchemy 2.x:** `create_engine`, `sessionmaker`, `declarative_base`, `select()`,
`.scalars().all()`, `session.get()`, expiry-on-commit semantics.
**Alembic:** `init`, `revision --autogenerate`, `upgrade`, `downgrade`, `current`,
`history`, revision chaining, `target_metadata`, why models must be imported.
**python-telegram-bot:** `Application.builder()`, `CommandHandler`, `MessageHandler`,
filters and negation, async handlers, `post_init`, `run_polling`, `Bot.send_message`.
**pydantic / pydantic-settings:** `BaseSettings`, `model_config`, `SettingsConfigDict`,
`Field` constraints, `Literal`, `model_validate`, `ValidationError`, `extra="ignore"`.
**google-genai:** `Client`, `models.generate_content`, `types.Content`/`Part`,
`GenerateContentConfig`, `usage_metadata`, `models.list()`.
**APScheduler:** `AsyncIOScheduler`, interval triggers, event-loop requirements.
**dateparser:** `TIMEZONE`, `RETURN_AS_TIMEZONE_AWARE`, `PREFER_DATES_FROM`, and its gaps.

## Architecture knowledge

Modular monolith over microservices; layered architecture with unidirectional
dependencies; the service layer as an interface-agnostic core; adapter and factory
patterns; dispatch tables over conditionals; the deliberate choice *not* to over-engineer
(no Kubernetes, no Kafka, no separate vector database).

## DevOps knowledge

Docker image authoring and layer caching; Compose service definition, dependencies, and
volumes; the `0.0.0.0` vs `127.0.0.1` distinction and that `ufw` doesn't reliably cover
Docker-published ports; VM vs VPS deployment; SSH keys per machine; systemd service
enablement; VM snapshots as rollback points; disk-usage inspection; `docker system prune`
safety semantics; **and the migration itself** — cloning from GitHub onto a fresh machine
and having it running in minutes, which validated the entire portability thesis.

## Database knowledge

Schema design and column constraints; primary keys and sequences; **indexes chosen from
query patterns**; migrations as versioned code; transactional DDL; `default=` vs
`server_default=`; UTC storage conventions; connection pooling and session lifecycle; psql
meta-commands; database size inspection; the absence of foreign keys as a deliberate
single-user choice.

## Security knowledge

Secrets in `.env`, never in Git; `.env.example` as a safe contract; **secrets leaking
through logs**; token revocation and rotation; minimising published ports; that placeholder
passwords are real vulnerabilities; silent denial to avoid information disclosure;
allowlist authorization; validation-before-action; prompt injection as a future threat the
architecture already mitigates; that public IPs are scanned continuously; least privilege as
an unfinished item (root containers, root VPS sessions).

## Testing knowledge

pytest discovery conventions; in-process ASGI testing; focused assertions; deliberately
breaking a test to watch it fail; and — honestly — recognising what *isn't* tested and why
that matters, since five of the seven untested areas broke during development.

## Debugging knowledge

The reflex order: `docker compose ps` → `docker compose logs <service>` → `grep` the file →
isolate the failing piece. Reading tracebacks bottom-up. Using line numbers as a hint (line
1 means missing imports). **Distinguishing error categories:** `SyntaxError` means nothing
ran at all; `NameError` means a missing import; `5xx` means their servers; `4xx` means my
request; `TypeError` means my code. Checking syntax with
`python -c "import app.x"` *before* restarting a container. Verifying observed state rather
than trusting exit codes. And — importantly — **checking data before assuming a bug**, as
with the reminder timing.

## Software engineering practices

Small frequent commits with descriptive messages; per-machine Git identity;
push-before-stop / pull-before-start across two machines; reading generated code before
running it; documenting *why* rather than *what*; maintaining a personal lessons log
(`COMMANDS.md`); refactoring when duplication appears rather than when it hurts; deferring
complexity deliberately (no client caching, no usage table); and knowing when *not* to use a
powerful tool (declining the history rewrite).

---

# 21. Learning Timeline

> Reconstructed from the build sessions. The **sequence** is first-hand and reliable; exact
> commit boundaries were not inspected.

## Stage 1 — Linux and Docker foundation

Created an Ubuntu Server VM in VirtualBox; got locked out immediately by a forgotten
username; recovered via the GRUB `init=/bin/bash` route. Enabled SSH, set up a NAT port
forward, connected from Windows. Installed Docker from the official repository, hit a
harmless stale-cdrom apt warning, discovered the daemon wasn't running, ran `hello-world`.
Explored ports/networks/volumes with a throwaway nginx container, then wrote a trivial
Dockerfile.

**Learned:** the VM/host boundary, SSH keys, `systemctl enable --now`, that "installed" and
"running" are different states, the three Docker concepts that would matter later, and that
recovering a locked-out Linux box is possible rather than terminal.

## Stage 2 — Backend and database

Project skeleton, `.gitignore`, `.env`/`.env.example`, typed config with pydantic-settings,
FastAPI with `/health`, a Dockerfile, then Compose with Postgres alongside. SQLAlchemy
models, Alembic setup, the first migration. Structured logging. First pytest tests.

**Learned:** that config precedence goes `.env` over class defaults; that
`model_config` is read automatically by the parent class; that containers find each other by
service name; that databases need volumes; the full model→migration→table chain; and — via
the hand-created table — that Alembic must own the schema.

**Unplanned detour that mattered.** Away from home and unable to reach the VM, the entire
project was cloned from GitHub onto the Hostinger VPS and running within minutes. That
*validated the portability thesis empirically* rather than theoretically, and the VPS
became the de facto 24/7 host. It also introduced the first real security exposure, since
the same compose file behaves very differently behind NAT versus on a public IP.

## Stage 3 — Telegram interface

BotFather registration, the echo bot as a third Compose service, the allowlist, command
handlers, message persistence, then a refactor into transport/auth/service layers.

**Learned:** long-polling versus webhooks and why the choice eliminates a security
requirement; that the bot receives *everything* so authorization must be in code; that
silence is a better denial than a message; and — from the refactor — that removing
triplicated code is a design decision.

**The token leak happened here**, and it's the most valuable single lesson in the project:
secrets leak through your own logs, not just through your code.

## Stage 4 — LLM integration

The provider abstraction built *before* a second provider existed. Gemini chosen for its
free tier, with the privacy trade-off noted explicitly. First round-trip. Conversation
history — requiring the `role` migration that failed on `NotNullViolation`. Structured
intent parsing with pydantic. The reminder tool with timezone-correct parsing and a polling
scheduler. Token usage logging.

**Learned:** that abstractions pay off faster than expected (twice within an hour, from a
retired model and then a 503); the `default=`/`server_default=` distinction; the ORM session
trap; the asyncio event-loop requirement; that libraries have undocumented gaps worth
probing for; and how to distinguish an outage from a bug by isolating the failing call.

**The conceptual centrepiece is here:** the trust boundary. Everything upstream of
validation is untrusted, including the model's own output, and every failure path converges
on the least-privileged outcome.

## What the progression shows

The sequence isn't arbitrary. Infrastructure before application; storage before the thing
that stores; a boundary before the feature that exploits it. Twice, a session that produced
**no user-visible change** — the service-layer refactor, and the provider abstraction — made
the *following* session's feature nearly trivial. That pattern recurring twice is the most
transferable observation in the whole project.

---

# 22. Skills Demonstrated

Only claims supported by what was actually built.

## Backend development — strong

A layered Python application with FastAPI, an ORM, migrations, structured logging,
configuration management, and deliberate error handling. Not a tutorial follow-along:
the layering was refactored into place for stated reasons and immediately paid off.

## Database design — solid

Two tables with appropriate constraints, indexes chosen from actual query patterns, three
migrations including a schema change to a populated table, and a documented UTC convention.
Understands transactional DDL and the Python/server default distinction. Gap: no backup
strategy.

## Docker and containerisation — strong

Multi-service Compose stack, one image serving two roles, volumes for persistence,
layer-cache-aware Dockerfile, and a genuine understanding of port publication as a security
decision. Deployed and running 24/7.

## Linux server administration — solid

VM provisioning, SSH with key auth, service enablement, package management from third-party
repositories, port forwarding through NAT, filesystem navigation, disk inspection, and
recovery from a lockout.

## LLM integration — strong, and the differentiator

This is the part most portfolios get wrong. Rather than calling an API directly, this
project has a provider abstraction, a validated structured-output boundary, bounded
conversation history, per-call usage logging, and a genuine articulation of *why* the model
must not act directly. The trust-boundary design would stand up to scrutiny in a senior
interview.

## Security awareness — solid, with honest gaps

Secrets management, `.gitignore` as a control, an allowlist, silent denial, minimal port
exposure, and — most tellingly — **finding, understanding, and fixing two real
vulnerabilities** in one's own project, then documenting them. The gaps (root containers,
no rate limiting, unpinned dependencies) are known and articulated rather than invisible.

## Git and collaborative workflow — competent

Small descriptive commits, per-machine SSH keys, two-machine synchronisation discipline, and
a reasoned decision to decline a history rewrite. No branching or PR workflow yet, which is
the honest limit of this claim.

## Debugging — strong, and underrated

Roughly a dozen distinct failures diagnosed and fixed, including several with misleading
symptoms: a crash that manifested as silence, a bug that was actually a vendor outage,
timing that looked wrong but was correct, and a data artifact that looked like a model
problem. The triage habits are documented well enough to teach.

## Technical writing — strong

`COMMANDS.md` is genuinely unusual for a personal project: a lessons log written in the
author's own words at the moment of understanding, recording gotchas alongside commands.
More valuable to a reader than the code itself.

## Not demonstrated — say so honestly

No frontend or UI work. No CI/CD. No meaningful test coverage. No team collaboration
(branches, PRs, code review). No horizontal scaling, caching layer, or message queue. No
type checking beyond hints. Claiming any of these would be unsupported.

---

# 23. Complexity Analysis

## What makes it simple

Single user; no frontend; one deployable image; no distributed system; low traffic (so
performance is mostly irrelevant); a small schema with two tables and no foreign keys; one
external API; and a deliberately narrow feature set.

## What makes it genuinely difficult

The **integration surface**. Each piece is individually approachable, but making Linux, SSH,
Docker, Compose, Postgres, SQLAlchemy, Alembic, Telegram, an LLM SDK, and a scheduler
cooperate — across two machines, with secrets, timezones, and an async runtime — is where
the real difficulty lives. Most bugs occurred at *boundaries*, not inside components.

## Ranked by difficulty

1. **The intent validation architecture** — conceptually the hardest. Requires
   understanding trust boundaries, why an LLM's output is untrusted, discriminated unions,
   and fail-safe design. Also the most valuable.
2. **Timezone-correct reminder handling** — deceptively hard. Local→UTC→local, DST,
   naive-versus-aware datetimes, and a parser with undocumented gaps. Errors here are
   silent and misattributed.
3. **The ORM session lifecycle** — the least intuitive. Requires understanding identity,
   expiry-on-commit, and detachment. The error message doesn't obviously point at the
   cause.
4. **Migrations against existing data** — the `default=`/`server_default=` distinction is
   subtle, and getting it wrong blocks deployment.
5. **The asyncio event loop** — a genuine conceptual hurdle, and the error message
   (`no running event loop`) doesn't suggest the fix.
6. **The provider abstraction** — moderate. ABCs and factories are standard once seen, but
   knowing *when* to abstract is judgement.
7. **Docker networking and port exposure** — moderate, with high stakes. The `0.0.0.0`
   default is a trap.
8. **The layered refactor** — moderate. Mechanically simple, conceptually about dependency
   direction.
9. **FastAPI, logging, config** — straightforward.

## Most error-prone areas

Migrations against existing data; ORM session boundaries; anything involving timezones;
YAML indentation (silent failures); `.env` synchronisation across machines; and pasting
code through a terminal.

## Most impressive implementation details

Three, in order:

**The validation gate with universal safe fallback.** Five failure modes converging on the
least-privileged outcome, with a closed action set enforced by `Literal` types. This is
architecture, not plumbing.

**The database-as-source-of-truth scheduler.** The reasoning — scheduled jobs die with the
process and fail *silently* — leads to a design that is restart-safe, self-catching-up, and
self-retrying, using nothing but a boolean column.

**Removing the Postgres port mapping at zero functional cost.** Recognising that the
published port served no purpose because the internal network already provided the path is
exactly the kind of insight that distinguishes understanding from configuration copying.

---

# 24. Glossary

**ABC (Abstract Base Class)** — a class that cannot be instantiated and declares methods
subclasses must implement. `LLMProvider`.

**Alembic** — the migration tool for SQLAlchemy. Diffs models against the live database and
writes versioned SQL.

**`alembic_version`** — Alembic's own table recording which migration a database has
reached.

**Allowlist** — the permitted set. Here, `TELEGRAM_ALLOWED_USER_IDS`. Safer than a
blocklist because the default is deny.

**APScheduler** — the in-process job scheduler running `send_due_reminders` every 60s.

**ASGI** — the async Python web server interface. FastAPI is an ASGI app; uvicorn is an
ASGI server.

**`Base`** — SQLAlchemy's declarative base. Also a registry: `Base.metadata` holds every
imported model, which is how Alembic knows what should exist.

**Bind mount** — mounting a host directory into a container (`.:/app`). Useful in
development; a concern in production.

**BotFather** — Telegram's bot for creating and managing bots. Source of the token; also
`/revoke`.

**Container** — a running instance of an image. Disposable by design.

**Context manager** — an object usable with `with`, guaranteeing setup and teardown.
`get_session()`.

**`create_reminder`** — the service function validating a time phrase and storing a
reminder.

**`DetachedInstanceError`** — raised when an ORM attribute is read after its session
closed.

**Discriminated union** — a union of types distinguished by a tag field. Here `action`,
constrained by `Literal`.

**Docker Compose** — declares a multi-container application in one file.

**Engine** — SQLAlchemy's connection pool. Created once.

**Event loop** — asyncio's scheduler. Created by `run_polling()`; required before
`AsyncIOScheduler.start()`.

**Fail safe / fail open** — on failure, deny (safe) or permit (open). Every failure path in
`parse_intent` fails safe.

**Factory** — `get_llm()`, constructing the right provider from configuration.

**`get_session()`** — the context manager guaranteeing commit, rollback, and close.

**`handle_message()`** — the service-layer entry point. Takes strings, returns a string,
knows nothing about Telegram.

**`HISTORY_LIMIT`** — 10. The bound on the conversation window.

**Image** — a built, immutable filesystem snapshot. `api` and `bot` share one.

**Index** — a database lookup structure. Every index here backs a real query.

**Intent** — a validated, structured action request. `ChatIntent` or
`CreateReminderIntent`.

**`Literal`** — a pydantic/typing construct constraining a field to exact values. What
closes the action set.

**Long-polling** — repeatedly asking Telegram for updates. All outbound; needs no open
ports.

**Migration** — one versioned schema change, chained by `down_revision`.

**Naive datetime** — one with no timezone attached. All stored datetimes here are naive but
UTC *by convention*.

**ORM** — Object-Relational Mapper. Lets you work with Python objects instead of SQL.

**`post_init`** — a python-telegram-bot lifecycle hook running after the event loop starts.
Where the scheduler is started.

**Prompt injection** — malicious instructions embedded in text the model reads. Mitigated
here by the validation gate; becomes a live threat at Phase 6.

**pydantic** — runtime validation from type declarations. Used for both config and LLM
output.

**`require_auth`** — the decorator enforcing the allowlist on every handler.

**`role`** — the `messages` column marking each row `"user"` or `"assistant"`. Added by
migration.

**`sent`** — the `reminders` boolean making delivery restart-safe and retryable.

**`server_default`** — a default applied by the database, including to existing rows during
a migration. Distinct from Python-side `default=`.

**Service layer** — `services.py`. Business logic, transport-agnostic.

**Session** — one unit of database work. Must be committed and closed.

**`SYSTEM_PROMPT`** — the standing instruction defining Jarvis's persona and brevity.

**Trust boundary** — the point where untrusted input becomes verified data. Here,
`model_validate` in `parse_intent`.

**UTC** — the storage convention for all datetimes. Converted at the boundaries.

**Volume** — Docker-managed storage outside a container. Without it, database data dies
with the container.

---

# 25. Interview Questions & Answers

## Beginner

**Q: Walk me through what happens when you message your bot.**

The bot container is long-polling Telegram, so it retrieves the message on its next
`getUpdates`. python-telegram-bot matches a handler by filter. The `@require_auth`
decorator checks my Telegram ID against an allowlist from `.env`; if it fails, it logs a
warning and returns without replying. Otherwise the handler delegates to
`handle_message(text, sender)` in the service layer, which fetches the last ten messages
for that sender, saves the incoming one, and calls the intent parser. That's one LLM call
returning JSON, which gets validated against pydantic schemas. If it's a reminder intent,
the app parses the time phrase, stores a row, and confirms in local time. Otherwise a
second LLM call generates a reply with history as context. Either way the reply is saved
with `role="assistant"` and returned to the transport layer, which sends it back.

**Q: Why Docker?**

Portability, primarily. The whole point was that the same stack runs on my dev VM, the VPS,
and eventually a Raspberry Pi. I proved it mid-project: I was away from home and couldn't
reach my VM, so I cloned from GitHub onto a VPS and had it running in minutes — install
Docker, clone, create `.env`, `compose up`, `alembic upgrade head`. No dependency
installation, no version mismatches.

**Q: What does `/health` do and why have it?**

Returns JSON with a status, the app name, and the environment. It's a liveness convention —
something can check whether the service is up. Honestly it's also scaffolding: the bot
doesn't need HTTP, but a web dashboard is on the roadmap and this is the foundation.

## Technical

**Q: Explain your logging setup and one thing you learned from it.**

`setup_logging()` configures a pipe-delimited format — timestamp, level, module, message —
writing to stdout, because Docker captures stdout and that's what `docker compose logs`
shows. Logging to a file inside a container is pointless; it vanishes on recreation.

The thing I learned was uncomfortable. `httpx` logs full request URLs at INFO, and Telegram
puts the bot token *in the URL path*. So my own logs contained the token in plaintext, and I
pasted them somewhere. I revoked and reissued the token, then silenced those loggers. The
lesson generalises: your observability tooling is an exfiltration channel. My code had no
bug at all.

**Q: You have `try/except` around the LLM call but not around history retrieval. Was that
deliberate?**

Not initially, and it caused a real bug. A `DetachedInstanceError` in
`get_recent_history` — which runs *before* the try/except — crashed the handler, and the
user got **silence**. Which is indistinguishable from being unauthorized, so it was
genuinely confusing to diagnose. The lesson: error handling only protects the code it
wraps. I'd now argue for a top-level handler in the transport layer as a backstop, which is
on my improvement list.

**Q: Why does `parse_when` return `None` instead of raising?**

Because failing to parse a time phrase is an *expected* outcome, not an exceptional one.
The LLM might extract something ambiguous, or the user might phrase it oddly.
`create_reminder` checks for `None` and tells the user honestly, suggesting formats that
work. A reminder you *think* is set but isn't is worse than a clear rejection. I'd reserve
exceptions for genuinely unexpected conditions.

## Architecture

**Q: Why is the service layer separate from the Telegram code?**

So business logic isn't welded to one interface. `handle_message` takes plain strings and
returns a string — it doesn't import anything from Telegram. A web dashboard or voice
interface would call the same function.

It paid off immediately. The refactor produced no user-visible change, and the very next
task — replacing echo with LLM replies — was a two-line change in one file. If that logic
had lived in a Telegram handler, I'd have been duplicating it for every future interface.

**Q: You built the LLM abstraction before you had a second provider. Isn't that
premature?**

It's a fair challenge, and I'd defend it on two grounds. First, I had a *specific* named
future requirement, not vague flexibility: local models on my RTX 4080 are on the roadmap,
and the free tier's privacy terms conflict with the project's own privacy principle.
Second, it paid off within the hour, twice. `gemini-2.5-flash` turned out to be retired for
new API keys — one `.env` line. Later `gemini-3.5-flash` returned 503 on every request while
`flash-lite` worked fine — one `.env` line. Retrofitting the abstraction after prompts,
history, intent parsing, and usage logging were tangled into direct API calls would have
been far more work than forty lines up front.

**Q: What would you change if you had ten users instead of one?**

Three things, in order. First, the blocking I/O: `handle_message` does synchronous database
and HTTP calls from an async handler, which blocks the event loop. Invisible at one user, a
hard throughput ceiling with concurrency. Second, the two-LLM-calls-per-message pattern
would need to become one. Third, I'd need a `users` table — right now the same Telegram ID
is duplicated as a string in two tables with no referential integrity, and I'm conflating
user ID with chat ID, which coincide in DMs but not in groups.

## Database

**Q: Why did adding the `role` column fail, and what did that teach you?**

The migration tried `ALTER TABLE messages ADD COLUMN role VARCHAR NOT NULL` against a table
with eleven rows. Those rows had nothing to put in the new column, so Postgres rejected it
with `NotNullViolation`.

The subtlety is that my model *did* declare `default="user"` — but that's a **Python-side**
default. SQLAlchemy applies it when I construct an object; it never becomes part of the
table definition. What existing rows needed was `server_default`, which Postgres applies
during the ALTER. Alembic's autogenerate doesn't translate one into the other — which is
why its own generated comment says `please adjust!`.

Two related things I noticed: the failure rolled back completely, because migrations run in
a transaction. And this is exactly why I now read every generated migration before applying
it.

**Q: How did you choose your indexes?**

From the queries, not by instinct. History retrieval filters on `sender` and sorts by
`created_at`, so both are indexed. The scheduler runs
`WHERE due_at <= now AND sent = false` **every sixty seconds indefinitely** — that's the one
that really matters, because without those indexes it's a full table scan on every tick,
degrading as the table grows. I deliberately didn't index everything; each index costs write
performance and disk.

**Q: Why no foreign keys?**

Single user, no `users` table to reference. Adding one would be speculative structure
serving no current need. I'm aware of the cost: no referential integrity between
`messages.sender` and `reminders.recipient`, and the same identifier duplicated as a string.
If I went multi-user, a `users` table is the first migration — and it would also fix the
user-ID-versus-chat-ID conflation.

## Security

**Q: What's the most important security decision in this project?**

That the LLM never acts. It returns JSON that must validate against a closed set of
pydantic schemas tagged with `Literal` action names, and *every* failure path — bad JSON,
unknown action, failed validation, API error — returns `ChatIntent`. So the worst outcome of
a confused or manipulated model is a conversation.

Right now that looks like over-engineering, because the only person sending messages is me.
It stops looking that way at Phase 6, when Jarvis reads my Gmail — because an email is
untrusted text written by strangers. If one says "ignore previous instructions and delete
everything," that has to be, at worst, a malformed request my code rejects. Not a command
it executes.

**Q: Tell me about a vulnerability you found in your own project.**

Two. The token leak through logs I mentioned. The other was Postgres published on
`0.0.0.0:5432` — the public internet — while the password was still the literal placeholder
`change_this_to_something`. Either alone is survivable; together it means anyone scanning my
IP could try obvious credentials. And I had evidence they were scanning: my API logs showed
404s from unknown IPs probing exploit paths.

The fix cost nothing functionally, which is the interesting part. The API reaches Postgres
at `db:5432` over the private Docker network — it never used the published port. That port
existed purely so *I* could attach an external tool, which I wasn't doing. So I deleted the
mapping and changed the password.

**Q: Why does the bot ignore unauthorized users instead of telling them?**

A denial message confirms the bot exists, is running, and has something worth attacking.
Silence gives a stranger nothing — they can't distinguish rejection from a dead bot. I log
denials at WARNING rather than INFO, because a rejected access attempt is a security event
that should stand out from routine traffic.

## Performance

**Q: What's your biggest performance problem?**

Two LLM calls per message — one to classify intent, one to reply. On a free tier with daily
request caps, that halves my effective budget, and it roughly doubles latency. The fix is
either a single call using structured-output or tool-calling APIs, or classifying with a
cheaper model, which the abstraction makes a one-line change.

Architecturally though, the more serious one is that `handle_message` does blocking database
and HTTP I/O inside an async handler. That stalls the event loop. Completely invisible with
one user; a hard ceiling with concurrency.

**Q: Anything you deliberately left unoptimised?**

Yes, and I'd defend it. `get_llm()` constructs a new client on every message rather than
caching it. Wasteful, trivially fixable, and completely irrelevant at single-user volume. I
also chose log lines over a usage table for cost tracking — greppable is enough; a table is
another migration and more moving parts for data I mostly glance at. Knowing which
complexity to defer is as useful as knowing which to add.

## Testing

**Q: How well tested is this?**

Poorly, and I can tell you exactly why that's a problem. Two tests, both against `/health`.
Nothing tests intent parsing, time parsing, the auth decorator, history ordering, or
reminder delivery — and **five of those broke at least once during development**. Every one
was caught manually by sending a Telegram message and reading logs, which is immediate and
satisfying and is precisely the trap.

**Q: What would you test first?**

`parse_when`, because it's a pure function with a known bug class — table-driven cases for
each working format, the "next" failures, past times, garbage. Then `parse_intent` with a
fake `LLMProvider` returning canned responses: valid JSON, fenced JSON, malformed JSON, an
unknown action, an over-length task. Assert every path yields `ChatIntent`. That's
deterministic, free, and tests the security boundary. It's also the abstraction's second
payoff — the ABC makes the fake trivial.

## Debugging

**Q: Describe a bug where the symptom misled you.**

Reminders seemed to fire almost immediately instead of after two minutes. I assumed the time
parsing was broken. Then I queried the table and compared `created_at` to `due_at` — exactly
two minutes apart, every time. The scheduler ticks on a fixed 60-second interval independent
of when reminders are created, so delivery lands anywhere from 0 to 60 seconds after due.
Combined with the fact that I was watching the logs expecting it, two minutes just didn't
feel like waiting. Nothing was wrong. The lesson: check the data before assuming a bug.

**Q: How do you tell your bug from someone else's outage?**

Isolate the failing piece and run it alone. When my chat replies started failing I ran the
LLM call directly — three lines, touching nothing I'd edited that day. It failed identically
with a 503 saying "experiencing high demand," which settled it. Then the status code tells
you the category: 5xx is their servers, 4xx is my request or my quota, and a `TypeError` or
`NameError` is my code. Switching to `flash-lite` fixed it, which also told me availability
varies per model, not per account.

## "Why X instead of Y?"

**Q: Why long-polling instead of webhooks?**

Webhooks need a public HTTPS endpoint, an open port, TLS certificates, and a stable
address. Long-polling means every connection is outbound, so the bot container publishes
**no ports at all** — and the identical setup works behind my home NAT and on a public VPS.
The trade-off is a persistent outbound connection and slightly higher latency, plus it
doesn't scale to multiple instances. For a single-user assistant that's clearly the right
side of the trade. What I like about it is that the architecture *eliminated* a security
requirement rather than satisfying one.

**Q: Why SQLAlchemy instead of raw SQL?**

For application code, three reasons: it prevents SQL injection automatically, it's far less
error-prone than assembling strings for the reads and writes that happen on every message,
and it pairs with Alembic so my schema is versioned code that rebuilds identically on any
machine. I still use raw SQL constantly for *inspection* and debugging — `\d`, `SELECT`,
`GROUP BY`. Different tools for different jobs, and understanding the SQL underneath is what
lets me debug the ORM.

**Q: Why Gemini instead of Anthropic or OpenAI?**

Honestly: the free tier removed cost as a barrier while learning. I made the trade-off
explicitly though — Google may use free-tier prompts to improve their models, which
conflicts with my own stated privacy principle. That's acceptable while I'm sending test
messages, and it stops being acceptable before Phase 6 when Jarvis reads my email. The whole
point of the abstraction is that moving to a paid tier, Anthropic, or a local model is a
config change.

**Q: Why polling the database instead of scheduling a job per reminder?**

Because scheduled jobs live in memory. A container restart would discard every pending
reminder, and the failure would be *silent* — reminders just stop arriving, no error
anywhere. Polling makes the database the source of truth, so a restart loses nothing.
`due_at <= now` rather than `== now` means anything missed during downtime fires on the next
tick. And I only set `sent = true` after a successful send, so if Telegram is down it
retries. The cost is up to 60 seconds of imprecision and a query every minute forever, which
is nothing compared to silently losing reminders.

## Senior-level

**Q: Where would this design break first, and how would you know?**

Concurrency, and I'd know from latency rather than errors. `handle_message` does blocking
database and HTTP I/O inside an async handler, so a second user's message waits for the
first's LLM call. Nothing errors — it just gets slow, which is the hard kind of failure to
notice. Second break: two bot instances would both poll Telegram *and* both run the
scheduler, and because I check and set `sent` in separate transactions there's a race
window where a reminder could double-send. I'd need `SELECT ... FOR UPDATE SKIP LOCKED` or
a real queue.

**Q: Critique your own abstraction.**

The `LLMProvider` interface is shaped by what Gemini does. It exposes
`complete(prompt, system, history, label)` — a single-shot text completion. That's fine for
Gemini and Anthropic, but it doesn't model streaming, native tool-calling, or multimodal
input. If I wanted native function-calling — which is arguably the *right* way to do intent
extraction and would halve my API calls — I'd have to widen the interface, and the
abstraction would start leaking.

I'd also note it's a nominal interface via inheritance where `typing.Protocol` would be
structural and arguably better, since a fake provider for tests wouldn't need to inherit
anything.

**Q: You have a validation boundary for LLM output but no confirmation step for actions.
Why is that a gap?**

Because my own project brief requires confirmation for destructive operations, and I haven't
built the mechanism. It's not currently exploitable — `create_reminder` is additive, and the
worst a successful prompt injection achieves today is an unwanted reminder row. But the
mechanism needs to exist *before* the first destructive tool, not after. Once Jarvis can
delete an email or modify a calendar event, retrofitting confirmation means touching every
tool path. The right time to build it is while there's exactly one tool to fit it around.

**Q: What's the weakest part of this project?**

Test coverage, and I'd rank it as the top priority alongside backups. Two tests on a health
endpoint while the intent validator, the time parser, and the scheduler are untested — and
five of the seven untested areas have already broken once. Every one was caught by hand.
That works at this scale and stops working the moment I refactor something.

The reason it happened is instructive: manual testing through Telegram was immediate and
felt like progress, so writing tests always looked like the lower-value option. That's a
discipline failure, not a knowledge one.

---

# 26. Final Reflection

## What programming skills this taught

Python beyond syntax: decorators as a tool for cross-cutting concerns, context managers for
resource lifecycles, abstract base classes as enforced contracts, the async model and its
constraints, and type hints as documentation that tooling can act on. Also the habit of
reading a traceback bottom-up and treating error *categories* as diagnostic information.

## What software engineering skills this taught

The one that mattered most: **dependency direction as a design tool.** Twice, a session
producing no user-visible change made the following feature nearly trivial — the
service-layer refactor, then the provider abstraction. That's not a coincidence to note
once; it's the central lesson.

Alongside it: recognising duplication as a *design* signal rather than a style preference;
deferring complexity deliberately and being able to say why; documenting *why* rather than
*what*; and knowing when not to use a powerful tool.

## What architecture concepts this taught

Layering with unidirectional dependencies. Trust boundaries, and the idea that validation
converts untrusted input into data you can then use without defensive checking. Fail-safe
versus fail-open, and designing so every failure path converges on the least-privileged
outcome. Choosing durable state over in-memory state by asking "what happens when this
restarts?" *before* picking a mechanism. And that the right architecture can eliminate a
requirement — long-polling didn't secure an open port, it removed the need for one.

## What debugging skills this taught

A reflex order (`ps` → `logs` → `grep` → isolate) and, more importantly, the ability to
distinguish categories of failure: my code, my request, my quota, their servers, my data.
Several bugs had actively misleading symptoms — a crash that appeared as silence, a vendor
outage that looked like a code bug, correct timing that felt wrong, and a data artifact that
looked like model confusion. Learning to *check the data before assuming a bug* came
directly from one of those.

## What mistakes taught the most

The **token leak through logs** is the most valuable, because the code was correct. Secrets
escape through observability tooling, and that's not a category most people consider until
it happens.

The **exposed Postgres with a placeholder password** taught that the same configuration
means different things on different networks, and that placeholder credentials are a
vulnerability rather than a TODO.

The **`NotNullViolation`** taught that generated code is a draft — Alembic literally writes
`please adjust!` — and the `default=`/`server_default=` distinction.

The **`DetachedInstanceError`** taught that a convenience wrapper can create a subtle
failure while removing an obvious one, and that understanding *why* commit expires
attributes beats memorising a rule.

The **hand-created table** taught that letting a tool own the schema isn't bureaucracy —
hand edits produce migrations that fail elsewhere.

## What advanced concepts were encountered

Schema-constrained LLM output as a security mechanism. Prompt injection as a threat model.
ORM session identity and expiry semantics. Async event loop lifecycle. Timezone-correct
datetime handling. Transactional DDL. Layer-cache-aware image builds. At-least-once
delivery via a state flag. Dependency inversion.

## What I understand now that I didn't before

That an LLM's output is untrusted input. That containers are disposable and state needs
explicit provision. That the schema is code. That the same config file is safe on one
machine and dangerous on another. That "installed" and "running" are different states. That
port publication is a security decision. That error handling only protects the code it
wraps. That refactoring is leverage rather than tidying. And that most bugs live at
boundaries between components, not inside them.

## What to learn next

In rough priority order:

1. **Testing properly** — test doubles, fixtures, a transactional test database. It's the
   biggest gap, and the provider abstraction already makes fakes easy.
2. **Backups and operational discipline** — `pg_dump`, off-machine storage, and a *tested*
   restore, before personal data arrives.
3. **Async Python properly** — enough to recognise event-loop blocking, then async
   SQLAlchemy.
4. **Native tool-calling APIs** — likely halves the API calls and is the standard approach
   to what `intent_parser.py` does by hand.
5. **CI/CD** — GitHub Actions running pytest and ruff on every push.
6. **pgvector and embeddings** — Phase 10, and the natural next conceptual step.
7. **Linting and type checking** — `ruff` and `mypy`, cheap and disproportionately useful.

## What to be able to explain confidently in an interview

Four things, all defensible in depth:

**The trust boundary.** Why the LLM returns validated intents instead of acting, why
`Literal` closes the action set, why every failure path returns `ChatIntent`, and why this
matters more once the assistant reads email.

**The layered refactor and its payoff.** Why the service layer knows nothing about
Telegram, and the concrete evidence that it worked.

**The scheduler design.** Why polling beats per-reminder jobs, what `due_at <= now` buys,
and why `sent` is set only after a successful send.

**The two security incidents.** What happened, why the code wasn't at fault in one case,
and why one fix cost nothing functionally. Finding and fixing real vulnerabilities in your
own work, then documenting them, is a stronger signal than never having had any.

---

# 27. Coverage Report

## Method

This document was **reconstructed from the guided build sessions** in which every
application file was written, plus captured terminal output, error messages, migration
files, and database query results. It is **not** the result of a repository scan.

## What I could not inspect — stated plainly

| Not inspected | Consequence |
|---|---|
| The live repository filesystem | No verification of current file contents or line numbers |
| Full `git log`, branches, tags | §9 is limited to what was observed during sessions |
| `.github/` directory | Believed absent; not confirmed |
| Installed dependency versions (`pip freeze`) | Only the unpinned names in `requirements.txt` are known |
| `alembic.ini` full contents | Only the URL-override behaviour is known |
| `tests/__init__.py`, `alembic/script.py.mako` | Assumed default/empty |
| Any edits made outside the build sessions | Would not be reflected here |
| Actual Gemini quota consumption | Only the log-based counting method is documented |

## Files documented

**Application code (16):** `app/__init__.py`, `main.py`, `config.py`, `database.py`,
`models.py`, `logging_config.py`, `auth.py`, `bot.py`, `services.py`, `intents.py`,
`intent_parser.py`, `timeparse.py`, `scheduler.py`, `llm/__init__.py`, `llm/base.py`,
`llm/gemini.py`

**Migrations (3) + config (2):** all three version files, `alembic/env.py` (modifications),
`alembic.ini` (partial)

**Tests (2):** `tests/__init__.py`, `tests/test_health.py`

**Infrastructure (5):** `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitignore`,
`requirements.txt`

**Configuration (2):** `.env` (structure only — **no secret values reproduced**),
`.env.example`

**Documentation (2):** `README.md`, `COMMANDS.md`

**Learning artifacts (2):** `docker-practice/hello.py`, `docker-practice/Dockerfile`

**Total: ~34 files.** No meaningful file known to exist was skipped.

## Prompt sections addressed

| Requested | Status |
|---|---|
| Repository overview, tech stack | Complete |
| File-by-file documentation | Complete for all known files |
| Code explanation and control flow | Complete |
| Architecture deep dive | Complete |
| Database architecture | Complete |
| Dependency analysis | Complete |
| Configuration analysis | Complete |
| Git/GitHub analysis | **Partial** — history not accessible |
| Testing documentation | Complete, including honest gaps |
| Security analysis | Complete, with severity classification |
| Performance analysis | Complete |
| Code quality analysis | Complete |
| "What I learned" per component | Complete |
| Learning map | Complete |
| Skills demonstrated | Complete, with explicit non-claims |
| Complexity analysis | Complete |
| Design decisions | Complete (9 decisions) |
| Improvements | Complete (17, prioritised) |
| Bugs | Complete (8 confirmed + 5 non-bugs) |
| Code patterns | Complete |
| Concepts explained three ways | Complete (7 concepts) |
| How everything connects | Complete |
| Glossary | Complete |
| Learning timeline | Complete (session-based, labelled) |
| Interview questions | Complete (~28 with answers) |
| Final reflection | Complete |
| Frontend flow | **N/A** — no frontend exists |
| CI/CD documentation | **N/A** — none exists (flagged as a gap) |

## Major technologies identified

Python 3.12, FastAPI, uvicorn, SQLAlchemy 2.x, Alembic, PostgreSQL 16, pydantic,
pydantic-settings, python-telegram-bot, google-genai (Gemini), APScheduler, dateparser,
pytest, httpx, psycopg2-binary, Docker, Docker Compose, Ubuntu Server, Git.

## Major architectural components identified

Transport layer (Telegram + HTTP), authorization decorator, service layer, LLM provider
abstraction with factory, intent validation boundary, time parsing, data layer with
migrations, and a polling scheduler.

## Where more information would help

1. **Verify every file against the current repository** — the highest-value next step
2. Actual `git log` output, to confirm the timeline and commit boundaries
3. Installed dependency versions, so the pinning recommendation can be concrete
4. Whether `docker-practice/` and the `LICENSE` situation are as described
5. Whether any linting or CI configuration has since been added

## Honest overall assessment

The **architecture, design reasoning, bug history, and learning progression** in this
document are first-hand and reliable — they were observed as they happened, which is
context a repository scan could not recover. The **exact current state of the code** is not
verified. Read this as an accurate account of how the project was built and why, then check
the specifics against your repository before relying on them.