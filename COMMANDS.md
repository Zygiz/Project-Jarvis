# Jarvis — Command Reference

My own cheat sheet of the useful, project-specific commands. Filled in with real
values (repo, db user, ports) so they're copy-paste ready.

Key values:
- Repo folder: `Project-Jarvis`
- DB user / DB name: `jarvis` / `jarvis`
- Ports: API `8000` (loopback only), Postgres `5432` (internal only), SSH-to-VM `2222`
- Services: `api`, `bot`, `db`
- My Telegram user ID: `8524921379`
- LLM: Gemini free tier, model `gemini-3.5-flash-lite`
- Timezone: `Europe/Vilnius` (UTC+3 summer) — stored as UTC, displayed local

---

## How a message flows (the whole system in one place)

```
Telegram
  → bot.py                      receives the update
  → @require_auth (auth.py)     allowlist check, silence if not allowed
  → handle_message (services.py)
        ├─ get_recent_history()   last 10 messages for this sender
        ├─ save_message(role="user")
        ├─ parse_intent()         → LLM call #1 (label=intent), VALIDATED Intent
        │     ├─ CreateReminderIntent → create_reminder() → parse_when() → DB
        │     └─ ChatIntent           → LLM call #2 (label=chat) with history
        └─ save_message(role="assistant")
  → reply returned to bot.py → sent back to Telegram

Separately, every 60s:
  scheduler.py send_due_reminders()
        → SELECT reminders WHERE due_at <= now AND sent = false
        → send via Telegram → mark sent = true
```

`services.py` knows nothing about Telegram — it takes strings and returns a string.
That boundary lets a web UI or voice interface reuse the same logic later.

---

## Usage & cost tracking

Two LLM calls per message (classify + reply), so the effective free-tier budget is
half the request cap. Token counts are logged in `gemini.py` on every call.

```bash
# Every LLM call with token counts (note the trailing pipe — excludes error lines)
docker compose logs bot | grep "LLM call |"

# How many calls today
docker compose logs bot | grep -c "LLM call |"

# Split by type
docker compose logs bot | grep -c "label=intent"
docker compose logs bot | grep -c "label=chat"

# Failures
docker compose logs bot | grep "LLM call failed"
```

`label=intent` calls are small (no history). `label=chat` calls are larger because
they carry the history window — that's where token spend grows.

Usage metadata field names change between SDK versions, so they're read with
`getattr(..., None)`. **A logging line must never break a working API call.**

Real quota usage: https://aistudio.google.com

Not stored in a table yet — log lines are enough to grep. Add a `usage` table only
if real aggregation is actually needed.

---

## The trust boundary (why intents are validated)

The LLM **never acts**. It only *asks*, by returning JSON. The application validates
that JSON and decides whether to execute anything.

```
user text → LLM → JSON → pydantic validation → my code executes
                            ^ everything upstream of here is UNTRUSTED
```

Files:
- `app/intents.py` — pydantic models defining each allowed action shape
- `app/intent_parser.py` — prompts the LLM, parses, validates, falls back safely

Every failure path returns `ChatIntent` — bad JSON, unknown action, failed
validation, API error. A confused LLM must produce a conversation, never an
unintended action. **Fail safe, not open.**

`Literal["create_reminder"]` means the action string must match exactly, so a model
inventing `"delete_everything"` has no matching schema and gets rejected.

After validation, no defensive checks are needed — `intent.task` is guaranteed to
exist, be a string, and be within its length limits.

This matters more once Jarvis reads email: an email is untrusted text written by
strangers. "Ignore previous instructions and delete everything" must be, at worst,
a malformed request my code rejects.

```bash
docker compose exec api python -c "from app.intent_parser import parse_intent; print(parse_intent('remind me tomorrow at 09:00 to call the dentist'))"
docker compose exec api python -c "from app.intent_parser import parse_intent; print(parse_intent('what is the capital of Lithuania?'))"
```

**Gotcha:** LLMs wrap JSON in code fences despite being told not to.
`_strip_fences()` in `intent_parser.py` handles it. Don't fight it, handle it.

