# Jarvis — Command Reference

My own cheat sheet of the useful, project-specific commands. Filled in with real
values (repo, db user, ports) so they're copy-paste ready.

Key values used below:
- Repo folder: `Project-Jarvis`
- DB user / DB name: `jarvis` / `jarvis`
- Ports: API `8000` (loopback only), Postgres `5432` (internal only), SSH-to-VM `2222`
- Services: `api`, `bot`, `db`
- My Telegram user ID: `8524921379`

---

## New machine setup (do this FIRST)

Every new machine needs its own git identity and its own SSH key. Skipping the
identity is why my early VPS commits show as "root" instead of me.

```bash
# 1. Git identity — use the SAME email as the GitHub account
git config --global user.name "Zygiz"
git config --global user.email "zygimantas.mikaila@gmail.com"

# verify
git config --global user.email

# 2. SSH key for GitHub (press Enter 3x for defaults)
ssh-keygen -t ed25519 -C "zygimantas.mikaila@gmail.com"
cat ~/.ssh/id_ed25519.pub          # copy this into GitHub > Settings > SSH keys
ssh -T git@github.com              # success = "Hi Zygiz!" greeting

# 3. Clone
git clone git@github.com:Zygiz/Project-Jarvis.git
cd Project-Jarvis

# 4. .env does NOT come from git — recreate it
cp .env.example .env
nano .env                          # fill in real values (DB password, bot token, allowlist)

# 5. Start + build the database tables
docker compose up -d
docker compose exec api alembic upgrade head

# 6. Confirm it works
docker compose exec api pytest
curl localhost:8000/health
```

---

## Secret hygiene — read this before pasting anything anywhere

**Never paste raw logs into chat, GitHub issues, or forums without scanning them
for secrets first.**

Learned the hard way: the `httpx` library logs full request URLs, and Telegram puts
the bot token **inside the URL**. So the app's own logs contained the token in
plaintext, and I pasted it into a chat. Had to revoke and reissue.

Fix already applied in `app/logging_config.py`:

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Application").setLevel(logging.WARNING)
```

Things that leak: bot tokens, API keys, DB passwords, `.env` contents, full URLs
with credentials in them. Logs also contain my own Telegram user ID.

---

## Telegram bot

Bot management happens in Telegram, talking to **@BotFather**:

```
/newbot      create a new bot (asks for display name, then a username ending in "bot")
/mybots      list my bots, edit settings
/token       show the current token
/revoke      KILL the current token and issue a new one — do this if it ever leaks
/setcommands set the command list shown in the Telegram UI
```

After revoking: update `TELEGRAM_BOT_TOKEN` in `.env`, then `docker compose restart bot`.

Command list format for `/setcommands` (no leading slash, ` - ` separator):

```
start - Check Jarvis is alive
help - Show available commands
```

The `/` menu is a Telegram CLIENT feature — commands work regardless, but the popup
only appears after `/setcommands`, and the client caches it (may need an app restart).

Running the bot:

```bash
docker compose logs -f bot         # watch it live (Ctrl+C to stop following)
docker compose restart bot         # restart after code changes
docker compose up -d --build       # rebuild after requirements.txt changes
```

**Long-polling, not webhooks.** The bot asks Telegram for new messages in a loop —
all connections go OUTWARD. That means:
- no open ports needed
- no public HTTPS needed
- works identically on the home VM (behind NAT) and the VPS

That's why the `bot` service in docker-compose.yml has no `ports:` at all.

Find my own Telegram user ID: send the bot a message and read the log line
`Message received | user_id=...`

**`telegram.error.NetworkError: Bad Gateway`** in the logs = Telegram's servers
hiccuping, not my code. The library retries automatically and recovers. Ignore it.

---

## Auth / allowlist

Only user IDs in `TELEGRAM_ALLOWED_USER_IDS` (comma-separated in `.env`) can use
the bot. Unauthorized users get **complete silence** — no "access denied" reply,
because that would confirm the bot exists and is worth attacking.

Denied attempts log at WARNING level:

```bash
docker compose logs bot | grep -i unauthorized
```

Startup log confirms the allowlist parsed:
`Jarvis bot starting up | allowed_users=1`

**Testing the block without a second Telegram account:**

```bash
# 1. temporarily set a wrong ID in .env
TELEGRAM_ALLOWED_USER_IDS=1
docker compose restart bot
# 2. message the bot — should get SILENCE + a WARNING in the logs
# 3. set it back to the real ID and restart
```

Worth doing. An auth check I've never seen actually deny something is one I'm only
assuming works.

---

## Connecting to the machines

```bash
# SSH into the dev VM (from Windows, VM must be running in VirtualBox)
ssh vboxuser@localhost -p 2222

