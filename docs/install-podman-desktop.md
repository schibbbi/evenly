# Evenly — Installation via Podman Desktop (GUI, macOS)

This guide walks through running Evenly entirely through the **Podman Desktop**
graphical interface — no terminal required except for one-time setup steps
(cloning the repo and creating the `.env` file).

**Evenly runs on:**
- Frontend: `http://localhost:3001`
- Backend: `http://localhost:8000`

---

## Step 1 — Install Podman Desktop

1. Open your browser and go to **https://podman-desktop.io**
2. Click **Download for macOS**
3. Open the downloaded `.dmg` file
4. Drag **Podman Desktop** into your Applications folder
5. Open **Podman Desktop** from Launchpad or Applications

> Alternatively via Homebrew:
> ```bash
> brew install --cask podman-desktop
> ```

---

## Step 2 — Initial setup in Podman Desktop

On first launch, Podman Desktop runs a setup wizard:

1. **Welcome screen** — click **Get started with Podman**
2. **Install Podman** — if not yet installed, Podman Desktop offers to install it.
   Click **Install** and follow the prompts (requires your macOS password)
3. **Initialize Podman machine** — Podman needs a small Linux VM to run
   containers on macOS. Click **Initialize and start** when prompted
4. Wait for the machine status to show a green dot — **Running**

You can check the machine status at any time in the bottom-left status bar of
Podman Desktop.

---

## Step 3 — Clone the repository (Terminal — one time only)

Open **Terminal** (Spotlight → Terminal) and run:

```bash
git clone https://github.com/schibbbi/evenly.git
cd evenly
cp .env.example .env
```

The `.env` file is pre-configured for local use — no changes needed for a basic
setup. If you want to add optional services, open `.env` in any text editor:

```env
# Already correct for local use — no changes needed:
VITE_API_URL=http://localhost:8000

# Optional — AI-generated task catalog
CLAUDE_API_KEY=your_claude_api_key_here

# Optional — Google Calendar integration
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/calendar/callback
```

This is the only time you need the Terminal. Everything else is done in Podman
Desktop.

---

## Step 4 — Open the project in Podman Desktop

1. In Podman Desktop, click **Images** in the left sidebar
2. Click **Build** (top right)

   ![Build button location: Images → Build]

3. In the **Build Image** dialog:
   - **Containerfile path** — click the folder icon and navigate to:
     `evenly/backend/Dockerfile`
   - **Build context** — set to the `evenly/backend/` folder
   - **Image name** — enter `evenly-backend`
   - Click **Build**

4. Repeat for the frontend:
   - **Containerfile path** → `evenly/frontend/Dockerfile`
   - **Build context** → `evenly/frontend/` folder
   - **Build arguments** — click **Add build argument**:
     - Key: `VITE_API_URL`
     - Value: `http://localhost:8000`
   - **Image name** — enter `evenly-frontend`
   - Click **Build**

> **Why two separate builds?** Podman Desktop's image builder works on one
> Dockerfile at a time. The `docker compose` approach (below) builds both
> automatically — see Step 5 for the easier method.

---

## Step 5 — Start with Docker Compose (recommended)

Podman Desktop supports Compose files directly, which builds and starts both
containers in one step.

1. In Podman Desktop, click the **⋮** menu (top right) → **Extensions**
2. Make sure **Compose** is listed as installed. If not, click **Install**

3. Click **Containers** in the left sidebar
4. Click **Play Kubernetes YAML / Compose** (the play button with a document icon,
   top right area) — or look for **"Start Compose"** / **"Run Compose"** button

   > The exact label depends on your Podman Desktop version. Look for any button
   > referencing "Compose" in the Containers view.

5. In the dialog:
   - Select the `docker-compose.yml` file from the `evenly/` folder
   - Click **Start**

6. Podman Desktop builds both images (this takes 2–5 minutes on first run) and
   starts the containers. You will see progress in the build log panel.

---

## Step 6 — Verify containers are running

1. Click **Containers** in the left sidebar
2. You should see two running containers:
   - `evenly-backend-1` — green dot, status **Running**
   - `evenly-frontend-1` — green dot, status **Running**

3. Click on `evenly-backend-1` → **Logs** tab
   Look for:
   ```
   INFO:     Application startup complete.
   ```

---

## Step 7 — Open Evenly in your browser

```
http://localhost:3001
```

The setup wizard launches automatically on first visit. It walks you through:
1. Naming your household
2. Selecting who lives there (children, pets, garden)
3. Adding appliances and rooms
4. Creating your admin profile and PIN
5. Generating the task catalog

---

## Managing containers in Podman Desktop

### Start / Stop

- **Containers** sidebar → find `evenly-backend-1` or `evenly-frontend-1`
- Click the **▶ Start** or **⏹ Stop** button on the right side of each row
- To start/stop both at once: use **Pods** if they were started as a pod, or
  stop them individually

### View logs

- Click on a container → **Logs** tab
- Logs update live

### Inspect environment variables

- Click on a container → **Inspect** tab → scroll to `Env`

### Delete containers and start fresh

- Click the **trash icon** next to each container to delete it
- To also delete the data volume: **Volumes** sidebar → find `evenly-data` →
  click the **trash icon**
  > **Warning:** this deletes your household data permanently

---

## Updating Evenly

1. Open **Terminal** and pull the latest code:
   ```bash
   cd evenly
   git pull
   ```

2. In Podman Desktop → **Containers** → stop both Evenly containers

3. In Podman Desktop → **Images** → find `evenly-backend` and `evenly-frontend`
   → delete both images (trash icon)

4. Re-run the Compose start from Step 5 — Podman Desktop will rebuild fresh
   images automatically

---

## Port overview

| Service  | Port | URL |
|----------|------|-----|
| Frontend | 3001 | `http://localhost:3001` |
| Backend  | 8000 | `http://localhost:8000` |

---

## Troubleshooting

**Podman machine shows red dot / not running**
→ Click the status indicator in the bottom-left of Podman Desktop → **Start machine**

**Containers start but browser shows "Can't reach Evenly server"**
→ The frontend was built with the wrong `VITE_API_URL`.
→ Delete the `evenly-frontend` image, re-add the build argument
  `VITE_API_URL=http://localhost:8000`, and rebuild.

**Port 3001 already in use**
→ Edit `docker-compose.yml` in any text editor, change `"3001:80"` to `"3002:80"`
  (or any free port), then restart the Compose stack in Podman Desktop.

**Build fails — "npm not found" or similar**
→ The frontend Dockerfile uses a Node.js base image that includes npm. This error
  means the image build did not complete. Check the build log in Podman Desktop
  for the specific error and ensure the Podman machine has internet access.

**Compose button not visible in Podman Desktop**
→ Podman Desktop → Settings → Extensions → enable **Compose**
→ Restart Podman Desktop
