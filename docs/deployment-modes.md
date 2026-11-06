# Telegram Finance Bot: Deployment Modes & Migration Guide

A comprehensive, beginner-friendly guide to configuring, running, and switching the Telegram Finance Bot across hosting environments and transport modes:

1. **Cloudflare Workers** (Webhook — Recommended primary production deployment)
2. **Railway** (Webhook — Serverless / App-Sleeping or standard)
3. **Railway** (Long Polling — Persistent container)
4. **Local / Docker** (Development & testing via polling or tunnels)

---

## 1. Understanding Transport Modes

The Telegram Bot API supports two mutually exclusive delivery mechanisms for delivering messages and commands to your bot:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TELEGRAM BOT API ENGINE                         │
└──────────────┬──────────────────────────────────────────┬──────────────┘
               │                                          │
       [Mode A: Webhook]                         [Mode B: Long Polling]
               │                                          │
               ▼                                          ▼
   Telegram pushes HTTPS POST                 Bot process calls getUpdates
   to your public endpoint                    in a continuous loop
               │                                          │
       ┌───────┴────────┐                         ┌───────┴────────┐
       │                │                         │                │
       ▼                ▼                         ▼                ▼
   Cloudflare        Railway                   Railway           Local
  Python Worker   (bot.webhook)              (bot.main)       (bot.main)
  (Serverless)   (Docker container)       (1 fixed replica)   (Developer machine)