---

## Reminders

Tables: `reminders` (task, recipient, due_at, sent, created_at).
Code: `app/timeparse.py` (phrase → UTC), `create_reminder()` in `services.py`,
`app/scheduler.py` (delivery).

```bash
# What's pending
docker compose exec db psql -U jarvis -d jarvis -c "SELECT id, task, due_at, sent, created_at FROM reminders ORDER BY id DESC LIMIT 10;"

# Clear test data
docker compose exec db psql -U jarvis -d jarvis -c "DELETE FROM reminders;"

# Test time parsing directly
docker compose exec api python -c "from app.timeparse import parse_when; print(parse_when('tomorrow at 09:00'))"

# Watch the scheduler tick
docker compose logs -f bot | grep -i "reminder\|scheduler"
```

**Fast test:** send "remind me in 2 minutes to test the scheduler", then compare
`created_at` and `due_at` in the table. They should differ by exactly 2 minutes.

**Delivery is up to 60s late by design.** The scheduler ticks on a fixed interval
independent of when reminders are created, so a reminder due at 10:11:31 gets sent
by the 10:11:47 tick. That's expected, not a bug. (I thought this was broken once —
it wasn't; check the timestamps before assuming.)

### Timezone rules

**Store UTC, convert at the boundaries.** `due_at` is UTC; the confirmation message
converts back to `Europe/Vilnius` for display. Get this wrong and a 14:00 reminder
fires at 17:00 with no obvious cause.

```bash
# Sanity check: 09:00 Vilnius should come back as 06:00 UTC
docker compose exec api python -c "from app.timeparse import parse_when; print(parse_when('tomorrow at 09:00'))"
```

### dateparser quirks

Works: `tomorrow`, `tomorrow at 09:00`, `Friday 14:00`, `in 2 hours`, `25 December 10:00`
**Fails: anything with the word "next"** — `next Friday` and `next Friday at 14:00`
both return None.

Defended in two places:
1. `INTENT_PROMPT` tells the LLM not to use "next"
2. `parse_when()` strips a leading "next " before parsing

Safe to strip because `PREFER_DATES_FROM: "future"` already resolves bare "Friday"
to the upcoming one.

If parsing fails, `create_reminder()` tells the user and suggests a working format.
A reminder you *think* is set but isn't is worse than a clear rejection.

**Lesson:** probe a library's actual behaviour with a few quick tests instead of
assuming it handles everything. Four commands found the exact boundary.

### Why the scheduler polls instead of scheduling each reminder

One precise job per reminder would live in memory and vanish on container restart —
reminders would silently stop firing. Instead a job runs every minute and queries
the database. **The database is the source of truth, not the scheduler's memory.**

- `due_at <= now` (not `==`) means anything missed while the container was down
  fires on the next tick. Late beats never.
- `sent` is only set to true *after* a successful send. If Telegram is down, the
  reminder retries next tick rather than being lost.
- Values are read out of ORM objects into plain tuples inside the session, because
  sending takes time and the objects go stale (see the session section below).

**Gotcha — `RuntimeError: no running event loop`:** `AsyncIOScheduler` needs a
running event loop, which does not exist inside the synchronous `main()`. Start it
from a `post_init` hook instead:

```python
application = Application.builder().token(...).post_init(_start_scheduler).build()
```

General rule: anything asyncio-based must be created INSIDE a running event loop,
not before it. Same shape of fix for async DB connections or HTTP clients.

---

## LLM provider

Config in `.env`: `LLM_PROVIDER`, `LLM_MODEL`, `GEMINI_API_KEY`.
Code in `app/llm/`:
- `base.py` — the abstract contract (`complete(prompt, system, history, label)`)
- `gemini.py` — Gemini impl; the ONLY file importing `google.genai`
- `__init__.py` — `get_llm()` factory, maps the config string to a class

Adding another provider (Anthropic, Ollama) = one new file + three lines in the
factory. Nothing else changes.

