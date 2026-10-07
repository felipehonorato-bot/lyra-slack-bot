"""Lyra Slack bot: a thin Slack-to-Toqan Agent API relay."""
from __future__ import annotations

import json
import logging
import os
import re
import base64
import io
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
MOP_SUCCESS_MESSAGE = (
    "MOP atualizado com sucesso! Planilha atualizada: "
    "https://docs.google.com/spreadsheets/d/1cy23m4iN0D7vEiJbbAw9hRpUtaHgGuRew_fgAUz_l14/edit?gid=469945566#gid=469945566"
)
MOP_CREDENTIALS_ERROR_MESSAGE = (
    "Não consigo atualizar o MOP agora — credenciais do Google não configuradas."
)
MOP_DOWNLOAD_ERROR_MESSAGE = "Não consegui baixar o arquivo. Tente enviar novamente."
MOP_READ_ERROR_MESSAGE = "Não consegui ler o arquivo Excel. Verifique se o formato está correto."
MOP_SHEETS_ERROR_MESSAGE = "Erro ao atualizar a planilha do MOP. Tente novamente."
MOP_SPREADSHEET_ID = "1cy23m4iN0D7vEiJbbAw9hRpUtaHgGuRew_fgAUz_l14"
MOP_WORKSHEET_GID = 469945566

DAILY_REPORT_CHANNEL = os.getenv("DAILY_REPORT_CHANNEL", "C0BF6JVFG7N")
DAILY_REPORT_HOUR = 11
DAILY_REPORT_PROMPT = (
    "Report diário de CSAT. Formato curto e direto, como uma mensagem de Slack.\n\n"
    "Para cada fila (CX Review, CX Review - AeC, CX Review - CSU, CX Suporte, "
    "CX Super Cliente - CSU, CX Super Cliente - AeC, Agentforce CX), mostre:\n"
    "- CSAT do dia anterior (D-1) e CSAT do mês (MTD), com n e gap para a meta de 75%\n"
    "- Ajuste de fuso: subtrair 3 horas do csat_timestamp\n\n"
    "Formato: uma linha por fila, curta. Exemplo:\n"
    "*CX Suporte* — D-1: 60,3% (n=63) | MTD: 61,3% (n=204, gap: -13,7 p.p.)\n\n"
    "No final, um bullet curto com o principal alerta se houver.\n"
    "Sem tabelas, sem code blocks, sem listas longas. Texto direto como uma pessoa escreveria.\n"
    "Se algo estiver crítico (CSAT abaixo de 50% ou gap maior que -20 p.p.), sinalize com ⚠️.\n"
    "Máximo 15 linhas."
)

MOP_CHECK_MESSAGE = (
    "Bom dia! ☀️ Report de CSAT enviado acima. \n\n"
    "Outra coisa: temos MOP atualizado? Se sim, me envie o arquivo Excel "
    "marcando a Lyra que eu atualizo a planilha. Se não tiver atualizado, "
    "tudo bem — segue o dia! 📋"
)
MOP_CHECK_HOUR = 14
MOP_CHECK_DAY = 1  # Monday=0, Tuesday=1, ..., Sunday=6

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
            18: "Ainda processando — essa é uma consulta complexa, só um momento...",
            42: "Quase lá, finalizando a consulta...",
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


class MOPGoogleCredentialsError(RuntimeError):
    """Raised when the Google service-account configuration is absent."""


class MOPDownloadError(RuntimeError):
    """Raised when an attached Slack file cannot be downloaded."""


class MOPReadError(RuntimeError):
    """Raised when the attached workbook cannot be read."""


class MOPSheetsError(RuntimeError):
    """Raised when the destination Google Sheet cannot be updated."""


def _get_google_client():
    """Create the Google client from the service-account JSON (base64 or raw), if set."""
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not raw:
        return None
    try:
        # Try base64 first, then raw JSON
        try:
            credentials_json = json.loads(base64.b64decode(raw))
        except Exception:
            credentials_json = json.loads(raw)
        from google.oauth2.service_account import Credentials
        import gspread

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(credentials_json, scopes=scopes)
        return gspread.authorize(credentials)
    except Exception as exc:
        logger.error("Could not configure Google Sheets client: %s", exc)
        raise MOPGoogleCredentialsError(str(exc)) from exc


def _is_xlsx_attachment(file_info: dict[str, Any]) -> bool:
    """Return True only for .xlsx attachments; other files use normal chat flow."""
    name = str(file_info.get("name") or "")
    return name.lower().endswith(".xlsx")