```

### Webhooks vs. Long Polling

| Characteristic | Telegram Webhook (`BOT_MODE=webhook`) | Long Polling (`BOT_MODE=polling`) |
|---|---|---|
| **Mechanism** | Telegram sends an HTTPS `POST` request to your server when an event occurs. | Your application keeps an open HTTPS connection to Telegram calling `getUpdates`. |
| **Public Endpoint** | **Required:** Must be a valid, publicly reachable HTTPS URL with a valid SSL/TLS certificate. | **Not Required:** Operates entirely outbound; works behind NAT and firewalls. |
| **Runtime Model** | Event-driven; processes requests only when Telegram sends an update. | Continuously running process loop; never exits while waiting for events. |
| **Concurrency Rule** | Multiple workers/instances can process distinct updates simultaneously. | **Strictly 1 replica.** Multiple polling instances on the same token cause `409 Conflict`. |
| **Mutual Exclusivity** | **A bot token cannot use webhooks and polling at the same time.** | **Registering a webhook blocks `getUpdates` polling until deleted.** |
| **Statelessness** | Purely stateless: no database, D1, or persistent volume required. | Purely stateless: no database, SQLite, or persistent volume required. |

### Platform Compatibility

- **Cloudflare Workers:** Executes on demand in an ephemeral serverless Pyodide sandbox. Cloudflare Workers **only support Webhook mode**. Long polling is **unsupported** because Workers do not maintain long-running background daemon processes or persistent inbound TCP sockets.
- **Railway:** Can run either Docker entrypoint:
  - `BOT_MODE=webhook` runs the lightweight `bot.webhook` HTTP server (supports Railway Serverless / App-Sleeping).
  - `BOT_MODE=polling` runs the continuous `bot.main` loop (requires an always-on container; App-Sleeping must be disabled).
- **Local / Docker:** Can run long polling (`python -m bot.main`) with no public ingress needed, or webhook mode (`python -m bot.webhook`) via an HTTPS tunnel (e.g., ngrok or Cloudflare Tunnel).

> [!TIP]
> **Recommended Production Configuration:**  
> Run **Cloudflare Workers in Webhook mode**. It executes purely on incoming requests, utilizes Cloudflare's Free tier (up to 100,000 requests/day at zero ongoing compute cost), and requires no persistent virtual machine.

---

## 2. Cloudflare Workers Webhook Setup (Recommended)

Cloudflare Workers run the bot as a serverless Python script triggered by Telegram webhook POST requests.

### Configuration Variables

Cloudflare Workers configure secrets via the Wrangler CLI and non-secret variables in `wrangler.jsonc`:

| Variable | Type | Where Configured | Description |
|---|---|---|---|
| `BOT_MODE` | Variable | `wrangler.jsonc` | Must be `webhook` (default). |
| `TELEGRAM_BOT_TOKEN` | Secret | `wrangler secret put` | Your Telegram Bot API token from [@BotFather](https://t.me/BotFather). |
| `TELEGRAM_WEBHOOK_SECRET` | Secret | `wrangler secret put` | 1–256 characters (`[A-Za-z0-9_-]`) sent in the `X-Telegram-Bot-Api-Secret-Token` header. |
| `ALLOWED_CHAT_IDS` | Secret / Var | Optional | Comma-separated Telegram chat IDs allowed to access the bot (e.g. `123456789`). |
| `ADMIN_USER_IDS` | Secret / Var | Optional | Comma-separated Telegram user IDs allowed to view `/admin stats`. |

### Step-by-Step Setup

1. **Verify Prerequisites:**
   Ensure Node.js 22+ and Wrangler are available:
   ```bash
   npx wrangler --version
   ```

2. **Authenticate with Cloudflare:**
   ```bash
   npx wrangler login
   # Or set CLOUDFLARE_API_TOKEN in your environment
   ```

3. **Store Production Secrets in Cloudflare:**
   Secrets are encrypted and stored directly within Cloudflare's platform:
   ```bash
   npx wrangler secret put TELEGRAM_BOT_TOKEN
   # Prompt: Enter your Telegram Bot Token

   npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
   # Prompt: Enter a secure random string (e.g. openssl rand -hex 24)
   ```
   *(Optional)* If you restrict access to specific chats or admins:
   ```bash
   npx wrangler secret put ALLOWED_CHAT_IDS
   npx wrangler secret put ADMIN_USER_IDS
   ```

4. **Deploy the Worker:**
   Deploy the Python Worker preserving all configured secrets:
   ```bash
   npx wrangler deploy --keep-vars
   ```

5. **Identify Your Worker URL:**
   Wrangler outputs your deployment URL at the end of the deployment:
   ```text
   Uploaded telegram-finance-bot-webhook
   Deployed telegram-finance-bot-webhook triggers
     https://<worker-name>.<your-subdomain>.workers.dev
   ```

   *(Example Worker endpoint from this repository:)*
   ```text
   https://telegram-finance-bot-webhook.mrcoffee.workers.dev/webhook
   ```
   > [!IMPORTANT]
   > Do not register or modify the example production URL above. Always use your own Worker subdomain.

6. **Verify the Health Check Endpoint:**
   Before registering with Telegram, test the `/health` endpoint with `curl`:
   ```bash
   curl -sS https://<worker-name>.<your-subdomain>.workers.dev/health
   ```
   Expected response:
   ```json
   {"ok": true}
   ```

7. **Register the Webhook with Telegram:**
   Use the repository's webhook management CLI:
   ```bash
   export TELEGRAM_BOT_TOKEN="<your-bot-token>"
   export TELEGRAM_WEBHOOK_SECRET="<your-webhook-secret>"
   export WEBHOOK_URL="https://<worker-name>.<your-subdomain>.workers.dev/webhook"

   uv run python -m bot.manage_webhook register
   ```
   Expected output:
   ```text
   Webhook registered.
   ```

8. **Verify the Active Webhook Registration:**
   ```bash
   uv run python -m bot.manage_webhook info
   ```
   Expected output format:
   ```json
   {
     "url": "https://<worker-name>.<your-subdomain>.workers.dev/webhook",
     "has_custom_certificate": false,
     "pending_update_count": 0,
     "max_connections": 40,
     "ip_address": "188.114.97.0"
   }
   ```

9. **Test in Telegram:**
   Open your Telegram client and send `/stock AAPL` or `/indices` to your bot. Confirm the bot replies with market data.

### Cloudflare Webhook Troubleshooting

- **Why browser GET to `/webhook` returns 404 Not Found:**  
  The Worker's route router only accepts `POST` on `/webhook`. Browser visits send `GET` requests; the Worker rejects them with HTTP 404 by design. Only `GET /health` is designed for browser or curl inspection.
- **HTTP 403 Forbidden on Webhook POST:**  
  The `X-Telegram-Bot-Api-Secret-Token` header sent in the request does not match the `TELEGRAM_WEBHOOK_SECRET` stored in the Worker. Verify the secret configured in `wrangler secret put` matches the secret passed to `bot.manage_webhook register`.
- **HTTP 503 Service Unavailable:**  
  Indicates missing credentials (the Worker cannot find `TELEGRAM_BOT_TOKEN` or `TELEGRAM_WEBHOOK_SECRET`), or upstream market data providers are temporarily unreachable. Check Worker logs using:
  ```bash
  npx wrangler tail
  ```
- **Why Cloudflare cannot run `BOT_MODE=polling`:**  
  Cloudflare Workers execute serverless handlers strictly in response to incoming HTTP events. A polling bot requires a persistent Python process running an infinite `while True:` loop calling `getUpdates`. Cloudflare Workers automatically terminate when all active request promises resolve, making long polling technically impossible.

---

## 3. Railway Webhook Setup

Railway can run the bot as a containerized Python service using the repository's `Dockerfile` and `bot.webhook` server.

### Required Configuration

Configure these environment variables in your Railway Project Settings:

```env
BOT_MODE=webhook
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_WEBHOOK_SECRET=<your-webhook-secret>
DROP_PENDING_UPDATES=false
PORT=8080
```

### Step-by-Step Setup

1. **Create or Connect Service in Railway:**
   - In the [Railway Dashboard](https://railway.app), open your project.
   - Click **+ New** $\rightarrow$ **GitHub Repo** $\rightarrow$ Select `telegram-finance-bot`.
   - Railway automatically detects the root `Dockerfile`.

2. **Configure Environment Variables:**
   Under **Variables**, add:
   - `BOT_MODE`: `webhook`
   - `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather.
   - `TELEGRAM_WEBHOOK_SECRET`: Secure random string (`[A-Za-z0-9_-]{1,256}`).
   - `DROP_PENDING_UPDATES`: `false`
   - *(Optional)* `ALLOWED_CHAT_IDS` and `ADMIN_USER_IDS`.

