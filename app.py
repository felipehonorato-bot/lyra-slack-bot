"""Lyra Slack bot: a thin Slack-to-Toqan Agent API relay."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("lyra-slack-bot")

TOQAN_BASE_URL = "https://api.toqan.ai/api"
TOQAN_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 12
PROCESSING_REACTION = "eyes"
DONE_REACTION = "white_check_mark"
ERROR_MESSAGE = "Não consegui processar agora, tente novamente"
EMPTY_ANSWER_MESSAGE = "Não consegui obter uma resposta agora."

# Slack Bolt can be imported and the health endpoint can run without credentials,
# which is useful for local smoke tests. Slack event handling still requires the
# real values in the deployment environment.
slack_app = App(
    token=os.getenv("SLACK_BOT_TOKEN") or "dev-token",
    signing_secret=os.getenv("SLACK_SIGNING_SECRET") or "dev-signing-secret",
    token_verification_enabled=bool(os.getenv("SLACK_BOT_TOKEN")),
)
slack_handler = SlackRequestHandler(slack_app)
flask_app = Flask(__name__)
app = flask_app
PORT = int(os.getenv("PORT", "3000"))

_MENTION_RE = re.compile(r"<@[A-Z0-9]+(?:\|[^>]+)?>")
_THINK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)
_IN_FLIGHT: set[str] = set()
_IN_FLIGHT_LOCK = threading.Lock()


class ToqanAPIError(RuntimeError):
    """Raised when the Toqan Agent API cannot complete a request."""


def _require_toqan_key() -> str:
    api_key = os.getenv("TOQAN_API_KEY")
    if not api_key:
        raise ToqanAPIError("TOQAN_API_KEY is not configured")
    return api_key


def _toqan_request(method: str, payload: dict[str, str]) -> dict[str, Any]:
    """Make one authenticated JSON request to the Toqan Agent API."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=f"{TOQAN_BASE_URL}/{method}",
        data=body,
        headers={
            "X-Api-Key": _require_toqan_key(),
            "Content-Type": "application/json",
        },
        method="POST" if method == "create_conversation" else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=TOQAN_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # Do not log the response body: it could contain user data or secrets.
        logger.error("Toqan API returned HTTP %s for %s", exc.code, method)
        raise ToqanAPIError(f"Toqan HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Toqan API request failed for %s: %s", method, exc)
        raise ToqanAPIError("Toqan request failed") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Toqan API returned invalid JSON for %s", method)
        raise ToqanAPIError("Toqan returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ToqanAPIError("Toqan returned an unexpected response")
    return data


def create_conversation(user_message: str) -> tuple[str, str]:
    """Start a new Toqan conversation for one Slack message."""
    data = _toqan_request("create_conversation", {"user_message": user_message})
    conversation_id = data.get("conversation_id")
    request_id = data.get("request_id")
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ToqanAPIError("Toqan response did not include conversation_id")
    if not isinstance(request_id, str) or not request_id:
        raise ToqanAPIError("Toqan response did not include request_id")
    return conversation_id, request_id


def get_answer(conversation_id: str, request_id: str) -> str:
    """Poll Toqan until the answer is finished or the poll limit is reached."""
    payload = {"conversation_id": conversation_id, "request_id": request_id}
    for attempt in range(MAX_POLL_ATTEMPTS):
        data = _toqan_request("get_answer", payload)
        if data.get("status") == "finished":
            answer = data.get("answer", "")
            if not isinstance(answer, str):
                raise ToqanAPIError("Toqan returned a non-text answer")
            return _clean_answer(answer)
        if attempt < MAX_POLL_ATTEMPTS - 1:
            logger.info("Toqan answer still in progress (poll %d/%d)", attempt + 1, MAX_POLL_ATTEMPTS)
            # This is intentionally a blocking wait in the worker thread, not in
            # Slack's acknowledgement request.
            time.sleep(POLL_INTERVAL_SECONDS)

    raise ToqanAPIError("Toqan answer polling timed out")


def _clean_answer(answer: str) -> str:
    """Remove internal reasoning tags before a response reaches Slack."""
    return _THINK_RE.sub("", answer).strip()


def _strip_mentions(text: str) -> str:
    return re.sub(r"\s+", " ", _MENTION_RE.sub("", text)).strip()


def _event_key(event: dict[str, Any]) -> str:
    return str(event.get("client_msg_id") or event.get("ts") or event.get("text") or "unknown")


def _say(say: Callable[..., Any], answer: str, event: dict[str, Any], in_thread: bool) -> None:
    if in_thread:
        thread_ts = event.get("thread_ts") or event.get("ts")
        say(text=answer, thread_ts=thread_ts)
    else:
        say(text=answer)


def _process_event(event: dict[str, Any], say: Callable[..., Any], in_thread: bool) -> None:
    """Relay one Slack event to Toqan and send the resulting answer."""
    event_key = _event_key(event)
    with _IN_FLIGHT_LOCK:
        if event_key in _IN_FLIGHT:
            return
        _IN_FLIGHT.add(event_key)

    question = _strip_mentions(str(event.get("text") or ""))
    try:
        if not question:
            _say(say, "Oi! Sou a Lyra. Como posso ajudar?", event, in_thread)
            return

        conversation_id, request_id = create_conversation(question)
        answer = get_answer(conversation_id, request_id)
        if not answer:
            answer = EMPTY_ANSWER_MESSAGE
        _say(say, answer, event, in_thread)
    except Exception:
        logger.exception("Lyra could not process Slack event")
        _say(say, ERROR_MESSAGE, event, in_thread)
    finally:
        with _IN_FLIGHT_LOCK:
            _IN_FLIGHT.discard(event_key)


def _dispatch(event: dict[str, Any], say: Callable[..., Any], client: Any, ack: Callable[[], Any]) -> None:
    """Acknowledge quickly, show processing state, and run the relay worker."""
    ack()
    channel = event.get("channel")
    timestamp = event.get("ts")
    if channel and timestamp:
        try:
            client.reactions_add(channel=channel, timestamp=timestamp, name=PROCESSING_REACTION)
        except Exception:
            logger.warning("Could not add processing reaction", exc_info=True)

    in_thread = event.get("channel_type") != "im"
    event_key = _event_key(event)

    def worker() -> None:
        try:
            _process_event(event, say, in_thread)
        finally:
            if channel and timestamp:
                try:
                    client.reactions_remove(channel=channel, timestamp=timestamp, name=PROCESSING_REACTION)
                except Exception:
                    logger.debug("Could not remove processing reaction", exc_info=True)
                try:
                    client.reactions_add(channel=channel, timestamp=timestamp, name=DONE_REACTION)
                except Exception:
                    logger.debug("Could not add done reaction", exc_info=True)

    # Keep the event acknowledgement fast while allowing the Toqan poll to run
    # for up to about one minute in the background.
    try:
        threading.Thread(target=worker, name=f"lyra-{event_key}", daemon=True).start()
    except Exception:
        logger.exception("Could not start Lyra worker")


@slack_app.event("app_mention")
def handle_app_mention(event, say, client, ack):
    _dispatch(event, say, client, ack)


@slack_app.event("message")
def handle_message(event, say, client, ack):
    if event.get("channel_type") == "im" and not event.get("bot_id") and not event.get("subtype"):
        _dispatch(event, say, client, ack)
    else:
        ack()


@flask_app.get("/")
@flask_app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "lyra-slack-bot"}), 200


@flask_app.post("/slack/events")
def slack_events():
    return slack_handler.handle(request)


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
