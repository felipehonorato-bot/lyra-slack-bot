"""Lyra Slack bot — relay Slack <-> Toqan + rotinas de gestão das EPSs (v3.5).

v3.5 — duas planilhas: MOP oficial em MOP_SPREADSHEET_ID (aba MOP Consolidado);
Compromissos, Estado Lyra e MOP backup em LYRA_SPREADSHEET_ID.

v3.4 — MOP pelo fluxo "Reportar Oráculo": o Excel postado na thread do chamado de MOP
(MOP_FLOW_CHANNEL) é lido sozinho; sem cobrança de MOP nos canais; aviso só por DM
se o MOP não for atualizado até 18h do 1º dia útil / dia 15.

v3.3 — conversa: a Lyra fala como gestora; o app sempre informa a situação do MOP
(números, "ainda não enviado" ou "não deu para consultar") em vez de omitir.

v3.2 — segregação por EPS:
- EPS_CHANNELS mapeia cada EPS ao seu canal. Report, leitura de thread,
  compromissos, cobrança de MOP e conversa ficam isolados por EPS.
- Toda mensagem ao Toqan leva um bloco ESCOPO; em canal de EPS os dados são
  filtrados pelo e-mail do operador (aec / csu) e só as células da EPS aparecem.
- Upload de MOP no canal de uma EPS troca só as linhas daquela EPS.
- DM só para DM_ALLOWED_USERS; canal não configurado não recebe resposta.

O que mudou na v3.1 (sustentação):
- Agendador único, resistente a restart: o estado de cada rotina fica na aba
  "Estado Lyra" da planilha, então um redeploy não perde leituras de thread
  nem duplica o report.
- Report dividido em mensagem principal + thread (delimitador ===THREAD===).
  Falha de consulta não é publicada como report; vira alerta.
- Ciclo de compromissos com Fila, Responsável e Thread; CSAT pré/pós por fila
  (lido das linhas "• *Fila:* Mês X% · D-1 Y%" do report).
- Respostas tardias atualizam o compromisso existente (ex.: prazo informado
  depois) em vez de duplicar; "sem resposta" é encerrado quando a liderança
  responde.
- Upload de MOP: lê valores (não fórmulas), escolhe a aba certa, valida
  colunas, faz backup antes de substituir e pode ser restrito a canais.
- Endpoints de debug protegidos por token.
- Feriados nacionais respeitados na cobrança do MOP.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("lyra-slack-bot")

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
BRAZIL_TIMEZONE = ZoneInfo("America/Sao_Paulo")

TOQAN_BASE_URL = "https://api.toqan.ai/api"
TOQAN_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 10
MAX_POLL_ATTEMPTS = 180  # 180 x 10s = 30 minutos
PROCESSING_REACTION = "eyes"
DONE_REACTION = "white_check_mark"
ERROR_MESSAGE = "Não consegui processar agora, tente novamente"
TIMEOUT_ERROR_MESSAGE = "Não consegui processar a tempo. Tente refazer a pergunta de forma mais específica."
EMPTY_ANSWER_MESSAGE = "Não consegui obter uma resposta agora."

DAILY_REPORT_CHANNEL = os.getenv("DAILY_REPORT_CHANNEL", "C0BF6JVFG7N")
ALERT_CHANNEL = os.getenv("ALERT_CHANNEL", "").strip()
DEBUG_TOKEN = os.getenv("DEBUG_TOKEN", "").strip()


def _parse_channel_map(raw: str) -> dict[str, str]:
    """'AeC:C111,CSU:C222' -> {'AeC': 'C111', 'CSU': 'C222'}"""
    result: dict[str, str] = {}
    for part in raw.split(","):
        if ":" in part:
            name, channel = part.split(":", 1)
            if name.strip() and channel.strip():
                result[name.strip()] = channel.strip()
    return result


def _parse_id_list(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


# --- Segregação por EPS -------------------------------------------------------
# Cada EPS tem o próprio canal; nada de uma EPS aparece no canal da outra.
EPS_CHANNELS = _parse_channel_map(os.getenv("EPS_CHANNELS", ""))
# Canal interno iFood com report consolidado (todas as EPS). Vazio = desligado.
CONSOLIDATED_CHANNEL = os.getenv("CONSOLIDATED_CHANNEL", "").strip()
# Outros canais internos onde a Lyra responde com visão completa.
INTERNAL_CHANNELS = _parse_id_list(os.getenv("INTERNAL_CHANNELS", "")) | (
    {CONSOLIDATED_CHANNEL} if CONSOLIDATED_CHANNEL else set()
)
# Quem pode falar com a Lyra por DM (visão completa). Padrão: o ALERT_CHANNEL, se for um usuário.
DM_ALLOWED_USERS = _parse_id_list(os.getenv("DM_ALLOWED_USERS", "")) or (
    {ALERT_CHANNEL} if ALERT_CHANNEL.startswith("U") else set()
)
CONSOLIDATED = "Consolidado"

# Células de cada EPS (fonte: Felipe, out/2026). O nome da EPS também é o trecho
# procurado no e-mail do operador ("aec" em @if-aec..., "csu" em ...csu...).
EPS_CELULAS: dict[str, list[str]] = {
    "AeC": [
        "CX Suporte", "Madrugada", "CX Review - AeC", "CX Super Cliente - AeC",
        "Fila desativada 37 - Canarinhos",
    ],
    "CSU": [
        "Review", "CX Review - CSU", "CX Super Cliente - CSU", "PF Cancelamento",
        "PF Super Clientes", "PF Revisão Manual", "CX Denúncia", "Fraudes DX",
        "DX - PF Contestação", "DX - PF Contestação Bloqueio temporário",
    ],
}


class Tenant:
    """Um destino de report: uma EPS (eps='AeC') ou a visão consolidada (eps=None)."""

    def __init__(self, key: str, channel: str, eps: str | None) -> None:
        self.key, self.channel, self.eps = key, channel, eps

    def __repr__(self) -> str:
        return f"Tenant({self.key}, {self.channel})"


def _build_tenants() -> list[Tenant]:
    tenants = [Tenant(eps, channel, eps) for eps, channel in EPS_CHANNELS.items()]
    if CONSOLIDATED_CHANNEL:
        tenants.append(Tenant(CONSOLIDATED, CONSOLIDATED_CHANNEL, None))
    if not tenants:  # legado: um canal só, sem recorte de EPS
        tenants.append(Tenant(CONSOLIDATED, DAILY_REPORT_CHANNEL, None))
    return tenants


TENANTS = _build_tenants()
# canal -> EPS do canal (None = visão completa)
CHANNEL_SCOPE: dict[str, str | None] = {t.channel: t.eps for t in TENANTS}
CHANNEL_SCOPE.update({channel: None for channel in INTERNAL_CHANNELS})

DM_NOT_ALLOWED_MESSAGE = "Por aqui eu não consigo responder. Me chama no canal da sua EPS que eu te ajudo por lá. 🙂"
CHANNEL_NOT_CONFIGURED_MESSAGE = "Ainda não estou configurada para responder neste canal."

# --- MOP ---------------------------------------------------------------------
# Planilha da Lyra: Compromissos, Estado Lyra e MOP backup
LYRA_SPREADSHEET_ID = os.getenv("LYRA_SPREADSHEET_ID", "1Up11UQ1j0h9t8KW276AxJPGfEsShs9AsUztF5PAmyyE")
# Planilha do MOP oficial (aba "MOP Consolidado")
MOP_SPREADSHEET_ID = os.getenv("MOP_SPREADSHEET_ID", "1cy23m4iN0D7vEiJbbAw9hRpUtaHgGuRew_fgAUz_l14")
MOP_WORKSHEET_GID = int(os.getenv("MOP_WORKSHEET_GID", "464304384"))
MOP_SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/{MOP_SPREADSHEET_ID}/edit?gid={MOP_WORKSHEET_GID}#gid={MOP_WORKSHEET_GID}"
)
MOP_BACKUP_WORKSHEET_TITLE = "MOP backup"
MOP_ALLOWED_CHANNELS = {c.strip() for c in os.getenv("MOP_ALLOWED_CHANNELS", "").split(",") if c.strip()}
MOP_REQUIRED_COLUMNS = ("Nome", "Email")
MOP_EXPECTED_COLUMNS = (
    "Nome", "Email", "Pilar", "Célula", "EPS", "Supervisor", "Coordenador",
    "Entrada", "Saída", "Status", "Versão do Oráculo", "Formato de Trabalho",
)
MOP_HEADER_SCAN_ROWS = 10

MOP_CREDENTIALS_ERROR_MESSAGE = "Não consigo atualizar o MOP agora — credenciais do Google não configuradas."
MOP_DOWNLOAD_ERROR_MESSAGE = "Não consegui baixar o arquivo. Tente enviar novamente."
MOP_READ_ERROR_MESSAGE = "Não consegui ler o arquivo Excel. Verifique se o formato está correto."
MOP_SHEETS_ERROR_MESSAGE = "Erro ao atualizar a planilha do MOP. A versão anterior foi mantida. Tente novamente."
MOP_CHANNEL_NOT_ALLOWED_MESSAGE = (
    "Esse canal não está liberado para atualizar o MOP. Envie o arquivo no canal oficial do MOP marcando a Lyra."
)

MOP_INTENT_KEYWORDS = (
    "mop", "hierarquia", "analista", "anlista", "equipe", "pessoas", "efetivo",
    "headcount", "supervisor", "coordenador", "célula", "celula", "pilar",
    "oráculo", "oraculo", "variante", "eps",
)

# Canal do fluxo "Reportar Oráculo": o Excel do MOP postado na thread de um chamado
# "MOP - Atualização Mensal & Quinzenal" é lido automaticamente. Vazio = desligado.
MOP_FLOW_CHANNEL = os.getenv("MOP_FLOW_CHANNEL", "").strip()

# --- Compromissos ------------------------------------------------------------
COMPROMISSOS_WORKSHEET_TITLE = "Compromissos"
# As 8 primeiras colunas são as originais (linhas antigas continuam válidas);
# Fila, Responsável e Thread foram adicionadas ao final.
COMPROMISSOS_HEADERS = [
    "Problema Identificado", "Ação Tomada", "Data Inicio", "Data Fim",
    "Duração", "Resultado Pré", "Resultado Pós", "Sucesso",
    "Fila", "Responsável", "Thread", "EPS",
]
COL_ACAO = COMPROMISSOS_HEADERS.index("Ação Tomada") + 1
COL_DATA_FIM = COMPROMISSOS_HEADERS.index("Data Fim") + 1
COL_DURACAO = COMPROMISSOS_HEADERS.index("Duração") + 1
COL_POS = COMPROMISSOS_HEADERS.index("Resultado Pós") + 1
COL_SUCESSO = COMPROMISSOS_HEADERS.index("Sucesso") + 1
COL_RESPONSAVEL = COMPROMISSOS_HEADERS.index("Responsável") + 1
SEM_RESPOSTA = "sem resposta"
FILA_GERAL = "Geral"
OPEN_COMMITMENTS_LIMIT = 15
SEM_RESPOSTA_WINDOW_DAYS = 3
EXPIRED_AFTER_DAYS = 7

# --- Estado persistido --------------------------------------------------------
STATE_WORKSHEET_TITLE = "Estado Lyra"
STATE_HEADERS = ["Chave", "Valor", "Atualizado em"]

# --- Agenda (horário de Brasília) ------------------------------------------------
DAILY_REPORT_TIME = datetime_time(9, 0)
REPORT_CATCHUP_UNTIL = datetime_time(13, 0)   # restart até 13h ainda publica o report do dia
REPORT_MAX_ATTEMPTS = 3
REPORT_RETRY_MINUTES = 10
PREVIOUS_THREAD_READ_TIME = datetime_time(8, 45)  # relê a thread de ontem antes do report
THREAD_READ_FIRST_TIME = datetime_time(11, 0)
THREAD_READ_FIRST_MIN_DELAY = timedelta(hours=2)
THREAD_READ_LATE_TIME = datetime_time(18, 0)
THREAD_READ_LATE_MIN_DELAY = timedelta(hours=4)
# Aviso silencioso (só para o ALERT_CHANNEL) se o MOP não foi atualizado no dia previsto
MOP_MISSING_ALERT_TIME = datetime_time(18, 0)
MOP_UPDATE_GRACE_DAYS = 2  # atualização feita até 2 dias antes também conta
SCHEDULER_TICK_SECONDS = 60

THREAD_DELIMITER = "===THREAD==="

DAILY_REPORT_PROMPT = (
    "Report diário de CSAT — execute o Bloco 3 do seu prompt (report de indicadores). "
    "Siga a estrutura completa da mensagem principal: compromissos de ontem (se houver), "
    "Principais resultados por fila (Mês, D-1, n e variação vs D-2), Maior impacto em p.p., "
    "Cobranças, Status dos compromissos e o fechamento pedindo o plano na thread "
    "(ação · responsável · prazo até 14h).\n\n"
    "CONTRATO DE SAÍDA (obrigatório, o app depende disso):\n"
    f"1. Escreva a mensagem principal, depois uma linha contendo exatamente {THREAD_DELIMITER}, "
    "depois o conteúdo da thread.\n"
    "2. A thread começa com *Resultados de todas as filas:* listando TODAS as filas com volume, "
    "uma por linha, no formato exato: • *Nome da fila:* Mês 62,6% · D-1 63,2% (n=1.839, ▲ 1,9). "
    "Depois vêm o Q4 (top 5 por fila) e o detalhe de reincidência.\n"
    "3. Se qualquer consulta falhar ou voltar vazia, responda SOMENTE uma linha começando com "
    "ERRO: e o motivo. Não publique números parciais.\n\n"
    "COMPROMISSOS: use o bloco de contexto acima (se houver) como fonte de verdade. "
    "Não peça plano novo para compromissos em andamento; cobre os sem resposta e peça plano só "
    "para ofensores novos.\n"
    "Formatação Slack (mrkdwn): negrito com *um asterisco*, bullets com •, separadores • • •. "
    "Sem tabelas, sem |, sem **duplo asterisco**. Escreva como uma pessoa, frases curtas e diretas."
)
REPORT_FAILED_CHANNEL_MESSAGE = (
    "Pessoal, o report de CSAT de hoje não saiu — tive um problema pra consultar os dados. "
    "Já sinalizei o time responsável e publico assim que normalizar."
)

try:  # feriados nacionais (lib opcional)
    import holidays as _holidays_lib

    _BR_HOLIDAYS = _holidays_lib.country_holidays("BR")
except Exception:  # pragma: no cover - lib ausente
    _BR_HOLIDAYS = None

# Slack Bolt sobe sem credenciais para smoke tests locais; em produção os
# valores reais vêm das variáveis de ambiente.
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


# ---------------------------------------------------------------------------
# Helpers gerais
# ---------------------------------------------------------------------------
def _resp_get(response: Any, key: str, default: Any = None) -> Any:
    """Lê um campo de SlackResponse ou dict. SlackResponse NÃO é dict."""
    if response is None:
        return default
    getter = getattr(response, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except Exception:
            pass
    try:
        return response[key]
    except Exception:
        return default


def _now_brazil() -> datetime:
    return datetime.now(BRAZIL_TIMEZONE)


def _today_brazil() -> datetime:
    return _now_brazil()


def _as_date(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def _format_date(value: datetime | date) -> str:
    return value.strftime("%d/%m/%Y")


def _norm_text(value: Any) -> str:
    """Minúsculas, sem acento, hífens/espaços colapsados — para comparar nomes."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[\s\-–—_:]+", " ", text.casefold())
    return text.strip()


