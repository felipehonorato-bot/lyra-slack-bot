"""Allow-listed, read-only Databricks query layer for Lyra."""
from __future__ import annotations
import concurrent.futures
import datetime as dt
import os
import re
from typing import Any
try:
    from databricks import sql as databricks_sql
except ImportError:
    databricks_sql = None

QUERY_TIMEOUT_SECONDS = 30
MAX_ROWS = 20
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

QUERY_TEMPLATES: dict[str, str] = {
    "report_diario": """SELECT date_utc3, ticket_last_eps, ticket_group, COUNT(DISTINCT support_ticket_id) AS volume FROM saex.gold.cx_support WHERE dt >= '{start_date}'{end_date_clause} AND ticket_last_eps IS NOT NULL{filters} GROUP BY date_utc3, ticket_last_eps, ticket_group ORDER BY date_utc3, volume DESC LIMIT {limit}""",
    "report_semanal": """SELECT date_utc3, ticket_last_eps, ticket_group, COUNT(DISTINCT support_ticket_id) AS volume FROM saex.gold.cx_support WHERE dt >= '{start_date}'{end_date_clause} AND ticket_last_eps IS NOT NULL{filters} GROUP BY date_utc3, ticket_last_eps, ticket_group ORDER BY date_utc3, volume DESC LIMIT {limit}""",
    "csat_analise": """SELECT ticket_last_agent_email, ticket_last_eps, COUNT(DISTINCT support_ticket_id) AS casos, COUNT(DISTINCT CASE WHEN csat_rating IS NOT NULL THEN support_ticket_id END) AS respondeu_csat, ROUND(AVG(CASE WHEN csat_rating IS NOT NULL THEN csat_rating END), 2) AS csat_medio, ROUND(SUM(CASE WHEN csat_rating IN (4, 5) THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(CASE WHEN csat_rating IS NOT NULL THEN 1 END), 0), 1) AS pct_promotores FROM saex.gold.cx_support WHERE dt >= '{start_date}'{end_date_clause} AND ticket_last_agent_email IS NOT NULL AND csat_rating IS NOT NULL{filters} GROUP BY ticket_last_agent_email, ticket_last_eps HAVING COUNT(DISTINCT support_ticket_id) >= 30 ORDER BY csat_medio ASC LIMIT {limit}""",
    "volume_vs_planejado": """SELECT date_utc3, queue_name, SUM(qtd) AS volume FROM saex.gold.cx_metrics_computed WHERE index = 'supports' AND date_utc3 >= '{start_date}'{end_date_clause}{filters} GROUP BY date_utc3, queue_name ORDER BY date_utc3, volume DESC LIMIT {limit}""",
    "tma": """SELECT ticket_group, ticket_last_eps, AVG(ticket_resolution_time) AS tma_media_seg, PERCENTILE(ticket_resolution_time, 0.5) AS tma_mediana_seg, PERCENTILE(ticket_resolution_time, 0.9) AS tma_p90_seg FROM saex.gold.cx_support WHERE dt >= '{start_date}'{end_date_clause} AND ticket_resolution_time IS NOT NULL{filters} GROUP BY ticket_group, ticket_last_eps ORDER BY tma_media_seg DESC LIMIT {limit}""",
    "reabertura": """SELECT ticket_last_eps, COUNT(DISTINCT support_ticket_id) AS total_casos, SUM(CASE WHEN has_reopened THEN 1 ELSE 0 END) AS reabertos, ROUND(SUM(CASE WHEN has_reopened THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(DISTINCT support_ticket_id), 0), 1) AS pct_reabertura FROM saex.gold.cx_support WHERE dt >= '{start_date}'{end_date_clause}{filters} GROUP BY ticket_last_eps ORDER BY pct_reabertura DESC LIMIT {limit}""",
    "sla": """SELECT ticket_group, ticket_last_eps, COUNT(DISTINCT support_ticket_id) AS total_casos, ROUND(AVG(CAST(sla_first_comment AS DOUBLE)) * 100, 1) AS pct_sla_cumprido FROM saex.gold.cx_support, UNNEST(ticket_queue_segments_metrics) AS t(qname, qdur, qwork, ttf, sla_first_comment, agents) WHERE dt >= '{start_date}'{end_date_clause} AND sla_first_comment IS NOT NULL{filters} GROUP BY ticket_group, ticket_last_eps ORDER BY pct_sla_cumprido ASC LIMIT {limit}""",
}
SLA_FALLBACK_TEMPLATE = """SELECT ticket_group, ticket_last_eps, COUNT(DISTINCT support_ticket_id) AS total_casos, ROUND(AVG(CAST(sla_first_comment AS DOUBLE)) * 100, 1) AS pct_sla_cumprido FROM saex.gold.cx_support WHERE dt >= '{start_date}'{end_date_clause} AND sla_first_comment IS NOT NULL{filters} GROUP BY ticket_group, ticket_last_eps ORDER BY pct_sla_cumprido ASC LIMIT {limit}"""
INTENT_ALIASES = {key: key for key in QUERY_TEMPLATES}

