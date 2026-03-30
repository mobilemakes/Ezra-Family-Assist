# WhatsApp Setup Guide — Joseph Health Support Agent

Text the Joseph agent directly from WhatsApp. All incident reports, communication
logs, and complaint drafts are saved automatically to the folder system.

---

## What You'll Need

- An **Anthropic API key** (platform.anthropic.com)
- A free **Twilio account** (twilio.com) — no credit card needed for sandbox
- **Python 3.11+** installed
- A way to expose a local port publicly — **ngrok** (free) works great

---

## Step 1 — Get Your API Keys

### Anthropic API Key
1. Go to platform.anthropic.com → API Keys
2. Create a new key
3. Copy it — you'll need it below

### Twilio
1. Sign up free at twilio.com
2. In the Twilio Console, go to:
   **Messaging → Try it out → Send a WhatsApp message**
3. This opens the **WhatsApp Sandbox**
4. Follow the instructions to connect your phone:
   - Send the join code (e.g. `join purple-monkey`) to the sandbox number
   - Your phone is now connected to the sandbox
5. Copy your **Auth Token** from the Twilio Console home page

---

## Step 2 — Configure Environment

```bash
cd joseph-support/whatsapp

# Copy the example env file
cp .env.example .env

# Edit .env and fill in your keys
nano .env   # or use any editor
```

Your `.env` should look like:
```
ANTHROPIC_API_KEY=sk-ant-...
TWILIO_AUTH_TOKEN=...your token...
VALIDATE_TWILIO_SIG=true
```

---

## Step 3 — Install & Run

```bash
cd joseph-support/whatsapp

pip install -r requirements.txt

# Load your env variables
export $(cat .env | xargs)

python server.py
```

You should see:
```
Joseph WhatsApp Agent starting on port 5000...
```

---

## Step 4 — Expose Publicly with ngrok

Twilio needs a public URL to send webhooks to. In a **second terminal**:

```bash
# Install ngrok if you haven't: https://ngrok.com/download
ngrok http 5000
```

You'll get a URL like:
```
https://abc123.ngrok.io
```

---

## Step 5 — Configure Twilio Webhook

1. Go to Twilio Console → **Messaging → Try it out → Send a WhatsApp message**
2. In the **Sandbox Settings** section, set:
   - **When a message comes in**: `https://abc123.ngrok.io/whatsapp`
   - Method: `HTTP POST`
3. Click **Save**

---

## Step 6 — Send Your First Message

Text anything to your Twilio sandbox number from WhatsApp.

The agent will respond as Joseph's health advocate.

---

## Special Commands

| Text this | What happens |
|---|---|
| `reset` | Clears conversation history, starts fresh |
| `summary` | Quick case status — counts incidents, flags patterns |
| `help` | Lists what the agent can do |

---

## What the Agent Can Do Over WhatsApp

- **Document an incident** — it'll ask you questions and save the report automatically
- **Log a phone call or visit** — saves to `case-documentation/communications/`
- **Summarize the case** — reads all saved files and gives you an update
- **Explain patient rights** — pulls from the reference files
- **Draft a complaint letter** — saves a ready-to-review draft
- **Prep appointment questions** — based on what's been documented

---

## Deploy to the Cloud (Optional — for Always-On Access)

For permanent access without running your laptop:

### Railway (easiest, free tier)
```bash
# Install Railway CLI
npm install -g @railway/cli

railway login
railway init
railway up
```
Set your environment variables in the Railway dashboard, then use the Railway URL as your Twilio webhook.

### Render
1. Push this folder to a GitHub repo
2. Go to render.com → New Web Service → connect your repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python server.py`
5. Add environment variables in the Render dashboard

### Heroku
```bash
heroku create joseph-health-agent
heroku config:set ANTHROPIC_API_KEY=... TWILIO_AUTH_TOKEN=...
git push heroku main
```

---

## Security Notes

- `.env` is gitignored — never commit your API keys
- `conversation_history.json` stores conversation history locally — keep it private
- The server validates Twilio's signature on every request (set `VALIDATE_TWILIO_SIG=false` only for local testing without ngrok)
- This is designed for personal/family use — do not share the Twilio number publicly

---

## Troubleshooting

**"Forbidden" response from the server**
→ Twilio signature validation failed. During local dev, set `VALIDATE_TWILIO_SIG=false` in `.env`.

**Agent not responding**
→ Check that ngrok is running and the URL in Twilio matches exactly (including `/whatsapp`).

**Messages not saving to files**
→ Check that the `joseph-support/` folder paths exist. Run from within the repo.

**Rate limit errors**
→ You're hitting the Anthropic API rate limit. Wait a moment and try again.
