# Jarvis — Command Reference

My own cheat sheet of the useful, project-specific commands. Filled in with real
values (repo, db user, ports) so they're copy-paste ready.

Key values used below:
- Repo folder: `Project-Jarvis`
- DB user / DB name: `jarvis` / `jarvis`
- Ports: API `8000`, Postgres `5432`, SSH-to-VM `2222`

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
```

Rule when switching between VM and VPS: **push before you stop, pull before you start.**

---

## Docker Compose — running Jarvis

Run these from inside `~/Project-Jarvis` (where docker-compose.yml lives).

```bash
docker compose up -d           # build (if needed) + start all containers in background
docker compose up -d --build   # force a rebuild, then start (use after code changes)
docker compose down            # stop AND remove containers (data survives via volume)
docker compose stop            # stop containers but keep them (faster restart)
docker compose start           # start previously-stopped containers
docker compose restart api     # restart just the api service
docker compose ps              # status of this project's containers
```

---

## Logs & debugging (your first move when something breaks)

```bash
docker compose logs api        # all output from the api container
docker compose logs db         # all output from the postgres container
docker compose logs -f api     # follow logs live (Ctrl+C to stop watching)
docker compose logs --tail 50 api   # just the last 50 lines

docker ps                      # every running container (not just this project)
docker ps -a                   # include stopped containers
```

When a container behaves oddly: `docker compose down` then `docker compose up -d --build`
forces a clean recreate.

---

## Talking to the database

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

One-liner without entering psql interactively:

```bash
docker compose exec db psql -U jarvis -d jarvis -c "SELECT COUNT(*) FROM messages;"
```

---

## Database size & disk usage

```bash
# Size of the jarvis database (run inside psql)
SELECT pg_size_pretty(pg_database_size('jarvis'));

# Docker disk usage — images, containers, and volumes (your data volume shows here)
docker system df -v

# Whole-machine disk: total / used / free (look at the "/" line)
df -h
```

---

## Cleanup (when Docker disk creeps up)

```bash
docker system df               # summary of what Docker is using
docker system prune            # remove stopped containers + dangling images (asks first)
docker image ls                # list images
docker volume ls               # list volumes (your DB data lives in a named volume)
```

`docker system prune` will NOT delete running containers or named volumes, so your
database data is safe. Never run `docker volume rm jarvis_db_data` unless you truly
want to wipe the database.

---

## Testing the API

```bash
# Health check (run on the same machine the API is on)
curl localhost:8000/health

# Pretty-print the JSON response (if python is available)
curl -s localhost:8000/health | python3 -m json.tool

# FastAPI's auto-generated interactive docs (in a browser, once port is reachable)
# http://localhost:8000/docs
```

---

## Getting help in the terminal (reduce AI dependence)

```bash
man <command>        # full manual for a command (q to quit)
<command> --help     # quick list of options, e.g. docker compose --help
docker --help
git --help
```

---

## Handy Python virtual environment (when running the app directly, not in Docker)

```bash
source .venv/bin/activate      # enter the project's Python sandbox (prompt shows (.venv))
deactivate                     # leave it
pip install -r requirements.txt   # install project dependencies into the venv
pip freeze                     # list installed packages + versions
```