def _download_slack_file(file_info: dict[str, Any], client: Any) -> bytes:
    """Fetch a Slack file using files.info metadata and its private download URL."""
    details = dict(file_info)
    file_id = details.get("id")
    if file_id and client is not None:
        try:
            response = client.files_info(file=file_id)
            remote_file = response.get("file") if isinstance(response, dict) else None
            if isinstance(remote_file, dict):
                details.update(remote_file)
        except Exception as exc:
            logger.warning("Slack files.info failed for attached file: %s", exc)
            raise MOPDownloadError from exc

    file_url = details.get("url_private_download") or details.get("url_private")
    if not file_url:
        raise MOPDownloadError("Slack file has no private download URL")

    headers = {}
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if slack_token:
        headers["Authorization"] = f"Bearer {slack_token}"
    request = urllib.request.Request(str(file_url), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TOQAN_TIMEOUT_SECONDS) as response:
            content = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        logger.error("Slack file download failed")
        raise MOPDownloadError from exc
    if not content:
        raise MOPDownloadError("Slack file download was empty")
    return content


def _workbook_rows(workbook_bytes: bytes) -> list[list[Any]]:
    """Read the first worksheet and make cell values JSON-safe for Sheets."""
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(workbook_bytes), data_only=False, read_only=True)
        worksheet = workbook.active
        rows: list[list[Any]] = []
        for row in worksheet.iter_rows(values_only=True):
            converted = []
            for value in row:
                if isinstance(value, (datetime,)):
                    converted.append(value.isoformat(sep=" "))
                elif value is None:
                    converted.append("")
                else:
                    converted.append(value)
            rows.append(converted)
        workbook.close()
        return rows
    except Exception as exc:
        logger.error("Excel workbook could not be read")
        raise MOPReadError from exc


def _worksheet_by_gid(spreadsheet: Any, worksheet_gid: int) -> Any:
    """Find a worksheet by numeric gid, supporting gspread API variants."""
    get_by_id = getattr(spreadsheet, "get_worksheet_by_id", None)
    if callable(get_by_id):
        worksheet = get_by_id(worksheet_gid)
        if worksheet is not None:
            return worksheet
    for worksheet in spreadsheet.worksheets():
        if int(worksheet.id) == worksheet_gid:
            return worksheet
    raise MOPSheetsError(f"Worksheet gid {worksheet_gid} was not found")


def _update_mop_sheet(workbook_bytes: bytes, google_client: Any = None) -> None:
    """Replace destination worksheet values with the first worksheet's Excel rows."""
    if google_client is None:
        google_client = _get_google_client()
    if google_client is None:
        raise MOPGoogleCredentialsError

    rows = _workbook_rows(workbook_bytes)
    try:
        spreadsheet = google_client.open_by_key(MOP_SPREADSHEET_ID)
        worksheet = _worksheet_by_gid(spreadsheet, MOP_WORKSHEET_GID)
        # Clear existing data
        worksheet.clear()
        if rows:
            # Use append_rows for better compatibility across gspread versions
            worksheet.append_rows(rows, value_input_option="RAW")
        logger.info("MOP sheet updated with %d rows", len(rows))
    except MOPSheetsError:
        raise
    except Exception as exc:
        logger.error("Google Sheets MOP update failed: %s", exc)
        raise MOPSheetsError(str(exc)) from exc