# SSH into the Hostinger VPS
ssh root@<vps-ip>

# Copy a file from Windows INTO the VM (run in Windows PowerShell)
scp -P 2222 "C:\path\to\file" vboxuser@localhost:~/Project-Jarvis/

# Leave any SSH session
exit
```

**VS Code Remote-SSH:** F1 → "Remote-SSH: Connect to Host" → pick host → then
File > Open Folder → `/root/Project-Jarvis` (VPS) or `/home/vboxuser/Project-Jarvis` (VM).
Green "SSH: ..." badge bottom-left = connected. Terminal inside VS Code: Ctrl+backtick

---

## The Git loop (run constantly)

```bash
git status                 # what changed? (ALWAYS run this first)
git add .                  # stage all changes
git commit -m "message"    # save a snapshot with a description
git push                   # send commits up to GitHub
git pull                   # pull down changes (do this when switching machines)
git log --oneline          # compact history of commits
git diff                   # see exactly what changed since last commit
git log --format="%an <%ae>" -5    # who authored the last 5 commits
```

Rule when switching between VM and VPS: **push before you stop, pull before you start.**

Before every commit: check `git status` does NOT list `.env` — it holds the DB
password, the Telegram bot token, and my user ID.

Commit message style: start with a verb, present tense, describe WHAT changed.
Good: `Add Telegram user ID allowlist for bot authorization`
Bad: `update`, `fix bug`, `changes`

---

## Docker Compose — running Jarvis

Three services: `api` (FastAPI), `bot` (Telegram), `db` (Postgres).
`api` and `bot` share the same image — only the startup command differs.

Run these from inside `~/Project-Jarvis` (where docker-compose.yml lives).

```bash
docker compose up -d           # start all containers in background
docker compose up -d --build   # force rebuild, then start (after requirements.txt changes)
docker compose restart api     # restart just one service (api / bot / db)
docker compose down            # stop AND remove containers (data survives — volume kept)
docker compose stop            # stop containers but keep them (faster restart)
docker compose start           # start previously-stopped containers
docker compose ps              # status of this project's containers
```

**Gotcha:** `docker compose up -d` may say "Running" and NOT pick up code changes.
If edits don't seem to apply, use `docker compose restart <service>` or
`docker compose down && docker compose up -d`.

**Crash loop:** with `restart: unless-stopped`, a broken service restarts every few
seconds and floods the logs with the same traceback. Ctrl+C out of the log follow,
read ONE traceback, fix, then restart.

**DANGER — wipes the database:**

```bash
docker compose down -v         # -v ALSO DELETES THE VOLUME = all database data gone
```

Only use `-v` when deliberately resetting (e.g. changing POSTGRES_PASSWORD, which
Postgres only reads when initialising a fresh volume). Afterwards you must re-run
`docker compose exec api alembic upgrade head` to rebuild the tables.

---

## Running tests (pytest)

Run inside the container — that's where the dependencies and config live.

```bash
docker compose exec api pytest              # run everything
docker compose exec api pytest -v           # verbose: one line per test name
docker compose exec api pytest tests/test_health.py     # just one file
docker compose exec api pytest -k health    # only tests with "health" in the name
docker compose exec api pytest -x           # stop at the first failure
docker compose exec api pytest -q           # quiet, less output
```

Reading the output: each `.` is a passing test. `2 passed` = all good.
`F` marks a failure, and pytest prints exactly what it expected vs what it got.

How pytest finds tests — no registration needed, it discovers by naming:
- files named `test_*.py`
- functions named `test_*`

Structure must be exactly:

```
tests/
  __init__.py        (empty — marks it as a package)
  test_health.py