**Role names:** the interface uses `"user"` / `"assistant"`. Gemini calls the AI's
turn `"model"`, so `gemini.py` has `_ROLE_MAP` to translate. Provider quirks stay
inside the provider.

```bash
docker compose exec api python -c "from app.llm import get_llm; print(get_llm().complete('hi'))"

# List models my key can see
docker compose exec api python -c "from google import genai; from app.config import settings; c = genai.Client(api_key=settings.gemini_api_key); [print(m.name) for m in c.models.list()]"
```

### Diagnosing "is it my code or theirs?"

Run the direct call above. It touches almost nothing, so:
- **It fails too** → not my code. Server side or config.
- **It works** → something in the chat/intent path specifically is broken.

Status codes tell you which:
- **5xx** (503 UNAVAILABLE "experiencing high demand") → their servers. Not my bug.
  Switch models or wait.
- **4xx** (404 NOT_FOUND, 429 RESOURCE_EXHAUSTED) → my request or my quota.
- `TypeError` / `NameError` → my code.

Happened once: `gemini-3.5-flash` returned 503 for every call while
`gemini-3.5-flash-lite` worked fine. **Model availability varies per model** —
switching is a one-line `.env` change. That's what the abstraction is for.

Fallback models my key can use: `gemini-3.5-flash-lite`, `gemini-3.6-flash`,
`gemini-3.1-flash-lite`, `gemini-2.0-flash`.

**Gotcha:** assign the client to a variable (`c = genai.Client(...)`) before
iterating `models.list()`. Inline, Python garbage-collects it mid-pagination:
`RuntimeError: Cannot send a request, as the client has been closed`.

**Gotcha:** `models.list()` shows models the key can SEE, not ones it can CALL.
`gemini-2.5-flash` was listed but returned 404 "no longer available to new users".
Trust the actual call, not the list.

**Gotcha:** after changing `.env`, use `docker compose up -d` — plain `restart` can
keep the old environment values.

Avoid `-latest` aliases — the model changes under you without warning. Pin a version.
Use Flash tier; Pro free quotas are too small to build on.

Harmless stderr noise: `Direct use of automatic function calling (AFC) in
Models.generate_content is not recommended` — the SDK nudging toward its `Chat` API
for multi-turn. Worth exploring later; not an error.

Free-tier privacy note: Google may use free-tier prompts/responses to improve their
models. Fine for testing; revisit before Jarvis touches email or personal memory.
Options then: paid tier, Vertex AI, or local models via Ollama (Phase 13).

---

## Conversation history

`get_recent_history(sender)` returns the last `HISTORY_LIMIT` (10) messages for that
sender, oldest first. Both sides are stored — `role` is `"user"` or `"assistant"`.

Bounded because unbounded history blows past context limits, costs more on every
call, and adds noise. Semantic memory (Phase 10) is the proper answer for old
context; this is just the recent window.

10 messages ≈ 5 exchanges, since both sides count. Raising `HISTORY_LIMIT` costs
tokens on every call — visible in the `label=chat` token counts.

History is fetched BEFORE saving the new message, or the current message appears
twice. The assistant reply is only saved if the LLM call succeeded, so failures
don't fill history with error text.

**Gotcha:** after the migration that added `role`, all existing rows were backfilled
to `"user"`. The window then looked like ten unanswered questions and the model tried
to address them all. Cleared the table and it was fine.

---

## New machine setup (do this FIRST)

```bash
# 1. Git identity — use the SAME email as the GitHub account
git config --global user.name "Zygiz"
git config --global user.email "zygimantas.mikaila@gmail.com"
git config --global user.email          # verify

# 2. SSH key for GitHub (press Enter 3x for defaults)
ssh-keygen -t ed25519 -C "zygimantas.mikaila@gmail.com"
cat ~/.ssh/id_ed25519.pub              # paste into GitHub > Settings > SSH keys
ssh -T git@github.com                  # success = "Hi Zygiz!" greeting

# 3. Clone
git clone git@github.com:Zygiz/Project-Jarvis.git
cd Project-Jarvis

# 4. .env does NOT come from git — recreate it
cp .env.example .env
nano .env      # DB password, bot token, allowlist, Gemini key, timezone

# 5. Start + build the database tables
docker compose up -d
docker compose exec api alembic upgrade head

# 6. Confirm it works
docker compose exec api pytest
curl localhost:8000/health
docker compose exec api python -c "from app.llm import get_llm; print(get_llm().complete('hi'))"
```

