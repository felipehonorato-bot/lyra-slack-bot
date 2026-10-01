# Lyra Slack Bot

Lyra is an external Slack bot for iFood CX EPS operations. Team members can
mention **@Lyra** in a channel or send her a direct message. She responds in
Portuguese using the Lyra persona and Google Gemini (`gemini-2.0-flash`).

This first version does **not** query Databricks or any iFood system. It only
uses the question and the last ten in-memory messages for that Slack
channel/thread. It does not change systems, open tickets, or adjust Akamai/MOP.

## Files

- `app.py`: Flask server, Slack Bolt Events API route, `app_mention` handler,
  DM handler, bounded context, and Gemini integration.
- `lyra_persona.py`: complete Portuguese Gemini system prompt.
- `requirements.txt`: runtime dependencies plus the future Databricks connector.
- `.env.example`: secret variable template with placeholders only.
- `Procfile`: `web: python app.py`.

## Local setup

Use Python 3.11+:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your own values; never commit .env.
python app.py
```

The local server listens on `http://localhost:3000` by default. Confirm the
process with:

```bash
curl http://localhost:3000/health
```

Slack cannot reach localhost directly. For development, use a secure HTTPS
tunnel or deploy the app to a public HTTPS service.

### Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `SLACK_BOT_TOKEN` | Yes | Bot User OAuth Token |
| `SLACK_SIGNING_SECRET` | Yes | Slack app signing secret |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `PORT` | No | HTTP port; defaults to `3000` |

Missing variables allow the health endpoint to start, but Slack/Gemini behavior
will not work until the required values are configured.

## Slack app configuration

1. Open <https://api.slack.com/apps> and create a Slack app for the workspace.
2. Under **OAuth & Permissions**, add bot scopes `app_mentions:read`,
   `chat:write`, `im:history`, and `im:read`.
3. Install the app in the workspace and put its Bot User OAuth Token in
   `SLACK_BOT_TOKEN`.
4. Under **Event Subscriptions**, enable events and set the Request URL to:
   `https://<deployed-url>/slack/events`
5. Subscribe to bot events `app_mention` and `message.im`.
   Slack delivers the DM subscription as a `message` payload with
   `channel_type=im`; `app.py` handles that delivery and ignores all other
   message events.
6. Save the configuration and invite Lyra to channels where she should answer.

The `/slack/events` route delegates URL verification and signature checking to
Slack Bolt's `SlackRequestHandler`.

## Deploy on Railway (recommended)

1. Create an account at <https://railway.app>.
2. Create a new project from a GitHub repository containing this folder, or
   deploy the folder with the Railway CLI.
3. In the service **Variables** panel, set `SLACK_BOT_TOKEN`,
   `SLACK_SIGNING_SECRET`, and `GEMINI_API_KEY`. Railway supplies `PORT`.
4. Railway installs `requirements.txt` and uses the `Procfile` command.
5. Copy the public HTTPS URL Railway gives the service.
6. In the Slack app's **Event Subscriptions**, enable events and set:
   `https://<railway-public-url>/slack/events`
7. Subscribe to `app_mention` and `message.im`, save, and reinstall the app if
   scopes changed.
8. Verify `https://<railway-public-url>/health`, then test in Slack.

## Deploy on Render (alternative)

1. Create a **Web Service** at <https://render.com> from the repository.
2. Use Python 3.11 or later.
3. Set the build command to `pip install -r requirements.txt`.
4. Set the start command to:
   `gunicorn --bind 0.0.0.0:$PORT app:flask_app`
5. Add `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, and `GEMINI_API_KEY` as
   environment variables. Render supplies `PORT`.
6. After deployment, set Slack's Request URL to
   `https://<render-service-url>/slack/events` and subscribe to `app_mention`
   and `message.im`.

## Deploy on Google Cloud Run (alternative)

From the directory containing `app.py`, run:

```bash
gcloud run deploy lyra-slack-bot \
  --source . \
  --region <region> \
  --allow-unauthenticated
```

After the service is created, set the three required variables under Cloud
Run **Variables & Secrets**. For production, store secret values in Secret
Manager rather than shell history. Use the Cloud Run service URL plus
`/slack/events` as Slack's Request URL and verify `/health` first.

## Future Databricks integration

The Databricks connector is listed for a future data layer but is intentionally
not imported or used in this release. The extension point is
`build_context_for_gemini` in `app.py`. A future implementation should query
approved aggregates, include period and sample size, enforce timeouts and
access controls, and keep all system-changing actions behind human approval.

## Security notes

- Never commit `.env`, tokens, signing secrets, or API keys.
- `.env.example` contains placeholders only.
- Do not put customer or operator personal data in prompts.
- The in-memory context resets on restart and is not shared between workers.
- Rotate Slack/Gemini credentials if they are exposed.
