# Evenly — Installation via Podman Desktop (macOS)

Podman Desktop is a free, open-source alternative to Docker Desktop. It runs
containers rootless (no daemon running as root) and is fully compatible with
`docker-compose.yml` files via the `podman compose` command.

---

## Step 1 — Install Podman Desktop

Download and install **Podman Desktop** from the official website:

```
https://podman-desktop.io
```

Or via Homebrew:

```bash
brew install --cask podman-desktop
```

After installation, open **Podman Desktop** from your Applications folder.

---

## Step 2 — Initialize and start the Podman machine

Podman on macOS runs containers inside a lightweight Linux VM (the "Podman
machine"). Podman Desktop handles this automatically on first launch — you will
be prompted to create and start a machine.

If you prefer the terminal:

```bash
# Create the machine (only once)
podman machine init

# Start the machine
podman machine start
```

Verify it is running:

```bash
podman machine list
# NAME                     VM TYPE     CREATED     LAST UP     CPUS    MEMORY      DISK SIZE
# podman-machine-default*  applehv     ...         Running     ...
```

---

## Step 3 — Install the compose plugin

Podman Desktop installs `podman compose` as part of its setup. If the command is
not available, install it manually:

```bash
brew install podman-compose
```

Verify:

```bash
podman compose version
# podman-compose version 1.x.x
```

> **Note:** There are two variants — `podman compose` (built into newer Podman
> versions) and `podman-compose` (the standalone Python tool). Both work with
> Evenly's `docker-compose.yml`. Use whichever is available on your system.

---

## Step 4 — Clone the repository

```bash
git clone https://github.com/schibbbi/evenly.git
cd evenly
```

---

## Step 5 — Create the environment file

```bash
cp .env.example .env
```

For local use on your MacBook, the defaults work without changes. Open `.env` in
any editor if you want to add optional services:

```env
# Already correct for local use — no changes needed:
VITE_API_URL=http://localhost:8000
DATABASE_URL=sqlite:////app/data/evenly.db
APP_VERSION=0.1.0

# Optional — AI-generated task catalog (falls back to built-in 136-task catalog)
CLAUDE_API_KEY=your_claude_api_key_here

# Optional — Google Calendar integration
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/calendar/callback
```

---

## Step 6 — Build and start Evenly

```bash
podman compose up -d --build
```

Or with the standalone tool:

```bash
podman-compose up -d --build
```

What happens during the build:

1. **Backend image** — Python 3.11 base image, all pip dependencies from
   `requirements.txt` are installed (FastAPI, SQLAlchemy, uvicorn, etc.)
2. **Frontend image** — Node 20 base image, `npm install` runs inside the
   container installing all dependencies including `vue-i18n` (the library
   that powers DE/EN language switching), then Vite compiles the app into
   static files served by nginx
3. **Containers start** — backend on port `8000`, frontend on port `3001`
4. **Database migrations** run automatically on first backend start

The first build takes 2–5 minutes depending on your connection. Subsequent
starts are instant (images are cached).

---

## Step 7 — Verify

```bash
# Check both containers are running
podman compose ps

# Check backend health
curl http://localhost:8000/health
# → { "status": "ok", "version": "0.1.0" }
```

In **Podman Desktop** you can also see both containers in the **Containers** tab
with their status, logs, and resource usage.

---

## Step 8 — Open Evenly in your browser

```
http://localhost:3001
```

The setup wizard launches automatically on first visit. It walks you through
creating your household, rooms, residents, and generating the task catalog.

---

## Daily usage

Containers are configured with `restart: unless-stopped` — they start
automatically when the Podman machine starts.

**Start the Podman machine** (if not already running):
```bash
podman machine start
```

**Start Evenly containers** (if stopped):
```bash
podman compose up -d
```

**Stop Evenly** (machine keeps running):
```bash
podman compose down
```

**Stop everything including the VM**:
```bash
podman compose down
podman machine stop
```

---

## Viewing logs

```bash
# All containers — live output
podman compose logs -f

# Backend only
podman compose logs -f backend

# Frontend only
podman compose logs -f frontend
```

Logs are also available in **Podman Desktop** → Containers → select container →
Logs tab.

---

## Updating Evenly

```bash
cd evenly

# Pull latest code
git pull

# Rebuild images and restart
podman compose up -d --build
```

> The `--build` flag forces a fresh image build. This is required whenever
> `requirements.txt` or `package.json` change (new dependencies). For code-only
> changes, `--build` is still recommended to keep images in sync.

---

## Resetting the database

```bash
# Stop containers and delete the data volume (WARNING: deletes all household data)
podman compose down -v

# Start fresh
podman compose up -d --build
```

---

## Port overview

| Service  | Port | URL |
|----------|------|-----|
| Frontend |  3001 | `http://localhost:3001` |
| Backend  | 8000 | `http://localhost:8000` |

---

## Troubleshooting

**`podman compose` command not found**
```bash
brew install podman-compose
# then use: podman-compose up -d --build
```

**Podman machine not running — containers fail to start**
```bash
podman machine start
# then retry: podman compose up -d
```

**Frontend shows "Can't reach Evenly server"**
→ The backend container is not running, or `VITE_API_URL` in `.env` is wrong.
```bash
podman compose ps          # check status
podman compose logs backend  # check for errors
```

**Port 3001 or 8000 already in use**
```bash
# Find what is using the port
lsof -i :3001
lsof -i :8000
```
→ Change the host-side port in `docker-compose.yml` if needed:
```yaml
ports:
  - "3002:80"   # use any free port
```

**Build fails with "no space left on device" inside Podman machine**
```bash
# Increase disk size (stop machine first)
podman machine stop
podman machine set --disk-size 40   # size in GB
podman machine start
```

**Permission denied on volume mount (rootless Podman)**
→ Rootless Podman uses user namespaces. The `evenly-data` named volume is managed
by Podman and does not have permission issues. Only bind mounts to host paths can
cause this — Evenly does not use bind mounts by default.

**Podman Desktop shows containers as "Exited"**
→ Open Podman Desktop → Containers → click the container → Logs tab to see the
error. Most common cause is a misconfigured `.env` or a port conflict.