Skipping the git identity is why my early VPS commits show as "root" instead of me.

---

## Secret hygiene — read this before pasting anything anywhere

**Never paste raw logs into chat, GitHub issues, or forums without scanning them
for secrets first.**

Learned the hard way: `httpx` logs full request URLs, and Telegram puts the bot
token **inside the URL**. So the app's own logs contained the token in plaintext,
and I pasted it into a chat. Had to revoke and reissue.

Fix already applied in `app/logging_config.py`:

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Application").setLevel(logging.WARNING)
```

Things that leak: bot tokens, API keys, DB passwords, `.env` contents, URLs with
credentials. Logs also contain my own Telegram user ID.

Truncate logged LLM output (`raw[:200]`) so a runaway response can't flood the logs.

Check `.env.example` before committing — every secret value must be blank. Non-secret
defaults like `LLM_MODEL` and `TIMEZONE` are fine and useful as documentation.

---

## Telegram bot

Bot management happens in Telegram, talking to **@BotFather**:

```
/newbot      create a new bot (display name, then a username ending in "bot")
/mybots      list my bots, edit settings
/token       show the current token
/revoke      KILL the current token and issue a new one — do this if it ever leaks
/setcommands set the command list shown in the Telegram UI
```

After revoking: update `TELEGRAM_BOT_TOKEN` in `.env`, then `docker compose up -d`.

`/setcommands` format (no leading slash, ` - ` separator):

```
start - Check Jarvis is alive
help - Show available commands
```

The `/` popup menu is a Telegram CLIENT feature — commands work regardless, but the
menu only appears after `/setcommands`, and the client caches it (may need an app
restart).

```bash
docker compose logs -f bot         # watch it live (Ctrl+C to stop following)
docker compose restart bot         # restart after code changes
docker compose up -d --build       # rebuild after requirements.txt changes
```

**Long-polling, not webhooks.** The bot asks Telegram for new messages in a loop —
all connections go OUTWARD. So: no open ports, no public HTTPS, works identically
on the home VM (behind NAT) and the VPS. That's why the `bot` service has no
`ports:` at all.

Find my Telegram user ID: message the bot and read `Message received | user_id=...`

**`telegram.error.NetworkError: Bad Gateway`** = Telegram's servers hiccuping, not
my code. The library retries and recovers. Ignore it.

---

## Auth / allowlist

Only user IDs in `TELEGRAM_ALLOWED_USER_IDS` (comma-separated in `.env`) can use the
bot. Unauthorized users get **complete silence** — no "access denied", because that
confirms the bot exists and is worth attacking.

Enforced by the `@require_auth` decorator in `app/auth.py`, applied to every handler.
Written once so it can't be forgotten on a new handler.

```bash
docker compose logs bot | grep -i unauthorized
```

Startup log confirms it parsed: `Jarvis bot starting up | allowed_users=1`

**Testing the block without a second Telegram account:**

```bash
# 1. temporarily set a wrong ID in .env
TELEGRAM_ALLOWED_USER_IDS=1
docker compose up -d
# 2. message the bot — expect SILENCE + a WARNING in the logs
# 3. set it back and bring it up again
```

An auth check I've never seen actually deny something is one I'm only assuming works.

---

## Connecting to the machines

```bash
ssh vboxuser@localhost -p 2222     # dev VM (from Windows, VM must be running)
ssh root@<vps-ip>                  # Hostinger VPS
exit                               # leave any SSH session