def _safe_date(value: Any) -> str:
    if isinstance(value, str) and _DATE_RE.fullmatch(value):
        try:
            dt.date.fromisoformat(value)
            return value
        except ValueError:
            pass
    return (dt.date.today() - dt.timedelta(days=7)).isoformat()

def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 200:
        return None
    return text.replace("'", "''")

def _end_date_clause(parameters: dict[str, Any], field: str = "dt") -> str:
    end = parameters.get("end_date")
    if isinstance(end, str) and _DATE_RE.fullmatch(end):
        try:
            dt.date.fromisoformat(end)
            return f" AND {field} <= '{end}'"
        except ValueError:
            pass
    return ""

def _filters(parameters: dict[str, Any], intent: str = "") -> str:
    clauses = []
    eps = _safe_text(parameters.get("eps_name"))
    queue = _safe_text(parameters.get("queue"))
    analyst = _safe_text(parameters.get("analyst"))
    if eps and intent != "volume_vs_planejado":
        clauses.append(f" AND ticket_last_eps = '{eps}'")
    if queue:
        field = "queue_name" if intent == "volume_vs_planejado" else "ticket_group"
        clauses.append(f" AND {field} = '{queue}'")
    if analyst and intent == "csat_analise":
        clauses.append(f" AND ticket_last_agent_email = '{analyst}'")
    return "".join(clauses)

def build_query(intent: str, parameters: dict[str, Any] | None = None, limit: int = MAX_ROWS) -> str:
    parameters = parameters or {}
    key = INTENT_ALIASES.get(intent)
    if key is None:
        raise ValueError(f"Intent não habilitada para consulta: {intent}")
    limit = max(1, min(int(limit), MAX_ROWS))
    field = "date_utc3" if key == "volume_vs_planejado" else "dt"
    return QUERY_TEMPLATES[key].format(start_date=_safe_date(parameters.get("start_date")), end_date_clause=_end_date_clause(parameters, field), filters=_filters(parameters, key), limit=limit).strip()

def _run_once(query: str) -> dict[str, Any]:
    if databricks_sql is None:
        return {"ok": False, "error": "dependência databricks-sql-connector não instalada"}
    required = ("DATABRICKS_HOST", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        return {"ok": False, "error": "configuração Databricks ausente: " + ", ".join(missing)}
    connection = cursor = None
    try:
        connection = databricks_sql.connect(server_hostname=os.environ["DATABRICKS_HOST"], http_path=os.environ["DATABRICKS_HTTP_PATH"], access_token=os.environ["DATABRICKS_TOKEN"])
        cursor = connection.cursor()
        cursor.execute(query)
        columns = [item[0] for item in (cursor.description or [])]
        rows = [dict(zip(columns, row)) for row in cursor.fetchmany(MAX_ROWS)]
        return {"ok": True, "columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as exc:
        return {"ok": False, "error": f"falha na consulta Databricks: {type(exc).__name__}"}
    finally:
        for resource in (cursor, connection):
            try:
                if resource is not None:
                    resource.close()
            except Exception:
                pass

def execute_query(query: str, timeout_seconds: int = QUERY_TIMEOUT_SECONDS) -> dict[str, Any]:
    if not query.lstrip().upper().startswith("SELECT"):
        return {"ok": False, "error": "apenas consultas SELECT são permitidas"}
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run_once, query)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError:
        return {"ok": False, "error": f"consulta excedeu {timeout_seconds} segundos"}
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

def query_intent(intent: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    result = execute_query(build_query(intent, parameters))
    if intent == "sla" and not result.get("ok"):
        params = parameters or {}
        fallback = SLA_FALLBACK_TEMPLATE.format(start_date=_safe_date(params.get("start_date")), end_date_clause=_end_date_clause(params), filters=_filters(params, "sla"), limit=MAX_ROWS).strip()
        fallback_result = execute_query(fallback)
        if fallback_result.get("ok"):
            fallback_result["fallback_used"] = True
            return fallback_result
    return result