3. **Verify the Docker Entrypoint:**
   The `Dockerfile` contains:
   ```dockerfile
   CMD ["sh", "-c", "case \"${BOT_MODE:-webhook}\" in polling) exec python -m bot.main ;; webhook) exec python -m bot.webhook ;; *) echo 'Invalid BOT_MODE' >&2; exit 1 ;; esac"]
   ```
   When `BOT_MODE=webhook`, Railway executes `python -m bot.webhook`, starting an `aiohttp` web server on `0.0.0.0:${PORT:-8080}`.

4. **Generate a Public Domain:**
   - Navigate to **Service Settings** $\rightarrow$ **Networking** $\rightarrow$ **Public Networking**.
   - Click **Generate Domain** (e.g. `https://telegram-finance-bot-production.up.railway.app`).

5. **Verify the Health Check:**
   ```bash
   curl -sS https://<your-railway-domain>.up.railway.app/health
   ```
   Expected response:
   ```json
   {"ok": true}
   ```

6. **Register the Webhook with Telegram:**
   ```bash
   export TELEGRAM_BOT_TOKEN="<your-bot-token>"
   export TELEGRAM_WEBHOOK_SECRET="<your-webhook-secret>"
   export WEBHOOK_URL="https://<your-railway-domain>.up.railway.app/webhook"

   uv run python -m bot.manage_webhook register
   ```

7. **Verify Registration:**
   ```bash
   uv run python -m bot.manage_webhook info
   ```
   Ensure the `url` field displays your Railway domain.

8. **Test Telegram Commands:**
   Send `/stock MSFT` or `/compare AAPL GOOG` to your bot.

### Railway Serverless / App-Sleeping Configuration