# Copy a file from Windows INTO the VM (run in Windows PowerShell)
scp -P 2222 "C:\path\to\file" vboxuser@localhost:~/Project-Jarvis/
```

**VS Code Remote-SSH:** F1 → "Remote-SSH: Connect to Host" → pick host → then
File > Open Folder → `/root/Project-Jarvis` (VPS) or `/home/vboxuser/Project-Jarvis` (VM).
Green "SSH: ..." badge bottom-left = connected. Terminal inside VS Code: Ctrl+backtick

**Use VS Code for editing code, not terminal heredocs.** Pasting multi-line Python
into a terminal broke files three times in one session: wiped imports, mangled
indentation, dropped docstring quotes. VS Code preserves indentation and flags
syntax errors as you type.

---

## The Git loop (run constantly)

```bash
git status                 # what changed? (ALWAYS run this first)
git add .                  # stage all changes
git commit -m "message"    # save a snapshot
git push                   # send to GitHub
git pull                   # get changes (do this when switching machines)
git log --oneline          # compact history
git diff                   # what changed since last commit
git tag -a v0.1 -m "..." && git push --tags    # mark a milestone release
```

Switching between VM and VPS: **push before you stop, pull before you start.**

Before every commit: check `git status` does NOT list `.env` — it holds the DB
password, bot token, Gemini API key, and my user ID.

Commit messages: verb first, present tense, describe WHAT changed.
Good: `Add reminder tool with APScheduler delivery`
Bad: `update`, `fix bug`, `changes`

Prefer several small commits over one big one — separate a feature from its docs so
history reads cleanly and one change can be reverted without the other.

---

## Docker Compose — running Jarvis

Three services: `api` (FastAPI), `bot` (Telegram + scheduler), `db` (Postgres).
`api` and `bot` share the same image — only the startup command differs.

```bash
docker compose up -d           # start all in background
docker compose up -d --build   # rebuild first (after requirements.txt changes)
docker compose restart api     # restart one service (api / bot / db)
docker compose down            # stop AND remove containers (volume/data survives)
docker compose ps              # status
```

**Gotcha — code changes not applying:** `restart` sometimes doesn't pick up edited
files. First verify the file actually saved, then force a recreate:

```bash
grep -n "SYSTEM_PROMPT" app/services.py
docker compose down && docker compose up -d
```

**Gotcha:** for `.env` changes, `restart` is not enough — use `up -d`.

**Crash loop:** with `restart: unless-stopped`, a broken service restarts every few
seconds and floods the logs with the same traceback. Ctrl+C out of the follow, read
ONE traceback, fix, restart.

**Check syntax before restarting** — much faster than waiting for a crash loop:

```bash
docker compose exec api python -c "import app.services; print('ok')"
docker compose exec api python -c "import app.bot; print('ok')"
```

**Verify an edit actually landed** before rebuilding:

```bash
grep -n "label" app/llm/gemini.py app/llm/base.py app/services.py app/intent_parser.py
```

Multi-file changes are easy to half-finish — this catches it in one command.

**DANGER — wipes the database:**

```bash
docker compose down -v         # -v ALSO DELETES THE VOLUME = all data gone
```

Only for deliberate resets (e.g. changing POSTGRES_PASSWORD, which Postgres only
reads when initialising a fresh volume). Afterwards re-run
`docker compose exec api alembic upgrade head`.

---

## Running tests (pytest)

```bash
docker compose exec api pytest              # run everything
docker compose exec api pytest -v           # one line per test name
docker compose exec api pytest -k health    # only tests matching "health"
docker compose exec api pytest -x           # stop at first failure
```

Each `.` is a passing test. `F` marks a failure, with expected-vs-actual printed.

pytest discovers tests by naming — no registration:
- files named `test_*.py`
- functions named `test_*`

```
tests/
  __init__.py        (empty — marks it as a package)
  test_health.py
