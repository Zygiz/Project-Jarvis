# Jarvis — Command Reference

My own cheat sheet of the useful, project-specific commands. Filled in with real
values (repo, db user, ports) so they're copy-paste ready.

Key values used below:
- Repo folder: `Project-Jarvis`
- DB user / DB name: `jarvis` / `jarvis`
- Ports: API `8000`, Postgres `5432` (internal only), SSH-to-VM `2222`

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
nano .env                          # fill in real values

# 5. Start + build the database tables
docker compose up -d
docker compose exec api alembic upgrade head

# 6. Confirm it works
docker compose exec api pytest
curl localhost:8000/health
```

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

Before every commit: check `git status` does NOT list `.env` — it holds real
passwords and API keys.

---

## Docker Compose — running Jarvis

Run these from inside `~/Project-Jarvis` (where docker-compose.yml lives).

```bash
docker compose up -d           # start all containers in background
docker compose up -d --build   # force rebuild, then start (after requirements.txt changes)
docker compose restart api     # restart just the api service
docker compose down            # stop AND remove containers (data survives — volume kept)
docker compose stop            # stop containers but keep them (faster restart)
docker compose start           # start previously-stopped containers
docker compose ps              # status of this project's containers
```

**Gotcha:** `docker compose up -d` may say "Running" and NOT pick up code changes.
If edits don't seem to apply, use `docker compose restart api` or
`docker compose down && docker compose up -d`.

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
docker compose logs api        # all output from the api container
docker compose logs db         # all output from the postgres container
docker compose logs -f api     # follow logs live (Ctrl+C to stop watching)
docker compose logs --tail 50 api   # just the last 50 lines

docker ps                      # every running container (not just this project)
docker ps -a                   # include stopped containers
```

Debug order when something's wrong:

1. `docker compose ps` — is it even running?
2. `docker compose logs <service>` — what did it say before dying?
3. `git status` — what did I change?

Read tracebacks **bottom-up** — the real error is the last line, everything above
is just the call chain.

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

SELECT * FROM messages LIMIT 10;      -- peek at rows
SELECT COUNT(*) FROM messages;        -- how many rows
```

Note: `\dt`, `\d` etc. only work INSIDE psql — they are not shell commands.

One-liner without entering psql interactively:

```bash
docker compose exec db psql -U jarvis -d jarvis -c "\dt"
docker compose exec db psql -U jarvis -d jarvis -c "SELECT COUNT(*) FROM messages;"
```

`alembic_version` is Alembic's own table — it records which migration has been
applied. Leave it alone.

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

---

## Database size & disk usage

```bash
# Size of the jarvis database (run inside psql)
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