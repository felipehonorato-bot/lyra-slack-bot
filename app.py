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
MAX_POLL_ATTEMPTS = 180
PROCESSING_REACTION = "eyes"
DONE_REACTION = "white_check_mark"
ERROR_MESSAGE = "Não consegui processar agora, tente novamente"
TIMEOUT_ERROR_MESSAGE = "Não consegui processar a tempo. Tente refazer a pergunta de forma mais específica."
EMPTY_ANSWER_MESSAGE = "Não consegui obter uma resposta agora."
MOP_SUCCESS_MESSAGE = (
    "MOP atualizado com sucesso! Planilha atualizada: "
    "https://docs.google.com/spreadsheets/d/1Up11UQ1j0h9t8KW276AxJPGfEsShs9AsUztF5PAmyyE/edit?gid=0#gid=0"
)
MOP_CREDENTIALS_ERROR_MESSAGE = (
    "Não consigo atualizar o MOP agora — credenciais do Google não configuradas."
)
MOP_DOWNLOAD_ERROR_MESSAGE = "Não consegui baixar o arquivo. Tente enviar novamente."
MOP_READ_ERROR_MESSAGE = "Não consegui ler o arquivo Excel. Verifique se o formato está correto."
MOP_SHEETS_ERROR_MESSAGE = "Erro ao atualizar a planilha do MOP. Tente novamente."
MOP_SPREADSHEET_ID = "1Up11UQ1j0h9t8KW276AxJPGfEsShs9AsUztF5PAmyyE"
MOP_WORKSHEET_GID = 0
COMPROMISSOS_WORKSHEET_TITLE = "Compromissos"
COMPROMISSOS_HEADERS = [
    "Problema Identificado", "Ação Tomada", "Data Inicio", "Data Fim",
    "Duração", "Resultado Pré", "Resultado Pós", "Sucesso",
]
COMPROMISSOS_THREAD_DELAY_SECONDS = 2 * 60 * 60