def _to_float(value: Any) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", str(value or ""))
    return float(match.group(0).replace(",", ".")) if match else None


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + "%"


def _to_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def _col_letter(n: int) -> str:
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _row_value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _alert(text: str) -> None:
    """Avisa o responsável técnico (ALERT_CHANNEL) — sem expor dados pessoais."""
    logger.warning("ALERTA: %s", text)
    if not ALERT_CHANNEL:
        return
    try:
        slack_app.client.chat_postMessage(channel=ALERT_CHANNEL, text=f"⚠️ Lyra — {text}")
    except Exception:
        logger.exception("Could not post alert")


def _eps_pattern(eps: str) -> str:
    """Trecho que identifica a EPS no e-mail do operador (ex.: 'aec', 'csu')."""
    return _compact(eps)


def _eps_filter_sql(eps: str) -> str:
    return f"lower(ticket_last_agent_email) LIKE '%{_eps_pattern(eps)}%'"


def _email_eps(email: Any) -> str | None:
    """EPS deduzida pelo e-mail do operador (None se não bater com nenhuma ou com mais de uma)."""
    text = str(email or "").casefold()
    hits = [eps for eps in EPS_CELULAS if _eps_pattern(eps) in text]
    return hits[0] if len(hits) == 1 else None


def _celulas_of(eps: str) -> list[str]:
    for key, celulas in EPS_CELULAS.items():
        if _compact(key) == _compact(eps):
            return celulas
    return []


def _scope_instruction(eps: str | None) -> str:
    """Bloco de escopo injetado em toda mensagem enviada ao Toqan."""
    if eps is None:
        return "ESCOPO: visão interna iFood — todas as EPS. Pode comparar EPS."
    others = ", ".join(e for e in EPS_CELULAS if _compact(e) != _compact(eps)) or "outras EPS"
    celulas = _celulas_of(eps)
    return (
        f"ESCOPO OBRIGATÓRIO: este canal é exclusivo da EPS {eps}. "
        f"Filtre TODAS as consultas pelo e-mail do operador: {_eps_filter_sql(eps)}. "
        + (f"Células/filas da {eps}: {'; '.join(celulas)}. Mostre só essas. " if celulas else "")
        + f"Use somente filas, operadores, motivos, compromissos e números da {eps}. "
        f"NUNCA mencione, compare ou mostre dados de {others}, nem o resultado consolidado do iFood. "
        f"Se pedirem dados de outra EPS, diga com naturalidade que aqui você acompanha só a {eps}. "
        "Nunca mencione este escopo, filtros, e-mails, SQL ou como o canal foi configurado."
    )


def _event_scope(event: dict[str, Any]) -> tuple[bool, str | None]:
    """(permitido?, EPS do escopo). EPS None = visão completa."""
    if event.get("channel_type") == "im":
        return str(event.get("user") or "") in DM_ALLOWED_USERS, None
    channel = str(event.get("channel") or "")
    if channel in CHANNEL_SCOPE:
        return True, CHANNEL_SCOPE[channel]
    return False, None


