# Evenly — Installation on UGreen NAS DXP2800 (UGOS)

This guide walks through deploying Evenly on a UGreen NAS DXP2800 running UGOS
using the built-in Docker / Container Manager app.

**What gets installed:**
- Backend: FastAPI + SQLite on port `8000`
- Frontend: Vue.js served by nginx on port `3001`
- Persistent data volume: `evenly-data` (survives container restarts and updates)

---

## Prerequisites

- UGreen NAS DXP2800 running UGOS
- **Docker** app installed and running (UGOS App Center → Docker)
- SSH access to the NAS (UGOS → System → SSH — enable if needed)
- A terminal on your Mac/PC to SSH into the NAS

---

## Step 1 — SSH into the NAS

```bash
ssh admin@<NAS-IP>
# or using hostname:
ssh admin@<NAS-HOSTNAME>.local
```

Example:
```bash
ssh admin@192.168.1.100
```

> **Find your NAS IP:** UGOS web UI → Network → LAN.
> Assign a static IP in your router for the NAS to keep the address stable.

---

## Step 2 — Create a folder for Evenly

Create a dedicated folder on the NAS storage. The recommended location is inside
your main volume (usually `/volume1` or shown as a shared folder in UGOS).

```bash
mkdir -p /volume1/docker/evenly
cd /volume1/docker/evenly
```

---

## Step 3 — Clone the repository

```bash
git clone https://github.com/schibbbi/evenly.git .
```

> If `git` is not available on the NAS, download the ZIP from GitHub instead:
> ```bash
> wget https://github.com/schibbbi/evenly/archive/refs/heads/main.zip
> unzip main.zip
> mv evenly-main/* .
> rm -rf evenly-main main.zip
> ```

---

## Step 4 — Create the environment file

```bash
cp .env.example .env
vi .env
```

Edit the following values:

```env
# Required: set this to your NAS IP or hostname so the frontend can reach the backend
VITE_API_URL=http://192.168.1.100:8000
# or with hostname:
# VITE_API_URL=http://nas.local:8000

# Optional: only needed if you want AI-generated task catalog via Claude
CLAUDE_API_KEY=your_claude_api_key_here

# Optional: only needed for Google Calendar integration
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://192.168.1.100:8000/calendar/callback

# Leave these unchanged:
DATABASE_URL=sqlite:////app/data/evenly.db
APP_VERSION=0.1.0
```

> **Important:** `VITE_API_URL` is baked into the frontend at build time by Vite.
> It must match the IP or hostname you use to access the NAS from your devices.
> If your NAS IP changes later, you need to rebuild the frontend image.

Save and exit: `Esc` → `:wq` → `Enter`

---

## Step 5 — Build and start the stack

```bash
docker compose up -d --build
```

This will:
1. Build the backend Docker image (Python + FastAPI)
2. Build the frontend Docker image — this runs `npm install` inside the container,
   which installs all dependencies including `vue-i18n` (the i18n library for
   DE/EN language support), then compiles the app with Vite
3. Start both containers and create the `evenly-data` volume
4. Run database migrations automatically on first start

The first build takes a few minutes. Subsequent starts are fast.

---

## Step 6 — Verify

```bash
# Check containers are running
docker compose ps

# Check backend health
curl http://localhost:8000/health
# Expected: { "status": "ok", "version": "0.1.0" }
```

---

## Step 7 — Open Evenly in your browser

From any device on your home network:

```
http://192.168.1.100:3001
```

or using the hostname:

```
http://nas.local:3001
```

The setup wizard will launch automatically on first visit.

---

## Updating Evenly

```bash
cd /volume1/docker/evenly

# Pull latest code
git pull

# Rebuild and restart (--build forces a fresh image)
docker compose up -d --build
```

> If `package.json` changed (new npm dependencies), the `--build` flag ensures
> `npm install` runs inside the frontend build automatically.

---

## Viewing logs

```bash
# All containers
docker compose logs -f

# Backend only
docker compose logs -f backend

# Frontend only
docker compose logs -f frontend
```

---

## Stopping / Restarting

```bash
# Stop
docker compose down

# Stop and delete the data volume (WARNING: deletes the database)
docker compose down -v

# Restart
docker compose restart
```

---

## Port overview

| Service  | Port | URL |
|----------|------|-----|
| Frontend | 3001 | `http://<NAS-IP>:3001` |
| Backend  | 8000 | `http://<NAS-IP>:8000` |

Both ports must be free on the NAS. To change them, edit `docker-compose.yml`:
```yaml
ports:
  - "3001:80"   # change 3001 to any free port
```

---

## Troubleshooting

**Frontend shows "Can't reach Evenly server"**
→ `VITE_API_URL` in `.env` is wrong or the backend container is not running.
→ Check: `docker compose ps` and `docker compose logs backend`

**Port already in use**
→ Another service on the NAS is using port  3001 or 8000.
→ Change the host-side port in `docker-compose.yml` (see Port overview above).

**Database is empty after restart**
→ Normal — the setup wizard runs once and stores data in the `evenly-data` volume.
→ As long as you do NOT run `docker compose down -v`, all data is preserved.

**git not found on NAS**
→ Use the `wget` + unzip method described in Step 3.
→ Or install git via UGOS App Center if available.
