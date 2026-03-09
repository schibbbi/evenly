# Evenly — Local Installation Guide

This guide covers running Evenly locally on macOS or Linux for development or
personal use. Three options are available — choose the one that fits your setup.

| Option | Requirements | Best for |
|--------|-------------|---------|
| [A — Docker / Podman](#option-a--docker--podman) | Docker Desktop or Podman | Closest to production, easiest setup |
| [B — Native via Homebrew](#option-b--native-via-homebrew) | macOS + Homebrew | Development without containers |
| [C — Native without Homebrew](#option-c--native-without-homebrew) | Python 3.11+, Node 20+ already installed | Linux or custom setups |

---

## Prerequisites (all options)

Clone the repository first:

```bash
git clone https://github.com/schibbbi/evenly.git
cd evenly
```

Copy the environment file:

```bash
cp .env.example .env
```

For local use, the defaults in `.env` work as-is. `VITE_API_URL` is already set
to `http://localhost:8000`. You only need to fill in optional values:

```env
# Optional — AI-generated task catalog (falls back to built-in catalog if not set)
CLAUDE_API_KEY=your_claude_api_key_here

# Optional — Google Calendar integration
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/calendar/callback
```

---

## Option A — Docker / Podman

### Install Docker or Podman

**Docker Desktop (macOS):**
```bash
brew install --cask docker
# Then open Docker.app to start the daemon
```

**Podman (macOS, open source alternative to Docker):**
```bash
brew install podman podman-compose
podman machine init
podman machine start
```

**Docker (Linux):**
```bash
# Debian/Ubuntu
sudo apt install docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # log out and back in after this
```

### Start the stack

```bash
# Docker
docker compose up -d --build

# Podman (drop-in compatible)
podman-compose up -d --build
```

The first build takes a few minutes. What happens:
1. Backend image is built (Python 3.11 + all pip dependencies)
2. Frontend image is built — `npm install` runs inside the container, installing
   all dependencies including `vue-i18n` (DE/EN language support), then Vite
   compiles the app
3. Database migrations run automatically on first start

### Verify

```bash
# Docker
docker compose ps
curl http://localhost:8000/health
# → { "status": "ok", "version": "0.1.0" }

# Podman
podman-compose ps
curl http://localhost:8000/health
```

### Open in browser

```
http://localhost:3001
```

### Stop

```bash
docker compose down        # stop, keep data
docker compose down -v     # stop + delete database (irreversible)
```

### Update

```bash
git pull
docker compose up -d --build
```

---

## Option B — Native via Homebrew

Runs backend and frontend directly on your machine without containers.

### Install dependencies

```bash
# Python 3.11
brew install python@3.11

# Node.js 20
brew install node@20

# Link node to PATH (if not already)
echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Verify:
```bash
python3.11 --version   # Python 3.11.x
node --version         # v20.x.x
npm --version          # 10.x.x
```

### Backend setup

```bash
cd backend

# Create a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the backend (stays running in this terminal)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> `--reload` enables auto-restart on code changes — useful for development.
> Leave this terminal open.

### Frontend setup

Open a **second terminal tab**:

```bash
cd frontend

# Install dependencies (includes vue-i18n for DE/EN language support)
npm install

# Start the dev server (stays running in this terminal)
npm run dev
```

The Vite dev server starts at `http://localhost:5173` (not port  3001 — that is
only used in the Docker/production build with nginx).

### Open in browser

```
http://localhost:5173
```

### Stop

- Backend: `Ctrl+C` in the backend terminal
- Frontend: `Ctrl+C` in the frontend terminal
- Deactivate Python venv: `deactivate`

### Update

```bash
git pull

# Backend — reinstall if requirements.txt changed
cd backend
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Frontend — reinstall if package.json changed
cd ../frontend
npm install
```

---

## Option C — Native without Homebrew

For Linux systems or macOS where Python and Node are already installed.

### Requirements

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.11 | `python3 --version` |
| pip | any | `pip3 --version` |
| Node.js | 20 | `node --version` |
| npm | 10 | `npm --version` |

**Install on Ubuntu/Debian:**
```bash
# Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip

# Node 20 via NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs
```

**Install on Fedora/RHEL:**
```bash
sudo dnf install python3.11 nodejs
```

### Backend setup

```bash
cd backend

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend setup

Open a **second terminal**:

```bash
cd frontend
npm install        # installs all dependencies including vue-i18n
npm run dev
```

### Open in browser

```
http://localhost:5173
```

---

## Port overview

| Method | Frontend | Backend |
|--------|----------|---------|
| Docker / Podman | `localhost:3001` | `localhost:8000` |
| Native (dev server) | `localhost:5173` | `localhost:8000` |

---

## Troubleshooting

**`npm install` fails with EACCES permission error**
→ Never use `sudo npm install`. Fix npm permissions instead:
```bash
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.zshrc && source ~/.zshrc
```

**Backend starts but frontend shows "Can't reach Evenly server"**
→ Check that `VITE_API_URL=http://localhost:8000` is set in `.env`.
→ For native dev: restart `npm run dev` after changing `.env`.
→ For Docker: rebuild the image (`--build`) after changing `.env`.

**`alembic upgrade head` fails — database already exists**
→ Safe to ignore if the error is just "table already exists".
→ To start fresh: `rm backend/evenly.db` then re-run migrations.

**Port 8000 already in use**
```bash
# Find what's using it
lsof -i :8000
# Kill it
kill -9 <PID>
```

**Port 5173 or  3001 already in use**
→ Vite will automatically try the next available port and print the actual URL.
→ For Docker, change the host port in `docker-compose.yml`.

**`python3.11` not found on macOS after Homebrew install**
```bash
brew link python@3.11
# or use the full path:
/opt/homebrew/bin/python3.11 -m venv .venv
```