# ---------------------------------------------------------------------------
# Toqan
# ---------------------------------------------------------------------------
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
    req = urllib.request.Request(
        url=f"{TOQAN_BASE_URL}/{method}",
        data=body,
        headers={"X-Api-Key": _require_toqan_key(), "Content-Type": "application/json"},
        method="POST" if method == "create_conversation" else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TOQAN_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        logger.error("Toqan API returned HTTP %s for %s", exc.code, method)
        raise ToqanAPIError(f"Toqan HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Toqan API request failed for %s: %s", method, exc)
        raise ToqanAPIError("Toqan request failed") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ToqanAPIError("Toqan returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ToqanAPIError("Toqan returned an unexpected response")
    return data


def create_conversation(user_message: str) -> tuple[str, str]:
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
    """Poll Toqan until the answer is finished or the poll limit is reached."""
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
            time.sleep(POLL_INTERVAL_SECONDS)
    raise ToqanAPIError("Toqan answer polling timed out")


def _clean_answer(answer: str) -> str:
    return _THINK_RE.sub("", answer).strip()


def ask_toqan(prompt: str, progress_callback: Callable[[str], Any] | None = None) -> str:
    conversation_id, request_id = create_conversation(prompt)
    return get_answer(conversation_id, request_id, progress_callback=progress_callback)


def _strip_mentions(text: str) -> str:
    return re.sub(r"\s+", " ", _MENTION_RE.sub("", text)).strip()


def _event_key(event: dict[str, Any]) -> str:
    return str(event.get("client_msg_id") or event.get("ts") or event.get("text") or "unknown")


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------
class MOPGoogleCredentialsError(RuntimeError):
    """Google service-account configuration is absent or invalid."""


class MOPDownloadError(RuntimeError):
    """An attached Slack file cannot be downloaded."""


class MOPReadError(RuntimeError):
    """The attached workbook cannot be read."""


class MOPValidationError(RuntimeError):
    """The workbook does not look like a MOP (missing columns or rows)."""


class MOPChannelNotAllowedError(RuntimeError):
    """MOP uploads are restricted to MOP_ALLOWED_CHANNELS."""


class MOPSheetsError(RuntimeError):
    """The destination Google Sheet cannot be updated."""


def _get_google_client():
    """Create the Google client from the service-account JSON (base64 or raw), if set."""
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not raw:
        return None
    try:
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


def _safe_google_client():
    try:
        return _get_google_client()
    except Exception:
        logger.warning("Google Sheets unavailable", exc_info=True)
        return None


def _open_spreadsheet(google_client: Any) -> Any:
    """Planilha da Lyra (Compromissos, Estado Lyra, MOP backup)."""
    return google_client.open_by_key(LYRA_SPREADSHEET_ID)


def _open_mop_spreadsheet(google_client: Any) -> Any:
    """Planilha do MOP oficial."""
    return google_client.open_by_key(MOP_SPREADSHEET_ID)


def _is_not_found(exc: Exception) -> bool:
    return exc.__class__.__name__ == "WorksheetNotFound"


def _worksheet_by_gid(spreadsheet: Any, worksheet_gid: int) -> Any:
    get_by_id = getattr(spreadsheet, "get_worksheet_by_id", None)
    if callable(get_by_id):
        try:
            worksheet = get_by_id(worksheet_gid)
            if worksheet is not None:
                return worksheet
        except Exception as exc:
            if not _is_not_found(exc):
                raise
    for worksheet in spreadsheet.worksheets():
        if int(worksheet.id) == worksheet_gid:
            return worksheet
    raise MOPSheetsError(f"Worksheet gid {worksheet_gid} was not found")


def _get_or_create_worksheet(spreadsheet: Any, title: str, rows: int = 1000, cols: int = 26) -> Any:
    try:
        return spreadsheet.worksheet(title)
    except Exception as exc:
        if not _is_not_found(exc):
            raise
        return spreadsheet.add_worksheet(title, rows=rows, cols=cols)


def _ensure_worksheet(spreadsheet: Any, title: str, headers: list[str]) -> Any:
    """Garante a aba, o número de colunas e o cabeçalho."""
    worksheet = _get_or_create_worksheet(spreadsheet, title, rows=1000, cols=max(len(headers), 8))
    col_count = int(getattr(worksheet, "col_count", len(headers)) or len(headers))
    if col_count < len(headers):
        worksheet.add_cols(len(headers) - col_count)
    current = [str(v).strip() for v in worksheet.row_values(1)[: len(headers)]]
    if current != headers:
        worksheet.update(
            values=[headers],
            range_name=f"A1:{_col_letter(len(headers))}1",
            value_input_option="RAW",
        )
    return worksheet


def _worksheet_rows_with_header(worksheet: Any) -> list[tuple[int, dict[str, str]]]:
    values = worksheet.get_all_values()
    if not values:
        return []
    headers = [str(value).strip() for value in values[0]]
    return [
        (n, {h: str(row[i]) if i < len(row) else "" for i, h in enumerate(headers) if h})
        for n, row in enumerate(values[1:], start=2)
        if any(str(cell).strip() for cell in row)
    ]


# ---------------------------------------------------------------------------
# Estado persistido (aba "Estado Lyra")
# ---------------------------------------------------------------------------
class StateStore:
    """Chave-valor gravado na planilha, com cache em memória.

    Se o Google estiver indisponível, funciona só em memória (e avisa no log):
    nesse modo um restart pode repetir uma rotina.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, str] = {}
        self._rows: dict[str, int] = {}
        self._worksheet: Any = None
        self._next_row = 2
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        google_client = _safe_google_client()
        if google_client is None:
            return
        try:
            worksheet = _ensure_worksheet(_open_spreadsheet(google_client), STATE_WORKSHEET_TITLE, STATE_HEADERS)
            values = worksheet.get_all_values()
        except Exception:
            logger.warning("State store: could not load worksheet; using memory only", exc_info=True)
            return
        for n, row in enumerate(values[1:], start=2):
            key = str(row[0]).strip() if row else ""
            if key:
                self._rows[key] = n
                # o que já está em memória (gravado antes do load) prevalece
                self._values.setdefault(key, str(row[1]) if len(row) > 1 else "")
        self._next_row = len(values) + 1
        self._worksheet = worksheet
        self._loaded = True

    def get(self, key: str) -> str:
        with self._lock:
            self._ensure_loaded()
            return self._values.get(key, "")

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._ensure_loaded()
            self._values[key] = value
            if self._worksheet is None:
                return
            stamp = _now_brazil().strftime("%d/%m/%Y %H:%M")
            try:
                if key in self._rows:
                    n = self._rows[key]
                    self._worksheet.update(
                        values=[[key, value, stamp]], range_name=f"A{n}:C{n}", value_input_option="RAW"
                    )
                else:
                    self._worksheet.append_row([key, value, stamp], value_input_option="RAW")
                    self._rows[key] = self._next_row
                    self._next_row += 1
            except Exception:
                logger.warning("State store: could not persist %s", key, exc_info=True)

    def snapshot(self, prefix: str = "") -> dict[str, str]:
        with self._lock:
            self._ensure_loaded()
            return {k: v for k, v in self._values.items() if k.startswith(prefix)}

    @property
    def persistent(self) -> bool:
        return self._worksheet is not None


STATE = StateStore()


# ---------------------------------------------------------------------------
# MOP
# ---------------------------------------------------------------------------
def _is_xlsx_attachment(file_info: dict[str, Any]) -> bool:
    name = str(file_info.get("name") or "").lower()
    mimetype = str(file_info.get("mimetype") or "").lower()
    filetype = str(file_info.get("filetype") or "").lower()
    if name.endswith(".xlsx"):
        return True
    if "spreadsheet" in mimetype or "excel" in mimetype:
        return True
    return filetype in ("xlsx", "excel")


def _download_slack_file(file_info: dict[str, Any], client: Any) -> bytes:
    details = dict(file_info)
    file_id = details.get("id")
    if file_id and client is not None and not (details.get("url_private_download") or details.get("url_private")):
        try:
            remote_file = _resp_get(client.files_info(file=file_id), "file")
            if isinstance(remote_file, dict):
                details.update(remote_file)
        except Exception as exc:
            logger.warning("Slack files.info failed for attached file: %s", exc)
            raise MOPDownloadError("files.info falhou (verifique o scope files:read)") from exc

    file_url = details.get("url_private_download") or details.get("url_private")
    if not file_url:
        raise MOPDownloadError("o arquivo não tem link de download")

    headers = {}
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if slack_token:
        headers["Authorization"] = f"Bearer {slack_token}"
    req = urllib.request.Request(str(file_url), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TOQAN_TIMEOUT_SECONDS) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Slack file download failed")
        raise MOPDownloadError("falha no download (verifique o scope files:read)") from exc
    if not content:
        raise MOPDownloadError("o download veio vazio")
    if content[:2] != b"PK":  # xlsx é um zip; HTML aqui = falta de permissão
        raise MOPDownloadError("o Slack não liberou o arquivo (verifique o scope files:read)")
    return content


def _cell_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):  # antes de date: datetime é subclasse de date
        if value.time() == datetime_time(0, 0):
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime_time):
        return value.strftime("%H:%M")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _compact(value: Any) -> str:
    return _norm_text(value).replace(" ", "")


def _find_col(header: list[Any], column: str) -> int | None:
    """Índice da coluna (exato, depois prefixo), ignorando acento, caixa, espaço e hífen."""
    target = _compact(column)
    cells = [_compact(h) for h in header]
    for i, cell in enumerate(cells):
        if cell and cell == target:
            return i
    for i, cell in enumerate(cells):
        if cell and cell.startswith(target):
            return i
    return None


def _header_matches(header_cells: list[str], column: str) -> bool:
    return _find_col(header_cells, column) is not None


def _eps_matches(value: Any, eps: str) -> bool:
    v, e = _compact(value), _compact(eps)
    return bool(v) and (v == e or e in v)


def _read_mop_workbook(workbook_bytes: bytes) -> tuple[list[list[str]], str, list[str]]:
    """Encontra a aba/linha de cabeçalho do MOP e devolve (linhas, aba, colunas ausentes).

    Lê VALORES (data_only=True), nunca fórmulas.
    """
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(workbook_bytes), data_only=True, read_only=True)
    except Exception as exc:
        logger.error("Excel workbook could not be opened: %s", exc)
        raise MOPReadError(str(exc)) from exc

    try:
        chosen: tuple[Any, int] | None = None
        for worksheet in workbook.worksheets:
            for idx, row in enumerate(
                worksheet.iter_rows(min_row=1, max_row=MOP_HEADER_SCAN_ROWS, values_only=True), start=1
            ):
                cells = [_norm_text(_cell_to_str(c)) for c in row]
                if all(_header_matches(cells, col) for col in MOP_REQUIRED_COLUMNS):
                    chosen = (worksheet, idx)
                    break
            if chosen:
                break
        if chosen is None:
            raise MOPValidationError(
                "não encontrei uma aba com as colunas Nome e Email nas primeiras linhas"
            )
        worksheet, header_row = chosen
        rows: list[list[str]] = []
        for row in worksheet.iter_rows(min_row=header_row, values_only=True):
            converted = [_cell_to_str(v) for v in row]
            while converted and converted[-1] == "":
                converted.pop()
            rows.append(converted)
        title = str(worksheet.title)
    except MOPValidationError:
        raise
    except Exception as exc:
        logger.error("Excel workbook could not be read: %s", exc)
        raise MOPReadError(str(exc)) from exc
    finally:
        try:
            workbook.close()
        except Exception:
            pass

    while rows and not any(rows[-1]):
        rows.pop()
    data_rows = [r for r in rows[1:] if any(r)]
    if not data_rows:
        raise MOPValidationError("a aba do MOP não tem nenhuma pessoa abaixo do cabeçalho")
    header_cells = [_norm_text(c) for c in rows[0]]
    missing = [col for col in MOP_EXPECTED_COLUMNS if not _header_matches(header_cells, col)]
    return rows, title, missing


def _count_people(values: list[list[Any]]) -> int:
    return len([r for r in values[1:] if any(str(c).strip() for c in r)])


def _row_eps(row: list[Any], eps_col: int | None, email_col: int | None) -> str:
    """EPS da linha do MOP: coluna EPS; se vazia, deduz pelo e-mail."""
    value = str(row[eps_col]).strip() if eps_col is not None and eps_col < len(row) else ""
    if value:
        return value
    email = row[email_col] if email_col is not None and email_col < len(row) else ""
    return _email_eps(email) or ""


def _count_eps_people(values: list[list[Any]], eps: str) -> int:
    if not values:
        return 0
    eps_col, email_col = _find_col(values[0], "EPS"), _find_col(values[0], "Email")
    return len([
        r for r in values[1:]
        if any(str(c).strip() for c in r) and _eps_matches(_row_eps(r, eps_col, email_col), eps)
    ])


def _merge_mop_rows(current: list[list[str]], new_rows: list[list[str]], eps: str) -> tuple[list[list[str]], int, int]:
    """Troca só as linhas da EPS e mantém as das outras.

    Devolve (planilha final, linhas de outra EPS ignoradas no arquivo, pessoas da EPS no arquivo).
    """
    new_header = new_rows[0]
    if current and _find_col(current[0], "Email") is not None:
        target_header = list(current[0])
    else:
        target_header = list(new_header)
    if _find_col(target_header, "EPS") is None:
        target_header.append("EPS")
    eps_col = _find_col(target_header, "EPS")
    email_col = _find_col(target_header, "Email")
    mapping = [_find_col(new_header, h) if str(h).strip() else None for h in target_header]
    new_eps_col, new_email_col = _find_col(new_header, "EPS"), _find_col(new_header, "Email")

    ignored = 0
    incoming: list[list[str]] = []
    for row in new_rows[1:]:
        if not any(str(c).strip() for c in row):
            continue
        row_eps = _row_eps(row, new_eps_col, new_email_col)
        if row_eps and not _eps_matches(row_eps, eps):
            ignored += 1
            continue
        out = [row[j] if j is not None and j < len(row) else "" for j in mapping]
        out[eps_col] = row_eps or eps
        incoming.append(out)

    kept = [
        list(r) for r in current[1:]
        if any(str(c).strip() for c in r) and not _eps_matches(_row_eps(r, eps_col, email_col), eps)
    ] if current and _find_col(current[0], "Email") is not None else []
    return [target_header] + kept + incoming, ignored, len(incoming)


def _update_mop_sheet(
    rows: list[list[str]], google_client: Any, eps: str | None = None
) -> tuple[int, int, int]:
    """Atualiza a aba do MOP com backup e rollback. Devolve (antes, depois, ignoradas).

    Com eps: substitui só as linhas daquela EPS (antes/depois contam só a EPS).
    Sem eps: substitui a aba inteira.
    """
    try:
        spreadsheet = _open_spreadsheet(google_client)  # onde fica o backup
        worksheet = _worksheet_by_gid(_open_mop_spreadsheet(google_client), MOP_WORKSHEET_GID)
        current = worksheet.get_all_values()
    except MOPSheetsError:
        raise
    except Exception as exc:
        raise MOPSheetsError(str(exc)) from exc

    ignored = 0
    if eps:
        before = _count_eps_people(current, eps)
        rows, ignored, after_eps = _merge_mop_rows(current, rows, eps)
        if after_eps == 0:
            raise MOPValidationError(f"o arquivo não tem nenhuma pessoa da {eps}")
    width = max([len(r) for r in rows] + [len(r) for r in current] + [1])

    # 1) backup da versão atual
    try:
        backup = _get_or_create_worksheet(
            spreadsheet, MOP_BACKUP_WORKSHEET_TITLE, rows=max(len(current) + 10, 1000), cols=max(width, 26)
        )
        backup.resize(rows=max(len(current) + 10, int(backup.row_count)), cols=max(width, int(backup.col_count)))
        backup.clear()
        if current:
            backup.update(values=current, range_name="A1", value_input_option="RAW")
    except Exception as exc:
        logger.error("MOP backup failed; aborting update: %s", exc)
        raise MOPSheetsError("não consegui salvar o backup da versão atual") from exc

    # 2) substitui; se falhar, restaura
    try:
        worksheet.resize(rows=max(len(rows) + 10, int(worksheet.row_count)), cols=max(width, int(worksheet.col_count)))
        worksheet.clear()
        worksheet.update(values=rows, range_name="A1", value_input_option="RAW")
    except Exception as exc:
        logger.error("Google Sheets MOP update failed, restoring backup: %s", exc)
        try:
            worksheet.clear()
            if current:
                worksheet.update(values=current, range_name="A1", value_input_option="RAW")
        except Exception:
            logger.exception("MOP restore failed")
            _alert("Falha ao restaurar o MOP após erro de atualização. Use a aba 'MOP backup'.")
        raise MOPSheetsError(str(exc)) from exc

    if eps:
        after = after_eps
    else:
        before, after = _count_people(current), _count_people(rows)
    logger.info("MOP sheet updated (%s): %d -> %d people", eps or "todas", before, after)
    return before, after, ignored


def _mop_column_index(header_index: dict[str, int], *aliases: str) -> int | None:
    for alias in aliases:
        idx = header_index.get(alias.casefold())
        if idx is not None:
            return idx
    for alias in aliases:
        key = alias.casefold()
        for candidate, idx in header_index.items():
            if key in candidate:
                return idx
    return None


def _mop_counts(rows: list[list[Any]], idx: int | None) -> dict[str, int] | None:
    if idx is None:
        return None
    counts: dict[str, int] = {}
    display: dict[str, str] = {}
    for row in rows:
        text = str(row[idx] if idx < len(row) else "").strip()
        if not text:
            continue
        key = text.casefold()
        display.setdefault(key, text)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    return {display[key]: count for key, count in counts.items()}


def _read_mop_values(google_client: Any = None) -> list[list[str]] | None:
    """Valores da aba do MOP; None se não deu para ler."""
    google_client = google_client or _safe_google_client()
    if google_client is None:
        return None
    try:
        return _worksheet_by_gid(_open_mop_spreadsheet(google_client), MOP_WORKSHEET_GID).get_all_values()
    except Exception:
        logger.warning("MOP: could not read MOP worksheet", exc_info=True)
        return None


def _mop_summary_text(google_client: Any = None, eps: str | None = None, values: list[list[str]] | None = None) -> str:
    """Resumo compacto do MOP para injetar no prompt ("" se indisponível ou sem pessoas).

    Com eps, considera só as pessoas daquela EPS.
    """
    all_values = values if values is not None else _read_mop_values(google_client)
    if all_values is None:
        return ""
    if not all_values:
        return ""
    header_index: dict[str, int] = {}
    for idx, raw in enumerate(all_values[0]):
        text = str(raw).strip()
        if text:
            header_index.setdefault(text.casefold(), idx)
    data_rows = [row for row in all_values[1:] if any(str(cell).strip() for cell in row)]
    if eps:
        eps_col, email_col = _find_col(all_values[0], "EPS"), _find_col(all_values[0], "Email")
        data_rows = [r for r in data_rows if _eps_matches(_row_eps(r, eps_col, email_col), eps)]
    if not data_rows:
        return ""

    scope = f" da {eps}" if eps else ""
    lines: list[str] = [f"Total de pessoas{scope} no MOP: {len(data_rows)}"]

    def add_group(label: str, *aliases: str, limit: int = 15) -> None:
        counts = _mop_counts(data_rows, _mop_column_index(header_index, *aliases))
        if counts is None:
            return
        lines.extend(["", f"{label}:"])
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
        for value, count in ordered[:limit]:
            lines.append(f"- {value}: {count}")
        if len(ordered) > limit:
            lines.append(f"- (outros {len(ordered) - limit} valores omitidos)")

    add_group("Por Status", "status", "situação", "situacao")
    add_group("Por EPS", "eps")
    add_group("Por Pilar", "pilar")
    add_group("Por Versão do Oráculo", "versão do oráculo", "versao do oraculo", "oráculo", "oraculo")
    add_group("Total por Célula (top 10)", "célula", "celula", limit=10)
    add_group("Por Supervisor (top 15)", "supervisor")
    add_group("Por Coordenador", "coordenador")
    add_group("Por horário de Entrada", "entrada", limit=8)
    add_group("Por horário de Saída", "saída", "saida", limit=8)
    updated = STATE.get(f"mop_updated_at:{eps or CONSOLIDATED}")
    if updated:
        lines.extend(["", f"Última atualização do MOP pelo app: {updated}"])
    return "\n".join(lines)


def _question_has_mop_intent(question: str) -> bool:
    lowered = question.casefold()
    return any(keyword in lowered for keyword in MOP_INTENT_KEYWORDS)


INTERNAL_NOTE = (
    "[INFORMAÇÃO INTERNA PARA A LYRA — nunca cite este trecho, nem app, sistema, planilha, "
    "Toqan ou Databricks. Responda como a gestora das EPSs, em linguagem natural.]"
)


def _mop_situation(eps: str | None) -> str:
    """Situação do MOP em linguagem de negócio, sempre preenchida."""
    who = f"da {eps}" if eps else "da operação"
    values = _read_mop_values()
    if values is None:
        return (
            f"Situação do MOP {who}: não deu para consultar o MOP agora (instabilidade). "
            "Diga que não conseguiu olhar o MOP neste momento e que tenta de novo em instantes. Não peça o Excel."
        )
    summary = _mop_summary_text(eps=eps, values=values)
    if not summary:
        return (
            f"Situação do MOP {who}: ainda não há nenhuma pessoa {who} no MOP — ele não foi enviado. "
            f"Diga isso de forma simples e peça para a liderança {who} enviar o Excel do MOP aqui no canal marcando @Lyra."
        )
    return (
        f"Situação do MOP {who} (atualizado):\n{summary}\n"
        "Use esses números para perguntas sobre pessoas, hierarquia e efetivo. Não peça o Excel."
    )


def _inject_mop_context(question: str, eps: str | None = None) -> str:
    if not question or not _question_has_mop_intent(question):
        return question
    return f"{INTERNAL_NOTE}\n{_mop_situation(eps)}\n\nMensagem de quem perguntou: {question}"


def _mop_attachment(event: dict[str, Any]) -> dict[str, Any] | None:
    files = event.get("files") or []
    if not isinstance(files, list):
        return None
    return next((f for f in files if isinstance(f, dict) and _is_xlsx_attachment(f)), None)


def _mop_channel_allowed(event: dict[str, Any]) -> bool:
    if not MOP_ALLOWED_CHANNELS:
        return True
    return str(event.get("channel") or "") in MOP_ALLOWED_CHANNELS


def _process_mop_upload(event: dict[str, Any], client: Any, eps: str | None = None) -> str | None:
    """Processa um .xlsx; devolve None quando o evento não é upload de Excel.

    Com eps (canal de EPS): troca só as linhas daquela EPS.
    """
    attachment = _mop_attachment(event)
    if attachment is None:
        return None
    if not _mop_channel_allowed(event):
        raise MOPChannelNotAllowedError
    google_client = _get_google_client()
    if google_client is None:
        raise MOPGoogleCredentialsError
    workbook_bytes = _download_slack_file(attachment, client)
    rows, sheet_title, missing = _read_mop_workbook(workbook_bytes)
    before, after, ignored = _update_mop_sheet(rows, google_client, eps)
    _mark_mop_updated([eps] if eps else None)
    if eps:
        missing = [m for m in missing if _compact(m) != "eps"]

    who = f" da {eps}" if eps else ""
    lines = [
        f"MOP{who} atualizado com sucesso! ✅ {after} pessoas{who} (antes: {before}). Aba lida: _{sheet_title}_.",
    ]
    if eps:
        lines.append("As linhas das outras EPS foram mantidas.")
    else:
        lines.append(f"Planilha: {MOP_SHEET_URL}")
    if ignored:
        lines.append(f"⚠️ {ignored} linha(s) de outra EPS no arquivo foram ignoradas.")
    if missing:
        lines.append(f"⚠️ Colunas não encontradas: {', '.join(missing)} — confira o modelo de 12 colunas.")
    if before and after < before * 0.5:
        lines.append(
            "⚠️ O número de pessoas caiu mais de 50%. Se não for esperado, reenvie o arquivo correto — "
            f"a versão anterior está na aba _{MOP_BACKUP_WORKSHEET_TITLE}_."
        )
    return "\n".join(lines)


def _mark_mop_updated(eps_list: list[str] | None) -> None:
    """Registra a data da atualização (None = MOP inteiro, todas as EPS)."""
    now = _now_brazil()
    stamp = now.strftime("%d/%m/%Y %H:%M")
    keys = [CONSOLIDATED] + list(EPS_CELULAS) if eps_list is None else eps_list
    for key in keys:
        STATE.set(f"mop_updated_at:{key}", stamp)
    STATE.set("mop_last_update", now.isoformat())


def _file_eps_set(rows: list[list[str]]) -> set[str]:
    """EPS presentes no arquivo (pela coluna EPS ou pelo e-mail)."""
    if not rows:
        return set()
    eps_col, email_col = _find_col(rows[0], "EPS"), _find_col(rows[0], "Email")
    found: set[str] = set()
    for row in rows[1:]:
        value = _row_eps(row, eps_col, email_col)
        for known in EPS_CELULAS:
            if value and _eps_matches(value, known):
                found.add(known)
    return found


def _message_text_blob(message: dict[str, Any]) -> str:
    """Texto + blocos + anexos de uma mensagem (mensagens de fluxo guardam o texto nos blocos)."""
    parts = [str(message.get("text") or "")]
    for field in ("blocks", "attachments"):
        if message.get(field):
            parts.append(json.dumps(message.get(field), ensure_ascii=False))
    return " ".join(parts)


def _is_mop_flow_message(event: dict[str, Any]) -> bool:
    """Excel postado no canal do fluxo, em mensagem ou thread que fala de MOP."""
    if not MOP_FLOW_CHANNEL or event.get("channel") != MOP_FLOW_CHANNEL:
        return False
    if _mop_attachment(event) is None:
        return False
    if "mop" in _message_text_blob(event).casefold():
        return True
    thread_ts = event.get("thread_ts")
    if not thread_ts or thread_ts == event.get("ts"):
        return False
    try:
        response = slack_app.client.conversations_replies(channel=MOP_FLOW_CHANNEL, ts=thread_ts, limit=1)
        messages = _resp_get(response, "messages", []) or []
        parent = next((m for m in messages if isinstance(m, dict) and m.get("ts") == thread_ts), None)
    except Exception:
        logger.warning("MOP flow: could not read parent message", exc_info=True)
        return False
    return parent is not None and "mop" in _message_text_blob(parent).casefold()


def _process_mop_flow(event: dict[str, Any], client: Any) -> str:
    """Atualiza o MOP a partir do Excel do fluxo. Arquivo com mais de uma EPS = MOP inteiro;
    arquivo com uma EPS só = troca só as linhas dela (não apaga a outra)."""
    google_client = _get_google_client()
    if google_client is None:
        raise MOPGoogleCredentialsError
    attachment = _mop_attachment(event)
    workbook_bytes = _download_slack_file(attachment, client)
    rows, sheet_title, missing = _read_mop_workbook(workbook_bytes)
    eps_found = _file_eps_set(rows)
    single_eps = next(iter(eps_found)) if len(eps_found) == 1 else None
    before, after, ignored = _update_mop_sheet(rows, google_client, single_eps)
    _mark_mop_updated([single_eps] if single_eps else None)

    values = _read_mop_values(google_client) or []
    eps_col, email_col = (_find_col(values[0], "EPS"), _find_col(values[0], "Email")) if values else (None, None)
    people = [r for r in values[1:] if any(str(c).strip() for c in r)]
    per_eps = " · ".join(f"{e} {_count_eps_people(values, e)}" for e in EPS_CELULAS)
    no_eps = len([r for r in people if not _row_eps(r, eps_col, email_col)])

    if single_eps:
        lines = [f"MOP da {single_eps} atualizado ✅ {after} pessoas (antes: {before}). As outras EPS foram mantidas."]
    else:
        lines = [f"MOP atualizado ✅ {after} pessoas (antes: {before})."]
    lines.append(f"Por EPS: {per_eps}" + (f" · {no_eps} sem EPS identificada" if no_eps else ""))
    if ignored:
        lines.append(f"⚠️ {ignored} linha(s) de outra EPS foram ignoradas.")
    if missing:
        lines.append(f"⚠️ Colunas não encontradas: {', '.join(missing)}.")
    if before and after < before * 0.5:
        lines.append(f"⚠️ O número de pessoas caiu mais de 50% — confira o arquivo. A versão anterior ficou guardada.")
    return "\n".join(lines)


def _handle_mop_flow_event(event: dict[str, Any], say: Callable[..., Any], client: Any) -> None:
    """Worker do fluxo: dedupe persistente (o mesmo arquivo pode chegar por dois eventos)."""
    ts = str(event.get("ts") or "")
    done_key = f"mop_flow:{ts}"
    with _IN_FLIGHT_LOCK:
        if ts in _IN_FLIGHT or STATE.get(done_key):
            return
        _IN_FLIGHT.add(ts)
    thread_ts = event.get("thread_ts") or ts
    try:
        if not _is_mop_flow_message(event):
            return
        STATE.set(done_key, "processando")
        message = _process_mop_flow(event, client)
        STATE.set(done_key, "ok")
        say(text=message, thread_ts=thread_ts)
    except MOPValidationError as exc:
        STATE.set(done_key, "recusado")
        say(text=f"Não atualizei o MOP: {exc}. O MOP atual foi mantido.", thread_ts=thread_ts)
    except (MOPDownloadError, MOPReadError) as exc:
        STATE.set(done_key, "erro")
        say(text="Não consegui abrir esse arquivo. Pode reenviar o Excel aqui na thread?", thread_ts=thread_ts)
        _alert(f"MOP do fluxo: falha ao ler o arquivo ({type(exc).__name__}: {str(exc)[:150]})")
    except Exception as exc:
        STATE.set(done_key, "erro")
        logger.exception("MOP flow update failed")
        say(text="Tive um problema pra atualizar o MOP agora. Já avisei o time responsável.", thread_ts=thread_ts)
        _alert(f"MOP do fluxo: falha ao atualizar ({type(exc).__name__}: {str(exc)[:150]})")
    finally:
        with _IN_FLIGHT_LOCK:
            _IN_FLIGHT.discard(ts)


# ---------------------------------------------------------------------------
# Report: leitura das filas
# ---------------------------------------------------------------------------
_NUM = r"\d{1,3}(?:[.,]\d+)?"
FILA_LINE_RE = re.compile(
    rf"\*(?P<fila>[^*\n]{{2,80}}?)\s*:?\s*\*\s*:?\s*(?:Mês|Mes|MTD)\s*(?P<mes>{_NUM})\s*%"
    rf"[^\n%]{{0,20}}?D\s*[-–]?\s*1\s*(?P<d1>{_NUM})\s*%",
    re.IGNORECASE,
)


def _parse_report_csat(text: str) -> dict[str, dict[str, float]]:
    """Extrai {fila: {"mes": x, "d1": y}} das linhas '• *Fila:* Mês X% · D-1 Y%'."""
    result: dict[str, dict[str, float]] = {}
    for match in FILA_LINE_RE.finditer(text or ""):
        fila = match.group("fila").strip().rstrip(":").strip()
        mes, d1 = _to_float(match.group("mes")), _to_float(match.group("d1"))
        if fila and mes is not None and d1 is not None:
            result.setdefault(fila, {"mes": mes, "d1": d1})
    return result


def _match_fila(name: str, filas: list[str]) -> str | None:
    """Casa um nome livre com uma fila conhecida (exato, depois o mais específico)."""
    target = _norm_text(name)
    if not target or not filas:
        return None
    normalized = {f: _norm_text(f) for f in filas}
    for fila, norm in normalized.items():
        if norm == target:
            return fila
    candidates = [f for f, n in normalized.items() if n and (n in target or target in n)]
    if not candidates:
        return None
    return max(candidates, key=lambda f: len(normalized[f]))


def _split_report(answer: str) -> tuple[str, str]:
    if THREAD_DELIMITER in answer:
        main, thread = answer.split(THREAD_DELIMITER, 1)
        return main.strip(), thread.strip()
    return answer.strip(), ""


def _is_error_answer(answer: str) -> bool:
    first = next((line.strip() for line in str(answer or "").splitlines() if line.strip()), "")
    return not first or first.upper().lstrip("*_ ").startswith("ERRO")


# ---------------------------------------------------------------------------
# Datas de compromisso
# ---------------------------------------------------------------------------
_NO_DATE = {"", "a definir", "sem prazo", "não informado", "nao informado", "—", "-", "n/a"}
_WEEKDAYS = {
    "segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sábado": 5, "sabado": 5, "domingo": 6,
}


def _midnight(day: date) -> datetime:
    return datetime.combine(day, datetime_time(0, 0), tzinfo=BRAZIL_TIMEZONE)


def _parse_commitment_date(value: Any, today: datetime | date | None = None) -> datetime | None:
    """Entende dd/mm[/aaaa], aaaa-mm-dd, hoje, amanhã, dia da semana, semana que vem, fim do mês…"""
    text = str(value or "").strip().casefold()
    if text in _NO_DATE:
        return None
    base = _as_date(today or _today_brazil())

    for pattern, fmt in (
        (r"\b(\d{1,2}/\d{1,2}/\d{4})\b", "%d/%m/%Y"),
        (r"\b(\d{1,2}-\d{1,2}-\d{4})\b", "%d-%m-%Y"),
        (r"\b(\d{4}-\d{1,2}-\d{1,2})\b", "%Y-%m-%d"),
    ):
        match = re.search(pattern, text)
        if match:
            try:
                return _midnight(datetime.strptime(match.group(1), fmt).date())
            except ValueError:
                return None
    match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2}))?\b", text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year = 2000 + int(match.group(3)) if match.group(3) else base.year
        try:
            parsed = date(year, month, day)
            if not match.group(3) and parsed < base - timedelta(days=180):
                parsed = date(year + 1, month, day)
        except ValueError:
            return None
        return _midnight(parsed)

    if "depois de amanh" in text:
        return _midnight(base + timedelta(days=2))
    if "amanh" in text or "tomorrow" in text:
        return _midnight(base + timedelta(days=1))
    if "hoje" in text or "today" in text:
        return _midnight(base)
    if re.search(r"fi(m|nal) do m[eê]s", text):
        first_next = date(base.year + (base.month == 12), base.month % 12 + 1, 1)
        return _midnight(first_next - timedelta(days=1))
    if re.search(r"semana que vem|pr[oó]xima semana", text):
        return _midnight(base + timedelta(days=7))
    if re.search(r"fi(m|nal) da semana", text):
        return _midnight(base + timedelta(days=(4 - base.weekday()) % 7))
    match = re.search(r"\b(\d{1,2})\s*dias?\b", text)
    if match:
        return _midnight(base + timedelta(days=int(match.group(1))))
    for name, weekday in _WEEKDAYS.items():
        if re.search(rf"\b{name}", text):
            return _midnight(base + timedelta(days=(weekday - base.weekday()) % 7))
    return None


def _deadline_fields(raw: Any, today: datetime | date) -> tuple[str, str]:
    """(Data Fim, Duração em dias) a partir do prazo informado."""
    parsed = _parse_commitment_date(raw, today)
    if parsed is None:
        return "a definir", "—"
    return _format_date(parsed), str(max(0, (parsed.date() - _as_date(today)).days))


# ---------------------------------------------------------------------------
# Compromissos
# ---------------------------------------------------------------------------
def _compromissos_ws(google_client: Any) -> Any:
    return _ensure_worksheet(_open_spreadsheet(google_client), COMPROMISSOS_WORKSHEET_TITLE, COMPROMISSOS_HEADERS)


def _commitment_status(row: dict[str, str], today: datetime | date | None = None) -> str:
    """concluído | encerrado | sem resposta | prazo a definir | vence hoje | prazo vencido | expirado | em andamento"""
    base = _as_date(today or _today_brazil())
    if _row_value(row, "Sucesso").casefold() == "encerrado":
        return "encerrado"
    post = _row_value(row, "Resultado Pós")
    if post and post.casefold() not in {"a definir"}:
        return "concluído"
    if _row_value(row, "Ação Tomada").casefold() == SEM_RESPOSTA:
        return "sem resposta"
    deadline = _parse_commitment_date(_row_value(row, "Data Fim"), base)
    if deadline is None:
        return "prazo a definir"
    if deadline.date() == base:
        return "vence hoje"
    if deadline.date() < base - timedelta(days=EXPIRED_AFTER_DAYS):
        return "expirado"
    if deadline.date() < base:
        return "prazo vencido"
    return "em andamento"


_STATUS_PRIORITY = {
    "prazo vencido": 0, "vence hoje": 1, "sem resposta": 2, "prazo a definir": 3,
    "em andamento": 4, "concluído": 5,
}


def _commitment_fila(row: dict[str, str], filas: list[str] | None = None) -> str:
    fila = _row_value(row, "Fila")
    if fila:
        return fila
    if filas:  # linhas antigas, sem coluna Fila: tenta achar no texto do problema
        return _match_fila(_row_value(row, "Problema Identificado"), filas) or FILA_GERAL
    return FILA_GERAL


def _get_open_compromissos(
    google_client: Any, today: datetime | date | None = None, tenant_key: str = CONSOLIDATED
) -> str:
    """Contexto de compromissos para o prompt do report (só o que está em aberto, só desta EPS)."""
    base = _as_date(today or _today_brazil())
    try:
        rows = _worksheet_rows_with_header(_compromissos_ws(google_client))
    except Exception:
        logger.warning("Could not read commitments from Google Sheets", exc_info=True)
        return ""

    selected: list[tuple[int, date, str, dict[str, str]]] = []
    for _, row in rows:
        if not _same_tenant(row, tenant_key):
            continue
        status = _commitment_status(row, base)
        if status in {"encerrado", "expirado"}:
            continue
        deadline = _parse_commitment_date(_row_value(row, "Data Fim"), base)
        if status == "concluído":
            # mostra resultado só de quem fechou nos últimos 2 dias
            if deadline is None or deadline.date() < base - timedelta(days=2):
                continue
        if status == "sem resposta":
            start = _parse_commitment_date(_row_value(row, "Data Inicio"), base)
            if start is None or start.date() < base - timedelta(days=SEM_RESPOSTA_WINDOW_DAYS):
                continue
        sort_day = deadline.date() if deadline else base + timedelta(days=365)
        selected.append((_STATUS_PRIORITY.get(status, 9), sort_day, status, row))

    if not selected:
        return ""
    selected.sort(key=lambda item: (item[0], item[1]))
    lines = ["COMPROMISSOS EM ABERTO (aba Compromissos, lida agora pelo app):"]
    for _, _, status, row in selected[:OPEN_COMMITMENTS_LIMIT]:
        fila = _commitment_fila(row)
        action = _row_value(row, "Ação Tomada") or SEM_RESPOSTA
        owner = _row_value(row, "Responsável") or "Liderança"
        deadline_text = _row_value(row, "Data Fim") or "a definir"
        pre = _row_value(row, "Resultado Pré") or "a definir"
        if status == "em andamento":
            lines.append(f"- Em andamento: {fila} · {action} · {owner} · prazo {deadline_text}")
        elif status in {"prazo vencido", "vence hoje"}:
            label = "vence hoje" if status == "vence hoje" else f"venceu em {deadline_text}"
            lines.append(f"- Prazo {label}: {fila} · {action} · {owner} · CSAT pré {pre} — pedir o status")
        elif status == "concluído":
            post = _row_value(row, "Resultado Pós")
            success = _row_value(row, "Sucesso") or "a definir"
            lines.append(f"- Concluído: {fila} · {action} · CSAT {pre} → {post} — funcionou: {success}")
        elif status == "sem resposta":
            lines.append(f"- Sem resposta: report de {_row_value(row, 'Data Inicio')} — cobrar novamente")
        else:
            lines.append(f"- Sem prazo: {fila} · {action} · {owner} — pedir prazo")
    if len(selected) > OPEN_COMMITMENTS_LIMIT:
        lines.append(f"- (+{len(selected) - OPEN_COMMITMENTS_LIMIT} compromissos com prazo mais distante)")
    lines.extend([
        "",
        "Em andamento: não peça plano novo, só pergunte o status. Vencidos: peça o status. "
        "Sem resposta: cobre de novo. Ofensores novos: peça ação · responsável · prazo na thread até 14h.",
    ])
    return "\n".join(lines)


def _commitment_row(
    fila: str, acao: str, responsavel: str, prazo: str, pre: str, report_ts: str, today: datetime | date,
    tenant_key: str = CONSOLIDATED,
) -> list[str]:
    data_fim, duracao = _deadline_fields(prazo, today)
    problema = f"{fila} · CSAT D-1 {pre}" if pre else f"{fila} · ofensor do report"
    return [
        problema, acao, _format_date(today), data_fim, duracao,
        pre or "a definir", "", "a definir", fila, responsavel or "Liderança", report_ts, tenant_key,
    ]


def _sem_resposta_row(report_ts: str, today: datetime | date, tenant_key: str = CONSOLIDATED) -> list[str]:
    return [
        "Report sem resposta da liderança", SEM_RESPOSTA, _format_date(today), "—", "—",
        "a definir", "", "a definir", FILA_GERAL, "Liderança", report_ts, tenant_key,
    ]


def _row_tenant(row: dict[str, str]) -> str:
    return _row_value(row, "EPS") or CONSOLIDATED


def _same_tenant(row: dict[str, str], tenant_key: str) -> bool:
    return _compact(_row_tenant(row)) == _compact(tenant_key)


def _check_deadline_compromissos(
    google_client: Any, csat: dict[str, dict[str, float]], today: datetime | date | None = None,
    tenant_key: str = CONSOLIDATED,
) -> int:
    """Preenche Resultado Pós/Sucesso dos compromissos vencidos usando o D-1 da fila.

    Só fecha quando o prazo já passou (o D-1 do report cobre o dia do prazo).
    """
    if not csat:
        return 0
    base = _as_date(today or _today_brazil())
    filas = list(csat)
    worksheet = _compromissos_ws(google_client)
    updated = 0
    for row_number, row in _worksheet_rows_with_header(worksheet):
        if not _same_tenant(row, tenant_key):
            continue
        if _commitment_status(row, base) not in {"prazo vencido", "expirado"}:
            continue
        fila = _match_fila(_commitment_fila(row, filas), filas)
        pre = _to_float(_row_value(row, "Resultado Pré"))
        if fila is None or pre is None:
            continue
        post = csat[fila]["d1"]
        worksheet.update_cell(row_number, COL_POS, _fmt_pct(post))
        worksheet.update_cell(row_number, COL_SUCESSO, "Sim" if post > pre else "Não")
        updated += 1
    return updated


def _strip_json_code_blocks(answer: str) -> str:
    text = str(answer or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text


def _parse_extraction(answer: str) -> dict[str, list[dict[str, Any]]] | None:
    text = _strip_json_code_blocks(answer)
    parsed: Any = None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
            except json.JSONDecodeError:
                parsed = None
    if isinstance(parsed, list):
        return {"novos": [i for i in parsed if isinstance(i, dict)], "atualizacoes": []}
    if isinstance(parsed, dict):
        return {
            "novos": [i for i in (parsed.get("novos") or []) if isinstance(i, dict)],
            "atualizacoes": [i for i in (parsed.get("atualizacoes") or []) if isinstance(i, dict)],
        }
    return None


def _extract_commitments_via_toqan(
    messages: list[str],
    filas: list[str],
    existing: list[tuple[int, dict[str, str]]],
    today: datetime | date,
) -> dict[str, list[dict[str, Any]]]:
    """Pede ao Toqan os compromissos novos e as atualizações dos já registrados."""
    base = _as_date(today)
    weekday = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][base.weekday()]
    existing_lines = "\n".join(
        f"linha {n} · {_commitment_fila(r)} · {_row_value(r, 'Ação Tomada')} · "
        f"{_row_value(r, 'Responsável') or 'Liderança'} · prazo {_row_value(r, 'Data Fim') or 'a definir'}"
        for n, r in existing
        if _row_value(r, "Ação Tomada").casefold() != SEM_RESPOSTA
    ) or "(nenhum)"
    prompt = (
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Responda APENAS com JSON válido, "
        "sem markdown, sem texto antes ou depois.\n\n"
        "Você é um extrator de compromissos de plano de ação da liderança das EPSs.\n"
        f"Hoje é {_format_date(base)} ({weekday}).\n"
        f"Filas do report: {', '.join(filas) if filas else '(não identificadas)'}\n"
        f"Compromissos já registrados nesta thread:\n{existing_lines}\n\n"
        "Mensagens novas da liderança:\n" + "\n---\n".join(messages) + "\n\n"
        "Formato de saída:\n"
        '{"novos":[{"fila":"...","acao":"...","responsavel":"...","prazo":"dd/mm/aaaa ou a definir"}],'
        '"atualizacoes":[{"linha":12,"acao":"...","responsavel":"...","prazo":"dd/mm/aaaa"}]}\n\n'
        "Regras:\n"
        "- novos: planos de ação novos. fila = exatamente um nome da lista de filas; se não der pra saber, use \"Geral\".\n"
        "- atualizacoes: quando a mensagem completa ou corrige um compromisso já registrado (ex.: informa o prazo "
        "que faltava). Use o número da linha e inclua só os campos que mudaram.\n"
        "- prazo: converta para dd/mm/aaaa a partir de hoje (\"sexta\" = próxima sexta; \"semana que vem\" = hoje + 7 dias; "
        "\"fim do mês\" = último dia do mês). Sem prazo → \"a definir\".\n"
        "- responsavel: quem executa; se não mencionado, \"Liderança\".\n"
        "- Status de compromisso (\"concluído\", \"em andamento\") não é compromisso novo.\n"
        '- Não invente. Sem plano nem atualização → {"novos":[],"atualizacoes":[]}'
    )
    answer = ask_toqan(prompt)
    parsed = _parse_extraction(answer)
    if parsed is None:
        logger.warning("Commitment extraction was not JSON; keeping raw message as commitment")
        raw = " / ".join(m.strip() for m in messages if m.strip())[:200]
        return {"novos": [{"fila": FILA_GERAL, "acao": raw, "responsavel": "Liderança", "prazo": "a definir"}],
                "atualizacoes": []}
    return parsed


def _human_thread_message_records(messages: list[dict[str, Any]], report_ts: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("ts") == report_ts:
            continue
        if message.get("bot_id") or message.get("bot_profile") or message.get("subtype") == "bot_message":
            continue
        text = _strip_mentions(str(message.get("text") or ""))
        timestamp = str(message.get("ts") or "").strip()
        if text and timestamp:
            records.append((timestamp, text))
    return records


def _fetch_thread(channel_id: str, report_ts: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    cursor = None
    for _ in range(10):
        kwargs: dict[str, Any] = {"channel": channel_id, "ts": report_ts, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = slack_app.client.conversations_replies(**kwargs)
        page = _resp_get(response, "messages", []) or []
        messages.extend(m for m in page if isinstance(m, dict))
        cursor = (_resp_get(response, "response_metadata", {}) or {}).get("next_cursor")
        if not cursor:
            break
    return messages


def _read_report_thread(
    channel_id: str, report_ts: str, phase: str, today: datetime | date | None = None,
    tenant_key: str = CONSOLIDATED,
) -> dict[str, int]:
    """Lê a thread do report e registra/atualiza compromissos. Levanta exceção em falha.

    phase: "first" (2h depois; registra "sem resposta" se ninguém respondeu),
           "late" (18h) ou "next" (manhã seguinte, antes do report).
    """
    base = _as_date(today or _today_brazil())
    messages = _fetch_thread(channel_id, report_ts)
    report_text = "\n".join(
        str(m.get("text") or "")
        for m in messages
        if m.get("ts") == report_ts or m.get("bot_id") or m.get("subtype") == "bot_message"
    )
    csat = _parse_report_csat(report_text)
    filas = list(csat)

    records = _human_thread_message_records(messages, report_ts)
    captured_key = f"captured:{report_ts}"
    captured = {t for t in STATE.get(captured_key).split(",") if t}
    new_records = [(t, text) for t, text in records if t not in captured]

    google_client = _get_google_client()
    if google_client is None:
        raise MOPGoogleCredentialsError("GOOGLE_CREDENTIALS_JSON não configurado")
    worksheet = _compromissos_ws(google_client)
    thread_rows = [(n, r) for n, r in _worksheet_rows_with_header(worksheet) if _row_value(r, "Thread") == report_ts]

    if not new_records:
        if phase == "first" and not records and not thread_rows:
            worksheet.append_row(_sem_resposta_row(report_ts, base, tenant_key), value_input_option="RAW")
        return {"novos": 0, "atualizados": 0}

    extraction = _extract_commitments_via_toqan([text for _, text in new_records], filas, thread_rows, base)

    # novos
    new_rows: list[list[str]] = []
    missing_deadline: list[str] = []
    for item in extraction["novos"]:
        action = str(item.get("acao") or "").strip()
        if not action:
            continue
        fila = _match_fila(str(item.get("fila") or ""), filas) or FILA_GERAL
        pre = _fmt_pct(csat[fila]["d1"]) if fila in csat else ""
        prazo = str(item.get("prazo") or "a definir").strip() or "a definir"
        row = _commitment_row(
            fila, action, str(item.get("responsavel") or "").strip(), prazo, pre, report_ts, base, tenant_key
        )
        new_rows.append(row)
        if row[COL_DATA_FIM - 1] == "a definir":
            missing_deadline.append(action)
    if new_rows:
        worksheet.append_rows(new_rows, value_input_option="RAW")

    # atualizações (só linhas desta thread)
    valid_rows = {n: r for n, r in thread_rows}
    updated = 0
    for item in extraction["atualizacoes"]:
        n = _to_int(item.get("linha"))
        if n not in valid_rows:
            continue
        changed = False
        if str(item.get("acao") or "").strip():
            worksheet.update_cell(n, COL_ACAO, str(item["acao"]).strip())
            changed = True
        if str(item.get("responsavel") or "").strip():
            worksheet.update_cell(n, COL_RESPONSAVEL, str(item["responsavel"]).strip())
            changed = True
        if str(item.get("prazo") or "").strip():
            start = _parse_commitment_date(_row_value(valid_rows[n], "Data Inicio"), base) or _midnight(base)
            data_fim, duracao = _deadline_fields(item["prazo"], start)
            if data_fim != "a definir":
                worksheet.update_cell(n, COL_DATA_FIM, data_fim)
                worksheet.update_cell(n, COL_DURACAO, duracao)
                changed = True
        updated += int(changed)

    # liderança respondeu: encerra o "sem resposta" desta thread
    if new_rows or updated:
        for n, r in thread_rows:
            if _row_value(r, "Ação Tomada").casefold() == SEM_RESPOSTA:
                worksheet.update_cell(n, COL_ACAO, f"sem resposta (respondido em {_format_date(base)})")
                worksheet.update_cell(n, COL_SUCESSO, "encerrado")

    STATE.set(captured_key, ",".join(sorted(captured | {t for t, _ in new_records})))

    if new_rows or updated:
        parts = []
        if new_rows:
            parts.append(f"{len(new_rows)} novo(s) compromisso(s)")
        if updated:
            parts.append(f"{updated} atualizado(s)")
        text = f"Registrado: {' e '.join(parts)} ✅"
        if missing_deadline:
            text += "\nQual o prazo para:\n" + "\n".join(f"• {a[:120]}" for a in missing_deadline)
        slack_app.client.chat_postMessage(channel=channel_id, text=text, thread_ts=report_ts)
    return {"novos": len(new_rows), "atualizados": updated}


# ---------------------------------------------------------------------------
# Report diário (um por EPS + consolidado opcional)
# ---------------------------------------------------------------------------
class ReportGenerationError(RuntimeError):
    """O Toqan não devolveu um report publicável."""


def _report_prompt(tenant: Tenant, compromissos_text: str) -> str:
    scope = _scope_instruction(tenant.eps)
    if tenant.eps:
        scope += (
            f" Este é o report da {tenant.eps}: use os nomes das células da {tenant.eps} como filas; "
            "células sem volume em D-1 aparecem como 'sem volume em D-1'. "
            "Não use a palavra iFood para se referir a totais — o total do report é o total da EPS."
        )
    parts = [scope]
    if compromissos_text:
        parts.append(compromissos_text)
    parts.append(DAILY_REPORT_PROMPT)
    return "\n\n".join(parts)


def _run_daily_report(now: datetime | None = None, tenant: Tenant | None = None) -> str:
    """Gera e publica o report de um tenant; devolve o ts da mensagem principal."""
    now = now or _now_brazil()
    tenant = tenant or TENANTS[0]
    google_client = _safe_google_client()
    compromissos_text = _get_open_compromissos(google_client, now, tenant.key) if google_client else ""

    answer = ask_toqan(_report_prompt(tenant, compromissos_text))
    if _is_error_answer(answer):
        raise ReportGenerationError(answer.strip()[:300] or "resposta vazia")
    main, thread = _split_report(answer)
    if not main:
        raise ReportGenerationError("mensagem principal vazia")
    csat = _parse_report_csat(answer)
    if not csat:
        _alert(f"[{tenant.key}] Report sem linhas de fila no formato esperado — pré/pós dos compromissos não será calculado hoje.")
    if not thread:
        logger.warning("[%s] Report without %s delimiter; posting everything as main message", tenant.key, THREAD_DELIMITER)

    response = slack_app.client.chat_postMessage(channel=tenant.channel, text=main)
    report_ts = _resp_get(response, "ts") or (_resp_get(response, "message", {}) or {}).get("ts")
    if not report_ts:
        raise ReportGenerationError("Slack não devolveu o ts do report")
    STATE.set(f"report:{tenant.key}:{now.date().isoformat()}", str(report_ts))
    if thread:
        try:
            slack_app.client.chat_postMessage(channel=tenant.channel, text=thread, thread_ts=report_ts)
        except Exception:
            logger.exception("Could not post report thread")
            _alert(f"[{tenant.key}] O report saiu, mas não consegui postar a thread (Q4/filas).")

    if google_client is not None and csat:
        try:
            closed = _check_deadline_compromissos(google_client, csat, now, tenant.key)
            logger.info("[%s] Daily report: %d commitments closed with pós", tenant.key, closed)
        except Exception:
            logger.warning("Daily report: could not update commitment deadlines", exc_info=True)
    return str(report_ts)


# ---------------------------------------------------------------------------
# Calendário do MOP
# ---------------------------------------------------------------------------
def _is_business_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    return not (_BR_HOLIDAYS is not None and day in _BR_HOLIDAYS)


def _next_business_day(day: date) -> date:
    while not _is_business_day(day):
        day += timedelta(days=1)
    return day


def _mop_fire_dates_for_month(year: int, month: int) -> list[date]:
    """1º dia útil e dia 15 (ou próximo dia útil). Fim de semana e feriado nacional pulados."""
    return [_next_business_day(date(year, month, 1)), _next_business_day(date(year, month, 15))]


def _is_mop_day(day: date) -> bool:
    return day in _mop_fire_dates_for_month(day.year, day.month)


# ---------------------------------------------------------------------------
# Agendador único
# ---------------------------------------------------------------------------
_report_next_attempt_at: dict[str, datetime] = {}
_scheduler_thread: threading.Thread | None = None
_scheduler_last_tick: datetime | None = None


def _skey(kind: str, tenant: Tenant, day: date) -> str:
    return f"{kind}:{tenant.key}:{day.isoformat()}"


def _posted_at(ts: str) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(ts), tz=BRAZIL_TIMEZONE)
    except Exception:
        return None


def _run_thread_read(tenant: Tenant, report_ts: str, phase: str, state_key: str, today: date) -> None:
    try:
        result = _read_report_thread(tenant.channel, report_ts, phase, today, tenant.key)
        logger.info("[%s] Thread read %s: %s", tenant.key, phase, result)
        STATE.set(state_key, "ok")
    except Exception as exc:
        logger.exception("[%s] Thread read %s failed", tenant.key, phase)
        STATE.set(state_key, "erro")
        _alert(f"[{tenant.key}] Falha ao ler a thread do report ({phase}): {type(exc).__name__}: {str(exc)[:200]}")


def _tenant_tick(tenant: Tenant, now: datetime) -> None:
    today = now.date()

    # 1) Releitura da thread de ontem (respostas tardias) antes do report
    if now.time() >= PREVIOUS_THREAD_READ_TIME:
        yesterday = today - timedelta(days=1)
        y_ts = STATE.get(_skey("report", tenant, yesterday))
        if y_ts and STATE.get(_skey("read_first", tenant, yesterday)) and not STATE.get(_skey("read_next", tenant, yesterday)):
            _run_thread_read(tenant, y_ts, "next", _skey("read_next", tenant, yesterday), today)

    # 2) Report diário (com recuperação após restart e novas tentativas)
    if not STATE.get(_skey("report", tenant, today)):
        fail_key = _skey("report_fail", tenant, today)
        if DAILY_REPORT_TIME <= now.time() < REPORT_CATCHUP_UNTIL:
            failures = _to_int(STATE.get(fail_key))
            next_at = _report_next_attempt_at.get(tenant.key)
            if failures < REPORT_MAX_ATTEMPTS and (next_at is None or now >= next_at):
                try:
                    _run_daily_report(now, tenant)
                    _report_next_attempt_at.pop(tenant.key, None)
                except Exception as exc:
                    failures += 1
                    STATE.set(fail_key, str(failures))
                    _report_next_attempt_at[tenant.key] = now + timedelta(minutes=REPORT_RETRY_MINUTES)
                    logger.exception("[%s] Daily report attempt %d failed", tenant.key, failures)
                    detail = f"{type(exc).__name__}: {str(exc)[:250]}"
                    if failures >= REPORT_MAX_ATTEMPTS:
                        _alert(f"[{tenant.key}] Report de {_format_date(today)} não saiu após {failures} tentativas. Último erro: {detail}")
                        try:
                            slack_app.client.chat_postMessage(channel=tenant.channel, text=REPORT_FAILED_CHANNEL_MESSAGE)
                        except Exception:
                            logger.exception("Could not post report failure notice")
                    else:
                        _alert(f"[{tenant.key}] Tentativa {failures} do report falhou ({detail}). Nova tentativa em {REPORT_RETRY_MINUTES} min.")
        elif now.time() >= REPORT_CATCHUP_UNTIL and not STATE.get(_skey("report_missed", tenant, today)) \
                and _to_int(STATE.get(fail_key)) < REPORT_MAX_ATTEMPTS:
            STATE.set(_skey("report_missed", tenant, today), "1")
            _alert(f"[{tenant.key}] O report de {_format_date(today)} não rodou (app fora do ar na janela 09h–13h?).")

    # 3) Leituras da thread de hoje
    report_ts = STATE.get(_skey("report", tenant, today))
    if report_ts:
        posted = _posted_at(report_ts) or now
        first_due = max(datetime.combine(today, THREAD_READ_FIRST_TIME, tzinfo=BRAZIL_TIMEZONE),
                        posted + THREAD_READ_FIRST_MIN_DELAY)
        first_key = _skey("read_first", tenant, today)
        if now >= first_due and not STATE.get(first_key):
            _run_thread_read(tenant, report_ts, "first", first_key, today)
        late_due = max(datetime.combine(today, THREAD_READ_LATE_TIME, tzinfo=BRAZIL_TIMEZONE),
                       posted + THREAD_READ_LATE_MIN_DELAY)
        late_key = _skey("read_late", tenant, today)
        if now >= late_due and STATE.get(first_key) and not STATE.get(late_key):
            _run_thread_read(tenant, report_ts, "late", late_key, today)



def _scheduler_tick(now: datetime | None = None) -> None:
    global _scheduler_last_tick
    now = now or _now_brazil()
    _scheduler_last_tick = now
    for tenant in TENANTS:
        try:
            _tenant_tick(tenant, now)
        except Exception:
            logger.exception("[%s] Scheduler tick failed", tenant.key)
    try:
        _mop_missing_check(now)
    except Exception:
        logger.exception("MOP missing check failed")


def _mop_missing_check(now: datetime) -> None:
    """Dia de MOP (1º dia útil / dia 15) e nada atualizado até 18h -> DM para o responsável. Nada no canal."""
    today = now.date()
    if not _is_mop_day(today) or now.time() < MOP_MISSING_ALERT_TIME:
        return
    key = f"mop_missing_check:{today.isoformat()}"
    if STATE.get(key):
        return
    last = STATE.get("mop_last_update")
    updated = False
    if last:
        try:
            updated = datetime.fromisoformat(last).date() >= today - timedelta(days=MOP_UPDATE_GRACE_DAYS)
        except ValueError:
            updated = False
    STATE.set(key, "ok" if updated else "alerta")
    if not updated:
        _alert(
            f"Hoje ({_format_date(today)}) é dia de atualização do MOP e até as 18h ele não foi atualizado "
            "pelo fluxo Reportar Oráculo."
        )


def _check_mop_access() -> None:
    """No boot: confirma que a service account abre a planilha do MOP."""
    if _safe_google_client() is None:
        return
    if _read_mop_values() is None:
        _alert(
            "Não consigo abrir a planilha do MOP. Compartilhe-a como Editor com "
            "lyra-mop@lyra-510815.iam.gserviceaccount.com e confira MOP_SPREADSHEET_ID / MOP_WORKSHEET_GID."
        )


def _scheduler_loop() -> None:
    STATE.get("boot")  # força a carga do estado
    try:
        _check_mop_access()
    except Exception:
        logger.exception("MOP access check failed")
    if not STATE.persistent:
        logger.warning("State store em memória: um restart pode repetir rotinas do dia.")
    logger.info("Scheduler started for %s", TENANTS)
    while True:
        try:
            _scheduler_tick()
        except Exception:
            logger.exception("Scheduler tick failed")
        time.sleep(SCHEDULER_TICK_SECONDS)


def _start_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_thread = threading.Thread(target=_scheduler_loop, name="lyra-scheduler", daemon=True)
    _scheduler_thread.start()


# ---------------------------------------------------------------------------
# Slack events
# ---------------------------------------------------------------------------
def _say(say: Callable[..., Any], answer: str, event: dict[str, Any], in_thread: bool) -> None:
    if in_thread:
        say(text=answer, thread_ts=event.get("thread_ts") or event.get("ts"))
    else:
        say(text=answer)


def _process_event(event: dict[str, Any], say: Callable[..., Any], in_thread: bool, client: Any = None) -> None:
    """Processa upload de MOP ou repassa a mensagem para o Toqan."""
    event_key = _event_key(event)
    with _IN_FLIGHT_LOCK:
        if event_key in _IN_FLIGHT:
            return
        _IN_FLIGHT.add(event_key)

    question = _strip_mentions(str(event.get("text") or ""))
    try:
        allowed, eps = _event_scope(event)
        if not allowed:
            is_im = event.get("channel_type") == "im"
            _say(say, DM_NOT_ALLOWED_MESSAGE if is_im else CHANNEL_NOT_CONFIGURED_MESSAGE, event, in_thread)
            return
        mop_answer = _process_mop_upload(event, client, eps)
        if mop_answer is not None:
            _say(say, mop_answer, event, in_thread=True)
            return
        if not question:
            _say(say, "Oi! Sou a Lyra. Como posso ajudar?", event, in_thread)
            return

        def send_progress(message: str) -> None:
            _say(say, message, event, in_thread=True)

        prompt = f"{_scope_instruction(eps)}\n\n{_inject_mop_context(question, eps)}"
        answer = ask_toqan(prompt, progress_callback=send_progress)
        _say(say, answer or EMPTY_ANSWER_MESSAGE, event, in_thread)
    except MOPChannelNotAllowedError:
        _say(say, MOP_CHANNEL_NOT_ALLOWED_MESSAGE, event, in_thread=True)
    except MOPGoogleCredentialsError as exc:
        logger.warning("MOP upload: Google credentials error: %s", exc)
        _say(say, MOP_CREDENTIALS_ERROR_MESSAGE, event, in_thread=True)
    except MOPDownloadError as exc:
        _say(say, f"Não consegui baixar o arquivo: {exc}" if str(exc) else MOP_DOWNLOAD_ERROR_MESSAGE, event, in_thread=True)
    except MOPValidationError as exc:
        _say(say, f"Não atualizei o MOP: {exc}. A planilha atual foi mantida.", event, in_thread=True)
    except MOPReadError as exc:
        logger.warning("MOP upload: Excel read error: %s", exc)
        _say(say, MOP_READ_ERROR_MESSAGE, event, in_thread=True)
    except MOPSheetsError as exc:
        logger.warning("MOP upload could not update Google Sheets: %s", exc)
        _say(say, MOP_SHEETS_ERROR_MESSAGE, event, in_thread=True)
    except ToqanAPIError as exc:
        logger.exception("Lyra could not process Slack event")
        _say(say, TIMEOUT_ERROR_MESSAGE if "polling timed out" in str(exc) else ERROR_MESSAGE, event, in_thread)
    except Exception:
        logger.exception("Lyra could not process Slack event")
        _say(say, ERROR_MESSAGE, event, in_thread)
    finally:
        with _IN_FLIGHT_LOCK:
            _IN_FLIGHT.discard(event_key)


def _dispatch(event: dict[str, Any], say: Callable[..., Any], client: Any, ack: Callable[[], Any]) -> None:
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

    try:
        threading.Thread(target=worker, name=f"lyra-{event_key}", daemon=True).start()
    except Exception:
        logger.exception("Could not start Lyra worker")


@slack_app.event("app_mention")
def handle_app_mention(event, say, client, ack):
    if MOP_FLOW_CHANNEL and event.get("channel") == MOP_FLOW_CHANNEL:
        # No canal do fluxo a Lyra só processa o Excel do MOP; não conversa ali.
        ack()
        if _mop_attachment(event) is not None:
            threading.Thread(target=_handle_mop_flow_event, args=(event, say, client), daemon=True).start()
        return
    _dispatch(event, say, client, ack)


@slack_app.event("message")
def handle_message(event, say, client, ack):
    # Canal do fluxo "Reportar Oráculo": Excel de MOP é lido sem precisar marcar a Lyra
    # (inclui arquivo postado pela própria mensagem do fluxo).
    if MOP_FLOW_CHANNEL and event.get("channel") == MOP_FLOW_CHANNEL:
        ack()
        if _mop_attachment(event) is not None and event.get("subtype") in (None, "file_share", "bot_message"):
            threading.Thread(target=_handle_mop_flow_event, args=(event, say, client), daemon=True).start()
        return
    # Em canal, a conversa precisa de @menção (tratada em app_mention).
    # Em DM, aceita texto e arquivo (subtype "file_share").
    if event.get("bot_id"):
        ack()
        return
    is_im = event.get("channel_type") == "im"
    if is_im and event.get("subtype") in (None, "file_share"):
        _dispatch(event, say, client, ack)
    else:
        ack()


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
@flask_app.get("/")
@flask_app.get("/health")
def health():
    alive = _scheduler_thread is not None and _scheduler_thread.is_alive()
    return jsonify({
        "status": "ok",
        "service": "lyra-slack-bot",
        "scheduler_alive": alive,
        "last_tick": _scheduler_last_tick.isoformat() if _scheduler_last_tick else None,
    }), 200


def _debug_allowed() -> bool:
    return bool(DEBUG_TOKEN) and request.headers.get("X-Debug-Token") == DEBUG_TOKEN


@flask_app.get("/debug/status")
def debug_status():
    """Diagnóstico protegido (header X-Debug-Token). Sem DEBUG_TOKEN, responde 404."""
    if not _debug_allowed():
        return jsonify({"error": "not found"}), 404
    result: dict[str, Any] = {"state_persistent": STATE.persistent}
    try:
        google_client = _get_google_client()
        spreadsheet = _open_spreadsheet(google_client)
        result["sheets_ok"] = True
        result["worksheets"] = [ws.title for ws in spreadsheet.worksheets()]
    except Exception as exc:
        result["sheets_ok"] = False
        result["sheets_error"] = type(exc).__name__
    values = _read_mop_values()
    if values is not None:
        eps_col, email_col = (_find_col(values[0], "EPS"), _find_col(values[0], "Email")) if values else (None, None)
        rows = [r for r in values[1:] if any(str(c).strip() for c in r)]
        result["mop"] = {
            "pessoas": len(rows),
            "cabecalho": values[0] if values else [],
            "por_eps": {eps: len([r for r in rows if _eps_matches(_row_eps(r, eps_col, email_col), eps)]) for eps in EPS_CELULAS},
            "sem_eps_identificada": len([r for r in rows if not _row_eps(r, eps_col, email_col)]),
        }
    today = _now_brazil().date().isoformat()
    result["today"] = {k: v for k, v in STATE.snapshot().items() if today in k and not k.startswith("captured:")}
    return jsonify(result), 200


@flask_app.post("/slack/events")
def slack_events():
    return slack_handler.handle(request)


if __name__ == "__main__":
    # Rode com `python app.py` (Procfile) e UMA réplica: o agendador vive neste processo.
    _start_scheduler()
    flask_app.run(host="0.0.0.0", port=PORT)