Railway provides an optional **Serverless** (App-Sleeping) toggle under:
**Service Settings** $\rightarrow$ **Deploy** $\rightarrow$ **Serverless** (or **App Sleeping**).

- **How it works:** When no HTTP requests arrive for approximately 5 minutes, Railway scales the container down to 0 instances. When Telegram sends an incoming webhook POST, Railway boots the container to service the request.
- **Cost implications:** Reduces billable vCPU and memory hours during idle hours (nights, weekends). However, Railway charges a base platform fee or usage minimum depending on your plan tier; Serverless does not guarantee absolute zero billing.
- **Cold Starts & Latency:** Waking a sleeping container takes approximately 2–5 seconds. While Telegram automatically retries unacknowledged updates, cold starts can occasionally cause transient gateway timeouts (HTTP 502/504) if initialization exceeds Telegram's immediate connection timeout.
- **Webhook Retry Limits:** Telegram retries unacknowledged updates with exponential backoff for up to 24 hours. Do not rely on retries indefinitely—if your service fails to respond with HTTP 200 consistently, Telegram will eventually suspend webhook delivery.

---

## 4. Railway Long Polling Setup

In polling mode, the bot continuously polls Telegram's `getUpdates` API.

> [!WARNING]
> **Railway Polling is supported but not recommended for the lowest-cost deployment.**  
> Polling requires an active, uninterrupted container process 24 hours a day, 7 days a week, consuming continuous billable compute time even when no user sends commands.

### Required Configuration

Set these variables in Railway:

```env
BOT_MODE=polling
TELEGRAM_BOT_TOKEN=<your-bot-token>
DROP_PENDING_UPDATES=false
```

### Critical Rules for Polling Mode

1. **Delete Any Registered Webhook First:**  
   Telegram's API strictly rejects polling if a webhook is currently active. Before starting a poller, you must delete the webhook:
   ```bash
   uv run python -m bot.manage_webhook remove
   ```
2. **Disable Railway Serverless / App-Sleeping:**  
   In **Service Settings** $\rightarrow$ **Deploy**, ensure **Serverless / App Sleeping is DISABLED**. If enabled, Railway will detect zero inbound HTTP traffic and put the container to sleep, abruptly stopping the polling process.
3. **Keep Railway Replicas at Exactly 1:**  
   Under **Service Settings** $\rightarrow$ **Deploy** $\rightarrow$ **Replicas**, set the replica count to `1`. If multiple instances attempt to call `getUpdates` with the same token, Telegram terminates the requests with:
   ```text
   telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
   ```
4. **No Public Domain Required:**  
   Polling initiates outbound connections to Telegram (`https://api.telegram.org`). You do not need to configure a public domain or open any incoming ports.

---

## 5. Local Development & Testing

When developing new commands or testing bug fixes locally, you can choose between polling or local webhooks.

### Option A: Local Long Polling (Fastest & Simplest)

Polling is the quickest way to test changes on your local machine without creating tunnels or public URLs.

1. **Install dependencies:**
   ```bash
   uv sync --locked
   ```

2. **Configure your local `.env`:**
   ```bash
   cp .env.example .env
   ```
   Add your test bot token:
   ```env
   TELEGRAM_BOT_TOKEN="123456789:ABCDefgh..."
   BOT_MODE="polling"
   ```

3. **Ensure no webhook is registered on your test bot:**
   ```bash
   uv run python -m bot.manage_webhook remove
   ```

4. **Launch the local bot:**
   ```bash
   BOT_MODE=polling uv run python -m bot.main
   ```
   The bot will connect to Telegram and listen for commands. Press `Ctrl+C` to stop.

### Option B: Local Webhooks via Tunnel (Advanced)

If you need to test the webhook transport (`bot.webhook`) locally:

1. **Start the local webhook server:**
   ```bash
   export BOT_MODE=webhook
   export TELEGRAM_BOT_TOKEN="<test-bot-token>"
   export TELEGRAM_WEBHOOK_SECRET="local-dev-secret-12345"
   export PORT=8080

   uv run python -m bot.webhook
   ```