```

**Gotcha:** I once created `tests/tests/tests/` by making a folder while already
inside one. Check with `find tests -type f`.

---

## Database migrations (Alembic)

Run INSIDE the api container — that's where the hostname `db` resolves.

```bash
docker compose exec api alembic revision --autogenerate -m "describe the change"
cat alembic/versions/*.py      # READ IT before applying
docker compose exec api alembic upgrade head
docker compose exec api alembic current
docker compose exec api alembic history
docker compose exec api alembic downgrade -1
```

**Rule:** never create or alter tables by hand in psql. Alembic diffs the real
database against `models.py` — hand-made changes make it generate wrong migrations
(it produced `alter_column` instead of `create_table` when I did this once).

Chain: `models.py` (blueprint) → `revision --autogenerate` (writes the plan)
→ `upgrade head` (runs the plan) → real table.

**Gotcha — adding a NOT NULL column to a table with existing rows fails:**
`NotNullViolation: column "role" contains null values`. Existing rows need a value,
and autogenerate does NOT add one. Edit the migration to add `server_default`:

```python
op.add_column('messages', sa.Column('role', sa.String(), nullable=False, server_default='user'))
```

- `default=` in models.py → **Python-side**, SQLAlchemy fills it when creating objects
- `server_default=` → **database-side**, Postgres backfills existing rows

A brand-new table doesn't need `server_default` (no rows to backfill) — but it also
means the DB won't fill the column for hand-written INSERTs.

Migrations run in a transaction, so a failed one rolls back cleanly — no half-applied
state. Verify with `\d <table>`.

---

## Logs & debugging (first move when something breaks)

```bash
docker compose logs api
docker compose logs -f bot
docker compose logs --tail 50 api
docker compose logs bot | grep -i "reminder\|error"
docker ps -a                   # include stopped containers
```

Debug order:

1. `docker compose ps` — is it even running?
2. `docker compose logs <service>` — what did it say before dying?
3. `grep` the file — did my change actually save?
4. Test the failing piece in isolation — is it my code or theirs?

Read tracebacks **bottom-up** — the real error is the last line. Check the LINE
NUMBER too: an error on line 1 usually means the imports are missing.

Error types worth telling apart:
- `SyntaxError` / `IndentationError` → the file can't even be parsed; NOTHING in it
  ran. Different category from the ones below, where code ran and then failed.
- `AttributeError: 'Settings' object has no attribute 'x'` → field not declared in
  `config.py` at all
- `ValidationError: field required` → declared but missing from `.env`
- `NameError: name 'X' is not defined` → missing import, or a partial paste wiped
  the imports
- `404 NOT_FOUND` from an LLM call → wrong/retired model in `LLM_MODEL`
- `503 UNAVAILABLE` from an LLM call → THEIR servers. Switch model or wait.
- `429 RESOURCE_EXHAUSTED` → my quota, not my code
- `DetachedInstanceError` → read ORM attributes outside the session
- `NotNullViolation` on migrate → missing `server_default`
- `RuntimeError: no running event loop` → started an asyncio object outside the loop
- `unterminated triple-quoted string` → a docstring quote got lost in a paste
- `invalid character '—' (U+2014)` → prose is being parsed as code, i.e. the
  docstring quotes are missing
- Old behaviour after an edit → container didn't reload; `down && up -d`

**Gotcha:** error handling only protects the code it WRAPS. A crash in
`get_recent_history()` (before the try/except around the LLM call) killed the handler
with no reply — silence, which looks identical to being unauthorized.

**Gotcha:** keep `python -c "..."` on ONE line, or bash tries to run line 2 as a
shell command (`syntax error near unexpected token`).

Logs go to stdout on purpose — that's what `docker compose logs` shows. Never log to
a file inside a container; it vanishes when the container is recreated.

Format: `timestamp | LEVEL | module | message`

---

## SQLAlchemy sessions (the DetachedInstanceError trap)

ORM objects stay bound to the session that loaded them. Reading an attribute can
trigger a lazy reload from the database. `get_session()` calls `commit()` on exit,
which **expires** all loaded attributes, then `close()` detaches them.

So this breaks:

```python
with get_session() as session:
    rows = session.execute(stmt).scalars().all()
return [{"role": r.role} for r in rows]     # DetachedInstanceError
```

**Rule: convert ORM objects to plain data INSIDE the `with` block.**

```python
with get_session() as session:
    rows = session.execute(stmt).scalars().all()
    result = [{"role": r.role} for r in rows]   # inside
return result
```

`get_session()` in `app/database.py` commits on success, rolls back on error, and
always closes. Wrapped once so callers can't forget any of the three.

---

## Talking to the database

Port 5432 is NOT published to the host, so connect through the container.

```bash
docker compose exec db psql -U jarvis -d jarvis
```

Inside psql (prompt `jarvis=#`):

```sql
\dt                 -- list tables
\d messages         -- structure of a table
\l                  -- list databases
\q                  -- quit
```

Useful queries:

```sql
SELECT id, role, text FROM messages ORDER BY created_at DESC LIMIT 10;
SELECT role, COUNT(*) FROM messages GROUP BY role;
SELECT id, task, due_at, sent FROM reminders ORDER BY id DESC LIMIT 10;
SELECT COUNT(*) FROM reminders WHERE sent = false;   -- pending
DELETE FROM messages;
DELETE FROM reminders;
```

`\dt`, `\d` etc. only work INSIDE psql — not shell commands.

One-liners:

```bash
docker compose exec db psql -U jarvis -d jarvis -c "\dt"
docker compose exec db psql -U jarvis -d jarvis -c "SELECT COUNT(*) FROM reminders WHERE sent = false;"
```

`alembic_version` is Alembic's own bookkeeping table. Leave it alone.

No SQL written by hand in app code — `session.add(Reminder(...))` and SQLAlchemy
generates the INSERT.

---

## Security — port exposure

`"8000:8000"` means host port 8000 → container port 8000. Omit the interface and
**Docker defaults to `0.0.0.0` = every interface, including the public IP.** On a
VPS that means the whole internet.

```yaml
ports:
  - "8000:8000"            # = 0.0.0.0:8000 — PUBLIC on a VPS
  - "127.0.0.1:8000:8000"  # loopback only
```

```bash
docker compose ps
# 0.0.0.0:8000->8000/tcp   = published to the internet
# 127.0.0.1:8000->8000/tcp = local only
# 5432/tcp (no prefix)     = internal Docker network only
# (blank)                  = nothing published (the bot — long-polling needs none)
```

**Rule:** publish a port only if something OUTSIDE the machine needs it, as narrowly
as possible. The api does NOT need a host port to reach the db — containers talk by
service name (`db:5432`) over the private Docker network.

A `ufw` firewall does NOT reliably block Docker-published ports — Docker writes its
rules ahead of it. Not binding the port is the reliable fix.

The same compose file is safe on the home VM (behind NAT) and risky on the VPS
(public IP). Same config, different exposure — the network position changed.

Public IPs get scanned constantly. Random 404s from unknown IPs in the api logs are
strangers probing for exploits — normal noise, but a reminder not to expose anything
unnecessary.

---

## Disk usage & cleanup

```sql
-- inside psql
SELECT pg_size_pretty(pg_database_size('jarvis'));
```

```bash
docker system df -v            # images, containers, volumes
df -h                          # whole machine (see the "/" line)
docker system prune            # remove stopped containers + dangling images
docker volume ls
```

`prune` will NOT delete running containers or named volumes, so the database is safe.
Never `docker volume rm project-jarvis_jarvis_db_data` unless wiping the DB on purpose.

---

## Testing the API by hand

```bash
curl localhost:8000/health
curl -s localhost:8000/health | python3 -m json.tool
```

FastAPI auto-generates interactive docs at `/docs`.

---

## Getting help in the terminal (reduce AI dependence)

```bash
man <command>        # full manual (q to quit)
<command> --help
docker compose --help
alembic --help
pytest --help
```

---

## Python virtual environment (only outside Docker)

Mostly not needed — the app runs in Docker with its own Python. The venv is only for
running tools directly on the host (e.g. the one-time `alembic init`).

```bash
python3 -m venv .venv          # once per machine
source .venv/bin/activate      # prompt shows (.venv)
deactivate
pip install -r requirements.txt
```

`docker compose exec ...` ignores the host venv entirely — it runs the container's
Python.