```

**Gotcha I hit:** accidentally created `tests/tests/tests/` by making a folder while
already inside one. Check with `find tests -type f` — should show exactly two files.

---

## Database migrations (Alembic)

Run these INSIDE the api container — that's where the hostname `db` resolves.

```bash
# After changing app/models.py — generate a migration file
docker compose exec api alembic revision --autogenerate -m "describe the change"

# Read what it generated BEFORE applying it
cat alembic/versions/*.py

# Apply pending migrations (creates/updates the real tables)
docker compose exec api alembic upgrade head

# Which migration is currently applied
docker compose exec api alembic current

# History of all migrations
docker compose exec api alembic history

# Undo the last migration
docker compose exec api alembic downgrade -1
```

**Rule:** never create or alter tables by hand in psql. Alembic compares the real
database against `models.py` — hand-made changes make it generate wrong migrations
(it produced `alter_column` instead of `create_table` when I did this once).

The chain: `models.py` (blueprint) → `revision --autogenerate` (writes the plan)
→ `upgrade head` (runs the plan) → real table in Postgres.

---

## Logs & debugging (first move when something breaks)

```bash
docker compose logs api        # all output from a service (api / bot / db)
docker compose logs -f bot     # follow live (Ctrl+C to stop watching)
docker compose logs --tail 50 api   # just the last 50 lines

docker ps                      # every running container (not just this project)
docker ps -a                   # include stopped containers
```

Debug order when something's wrong:

1. `docker compose ps` — is it even running?
2. `docker compose logs <service>` — what did it say before dying?
3. `git status` — what did I change?

Read tracebacks **bottom-up** — the real error is the last line, everything above
is just the call chain. Also check the LINE NUMBER: an error on line 1 usually
means the file's imports are missing.

Error types worth telling apart:
- `AttributeError: 'Settings' object has no attribute 'x'` → the field isn't declared
  in `config.py` at all
- `ValidationError: field required` → the field IS declared but missing from `.env`
- `NameError: name 'BaseSettings' is not defined` → I pasted a partial code block
  over the whole file and wiped the imports

**Gotcha:** when pasting code from a chat, check whether it's the WHOLE file or just
a section. Pasting a class definition over a full file deletes the imports above it.

App logs go to stdout on purpose, which is what `docker compose logs` shows.
Never log to a file inside a container — it vanishes when the container is recreated.

Log format is `timestamp | LEVEL | module | message`, e.g.
`2026-08-02 09:52:39 | INFO | app.main | Jarvis starting up`

---

## Talking to the database

Port 5432 is NOT published to the host (deliberately — see Security below), so
connect through the container.

```bash
# Open the Postgres command-line client INSIDE the db container
docker compose exec db psql -U jarvis -d jarvis
```

Once inside psql (prompt looks like `jarvis=#`):

```sql
\dt                 -- list all tables ("describe tables")
\d messages         -- show columns/structure of the "messages" table
\l                  -- list all databases
\du                 -- list users/roles
\q                  -- quit back to the normal terminal
```

Useful queries on the messages table:

```sql
SELECT * FROM messages ORDER BY created_at DESC LIMIT 10;   -- most recent first
SELECT COUNT(*) FROM messages;                              -- how many stored
SELECT * FROM messages WHERE sender = '8524921379';         -- just my messages
DELETE FROM messages;                                       -- clear them all (careful)
```

Note: `\dt`, `\d` etc. only work INSIDE psql — they are not shell commands.

One-liner without entering psql interactively:

```bash
docker compose exec db psql -U jarvis -d jarvis -c "SELECT * FROM messages;"
docker compose exec db psql -U jarvis -d jarvis -c "SELECT COUNT(*) FROM messages;"
```

`alembic_version` is Alembic's own table — it records which migration has been
applied. Leave it alone.

**How rows get written:** bot.py receives the message → calls handle_message() in
app/services.py → which calls save_message() → which opens a session via
get_session() in app/database.py and commits. No SQL written by hand.
Auth happens first via the @require_auth decorator in app/auth.py.

---

## Security — port exposure

In docker-compose.yml, `"8000:8000"` means host port 8000 → container port 8000.
If you don't specify an interface, **Docker defaults to `0.0.0.0` = every interface,
including the public IP.** On a VPS that means the whole internet can reach it.

```yaml
ports:
  - "8000:8000"            # = 0.0.0.0:8000 — PUBLIC on a VPS
  - "127.0.0.1:8000:8000"  # loopback only — reachable from the machine itself
```

Check which you have:

```bash
docker compose ps
# 0.0.0.0:8000->8000/tcp   = published to the internet
# 127.0.0.1:8000->8000/tcp = local only
# 5432/tcp (no prefix)     = internal Docker network only — not published at all
# (blank)                  = nothing published (the bot — long-polling needs none)
```

**Rule:** publish a port only if something OUTSIDE the machine needs to reach it,
and publish it as narrowly as possible. The api does NOT need a host port to reach
the db — containers talk to each other by service name (`db:5432`) over the private
Docker network.

Note: a `ufw` firewall does NOT reliably block Docker-published ports — Docker
writes its own rules ahead of it. Not binding the port is the reliable fix.

The same docker-compose.yml is safe on the home VM (behind NAT) and risky on the
VPS (public IP). Same config, different exposure — the machine's network position
is what changed.

Public IPs get scanned constantly. Random 404s in the api logs from unknown IPs are
strangers probing for exploits — normal background noise, but a reminder not to
expose anything unnecessary.

---

## Database size & disk usage

```sql
-- run inside psql
SELECT pg_size_pretty(pg_database_size('jarvis'));
```

```bash
docker system df -v            # Docker disk usage — images, containers, volumes
df -h                          # whole machine: total / used / free (see the "/" line)
```

---

## Cleanup (when Docker disk creeps up)

```bash
docker system df               # summary of what Docker is using
docker system prune            # remove stopped containers + dangling images (asks first)
docker image ls                # list images
docker volume ls               # list volumes (DB data lives in a named volume)
```

`docker system prune` will NOT delete running containers or named volumes, so the
database data is safe. Never run `docker volume rm project-jarvis_jarvis_db_data`
unless you truly want to wipe the database.

---

## Testing the API by hand

```bash
curl localhost:8000/health                              # health check
curl -s localhost:8000/health | python3 -m json.tool    # pretty-print the JSON
```

FastAPI auto-generates interactive docs at `/docs` — useful once the port is
reachable from a browser.

---

## Getting help in the terminal (reduce AI dependence)

```bash
man <command>        # full manual for a command (q to quit)
<command> --help     # quick list of options
docker compose --help
alembic --help
pytest --help
git --help
```

---

## Python virtual environment (only when running outside Docker)

Mostly not needed — the app runs in Docker, which has its own Python. The venv is
only for running tools directly on the host (e.g. the one-time `alembic init`).

```bash
python3 -m venv .venv          # create it (once per machine)
source .venv/bin/activate      # enter it (prompt shows (.venv))
deactivate                     # leave it
pip install -r requirements.txt
pip freeze                     # list installed packages + versions
```

`docker compose exec ...` commands ignore the host venv entirely — they run inside
the container's own Python.