2. **Open an HTTPS Tunnel:**
   In another terminal, expose port `8080` using an HTTPS tunneling tool:
   ```bash
   # Using ngrok as an example:
   ngrok http 8080

   # Or using Cloudflare Tunnel:
   cloudflared tunnel --url http://localhost:8080
   ```

3. **Register the Tunnel Webhook:**
   Copy the assigned HTTPS forwarding domain (e.g. `https://random-subdomain.ngrok-free.app`):
   ```bash
   export WEBHOOK_URL="https://random-subdomain.ngrok-free.app/webhook"
   export TELEGRAM_BOT_TOKEN="<test-bot-token>"
   export TELEGRAM_WEBHOOK_SECRET="local-dev-secret-12345"

   uv run python -m bot.manage_webhook register
   ```

4. **Clean up when finished:**
   When done testing, remove the tunnel webhook so Telegram stops sending requests to the dead tunnel:
   ```bash
   uv run python -m bot.manage_webhook remove
   ```

> [!TIP]
> **Use a Separate Test Bot Token:**  
> Always register a separate development bot using [@BotFather](https://t.me/BotFather) (e.g. `@my_finance_dev_bot`) for local testing. Testing with your production token will steal updates from your live deployment and trigger `409 Conflict` errors.

---

## 6. The Webhook Management CLI

The repository includes a dedicated management tool: [`bot/manage_webhook.py`](file:///Users/atr/code/telegram-finance-bot/bot/manage_webhook.py).

This tool safely interacts with Telegram's `setWebhook`, `deleteWebhook`, and `getWebhookInfo` endpoints without exposing tokens in shell history or query parameters.

### Command Reference

All commands automatically load configuration from your local `.env` file via `dotenv`, or from current shell environment variables.

#### 1. Inspect Current Webhook (`info`)
```bash
uv run python -m bot.manage_webhook info
```
- **Required Variable:** `TELEGRAM_BOT_TOKEN`
- **Output:** Outputs the raw JSON response from Telegram's `getWebhookInfo` method.
- **Sample Output (Active Webhook):**
  ```json
  {"url": "https://telegram-finance-bot-webhook.mrcoffee.workers.dev/webhook", "has_custom_certificate": false, "pending_update_count": 0, "max_connections": 40, "ip_address": "188.114.97.0"}
  ```
- **Sample Output (Polling / No Webhook):**
  ```json
  {"url": "", "has_custom_certificate": false, "pending_update_count": 0}
  ```

#### 2. Register or Update Webhook (`register`)
```bash
WEBHOOK_URL="https://<your-host>/webhook" \
TELEGRAM_WEBHOOK_SECRET="<your-secret>" \
  uv run python -m bot.manage_webhook register
```
- **Required Variables:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `WEBHOOK_URL`.
- **Validation:** 
  - `WEBHOOK_URL` must start with `https://` and include a valid hostname.
  - `TELEGRAM_WEBHOOK_SECRET` must match `^[A-Za-z0-9_-]{1,256}$`.
- **Pending Updates:** Sends `drop_pending_updates: false` by default, preserving unacknowledged updates queued in Telegram during switching.
- **Output:** `Webhook registered.`

#### 3. Delete Webhook (`remove`)
```bash
uv run python -m bot.manage_webhook remove
```
- **Required Variable:** `TELEGRAM_BOT_TOKEN`.
- **Pending Updates:** Sends `drop_pending_updates: false` by default, preserving pending updates for an incoming polling client.
- **Output:** `Webhook removed.`

---

## 7. Step-by-Step Migration Procedures

Follow these verified transition procedures to safely move between environments without losing user updates or causing routing conflicts.

### Procedure A: Cloudflare Webhook $\rightarrow$ Railway Webhook

Switching from Cloudflare Workers to Railway Webhook mode.

1. **Deploy and Verify Railway:**
   - In Railway, deploy the repository with `BOT_MODE=webhook`.
   - Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` in Railway Variables.
   - Verify the Railway health endpoint:
     ```bash
     curl -sS https://<your-railway-domain>.up.railway.app/health
     ```
     Ensure it returns `{"ok": true}`.

2. **Switch Webhook URL to Railway:**
   Run `register` with the Railway URL. Telegram immediately points all new updates to Railway:
   ```bash
   WEBHOOK_URL="https://<your-railway-domain>.up.railway.app/webhook" \
     uv run python -m bot.manage_webhook register
   ```
   *(Note: Calling `register` replaces the existing Cloudflare webhook atomically without needing to call `remove` first).*

3. **Confirm Active Destination:**
   ```bash
   uv run python -m bot.manage_webhook info
   ```
   Verify that `url` shows `https://<your-railway-domain>.up.railway.app/webhook`.

4. **Send a Test Command in Telegram:**
   Send `/stock AAPL` in Telegram. Confirm Railway logs reflect the processed request.

5. **Cloudflare Worker Status:**
   The Cloudflare Worker remains deployed and idle at zero cost, serving as an instant rollback target.

---

### Procedure B: Railway Webhook $\rightarrow$ Cloudflare Webhook

Switching from Railway Webhook mode to Cloudflare Workers.

1. **Verify Cloudflare Deployment:**
   - Confirm Worker secrets are set (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`).
   - If deploying updates, run `npx wrangler deploy --keep-vars`.
   - Check the health check endpoint:
     ```bash
     curl -sS https://<your-worker-name>.<your-subdomain>.workers.dev/health
     ```
     Ensure it returns `{"ok": true}`.

2. **Switch Webhook URL to Cloudflare:**
   ```bash
   WEBHOOK_URL="https://<your-worker-name>.<your-subdomain>.workers.dev/webhook" \
     uv run python -m bot.manage_webhook register
   ```

3. **Confirm Destination:**
   ```bash
   uv run python -m bot.manage_webhook info
   ```
   Verify `url` is now your Cloudflare Worker URL.

4. **Verify Functionality in Telegram:**
   Test `/stock TSLA`, `/crypto ETH`, `/indices`, and `/chart AAPL`.

5. **Scale Down Railway Service:**
   In Railway, navigate to **Settings** $\rightarrow$ scale replicas to `0` or delete/pause the service to eliminate unnecessary container costs.

---

### Procedure C: Any Webhook $\rightarrow$ Railway Polling

Switching from a Webhook (Cloudflare or Railway) to Railway Long Polling.

1. **Configure Railway Service:**
   - In Railway, set `BOT_MODE=polling`.
   - Ensure `DROP_PENDING_UPDATES=false`.
   - Under **Deploy**, disable **Serverless / App Sleeping**.
   - Under **Replicas**, ensure replica count is set to `1`.

2. **Delete the Active Telegram Webhook:**
   Before the poller starts, delete the existing webhook:
   ```bash
   uv run python -m bot.manage_webhook remove
   ```

3. **Verify Webhook Is Empty:**
   ```bash
   uv run python -m bot.manage_webhook info
   ```
   Confirm `"url": ""` in the output.

4. **Start the Railway Poller:**
   Trigger deployment or restart the Railway service. Check Railway deployment logs:
   ```text
   Starting bot (drop_pending_updates=False)... Waiting for commands.
   ```

5. **Verify Telegram Delivery:**
   Send `/stock SPY` in Telegram. Confirm the bot replies promptly and check that no `Conflict` errors appear in Railway logs.

---

### Procedure D: Railway Polling $\rightarrow$ Cloudflare Webhook

Switching from Railway Long Polling to Cloudflare Workers.

1. **Verify Cloudflare Worker Readiness:**
   Ensure the Worker is deployed and healthy:
   ```bash
   curl -sS https://<your-worker-name>.<your-subdomain>.workers.dev/health
   ```

2. **Stop the Railway Poller First:**
   > [!IMPORTANT]
   > You must stop the polling container **before** registering the webhook to prevent race conditions or duplicate update consumption.
   In Railway, click **Stop** or scale replicas to `0`.

3. **Register the Cloudflare Webhook:**
   ```bash
   WEBHOOK_URL="https://<your-worker-name>.<your-subdomain>.workers.dev/webhook" \
     uv run python -m bot.manage_webhook register
   ```

4. **Verify Active Webhook:**
   ```bash
   uv run python -m bot.manage_webhook info
   ```
   Verify that `url` displays your Cloudflare Worker endpoint and `pending_update_count` is 0.

5. **Send a Test Message:**
   Send `/indices` in Telegram and confirm response.

---

### Procedure E: Railway Polling $\rightarrow$ Railway Webhook

Switching Railway from Long Polling mode to Webhook mode.

1. **Update Railway Environment Variables:**
   Change `BOT_MODE` from `polling` to `webhook`:
   - `BOT_MODE=webhook`
   - `TELEGRAM_WEBHOOK_SECRET=<your-secret>`

2. **Enable App Sleeping (Optional):**
   If you wish to reduce idle costs, enable **Serverless / App Sleeping** in Railway deploy settings.

3. **Redeploy and Verify Service:**
   Redeploy the service in Railway. The container will boot `bot.webhook`. Test the health check:
   ```bash
   curl -sS https://<your-railway-domain>.up.railway.app/health
   ```

4. **Register the Railway Webhook URL:**
   ```bash
   WEBHOOK_URL="https://<your-railway-domain>.up.railway.app/webhook" \
     uv run python -m bot.manage_webhook register
   ```

5. **Verify Active Destination:**
   ```bash
   uv run python -m bot.manage_webhook info
   ```

---

### Procedure F: Railway Webhook $\rightarrow$ Railway Polling

Switching Railway from Webhook mode to Long Polling mode.

1. **Delete the Telegram Webhook:**
   ```bash
   uv run python -m bot.manage_webhook remove
   ```

2. **Verify Webhook Is Cleared:**
   ```bash
   uv run python -m bot.manage_webhook info
   ```
   Confirm `"url": ""`.

3. **Update Railway Environment Variables:**
   - Set `BOT_MODE=polling`.
   - In **Deploy Settings**, **disable** Serverless / App-Sleeping.
   - Verify replicas are set to `1`.

4. **Redeploy Service:**
   Redeploy the Railway service. The Docker entrypoint boots `bot.main`.

5. **Check Deployment Logs & Test:**
   Confirm logs show `"Waiting for commands."` and test `/stock NVDA` in Telegram.

---

## 8. Quick Switching Cheat Sheet

| Starting Mode | Destination Mode | Must Call `remove`? | Must Call `register`? | Persistent Process Needed? | Cost Implications |
|---|---|:---:|:---:|:---:|---|
| **Cloudflare Webhook** | **Railway Webhook** | No (atomic swap) | Yes (Railway URL) | Only while active | Increased usage (Railway container runtime). |
| **Railway Webhook** | **Cloudflare Webhook** | No (atomic swap) | Yes (Cloudflare URL) | None | **Zero compute cost** on Workers Free tier. |
| **Any Webhook** | **Railway Polling** | **Yes** (clear webhook) | No | **Yes (1 replica)** | **Highest cost** (continuous 24/7 container uptime). |
| **Railway Polling** | **Cloudflare Webhook** | No (register overrides) | **Yes** (Cloudflare URL) | None | Stop Railway poller; drop cost to zero. |
| **Railway Polling** | **Railway Webhook** | No (register overrides) | **Yes** (Railway URL) | Only while active | Reduced cost if Serverless App-Sleeping is on. |
| **Railway Webhook** | **Railway Polling** | **Yes** (clear webhook) | No | **Yes (1 replica)** | Increased cost (requires always-on container). |

---

## 9. Troubleshooting & Common Errors

### 1. `409 Conflict: terminated by other getUpdates request`
- **Cause:** Two processes are attempting to poll Telegram simultaneously with the same bot token.
- **Remedy:** Ensure only one poller is active. Check for a local dev bot running in another terminal window or multiple replicas deployed in Railway. Keep replicas at `1`.

### 2. `409 Conflict: can't use getUpdates method while webhook is active`
- **Cause:** Starting `bot.main` (polling) while Telegram still has an active webhook registered.
- **Remedy:** Run `uv run python -m bot.manage_webhook remove` and verify with `info` before starting the poller.

### 3. Telegram Webhook Points to the Wrong Host
- **Symptom:** You deployed updates to Cloudflare, but the bot still executes code on Railway (or vice versa).
- **Remedy:** Remember that deploying code does **not** update Telegram's routing. Run `uv run python -m bot.manage_webhook info` to inspect the actual destination, then run `register` with the desired URL.

### 4. `403 Forbidden` on Webhook Requests
- **Cause:** The `X-Telegram-Bot-Api-Secret-Token` header sent by Telegram does not match your server's `TELEGRAM_WEBHOOK_SECRET`.
- **Remedy:** Ensure the secret configured in Cloudflare (`wrangler secret put TELEGRAM_WEBHOOK_SECRET`) or Railway environment variables exactly matches the secret used during `bot.manage_webhook register`.

### 5. Cloudflare `/health` Works, but `/webhook` Returns 404 / 403
- **Cause:** The `/webhook` endpoint requires an HTTP `POST` containing a valid update payload and secret token header.
- **Remedy:** Do not test `/webhook` in a standard web browser (which sends a `GET` without headers). Test only `/health` directly, and test `/webhook` by sending commands in Telegram.

### 6. Railway Serverless Cold Starts / HTTP 502 Bad Gateway
- **Cause:** When Railway App-Sleeping is enabled, waking a sleeping container takes several seconds.
- **Remedy:** Telegram automatically retries webhook delivery. If cold-start latency is unacceptable, disable Serverless / App-Sleeping in Railway settings to keep the container continuously warm.

### 7. Telegram `pending_update_count` Keeps Increasing
- **Cause:** Your webhook server is failing, returning HTTP 5xx errors, timing out, or returning non-200 responses, causing Telegram to queue updates.
- **Remedy:** Run `uv run python -m bot.manage_webhook info` to check `last_error_message` and `last_error_date`. Check server logs (`npx wrangler tail` or Railway Deploy Logs) for unhandled exceptions.

### 8. Bot Responds to Commands, but Stock Quotes Fail
- **Cause:** Yahoo Finance rate-limiting or upstream market data unavailability.
- **Remedy:** The bot is functioning correctly. Check logs for provider error status. If Yahoo rate-limits an IP, requests will return safe fallback messages.

---

## 10. Safety, Rollback & Security Guidance

1. **Active Update Destination vs. Deployed Service:**  
   Deploying code to Cloudflare or Railway does **not** change where Telegram delivers updates. Telegram only sends updates to the single URL registered in its servers. Always run `uv run python -m bot.manage_webhook register` when changing hosting.
2. **Never Commit Secrets:**  
   Never commit `.env`, `.dev.vars`, or tokens into git. The repository's `.gitignore` excludes these by default. Always use `wrangler secret put` on Cloudflare and Railway Variables.
3. **Never Run Competing Consumers:**  
   Do not run a Cloudflare Worker and a Railway container on the same bot token simultaneously unless you are deliberately switching webhooks. Never run two polling instances at once.
4. **Preserve Pending Updates:**  
   The management CLI uses `drop_pending_updates: false` by default for both `register` and `remove`. This prevents user commands sent during the transition from being silently discarded.
5. **Telegram Update Retention Limits:**  
   Telegram retains unacknowledged pending updates on its servers for **up to 24 hours**. If a migration takes longer than 24 hours or an outage persists, Telegram eventually purges older updates.
6. **Instant Rollback:**  
   If a migration fails or the new target experiences issues, rollback is instantaneous: simply re-register the previously working webhook URL using `bot.manage_webhook register`, or start your backup poller after calling `bot.manage_webhook remove`.