def _mop_attachment(event: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first .xlsx file in an event, or None for ordinary messages."""
    files = event.get("files") or []
    if not isinstance(files, list):
        return None
    return next((file_info for file_info in files if isinstance(file_info, dict) and _is_xlsx_attachment(file_info)), None)


def _process_mop_upload(event: dict[str, Any], client: Any) -> str | None:
    """Process one xlsx mention; return None when the event is not an Excel upload."""
    attachment = _mop_attachment(event)
    if attachment is None:
        return None
    google_client = _get_google_client()
    if google_client is None:
        raise MOPGoogleCredentialsError
    workbook_bytes = _download_slack_file(attachment, client)
    _update_mop_sheet(workbook_bytes, google_client)
    return MOP_SUCCESS_MESSAGE


def _say(say: Callable[..., Any], answer: str, event: dict[str, Any], in_thread: bool) -> None:
    if in_thread:
        thread_ts = event.get("thread_ts") or event.get("ts")
        say(text=answer, thread_ts=thread_ts)
    else:
        say(text=answer)


def _process_event(
    event: dict[str, Any],
    say: Callable[..., Any],
    in_thread: bool,
    client: Any = None,
) -> None:
    """Process an Excel MOP upload or relay an ordinary event to Toqan."""
    event_key = _event_key(event)
    with _IN_FLIGHT_LOCK:
        if event_key in _IN_FLIGHT:
            return
        _IN_FLIGHT.add(event_key)

    question = _strip_mentions(str(event.get("text") or ""))
    try:
        mop_answer = _process_mop_upload(event, client)
        if mop_answer is not None:
            _say(say, mop_answer, event, in_thread=True)
            return

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
    except MOPGoogleCredentialsError:
        logger.warning("MOP upload skipped because Google credentials are not configured")
        _say(say, MOP_CREDENTIALS_ERROR_MESSAGE, event, in_thread=True)
    except MOPDownloadError:
        logger.warning("MOP upload could not download the Slack file")
        _say(say, MOP_DOWNLOAD_ERROR_MESSAGE, event, in_thread=True)
    except MOPReadError:
        logger.warning("MOP upload contained an unreadable Excel workbook")
        _say(say, MOP_READ_ERROR_MESSAGE, event, in_thread=True)
    except MOPSheetsError:
        logger.warning("MOP upload could not update Google Sheets")
        _say(say, MOP_SHEETS_ERROR_MESSAGE, event, in_thread=True)
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
            _process_event(event, say, in_thread, client)
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


@flask_app.get("/debug/mop")
def debug_mop():
    """Debug endpoint to check Google Sheets connection — temporary."""
    import base64 as b64
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    result = {"env_set": bool(raw), "env_length": len(raw)}
    
    # Check if it's base64 or raw JSON
    if raw:
        try:
            decoded = b64.b64decode(raw)
            creds_json = json.loads(decoded)
            result["format"] = "base64"
        except Exception:
            try:
                creds_json = json.loads(raw)
                result["format"] = "raw_json"
            except Exception as e:
                result["format"] = "INVALID"
                result["error"] = str(e)
                return jsonify(result), 200
        
        result["client_email"] = creds_json.get("client_email", "NOT FOUND")
        result["has_private_key"] = bool(creds_json.get("private_key"))
        
        # Try to connect
        try:
            from google.oauth2.service_account import Credentials
            import gspread
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
            gc = gspread.authorize(creds)
            spreadsheet = gc.open_by_key("1cy23m4iN0D7vEiJbbAw9hRpUtaHgGuRew_fgAUz_l14")
            result["sheets_ok"] = True
            result["spreadsheet_title"] = spreadsheet.title
            worksheets = spreadsheet.worksheets()
            result["worksheets"] = [{"name": ws.title, "gid": ws.id} for ws in worksheets]
        except Exception as e:
            result["sheets_ok"] = False
            result["sheets_error"] = f"{type(e).__name__}: {str(e)}"
    
    return jsonify(result), 200


@flask_app.post("/slack/events")
def slack_events():
    return slack_handler.handle(request)


def _next_run_time_brazil() -> float:
    """Return seconds until the next 11:00 in America/Sao_Paulo."""
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
    """Run and publish the scheduled CSAT report, then ask about MOP."""
    # 1. Post CSAT report
    conversation_id, request_id = create_conversation(DAILY_REPORT_PROMPT)
    answer = get_answer(conversation_id, request_id)
    answer = _clean_answer(answer)
    if not answer:
        answer = EMPTY_ANSWER_MESSAGE
    slack_app.client.chat_postMessage(channel=DAILY_REPORT_CHANNEL, text=answer)



def _next_mop_run_time() -> float:
    """Seconds until next Tuesday 14:00 Brazil time."""
    now_brazil = datetime.now(BRAZIL_TIMEZONE)
    days_ahead = MOP_CHECK_DAY - now_brazil.weekday()
    if days_ahead < 0 or (days_ahead == 0 and now_brazil.hour >= MOP_CHECK_HOUR):
        days_ahead += 7
    target = datetime(
        now_brazil.year, now_brazil.month, now_brazil.day,
        MOP_CHECK_HOUR, 0, 0, tzinfo=BRAZIL_TIMEZONE,
    ) + timedelta(days=days_ahead)
    return max(0.0, (target.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds())


def _mop_check_loop() -> None:
    """Sleep until each Tuesday 14:00 Brazil and post MOP check."""
    while True:
        wait_seconds = _next_mop_run_time()
        logger.info("MOP check: sleeping %.0fs until next Tuesday 14:00 Brazil time", wait_seconds)
        time.sleep(wait_seconds)
        try:
            slack_app.client.chat_postMessage(channel=DAILY_REPORT_CHANNEL, text=MOP_CHECK_MESSAGE)
        except Exception:
            logger.exception("MOP check post failed")


def _start_mop_scheduler() -> None:
    """Start daemon thread for weekly MOP check."""
    thread = threading.Thread(target=_mop_check_loop, name="lyra-mop-check", daemon=True)
    thread.start()


def _daily_report_loop() -> None:
    """Sleep until each 11:00 Brazil run and isolate failures per run."""
    while True:
        wait_seconds = _next_run_time_brazil()
        logger.info("Daily report: sleeping %.0fs until next 11:00 Brazil time", wait_seconds)
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
    _start_mop_scheduler()
    flask_app.run(host="0.0.0.0", port=PORT)
