# Lyra Slack Bot

Lyra is a Slack bot for iFood CX EPS operations. Team members can mention
**@Lyra** in a channel or send her a direct message. The Slack app is a thin
relay: the Toqan Agent API handles intent detection, persona, Databricks
queries, and response generation.

Each Slack message starts a new Toqan conversation. The bot acknowledges the
Slack event immediately, adds an eyes reaction while the agent is working, polls
for the answer, removes the eyes reaction, adds a check-mark reaction, and
posts the answer in the mention's thread or back in the DM. Internal
`<think>...</think>` sections are removed before posting.

Toqan may run Databricks queries, so a response can take several minutes.
The app polls every ten seconds for up to fifteen minutes. At approximately
three and seven minutes, Lyra posts a progress update in the thread. If the API fails or
times out, Lyra replies:

> Não consegui processar agora, tente novamente

## Files

- `app.py`: Flask server, Slack Bolt Events API route, and Toqan relay.
- `requirements.txt`: exactly the four runtime dependencies required by the
  relay; there are no Gemini or Databricks SDK dependencies.
- `.env.example`: deployment variable template.
- `Procfile`: `web: python app.py`.

There is no local persona or query module: those responsibilities belong to
the Toqan agent.

## Local setup

Use Python 3.11+:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Replace the placeholders in .env with your own values.
python app.py
```

The local server listens on `http://localhost:3000` by default. Confirm it
with:

```bash
curl http://localhost:3000/health
```

Expected response:

```json
{"service":"lyra-slack-bot","status":"ok"}
```

## Environment variables

Only three variables are required for a deployed bot:

| Variable | Required | Description |
| --- | --- | --- |
| `SLACK_BOT_TOKEN` | Yes | Slack Bot User OAuth Token |
| `SLACK_SIGNING_SECRET` | Yes | Slack app signing secret |
| `TOQAN_API_KEY` | Yes | Toqan Agent API key |
| `DAILY_REPORT_CHANNEL` | No | Slack channel for the daily 09:00 Brazil CSAT report; defaults to `C0BF6JVFG7N` |
| `PORT` | No | HTTP port; defaults to `3000` and is supplied by Railway |

Never commit `.env` or real tokens. The app has no Gemini or Databricks
credentials.

## Slack app configuration

1. Under **OAuth & Permissions**, add bot scopes `app_mentions:read`,
   `chat:write`, `im:history`, and `im:read`.
2. Install the app and set `SLACK_BOT_TOKEN`.
3. Under **Event Subscriptions**, enable events and set the Request URL to:
   `https://<deployed-url>/slack/events`
4. Subscribe to bot events `app_mention` and `message.im`.
   Slack delivers the DM subscription as a `message` payload with
   `channel_type=im`; `app.py` handles that delivery and ignores other message
   events.
5. Set `SLACK_SIGNING_SECRET`, save the configuration, and invite Lyra to
   channels where she should answer.

The `/slack/events` route delegates URL verification and signature checking to
Slack Bolt's `SlackRequestHandler`.

## Deploy on Railway

1. Create a Railway service from the repository containing this folder.
2. In the service **Variables** panel, set exactly these three required
   variables: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, and `TOQAN_API_KEY`.
   Railway supplies `PORT`.
3. Railway installs `requirements.txt` and runs the `Procfile` command
   (`web: python app.py`).
4. Copy the public HTTPS URL Railway gives the service.
5. Set Slack's Event Subscriptions Request URL to
   `https://<railway-public-url>/slack/events`.
6. Verify `https://<railway-public-url>/health`, then test an `@Lyra` mention
   and a DM.

The Toqan agent performs the intent detection and data work. No Databricks
warehouse, host, token, or HTTP path is configured in this Slack service.

## Security notes

- Never commit `.env`, Slack tokens, signing secrets, or Toqan API keys.
- The Toqan API key is sent only in the `X-Api-Key` header by `app.py`.
- Do not put customer or operator personal data in logs.
- The bot does not change systems, open tickets, or adjust Akamai/MOP.