DAILY_REPORT_CHANNEL = os.getenv("DAILY_REPORT_CHANNEL", "C0BF6JVFG7N")
DAILY_REPORT_HOUR = 11
DAILY_REPORT_PROMPT = (
    "COMPROMISSOS: use o bloco de contexto abaixo como fonte de verdade. "
    "Não peça plano novo para compromissos em andamento ou concluídos; cobre apenas sem resposta "
    "e peça para novos ofensores: ação · responsável · prazo na thread até 14h. "
    "Report diário de CSAT — execute o Bloco 3 do seu prompt (report de indicadores). "
    "Siga a estrutura completa: compromissos de ontem (se houver), CSAT por célula "
    "(mês, D-2, D-1 com variação), motivo de maior impacto em p.p., reincidência em Q4 "
    "e chamada para ação pedindo o plano da liderança na thread. "
    "Use formatação Slack (mrkdwn): negrito com *um asterisco*, bullets com •, "
    "separadores com • • •. Sem tabelas com |, sem **duplo asterisco**. "
    "Escreva como uma pessoa, frases curtas e diretas."
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
_REPORT_FOLLOWUP_THREADS: set[str] = set()
_REPORT_FOLLOWUP_LOCK = threading.Lock()


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
            42: "Ainda consultando o Databricks, quase lá...",
            72: "Demorando mais que o normal — a consulta é pesada, aguarde...",
            108: "Continuando a consulta, não desista — já estamos em 18 min...",
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
    """Return True for .xlsx attachments, checking name, mimetype and filetype."""
    name = str(file_info.get("name") or "").lower()
    mimetype = str(file_info.get("mimetype") or "").lower()
    filetype = str(file_info.get("filetype") or "").lower()
    if name.endswith(".xlsx"):
        return True
    if "spreadsheet" in mimetype or "excel" in mimetype:
        return True
    if filetype in ("xlsx", "xls", "excel"):
        return True
    logger.info("File not recognized as xlsx: name=%s mimetype=%s filetype=%s", name, mimetype, filetype)
    return False


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


def _workbook_rows(workbook_bytes: bytes) -> list[list[str]]:
    """Read the first worksheet and convert all cell values to strings."""
    try:
        from openpyxl import load_workbook
        from datetime import datetime, date, time as dtime

        workbook = load_workbook(io.BytesIO(workbook_bytes), data_only=False, read_only=True)
        worksheet = workbook.active
        rows: list[list[str]] = []
        for row in worksheet.iter_rows(values_only=True):
            converted = []
            for value in row:
                if value is None:
                    converted.append("")
                elif isinstance(value, dtime):
                    converted.append(value.strftime("%H:%M:%S"))
                elif isinstance(value, date):
                    converted.append(value.isoformat())
                elif isinstance(value, datetime):
                    converted.append(value.isoformat(sep=" "))
                else:
                    converted.append(str(value))
            rows.append(converted)
        workbook.close()
        return rows
    except Exception as exc:
        logger.error("Excel workbook could not be read: %s", exc)
        raise MOPReadError(str(exc)) from exc


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


def _compromissos_worksheet(spreadsheet: Any, create: bool = True) -> Any:
    """Return the commitments worksheet, creating it on first use."""
    try:
        return spreadsheet.worksheet(COMPROMISSOS_WORKSHEET_TITLE)
    except Exception as exc:
        # Keep the gspread import local so the app can still serve /health in a
        # minimal local environment without Google dependencies configured.
        try:
            import gspread
            worksheet_not_found = isinstance(exc, gspread.WorksheetNotFound)
        except Exception:
            worksheet_not_found = exc.__class__.__name__ == "WorksheetNotFound"
        if not worksheet_not_found or not create:
            raise
        return spreadsheet.add_worksheet(COMPROMISSOS_WORKSHEET_TITLE, rows=1000, cols=8)


def _today_brazil() -> datetime:
    return datetime.now(BRAZIL_TIMEZONE)


def _format_date(value: datetime) -> str:
    return value.strftime("%d/%m/%Y")


def _parse_commitment_date(value: Any, today: datetime | None = None) -> datetime | None:
    """Parse the human deadline formats accepted in a Slack commitment."""
    text = str(value or "").strip().lower()
    if not text or text in {"a definir", "sem prazo", "não informado", "nao informado", "—", "-"}:
        return None
    today = today or _today_brazil()
    if any(token in text for token in ("hoje", "today")):
        return today
    if "amanhã" in text or "amanha" in text or "tomorrow" in text:
        return today + timedelta(days=1)
    for pattern, fmt in ((r"\b(\d{1,2}/\d{1,2}/\d{4})\b", "%d/%m/%Y"),
                         (r"\b(\d{1,2}-\d{1,2}-\d{4})\b", "%d-%m-%Y"),
                         (r"\b(\d{4}-\d{1,2}-\d{1,2})\b", "%Y-%m-%d")):
        match = re.search(pattern, text)
        if match:
            try:
                return datetime.strptime(match.group(1), fmt).replace(tzinfo=BRAZIL_TIMEZONE)
            except ValueError:
                return None
    short_date = re.search(r"\b(\d{1,2})/(\d{1,2})\b", text)
    if short_date:
        try:
            return datetime(today.year, int(short_date.group(2)), int(short_date.group(1)), tzinfo=BRAZIL_TIMEZONE)
        except ValueError:
            return None
    return None


def _deadline_fields(deadline: Any, today: datetime | None = None) -> tuple[str, str]:
    today = today or _today_brazil()
    parsed = _parse_commitment_date(deadline, today)
    if parsed is None:
        return "a definir", "—"
    return _format_date(parsed), str(max(0, (parsed.date() - today.date()).days))


def _normalise_csat(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if "%" in text else f"{text}%"


def _row_value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _ensure_compromissos_headers(worksheet: Any) -> None:
    values = worksheet.get_all_values()
    if not values:
        worksheet.append_row(COMPROMISSOS_HEADERS, value_input_option="RAW")
        return
    current = [str(value).strip() for value in values[0][:len(COMPROMISSOS_HEADERS)]]
    if current != COMPROMISSOS_HEADERS:
        try:
            worksheet.update("A1:H1", [COMPROMISSOS_HEADERS], value_input_option="RAW")
        except TypeError:
            worksheet.update("A1:H1", [COMPROMISSOS_HEADERS])


def _save_compromissos(compromissos: list[dict[str, Any]], google_client: Any) -> None:
    """Append commitments using the exact eight-column sheet contract."""
    if not compromissos:
        return
    spreadsheet = google_client.open_by_key(MOP_SPREADSHEET_ID)
    worksheet = _compromissos_worksheet(spreadsheet)
    _ensure_compromissos_headers(worksheet)
    rows: list[list[str]] = []
    for commitment in compromissos:
        data_inicio = _row_value(commitment, "data_inicio", "data") or _format_date(_today_brazil())
        raw_deadline = _row_value(commitment, "data_fim", "prazo")
        action = _row_value(commitment, "acao", "acao_tomada") or "sem resposta"
        if action.lower() == "sem resposta" and raw_deadline in {"", "—", "-"}:
            data_fim, duracao = "—", "—"
        else:
            data_fim, _ = _deadline_fields(raw_deadline, _today_brazil())
            start_date = _parse_commitment_date(data_inicio, _today_brazil())
            end_date = _parse_commitment_date(data_fim, _today_brazil())
            duracao = str(max(0, (end_date.date() - start_date.date()).days)) if start_date and end_date else "—"
        rows.append([
            _row_value(commitment, "problema", "problema_identificado", "fila") or "Ofensor do report",
            action,
            data_inicio,
            data_fim,
            duracao,
            _normalise_csat(_row_value(commitment, "resultado_pre", "pre")) or "a definir",
            "",
            "a definir",
        ])
    if hasattr(worksheet, "append_rows"):
        worksheet.append_rows(rows, value_input_option="RAW")
    else:
        for row in rows:
            worksheet.append_row(row, value_input_option="RAW")


def _commitment_status(row: dict[str, str], today: datetime | None = None) -> str:
    today = today or _today_brazil()
    post = _row_value(row, "Resultado Pós", "resultado_pos")
    success = _row_value(row, "Sucesso", "sucesso").lower()
    if post and post.lower() not in {"a definir", "—", "-"}:
        return "concluído"
    deadline = _parse_commitment_date(_row_value(row, "Data Fim", "data_fim", "prazo"), today)
    action = _row_value(row, "Ação Tomada", "acao", "acao_tomada").lower()
    if action == "sem resposta":
        return "sem resposta"
    if deadline is not None and deadline.date() <= today.date():
        return "prazo vencido"
    if deadline is not None:
        return "prazo em andamento"
    return "prazo a definir" if success != "não" else "prazo vencido"


def _get_open_compromissos(google_client: Any) -> str:
    """Read every commitment and render lifecycle context for the daily prompt."""
    try:
        spreadsheet = google_client.open_by_key(MOP_SPREADSHEET_ID)
        worksheet = _compromissos_worksheet(spreadsheet, create=False)
        rows = worksheet.get_all_records()
    except Exception as exc:
        if exc.__class__.__name__ == "WorksheetNotFound":
            return ""
        logger.warning("Could not read commitments from Google Sheets: %s", exc)
        return ""
    if not rows:
        return ""
    today = _today_brazil()
    lines = ["COMPROMISSOS ABERTOS:"]
    for row in rows:
        problem = _row_value(row, "Problema Identificado", "problema") or "ofensor"
        action = _row_value(row, "Ação Tomada", "acao") or "sem resposta"
        deadline_text = _row_value(row, "Data Fim", "data_fim") or "a definir"
        status = _commitment_status(row, today)
        if status == "prazo em andamento":
            deadline = _parse_commitment_date(deadline_text, today)
            days = max(0, (deadline.date() - today.date()).days) if deadline else 0
            lines.append(f"- Em andamento: {problem} · {action} · prazo {deadline_text} · faltam {days} dias")
        elif status == "prazo vencido":
            pre = _row_value(row, "Resultado Pré", "resultado_pre") or "a definir"
            label = "vence hoje" if _parse_commitment_date(deadline_text, today) and _parse_commitment_date(deadline_text, today).date() == today.date() else "vencido"
            lines.append(f"- Prazo {label} em {deadline_text}: {problem} · {action} · CSAT foi de {pre} para a definir — verificar resultado")
        elif status == "concluído":
            pre = _row_value(row, "Resultado Pré", "resultado_pre") or "a definir"
            post = _row_value(row, "Resultado Pós", "resultado_pos")
            success = _row_value(row, "Sucesso", "sucesso") or "a definir"
            lines.append(f"- Concluído: {problem} · CSAT de {pre} para {post} — sucesso {success.lower()}")
        elif status == "sem resposta":
            lines.append(f"- Sem resposta: {problem} — cobrar novamente")
        else:
            lines.append(f"- Sem prazo definido: {problem} · {action} — pedir prazo")
    lines.extend([
        "", "No report, para ofensores em andamento, não peça novo plano — só dê update do status.",
        "Para ofensores vencidos, compare Pré vs Pós e diga se funcionou.",
        "Para sem resposta, cobre novamente.",
        "Para novos, peça o plano no formato ação · responsável · prazo na thread até 14h.", "",
    ])
    return "\n".join(lines)



def _worksheet_rows_with_header(worksheet: Any) -> list[tuple[int, dict[str, str]]]:
    values = worksheet.get_all_values()
    if not values:
        return []
    headers = [str(value).strip() for value in values[0]]
    return [(n, {h: str(row[i]) if i < len(row) else "" for i, h in enumerate(headers) if h})
            for n, row in enumerate(values[1:], start=2)]


def _update_compromisso_cells(worksheet: Any, row_number: int, resultado_pos: str, sucesso: str) -> None:
    worksheet.update_cell(row_number, 7, resultado_pos)
    worksheet.update_cell(row_number, 8, sucesso)


def _extract_csat_for_commitment(report_text: str, problem: str, fallback: Any = None) -> str:
    if isinstance(fallback, dict):
        for key, value in fallback.items():
            if str(key).lower() in problem.lower() or problem.lower() in str(key).lower():
                return _normalise_csat(value)
    if fallback is not None and not isinstance(fallback, dict):
        return _normalise_csat(fallback)
    relevant = [line for line in str(report_text or "").splitlines() if any(token.lower() in line.lower() for token in str(problem).split() if len(token) > 3)]
    percentages = re.findall(r"(?<!\d)(\d{1,3}(?:[,.]\d+)?)\s*%", " ".join(relevant))
    if len(percentages) == 1:
        return _normalise_csat(percentages[0])
    # A small report/test response may contain one unlabelled D-1 value. Use
    # it; with several values we leave the row open rather than guessing a fila.
    all_percentages = re.findall(r"(?<!\d)(\d{1,3}(?:[,.]\d+)?)\s*%", str(report_text or ""))
    return _normalise_csat(all_percentages[0]) if len(all_percentages) == 1 else ""


def _check_deadline_compromissos(google_client: Any, report_text: str = "", csat_by_problem: dict[str, Any] | None = None) -> int:
    """Fill Resultado Pós/Sucesso for commitments due today or already overdue."""
    try:
        worksheet = _compromissos_worksheet(google_client.open_by_key(MOP_SPREADSHEET_ID), create=False)
        updated = 0
        today = _today_brazil()
        for row_number, row in _worksheet_rows_with_header(worksheet):
            if _row_value(row, "Resultado Pós", "resultado_pos") not in {"", "a definir"}:
                continue
            deadline = _parse_commitment_date(_row_value(row, "Data Fim", "data_fim"), today)
            if deadline is None or deadline.date() > today.date():
                continue
            problem = _row_value(row, "Problema Identificado", "problema")
            post = _extract_csat_for_commitment(report_text, problem, csat_by_problem)
            if not post:
                continue
            pre = _extract_csat_for_commitment("", problem, _row_value(row, "Resultado Pré", "resultado_pre"))
            def number(value: str) -> float | None:
                match = re.search(r"\d+(?:[,.]\d+)?", value or "")
                return float(match.group(0).replace(",", ".")) if match else None
            pre_num, post_num = number(pre), number(post)
            if pre_num is None or post_num is None:
                continue
            _update_compromisso_cells(worksheet, row_number, post, "Sim" if post_num > pre_num else "Não")
            updated += 1
        return updated
    except Exception as exc:
        if exc.__class__.__name__ != "WorksheetNotFound":
            logger.warning("Could not check commitment deadlines: %s", exc)
        return 0


def _human_thread_messages(messages: list[dict[str, Any]], report_ts: str) -> list[str]:
    """Extract human replies while excluding the report parent and bot posts."""
    texts: list[str] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("ts") == report_ts:
            continue
        if message.get("bot_id") or message.get("bot_profile") or message.get("subtype") == "bot_message":
            continue
        text = str(message.get("text") or "").strip()
        if text:
            texts.append(text)
    return texts


def _commitments_from_thread(messages: list[dict[str, Any]], report_ts: str) -> list[dict[str, str]]:
    """Parse `ação · responsável · prazo`, including replies with no prazo."""
    commitments: list[dict[str, str]] = []
    for text in _human_thread_messages(messages, report_ts):
        parsed_line = False
        for line in text.splitlines():
            if "·" not in line:
                continue
            parts = [part.strip() for part in line.split("·", 2)]
            if len(parts) >= 2 and parts[0]:
                commitments.append({
                    "acao": parts[0],
                    "responsavel": parts[1] or "Liderança",
                    "prazo": parts[2] if len(parts) == 3 and parts[2] else "a definir",
                })
                parsed_line = True
        if not parsed_line:
            commitments.append({"acao": text[:200], "responsavel": "Liderança", "prazo": "a definir"})
    return commitments


def _report_problem(parent_text: str) -> str:
    for line in str(parent_text or "").splitlines():
        if "%" in line and line.strip().startswith(('-', '•', '*')):
            return re.sub(r"^[\-•*\s]+", "", line).strip()[:200]
    return "Ofensor do report"


def _read_report_thread(channel_id: str, report_ts: str) -> None:
    """Read a report thread after two hours and persist the full commitment lifecycle."""
    try:
        response = slack_app.client.conversations_replies(channel=channel_id, ts=report_ts)
        messages = response.get("messages", []) if isinstance(response, dict) else []
        if not isinstance(messages, list):
            messages = []
        parent_text = next((str(m.get("text") or "") for m in messages if isinstance(m, dict) and m.get("ts") == report_ts), "")
        human_texts = _human_thread_messages(messages, report_ts)
        google_client = _get_google_client()
        if google_client is None:
            return
        pre = _extract_csat_for_commitment(parent_text, _report_problem(parent_text))
        # No reply creates a silent `sem resposta` row; only missing deadlines
        # receive a follow-up question in the thread.
        if human_texts:
            parsed = _commitments_from_thread(messages, report_ts)
            commitments = [{"problema": _report_problem(parent_text), "data_inicio": _format_date(_today_brazil()), "resultado_pre": pre, "thread_ts": report_ts, **item} for item in parsed]
            _save_compromissos(commitments, google_client)
            if any(str(item.get("prazo")) == "a definir" for item in parsed):
                slack_app.client.chat_postMessage(channel=channel_id, text="Qual o prazo para essa ação?", thread_ts=report_ts)
            slack_app.client.chat_postMessage(channel=channel_id, text=f"Registrado: {len(commitments)} compromissos.", thread_ts=report_ts)
        else:
            _save_compromissos([{"problema": _report_problem(parent_text), "data_inicio": _format_date(_today_brazil()), "acao": "sem resposta", "prazo": "—", "resultado_pre": pre, "thread_ts": report_ts}], google_client)
    except Exception:
        logger.exception("Failed to read report thread for commitments")

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
    except MOPGoogleCredentialsError as exc:
        detail = str(exc) if str(exc) else ""
        msg = f"Erro credenciais Google: {detail}" if detail else MOP_CREDENTIALS_ERROR_MESSAGE
        logger.warning("MOP upload: Google credentials error: %s", detail)
        _say(say, msg, event, in_thread=True)
    except MOPDownloadError as exc:
        detail = str(exc) if str(exc) else ""
        msg = f"Erro ao baixar arquivo: {detail}" if detail else MOP_DOWNLOAD_ERROR_MESSAGE
        logger.warning("MOP upload could not download Slack file: %s", detail)
        _say(say, msg, event, in_thread=True)
    except MOPReadError as exc:
        detail = str(exc) if str(exc) else ""
        msg = f"Erro ao ler Excel: {detail}" if detail else MOP_READ_ERROR_MESSAGE
        logger.warning("MOP upload: Excel read error: %s", detail)
        _say(say, msg, event, in_thread=True)
    except MOPSheetsError as exc:
        detail = str(exc) if str(exc) else ""
        msg = f"Erro ao atualizar MOP: {detail}" if detail else MOP_SHEETS_ERROR_MESSAGE
        logger.warning("MOP upload could not update Google Sheets: %s", detail)
        _say(say, msg, event, in_thread=True)
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


@flask_app.get("/debug/create-compromissos")
def debug_create_compromissos():
    """Create the Compromissos worksheet if it doesn't exist. Temporary debug endpoint."""
    try:
        google_client = _get_google_client()
        if google_client is None:
            return jsonify({"error": "Google credentials not configured"}), 500
        spreadsheet = google_client.open_by_key(MOP_SPREADSHEET_ID)
        worksheet = _compromissos_worksheet(spreadsheet, create=True)
        return jsonify({"ok": True, "worksheet": worksheet.title, "id": worksheet.id})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


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
            spreadsheet = gc.open_by_key("1Up11UQ1j0h9t8KW276AxJPGfEsShs9AsUztF5PAmyyE")
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
    """Run and publish the CSAT report, updating commitment deadlines from it."""
    google_client = None
    try:
        google_client = _get_google_client()
    except Exception:
        logger.warning("Daily report: Google Sheets unavailable; skipping commitments", exc_info=True)

    compromissos_text = ""
    if google_client is not None:
        try:
            spreadsheet = google_client.open_by_key(MOP_SPREADSHEET_ID)
            worksheet = _compromissos_worksheet(spreadsheet)
            _ensure_compromissos_headers(worksheet)
            compromissos_text = _get_open_compromissos(google_client)
        except Exception:
            logger.warning("Daily report: could not prepare commitments", exc_info=True)

    prompt = compromissos_text + ("\n\n" if compromissos_text else "") + DAILY_REPORT_PROMPT
    conversation_id, request_id = create_conversation(prompt)
    answer = _clean_answer(get_answer(conversation_id, request_id)) or EMPTY_ANSWER_MESSAGE

    # The report already contains D-1 CSAT by fila. Use it as the lifecycle
    # source of truth for due/overdue commitments; a missing match remains open
    # and is retried on the next report rather than being guessed.
    if google_client is not None:
        try:
            _check_deadline_compromissos(google_client, answer)
        except Exception:
            logger.warning("Daily report: could not update commitment deadlines", exc_info=True)

    response = slack_app.client.chat_postMessage(channel=DAILY_REPORT_CHANNEL, text=answer)
    report_ts = response.get("ts") or response.get("message", {}).get("ts") if isinstance(response, dict) else None
    if report_ts:
        with _REPORT_FOLLOWUP_LOCK:
            _REPORT_FOLLOWUP_THREADS.add(report_ts)
        try:
            threading.Timer(
                COMPROMISSOS_THREAD_DELAY_SECONDS,
                _read_report_thread,
                args=(DAILY_REPORT_CHANNEL, report_ts),
            ).start()
        except Exception:
            logger.exception("Could not schedule commitment thread read")



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
