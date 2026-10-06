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
from datetime import datetime, time as datetime_time, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("lyra-slack-bot")

TOQAN_BASE_URL = "https://api.toqan.ai/api"
TOQAN_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 10
MAX_POLL_ATTEMPTS = 90
PROCESSING_REACTION = "eyes"
DONE_REACTION = "white_check_mark"
ERROR_MESSAGE = "Não consegui processar agora, tente novamente"
TIMEOUT_ERROR_MESSAGE = "Não consegui processar a tempo. Tente refazer a pergunta de forma mais específica."
EMPTY_ANSWER_MESSAGE = "Não consegui obter uma resposta agora."

DAILY_REPORT_CHANNEL = os.getenv("DAILY_REPORT_CHANNEL", "C0BF6JVFG7N")
DAILY_REPORT_HOUR = 11
DAILY_REPORT_PROMPT = (
    "Report diário de CSAT. Preciso do CSAT consolidado de todas as filas: "
    "CX Review, CX Review - AeC, CX Review - CSU, CX Suporte, CX Super Cliente - CSU, "
    "CX Super Cliente - AeC, Agentforce CX. Apresente o CSAT do dia anterior e do mês "
    "atual para cada fila, com total de avaliações, promotoras, detratoras e o CSAT "
    "consolidado. Considere o ajuste de fuso horário subtraindo 3 horas do "
    "csat_timestamp. Mostre também a diferença em relação à meta de 75%."
)
BRAZIL_TIMEZONE = ZoneInfo("America/Sao_Paulo")

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


def get_answer(
    conversation_id: str,
    request_id: str,
    progress_callback: Callable[[str], Any] | None = None,
) -> str:
    """Poll Toqan until the answer is finished or the poll limit is reached.

    ``progress_callback`` is optional so Slack workers can report long-running
    queries in the originating thread without coupling the Toqan client to
    Slack.
    """
    payload = {"conversation_id": conversation_id, "request_id": request_id}
    for attempt in range(MAX_POLL_ATTEMPTS):
        data = _toqan_request("get_answer", payload)
        if data.get("status") == "finished":
            answer = data.get("answer", "")
            if not isinstance(answer, str):
                raise ToqanAPIError("Toqan returned a non-text answer")
            return _clean_answer(answer)

        progress_message = {
            18: "Still processing, this is a complex query — hang tight...",
            42: "Still working on it, almost there...",
        }.get(attempt)
        if progress_message and progress_callback:
            try:
                progress_callback(progress_message)
            except Exception:
                logger.warning("Could not send Toqan progress message", exc_info=True)

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

        def send_progress(message: str) -> None:
            # Progress always replies in the originating thread, including for
            # events whose final answer is posted directly to a DM.
            _say(say, message, event, in_thread=True)

        answer = get_answer(conversation_id, request_id, progress_callback=send_progress)
        if not answer:
            answer = EMPTY_ANSWER_MESSAGE
        _say(say, answer, event, in_thread)
    except ToqanAPIError as exc:
        logger.exception("Lyra could not process Slack event")
        if "polling timed out" in str(exc):
            _say(say, TIMEOUT_ERROR_MESSAGE, event, in_thread)
        else:
            _say(say, ERROR_MESSAGE, event, in_thread)
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


def _next_run_time_brazil() -> float:
    """Return seconds until the next 09:00 in America/Sao_Paulo."""
    now_utc = datetime.now(timezone.utc)
    now_brazil = now_utc.astimezone(BRAZIL_TIMEZONE)
    target_date = now_brazil.date()
    if now_brazil.time() >= datetime_time(DAILY_REPORT_HOUR, 0):
        target_date += timedelta(days=1)
    target_brazil = datetime.combine(
        target_date,
        datetime_time(DAILY_REPORT_HOUR, 0),
        tzinfo=BRAZIL_TIMEZONE,
    )
    return max(0.0, (target_brazil.astimezone(timezone.utc) - now_utc).total_seconds())


def _run_daily_report() -> None:
    """Run and publish the scheduled CSAT report."""
    conversation_id, request_id = create_conversation(DAILY_REPORT_PROMPT)
    answer = get_answer(conversation_id, request_id)
    answer = _clean_answer(answer)
    if not answer:
        answer = EMPTY_ANSWER_MESSAGE
    slack_app.client.chat_postMessage(channel=DAILY_REPORT_CHANNEL, text=answer)


def _daily_report_loop() -> None:
    """Sleep until each 09:00 Brazil run and isolate failures per run."""
    while True:
        wait_seconds = _next_run_time_brazil()
        logger.info("Daily report: sleeping %.0fs until next 09:00 Brazil time", wait_seconds)
        time.sleep(wait_seconds)
        try:
            _run_daily_report()
        except Exception:
            logger.exception("Daily report failed")


def _start_daily_report_scheduler() -> None:
    """Start one daemon scheduler thread for this process."""
    thread = threading.Thread(target=_daily_report_loop, name="lyra-daily-report", daemon=True)
    thread.start()


if __name__ == "__main__":
    _start_daily_report_scheduler()
    flask_app.run(host="0.0.0.0", port=PORT)
