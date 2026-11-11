"""Lyra Slack bot — relay Slack <-> Toqan + rotinas de gestão das EPSs (v5.14).

v5.14 — Tabela do dia (DAY_TABLE): CSAT do mês e do D-1 por fila das duas EPSs numa consulta só (Indicadores
        v1.11, "tabela do dia"), em cache até a meia-noite e carregada junto com o report. "Resultado por fila",
        "como está a <fila>", "qual fila/EPS mais impacta", "pior fila" saem dela em segundos, com o mesmo número em
        toda resposta (as respostas livres recebem esses números como oficiais). Impacto = CSAT do conjunto com x
        sem a fila; Agentforce fora. Ritmo do mês: quanto a fila precisa nos dias que faltam para fechar na meta (na
        cobrança do report e nas respostas). Até o dia 5, o mês vem com o mês anterior fechado de contexto.
        👍/👎 nas respostas (evento reaction_added): registra na aba "Avaliações"; 👎 de alguém do iFood pergunta "o
        que ficou errado?" e a resposta vira aprendizado. Toda conversa vai para a aba "Conversas" (rota, tempo,
        status). Auditoria diária às 18h (amostra de 10, regras da Lyra) e saúde semanal na segunda 9h40 no canal de
        alerta. Fechamento do mês no 1º dia útil às 10h, no canal de cada EPS.

v5.13 — Respostas grandes no visual do report diário (o report em si não muda): título "<status> *Rótulo ·* `fila/EPS`
        *— período* · número", seções com divisória (📍 Resultado · 👥 Por supervisor · 👤 Operadores · 💡 Leitura),
        linhas curtas, nome sem CAIXA ALTA, e-mail sem crase, 10 itens por padrão e o resto na planilha. Vale para a
        visão de equipe/supervisores, ofensores/lista de operadores, reincidentes e para as respostas livres da Lyra
        (instrução de layout no prompt + divisórias pelo app). Uma mensagem só de andamento, editada e apagada quando
        a resposta chega. Pergunta de análise ("por que", "quem piorou", "quanto contribuiu") que cita supervisor ou
        operador vai para a análise livre, não para as listas prontas. Reincidentes 4 semanas: consulta única agrupada
        (SQL na Indicadores v1.9.2), leitura tolerante (separador, ordem das colunas, formato longo) e alerta com o
        início da resposta quando não der para ler. Contra sobrecarga: bases de operadores ficam em cache até a
        meia-noite (pedidos iguais simultâneos viram uma consulta só), pré-carga da semana depois do report
        (PREWARM_BASES) e pergunta repetida em 30 min reaproveita a resposta (RECENT_ANSWER_TTL).
        Canais de melhorias (MELHORIAS_CHANNELS: #ef-melhorias-aec C0C5NDFB87R, #ef-melhorias-csu C0C6Y5W8ETS): a Lyra
        lê toda thread aberta pelo Fluxo Owners CX. Moedas: confere os dados, pede o que falta na thread e abre o
        chamado no formato do Reward Engine (Número do Ticket, ID do Cliente, ID do Pedido, Id ou Nome da Missão,
        Descreva o problema, Tipo de problema, Evidências) no destino da EPS (CHAMADOS_DESTINO — por padrão os canais
        de teste; com destino de teste o webhook do Rewards nunca é chamado). A resposta no chamado volta para a
        thread de origem. Outros tópicos (Ajuda, Escalar Ticket...): responde na thread pela Lyra Conhecimento e
        responde de novo quando marcarem a Lyra na thread.
        Crises (subagente Lyra Crises): antes de cobrar, a Lyra confere se teve crise no período (CRISIS_CHECK). No
        report, em paralelo com a consulta do D-1: fila cobrada em dia de crise ganha a linha 🚨 e a cobrança vira
        "o que a operação fez durante a crise". Nos status de hora em hora e prints: checagem das últimas 3h,
        reaproveitada por 30 min (CRISIS_CHECK_TTL). Falha na checagem nunca trava a cobrança.
        ClubIA: dúvida e investigação de Clube vão para a ClubIA (também nas threads de melhorias). Variação do CSAT com
        motivo pelo nome de negócio, lista na direção do efeito e, se o CSAT subiu, sem cobrança nem esteira. MOP pedido
        na visão completa ("MOP da AeC") sai só da EPS citada. Pedido de plano fora da thread do report: a Lyra busca o
        problema da fila sozinha. Na DM, só mensagem curta/de continuação puxa a conversa anterior.
        Aprendizados: quem é do iFood pode ensinar a Lyra na conversa ("da próxima vez traz o n"); o app extrai o
        aprendizado, guarda na aba "Aprendizados" (escopo Todos/AeC/CSU), confirma na thread, avisa no canal de alerta
        e manda os ativos (até 30) junto de toda conversa do escopo. Meta, cálculo, política e cobrança não viram
        aprendizado. "o que você aprendeu?" lista; "esquece o aprendizado N" desativa (só iFood). LEARNINGS=0 desliga.
        Perguntas sobre a própria Lyra (quem é, nome/constelação, como aprende) têm instrução própria.
        Regras oficiais do CSAT (Indicadores v1.10): L3, data da avaliação, Madrugada pelos operadores da célula
        Madrugada do MOP (o app manda a lista em todo pedido da AeC/iFood), filas normalizadas (PF Super Clientes,
        PF Revisão Manual), Agentforce CX = IA (só WillNegativas, nunca somada a EPS), BU FOOD/MULTI, Front/BKO e
        impacto da fila = CSAT do conjunto com x sem a fila. Recorte padrão = mês (resultado, ranking, pior, impacto);
        D-1 só quando pedirem. Lembretes: "me lembra amanhã às 14h de X" vira DM no horário.

v5.12 — Visão de equipe ("minha equipe", "equipe da X", "por supervisor"): pelo MOP (supervisor/coordenador) e pela
        base de operadores do período (com o anterior para o Δ: D-1 x D-8, semana x semana, mês x mesmos dias), traz
        CSAT x meta, positivas faltantes, quadrantes (amostra pequena < 10), dispersão Q4÷Q1, limite de controle,
        concentração das notas 1–3, tabela por supervisor (coordenação) e os Q4 com mais positivas faltantes. Plano
        escrito na thread do report não dispara essas listas. Reincidentes 4 semanas: Q4 nas 4 últimas semanas
        (5+ pesquisas em cada), pela base de operadores por semana. "Quais os 10 operadores mais reincidentes de
        CX Suporte?" vira ranking de semanas no Q4. Operador aparece como "Nome · e-mail".

v5.11 — DM aberta pelo e-mail do Slack: domínio iFood (DM_ALLOWED_DOMAINS) vê tudo, e-mail de EPS vê só a própria EPS
        (precisa do escopo users:read.email). DM com memória da conversa (últimas mensagens / thread), "ontem" completa
        o pedido anterior. Na DM a resposta sai na thread da pergunta, como no canal. A conversa recebe a data de hoje,
        e data digitada no futuro (29/11 pedido em 30/10) vira a data passada mais provável, avisando. Sem pergunta de volta: falta indicador = CSAT, falta período = D-1, falta fila = todas.
        "Resultado por operador" / "ofensores": quem tem visão completa (e-mail iFood ou canal interno) recebe direto
        no chat (até 15, do pior para o melhor; ofensores = Q4), com a planilha completa se passar disso. Nos canais
        das EPSs segue em planilha. Período pedido: ontem, mês ou semana; fila citada filtra. "Top N", "melhores" e
        "mais impacto" (avaliações × gap até a meta) também. Quem tem visão completa pode ver operador nas respostas
        livres da Lyra, com o NOME do MOP ao lado do usuário (OPERATOR_NAMES=all: em qualquer conversa, cada EPS só
        os dela; internal: só visão completa; off: só planilha). O report diário segue sem nomes.

v5.10 — PRINT_READING=0 desliga a leitura dos prints; falha técnica na leitura (download, Toqan, resposta fora do
        formato) vira alerta para o Felipe e não aparece para a EPS. Só print ilegível de verdade é devolvido.
        STATUS_SHADOW aceita lista de EPS em teste (ex.: AeC) e STATUS_TEST_CHANNELS guarda o canal de testes de cada
        EPS, para o modo teste seguir no canal de testes depois que EPS_CHANNELS virar o canal oficial.
        Acompanhamento de Fila da AeC (print hora a hora, só o CONSOLIDADO): cobra HC abaixo do planejado com volume
        no previsto, TMA > 110% do plan e SLA 1ª resposta abaixo da meta (SLA_METAS ou o P SLA do print). Print
        ilegível é pedido uma vez por thread; depois só alerta.

v5.9 — TMA_IN_REPORT=0 tira o TMA do report e da cobrança (CSAT segue normal).

v5.8 — EPS_EXTRA_CHANNELS: canais extras de conversa com recorte de uma EPS (sem report).

v5.7 — controles em print (Volume, Produtividade): a Lyra lê a imagem (upload no Toqan), confere pelos totais do
       próprio print e cobra (fila acumulando, gente sobrando/faltando, logado sem produção, equipe abaixo da célula);
       se não conseguir ler, diz que o print não está legível. Review: CSAT informado x promotoras/detratoras.

v5.6 — status de hora em hora em modo teste (STATUS_SHADOW=1): lê o canal real e responde no canal de testes da EPS;
       cobra quando o CSAT piora com o mesmo próximo passo; NRT sem dados não é cobrado.

v5.5 — sugestão de plano: Lyra consulta a Conhecimento (política/matriz), causa só a do dado, sem régua inventada;
       o app tira da resposta promessa de planilha/arquivo que ele não gerou.

v5.4 — fila com ação em andamento para o mesmo problema: cobra status e efeito, não ação nova; prazo vencido: resultado
       ou novo plano. Problema diferente da ação: pede plano para o problema novo.

v5.3 — mensagens montadas pelo app (thread do report, variação, esteira) saem com divisória entre as seções.

v5.2 — lê o status de hora em hora das EPSs (STATUS_CHANNELS) e cobra: CSAT/SLA fora da meta da fila, justificativa
       repetida, próximo passo genérico, previsão sem prazo. Causa do iFood fica só no registro (não cobra SLA).

v5.1 — dúvida de processo/política/agente: o app manda a Lyra chamar a Lyra Conhecimento (sem busca externa nem chute).

v5.0 — pergunta de causa: análise de variação primeiro; se a queda vem do efeito mix (mix ≥ 80% da queda e
       performance estável), responde só a leitura do mix, sem cobrar plano e sem esteira. Filas sem meta: "sem meta".

v4.7 — thread do report em seções D-1 x Mês + Leitura; conversa na thread leva o contexto da fila.

v4.6 — TMA em segundos; dispersão pela régua do Cockpit (CSAT Q4 ÷ Q1); esteira de impacto do mês (Lyra Qualidade
       v2.0) na thread das filas cobradas; owners por nome; Review e Canarinhos fora; chamados de moedas
       (Fluxo Owners CX -> #rewards-engine-support-cx).

v4.5 — TMA oficial no report (tempo de atribuição por interação × interações por ticket, vs plan da célula),
       decomposto em "mais interações" x "tempo por interação"; fila fora do alvo de CSAT OU TMA é cobrada.

v4.4 — report de analista: problema do D-1 x do mês, quadrantes mês x D-1 com dispersão, fila sem CSAT
       no D-1 fica fora; Lyra lê a thread ao vivo e comenta o plano (feedback de analista) além de registrar.

v4.3 — alarmística dos agentes: teste chega em cada subagente, reaviso enquanto continuar parado,
       teste na hora quando uma conversa volta com erro de acesso, aviso de agente esquecido na troca do token.

v4.2 — o APP monta o layout do report: título "Governança · <Fila> — dd/mm" no canal e detalhe
       + cobrança na thread. O modelo só devolve dados (JSON por fila); texto livre também é lido.

v4.1 — bloco por fila enxuto (3–4 linhas: status, D-1 vs meta, ofensor, cobrança 👉 com owner).

v4.0 — report em BLOCOS POR FILA no canal da EPS (um post por fila, cada um com a sua thread);
cobrança pelo D-1; owner marcado só quando o D-1 ficou abaixo da meta; compromissos e escalation por fila.

v3.9 — sem nome de operador no Slack; owners das filas marcados nas cobranças; escalation 5h
depois do report para quem não respondeu; Excel de operadores (CSAT + quadrante) sob pedido.

v3.8 — "roda o report [da aec|da csu]" na DM: dispara o report na hora (teste manual).

v3.7 — monitoramento dos agentes (Lyra + MONITORED_AGENTS: Nexus, Vera, ClubIA…) 4x ao dia, DM só quando
um agente para ou volta; lembrete do token do Databricks no 6º dia (validade de 7 dias a partir de
"troquei o token" na DM, ou inferida quando um agente volta depois de erro de token).

v3.6 — MOP conversacional: span por supervisor/coordenador, busca das pessoas citadas na
pergunta (só da EPS do canal) e envio do Excel do MOP quando pedem ("me manda o MOP").

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
- DM: DM_ALLOWED_USERS e e-mails iFood (visão completa) ou de EPS (só a EPS); canal não configurado não recebe resposta.

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
import math
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
TIMEOUT_ERROR_MESSAGE = ("Essa travou do meu lado: a consulta passou do tempo e eu parei pra não te deixar esperando. "
                         "Já avisei o time. Tenta de novo daqui a pouco?")
INTERACTIVE_MAX_POLLS = int(os.getenv("INTERACTIVE_MAX_POLLS", str(MAX_POLL_ATTEMPTS)))  # conversa: 30 min
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
    {t for t in _parse_id_list(ALERT_CHANNEL) if t.startswith("U")}
)
# DM liberada para e-mails desses domínios (visão completa). E-mail de EPS (aec/csu) vê só a própria EPS. Vazio = só a lista.
DM_ALLOWED_DOMAINS = {d.strip().lower().lstrip("@") for d in os.getenv("DM_ALLOWED_DOMAINS", "ifood.com.br").split(",")
                      if d.strip()}
CONSOLIDATED = "Consolidado"

# Células de cada EPS (fonte: Felipe, out/2026). O nome da EPS também é o trecho
# procurado no e-mail do operador ("aec" em @if-aec..., "csu" em ...csu...).
# Owners de cada fila (IDs do Slack), marcados nas cobranças do report.
# Pode ser sobrescrito por FILA_OWNERS="CX Suporte:U1|U2;Madrugada:U3" (aceita também "@Nome Sobrenome").
_DEFAULT_FILA_OWNERS: dict[str, list[str]] = {
    "CX Suporte": ["U09GNBTALNN", "U094HUNCPFS"],
    "Madrugada": ["U094HUNCPFS"],
    "CX Review - AeC": ["U076W2160TF"],
    "CX Review - CSU": ["U05EVUPKF0R"],
    "CX Super Cliente - AeC": ["U09GNBTALNN"],
    "CX Super Cliente - CSU": ["U05EVUPKF0R"],
    # por nome: o app procura o usuário no Slack (escopo users:read) e marca o ID certo
    "PF Cancelamento": ["U0A6C135VK5"],
    "PF Super Clientes": ["U0A6C135VK5"],
    "PF Revisão Manual": ["U0A6C135VK5"],
    "CX Denúncia": ["U02CL56C46N"],
    "Fraudes DX": ["U02CL56C46N"],
}


def _parse_owners(raw: str) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for part in raw.split(";"):
        if ":" in part:
            fila, ids = part.split(":", 1)
            ids_list = [i.strip() for i in ids.split("|") if i.strip()]
            if fila.strip() and ids_list:
                owners[fila.strip()] = ids_list
    return owners


FILA_OWNERS: dict[str, list[str]] = {**_DEFAULT_FILA_OWNERS, **_parse_owners(os.getenv("FILA_OWNERS", ""))}  # variável complementa/substitui por fila

# TMA planejado por célula (aba PLAN do Excel mensal): tempo único (s) e média de interações.
# TMA = tempo de atribuição por interação × média de interações por ticket (coluna X da CAPA).
# Filas que não têm TMA (não aparece no report nem é cobrado)
NO_TMA_FILAS = {"DX - PF Contestação", "DX - PF Contestação Bloqueio temporário"}
# TMA_IN_REPORT=0 tira o TMA do report e da cobrança (ex.: enquanto a query não bate com a planilha de eficiência)
TMA_IN_REPORT = os.getenv("TMA_IN_REPORT", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
_DEFAULT_TMA_PLAN: dict[str, tuple[float, float]] = {
    "CX Suporte": (520, 1.8), "Madrugada": (562, 1.89),
    "CX Review - AeC": (620, 2.05), "CX Review - CSU": (620, 2.05),
    "CX Super Cliente - AeC": (725, 1.73), "CX Super Cliente - CSU": (725, 1.73),
    "PF Cancelamento": (450, 1.23), "PF Super Clientes": (400, 1.23), "PF Revisão Manual": (410, 1.27),
    "CX Denúncia": (560, 1.0), "Fraudes DX": (585, 1.0),
}


def _parse_tma_plan(raw: str) -> dict[str, tuple[float, float]]:
    """'CX Suporte:520/1.8;Madrugada:562/1.89' -> {fila: (tempo_unico_s, interacoes)}"""
    plan: dict[str, tuple[float, float]] = {}
    for part in raw.split(";"):
        if ":" not in part or "/" not in part:
            continue
        fila, values = part.rsplit(":", 1)
        tempo, inter = values.split("/", 1)
        try:
            plan[fila.strip()] = (float(tempo.replace(",", ".")), float(inter.replace(",", ".")))
        except ValueError:
            continue
    return plan


TMA_PLAN: dict[str, tuple[float, float]] = {**_DEFAULT_TMA_PLAN, **_parse_tma_plan(os.getenv("TMA_PLAN", ""))}
ESCALATION_DELAY = timedelta(hours=5)

EPS_CELULAS: dict[str, list[str]] = {
    "AeC": [
        "CX Suporte", "Madrugada", "CX Review - AeC", "CX Super Cliente - AeC",
    ],
    "CSU": [
        "CX Review - CSU", "CX Super Cliente - CSU", "PF Cancelamento",
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
# Canais extras de conversa com recorte de uma EPS (ex.: teste com alguém da EPS): a Lyra responde quando marcada,
# só com dados daquela EPS; report e rotinas continuam no canal principal (EPS_CHANNELS).
# Formato: "AeC:C111,AeC:C222,CSU:C333" (pode repetir a EPS).
EPS_EXTRA_CHANNELS: list[tuple[str, str]] = [
    (part.split(":", 1)[0].strip(), part.split(":", 1)[1].strip())
    for part in os.getenv("EPS_EXTRA_CHANNELS", "").split(",") if ":" in part and part.split(":", 1)[1].strip()
]
for _eps, _channel in EPS_EXTRA_CHANNELS:
    _known = next((key for key in EPS_CELULAS if key.casefold() == _eps.casefold()), _eps)
    CHANNEL_SCOPE.setdefault(_channel, _known)

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
    "oráculo", "oraculo", "variante", "eps", "span", "spam", "gestor", "gestão", "gestao",
    "time do", "time da", "turno", "escala", "férias", "ferias", "licença", "licenca",
    "entrada", "saída", "saida", "formato de trabalho", "remoto", "presencial", "quem é", "quem e",
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

# --- Saúde dos agentes e do token do Databricks ---------------------------------------
# Agentes monitorados além da Lyra: "Nexus:<api_key>,Vera:<api_key>,ClubIA:<api_key>"
MONITORED_AGENTS = _parse_channel_map(os.getenv("MONITORED_AGENTS", ""))
AGENT_CHECK_TIMES = [
    datetime_time(int(h), 30) for h in os.getenv("AGENT_CHECK_HOURS", "7,11,15,19").split(",") if h.strip().isdigit()
]
AGENT_CHECK_MAX_POLLS = 30  # 30 x 10s = 5 min por agente
# O token do Databricks dura DATABRICKS_TOKEN_VALIDITY_DAYS a partir da troca.
DATABRICKS_TOKEN_VALIDITY_DAYS = int(os.getenv("DATABRICKS_TOKEN_VALIDITY_DAYS", "7"))
# Agentes que usam o MESMO token do Databricks (só para o texto do alerta)
# Agentes que não consultam o Databricks: o teste só confere se respondem (sem consulta, sem alerta de token)
NO_DATA_AGENTS = {a.strip().casefold() for a in os.getenv("NO_DATA_AGENTS", "Em preparo").split(",") if a.strip()}
PING_PROMPT = (
    "TAREFA INTERNA DE MONITORAMENTO — não é pergunta de usuário e não vai para o Slack. "
    "Não consulte nada. Responda APENAS: OK"
)
SHARED_TOKEN_AGENTS = [a.strip() for a in os.getenv("SHARED_TOKEN_AGENTS", "Nexus,Vera,ClubIA").split(",") if a.strip()]
DATABRICKS_TOKEN_RENEWED = os.getenv("DATABRICKS_TOKEN_RENEWED", "").strip()  # opcional: data da última troca
TOKEN_REMINDER_TIME = datetime_time(9, 30)
TOKEN_ERROR_HINTS = ("403", "401", "invalid access token", "token", "unauthorized", "unauthenticated",
                     "expired", "expirado", "permission", "permiss", "credential", "credencia")
HEALTHCHECK_PROMPT = (
    "EPS: iFood\n"
    "Pedido: verificação de acesso\n\n"
    "TAREFA INTERNA DE MONITORAMENTO — não é pergunta de usuário e não vai para o Slack.\n"
    "Se você consulta dados direto: rode SELECT COUNT(*) AS n FROM saex.gold.cx_support "
    "WHERE DATE(ticket_created_at) >= date_sub(current_date(), 2).\n"
    "Se você usa subagentes: chame CADA subagente que consulta dados (ex.: Lyra Indicadores e Lyra Qualidade), "
    "um por um, com 'EPS: iFood' e 'Pedido: verificação de acesso'.\n"
    "Responda APENAS uma linha: 'OK <n>' se TODAS as consultas funcionaram, ou "
    "'ERRO: <nome do subagente, se houver>: <mensagem técnica exata do erro>' se qualquer uma falhou."
)

THREAD_DELIMITER = "===THREAD==="

FILA_BLOCK_RE = re.compile(r"^\s*===\s*FILA\s*:\s*(?P<fila>.+?)\s*===\s*$", re.MULTILINE)
DAILY_REPORT_PROMPT = (
    "Report diário por fila. ESTA TAREFA É DO APP: este contrato vale acima de qualquer layout do seu prompt. "
    "Você NÃO escreve o texto do Slack — o app monta o layout. Você devolve só os dados e a frase de cobrança.\n\n"
    "1. Chame o Lyra Indicadores (EPS do escopo, 'Pedido: dados do report diário').\n"
    "2. Para CADA fila da EPS que teve avaliação de CSAT no D-1, escreva exatamente duas linhas "
    "(fila sem avaliação no D-1 fica de fora — não escreva nada sobre ela):\n"
    "===FILA: <nome exato da fila>===\n"
    '{"d1": 91.7, "n": 399, "var": -0.2, "meta": 94, "mes": 93.9, '
    '"ofensor": "pedido atrasado", "ofensor_pp": -2.8, "ofensor_mes": "pedido atrasado", "ofensor_mes_pp": -1.9, '
    '"quad_mes": {"q1": 39, "q2": 46, "q3": 12, "q4": 14}, "quad_d1": {"q1": 20, "q2": 18, "q3": 9, "q4": 16}, '
    '"disp_mes": {"q1": 98.5, "q4": 78.0}, "disp_d1": {"q1": 97.0, "q4": 62.0}, '
    '"reincidentes": 3, "tma_tpi_d1": 379.6, "tma_int_d1": 1.92, "tma_tpi_mes": 368.4, "tma_int_mes": 1.90, "tma_tratados_d1": 2650, '
    '"compromisso": "", "compromisso_cobre": null, '
    '"cobranca": "Pedido atrasado tira 2,8 p.p. no D-1 e já é o problema do mês, e a dispersão aumentou — o que muda hoje na tratativa de atraso?", '
    '"elogio": ""}\n'
    "3. Campos: d1 = CSAT D-1 em %; n = avaliações no D-1; var = variação do D-1 vs dia anterior em p.p. (negativo se caiu); "
    "meta em % (null se não definida); mes = CSAT do mês em %; ofensor / ofensor_pp = motivo de maior impacto negativo no D-1 "
    "e o impacto em p.p. (negativo); ofensor_mes / ofensor_mes_pp = o mesmo no mês; "
    "quad_mes / quad_d1 = quantidade de operadores em cada quadrante no mês e no D-1; "
    "disp_mes / disp_d1 = CSAT (%) dos operadores do Q1 e do Q4 no mês e no D-1 (dispersão = Q4 ÷ Q1, régua do Cockpit); "
    "reincidentes = operadores reincidentes no Q4; "
    "tma_tpi_d1 / tma_tpi_mes = tempo de atribuição por interação em SEGUNDOS; tma_int_d1 / tma_int_mes = média de interações por ticket; "
    "tma_tratados_d1 = interações tratadas no D-1 (copie do bloco TMA POR FILA do Indicadores; o app calcula o TMA e compara com o plan); "
    "compromisso = compromisso em aberto DESTA fila no contexto ('<ação> · prazo <dd/mm>') ou vazio; "
    "compromisso_cobre = true se essa ação ataca o problema de hoje (mesmo indicador/causa), false se o problema de hoje é outro, null se não há compromisso.\n"
    "4. cobranca (se CSAT do D-1 abaixo da meta OU TMA do D-1 acima do plan — o plan vem na lista PLAN DE TMA desta mensagem): "
    "UMA frase de analista de CX, assertiva, que conecta os dados — problema do D-1 vs do mês (estrutural ou pontual), "
    "a dispersão (índice Q4÷Q1 com duas casas, ex.: 0,86 → 0,76, nunca em %; caindo = dispersão aumentou = comportamento operacional) e o TMA (se subiu por mais interações por ticket = não resolveu "
    "no primeiro contato; se por tempo por interação = atendimento mais longo) — e termina numa pergunta direta sobre a ação. "
    "NÃO repita o valor do TMA nem do CSAT na cobrança (o app já mostra os números exatos nas seções acima; diga só "
    "'acima do plan' / 'abaixo da meta'). Interações por ticket são interações, não reaberturas. "
    "Se há compromisso em aberto que ataca o problema (compromisso_cobre true), NÃO peça ação nova: a pergunta é sobre o status "
    "e o efeito da ação que já está rodando (ex.: 'a ação X está segurando o problema?'). Se o problema de hoje é outro, peça a ação para ele. "
    "Sem 'Plano aqui na thread' (o app completa). elogio (CSAT e TMA no alvo): reconhecimento curto e específico.\n"
    "5. Só isso: nenhum título, texto, bullet, separador (---) ou comentário fora dessas linhas. Números com ponto decimal. "
    "Nunca nome, usuário ou e-mail de operador. Não escreva menções (@).\n"
    "6. Se qualquer consulta falhar ou voltar vazia: responda SOMENTE uma linha começando com ERRO: e o motivo."
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
APP_VERSION = "5.34.0"
_BOOT_AT = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
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
    for target in [t.strip() for t in ALERT_CHANNEL.split(",") if t.strip()]:
        try:
            slack_app.client.chat_postMessage(channel=target, text=f"Lyra — {text}" if text.lstrip().startswith("⚠️")
                                              else f"⚠️ Lyra — {text}")
        except Exception:
            logger.exception("Could not post alert to %s", target)


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


_MADRUGADA_CACHE: dict[str, Any] = {"at": 0.0, "emails": []}


def _madrugada_emails() -> list[str]:
    """E-mails da célula Madrugada no MOP (cache de 30 min). A fila Madrugada do CSAT é definida por esses operadores."""
    if time.time() - _MADRUGADA_CACHE["at"] < 1800:
        return _MADRUGADA_CACHE["emails"]
    emails: list[str] = []
    try:
        values = _read_mop_values() or []
        if len(values) > 1:
            header = values[0]
            c_cel, c_mail = _find_col(header, "Célula"), _find_col(header, "Email")
            if c_cel is not None and c_mail is not None:
                emails = sorted({str(r[c_mail]).strip().lower() for r in values[1:]
                                 if c_cel < len(r) and c_mail < len(r) and _norm_text(r[c_cel]) == "madrugada"
                                 and "@" in str(r[c_mail])})
    except Exception:
        logger.warning("Could not read Madrugada list from MOP", exc_info=True)
    if emails or not _MADRUGADA_CACHE["emails"]:
        _MADRUGADA_CACHE.update(at=time.time(), emails=emails)
    return _MADRUGADA_CACHE["emails"]


def _madrugada_line(eps: str | None) -> str:
    if eps is not None and _compact(eps) != _compact("AeC"):
        return ""
    emails = _madrugada_emails()
    if not emails:
        return ""
    return ("\nAo chamar a Lyra Indicadores (ou a Lyra Qualidade), inclua no pedido a linha: Madrugada: "
            + ", ".join(emails) + " (operadores da célula Madrugada no MOP; tudo o que eles atendem é da fila Madrugada).")


def _scope_instruction(eps: str | None) -> str:
    """Bloco de escopo injetado em toda mensagem enviada ao Toqan."""
    try:
        metas = "\n" + _metas_text(eps)
    except Exception:
        metas = ""
    return _scope_instruction_base(eps) + _madrugada_line(eps) + metas


def _scope_instruction_base(eps: str | None) -> str:
    if eps is None:
        return ("ESCOPO: visão interna iFood — todas as EPS. Pode comparar EPS. Agentforce CX é atendimento de IA: "
                "nunca some em AeC ou CSU nem compare com uma EPS.")
    others = ", ".join(e for e in EPS_CELULAS if _compact(e) != _compact(eps)) or "outras EPS"
    celulas = _celulas_of(eps)
    return (
        f"ESCOPO OBRIGATÓRIO: este canal é exclusivo da EPS {eps}. "
        + (f"Filas da {eps} (fila do ticket = ticket_last_form.queue_name): {'; '.join(celulas)}. Use só essas. " if celulas else "")
        + f"Para operadores (Q4, rankings), use só e-mails da {eps}: {_eps_filter_sql(eps)}. "
        + f"Use somente filas, operadores, motivos, compromissos e números da {eps}. "
        f"NUNCA mencione, compare ou mostre dados de {others}, nem o resultado consolidado do iFood. "
        f"Se pedirem dados de outra EPS, diga com naturalidade que aqui você acompanha só a {eps}. "
        "Nunca mencione este escopo, filtros, e-mails, SQL ou como o canal foi configurado."
    )


_DM_SCOPE_CACHE: dict[str, tuple[bool, str | None]] = {}
_DM_EMAIL_ALERTED = False


def _dm_scope(user: str) -> tuple[bool, str | None]:
    """Quem pode usar a DM e com qual visão, pelo e-mail do Slack:
    DM_ALLOWED_USERS ou domínio iFood (DM_ALLOWED_DOMAINS) = visão completa; e-mail de EPS (aec/csu no domínio) = só
    a EPS dela; resto = sem DM. Precisa do escopo users:read.email no app do Slack."""
    global _DM_EMAIL_ALERTED
    if user in DM_ALLOWED_USERS:
        return True, None
    if user in _DM_SCOPE_CACHE:
        return _DM_SCOPE_CACHE[user]
    email = ""
    try:
        info = slack_app.client.users_info(user=user)
        email = str(((info.get("user") or {}).get("profile") or {}).get("email") or "").lower()
    except Exception:
        logger.warning("Could not read e-mail of %s", user, exc_info=True)
    if not email:
        if not _DM_EMAIL_ALERTED:
            _DM_EMAIL_ALERTED = True
            _alert("DM: não consegui ler o e-mail de quem chamou a Lyra. Inclua o escopo users:read.email no app do Slack "
                   "(OAuth & Permissions) e reinstale; até lá a DM fica só para DM_ALLOWED_USERS.")
        return False, None
    domain = email.rsplit("@", 1)[-1]
    result: tuple[bool, str | None] = (False, None)
    eps_hit = next((e for e in EPS_CELULAS if _eps_pattern(e) and _eps_pattern(e) in domain), None)
    if eps_hit:
        result = (True, eps_hit)
    elif any(domain == d or domain.endswith("." + d) for d in DM_ALLOWED_DOMAINS):
        result = (True, None)
    _DM_SCOPE_CACHE[user] = result
    return result


def _event_scope(event: dict[str, Any]) -> tuple[bool, str | None]:
    """(permitido?, EPS do escopo). EPS None = visão completa."""
    if event.get("channel_type") == "im":
        return _dm_scope(str(event.get("user") or ""))
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


TOQAN_RETRY_CODES = {409, 429, 500, 502, 503, 504}
TOQAN_RETRY_WAITS = (10, 30, 60)

# --- Limite de uso do Toqan (o Toqan devolve 429/409 quando a chave da Lyra faz pedidos demais) ------------------
# Todo pedido ao Toqan passa por um balde de fichas (TOQAN_RPM por minuto). Conversa com gente tem prioridade: as
# tarefas de fundo (prints, releituras, report, aprendizado) só usam o balde deixando uma reserva para a conversa e
# rodam no máximo TOQAN_BG_PARALLEL conversas ao mesmo tempo.
TOQAN_RPM = float(os.getenv("TOQAN_RPM", "40"))
TOQAN_BURST = float(os.getenv("TOQAN_BURST", "8"))
TOQAN_BG_RESERVE = float(os.getenv("TOQAN_BG_RESERVE", "3"))
TOQAN_BG_PARALLEL = int(os.getenv("TOQAN_BG_PARALLEL", "3"))
_TOQAN_TL = threading.local()
_TOQAN_BUCKET = {"tokens": TOQAN_BURST, "at": time.time()}
_TOQAN_BUCKET_LOCK = threading.Lock()
_TOQAN_BG_SEM = threading.BoundedSemaphore(max(1, TOQAN_BG_PARALLEL))


def _toqan_interactive() -> bool:
    return bool(getattr(_TOQAN_TL, "interactive", False))


def _toqan_take_token() -> None:
    """Espera uma ficha do balde. Fundo só pega se sobrar a reserva da conversa."""
    need = 1.0 if _toqan_interactive() else 1.0 + TOQAN_BG_RESERVE
    while True:
        with _TOQAN_BUCKET_LOCK:
            now = time.time()
            _TOQAN_BUCKET["tokens"] = min(TOQAN_BURST, _TOQAN_BUCKET["tokens"] + (now - _TOQAN_BUCKET["at"]) * TOQAN_RPM / 60)
            _TOQAN_BUCKET["at"] = now
            if _TOQAN_BUCKET["tokens"] >= need:
                _TOQAN_BUCKET["tokens"] -= 1
                return
            wait = (need - _TOQAN_BUCKET["tokens"]) * 60 / TOQAN_RPM
        time.sleep(min(max(wait, 0.2), 5))


class _ToqanSlot:
    """Tarefa de fundo: no máximo TOQAN_BG_PARALLEL conversas no Toqan ao mesmo tempo. Conversa com gente não espera."""

    def __enter__(self) -> "_ToqanSlot":
        self.bg = not _toqan_interactive()
        if self.bg:
            _TOQAN_BG_SEM.acquire()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.bg:
            _TOQAN_BG_SEM.release()


def _toqan_request(method: str, payload: dict[str, Any], api_key: str | None = None,
                   http_method: str | None = None) -> dict[str, Any]:
    """Make one authenticated JSON request to the Toqan Agent API (chave da Lyra por padrão)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"{TOQAN_BASE_URL}/{method}",
        data=body,
        headers={"X-Api-Key": api_key or _require_toqan_key(), "Content-Type": "application/json"},
        method=http_method or ("POST" if method in {"create_conversation", "continue_conversation"} else "GET"),
    )
    raw = ""
    for attempt in range(len(TOQAN_RETRY_WAITS) + 1):
        if api_key is None:  # o balde é da chave da Lyra (checagem de outros agentes usa a chave deles)
            _toqan_take_token()
        try:
            with urllib.request.urlopen(req, timeout=TOQAN_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            # 409 (conflito), 429 (limite de pedidos) e 5xx: espera e tenta de novo
            if exc.code in TOQAN_RETRY_CODES and attempt < len(TOQAN_RETRY_WAITS):
                wait = TOQAN_RETRY_WAITS[attempt]
                try:
                    wait = max(wait, min(120, int(float(exc.headers.get("Retry-After") or 0))))
                except (TypeError, ValueError, AttributeError):
                    pass
                if exc.code == 429:
                    with _TOQAN_BUCKET_LOCK:  # limite estourado: esvazia o balde para todo mundo desacelerar
                        _TOQAN_BUCKET["tokens"] = min(_TOQAN_BUCKET["tokens"], 0.0)
                logger.warning("Toqan HTTP %s for %s; nova tentativa em %ss", exc.code, method, wait)
                time.sleep(wait)
                continue
            logger.error("Toqan API returned HTTP %s for %s", exc.code, method)
            raise ToqanAPIError(f"Toqan HTTP {exc.code} ({method})") from exc
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


def create_conversation(user_message: str, api_key: str | None = None) -> tuple[str, str]:
    data = _toqan_request("create_conversation", {"user_message": user_message}, api_key)
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
    api_key: str | None = None,
    max_attempts: int = MAX_POLL_ATTEMPTS,
) -> str:
    """Poll Toqan until the answer is finished or the poll limit is reached."""
    payload = {"conversation_id": conversation_id, "request_id": request_id}
    for attempt in range(max_attempts):
        data = _toqan_request("get_answer", payload, api_key)
        if data.get("status") == "finished":
            answer = data.get("answer", "")
            if not isinstance(answer, str):
                raise ToqanAPIError("Toqan returned a non-text answer")
            return _clean_answer(answer)

        progress_message = {
            18: "Ainda buscando os números, já te respondo... ⏳",
            42: "Ainda consultando a base, quase lá...",
            72: "Está demorando mais que o normal, mas sigo consultando...",
            108: "Ainda consultando (já são 18 min). Se não vier em seguida, me pede de novo.",
        }.get(attempt)
        if progress_message and progress_callback:
            try:
                progress_callback(progress_message)
            except Exception:
                logger.warning("Could not send Toqan progress message", exc_info=True)

        if attempt < max_attempts - 1:
            time.sleep(_poll_wait(attempt))
    raise ToqanAPIError("Toqan answer polling timed out")


def _poll_wait(attempt: int) -> float:
    """Conversa: confere rápido no começo (resposta curta chega em segundos), depois a cada 10s.
    Fundo: a cada 15s, para gastar menos pedidos."""
    if _toqan_interactive():
        return (2, 3, 3, 4, 5)[attempt] if attempt < 5 else POLL_INTERVAL_SECONDS
    return BG_POLL_SECONDS


BG_POLL_SECONDS = float(os.getenv("BG_POLL_SECONDS", "15"))


TOQAN_UPLOAD_URL = os.getenv("TOQAN_UPLOAD_URL", f"{TOQAN_BASE_URL}/upload_file")


def toqan_upload_file(content: bytes, filename: str, mimetype: str = "application/octet-stream") -> str:
    """Sobe um arquivo (ex.: print do Slack) para o Toqan e devolve o file_id."""
    boundary = f"----lyra{int(time.time() * 1000)}"
    safe_name = re.sub(r"[^\w.\-]", "_", filename or "arquivo")
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe_name}\"\r\n"
            f"Content-Type: {mimetype}\r\n\r\n").encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(TOQAN_UPLOAD_URL, data=body, method="PUT", headers={
        "X-Api-Key": _require_toqan_key(), "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=TOQAN_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raise ToqanAPIError(f"Toqan upload HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ToqanAPIError(f"Toqan upload failed: {exc}") from exc
    file_id = data.get("file_id") or data.get("id") if isinstance(data, dict) else None
    if not file_id:
        raise ToqanAPIError("Toqan upload did not return file_id")
    return str(file_id)


def ask_toqan_with_files(prompt: str, file_ids: list[str], max_attempts: int = MAX_POLL_ATTEMPTS) -> str:
    with _ToqanSlot():
        return _ask_toqan_with_files(prompt, file_ids, max_attempts)


def _ask_toqan_with_files(prompt: str, file_ids: list[str], max_attempts: int = MAX_POLL_ATTEMPTS) -> str:
    """Pergunta com arquivos anexados (private_user_files). Se a criação com arquivo não for aceita,
    abre a conversa e manda o pedido com os arquivos no continue_conversation."""
    files = [{"id": fid} for fid in file_ids]
    data: dict[str, Any] = {}
    try:
        data = _toqan_request("create_conversation", {"user_message": prompt, "private_user_files": files})
    except ToqanAPIError as exc:
        if re.search(r"HTTP (429|5\d\d)", str(exc)):
            raise  # Toqan ocupado/limite: abrir outra conversa só piora
        logger.info("create_conversation with files not accepted; trying continue_conversation")
    conversation_id, request_id = data.get("conversation_id"), data.get("request_id")
    if conversation_id and request_id:
        return get_answer(str(conversation_id), str(request_id), max_attempts=max_attempts)
    conversation_id, request_id = create_conversation("Vou te mandar imagens para ler. Responda só: OK.")
    get_answer(conversation_id, request_id, max_attempts=30)
    data = _toqan_request("continue_conversation", {"conversation_id": conversation_id, "user_message": prompt,
                                                    "private_user_files": files})
    request_id = data.get("request_id")
    if not request_id:
        raise ToqanAPIError("continue_conversation did not return request_id")
    return get_answer(conversation_id, str(request_id), max_attempts=max_attempts)


def _clean_answer(answer: str) -> str:
    return _THINK_RE.sub("", answer).strip()


def ask_toqan(prompt: str, progress_callback: Callable[[str], Any] | None = None,
              max_attempts: int = MAX_POLL_ATTEMPTS) -> str:
    with _ToqanSlot():
        conversation_id, request_id = create_conversation(prompt)
        return get_answer(conversation_id, request_id, progress_callback=progress_callback, max_attempts=max_attempts)


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
    add_group("Span por supervisor (pessoas por supervisor)", "supervisor", limit=80)
    add_group("Pessoas por coordenador", "coordenador", limit=40)
    sup_idx = _mop_column_index(header_index, "supervisor")
    coord_idx = _mop_column_index(header_index, "coordenador")
    sup_counts = _mop_counts(data_rows, sup_idx)
    if sup_counts:
        lines.extend(["", f"Span médio: {len(data_rows) / len(sup_counts):.1f} pessoas por supervisor ({len(sup_counts)} supervisores)"])
    if sup_idx is not None and coord_idx is not None:
        sups_by_coord: dict[str, set[str]] = {}
        for row in data_rows:
            coord = str(row[coord_idx] if coord_idx < len(row) else "").strip()
            sup = str(row[sup_idx] if sup_idx < len(row) else "").strip()
            if coord and sup:
                sups_by_coord.setdefault(coord, set()).add(sup.casefold())
        if sups_by_coord:
            lines.extend(["", "Span por coordenador (supervisores por coordenador):"])
            for coord, sups in sorted(sups_by_coord.items(), key=lambda item: (-len(item[1]), item[0])):
                lines.append(f"- {coord}: {len(sups)}")
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


def _mop_situation(eps: str | None, values: list[list[str]] | None = None) -> str:
    """Situação do MOP em linguagem de negócio, sempre preenchida."""
    who = f"da {eps}" if eps else "da operação"
    if values is None:
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


_LOOKUP_STOPWORDS = {
    "mop", "quem", "qual", "quais", "quantas", "quantos", "pessoas", "pessoa", "supervisor", "supervisora",
    "coordenador", "coordenadora", "celula", "equipe", "time", "esta", "estao", "onde", "como", "sobre",
    "tem", "temos", "para", "pela", "pelo", "dele", "dela", "deles", "delas", "esse", "essa", "isso",
    "lyra", "analista", "analistas", "operador", "operadores", "lista", "manda", "mandar", "favor",
    "turno", "entrada", "saida", "status", "ativo", "ativos", "ferias", "licenca", "maior", "menor",
    "span", "spam", "gestao", "gestor", "hoje", "agora", "todos", "todas", "aqui", "voces", "nosso", "nossa",
    "trabalha", "trabalham", "horario", "formato", "remoto", "presencial", "oraculo", "versao", "variante",
}
MOP_LOOKUP_LIMIT = 40


def _mop_lookup_rows(question: str, values: list[list[str]], eps: str | None) -> list[str]:
    """Linhas do MOP que batem com nomes/e-mails/supervisores citados na pergunta (só da EPS do canal)."""
    if not values or len(values) < 2:
        return []
    header = values[0]
    tokens = [t for t in re.findall(r"[a-z0-9.]+", _norm_text(question)) if len(t) >= 4 and t not in _LOOKUP_STOPWORDS]
    if not tokens:
        return []
    cols = {name: _find_col(header, name) for name in (
        "Nome", "Email", "Célula", "Supervisor", "Coordenador", "Entrada", "Saída", "Status",
        "Versão do Oráculo", "Formato de Trabalho", "EPS", "Pilar")}
    eps_col, email_col = cols["EPS"], cols["Email"]

    def cell(row: list[str], name: str) -> str:
        idx = cols[name]
        return str(row[idx]).strip() if idx is not None and idx < len(row) else ""

    scored: list[tuple[int, list[str]]] = []
    for row in values[1:]:
        if not any(str(c).strip() for c in row):
            continue
        if eps and not _eps_matches(_row_eps(row, eps_col, email_col), eps):
            continue
        blob = _norm_text(" ".join(cell(row, n) for n in ("Nome", "Email", "Supervisor", "Coordenador", "Célula")))
        score = sum(1 for t in set(tokens) if t in blob)
        if score:
            scored.append((score, row))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    rows = [row for score, row in scored if score == best][:MOP_LOOKUP_LIMIT]
    lines = []
    for row in rows:
        user = cell(row, "Email").split("@")[0]
        lines.append(
            f"- {cell(row, 'Nome')} ({user}) · célula {cell(row, 'Célula') or '—'} · supervisor {cell(row, 'Supervisor') or '—'} "
            f"· coordenador {cell(row, 'Coordenador') or '—'} · {cell(row, 'Entrada') or '—'}–{cell(row, 'Saída') or '—'} "
            f"· {cell(row, 'Status') or '—'} · {cell(row, 'Versão do Oráculo') or '—'} · {cell(row, 'Formato de Trabalho') or '—'}"
        )
    total = len([1 for score, _ in scored if score == best])
    if total > len(rows):
        lines.append(f"- (+{total - len(rows)} pessoas)")
    return lines


_EXPORT_RE = re.compile(
    r"\b(manda|mande|mandar|envia|envie|enviar|extrai|extraia|extrair|exporta|exporte|exportar|baixa|baixar|"
    r"gera|gere|gerar|passa|passe|compartilha|compartilhe)\b.*\bmop\b|\bmop\b.*\b(excel|xlsx|planilha|arquivo)\b",
    re.IGNORECASE,
)


def _is_mop_export_request(question: str) -> bool:
    return bool(_EXPORT_RE.search(_norm_text(question)))


def _build_mop_xlsx(values: list[list[str]], eps: str | None) -> tuple[bytes, int]:
    """Excel do MOP (só a EPS do canal, ou tudo na visão interna). Devolve (bytes, pessoas)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    header = values[0]
    eps_col, email_col = _find_col(header, "EPS"), _find_col(header, "Email")
    rows = [
        r for r in values[1:]
        if any(str(c).strip() for c in r) and (not eps or _eps_matches(_row_eps(r, eps_col, email_col), eps))
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = f"MOP {eps}" if eps else "MOP Consolidado"
    ws.append(list(header))
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="EA1D2C")
    for r in rows:
        ws.append(list(r) + [""] * (len(header) - len(r)))
    for idx, name in enumerate(header, start=1):
        width = max([len(str(name))] + [len(str(r[idx - 1])) for r in rows[:300] if idx - 1 < len(r)])
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = min(max(width + 2, 10), 45)
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), len(rows)


def _send_mop_export(event: dict[str, Any], client: Any, eps: str | None) -> str | None:
    """Gera e envia o Excel do MOP na thread. Devolve texto de resposta se não deu para enviar."""
    values = _read_mop_values()
    if values is None:
        return "Não consegui puxar o MOP agora. Tenta de novo em alguns minutos?"
    if len(values) < 2:
        return "O MOP ainda está vazio por aqui."
    content, people = _build_mop_xlsx(values, eps)
    if people == 0:
        return f"Ainda não tenho ninguém da {eps} no MOP." if eps else "O MOP ainda está vazio por aqui."
    who = f" da {eps}" if eps else ""
    stamp = _now_brazil().strftime("%d-%m-%Y")
    uploader = client or slack_app.client
    uploader.files_upload_v2(
        channel=event.get("channel"),
        thread_ts=_reply_ts(event),
        content=content,
        filename=f"MOP{('_' + eps) if eps else '_Consolidado'}_{stamp}.xlsx",
        title=f"MOP{who} — {stamp}",
        initial_comment=f"Segue o MOP{who} atualizado 📋",
    )
    return None


def _inject_mop_context(question: str, eps: str | None = None) -> str:
    if not question:
        return question
    values = _read_mop_values() if _question_has_mop_intent(question) else None
    people = _mop_lookup_rows(question, values or [], eps) if values else []
    if not _question_has_mop_intent(question) and not people:
        return question
    extra = ""
    if people:
        extra = "\nPessoas do MOP citadas na pergunta (nome · usuário · célula · supervisor · coordenador · turno · status · Oráculo · formato):\n" + "\n".join(people)
    return f"{INTERNAL_NOTE}\n{_mop_situation(eps, values)}{extra}\n\nMensagem de quem perguntou: {question}"


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

    lines = ["MOP atualizado na planilha ✅"]
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

    lines = ["MOP atualizado na planilha ✅"]
    # Só fala mais se houver algo que precise de atenção
    if ignored:
        lines.append(f"⚠️ {ignored} linha(s) de outra EPS foram ignoradas.")
    if missing:
        lines.append(f"⚠️ Colunas não encontradas: {', '.join(missing)}.")
    if before and after < before * 0.5:
        lines.append("⚠️ O número de pessoas caiu mais de 50% — confira o arquivo. A versão anterior ficou guardada.")
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


_REPORT_KPIS_RE = re.compile(r"(CSAT D-1 [\d.,]+%(?: \(meta [\d.,]+%\))?(?: · TMA [\d.]+ s(?: \(plan [\d.]+ s\))?)?)")
_REPORT_PROBLEM_RE = re.compile(r"Problema do D-1(?: \(CSAT\))?\s*:?\**\s*:?\s*([^\n]+)", re.IGNORECASE)


def _report_problem(report_text: str) -> str:
    """Resumo do que foi cobrado, tirado do bloco do report: indicadores do D-1 e o problema do D-1."""
    text = str(report_text or "").replace("*", "")
    parts = []
    kpis = _REPORT_KPIS_RE.search(text)
    if kpis:
        parts.append(kpis.group(1))
    problem = _REPORT_PROBLEM_RE.search(text)
    if problem:
        parts.append(problem.group(1).strip())
    return " · ".join(parts)


def _commitment_row(
    fila: str, acao: str, responsavel: str, prazo: str, pre: str, report_ts: str, today: datetime | date,
    tenant_key: str = CONSOLIDATED, problema_report: str = "",
) -> list[str]:
    data_fim, duracao = _deadline_fields(prazo, today)
    if problema_report:
        problema = f"{fila} · {problema_report}"
    else:
        problema = f"{fila} · CSAT D-1 {pre}" if pre else f"{fila} · ofensor do report"
    return [
        problema, acao, _format_date(today), data_fim, duracao,
        pre or "a definir", "", "a definir", fila, responsavel or "Liderança", report_ts, tenant_key,
    ]


def _sem_resposta_row(
    report_ts: str, today: datetime | date, tenant_key: str = CONSOLIDATED,
    fila: str = "", pre: str = "", problema_report: str = "",
) -> list[str]:
    problema = "Report sem resposta da liderança"
    if fila:
        problema = f"{fila} · sem resposta ao report" + (f" · {problema_report}" if problema_report else "")
    return [
        problema, SEM_RESPOSTA, _format_date(today), "—", "—",
        pre or "a definir", "", "a definir", fila or FILA_GERAL, "Liderança", report_ts, tenant_key,
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


def _parse_extraction(answer: str) -> dict[str, Any] | None:
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
        return {"novos": [i for i in parsed if isinstance(i, dict)], "atualizacoes": [], "feedback": ""}
    if isinstance(parsed, dict):
        return {
            "novos": [i for i in (parsed.get("novos") or []) if isinstance(i, dict)],
            "atualizacoes": [i for i in (parsed.get("atualizacoes") or []) if isinstance(i, dict)],
            "feedback": str(parsed.get("feedback") or "").strip(),
        }
    return None


def _extract_commitments_via_toqan(
    messages: list[str],
    filas: list[str],
    existing: list[tuple[int, dict[str, str]]],
    today: datetime | date,
    context: str = "",
) -> dict[str, Any]:
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
        + (f"Report desta fila (o que foi cobrado):\n{context[:1500]}\n\n" if context else "")
        +
        "Mensagens novas da liderança:\n" + "\n---\n".join(messages) + "\n\n"
        "Formato de saída:\n"
        '{"novos":[{"fila":"...","acao":"...","responsavel":"...","prazo":"dd/mm/aaaa ou a definir"}],'
        '"atualizacoes":[{"linha":12,"acao":"...","responsavel":"...","prazo":"dd/mm/aaaa"}],'
        '"feedback":"..."}\n\n'
        "Regras:\n"
        "- novos: planos de ação novos. fila = exatamente um nome da lista de filas; se não der pra saber, use \"Geral\".\n"
        "- atualizacoes: quando a mensagem completa ou corrige um compromisso já registrado (ex.: informa o prazo "
        "que faltava). Use o número da linha e inclua só os campos que mudaram.\n"
        "- prazo: converta para dd/mm/aaaa a partir de hoje (\"sexta\" = próxima sexta; \"semana que vem\" = hoje + 7 dias; "
        "\"fim do mês\" = último dia do mês). Sem prazo → \"a definir\".\n"
        "- responsavel: quem executa; se não mencionado, \"Liderança\".\n"
        "- Status de compromisso (\"concluído\", \"em andamento\") não é compromisso novo.\n"
        '- Não invente. Sem plano nem atualização → {"novos":[],"atualizacoes":[],"feedback":"..."}\n'
        "- feedback: sua avaliação de analista de CX sobre o que a liderança respondeu, para postar na thread "
        "(1 a 3 frases, tom de colega exigente e respeitoso, formatação Slack com *um asterisco*). Compare com o report: "
        "a ação ataca o problema cobrado (motivo de maior impacto, dispersão/Q4)? É concreta (o quê, para quem, quando)? "
        "Tem responsável, prazo e como medir o efeito? Se o plano é bom, reconheça em uma frase e diga o que vai acompanhar. "
        "Se é genérico (\"treinamento\", \"acompanhar\", \"alinhar\") ou não ataca a causa, aponte o que falta e faça UMA pergunta objetiva. "
        "Se a mensagem não é plano nem status (ex.: só \"ok\", \"vamos ver\"), peça o plano no formato ação · responsável · prazo. "
        "Nunca cite nome de operador. Vazio só se a mensagem não tiver relação com o report."
    )
    answer = ask_toqan(prompt)
    parsed = _parse_extraction(answer)
    if parsed is None:
        logger.warning("Commitment extraction was not JSON; keeping raw message as commitment")
        raw = " / ".join(m.strip() for m in messages if m.strip())[:200]
        return {"novos": [{"fila": FILA_GERAL, "acao": raw, "responsavel": "Liderança", "prazo": "a definir"}],
                "atualizacoes": [], "feedback": ""}
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


_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock(report_ts: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(report_ts, threading.Lock())


def _read_report_thread(
    channel_id: str, report_ts: str, phase: str, today: datetime | date | None = None,
    tenant_key: str = CONSOLIDATED, fila: str = "", register_no_reply: bool = True,
) -> dict[str, int]:
    """Lê a thread (uma leitura por vez por thread: agendada e ao vivo não se atropelam)."""
    with _thread_lock(report_ts):
        return _read_report_thread_locked(channel_id, report_ts, phase, today, tenant_key, fila, register_no_reply)


def _read_report_thread_locked(
    channel_id: str, report_ts: str, phase: str, today: datetime | date | None = None,
    tenant_key: str = CONSOLIDATED, fila: str = "", register_no_reply: bool = True,
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
    if fila:  # bloco de uma fila só: a fila é conhecida, o CSAT vem da linha Resultado
        values = _block_csat(fila, report_text)
        csat = {fila: values} if values else {}
        filas = [fila]
    else:
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
        if phase == "first" and register_no_reply and not records and not thread_rows:
            pre_sr = _fmt_pct(csat[fila]["d1"]) if fila and fila in csat else ""
            worksheet.append_row(_sem_resposta_row(report_ts, base, tenant_key, fila=fila, pre=pre_sr,
                                                   problema_report=_report_problem(report_text)),
                                 value_input_option="RAW")
        return {"novos": 0, "atualizados": 0}

    extraction = _extract_commitments_via_toqan([text for _, text in new_records], filas, thread_rows, base,
                                                context=report_text)

    # novos
    new_rows: list[list[str]] = []
    missing_deadline: list[str] = []
    for item in extraction["novos"]:
        action = str(item.get("acao") or "").strip()
        if not action:
            continue
        item_fila = fila or _match_fila(str(item.get("fila") or ""), filas) or FILA_GERAL
        pre = _fmt_pct(csat[item_fila]["d1"]) if item_fila in csat else ""
        prazo = str(item.get("prazo") or "a definir").strip() or "a definir"
        row = _commitment_row(
            item_fila, action, str(item.get("responsavel") or "").strip(), prazo, pre, report_ts, base, tenant_key,
            problema_report=_report_problem(report_text) if fila else "",
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

    feedback = str(extraction.get("feedback") or "").strip()
    answered = {t for t in STATE.get(f"answered:{report_ts}").split(",") if t}
    if feedback and all(t in answered for t, _ in new_records):
        feedback = ""  # a Lyra já respondeu essas mensagens na conversa
    if new_rows or updated or feedback:
        chunks = []
        if feedback:
            chunks.append(feedback)
        if new_rows or updated:
            parts = []
            if new_rows:
                parts.append(f"{len(new_rows)} novo(s) compromisso(s)")
            if updated:
                parts.append(f"{updated} atualizado(s)")
            chunks.append(f"Registrado: {' e '.join(parts)} ✅")
        text = "\n\n".join(chunks)
        if missing_deadline:
            text += "\nQual o prazo para:\n" + "\n".join(f"• {a[:120]}" for a in missing_deadline)
        slack_app.client.chat_postMessage(channel=channel_id, text=text, thread_ts=report_ts)
    return {"novos": len(new_rows), "atualizados": updated}


# ---------------------------------------------------------------------------
# Owners das filas, escalation e Excel de operadores
# ---------------------------------------------------------------------------
_MENTION_ID_RE = re.compile(r"<@(U[A-Z0-9]+)>")
_BULLET_FILA_RE = re.compile(r"^\s*[•\-]\s*\*(?P<fila>[^*\n]+?)\s*:?\s*\*")


_SLACK_USERS_CACHE: dict[str, Any] = {"at": None, "by_name": {}}
_UNRESOLVED_OWNERS_ALERTED: set[str] = set()


def _slack_users_by_name() -> dict[str, list[str]]:
    """{nome normalizado: [IDs]} a partir do Slack (real_name e display_name). Cache de 6h."""
    at = _SLACK_USERS_CACHE["at"]
    if at and _now_brazil() - at < timedelta(hours=6):
        return _SLACK_USERS_CACHE["by_name"]
    by_name: dict[str, list[str]] = {}
    try:
        cursor = None
        for _ in range(50):
            kwargs: dict[str, Any] = {"limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            resp = slack_app.client.users_list(**kwargs)
            for u in _resp_get(resp, "members", []) or []:
                if u.get("deleted") or u.get("is_bot"):
                    continue
                prof = u.get("profile") or {}
                for name in {u.get("real_name"), prof.get("real_name"), prof.get("display_name")}:
                    if name:
                        by_name.setdefault(_norm_text(name), [])
                        if u["id"] not in by_name[_norm_text(name)]:
                            by_name[_norm_text(name)].append(u["id"])
            cursor = (_resp_get(resp, "response_metadata", {}) or {}).get("next_cursor")
            if not cursor:
                break
    except Exception:
        logger.warning("Could not list Slack users (falta o escopo users:read?)", exc_info=True)
        return _SLACK_USERS_CACHE["by_name"]
    _SLACK_USERS_CACHE.update(at=_now_brazil(), by_name=by_name)
    return by_name


def _owner_mention(owner: str) -> str:
    """'U123' → <@U123>; '@Nome Sobrenome' → <@ID> achado no Slack (ou o nome em texto, com alerta)."""
    owner = owner.strip()
    if re.fullmatch(r"[UW][A-Z0-9]{6,}", owner):
        return f"<@{owner}>"
    name = owner.lstrip("@").strip()
    by_name = _slack_users_by_name()
    ids = by_name.get(_norm_text(name), [])
    if not ids:
        # nome no Slack costuma ser mais curto (ex.: "Carlos Porto"): aceita quando os nomes de um
        # estão todos no outro, com o mesmo primeiro nome e pelo menos 2 nomes em comum
        stop = {"da", "de", "do", "das", "dos", "e"}
        wanted = [w for w in _norm_text(name).split() if w not in stop]
        found: set[str] = set()
        for slack_name, uids in by_name.items():
            tokens = [w for w in slack_name.split() if w not in stop]
            if len(tokens) < 2 or not wanted or tokens[0] != wanted[0]:
                continue
            common = set(tokens) & set(wanted)
            if len(common) >= 2 and (set(tokens) <= set(wanted) or set(wanted) <= set(tokens)):
                found.update(uids)
        ids = sorted(found)
    if len(ids) == 1:
        return f"<@{ids[0]}>"
    if name not in _UNRESOLVED_OWNERS_ALERTED:
        _UNRESOLVED_OWNERS_ALERTED.add(name)
        motivo = "mais de uma pessoa com esse nome" if ids else "não achei no Slack"
        _alert(f"Owner '{name}': {motivo}. Coloque o ID do Slack em FILA_OWNERS. Por enquanto vai o nome em texto.")
    return f"@{name}"


def _owners_for(fila_label: str) -> list[str]:
    fila = _match_fila(fila_label, list(FILA_OWNERS))
    return FILA_OWNERS.get(fila, []) if fila else []


def _tag_owners(main: str) -> str:
    """Marca os owners nas linhas da seção Cobranças (cada linha começa com • *Fila:*)."""
    lines = main.splitlines()
    in_cobrancas = False
    for i, line in enumerate(lines):
        low = _norm_text(line)
        if "cobrancas" in low and line.strip().startswith("*"):
            in_cobrancas = True
            continue
        if in_cobrancas and line.strip().startswith("*") and not line.strip().startswith(("*•", "•")):
            in_cobrancas = False  # começou outra seção
        if not in_cobrancas:
            continue
        match = _BULLET_FILA_RE.match(line)
        if not match:
            continue
        mentions = [m for m in (_owner_mention(o) for o in _owners_for(match.group("fila"))) if m and m not in line]
        if mentions:
            lines[i] = line.rstrip() + " " + " ".join(mentions)
    return "\n".join(lines)


def _escalation_check(tenant: "Tenant", report_ts: str, today: date) -> str:
    """5h depois do report: cobra na thread quem foi marcado e não respondeu."""
    messages = _fetch_thread(tenant.channel, report_ts)
    parent = next((m for m in messages if m.get("ts") == report_ts), {})
    tagged = list(dict.fromkeys(_MENTION_ID_RE.findall(str(parent.get("text") or ""))))
    humans = [m for m in messages if m.get("ts") != report_ts and not m.get("bot_id") and m.get("subtype") != "bot_message"]
    responders = {str(m.get("user") or "") for m in humans}
    if tagged:
        pending = [uid for uid in tagged if uid not in responders]
        if not pending:
            return "todos responderam"
        who = " ".join(f"<@{uid}>" for uid in pending)
        text = f"{who} algum retorno sobre o plano? Preciso de *ação · responsável · prazo* aqui na thread pra gente acompanhar. 🙏"
    else:
        if humans:
            return "houve resposta"
        text = "Lideranças, algum retorno sobre o report? Preciso do plano aqui na thread no formato *ação · responsável · prazo*. 🙏"
    slack_app.client.chat_postMessage(channel=tenant.channel, text=text, thread_ts=report_ts)
    return "cobrado"


_OPERATORS_EXCEL_RE = re.compile(
    r"\b(excel|planilha|xlsx|arquivo|lista|base|relacao)\b.*\b(operador|operadores|analista|analistas|quadrante|quadrantes|q1|q2|q3|q4|pessoas)\b"
    r"|\b(operador|operadores|analista|analistas|quadrante|quadrantes|q4)\b.*\b(excel|planilha|xlsx|arquivo)\b"
)
OPERATORS_CSV_HEADER = ["email", "fila", "avaliacoes", "promotores", "csat", "meta", "atingimento", "quadrante"]


# Resultado individual pedido em texto ("resultado por operador de ontem", "CSAT dos analistas"): vai em Excel,
# porque nome/e-mail de operador não aparece no Slack.
_OPERATORS_RESULT_RE = re.compile(
    r"\bpor (operador|analista|atendente)\b|\bresultado (individual|dos operadores|dos analistas|dos atendentes)\b"
    r"|\b(quem|quais|lista|listar|resultado|traz|traga|mostra|manda)\b.*\b(ofensor|ofensores)\b"
    r"|\b(ofensor|ofensores)\b (de|do|da|em) (ontem|hoje|csat|d 1|mes|semana)\b"
    r"|^(os |as )?(ofensor|ofensores|detratores)\b"
    r"|\b(piores|melhores) (operadores|analistas|atendentes|agentes)\b"
    r"|\btop \d{1,2} (operadores|analistas|atendentes|agentes)\b"
    r"|\b(operadores|analistas|atendentes|agentes) com (mais|maior|menos|menor) (impacto|csat|atingimento)\b"
    r"|\b(csat|resultado|quadrante|ranking)\b.*\b(dos|de cada|por) (operador|operadores|analista|analistas|atendente|atendentes)\b"
)


def _is_operators_excel_request(question: str) -> bool:
    text = _norm_text(question)
    if re.search(r"\bmop\b", text):  # pedido de MOP tem prioridade
        return False
    return bool(_OPERATORS_EXCEL_RE.search(text) or _OPERATORS_RESULT_RE.search(text))


def _period_spec(question: str) -> dict[str, Any]:
    """Período pedido com datas explícitas e o período de comparação (regras do Cockpit: D-1 x D-8, W-1 x W-2,
    mês x mesmos dias do mês anterior)."""
    text = _norm_text(question)
    d1 = _as_date(_today_brazil()) - timedelta(days=1)
    f = lambda d: d.strftime("%d/%m/%Y")
    if re.search(r"\b(ontem|d 1|d1)\b", text):
        prev = d1 - timedelta(days=7)
        return {"label": f"de ontem ({d1.strftime('%d/%m')})", "cur": f"D-1: {f(d1)}", "prev": f"D-8: {f(prev)}",
                "prev_label": f"D-8 ({prev.strftime('%d/%m')})", "min": 3, "short": f"D-1 {d1.strftime('%d/%m')}"}
    if re.search(r"\b(mes|mensal)\b", text):
        start = d1.replace(day=1)
        pm_end = start - timedelta(days=1)
        try:
            p_end = pm_end.replace(day=d1.day)
        except ValueError:
            p_end = pm_end
        return {"label": "do mês", "cur": f"mês até o D-1: {f(start)} a {f(d1)}",
                "prev": f"mesmos dias do mês anterior: {f(pm_end.replace(day=1))} a {f(p_end)}",
                "prev_label": "mesmos dias do mês anterior", "min": 5, "short": (f"mês 01 a {d1.strftime('%d/%m')}" if d1.day > 1 else f"mês ({d1.strftime('%d/%m')})")}
    if not re.search(r"\b(semana|semanal|w 1|7 dias)\b", text):  # padrão do time: visão mês
        start = d1.replace(day=1)
        pm_end = start - timedelta(days=1)
        try:
            p_end = pm_end.replace(day=d1.day)
        except ValueError:
            p_end = pm_end
        return {"label": "do mês", "cur": f"mês até o D-1: {f(start)} a {f(d1)}",
                "prev": f"mesmos dias do mês anterior: {f(pm_end.replace(day=1))} a {f(p_end)}",
                "prev_label": "mesmos dias do mês anterior", "min": 5, "short": (f"mês 01 a {d1.strftime('%d/%m')}" if d1.day > 1 else f"mês ({d1.strftime('%d/%m')})")}
    start = d1 - timedelta(days=6)
    return {"label": "da semana", "cur": f"últimos 7 dias: {f(start)} a {f(d1)}",
            "prev": f"7 dias anteriores: {f(start - timedelta(days=7))} a {f(start - timedelta(days=1))}",
            "prev_label": "semana anterior", "min": 5, "short": f"semana {_short_range(start, d1)}"}


def _short_range(a: date, b: date) -> str:
    """23–29/10 (mesmo mês) ou 28/09–04/10."""
    return f"{a.day:02d}–{b.strftime('%d/%m')}" if a.month == b.month else f"{a.strftime('%d/%m')}–{b.strftime('%d/%m')}"


def _operators_period(question: str) -> tuple[str, str]:
    """(instrução de período para o agente, rótulo para o arquivo)."""
    spec = _period_spec(question)
    return f"{spec['cur']}. Só operadores com {spec['min']}+ avaliações.", spec["label"]


def _eps_in_text(question: str) -> str | None:
    words = set(re.findall(r"[a-z0-9]+", _norm_text(question)))
    return next((e for e in EPS_CELULAS if _norm_text(e) in words), None)


def _eps_of_question(question: str) -> str | None:
    """EPS citada pelo nome ou pela fila (CX Suporte -> AeC). Visão completa sem EPS na pergunta: recorta mesmo assim,
    para a consulta não trazer a base inteira do iFood."""
    eps = _eps_in_text(question)
    if eps:
        return eps
    fila = _fila_in_question(question, None)
    return next((e for e, cel in EPS_CELULAS.items() if fila in cel), None) if fila else None


def _operators_prompt(eps: str | None, period: str = "semana corrente (D-7 a D-1). Só operadores com 5+ avaliações.") -> str:
    return (
        f"{_scope_instruction(eps)}\n\n"
        "TAREFA INTERNA DO APP — base de operadores para Excel. Não é mensagem para o Slack.\n"
        "Se você usa subagentes, peça ao subagente de indicadores com "
        f"'EPS: {eps or 'iFood'}', 'Pedido: base de operadores (CSV)' e 'Período: {period}'\n"
        f"Período: {period} Só filas da lista oficial da EPS.\n"
        "Quadrante pelo atingimento = CSAT do operador ÷ meta da fila: Q1 ≥ 100% · Q2 95–99% · Q3 90–94% · Q4 < 90%.\n"
        "Responda APENAS um CSV separado por ';', escrito no corpo da resposta (NUNCA salve em arquivo nem devolva nome "
        "de arquivo ou link), sem markdown, com este cabeçalho exato:\n"
        "email;fila;avaliacoes;promotores;csat;meta;atingimento;quadrante\n"
        "Números com ponto decimal (csat, meta e atingimento em %, ex.: 72.5). Uma linha por operador.\n"
        "Última linha: TOTAL;<quantidade de operadores>\n"
        "Se a consulta falhar: responda só 'ERRO: <motivo>'."
    )


def _parse_operators_csv(answer: str) -> tuple[list[list[str]], int | None]:
    import csv as _csv
    text = _strip_json_code_blocks(answer)
    rows: list[list[str]] = []
    total: int | None = None
    header_seen = False
    for row in _csv.reader(io.StringIO(text), delimiter=";"):
        cells = [c.strip() for c in row]
        if not cells or not any(cells):
            continue
        if not header_seen:
            if [c.lower() for c in cells[:len(OPERATORS_CSV_HEADER)]] == OPERATORS_CSV_HEADER:
                header_seen = True
            continue
        if cells[0].upper() == "TOTAL":
            total = _to_int(cells[1] if len(cells) > 1 else "")
            continue
        if len(cells) >= len(OPERATORS_CSV_HEADER) and "@" in cells[0]:
            rows.append(cells[:len(OPERATORS_CSV_HEADER)])
    return rows, total


# --- Gráficos sob pedido (PNG montado pelo app; a Lyra só traz os dados) -------------
_CHART_RE = re.compile(r"\b(grafico|graficos|chart|plota|plotar|plote|visualizacao|visual)\b")
CHART_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # ordem fixa (paleta validada para daltonismo)


def _is_chart_request(question: str) -> bool:
    text = _norm_text(question)
    return bool(_CHART_RE.search(text)) and not re.search(r"\b(o que|como funciona|consegue gerar)\b.*\?$", text)


def _chart_prompt(eps: str | None, question: str, context: str) -> str:
    return (
        f"{_scope_instruction(eps)}\n\n{context}"
        "TAREFA INTERNA DO APP — a pessoa pediu um gráfico. Busque os dados com o subagente certo (TMA sempre pelo SQL "
        "oficial da Lyra Indicadores) e devolva APENAS JSON válido:\n"
        '{"titulo": "TMA por célula — D-1 x mês (s)", "tipo": "barra", "unidade": "s", '
        '"categorias": ["CX Suporte", "Madrugada"], '
        '"series": [{"nome": "D-1", "valores": [526, 689]}, {"nome": "Mês", "valores": [724, 672]}], '
        '"referencia": {"nome": "meta", "valor": null}, "nota": "1 frase factual com o principal destaque"}\n'
        "Regras: tipo = \"barra\" (comparar categorias) ou \"linha\" (evolução no tempo, categorias = datas dd/mm em ordem). "
        "No máximo 4 séries e 20 categorias. unidade = \"%\", \"s\" ou \"\". Números com ponto decimal. "
        "referencia só quando houver UMA meta/plan comum a todas as categorias; senão null. Respeite o escopo da EPS. "
        "Se não der para consultar: só ERRO: <motivo>.\n\n"
        f"Pedido: {question}"
    )


def _build_chart_png(spec: dict[str, Any]) -> bytes | None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker

    cats = [str(c) for c in (spec.get("categorias") or [])][:20]
    series = [s_ for s_ in (spec.get("series") or []) if isinstance(s_, dict)][:4]
    if not cats or not series:
        return None
    unit = str(spec.get("unidade") or "")
    fmt = (lambda v: f"{v:.1f}%".replace(".", ",")) if unit == "%" else \
          (lambda v: f"{_fmt_int(v)} s") if unit == "s" else (lambda v: _bfmt(v, 1))
    vals = [[(_num(v) if _num(v) is not None else float("nan")) for v in (s_.get("valores") or [])][:len(cats)] for s_ in series]
    vals = [v + [float("nan")] * (len(cats) - len(v)) for v in vals]
    ink, muted, grid = "#2b2b29", "#6b6a64", "#e6e5e0"
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": grid, "axes.labelcolor": muted,
                         "xtick.color": muted, "ytick.color": muted, "text.color": ink})
    kind = str(spec.get("tipo") or "barra").lower()
    horizontal = kind != "linha"
    height = max(3.2, 0.42 * len(cats) * (1 + 0.35 * (len(series) - 1)) + 1.2) if horizontal else 4.2
    fig, ax = plt.subplots(figsize=(9, height), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if horizontal:
        n = len(series)
        bar_h = 0.8 / n
        order = list(range(len(cats)))[::-1]  # primeira categoria no topo
        for i, (s_, v) in enumerate(zip(series, vals)):
            ys = [o + (n - 1 - i) * bar_h - 0.4 + bar_h / 2 for o in order]
            ax.barh(ys, v, height=bar_h * 0.9, color=CHART_COLORS[i], label=str(s_.get("nome") or ""), zorder=2)
            for y, x in zip(ys, v):  # rótulo de dados em todas as barras
                if x == x:
                    ax.text(x, y, " " + fmt(x), va="center", ha="left", fontsize=7.5 if n > 1 else 8.5, color=ink)
        ax.set_yticks(order)
        ax.set_yticklabels(cats)
        ax.xaxis.grid(True, color=grid, linewidth=0.8, zorder=0)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ref = spec.get("referencia") or {}
        if isinstance(ref, dict) and _num(ref.get("valor")) is not None:
            ax.axvline(_num(ref["valor"]), color=muted, linestyle=(0, (4, 3)), linewidth=1, zorder=3)
            ax.text(_num(ref["valor"]), len(cats) - 0.45, f" {ref.get('nome') or 'meta'} {fmt(_num(ref['valor']))}",
                    fontsize=8, color=muted, va="bottom")
        right = max([x for v in vals for x in v if x == x] or [1])
        ax.set_xlim(0, right * 1.15)
    else:
        for i, (s_, v) in enumerate(zip(series, vals)):
            ax.plot(cats, v, color=CHART_COLORS[i], linewidth=2, marker="o", markersize=5,
                    label=str(s_.get("nome") or ""), zorder=3)
            for j, y in enumerate(v):  # rótulo de dados em todos os pontos: acima nos picos, abaixo nos vales
                if y != y:
                    continue
                neigh = [v[k] for k in (j - 1, j + 1) if 0 <= k < len(v) and v[k] == v[k]]
                below = bool(neigh) and y < sum(neigh) / len(neigh)
                if len(series) > 1:
                    below = i % 2 == 1
                ax.annotate(fmt(y), (j, y), textcoords="offset points", xytext=(0, -13 if below else 8), ha="center",
                            fontsize=7 if len(cats) > 12 else 8, color=ink,
                            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85))
        ax.yaxis.grid(True, color=grid, linewidth=0.8, zorder=0)
        ref = spec.get("referencia") or {}
        if isinstance(ref, dict) and _num(ref.get("valor")) is not None:
            ax.axhline(_num(ref["valor"]), color=muted, linestyle=(0, (4, 3)), linewidth=1)
            ax.annotate(f"{ref.get('nome') or 'meta'} {fmt(_num(ref['valor']))}", (1, _num(ref["valor"])),
                        xycoords=("axes fraction", "data"), xytext=(4, 0), textcoords="offset points",
                        fontsize=8, color=muted, va="center", ha="left")
        if len(cats) > 10:
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _bfmt(v, 1)))
    if len(series) > 1:
        ax.legend(frameon=False, loc="lower right" if horizontal else "best", fontsize=9)
    ax.set_title(str(spec.get("titulo") or ""), loc="left", fontsize=12, color=ink, pad=12)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _send_chart(event: dict[str, Any], client: Any, eps: str | None, question: str,
                send_progress: Callable[[str], Any] | None = None) -> str | None:
    answer = ask_toqan(_chart_prompt(eps, question, _thread_context(event)), progress_callback=send_progress)
    if _is_error_answer(answer):
        return "Não consegui puxar esses dados agora. Tenta de novo em alguns minutos?"
    spec = _block_data_from_json(answer) or {}
    png = _build_chart_png(spec)
    if not png:
        return "Não consegui montar o gráfico com esse pedido. Me diz o indicador, o período e o recorte (ex.: TMA por célula, D-1 x mês)."
    nota = str(spec.get("nota") or "").strip()
    title = str(spec.get("titulo") or "Gráfico")
    (client or slack_app.client).files_upload_v2(
        channel=event.get("channel"), thread_ts=_reply_ts(event),
        content=png, filename=re.sub(r"[^\w\-]+", "_", title)[:60] + ".png", title=title,
        initial_comment=(f"📊 {nota}" if nota else "📊 Segue o gráfico."),
    )
    return None

# --- Base caso a caso por indicador (CSAT, SLA de 1ª resposta, TMA) + abertura por operador --------------------------
# Ex.: "casos fora do SLA de 1ª resposta da Super", "base de CSAT da minha equipe com número do caso", "casos de TMA
# alto do time da Supervisora 3". Excel com a aba dos casos e a aba por operador; filtra por fila e/ou equipe (MOP).
_CASE_FIELDS_RE = re.compile(r"\b(numero do caso|numeros dos casos|n do caso|caso a caso|ticket a ticket|numero do ticket|"
                             r"comentario\w*|hora da avaliacao|data da avaliacao|nota atribuida|formulario do caso|"
                             r"avaliacao por avaliacao|lista de avaliacoes|abertura das avaliacoes|casos?|tickets?|"
                             r"base de (csat|sla|tma|avaliac\w*)|fora do sla|estour\w*)\b")
_CASE_IND_RE = re.compile(r"\b(csat|avaliac\w*|nota\w*|entrega\w*|detrator\w*|sla|primeira resposta|1a resposta|"
                          r"tma|tempo de atendimento|tempo de atribuicao)\b")
CASE_LIST_MAX = int(os.getenv("CASE_LIST_MAX", "400"))
SLA_LIMITE_S = {"super cliente": 120}  # 1ª resposta (regra da CAPA): 2 min na CX Super Cliente AeC/CSU; 5 min nas demais
SLA_LIMITE_PADRAO_S = 300


def _is_case_list_request(question: str) -> bool:
    t = _norm_text(question)
    if not (_CASE_FIELDS_RE.search(t) and _CASE_IND_RE.search(t)):
        return False
    # "casos" sozinho só vale com pedido de lista/base/número (evita "quantos casos..." e perguntas de causa)
    return bool(re.search(r"\b(numero|numeros|lista|base|abertura|planilha|excel|traz|traga|manda|mande|envia|envie|"
                          r"me passa|quais (os )?casos|caso a caso|comentario\w*|hora da avaliacao|nota atribuida)\b", t))


def _case_indicator(question: str) -> str:
    t = _norm_text(question)
    if re.search(r"\b(sla|primeira resposta|1a resposta|fora do sla)\b", t):
        return "sla"
    if re.search(r"\b(tma|tempo de atendimento|tempo de atribuicao)\b", t):
        return "tma"
    return "csat"


def _sla_limite_txt(fila: str | None) -> str:
    if fila:
        lim = next((v for k, v in SLA_LIMITE_S.items() if k in _norm_text(fila)), SLA_LIMITE_PADRAO_S)
        return f"{lim} s ({lim // 60} min)"
    return "120 s (2 min) na CX Super Cliente - AeC/CSU e 300 s (5 min) nas demais"


def _case_team(question: str, event: dict[str, Any], eps: str | None) -> tuple[str | None, list[str] | None, str]:
    """(nome do líder, e-mails da equipe, problema). Só quando a pergunta fala de equipe/time/supervisor."""
    if not _TEAM_RE.search(_norm_text(question)):
        return None, None, ""
    people = _mop_people(eps)
    if not people:
        return None, None, "Não consegui ler o MOP pra achar a equipe agora. Tenta de novo em alguns minutos?"
    kind, leader = _resolve_team(question, event, people)
    if kind not in {"sup", "coord"} or not leader:
        return None, None, ("De qual equipe? Não achei você como supervisor(a) ou coordenador(a) no MOP. Me diz o nome "
                            "(ex.: \"casos de CSAT da equipe da Supervisora 3\").")
    field = "supervisor" if kind == "sup" else "coordenador"
    emails = sorted(e for e, p in people.items() if _norm_text(p[field]) == _norm_text(leader))
    return leader, emails or None, "" if emails else f"Não achei operadores da equipe de {leader} no MOP."


def _xlsx_sheet(wb: Any, title: str, header: list[str], rows: list[list[Any]], wide_cols: tuple[str, ...] = ()) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    ws = wb.create_sheet(title[:31])
    ws.append(header)
    for r in rows:
        ws.append([(_to_float(v) if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v.strip()) and len(v.strip()) < 9
                    else v) for v in r])
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="EA1D2C")
    for i, name in enumerate(header, start=1):
        col = ws.cell(row=1, column=i).column_letter
        wide = any(w in _norm_text(name) for w in wide_cols)
        ws.column_dimensions[col].width = 60 if wide else min(max(len(str(name)) + 4, 12), 40)
        if wide:
            for cell in ws[col][1:]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions


def _send_case_list(event: dict[str, Any], client: Any, eps: str | None, question: str) -> str | None:
    ind = _case_indicator(question)
    fila = _fila_in_question(question, eps) or (
        _fila_ref(question, eps, event) if not _TEAM_RE.search(_norm_text(question)) else None)
    leader, team, problem = _case_team(question, event, eps)
    if problem:
        return problem
    if not fila and not team:
        return ("Monto sim! De qual fila ou equipe? (ex.: \"Super Cliente\" ou \"equipe da Supervisora 3\"). Trago caso a "
                "caso e a abertura por operador.")
    d1 = _d1_context(question, event)
    spec = _period_spec("ontem" if d1 else ("semana" if re.search(r"\bsemana\b", _norm_text(question)) else "mês"))
    todas = d1 or bool(re.search(r"\b(todas|promotor\w*|todos os casos)\b", _norm_text(question)))
    filtro = (f"Fila: {fila}\n" if fila else "Fila: todas as filas da EPS\n") + (
        f"Só estes operadores (e-mails): {', '.join(team[:400])}\n" if team else "")
    base = f"{_scope_instruction(eps)}\n\nTAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Chame a *Lyra Indicadores* com exatamente:\nEPS: {eps or 'iFood'}\n"
    fim = "Devolva SOMENTE o CSV que ela responder (ou a linha ERRO:), sem comentar."
    if ind == "csat":
        p_casos = (base + f"Pedido: avaliações detalhadas (CSV)\n{filtro}Período: {spec['cur']}\nNotas: "
                   f"{'todas' if todas else 'detratoras (1, 2 e 3)'}\nLimite: {CASE_LIST_MAX}\n{fim}")
        p_ops = None
        aba, wide = "Avaliações", ("coment",)
        escopo = "todas as notas" if todas else "só detratoras (notas 1 a 3)"
        extra = "" if todas else " No mês, as promotoras ficam fora pelo volume; pra todas as notas, peça por D-1."
    elif ind == "sla":
        lim = _sla_limite_txt(fila)
        p_casos = (base + f"Pedido: casos fora do SLA (CSV)\n{filtro}Período: {spec['cur']}\nLimite de 1ª resposta: "
                   f"{lim}\nLimite: {CASE_LIST_MAX}\n{fim}")
        p_ops = base + f"Pedido: SLA por operador (CSV)\n{filtro}Período: {spec['cur']}\nLimite de 1ª resposta: {lim}\n{fim}"
        aba, wide = "Fora do SLA", ()
        escopo = f"interações com 1ª resposta acima de {lim}"
        extra = ""
    else:
        p_casos = (base + f"Pedido: casos de TMA (CSV)\n{filtro}Período: {spec['cur']}\nLimite: {CASE_LIST_MAX}\n{fim}")
        p_ops = base + f"Pedido: TMA por analista (CSV)\n{filtro}Período: {spec['cur']}\n{fim}"
        aba, wide = "Casos de TMA", ()
        escopo = "casos do maior para o menor tempo de atribuição"
        extra = ""
    out: dict[str, Any] = {}

    def ask(key: str, prompt: str) -> None:
        try:
            out[key] = ask_toqan(prompt, max_attempts=INTERACTIVE_MAX_POLLS)
        except Exception as exc:
            out[key] = f"ERRO: {exc}"

    threads = [threading.Thread(target=ask, args=("casos", p_casos), daemon=True)]
    if p_ops:
        threads.append(threading.Thread(target=ask, args=("ops", p_ops), daemon=True))
    for t in threads:
        t.start()
    rows_op_csat = None
    if ind == "csat":
        try:
            rows_op_csat = _fetch_operator_rows(eps, spec["cur"], team)
        except Exception:
            rows_op_csat = None
    for t in threads:
        t.join()

    def parse(key: str) -> tuple[list[str], list[list[str]], int] | None:
        parsed = None if _is_error_answer(out.get(key, "")) else _parse_data_csv(out.get(key, ""))
        if not parsed:
            return None
        _, header, rows = parsed
        total_line = next((r for r in rows if r and r[0].upper() == "TOTAL"), None)
        rows = [[_mask_pii(c) for c in r] for r in rows if r and r[0].upper() != "TOTAL"]
        raw_n = len(rows)
        op_col = next((i for i, h in enumerate(header) if "operador" in _norm_text(h) or "email" in _norm_text(h)), None)
        if op_col is not None:
            user = lambda v: str(v or "").strip().lower().split("@")[0]
            if eps:  # trava: operador só da EPS do canal (quando vier o e-mail completo)
                rows = [r for r in rows if len(r) > op_col and
                        ("@" not in r[op_col] or _eps_pattern(eps) in r[op_col].lower())]
            if team:  # compara pelo usuário do e-mail (a base pode devolver com ou sem domínio, maiúsculas etc.)
                ts = {user(e) for e in team}
                rows = [r for r in rows if len(r) > op_col and user(r[op_col]) in ts]
        out[f"{key}_raw_n"] = raw_n
        total = int(_to_float(total_line[1]) or raw_n) if total_line and len(total_line) > 1 else raw_n
        return header, rows, (total if total > raw_n else 0)  # 0 = não houve corte pelo limite

    casos = parse("casos")
    if ind == "csat":
        op_header = ["E-mail", "Fila", "Avaliações", "Promotores", "Detratores", "CSAT (%)", "Meta (%)",
                     "Atingimento (%)", "Quadrante"]
        ops = [r for r in (rows_op_csat or []) if len(r) >= 8 and (not fila or _norm_text(r[1]) == _norm_text(fila))
               and (not team or r[0].lower() in set(team))]
        ops.sort(key=lambda r: _to_float(r[6]) if _to_float(r[6]) is not None else 999)
        op_rows = [[r[0], r[1], _to_float(r[2]) or 0, _to_float(r[3]) or 0, (_to_float(r[2]) or 0) - (_to_float(r[3]) or 0),
                    _to_float(r[4]), _to_float(r[5]), _to_float(r[6]), r[7]] for r in ops]
    else:
        po = parse("ops")
        op_header, op_rows = (po[0], po[1]) if po else (["Operador"], [])
    if not casos and not op_rows:
        return "Não consegui puxar essa base agora. Tenta de novo em alguns minutos?"
    esperado = sum(int(r[4] or 0) for r in op_rows) if ind == "csat" and op_rows and len(op_rows[0]) > 4 else 0
    if (not casos or not casos[1]) and esperado:
        # base de casos veio vazia, mas os operadores têm detratoras: não entregar "0 casos" como se fosse verdade
        raw = str(out.get("casos", ""))[:600]
        _alert(f"⚠️ Base caso a caso de CSAT veio vazia ({fila or leader}, {spec['short']}), mas a aba por operador tem "
               f"{esperado} detratoras. Linhas da Indicadores antes do filtro: {out.get('casos_raw_n', 0)}. "
               f"Início da resposta:\n```{raw}```")
        return (f"A lista de casos voltou vazia, mas {('a equipe de ' + leader) if leader else f'`{fila}`'} tem {esperado} "
                f"detratora(s) no período — a consulta falhou do meu lado, não é falta de caso. Já avisei o time; tenta "
                "de novo daqui a pouco?")
    if ind in {"sla", "tma"} and (not casos or not casos[1]) and not op_rows:
        # nada de planilha vazia: o mais comum é a base de filas ainda não ter fechado o dia pedido
        alvo0 = f"`{fila}`" if fila else f"a equipe de {leader}"
        if d1:
            return (f"Não veio nenhuma interação de {alvo0} em {spec['short']} na base de filas: ela ainda não fechou o dia "
                    "de ontem (costuma entrar mais tarde). Me pede de novo amanhã cedo, ou peça \"da semana\" que eu "
                    "trago os dias já fechados.")
        return f"Não veio nenhuma interação de {alvo0} em {spec['short']} na base de filas. Quer outro período?"
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    if casos:
        _xlsx_sheet(wb, aba, casos[0], casos[1], wide)
    else:
        _xlsx_sheet(wb, aba, ["Aviso"], [["Os casos não vieram agora — peça de novo em alguns minutos."]])
    _xlsx_sheet(wb, "Por operador", op_header, op_rows)
    buf = io.BytesIO()
    wb.save(buf)
    n_casos = len(casos[1]) if casos else 0
    total_casos = casos[2] if casos else 0
    corte = (f" Pelo limite, vieram os {n_casos} primeiros de {_fmt_int(total_casos)}; pra ver todos, peça por D-1 ou "
             "por semana." if casos and total_casos else "")
    alvo = " · ".join(x for x in [f"`{fila}`" if fila else "", f"equipe de {leader}" if leader else ""] if x)
    nome_ind = {"csat": "CSAT", "sla": "SLA 1ª resposta", "tma": "TMA"}[ind]
    (client or slack_app.client).files_upload_v2(
        channel=event.get("channel"), thread_ts=_reply_ts(event), content=buf.getvalue(),
        filename=re.sub(r"[^\w\-]+", "_", f"{nome_ind}_casos_{fila or leader or ''}_{_now_brazil().strftime('%d-%m')}")[:60] + ".xlsx",
        title=f"{nome_ind} · casos · {fila or leader} · {spec['short']}",
        initial_comment=(f"📋 *{nome_ind}* · {alvo} · {spec['short']} · {escopo}: {n_casos} caso(s) na aba *{aba}* e "
                         f"{len(op_rows)} operador(es) na aba *Por operador*.{corte}{extra}"))
    return None


_PII_RES = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[e-mail]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[cpf]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[cartão]"),
    (re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b"), "[telefone]"),
]


def _mask_pii(value: str) -> str:
    """Comentário de cliente vai para a planilha sem dado pessoal (e-mail, CPF, cartão, telefone). E-mail de operador
    da EPS (if-aec/if-csu) fica."""
    v = str(value or "")
    if re.fullmatch(r"\s*[\w.+-]+@if-(aec|csu)\.com\.br\s*", v, re.I) or re.fullmatch(r"\s*\d{6,10}\s*", v):
        return v.strip()  # e-mail do operador / número do caso
    for rx, rep_ in _PII_RES:
        v = rx.sub(rep_, v)
    return v


# --- Visão da CAPA (eficiência CX: volume, TMA e SLA planejado x realizado, uma linha por célula) ------------------
# A query fica em queries/capa.sql (handoff validado contra a CAPA do Excel mensal; fórmulas sem alteração). O app só
# troca as datas e manda rodar. Com TOQAN_INDICADORES_KEY (chave da Lyra Indicadores no Toqan) o SQL vai direto para
# ela; sem a chave, vai pela Lyra principal. Manutenção mensal no próprio arquivo (MES_PLANO, plano_ticket, celulas).
CAPA_SQL_PATH = os.getenv("CAPA_SQL_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "queries", "capa.sql"))
TOQAN_INDICADORES_KEY = os.getenv("TOQAN_INDICADORES_KEY", "").strip() or None
CAPA_SLA_META = {"cx super cliente - aec": 90.0, "cx super cliente - csu": 90.0, "pf super clientes": 90.0}
CAPA_SLA_META_PADRAO = 80.0
_CAPA_CACHE: dict[str, tuple[float, list[dict[str, str]]]] = {}
CAPA_DIARIA_SQL_PATH = os.path.join(os.path.dirname(CAPA_SQL_PATH), "capa_diaria.sql")
CAPA_PLANOS_PATH = os.path.join(os.path.dirname(CAPA_SQL_PATH), "capa_planos.json")
# células da CAPA (ordem, EPS, corte de SLA em min) — o plano (média de interações, tempo de atendimento por interação e
# ticket único por dia) vem por mês do capa_planos.json (aba PLAN de cada Excel mensal)
CAPA_CELULAS = [(1, "AEC", "CX Suporte", 5), (2, "AEC", "Madrugada", 5), (3, "AEC", "CX Review - AeC", 5),
                (4, "CSU", "CX Review - CSU", 5), (5, "AEC", "CX Super Cliente - AeC", 2),
                (6, "CSU", "CX Super Cliente - CSU", 2), (7, "CSU", "PF Cancelamento", 5),
                (8, "CSU", "PF Super Clientes", 5), (9, "CSU", "PF Revisão Manual", 5), (10, "CSU", "CX Denúncia", 5),
                (11, "CSU", "Fraudes DX", 5), (12, "CSU", "DX - PF Contestação", 5),
                (13, "CSU", "DX - PF Contestação Bloqueio temporário", 5), (14, "AEC", "Fila desativada 37 - Canarinhos", 5)]
_DIARIO_RE = re.compile(r"\b(diari\w*|dia a dia|por dia|cada dia|dia por dia)\b")
_CAPA_RE = re.compile(r"\b(tma|sla|primeira resposta|capa|eficiencia|ticket unico|tickets unicos|interacoes|"
                      r"planejado x realizado|plan x real|aderencia ao plan\w*)\b")


def _compact_sql(sql: str) -> str:
    """Tira comentários e espaços repetidos (fora de strings): mesma consulta, mensagem menor."""
    out = []
    for line in sql.split("\n"):
        parts = re.split(r"('(?:[^']|'')*'|`[^`]*`)", line)
        new = ""
        for i, part in enumerate(parts):
            if i % 2:
                new += part
                continue
            if "--" in part:
                new += re.sub(r"[ \t]+", " ", part[:part.index("--")])
                break
            new += re.sub(r"[ \t]+", " ", part)
        if new.strip():
            out.append(new.strip())
    return "\n".join(out)


def _capa_template(diaria: bool = False) -> tuple[str | None, str]:
    try:
        with open(CAPA_DIARIA_SQL_PATH if diaria else CAPA_SQL_PATH, encoding="utf-8") as fh:
            sql = fh.read()
    except OSError:
        return None, ""
    return sql, ""


def _capa_planos() -> dict[str, Any]:
    try:
        with open(CAPA_PLANOS_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _capa_plano_values(mes: str) -> tuple[str, str, bool]:
    """(VALUES das células, VALUES do plano diário, tem plano do mês)."""
    plano = _capa_planos().get(mes) or {}
    cel = []
    for ordem, eps_c, nome, corte in CAPA_CELULAS:
        p = plano.get(nome)
        mi = f"{float(p['media_interacoes_plan']):.4f}" if p else "1.00"
        ti = f"{float(p['tempo_atendimento_plan']):.7f}" if p else "NULL"
        cel.append(f"({ordem}, '{eps_c}', '{nome}', {corte}, {mi}, {ti})")
    pt = []
    for nome, p in plano.items():
        dias = [v for _, v in sorted((p.get("tickets") or {}).items()) if _ and _.startswith(mes)]
        if dias:
            pt.append(f"('{nome}', ARRAY({', '.join(str(int(v)) for v in dias)}))")
    if not pt:
        pt = ["('__sem_plano__', ARRAY(0))"]
    return ",\n    ".join(cel), ",\n    ".join(pt), bool(plano)


def _is_capa_request(question: str) -> bool:
    t = _norm_text(question)
    return bool(_CAPA_RE.search(t)) and not re.search(
        r"\b(analista\w*|operador\w*|equipe|time d[aeo]|supervisor\w*|casos?|tickets? a ticket|por que|porque|pq|csat|"
        r"como funciona|o que e|o que significa|motivo\w*|ofensor\w*|trein\w*)\b", t) and bool(_capa_template()[0])


_MES_NOMES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
              "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def _capa_period(question: str, event: dict[str, Any]) -> tuple[date, date, str]:
    d1 = _as_date(_today_brazil()) - timedelta(days=1)
    t = _norm_text(question)
    m_rng = re.search(r"\b(\d{1,2})/(\d{1,2})\s*(?:a|ate|-)\s*(\d{1,2})/(\d{1,2})\b", t)
    if m_rng:  # "01/11 a 05/11"
        d_a, m_a, d_b, m_b = (int(x) for x in m_rng.groups())
        try:
            ano = d1.year if m_a <= d1.month else d1.year - 1
            ini, fim = date(ano, m_a, d_a), min(date(ano if m_b >= m_a else ano + 1, m_b, d_b), d1)
            return ini, fim, f"{ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}"
        except ValueError:
            pass
    mes_q = next((n for nome, n in _MES_NOMES.items() if re.search(rf"\b{nome}\b", t)), None)
    if mes_q is None and re.search(r"\b(mes passado|mes anterior|ultimo mes|mes fechado)\b", t):
        mes_q = (d1.replace(day=1) - timedelta(days=1)).month
    if mes_q:  # mês pedido pelo nome: o mês inteiro (ou até ontem, se for o mês atual)
        ano = d1.year if mes_q <= d1.month else d1.year - 1
        ini = date(ano, mes_q, 1)
        prox = date(ano + (mes_q == 12), mes_q % 12 + 1, 1)
        fim = min(prox - timedelta(days=1), d1)
        nome = _MESES[mes_q - 1]
        return ini, fim, (f"{nome} fechado" if fim < d1 or fim.day == (prox - timedelta(days=1)).day
                          else f"{nome} (01 a {fim.strftime('%d/%m')})")
    if _d1_context(question, event):
        return d1, d1, f"D-1 {d1.strftime('%d/%m')}"
    if re.search(r"\b(semana|7 dias|ultimos 7)\b", t):
        ini = max(d1 - timedelta(days=6), d1.replace(day=1))
        return ini, d1, f"{ini.strftime('%d/%m')} a {d1.strftime('%d/%m')}"
    return d1.replace(day=1), d1, f"mês 01 a {d1.strftime('%d/%m')}"


def _capa_rows(ini: date, fim: date, progress: Callable[[str], Any] | None = None, diaria: bool = False,
               celula: str | None = None) -> tuple[list[dict[str, str]] | None, str]:
    sql, _ = _capa_template(diaria)
    if not sql:
        return None, "A visão de eficiência não está configurada (falta o SQL em queries/)."
    if ini.strftime("%Y-%m") != fim.strftime("%Y-%m"):
        return None, "Me pede um mês por vez (ex.: outubro, ou novembro até ontem) que eu trago certinho."
    mes = ini.strftime("%Y-%m")
    key = f"{'d' if diaria else 'm'}:{celula or ''}:{ini}:{fim}"
    hit = _CAPA_CACHE.get(key)
    if hit and time.time() - hit[0] < 1800:
        return hit[1], ""
    cel_v, plano_v, tem_plano = _capa_plano_values(mes)
    filtro = f"celula_capa = '{celula}'" if celula else "1 = 1"
    filled = _compact_sql(sql.replace("{data_inicio}", ini.isoformat()).replace("{data_fim}", fim.isoformat())
                          .replace("{mes_plano}", mes).replace("{celulas_values}", cel_v)
                          .replace("{plano_ticket_values}", plano_v).replace("{filtro_celulas}", filtro))
    out, problema = _run_app_sql(filled, progress, f"Eficiência ({ini} a {fim}{', diária' if diaria else ''})")
    if out is not None and not tem_plano:
        for r in out:
            r["_sem_plano"] = "1"
    if out is not None:
        _CAPA_CACHE[key] = (time.time(), out)
    return out, problema


def _run_app_sql(filled: str, progress: Callable[[str], Any] | None, nome: str,
                 acesso: bool = False) -> tuple[list[dict[str, str]] | None, str]:
    """Manda um SQL pronto do app para a Lyra Indicadores executar como veio; devolve as linhas (cabeçalho normalizado)."""
    # a Lyra Indicadores recusa pedido sem a linha EPS: (seção 1 dela). O recorte já está no SQL, então vai iFood.
    # SQL com e-mail de operador: o app controla quem vê (mesma regra da visão de equipe), então libera a identificação
    corpo = ("EPS: iFood\nPedido: SQL pronto do app\n" + ("Acesso: completo\nLista: completa\n" if acesso else "") + "\n"
             "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Execute no Databricks EXATAMENTE o SQL abaixo, como UMA "
             "instrução só, sem alterar nada (nem datas, nem fórmulas, nem colunas). Devolva SOMENTE o resultado em CSV "
             "separado por ';', com a linha de cabeçalho exatamente como as colunas saírem, números com ponto decimal e "
             "sem separador de milhar. Se a execução falhar, devolva só: ERRO: <mensagem do Databricks>.\n\n```sql\n"
             + filled + "\n```")
    try:
        if TOQAN_INDICADORES_KEY:
            conv, req = create_conversation(corpo, TOQAN_INDICADORES_KEY)
            ans = get_answer(conv, req, progress_callback=progress, api_key=TOQAN_INDICADORES_KEY,
                             max_attempts=INTERACTIVE_MAX_POLLS)
        else:
            ans = ask_toqan("Chame a *Lyra Indicadores* e passe a ela, sem mudar nada, a tarefa abaixo. Devolva SOMENTE "
                            "o que ela responder.\n\n" + corpo, progress_callback=progress,
                            max_attempts=INTERACTIVE_MAX_POLLS)
    except Exception as exc:
        return None, f"A consulta falhou ({str(exc)[:120]})."
    parsed = None if _is_error_answer(ans) else _parse_data_csv(ans)
    if not parsed:
        _alert(f"⚠️ {nome} sem resultado. Resposta: ```{str(ans)[:500]}```")
        return None, "A consulta não voltou agora. Já avisei o time; tenta de novo daqui a pouco?"
    _, header, rows = parsed
    norm = [_norm_text(h).replace("`", "").strip() for h in header]
    return [{norm[i]: (r[i] if i < len(r) else "") for i in range(len(norm))} for r in rows
            if r and any(c.strip() for c in r)], ""


def _sql_num(value: Any) -> float | None:
    """Número vindo do Databricks: com sinal e notação científica (3.79E7), ponto decimal."""
    v = str(value if value is not None else "").strip().replace("−", "-").replace(" ", "")
    if v in ("", "null", "NULL", "None", "NaN"):
        return None
    try:
        return float(v)
    except ValueError:
        m = re.search(r"-?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", v)
        return float(m.group(0).replace(",", ".")) if m else None


def _cv(row: dict[str, str], *names: str) -> float | None:
    for n in names:
        f = _sql_num(row.get(_norm_text(n)))
        if f is not None:
            return f
    return None


def _capa_sla_meta(celula: str) -> float:
    metas = {_norm_text(k): v for k, v in CAPA_SLA_META.items()}
    return metas.get(_norm_text(celula), CAPA_SLA_META_PADRAO)


CAPA_MIN_TICKETS = 20  # célula com volume residual (ex.: fila desativada) não entra na mensagem


def _render_capa(rows: list[dict[str, str]], eps: str | None, label: str) -> str:
    """TMA e SLA no modelo do report das 9h: título com o consolidado, bloco por fila (valor → veredito) e Leitura."""
    blocos = []

    def tma_vs_plan(v: float, plan: float | None) -> str:
        if not plan:
            return "⚪ plan a definir"
        d = v - plan
        if d > 0.5:
            return f"🔴 {_fmt_int(d)} s acima do plan {_fmt_int(plan)} s"
        return f"🟢 {_fmt_int(-d)} s abaixo do plan {_fmt_int(plan)} s" if d < -0.5 else "🟢 no plan"

    def sla_vs_meta(v: float, meta: float) -> str:
        if v < meta:
            return f"🔴 {_bfmt(meta - v)} p.p. abaixo da meta {_fmt_meta(meta)}%"
        return f"🟢 {_bfmt(v - meta)} p.p. acima da meta {_fmt_meta(meta)}%" if v > meta else "🟢 na meta"

    for eps_k, eps_nome in (("aec", "AeC"), ("csu", "CSU")):
        if eps and _compact(eps) != eps_k:
            continue
        cel_all = [r for r in rows if _norm_text(r.get("eps", "")) == eps_k and (_cv(r, "interacoes real") or 0) > 0]
        cel = [r for r in cel_all if (_cv(r, "ticket unico real") or 0) >= CAPA_MIN_TICKETS]
        if not cel:
            continue
        sem_plano = any(r.get("_sem_plano") for r in cel)
        # consolidado com as somas (nunca média das células)
        s_tempo = sum(_cv(r, "soma tempo atribuicao") or 0 for r in cel_all)
        s_tk = sum(_cv(r, "ticket unico real") or 0 for r in cel_all)
        s_tk_p = sum(_cv(r, "ticket unico plan") or 0 for r in cel_all if _cv(r, "tempo atendimento plan (ticket)"))
        s_tempo_p = sum((_cv(r, "ticket unico plan") or 0) * (_cv(r, "tempo atendimento plan (ticket)") or 0) for r in cel_all)
        s_base = sum(_cv(r, "sla base") or 0 for r in cel_all)
        s_dentro = sum(_cv(r, "sla dentro") or 0 for r in cel_all)
        tk_plan_all = sum(_cv(r, "ticket unico plan") or 0 for r in cel_all)
        tma_c = s_tempo / s_tk if s_tk and s_tempo else None
        tma_cp = s_tempo_p / s_tk_p if s_tk_p else None
        sla_c = s_dentro / s_base * 100 if s_base else None
        off_c = tma_c is not None and tma_cp is not None and tma_c > tma_cp + 0.5
        head = f"{'🔴' if off_c else '🟢'} *TMA e SLA ·* `{eps_nome}` *— {label}*"
        if tma_c is not None:
            head += f" · TMA {_fmt_int(tma_c)} s" + (f" (plan {_fmt_int(tma_cp)} s)" if tma_cp else "")
        if sla_c is not None:
            head += f" · SLA {_bfmt(sla_c)}%"
        linhas = [head]
        if sem_plano:
            linhas.append("_Sem plano carregado para esse mês: comparo só o realizado._")
        linhas += ["", f"📍 *Consolidado {eps_nome}*"]
        if tma_c is not None:
            linhas.append(f"• TMA *{_fmt_int(tma_c)} s* → {tma_vs_plan(tma_c, tma_cp)}")
        if sla_c is not None:
            linhas.append(f"• SLA de 1ª resposta *{_bfmt(sla_c)}%* (2 min nas Super Cliente, 5 min nas demais)")
        if s_tk:
            linhas.append(f"• Tickets *{_fmt_int(s_tk)}*" + (f" → {_bfmt(abs(s_tk / tk_plan_all - 1) * 100)}% "
                                                          f"{'acima' if s_tk >= tk_plan_all else 'abaixo'} do plan "
                                                          f"{_fmt_int(tk_plan_all)}" if tk_plan_all else ""))
        linhas += ["", "🗂️ *Por fila*"]
        piores, leitura = [], []
        for r in cel:
            nome = r.get("celula", "")
            tma, tma_p = _cv(r, "tempo atribuicao (ticket)"), _cv(r, "tempo atendimento plan (ticket)")
            sla, corte = _cv(r, "sla"), r.get("corte sla", "")
            meta = _capa_sla_meta(nome)
            tk, tk_p = _cv(r, "ticket unico real"), _cv(r, "ticket unico plan")
            mi, mi_p = _cv(r, "media interacoes real"), _cv(r, "media interacoes plan")
            sla_pct = sla * 100 if sla is not None and sla <= 1.5 else sla
            ruim_tma = tma is not None and bool(tma_p) and tma > tma_p + 0.5
            ruim_sla = sla_pct is not None and sla_pct < meta
            vol = (f" · {_fmt_int(tk)} tickets" + (f" ({'+' if tk >= tk_p else '−'}{_bfmt(abs(tk / tk_p - 1) * 100, 0)}% "
                                                   f"vs plan)" if tk_p else "")) if tk is not None else ""
            linhas.append(f"{'🔴' if ruim_tma or ruim_sla else '🟢'} `{nome}`{vol}")
            if tma is not None:
                linhas.append(f"   • TMA *{_fmt_int(tma)} s* → {tma_vs_plan(tma, tma_p)}")
            if sla_pct is not None:
                linhas.append(f"   • SLA{(' ' + corte) if corte else ''} *{_bfmt(sla_pct)}%* → {sla_vs_meta(sla_pct, meta)}")
            peso = tk or 0
            if ruim_sla:
                piores.append((2, (meta - sla_pct) * peso, nome, f"SLA {_bfmt(meta - sla_pct)} p.p. abaixo da meta"))
            if ruim_tma:
                piores.append((1, (tma - tma_p) * peso, nome, f"TMA {_fmt_int(tma - tma_p)} s acima do plan"))
                if mi and mi_p and mi > mi_p * 1.03:
                    leitura.append(f"`{nome}`: {_bfmt(mi, 2)} interações por ticket (plan {_bfmt(mi_p, 2)}): o ticket "
                                   "está voltando mais vezes para a fila, e isso puxa o TMA.")
        if piores:  # o pior SLA (abaixo da meta) e o pior TMA (acima do plan), pesados pelo volume de tickets
            top: dict[str, list[str]] = {}
            for tipo in (2, 1):
                cand = sorted([p for p in piores if p[0] == tipo], key=lambda x: x[1], reverse=True)
                if cand:
                    top.setdefault(cand[0][2], []).append(cand[0][3])
            leitura.insert(0, "Mais preocupa: " + " e ".join(f"`{c}` ({' e '.join(v)})" for c, v in top.items()) + ".")
        else:
            leitura.insert(0, "Todas as filas dentro do plan de TMA e da meta de SLA. 👏")
        linhas += ["", "💡 *Leitura*"] + [f"↳ {t}" for t in leitura[:3]]
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)


def _capa_resumo(rows: list[dict[str, str]], eps: str | None, label: str) -> str:
    """Resumo de TMA e SLA para o "como tá a EPS?": consolidado + o que mais preocupa (o detalhe vem no "TMA e SLA")."""
    completo = _render_capa(rows, eps, label)
    out = []
    for parte in re.split(r"\n\n(?=[🔴🟢] \*TMA e SLA ·\*)", completo or ""):
        linhas = parte.split("\n")
        if not linhas:
            continue
        eps_txt = re.search(r"`([^`]+)`", linhas[0])
        cons = [l for l in linhas if l.startswith("• TMA") or l.startswith("• SLA")]
        fora_sla = sum(1 for l in linhas if l.startswith("   • SLA") and "🔴" in l)
        tot_sla = sum(1 for l in linhas if l.startswith("   • SLA"))
        fora_tma = sum(1 for l in linhas if l.startswith("   • TMA") and "🔴" in l)
        tot_tma = sum(1 for l in linhas if l.startswith("   • TMA") and "plan a definir" not in l)
        preocupa = next((l for l in linhas if l.startswith("↳ Mais preocupa")), "")
        r = [f"⚙️ *TMA e SLA · `{eps_txt.group(1) if eps_txt else ''}`* — {label}"]
        r += [c.replace(" (2 min nas Super Cliente, 5 min nas demais)", "") for c in cons[:2]]
        if tot_tma or tot_sla:
            r.append(f"• Filas fora: TMA acima do plan em {fora_tma} de {tot_tma} · SLA abaixo da meta em {fora_sla} de {tot_sla}")
        if preocupa:
            r.append(preocupa)
        out.append("\n".join(r))
    nome = f" da {eps}" if eps else ""
    return "\n\n".join(out) + (f"\n_Pra ver fila a fila: \"TMA e SLA{nome}\"; dia a dia: \"TMA e SLA dia a dia{nome}\"._"
                                 if out else "")


def _capa_xlsx(rows: list[dict[str, str]], eps: str | None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "CAPA"
    cols = [k for k in (rows[0].keys() if rows else [])]
    ws.append([c.upper() for c in cols] + ["SLA META", "TMA DESVIO (S)", "SLA X META (P.P.)"])
    sel = [r for r in rows if not eps or _norm_text(r.get("eps", "")) == _compact(eps)]
    for i, r in enumerate(sel, start=2):
        ws.append([(_sql_num(r[c]) if _sql_num(r[c]) is not None else r[c]) for c in cols] + [_capa_sla_meta(r.get("celula", "")) / 100])
        letter = lambda name: ws.cell(row=1, column=cols.index(name) + 1).column_letter if name in cols else None
        a, b, sl = letter("tempo atribuicao (ticket)"), letter("tempo atendimento plan (ticket)"), letter("sla")
        meta_col = ws.cell(row=1, column=len(cols) + 1).column_letter
        if a and b:
            ws.cell(row=i, column=len(cols) + 2, value=f'=IF({b}{i}="","",{a}{i}-{b}{i})')
        if sl:
            ws.cell(row=i, column=len(cols) + 3, value=f'=IF({sl}{i}="","",({sl}{i}-{meta_col}{i})*100)')
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="EA1D2C")
    ws.freeze_panes = "C2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()



# --- Motivos que mais pesam no TMA e no SLA (mesmas regras da CAPA) -------------------------------------------------
MOTIVOS_EFIC_SQL_PATH = os.getenv("MOTIVOS_EFIC_SQL_PATH", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "queries", "motivos_eficiencia.sql"))
_MOTIVOS_EFIC_CACHE: dict[str, tuple[float, list[dict[str, str]]]] = {}


def _efic_indicator(question: str) -> str | None:
    t = _norm_text(question)
    if re.search(r"\bcsat\b", t):
        return None
    if re.search(r"\b(sla|primeira resposta|1a resposta)\b", t):
        return "sla"
    if re.search(r"\b(tma|tempo de atendimento|tempo de atribuicao)\b", t):
        return "tma"
    return None


def _motivos_efic_rows(eps: str | None, ini: date, fim: date,
                       progress: Callable[[str], Any] | None = None) -> tuple[list[dict[str, str]] | None, str]:
    try:
        with open(MOTIVOS_EFIC_SQL_PATH, encoding="utf-8") as fh:
            sql = fh.read()
    except OSError:
        return None, "A análise de motivos de TMA e SLA não está configurada (falta queries/motivos_eficiencia.sql)."
    eps_lista = ", ".join(f"'{e}'" for e in (["AEC", "CSU"] if not eps else [_compact(eps).upper()]))
    key = f"{eps_lista}:{ini}:{fim}"
    hit = _MOTIVOS_EFIC_CACHE.get(key)
    if hit and time.time() - hit[0] < 1800:
        return hit[1], ""
    filled = _compact_sql(sql.replace("{data_inicio}", ini.isoformat()).replace("{data_fim}", fim.isoformat())
                          .replace("{eps_lista}", eps_lista))
    rows, problema = _run_app_sql(filled, progress, f"Motivos de TMA/SLA ({ini} a {fim})")
    if rows is not None:
        _MOTIVOS_EFIC_CACHE[key] = (time.time(), rows)
    return rows, problema


def _render_motivos_efic(rows: list[dict[str, str]], ind: str, label: str, fila: str | None = None, top: int = 3) -> str:
    """Motivos que pesam (impacto positivo) por célula. TMA: horas de operação a mais; SLA: interações fora do prazo a
    mais do que a taxa da célula."""
    imp_col = "impacto tma (h)" if ind == "tma" else "impacto sla (fora)"
    por_cel: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        if fila and _norm_text(r.get("celula", "")) != _norm_text(fila):
            continue
        if (_cv(r, imp_col) or 0) > 0:
            por_cel.setdefault(r.get("celula", ""), []).append(r)
    if not por_cel:
        return ""
    titulo = ("⏱️ *Motivos que mais pesam no TMA*" if ind == "tma" else "⏰ *Motivos que mais pesam no SLA de 1ª resposta*")
    regua = ("quanto cada motivo puxa o tempo da fila: (tempo do motivo − média da fila) × tratados" if ind == "tma"
             else "quanto cada motivo derruba o SLA da fila: interações fora do prazo além do que a taxa da fila daria")
    linhas = [f"{titulo} — {label} · _{regua}_"]
    ordem = sorted(por_cel, key=lambda c: -sum(_cv(r, imp_col) or 0 for r in por_cel[c]))
    sem_mot = lambda r: _norm_text(_motivo_label(r.get("motivo")) or "") in {"", "sem motivo", "null", "none"}
    for cel in ordem:
        validos = [r for r in por_cel[cel] if not sem_mot(r)]
        itens = sorted(validos, key=lambda r: -(_cv(r, imp_col) or 0))[:top]
        if not itens:
            continue
        r0 = itens[0]
        sm = next((r for r in por_cel[cel] if sem_mot(r)), None)
        peso_sm = (_cv(sm, "peso tratados" if ind == "tma" else "peso sla") or 0) if sm else 0
        if ind == "tma":
            ref = _cv(r0, "tempo atribuicao celula")
            linhas.append("")
            linhas.append(f"`{cel}` · média da fila: {_fmt_int(ref or 0)} s por interação")
            for r in itens:
                t_m = _cv(r, "tempo atribuicao motivo") or 0
                peso = _cv(r, "peso tratados") or 0
                linhas.append(f"• *{_motivo_label(r.get('motivo'))}*: {_fmt_int(t_m)} s, *{_fmt_int(t_m - (ref or 0))} s acima* "
                              f"da média · {_fmt_int(_cv(r, 'tratados') or 0)} tratados ({_bfmt(peso * 100)}% da fila)")
                linhas.append(f"   ↳ puxa a média da fila em +{_bfmt(peso * (t_m - (ref or 0)), 1)} s · "
                              f"{_bfmt(_cv(r, imp_col) or 0)} h a mais de operação no período")
        else:
            ref = _cv(r0, "sla celula")
            linhas.append("")
            linhas.append(f"`{cel}` · SLA da fila {r0.get('corte sla', '')}: {_bfmt((ref or 0) * 100)}%")
            for r in itens:
                n_i, peso = _cv(r, "interacoes sla") or 0, _cv(r, "peso sla") or 0
                total = n_i / peso if peso else 0
                extra = _cv(r, imp_col) or 0
                linhas.append(f"• *{_motivo_label(r.get('motivo'))}*: SLA {_bfmt((_cv(r, 'sla motivo') or 0) * 100)}% · "
                              f"{_fmt_int(n_i)} interações ({_bfmt(peso * 100)}% da fila)")
                linhas.append(f"   ↳ {_fmt_int(extra)} fora do prazo a mais do que a média da fila daria"
                              + (f" · tira {_bfmt(extra / total * 100, 1)} p.p. do SLA da fila" if total else ""))
        if peso_sm >= 0.05:
            linhas.append(f"   _{_bfmt(peso_sm * 100)}% da fila está sem motivo tabulado: ficou fora do ranking (não dá pra "
                          "treinar o que não foi tabulado), mas vale cobrar a tabulação._")
    return "\n".join(linhas)


def _capa_check_referencia(rows: list[dict[str, str]], ini: date, fim: date) -> None:
    """Mês fechado com referência da planilha oficial (queries/capa_referencia.json): se a Lyra não bater, alerta o time."""
    try:
        with open(os.path.join(os.path.dirname(CAPA_SQL_PATH), "capa_referencia.json"), encoding="utf-8") as fh:
            ref = json.load(fh).get(f"{ini.isoformat()}:{fim.isoformat()}") or {}
    except Exception:
        return
    if not ref:  # só confere quando o período é exatamente um dos que temos da planilha oficial
        return
    difs = []
    for r in rows:
        cel = r.get("celula", "")
        alvo = next((v for k, v in ref.items() if _norm_text(k) == _norm_text(cel)), None)
        if not alvo:
            continue
        tma, sla = _cv(r, "tempo atribuicao (ticket)"), _cv(r, "sla")
        if alvo.get("tma_ticket") and tma is not None and abs(tma - alvo["tma_ticket"]) > max(5, 0.02 * alvo["tma_ticket"]):
            difs.append(f"{cel}: TMA {_fmt_int(tma)} s x planilha {_fmt_int(alvo['tma_ticket'])} s")
        if alvo.get("sla") is not None and sla is not None and abs(sla - alvo["sla"]) > 0.01:
            difs.append(f"{cel}: SLA {_bfmt(sla * 100)}% x planilha {_bfmt(alvo['sla'] * 100)}%")
    if difs:
        _alert(f"⚠️ TMA/SLA de {ini.strftime('%d/%m')} a {fim.strftime('%d/%m')} não bateu com a planilha oficial em "
               f"{len(difs)} ponto(s):\n• "
               + "\n• ".join(difs[:12]))


def _render_capa_diaria(rows: list[dict[str, str]], eps: str | None, label: str, celula: str | None) -> str:
    """Dia a dia no modelo do report: um dia por linha com veredito de TMA (vs plan) e SLA (vs meta) e Leitura."""
    blocos = []
    dsem = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    for eps_k, eps_nome in (("aec", "AeC"), ("csu", "CSU")):
        if eps and _compact(eps) != eps_k:
            continue
        sel = [r for r in rows if _norm_text(r.get("eps", "")) == eps_k
               and (not celula or _norm_text(r.get("celula", "")) == _norm_text(celula))]
        if not sel:
            continue
        por_dia: dict[str, list[dict[str, str]]] = {}
        for r in sel:
            por_dia.setdefault(str(r.get("data", ""))[:10], []).append(r)
        dias = sorted(por_dia)
        vol = {d: sum(_cv(r, "ticket unico real") or 0 for r in por_dia[d]) for d in dias}
        tipico = sorted(vol.values())[len(vol) // 2] if vol else 0
        alvo = f"`{celula}`" if celula else f"`{eps_nome}`"
        linhas = [f"📅 *TMA e SLA por dia ·* {alvo} *— {label}*",
                  "_TMA contra o plan do dia · SLA contra a meta"
                  + (f" ({_fmt_meta(_capa_sla_meta(celula))}%)" if celula else " (90% nas Super Cliente, 80% nas demais, "
                     "ponderada pelo volume de cada fila)") + "_", ""]
        serie, pendente = [], None
        for dia in dias:
            rs = por_dia[dia]
            try:
                d = datetime.strptime(dia, "%Y-%m-%d")
                dia_txt = f"{d.strftime('%d/%m')} {dsem[d.weekday()]}"
            except ValueError:
                dia_txt = dia
            if dia == dias[-1] and len(dias) > 1 and vol[dia] < 0.5 * tipico:  # último dia ainda não fechou na base
                pendente = dia_txt.split()[0]
                continue
            tempo = sum(_cv(r, "soma tempo atribuicao") or 0 for r in rs)
            tk = vol[dia]
            tk_p = sum(_cv(r, "ticket unico plan") or 0 for r in rs if _cv(r, "tempo atendimento plan (ticket)"))
            tempo_p = sum((_cv(r, "ticket unico plan") or 0) * (_cv(r, "tempo atendimento plan (ticket)") or 0) for r in rs)
            tk_plan = sum(_cv(r, "ticket unico plan") or 0 for r in rs)
            base = sum(_cv(r, "sla base") or 0 for r in rs)
            dentro = sum(_cv(r, "sla dentro") or 0 for r in rs)
            meta_x = sum((_cv(r, "sla base") or 0) * _capa_sla_meta(r.get("celula", "")) for r in rs)
            tma = tempo / tk if tk else None
            plan = tempo_p / tk_p if tk_p else None
            sla = dentro / base * 100 if base else None
            meta = meta_x / base if base else None
            ruim = (tma is not None and plan and tma > plan + 0.5) or (sla is not None and meta and sla < meta)
            cab = f"{'🔴' if ruim else '🟢'} *{dia_txt}*"
            if tk:
                cab += f" · {_fmt_int(tk)} tickets" + (f" ({'+' if tk >= tk_plan else '−'}"
                                                      f"{_bfmt(abs(tk / tk_plan - 1) * 100, 0)}% vs plan)" if tk_plan else "")
            linhas.append(cab)
            if tma is not None:
                if plan:
                    v = (f"🔴 {_fmt_int(tma - plan)} s acima do plan {_fmt_int(plan)} s" if tma > plan + 0.5 else
                         f"🟢 {_fmt_int(plan - tma)} s abaixo do plan {_fmt_int(plan)} s")
                else:
                    v = "⚪ plan a definir"
                linhas.append(f"   • TMA *{_fmt_int(tma)} s* → {v}")
            if sla is not None:
                v = (f"🔴 {_bfmt(meta - sla)} p.p. abaixo da meta {_bfmt(meta, 0)}%" if meta and sla < meta else
                     f"🟢 {_bfmt(sla - meta)} p.p. acima da meta {_bfmt(meta, 0)}%" if meta else "")
                linhas.append(f"   • SLA *{_bfmt(sla)}%*" + (f" → {v}" if v else ""))
            linhas.append("")
            serie.append((dia_txt, tma, plan, sla, meta))
        if pendente:
            linhas.append(f"⏳ _{pendente}: a base ainda não fechou o dia; entra amanhã._")
        while linhas and linhas[-1] == "":
            linhas.pop()
        leitura = []
        t_ok = [x for x in serie if x[1] is not None and x[2]]
        s_ok = [x for x in serie if x[3] is not None and x[4]]
        if t_ok:
            acima = [x for x in t_ok if x[1] > x[2] + 0.5]
            pior = max(t_ok, key=lambda x: x[1] - x[2])
            leitura.append(f"TMA acima do plan em {len(acima)} de {len(t_ok)} dias"
                           + (f"; pior em {pior[0]} ({_fmt_int(pior[1])} s, +{_fmt_int(pior[1] - pior[2])} s)." if acima else "."))
        if s_ok:
            abaixo = [x for x in s_ok if x[3] < x[4]]
            pior = min(s_ok, key=lambda x: x[3] - x[4])
            leitura.append(f"SLA abaixo da meta em {len(abaixo)} de {len(s_ok)} dias"
                           + (f"; pior em {pior[0]} ({_bfmt(pior[3])}%, {_bfmt(pior[4] - pior[3])} p.p. abaixo)." if abaixo else "."))
            fds = [x for x in s_ok if x[0].endswith(("sáb", "dom"))]
            uteis = [x for x in s_ok if not x[0].endswith(("sáb", "dom"))]
            if len(fds) >= 2 and uteis:
                m_f, m_u = sum(x[3] for x in fds) / len(fds), sum(x[3] for x in uteis) / len(uteis)
                if m_u - m_f >= 3:
                    leitura.append(f"Fim de semana pior no SLA: média {_bfmt(m_f)}% contra {_bfmt(m_u)}% nos dias úteis; "
                                   "vale olhar a escala de sábado e domingo.")
        if leitura:
            linhas += ["", "💡 *Leitura*"] + [f"↳ {t}" for t in leitura]
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)


def _send_capa(event: dict[str, Any], client: Any, eps: str | None, question: str,
               progress: Callable[[str], Any] | None = None) -> str | None:
    if eps is None:
        eps = _eps_in_text(question)  # "TMA e SLA da AeC": só a AeC, mesmo num canal com visão completa
    ini, fim, label = _capa_period(question, event)
    diaria = bool(_DIARIO_RE.search(_norm_text(question)))
    celula = _fila_ref(question, eps, {}) if diaria else None
    rows, problema = _capa_rows(ini, fim, progress, diaria=diaria, celula=celula)
    if not rows:
        return problema or "Não consegui puxar TMA e SLA agora."
    if not diaria:
        _capa_check_referencia(rows, ini, fim)
    texto = _render_capa_diaria(rows, eps, label, celula) if diaria else _render_capa(rows, eps, label)
    if not texto:
        return "Não veio volume nesse período."
    if not re.search(r"\b(planilha|excel|xlsx|base|arquivo)\b", _norm_text(question)):
        return texto  # só texto; a planilha vai quando pedirem
    try:
        (client or slack_app.client).files_upload_v2(
            channel=event.get("channel"), thread_ts=_reply_ts(event), content=_capa_xlsx(rows, eps),
            filename=f"TMA_SLA_{eps or 'iFood'}_{ini.strftime('%d-%m')}_a_{fim.strftime('%d-%m')}.xlsx",
            title=f"TMA e SLA · {eps or 'iFood'} · {label}", initial_comment=texto)
    except Exception:
        logger.warning("CAPA: upload do Excel falhou; mando só o texto", exc_info=True)
        return texto
    return None


# --- Material em PPTX (apresentação da fila) ------------------------------------------------------------------------
_DECK_RE = re.compile(r"\b(pptx|ppt|powerpoint|power point|apresentacao|apresentacoes|slide|slides|deck|material)\b")
DECK_RED, DECK_INK, DECK_MUTED, DECK_LINE = "EA1D2C", "1F1F1F", "6B6B6B", "D9D9D9"


def _is_deck_request(question: str) -> bool:
    text = _norm_text(question)
    return bool(_DECK_RE.search(text)) and bool(re.search(
        r"\b(constroi|construa|construir|monta|monte|montar|cria|crie|criar|gera|gere|gerar|faz|faca|fazer|prepara|"
        r"prepare|preparar|manda|mande|quero|preciso|consegue|pode|me)\b", text))


def _deck_data(event: dict[str, Any], eps: str | None, fila: str, send_progress: Callable[[str], Any] | None):
    """Busca em paralelo: variação do mês (mix x performance) e a série diária do CSAT da fila."""
    cur, ref, l_cur, l_ref = _variation_periods("")
    out: dict[str, Any] = {"labels": (l_cur, l_ref)}

    def var() -> None:
        try:
            ans = ask_toqan(_variation_prompt(eps, fila, cur, ref), max_attempts=INTERACTIVE_MAX_POLLS)
            out["var"] = {} if _is_error_answer(ans) else (_block_data_from_json(ans) or {})
        except Exception:
            logger.warning("Deck: variação falhou", exc_info=True)
            out["var"] = {}

    def serie() -> None:
        try:
            meta = FILA_METAS.get(fila)
            pedido = (f"CSAT diário da fila {fila} no mês atual (dia 1 até D-1), gráfico de linha com as datas dd/mm, "
                      f"série 'CSAT', unidade %" + (f", referencia meta {meta}" if meta is not None else ""))
            ans = ask_toqan(_chart_prompt(eps, pedido, ""), max_attempts=INTERACTIVE_MAX_POLLS)
            spec = {} if _is_error_answer(ans) else (_block_data_from_json(ans) or {})
            out["png"] = _build_chart_png(spec) if spec else None
        except Exception:
            logger.warning("Deck: série diária falhou", exc_info=True)
            out["png"] = None

    threads = [threading.Thread(target=var, daemon=True), threading.Thread(target=serie, daemon=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def _build_deck(fila: str, eps: str | None, row: dict[str, Any] | None, conj: list[dict[str, Any]],
                var: dict[str, Any], png: bytes | None, labels: tuple[str, str]) -> bytes:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    rgb = RGBColor.from_string

    def text(slide, x, y, w, h, runs, size=14, color=DECK_INK, bold=False):
        tf = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
        tf.word_wrap = True
        for i, line in enumerate(runs if isinstance(runs, list) else [runs]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            parts = line if isinstance(line, list) else [(line, bold)]
            for chunk, b in parts:
                r = p.add_run()
                r.text, r.font.size, r.font.bold = chunk, Pt(size), b
                r.font.color.rgb = rgb(color)
            p.space_after = Pt(6)
        return tf

    def header(slide, titulo, sub=""):
        bar = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(0.12))
        bar.fill.solid(); bar.fill.fore_color.rgb = rgb(DECK_RED); bar.line.fill.background()
        text(slide, 0.5, 0.3, 12.3, 0.7, titulo, size=24, bold=True)
        if sub:
            text(slide, 0.5, 0.95, 12.3, 0.4, sub, size=12, color=DECK_MUTED)

    def table(slide, x, y, w, rows_, widths):
        shp = slide.shapes.add_table(len(rows_), len(rows_[0]), Inches(x), Inches(y), Inches(w),
                                     Inches(0.36 * len(rows_)))
        tb = shp.table
        for j, wd in enumerate(widths):
            tb.columns[j].width = Inches(wd)
        for i, r in enumerate(rows_):
            for j, v in enumerate(r):
                c = tb.cell(i, j)
                c.text = str(v)
                para = c.text_frame.paragraphs[0]
                para.runs[0].font.size = Pt(11)
                para.runs[0].font.bold = i == 0
                para.runs[0].font.color.rgb = rgb("FFFFFF" if i == 0 else DECK_INK)
                c.fill.solid()
                c.fill.fore_color.rgb = rgb(DECK_INK if i == 0 else ("F5F5F5" if i % 2 else "FFFFFF"))
        return tb

    l_cur, l_ref = labels
    pp = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + _bfmt(abs(v), 1)
    now = _now_brazil()

    # 1. capa
    sl = prs.slides.add_slide(blank)
    header(sl, f"{fila} · resultado e principais movimentos", f"{eps or 'iFood'} · {l_cur} · gerado pela Lyra em "
                                                               f"{now.strftime('%d/%m às %H:%M')}")
    c_m = n_m = c_d = n_d = imp = None
    meta = row.get("meta") if row else None
    if row:
        c_m, n_m, _ = _agg([row], "mes")
        c_d, n_d, _ = _agg([row], "d1")
        imp = _impact(conj, [row], "mes") if len(conj) > 1 else None
    linhas = []
    if c_m is not None:
        gap = (c_m - meta) if meta is not None else None
        linhas.append([("CSAT do mês: ", False), (f"{_bfmt(c_m)}%", True), (f" (n={_fmt_int(n_m)})", False)]
                      + ([(f" contra meta de {_fmt_meta(meta)}% — {pp(gap)} p.p.", False)] if gap is not None else []))
        if c_d is not None and n_d:
            linhas.append(f"D-1: {_bfmt(c_d)}% (n={_fmt_int(n_d)}).")
        if imp is not None:
            linhas.append(f"Impacto no consolidado da {eps}: {pp(imp)} p.p.")
        if row.get("motivo_mes"):
            linhas.append(f"Motivo de maior impacto no mês: {row['motivo_mes']}"
                          + (f" ({row.get('motivo_mes_pp')} p.p.)" if row.get("motivo_mes_pp") not in (None, "") else "") + ".")
    c_ref, c_cur = _num(var.get("csat_ref")), _num(var.get("csat_atual"))
    if c_ref is not None and c_cur is not None:
        linhas.append(f"Contra {l_ref}: {_bfmt(c_ref)}% → {_bfmt(c_cur)}% ({pp(c_cur - c_ref)} p.p.).")
    text(sl, 0.5, 1.6, 5.6 if png else 12.3, 4.5, linhas or ["Sem dados da fila no período."], size=15)
    destaque = ""
    if c_m is not None and meta is not None:
        destaque = ("Fila na meta no mês." if c_m >= meta else
                    f"Fila {_bfmt(meta - c_m)} p.p. abaixo da meta no mês.")
    if destaque:
        text(sl, 0.5, 6.3, 5.6 if png else 12.3, 0.6, destaque, size=16, bold=True, color=DECK_RED)
    if png:
        sl.shapes.add_picture(io.BytesIO(png), Inches(6.4), Inches(1.5), width=Inches(6.5))

    # 2. principais movimentos
    if var:
        sl = prs.slides.add_slide(blank)
        mix, perf = _num(var.get("mix_pp")), _num(var.get("performance_pp"))
        header(sl, "Principais movimentos", f"{l_ref} → {l_cur} · efeito mix (tipo de contato) x efeito performance "
                                            "(atendimento do mesmo motivo)")
        resumo = []
        if mix is not None and perf is not None:
            resumo.append([("Efeito mix: ", False), (f"{pp(mix)} p.p.", True), ("   ·   Efeito performance: ", False),
                           (f"{pp(perf)} p.p.", True)])
        rr_ref, rr_cur = _num(var.get("rr_ref")), _num(var.get("rr_atual"))
        if rr_ref is not None and rr_cur is not None:
            resumo.append(f"Response rate: {_bfmt(rr_ref)}% → {_bfmt(rr_cur)}% ({pp(rr_cur - rr_ref)} p.p.).")
        n_r, n_c = _num(var.get("n_ref")), _num(var.get("n_atual"))
        if n_r and n_c and (n_c / n_r > 2 or n_c / n_r < 0.5):
            resumo.append(f"Atenção: a amostra mudou muito ({_fmt_int(n_r)} → {_fmt_int(n_c)} avaliações).")
        text(sl, 0.5, 1.5, 12.3, 1.0, resumo, size=14)
        perf_rows = [["Motivo", "CSAT antes", "CSAT agora", "Efeito (p.p.)"]]
        for m in sorted([m for m in (var.get("top_performance") or []) if isinstance(m, dict)],
                        key=lambda m: _num(m.get("efeito_pp")) or 0)[:6]:
            perf_rows.append([_motivo_label(m.get("motivo")), f"{_bfmt(_num(m.get('csat_ref')) or 0)}%",
                              f"{_bfmt(_num(m.get('csat_atual')) or 0)}%", pp(_num(m.get("efeito_pp")) or 0)])
        mix_rows = [["Motivo", "Particip. antes", "Particip. agora", "Efeito (p.p.)"]]
        for m in (var.get("top_mix") or [])[:6]:
            if not isinstance(m, dict):
                continue
            sr, sa, cm = _num(m.get("share_ref")), _num(m.get("share_atual")), _num(m.get("csat_ref"))
            ef = (sa - sr) / 100 * (cm - c_ref) if None not in (sr, sa, cm, c_ref) else (_num(m.get("efeito_pp")) or 0)
            mix_rows.append([_motivo_label(m.get("motivo")), f"{_bfmt(sr or 0)}%", f"{_bfmt(sa or 0)}%", pp(ef)])
        text(sl, 0.5, 2.6, 6.0, 0.4, "Performance por motivo", size=13, bold=True)
        if len(perf_rows) > 1:
            table(sl, 0.5, 3.0, 6.0, perf_rows, [2.7, 1.1, 1.1, 1.1])
        text(sl, 6.8, 2.6, 6.0, 0.4, "Mix de motivos", size=13, bold=True)
        if len(mix_rows) > 1:
            table(sl, 6.8, 3.0, 6.0, mix_rows, [2.4, 1.2, 1.2, 1.2])
        if c_ref is not None and c_cur is not None and perf is not None and mix is not None:
            if c_cur >= c_ref:
                lei = "O CSAT não caiu contra a referência."
            elif abs(mix) >= abs(c_cur - c_ref) * MIX_DOMINANT_SHARE:
                lei = "A queda vem do mix: chegou mais contato de motivo com CSAT naturalmente menor."
            else:
                lei = f"A queda vem do atendimento (performance {pp(perf)} p.p.): é o que a EPS precisa atacar."
            text(sl, 0.5, 6.5, 12.3, 0.6, lei, size=15, bold=True, color=DECK_RED)

    # 3. o que cobrar
    sl = prs.slides.add_slide(blank)
    header(sl, "Próximos passos", "o que cobrar da operação e o que acompanhar")
    passos = []
    if c_m is not None and meta is not None and c_m < meta:
        passos.append(f"Plano para fechar {_bfmt(meta - c_m)} p.p. de gap no mês: ação · responsável · prazo.")
    top_p = sorted([m for m in (var.get("top_performance") or []) if isinstance(m, dict)],
                   key=lambda m: _num(m.get("efeito_pp")) or 0)[:2] if var else []
    for m in top_p:
        if (_num(m.get("efeito_pp")) or 0) < 0:
            passos.append(f"Atacar o atendimento de {_motivo_label(m.get('motivo'))}: CSAT "
                          f"{_bfmt(_num(m.get('csat_ref')) or 0)}% → {_bfmt(_num(m.get('csat_atual')) or 0)}%.")
    passos.append("Esteira de impacto por pilar (operador, tempo, política, parceiro, produto): peça à Lyra na thread.")
    text(sl, 0.5, 1.6, 12.3, 5.0, ["• " + p for p in passos], size=16)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _send_deck(event: dict[str, Any], client: Any, eps: str | None, question: str,
               send_progress: Callable[[str], Any] | None = None) -> str | None:
    fila = _fila_ref(question, eps, event)
    if not fila:
        return ("Monto sim! Me diz de qual fila (ex.: Review, Suporte, Super Cliente) que eu trago resultado do mês, "
                "movimentos de mix e performance e o que cobrar, em pptx.")
    try:
        rows = _day_table() or []
    except Exception:
        rows = []
    row = next((r for r in rows if r.get("fila") == fila), None)
    conj = [r for r in rows if row and r.get("eps") == row.get("eps")]
    data = _deck_data(event, eps, fila, send_progress)
    if not row and not data.get("var"):
        return "Não consegui puxar os dados da fila agora. Tenta de novo em alguns minutos?"
    try:
        pptx_bytes = _build_deck(fila, eps or (row or {}).get("eps"), row, conj, data.get("var") or {},
                                 data.get("png"), data["labels"])
    except Exception:
        logger.exception("Deck build failed")
        return "Montei os dados, mas o arquivo falhou na geração. Já avisei o time."
    nome = re.sub(r"[^\w\-]+", "_", f"Lyra_{fila}_{_now_brazil().strftime('%d-%m')}")[:60] + ".pptx"
    (client or slack_app.client).files_upload_v2(
        channel=event.get("channel"), thread_ts=_reply_ts(event), content=pptx_bytes, filename=nome,
        title=f"{fila} · resultado e movimentos",
        initial_comment=f"📎 Material de `{fila}`: resultado do mês, mix x performance por motivo e próximos passos.")
    return None


_DATA_EXCEL_RE = re.compile(r"\b(excel|xls|xlsx|planilha|csv|tabela em arquivo|arquivo)\b")


def _is_data_excel_request(question: str) -> bool:
    """Pedido de dados em planilha (ex.: "manda o CSAT por fila em excel"). MOP e operadores têm fluxo próprio."""
    text = _norm_text(question)
    asks = re.search(r"\b(manda|mande|envia|envie|gera|gere|gerar|exporta|exporte|exportar|extrai|extraia|"
                     r"quero|queria|preciso|passa|passe|baixar|tira|tire|monta|monte|montar|coloca|coloque|colocar|pode|consegue|em|numa|num)\b", text)
    return bool(_DATA_EXCEL_RE.search(text) and asks) and not re.search(r"\bmop\b", text)


def _data_excel_prompt(eps: str | None, question: str, context: str) -> str:
    return (
        f"{_scope_instruction(eps)}\n\n{context}"
        "TAREFA INTERNA DO APP — a pessoa pediu os dados em planilha. Busque os dados com o subagente certo "
        "(Lyra Indicadores para números; Lyra Qualidade para causa raiz/comentários) e responda APENAS:\n"
        "ARQUIVO: <nome curto do arquivo, sem extensão>\n"
        "<CSV separado por ';', com cabeçalho em linguagem de negócio (sem nome de coluna técnica), uma linha por registro, "
        "números com ponto decimal e sem símbolo de %>\n"
        "Nada além disso (sem markdown, sem comentário). Respeite o escopo da EPS. Nunca dado pessoal de cliente. "
        "E-mail de operador só se a pessoa pedir lista de operadores, e só da EPS do canal. "
        "Se não der para consultar, responda só ERRO: <motivo>.\n\n"
        f"Pedido: {question}"
    )


def _build_data_xlsx(header: list[str], rows: list[list[str]], title: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = (title or "Dados")[:31]
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="EA1D2C")
    for r in rows:
        ws.append([(_to_float(v) if _to_float(v) is not None and re.fullmatch(r"-?[\d.,]+", v.strip()) else v) for v in r])
    for i, name in enumerate(header, start=1):
        width = max([len(str(name))] + [len(str(r[i - 1])) for r in rows if len(r) >= i]) + 2
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(max(width, 10), 50)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _parse_data_csv(answer: str) -> tuple[str, list[str], list[list[str]]] | None:
    text = _strip_json_code_blocks(answer or "").strip().strip("`")
    name = "Dados"
    lines = [l for l in text.splitlines() if l.strip()]
    if lines and lines[0].upper().startswith("ARQUIVO:"):
        name = lines.pop(0).split(":", 1)[1].strip() or name
    lines = [l for l in lines if ";" in l]
    if len(lines) < 2:
        return None
    header = [h.strip() for h in lines[0].split(";")]
    rows = [[c.strip() for c in l.split(";")] for l in lines[1:]]
    rows = [r + [""] * (len(header) - len(r)) for r in rows]
    return name, header, rows


def _send_data_excel(event: dict[str, Any], client: Any, eps: str | None, question: str) -> str | None:
    answer = ask_toqan(_data_excel_prompt(eps, question, _thread_context(event)))
    if _is_error_answer(answer):
        return "Não consegui puxar esses dados agora. Tenta de novo em alguns minutos?"
    parsed = _parse_data_csv(answer)
    if not parsed:
        return "Não consegui montar a planilha com esse pedido. Me diz quais colunas você quer (ex.: fila, CSAT, meta, TMA)."
    name, header, rows = parsed
    if eps:  # trava: e-mail de operador só da EPS do canal
        rows = [r for r in rows if not any("@" in c and _eps_pattern(eps) not in c.lower() for c in r)]
    safe = re.sub(r"[^\w\- ]+", "", name).strip().replace(" ", "_") or "Dados"
    stamp = _now_brazil().strftime("%d-%m-%Y")
    (client or slack_app.client).files_upload_v2(
        channel=event.get("channel"),
        thread_ts=_reply_ts(event),
        content=_build_data_xlsx(header, rows, name),
        filename=f"{safe}{('_' + eps) if eps else ''}_{stamp}.xlsx",
        title=name,
        initial_comment=f"Segue a planilha 📋 ({len(rows)} linha{'s' if len(rows) != 1 else ''})",
    )
    return None


def _build_operators_xlsx(rows: list[list[str]], eps: str | None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    def num(value: str) -> float | str:
        f = _to_float(value)
        return f if f is not None else value

    wb = Workbook()
    ws = wb.active
    ws.title = f"Operadores {eps}" if eps else "Operadores"
    header = ["E-mail", "Fila", "Avaliações", "Promotores", "CSAT (%)", "Meta (%)", "Atingimento (%)", "Quadrante"]
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="EA1D2C")
    fills = {"Q1": "C6EFCE", "Q2": "E2F0D9", "Q3": "FFF2CC", "Q4": "F8CBAD"}
    order = {"Q4": 0, "Q3": 1, "Q2": 2, "Q1": 3}
    rows = sorted(rows, key=lambda r: (order.get(r[7].upper(), 9), _to_float(r[6]) or 0))
    for r in rows:
        ws.append([r[0], r[1], num(r[2]), num(r[3]), num(r[4]), num(r[5]), num(r[6]), r[7].upper()])
        q = r[7].upper()
        if q in fills:
            ws.cell(row=ws.max_row, column=8).fill = PatternFill("solid", fgColor=fills[q])
    for col, width in zip("ABCDEFGH", (38, 26, 11, 11, 10, 10, 15, 11)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _operators_rows(eps: str | None, question: str) -> tuple[list[list[str]], int | None, str, str | None] | str:
    """Base de operadores do período pedido: (linhas, total, rótulo do período, EPS usada) ou texto de erro."""
    period, period_label = _operators_period(question)
    if eps is None:
        eps = _eps_of_question(question)  # visão completa pedindo uma EPS (ou fila): recorta nela
    if eps is None:
        # visão iFood sem EPS: a base das duas juntas é grande demais para uma resposta só; busca uma por vez e junta
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(EPS_CELULAS)) as pool:
            answers = list(pool.map(lambda e: (e, _ask_base(_operators_prompt(e, period))), list(EPS_CELULAS)))
        rows, total = [], 0
        for e, ans in answers:
            if _is_error_answer(ans):
                _alert(f"Base de operadores ({e}) falhou: {str(ans)[:200]}")
                continue
            r, t = _parse_operators_csv(ans)
            rows += [x for x in r if _eps_pattern(e) in x[0].lower()]
            total += t or len(r)
        if not rows:
            return "Não consegui puxar os dados dos operadores agora. Tenta de novo em alguns minutos?"
    else:
        answer = _ask_base(_operators_prompt(eps, period))
        if _is_error_answer(answer):
            _alert(f"Base de operadores ({eps}) falhou: {str(answer)[:200]}")
            return "Não consegui puxar os dados dos operadores agora. Tenta de novo em alguns minutos?"
        rows, total = _parse_operators_csv(answer)
        if not rows:
            _alert_unreadable("Base de operadores", eps, answer)
            return "Não consegui montar a base dos operadores agora. Tenta de novo em alguns minutos?"
    if eps:
        rows = [r for r in rows if _eps_pattern(eps) in r[0].lower()]  # trava: só e-mails da EPS
    fila = _fila_in_question(question, eps)
    if fila:
        rows = [r for r in rows if _norm_text(r[1]) == _norm_text(fila)]
    return rows, total, period_label, eps


def _upload_operators_xlsx(event: dict[str, Any], client: Any, rows: list[list[str]], eps: str | None,
                           period_label: str, comment: str) -> None:
    stamp = _now_brazil().strftime("%d-%m-%Y")
    who = f" da {eps}" if eps else ""
    (client or slack_app.client).files_upload_v2(
        channel=event.get("channel"),
        thread_ts=_reply_ts(event),
        content=_build_operators_xlsx(rows, eps),
        filename=f"Operadores{('_' + eps) if eps else ''}_{stamp}.xlsx",
        title=f"Operadores{who} — CSAT e quadrante {period_label}",
        initial_comment=comment,
    )


def _send_operators_excel(event: dict[str, Any], client: Any, eps: str | None, question: str = "") -> str | None:
    """Pede a base ao agente, monta o Excel e posta na thread. Devolve texto se não deu."""
    got = _operators_rows(eps, question)
    if isinstance(got, str):
        return got
    rows, total, period_label, eps = got
    if not rows:
        return "Não achei operadores com avaliações suficientes nesse recorte."
    who = f" da {eps}" if eps else ""
    note = f" (vieram {len(rows)} de {total} — a lista pode estar incompleta)" if total and total > len(rows) else ""
    _upload_operators_xlsx(event, client, rows, eps, period_label,
                           f"Segue a planilha dos operadores{who} com CSAT e quadrante {period_label} 📋{note}")
    return None


OPERATORS_INLINE_MAX = 15
OPERATORS_INLINE_DEFAULT = 10
_OFFENDERS_RE = re.compile(r"\b(ofensor|ofensores|piores|q4|detrator|detratores)\b")


def _send_operators_inline(event: dict[str, Any], client: Any, eps: str | None, question: str,
                           say: Callable[..., Any], in_thread: bool) -> str | None:
    """Visão completa (e-mail iFood / canal interno): resultado por operador direto no chat. "Ofensores" = Q4,
    do pior para o melhor. Mais de 15 linhas: mostra as 15 piores e manda a planilha completa junto."""
    got = _operators_rows(eps, question)
    if isinstance(got, str):
        return got
    rows, _, period_label, eps = got
    fila = _fila_in_question(question, eps)
    qtext = _norm_text(question)
    offenders = bool(_OFFENDERS_RE.search(qtext))
    by_impact = "impacto" in qtext
    best = bool(re.search(r"\bmelhores\b", qtext)) and not offenders

    def impact(r: list[str]) -> float:  # avaliações abaixo do que a meta pedia: quanto o operador puxa a fila
        aval, csat, meta = _to_float(r[2]) or 0, _to_float(r[4]), _to_float(r[5])
        return aval * (meta - csat) / 100 if csat is not None and meta is not None else 0

    if by_impact:
        data = sorted(rows, key=lambda r: -impact(r))
        data = [r for r in data if impact(r) > 0]
    else:
        data = sorted(rows, key=lambda r: (_to_float(r[6]) if _to_float(r[6]) is not None else 999,
                                           -(_to_float(r[2]) or 0)), reverse=False)
        if best:
            data = list(reversed(data))
    if offenders:
        data = [r for r in data if str(r[7]).strip().upper() == "Q4"]
    mtop = re.search(r"\btop (\d{1,2})\b", qtext)
    limit = min(int(mtop.group(1)), OPERATORS_INLINE_MAX) if mtop else OPERATORS_INLINE_DEFAULT
    where = fila or eps or "todas as filas"
    when = _period_spec(question)["short"]
    label = ("Maior impacto no CSAT" if by_impact else "Ofensores de CSAT" if offenders
             else "Melhores em CSAT" if best else "CSAT por operador")
    emoji = "🏆" if best else ("🔴" if (offenders or by_impact) and data else "👤")
    head = f"{emoji} *{label} ·* `{where}` *— {when}*"
    if not data:
        return f"{head}\nNinguém no Q4 nesse recorte (abaixo de 90% da meta, com avaliações suficientes). 👏"
    head += f" · {len(data)} operador{'es' if len(data) != 1 else ''}"
    try:
        names = _operator_name_map()
    except Exception:
        names = {}
    lines = []
    for i, r in enumerate(data[:limit], 1):
        nome = names.get(r[0].lower()) or names.get(r[0].split("@")[0])
        csat, ating = _to_float(r[4]), _to_float(r[6])
        parts = [f"{i}. {_operator_label(r[0], nome or '')}"]
        if not fila:
            parts.append(r[1])
        parts.append(f"*{_bfmt(csat) if csat is not None else r[4]}%* ({r[3]}/{r[2]})")
        if by_impact:
            parts.append(f"impacto {_bfmt(impact(r))} aval.")
        else:
            parts.append(f"{_bfmt(ating, 0) if ating is not None else r[6]}% da meta")
        if not offenders:
            parts.append(str(r[7]).upper())
        lines.append(" · ".join(parts))
    rule = ("impacto = avaliações abaixo do que a meta pedia" if by_impact
            else "Q4 = abaixo de 90% da meta da fila" if offenders
            else "do maior para o menor atingimento" if best else "do menor para o maior atingimento")
    rule += f" · mínimo de {_period_spec(question)['min']} avaliações"
    text = f"{head}\n_{rule}_\n\n" + "\n".join(lines)
    if len(data) > limit:
        text += f"\n\n_…e mais {len(data) - limit} na planilha abaixo 📋_"
    _say_sections(say, text, event)
    if len(data) > limit:
        _upload_operators_xlsx(event, client, data, eps, period_label, "Lista completa 📋")
    return None


# --- Visual das respostas grandes (mesmo molde do report diário) + cache das bases ---------------------------
# Molde: título "<status> *<Rótulo> ·* `<fila/EPS>` *— <período>* · <número principal>"; seções separadas por linha
# em branco (viram divisórias); cabeçalhos 📍 resultado · 👥 quebra · 👤 operadores · 💡 Leitura; linhas curtas com o
# valor em negrito e "→ 🔴/🟢"; lista longa vai para a planilha.
_NAME_PARTICLES = {"da", "de", "do", "das", "dos", "e"}


def _nice_name(name: str) -> str:
    """ARTHUR FERNANDES NOBRE -> Arthur Fernandes Nobre (nome já em caixa mista fica como está)."""
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not name or not (name.isupper() or name.islower()):
        return name
    return " ".join(w.lower() if i and w.lower() in _NAME_PARTICLES else w.capitalize()
                    for i, w in enumerate(name.split(" ")))


def _status_dot(ating: float | None) -> str:
    return "⚪" if ating is None else ("🟢" if ating >= 100 else "🔴")


def _vs_meta(value: float, meta: float | None) -> str:
    if meta is None:
        return "⚪ sem meta"
    if value < meta:
        return f"🔴 {_bfmt(meta - value)} p.p. abaixo da meta {_bfmt(meta)}%"
    return "🟢 na meta" if abs(value - meta) < 0.05 else f"🟢 {_bfmt(value - meta)} p.p. acima da meta {_bfmt(meta)}%"


_BASE_CACHE: dict[str, tuple[float, str]] = {}
_BASE_INFLIGHT: dict[str, threading.Event] = {}
_BASE_LOCK = threading.Lock()


def _ask_cached(prompt: str, ttl_seconds: float | None = None) -> str:
    """Pergunta ao Toqan reaproveitando a resposta: as bases fecham no D-1, então valem o dia todo (ttl None = até a
    meia-noite). Duas pessoas pedindo a mesma base ao mesmo tempo: a segunda espera a primeira (uma consulta só)."""
    key = f"{_as_date(_today_brazil()).isoformat()}|{hash(prompt)}"
    while True:
        with _BASE_LOCK:
            hit = _BASE_CACHE.get(key)
            if hit and hit[0] > time.time():
                return hit[1]
            waiter = _BASE_INFLIGHT.get(key)
            if waiter is None:
                _BASE_INFLIGHT[key] = threading.Event()
                break
        waiter.wait(timeout=POLL_INTERVAL_SECONDS * MAX_POLL_ATTEMPTS + 120)
        with _BASE_LOCK:
            hit = _BASE_CACHE.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
        # a primeira falhou: esta tenta por conta própria
        with _BASE_LOCK:
            if key not in _BASE_INFLIGHT:
                _BASE_INFLIGHT[key] = threading.Event()
                break
    try:
        answer = ask_toqan(prompt)
        if not _is_error_answer(answer):
            if ttl_seconds is None:
                now = _now_brazil()
                midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                ttl_seconds = max(60.0, (midnight - now).total_seconds())
            with _BASE_LOCK:
                _BASE_CACHE[key] = (time.time() + ttl_seconds, answer)
                for k in [k for k, v in _BASE_CACHE.items() if v[0] <= time.time()]:
                    _BASE_CACHE.pop(k, None)
        return answer
    finally:
        with _BASE_LOCK:
            ev = _BASE_INFLIGHT.pop(key, None)
        if ev:
            ev.set()


class _Progress:
    """Uma mensagem só de andamento na thread: a primeira é postada, as seguintes editam a mesma, e ela some quando a
    resposta chega (thread limpa: pergunta → resposta)."""

    def __init__(self, event: dict[str, Any]):
        self.event = event
        self.ts: str | None = None

    def __call__(self, text: str) -> None:
        channel = str(self.event.get("channel") or "")
        try:
            if self.ts:
                slack_app.client.chat_update(channel=channel, ts=self.ts, text=text)
                return
            resp = slack_app.client.chat_postMessage(channel=channel, thread_ts=_reply_ts(self.event), text=text)
            self.ts = _resp_get(resp, "ts")
        except Exception:
            logger.warning("Progress message failed", exc_info=True)

    def done(self) -> None:
        if not self.ts:
            return
        try:
            slack_app.client.chat_delete(channel=str(self.event.get("channel") or ""), ts=self.ts)
        except Exception:
            logger.info("Could not delete progress message", exc_info=True)
        self.ts = None


_ANALYTIC_RE = re.compile(
    r"\b(por ?que|pq|contribu\w*|explica\w*|o que (aconteceu|houve|mudou)|causa\w*|piorou|piora|piorar|melhorou|"
    r"melhora|melhorar|caiu|cair|subiu|queda|variacao|variou|evolucao|evoluiu|impactou|puxou|puxando|influenci\w*|"
    r"diferenca|correlac\w*|relacao|tendencia)\b")


def _is_analytical(question: str) -> bool:
    """Pergunta de análise (por que, quem piorou, quanto contribuiu...): vai para a análise livre, não para as listas
    prontas, mesmo citando supervisor ou operador."""
    return bool(_ANALYTIC_RE.search(_norm_text(question)))


# --- Visão de equipe (supervisor / coordenador) -------------------------------------------------------------
# Regras do Cockpit (aba Operadores): soma antes de dividir; quadrante pelo atingimento (Q1 ≥ 100% · Q2 95–99,99% ·
# Q3 90–94,99% · Q4 < 90%); abaixo de 10 pesquisas = amostra pequena; positivas faltantes = promotoras que faltaram
# para a meta; dispersão = CSAT do Q4 ÷ CSAT do Q1; limite de controle = CSAT da célula − 1,96 × erro padrão.
_TEAM_RE = re.compile(
    r"\b(minha|meu|nossa|nosso) (equipe|time|coordenacao|operacao|celula)\b|\bmeus (operadores|analistas|atendentes)\b"
    r"|\b(equipe|time|coordenacao) (d[aeo]s?|da supervisora|do supervisor|do coordenador|da coordenadora) \w"
    r"|\b(resultado|csat|desempenho) d[ao]s? (coordenacao|supervisora?|coordenadora?|equipe)\b"
    r"|\bpor supervisor\b|\bpor coordenador\b|\b(supervisores|coordenadores)\b|\bpositivas faltantes\b")
TEAM_SMALL_SAMPLE = 10
TEAM_LIST_MAX = 10
TEAM_SUP_MAX = 8
TEAM_OPS_MAX = 8


def _is_question_like(text: str) -> bool:
    """Pedido/pergunta (e não um plano de ação escrito na thread do report)."""
    t = _norm_text(text)
    return "?" in text or bool(re.match(r"(qual|quais|quem|como|quanto|me (manda|mostra|traz|passa|envia)|manda|mostra|"
                                        r"traz|traga|envia|resultado|preciso|quero|lista|ranking|top)\b", t))


def _is_team_request(question: str) -> bool:
    return bool(_TEAM_RE.search(_norm_text(question)))


def _mop_people(eps: str | None) -> dict[str, dict[str, str]]:
    """e-mail -> {nome, supervisor, coordenador, celula} do MOP (só a EPS do escopo)."""
    values = _read_mop_values() or []
    if len(values) < 2:
        return {}
    header = values[0]
    cols = {k: _find_col(header, k) for k in ("Nome", "Email", "Supervisor", "Coordenador", "Célula", "EPS")}
    people: dict[str, dict[str, str]] = {}
    for row in values[1:]:
        def cell(k: str) -> str:
            i = cols[k]
            return str(row[i]).strip() if i is not None and i < len(row) else ""
        email = cell("Email").lower()
        if "@" not in email:
            continue
        if eps and not _eps_matches(_row_eps(row, cols["EPS"], cols["Email"]), eps):
            continue
        people[email] = {"nome": cell("Nome"), "supervisor": cell("Supervisor"), "coordenador": cell("Coordenador"),
                         "celula": cell("Célula"), "eps": _row_eps(row, cols["EPS"], cols["Email"])}
    return people


def _name_hit(name: str, text: str) -> bool:
    """O nome (ou pelo menos 2 partes dele) aparece no texto."""
    parts = [p for p in re.findall(r"[a-z0-9]+", _norm_text(name)) if len(p) >= 3 or p.isdigit()]
    if not parts:
        return False
    words = set(re.findall(r"[a-z0-9]+", _norm_text(text)))
    hits = sum(1 for p in parts if p in words)
    return hits >= (len(parts) if len(parts) <= 2 else 2)


def _resolve_team(question: str, event: dict[str, Any], people: dict[str, dict[str, str]]) -> tuple[str, str | None]:
    """('sup', nome) | ('coord', nome) | ('all', None) | ('none', None)."""
    sups = {p["supervisor"] for p in people.values() if p["supervisor"]}
    coords = {p["coordenador"] for p in people.values() if p["coordenador"]}
    for kind, names in (("sup", sups), ("coord", coords)):
        named = [n for n in names if _name_hit(n, question)]
        if named:
            return kind, max(named, key=len)
    text = _norm_text(question)
    if re.search(r"\b(minha|meu|nossa|nosso|meus)\b", text):
        me = ""
        try:
            info = slack_app.client.users_info(user=str(event.get("user") or ""))
            u = info.get("user") or {}
            email = str((u.get("profile") or {}).get("email") or "").lower()
            me = (people.get(email) or {}).get("nome") or u.get("real_name") or (u.get("profile") or {}).get("real_name") or ""
        except Exception:
            logger.warning("Team view: could not identify asker", exc_info=True)
        if me:
            for kind, names in (("coord", coords), ("sup", sups)):
                own = [n for n in names if _norm_text(n) == _norm_text(me) or _name_hit(n, me)]
                if own:
                    return kind, own[0]
        return "none", None
    return "all", None


def _team_stats(rows: list[list[str]]) -> dict[str, Any]:
    ops = []
    for r in rows:
        aval, prom, meta = _to_float(r[2]) or 0, _to_float(r[3]) or 0, _to_float(r[5])
        if aval <= 0 or meta is None:
            continue
        csat = prom / aval * 100
        ating = csat / meta * 100 if meta else 0
        quad = "Q1" if ating >= 100 else "Q2" if ating >= 95 else "Q3" if ating >= 90 else "Q4"
        falt = max(0, math.ceil(meta / 100 * aval - prom - 1e-9))
        ops.append({"row": r, "aval": aval, "prom": prom, "meta": meta, "csat": csat, "ating": ating, "quad": quad,
                    "falt": falt, "det": aval - prom, "small": aval < TEAM_SMALL_SAMPLE})
    if not ops:
        return {}
    aval = sum(o["aval"] for o in ops)
    prom = sum(o["prom"] for o in ops)
    meta = sum(o["aval"] * o["meta"] for o in ops) / aval
    big = [o for o in ops if not o["small"]]
    q = {k: [o for o in big if o["quad"] == k] for k in ("Q1", "Q2", "Q3", "Q4")}

    def agg(group: list[dict[str, Any]]) -> float | None:
        a = sum(o["aval"] for o in group)
        return sum(o["prom"] for o in group) / a * 100 if a else None

    q1, q4 = agg(q["Q1"]), agg(q["Q4"])
    csats = sorted(o["csat"] for o in big)
    amp = (csats[int(0.9 * (len(csats) - 1))] - csats[int(0.1 * (len(csats) - 1))]) if len(csats) >= 5 else None
    # limite de controle: contra a célula (fila) do operador, com todos os operadores da base
    cell_rate: dict[str, float] = {}
    for fila in {o["row"][1] for o in ops}:
        g = [o for o in ops if o["row"][1] == fila]
        cell_rate[fila] = sum(o["prom"] for o in g) / sum(o["aval"] for o in g)
    below = []
    for o in ops:
        p = cell_rate.get(o["row"][1], 0)
        if o["aval"] >= 5 and 0 < p < 1:
            lower = p - 1.96 * math.sqrt(p * (1 - p) / o["aval"])
            if o["prom"] / o["aval"] < lower:
                below.append(o)
    det_total = sum(o["det"] for o in ops)
    pareto = {}
    if det_total > 0:
        acc, n = 0.0, 0
        for o in sorted(ops, key=lambda o: -o["det"]):
            acc += o["det"]
            n += 1
            for cut in (50, 80):
                if cut not in pareto and acc / det_total * 100 >= cut:
                    pareto[cut] = n / len(ops) * 100
    return {"ops": ops, "aval": aval, "prom": prom, "csat": prom / aval * 100, "meta": meta,
            "ating": prom / aval * 100 / meta * 100 if meta else 0, "falt": sum(o["falt"] for o in ops),
            "quads": {k: len(v) for k, v in q.items()}, "small": len(ops) - len(big),
            "disp": (q4 / q1) if q1 and q4 is not None else None, "amp": amp, "below": below, "pareto": pareto}


_SQL_RETRY_RE = re.compile(r"(table_or_view_not_found|not found|syntax|parse|unresolved|cannot resolve|ambiguous|"
                           r"nao foi encontrad|invalid|unrecognized)", re.I)


def _ask_base(prompt: str) -> str:
    """Base pesada (operadores, semanas, tabela do dia): se a consulta voltar com erro de SQL (tabela/CTE não
    encontrada, sintaxe), tenta mais uma vez pedindo o SQL numa instrução só. Erro de token/acesso não repete."""
    answer = _ask_cached(prompt)
    if not _is_error_answer(answer) or _looks_like_token_error(answer) or not _SQL_RETRY_RE.search(str(answer)):
        return answer
    logger.warning("Base query SQL error, retrying once: %s", str(answer)[:200])
    retry = (prompt + "\n\nA tentativa anterior falhou com: " + str(answer).strip()[:300] + "\nRode o SQL como UMA "
             "instrução só (WITH ... SELECT ...) num único comando, sem criar nem referenciar tabela/view temporária e "
             "sem dividir em etapas; cada CTE precisa estar no mesmo WITH em que é usada.")
    second = _ask_cached(retry)
    return second


def _cached_only(prompt: str) -> str | None:
    key = f"{_as_date(_today_brazil()).isoformat()}|{hash(prompt)}"
    with _BASE_LOCK:
        hit = _BASE_CACHE.get(key)
    return hit[1] if hit and hit[0] > time.time() else None


def _fetch_operator_rows(eps: str | None, period: str, emails: list[str] | None = None) -> list[list[str]] | None:
    """Base de operadores do período. Com `emails` (equipe de um supervisor/coordenador): usa a base inteira da EPS se
    ela já estiver em cache; senão pede só esses e-mails (consulta menor e mais rápida)."""
    full = _operators_prompt(eps, f"{period}. Mínimo: 1 avaliação (o app marca amostra pequena).")
    answer = _cached_only(full) if emails else None
    if answer is None and emails:
        lista = ", ".join(sorted(emails)[:400])
        answer = _ask_base(_operators_prompt(eps, f"{period}. Mínimo: 1 avaliação (o app marca amostra pequena). "
                                                    f"Só estes operadores (e-mails): {lista}."))
    elif answer is None:
        answer = _ask_base(full)
    if _is_error_answer(answer):
        return None
    rows, _ = _parse_operators_csv(answer)
    if not rows:
        _alert_unreadable("Base de operadores", eps, answer)
        with _BASE_LOCK:
            for k in [k for k, v in _BASE_CACHE.items() if v[1] == answer]:
                _BASE_CACHE.pop(k, None)
    if eps:
        rows = [r for r in rows if _eps_pattern(eps) in r[0].lower()]
    return rows or None


WEEKS_HEADER = ["email", "fila", "meta", "s1_aval", "s1_prom", "s2_aval", "s2_prom", "s3_aval", "s3_prom",
                "s4_aval", "s4_prom"]
WEEK_MIN_AVAL = 5  # semana com menos de 5 pesquisas não conta (nem como Q4, nem como fora)


def _weeks_ranges() -> list[tuple[date, date]]:
    """As 4 últimas semanas fechadas no D-1: s1 = D-7..D-1, s2 = D-14..D-8, ..."""
    d1 = _as_date(_today_brazil()) - timedelta(days=1)
    return [(d1 - timedelta(days=7 * i + 6), d1 - timedelta(days=7 * i)) for i in range(4)]


def _weeks_prompt(eps: str | None) -> str:
    rng = _weeks_ranges()
    sem = "; ".join(f"s{i + 1} = {a.strftime('%d/%m/%Y')} a {b.strftime('%d/%m/%Y')}" for i, (a, b) in enumerate(rng))
    return (
        f"{_scope_instruction(eps)}\n\n"
        "TAREFA INTERNA DO APP — base de operadores por semana. Não é mensagem para o Slack.\n"
        "Se você usa subagentes, peça ao subagente de indicadores com "
        f"'EPS: {eps or 'iFood'}', 'Pedido: base de operadores por semana (CSV)' e 'Semanas: {sem}'.\n"
        f"Semanas (pela data de abertura do caso): {sem}. Só filas da lista oficial da EPS. Uma consulta só, agrupada "
        "por operador (use o SQL da seção 8.4b). Só operadores no Q4 (CSAT < 90% da meta da fila) em pelo menos 2 das 4 "
        "semanas, contando só semanas com 5+ avaliações (o filtro vai no SQL; a saída precisa ser pequena).\n"
        "Responda APENAS o CSV separado por ';', escrito no corpo da resposta (NUNCA salve em arquivo nem devolva nome de "
        "arquivo ou link), sem markdown e sem texto antes ou depois, com este cabeçalho:\n"
        f"{';'.join(WEEKS_HEADER)}\n"
        "meta = meta de CSAT da fila em %. sN_aval = avaliações na semana N; sN_prom = promotoras (notas 4 e 5). "
        "Semana sem avaliação: 0. Uma linha por operador. Última linha: TOTAL;<quantidade de operadores>\n"
        "Se a consulta falhar: responda só 'ERRO: <motivo>'."
    )


_WEEK_COL_RE = re.compile(r"^s(?:emana)?_?([1-4])_?(aval\w*|avaliac\w*|prom\w*)$")


def _parse_weeks_csv(answer: str, eps: str | None) -> dict[str, dict[str, Any]]:
    """Leitura tolerante: aceita ';', ',' ou tab, colunas em qualquer ordem (pelo nome), cercas de código, texto em
    volta, decimal com vírgula e também o formato longo (email;fila;meta;semana;aval;prom)."""
    import csv as _csv
    text = _strip_json_code_blocks(answer or "").replace("```", "")
    lines = [l for l in text.splitlines() if l.strip()]
    hdr_i = next((i for i, l in enumerate(lines) if "email" in l.lower() and re.search(r"aval", l.lower())), None)
    if hdr_i is None:
        return {}
    hdr_line = lines[hdr_i]
    delim = max((";", "\t", ","), key=hdr_line.count)
    rows = list(_csv.reader(io.StringIO("\n".join(lines[hdr_i:])), delimiter=delim))
    header = [_norm_text(c).replace(" ", "_") for c in rows[0]]
    idx = {h: i for i, h in enumerate(header)}
    col = lambda *names: next((idx[n] for n in names if n in idx), None)
    c_email, c_fila, c_meta = col("email", "e_mail", "operador_email"), col("fila"), col("meta")
    wide: dict[int, dict[str, int]] = {}
    for h, i in idx.items():
        m = _WEEK_COL_RE.match(h)
        if m:
            wide.setdefault(int(m.group(1)), {})["prom" if m.group(2).startswith("prom") else "aval"] = i
    c_sem, c_aval, c_prom = col("semana", "week", "sem"), col("aval", "avaliacoes"), col("prom", "promotoras", "promotores")
    if c_email is None or c_meta is None:
        return {}
    num = lambda v: _to_float(str(v).replace(",", ".")) if v not in (None, "") else None
    raw: dict[str, dict[str, Any]] = {}
    for r in rows[1:]:
        cells = [c.strip() for c in r]
        if len(cells) <= c_email or "@" not in cells[c_email]:
            continue
        email = cells[c_email].lower()
        if eps and _eps_pattern(eps) not in email:
            continue
        get = lambda i: cells[i] if i is not None and i < len(cells) else ""
        op = raw.setdefault(email, {"fila": get(c_fila), "meta": num(get(c_meta)), "w": {}})
        if wide:
            for w, cols in wide.items():
                op["w"][w] = (num(get(cols.get("aval"))) or 0, num(get(cols.get("prom"))) or 0)
        elif c_sem is not None and c_aval is not None and c_prom is not None:
            m = re.search(r"([1-4])", get(c_sem))
            if m:
                w = int(m.group(1))
                a0, p0 = op["w"].get(w, (0, 0))
                op["w"][w] = (a0 + (num(get(c_aval)) or 0), p0 + (num(get(c_prom)) or 0))
    out: dict[str, dict[str, Any]] = {}
    for email, op in raw.items():
        meta, q4, sampled, csats = op["meta"], 0, 0, []
        avals = [op["w"].get(w, (0, 0))[0] for w in range(1, 5)]
        proms = [op["w"].get(w, (0, 0))[1] for w in range(1, 5)]
        for w in range(1, 5):
            aval, prom = op["w"].get(w, (0, 0))
            if aval >= WEEK_MIN_AVAL and meta:
                c = prom / aval * 100
                csats.append(c)
                sampled += 1
                q4 += 1 if c / meta * 100 < 90 else 0
            else:
                csats.append(None)
        out[email] = {"q4": q4, "n": sampled, "csats": csats, "fila": op["fila"], "meta": meta, "avals": avals,
                      "proms": proms}
    return out


def _alert_unreadable(what: str, eps: str | None, answer: str | None) -> None:
    raw = str(answer or "").strip()
    masked = re.sub(r"[\w.+-]+@[\w.-]+", "<email>", raw)
    if re.fullmatch(r"[\w\-. /]+\.(csv|xlsx|txt|json)", raw.strip("` \n"), re.I):
        detail = f"o agente salvou um arquivo ({raw[:80]}) em vez de mandar o CSV na resposta"
    else:
        detail = f"início da resposta: {masked[:300] or '(vazia)'}"
    _alert(f"{what} ({eps or 'iFood'}): não li a resposta do agente — {detail}")


def _fetch_weekly_rows(eps: str | None) -> dict[str, dict[str, Any]] | None:
    """e-mail -> {q4: semanas no Q4, n: semanas com amostra, csats: CSAT s1..s4 (None sem amostra), fila}."""
    answer = _ask_base(_weeks_prompt(eps))
    if _is_error_answer(answer):
        _alert(f"Reincidentes 4 semanas ({eps or 'iFood'}): a consulta voltou com erro — {str(answer).strip()[:200]}")
        return None
    out = _parse_weeks_csv(answer, eps)
    if not out:
        _alert_unreadable("Reincidentes 4 semanas", eps, answer)
        with _BASE_LOCK:  # não guarda resposta ilegível no cache
            for k in [k for k, v in _BASE_CACHE.items() if v[1] == answer]:
                _BASE_CACHE.pop(k, None)
        return None
    return out


def _is_reincidentes_request(question: str) -> bool:
    text = _norm_text(question)
    return bool(re.search(r"\breincident\w*", text)) and bool(
        re.search(r"\b(operador|operadores|analista|analistas|atendente|atendentes|agentes|quem|quais|top|lista|mais)\b", text))


def _send_reincidentes(event: dict[str, Any], client: Any, eps: str | None, question: str,
                       say: Callable[..., Any], in_thread: bool) -> str | None:
    """Ranking de reincidência no Q4 nas 4 últimas semanas (semanas com 5+ pesquisas), por fila/EPS citada."""
    if eps is None:
        eps = _eps_of_question(question)
    weeks = _fetch_weekly_rows(eps)
    if not weeks:
        return "Não consegui puxar as últimas 4 semanas dos operadores agora. Tenta de novo em alguns minutos?"
    fila = _fila_in_question(question, eps)
    if fila:
        weeks = {e: w for e, w in weeks.items() if _norm_text(w["fila"]) == _norm_text(fila)}
    m = re.search(r"\b(\d{1,2})\b", _norm_text(question))
    limit = min(int(m.group(1)), OPERATORS_INLINE_MAX) if m and 0 < int(m.group(1)) <= 50 else OPERATORS_INLINE_DEFAULT
    ranked = sorted(((e, w) for e, w in weeks.items() if w["q4"] >= 2),
                    key=lambda x: (-x[1]["q4"], sum(c for c in x[1]["csats"] if c is not None) / max(1, x[1]["n"])))
    rng = _weeks_ranges()
    where = fila or eps or "todas as filas"
    full = sum(1 for _, w in ranked if w["q4"] == 4 and w["n"] == 4)
    head = f"🔁 *Reincidentes 4 semanas ·* `{where}` *— {_short_range(rng[-1][0], rng[0][1])}*"
    if not ranked:
        return f"{head}\nNinguém no Q4 em 2 ou mais das últimas 4 semanas (contando só semanas com 5+ pesquisas). 👏"
    head += f" · {full} no Q4 nas 4 semanas · {len(ranked)} em 2+"
    try:
        names = _operator_name_map() if _operator_names_allowed(eps) else {}
    except Exception:
        names = {}
    lines = []
    for i, (e, w) in enumerate(ranked[:limit], 1):
        serie = " → ".join(f"{_bfmt(c, 0)}%" if c is not None else "—" for c in reversed(w["csats"]))
        nome = names.get(e) or names.get(e.split("@")[0]) or ""
        who = _operator_label(e, nome) if _operator_names_allowed(eps) else e.split("@")[0]
        parts = [f"{i}. {who}"] + ([w["fila"]] if not fila and w.get("fila") else [])
        parts.append(f"Q4 em *{w['q4']} de {w['n']}* · {serie}")
        lines.append(" · ".join(parts))
    text = (f"{head}\n_Q4 = abaixo de 90% da meta da fila · só semanas com 5+ pesquisas · CSAT da semana mais antiga → "
            f"mais recente_\n\n" + "\n".join(lines))
    if len(ranked) > limit:
        text += f"\n\n_…e mais {len(ranked) - limit} no Q4 em 2+ semanas._"
    _say_sections(say, text, event)
    return None


def _send_team_view(event: dict[str, Any], client: Any, eps: str | None, question: str,
                    say: Callable[..., Any], in_thread: bool) -> str | None:
    """Resultado da equipe de um supervisor/coordenador (ou de todos os supervisores), com Δ vs período anterior."""
    if eps is None:
        eps = _eps_of_question(question)
    people = _mop_people(eps)
    if not people:
        return "Não consegui ler o MOP para montar as equipes agora. Tenta de novo em alguns minutos?"
    kind, leader = _resolve_team(question, event, people)
    if kind == "none":
        return ("Não achei você como supervisor(a) ou coordenador(a) no MOP. Me diz de quem é a equipe "
                "(ex.: \"resultado da equipe da Supervisora 3\").")
    if eps is None and kind in {"sup", "coord"}:  # equipe citada pelo nome: a EPS vem do MOP
        field = "supervisor" if kind == "sup" else "coordenador"
        team_eps = {p.get("eps") for p in people.values() if _norm_text(p[field]) == _norm_text(leader)} - {"", None}
        if len(team_eps) == 1:
            eps = team_eps.pop()
            people = {e: p for e, p in people.items() if _eps_matches(p.get("eps") or "", eps)}
    spec = _period_spec(question)
    results: dict[str, Any] = {}
    team_emails = None
    if kind in {"sup", "coord"}:
        field = "supervisor" if kind == "sup" else "coordenador"
        team_emails = [e for e, p in people.items() if _norm_text(p[field]) == _norm_text(leader)] or None

    def load(key: str, period: str) -> None:
        try:
            results[key] = _fetch_operator_rows(eps, period, team_emails)
        except Exception:
            logger.exception("Team view: operator base failed (%s)", key)
            results[key] = None

    def load_weeks() -> None:
        try:
            results["weeks"] = _fetch_weekly_rows(eps)
        except Exception:
            logger.exception("Team view: weekly base failed")
            results["weeks"] = None

    threads = [threading.Thread(target=load, args=(k, p)) for k, p in (("cur", spec["cur"]), ("prev", spec["prev"]))]
    threads.append(threading.Thread(target=load_weeks))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    cur, prev = results.get("cur"), results.get("prev") or []
    if not cur:
        return "Não consegui puxar o resultado dos operadores agora. Tenta de novo em alguns minutos?"

    def member(email: str) -> dict[str, str] | None:
        return people.get(email.lower())

    def in_team(email: str) -> bool:
        p = member(email)
        if not p:
            return False
        if kind == "sup":
            return _norm_text(p["supervisor"]) == _norm_text(leader)
        if kind == "coord":
            return _norm_text(p["coordenador"]) == _norm_text(leader)
        return True

    team = [r for r in cur if in_team(r[0])]
    if not team:
        return f"Não achei avaliações {spec['label']} para a equipe de {leader or 'ninguém'}. O MOP está atualizado?"
    st = _team_stats(team)
    st_prev = _team_stats([r for r in prev if in_team(r[0])]) if prev else {}
    names = {}
    try:
        names = _operator_name_map()
    except Exception:
        pass

    def who(r: list[str]) -> str:
        p = member(r[0]) or {}
        nome = p.get("nome") or names.get(r[0].lower()) or ""
        return _operator_label(r[0], nome if _operator_names_allowed(eps) else "")

    def dpp(a: float | None, b: float | None) -> str:
        if a is None or b is None:
            return ""
        d = a - b
        return f"{'▲' if d >= 0 else '▼'} {_bfmt(abs(d))} p.p."

    title = {"sup": f"Equipe de {_nice_name(leader or '')}", "coord": f"Coordenação de {_nice_name(leader or '')}"}.get(
        kind, "Supervisores")
    where = eps or "todas as EPSs"
    head = (f"{_status_dot(st['ating'])} *{title} ·* `{where}` *— {spec['short']}* · CSAT {_bfmt(st['csat'])}% "
            f"(meta {_bfmt(st['meta'])}%)")
    lines = [head, ""]

    # 📍 Resultado
    extra = [x for x in (dpp(st["csat"], st_prev.get("csat")) and f"{dpp(st['csat'], st_prev.get('csat'))} vs "
                         f"{spec['prev_label']}", f"n={_fmt_int(st['aval'])}") if x]
    lines.append(f"📍 *Resultado · {spec['short']}*")
    lines.append(f"• CSAT *{_bfmt(st['csat'])}%* → {_vs_meta(st['csat'], st['meta'])} ({' · '.join(extra)})")
    lines.append(f"• Positivas faltantes para a meta: *{_fmt_int(st['falt'])}*")
    qd = st["quads"]
    big = sum(qd.values())
    if big:
        q_txt = " · ".join(f"{k} {round(qd[k] / big * 100):d}%" for k in ("Q1", "Q2", "Q3", "Q4"))
        disp = f" · dispersão {_bfmt(st['disp'], 2)}" if st["disp"] is not None else ""
        lines.append(f"• Quadrantes: {q_txt}{disp}")

    # 👥 Por supervisor (coordenação ou todos)
    if kind in {"coord", "all"}:
        sups: dict[str, list[list[str]]] = {}
        for r in team:
            sups.setdefault((member(r[0]) or {}).get("supervisor") or "Sem supervisor no MOP", []).append(r)
        prev_by_sup: dict[str, list[list[str]]] = {}
        for r in prev:
            if in_team(r[0]):
                prev_by_sup.setdefault((member(r[0]) or {}).get("supervisor") or "Sem supervisor no MOP", []).append(r)
        table = []
        for sup, rs in sups.items():
            s_ = _team_stats(rs)
            sp = _team_stats(prev_by_sup.get(sup, [])) if prev_by_sup.get(sup) else {}
            if s_:
                table.append((s_["ating"], sup, s_, sp))
        table.sort(key=lambda t: t[0])
        lines += ["", "👥 *Por supervisor* — do maior gap para o menor"]
        for _, sup, s_, sp in table[:TEAM_SUP_MAX]:
            parts = [f"{_status_dot(s_['ating'])} {_nice_name(sup)}", f"*{_bfmt(s_['csat'])}%*",
                     f"{_bfmt(s_['ating'], 0)}% da meta"]
            d = dpp(s_["csat"], sp.get("csat"))
            if d:
                parts.append(d)
            parts.append(f"{_fmt_int(s_['falt'])} faltantes")
            lines.append(" · ".join(parts))
        if len(table) > TEAM_SUP_MAX:
            lines.append(f"_…e mais {len(table) - TEAM_SUP_MAX} supervisores na planilha 📋_")

    # 👤 Operadores para olhar primeiro (reincidentes 4 semanas, abaixo do limite de controle, Q4 com mais faltantes)
    weeks = results.get("weeks") or {}
    team_weeks = {e: w for e, w in weeks.items() if in_team(e)}
    rein4 = {e for e, w in team_weeks.items() if w["n"] == 4 and w["q4"] == 4}
    rein3 = sum(1 for w in team_weeks.values() if w["q4"] == 3)
    below = {o["row"][0].lower() for o in st["below"]}
    flagged = [o for o in st["ops"] if o["row"][0].lower() in rein4 or o["row"][0].lower() in below
               or (o["quad"] == "Q4" and not o["small"])]
    flagged.sort(key=lambda o: (o["row"][0].lower() not in rein4, o["row"][0].lower() not in below, -o["falt"]))
    if kind != "all" and flagged:
        lines += ["", "👤 *Operadores para olhar primeiro*"]
        for o in flagged[:TEAM_OPS_MAX]:
            e = o["row"][0].lower()
            tags = (["🔁 Q4 nas 4 semanas"] if e in rein4 else []) + (["⚠️ abaixo do limite"] if e in below else [])
            lines.append(" · ".join([f"• {who(o['row'])}", f"*{_bfmt(o['csat'])}%* ({_fmt_int(o['prom'])}/"
                                     f"{_fmt_int(o['aval'])})", f"faltam {_fmt_int(o['falt'])}"] + tags))
        if len(flagged) > TEAM_OPS_MAX:
            lines.append(f"_…e mais {len(flagged) - TEAM_OPS_MAX} na planilha 📋_")

    # 💡 Leitura
    leitura = []
    if st["pareto"].get(50):
        leitura.append(f"{_bfmt(st['pareto'][50], 0)}% dos operadores concentram metade das notas 1–3"
                       + (": o problema está concentrado, dá para atacar por nome." if st["pareto"][50] <= 30
                          else ": o problema está espalhado, é mais processo do que pessoa."))
    if st["below"]:
        leitura.append(f"{len(st['below'])} operador(es) abaixo do limite de controle: ruim de verdade, não é só amostra.")
    if rein4 or rein3:
        leitura.append(f"{len(rein4)} reincidente(s) 4 semanas no Q4" + (f" e {rein3} em 3 das 4" if rein3 else "") + ".")
    if kind == "all" and table:
        worst = table[0]
        leitura.append(f"Maior gap: {_nice_name(worst[1])}, com {_fmt_int(worst[2]['falt'])} positivas faltantes.")
    if st["small"]:
        leitura.append(f"{st['small']} operador(es) com amostra pequena (<{TEAM_SMALL_SAMPLE}) ficaram fora dos quadrantes.")
    if leitura:
        lines += ["", "💡 *Leitura*"] + [f"↳ {t}" for t in leitura]
    lines += ["", "_Quer ajuda para montar o plano da equipe? É só pedir aqui."
              + (" A base completa vai na planilha abaixo 📋_" if _operator_names_allowed(eps) else "_")]
    _say_sections(say, "\n".join(lines), event)
    if _operator_names_allowed(eps):
        _upload_operators_xlsx(event, client, team, eps, spec["label"], "Base completa da equipe 📋")
    return None


# ---------------------------------------------------------------------------
# Catálogo de consultas fixas. Pergunta recorrente (indicador × nível × período × tipo) vai por SQL pronto do app,
# com a conta feita aqui; pergunta nova vai para a análise livre, marcada como "feita na hora" e registrada: o formato
# que se repetir (3+ vezes em 14 dias) entra na lista semanal de candidatos ao catálogo.
# ---------------------------------------------------------------------------
CSAT_SQL_FIXO = os.getenv("CSAT_SQL_FIXO", "fallback").strip().lower()  # off | fallback | on (variação e motivos)
_CSAT_ROWS_CACHE: dict[str, tuple[float, list[dict[str, str]]]] = {}
_EMAIL_SAFE_RE = re.compile(r"[^a-z0-9@._+-]")
PESSOAS_OPS_MAX = 8
PESSOAS_SUP_MAX = 8
PESSOAS_MIN_AVAL = 5
PESSOAS_MIN_AVAL_D1 = 3
PESSOAS_SUP_MIN_AVAL = 30  # equipe com amostra menor não entra no ranking de supervisor (conta no consolidado)


def _query_text(nome: str) -> str | None:
    try:
        with open(os.path.join(os.path.dirname(CAPA_SQL_PATH), nome), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _csat_eps_params(eps: str | None) -> tuple[str, str]:
    """('AeC', 'CSU') no formato do eps_fila da base e o padrão do e-mail (aec|csu)."""
    nomes = ["AeC" if _compact(e) == "aec" else "CSU" for e in ([eps] if eps else ["AeC", "CSU"])]
    return ", ".join(f"'{n}'" for n in nomes), "|".join(_compact(n) for n in nomes)


def _csat_sql(nome: str, ini: date, fim: date, params: dict[str, str]) -> str | None:
    """Consulta fixa de CSAT: base oficial (csat_base.sql, com a Madrugada do MOP) + o template pedido, compactado."""
    tpl, base = _query_text(nome), _query_text("csat_base.sql")
    if not tpl or not base:
        return None
    mad = ", ".join(f"'{_EMAIL_SAFE_RE.sub('', e.lower())}'" for e in _madrugada_emails()) or "''"
    base = (base.replace("{base_inicio}", ini.isoformat()).replace("{base_fim}", fim.isoformat())
            .replace("{lista_madrugada}", mad))
    sql = tpl.replace("{base}", base)
    for k, v in params.items():
        sql = sql.replace("{" + k + "}", v)
    return _compact_sql(sql)


def _csat_fixed_rows(nome: str, ini: date, fim: date, params: dict[str, str], progress: Callable[[str], Any] | None,
                     rotulo: str) -> tuple[list[dict[str, str]] | None, str]:
    sql = _csat_sql(nome, ini, fim, params)
    if not sql:
        return None, "A consulta fixa de CSAT não está configurada (falta o SQL em queries/)."
    key = f"{nome}:{hash(sql)}"
    hit = _CSAT_ROWS_CACHE.get(key)
    if hit and time.time() - hit[0] < 1800:
        return hit[1], ""
    rows, problema = _run_app_sql(sql, progress, rotulo, acesso=nome in {"csat_operadores.sql", "csat_pessoas.sql"})
    if rows is not None:
        _CSAT_ROWS_CACHE[key] = (time.time(), rows)
    return rows, problema


# --- quem mais impacta: operador e supervisor ---------------------------------
_PESSOAS_RE = re.compile(r"\b(operador\w*|analista\w*|atendente\w*|supervisor\w*|supervisora\w*|coordenador\w*|"
                         r"equipes?|times)\b")
_PESSOAS_IMPACTO_RE = re.compile(r"\b(impact\w*|pesa\w*|puxa\w*|ofensor\w*|derrub\w*|contribu\w*|consolidado|"
                                 r"quem mais|maiores? gaps?|segura\w*|ajuda\w* mais)\b")


def _is_pessoas_impacto_request(question: str) -> bool:
    """"Quais operadores/supervisores mais impactam o CSAT (no consolidado)?" — TMA/SLA por analista seguem a rota deles."""
    t = _norm_text(question)
    if not (_PESSOAS_RE.search(t) and _PESSOAS_IMPACTO_RE.search(t)):
        return False
    if re.search(r"\b(tma|sla|primeira resposta|tempo)\b", t) and not re.search(r"\bcsat\b", t):
        return False
    return not re.search(r"\b(casos?|tickets?|motivos?)\b", t)


def _pessoas_impacto_calc(rows: list[dict[str, str]], eps_nome: str, fila: str | None, people: dict[str, dict[str, str]],
                          dia_meta: date, emails: set[str] | None = None) -> dict[str, Any] | None:
    """Impacto de cada operador no consolidado (régua do Cockpit aplicada à pessoa): peso dele nas avaliações do
    conjunto × (CSAT dele − meta da fila dele), somado nas filas em que atendeu, em p.p. Supervisor = soma dos dele.
    A soma de todos dá o gap do conjunto para a meta (menos o que é de e-mail fora da EPS)."""
    def mine(r: dict[str, str]) -> bool:
        return _compact(r.get("eps", "")) == _compact(eps_nome) and (fila is None or _norm_text(r.get("fila", "")) == _norm_text(fila))

    tot = [r for r in rows if r.get("email", "").upper() == "TOTAL" and mine(r)]
    n_tot = sum(_sql_num(r.get("avaliacoes")) or 0 for r in tot)
    p_tot = sum(_sql_num(r.get("promotoras")) or 0 for r in tot)
    if n_tot <= 0:
        return None
    com_meta = [(r, _meta_fila(r.get("fila", ""), dia_meta)) for r in tot]
    am = sum(_sql_num(r.get("avaliacoes")) or 0 for r, m in com_meta if m is not None)
    meta_cons = sum((_sql_num(r.get("avaliacoes")) or 0) * m for r, m in com_meta if m is not None) / am if am else None
    ops: dict[str, dict[str, Any]] = {}
    by_user = {e.split("@")[0]: e for e in people}
    for r in rows:
        email = r.get("email", "").strip().lower()
        if email and email != "total" and "@" not in email:  # veio só o usuário do e-mail: completa pelo MOP
            email = by_user.get(email, f"{email}@{_compact(eps_nome)}")
        if "@" not in email or not mine(r) or (emails is not None and email not in emails):
            continue
        a, p = _sql_num(r.get("avaliacoes")) or 0, _sql_num(r.get("promotoras")) or 0
        meta = _meta_fila(r.get("fila", ""), dia_meta)
        o = ops.setdefault(email, {"email": email, "aval": 0.0, "prom": 0.0, "acima": 0.0, "aval_meta": 0.0,
                                   "meta_x": 0.0, "filas": {}})
        o["aval"] += a
        o["prom"] += p
        o["filas"][r.get("fila", "")] = o["filas"].get(r.get("fila", ""), 0) + a
        if meta is not None:
            o["acima"] += p - meta / 100 * a  # positivas acima (+) ou abaixo (−) do que a meta pede
            o["aval_meta"] += a
            o["meta_x"] += meta * a
    if not ops:
        return None
    for o in ops.values():
        o["csat"] = o["prom"] / o["aval"] * 100 if o["aval"] else None
        o["meta"] = o["meta_x"] / o["aval_meta"] if o["aval_meta"] else None
        o["imp"] = o["acima"] / n_tot * 100 if o["aval_meta"] else None
        o["fila"] = max(o["filas"], key=o["filas"].get) if o["filas"] else ""
        p = people.get(o["email"]) or {}
        o["nome"], o["sup"] = p.get("nome", ""), p.get("supervisor") or "Sem supervisor no MOP"
    sups: dict[str, dict[str, Any]] = {}
    for o in ops.values():
        s = sups.setdefault(o["sup"], {"sup": o["sup"], "aval": 0.0, "prom": 0.0, "acima": 0.0, "aval_meta": 0.0,
                                       "meta_x": 0.0, "n_ops": 0})
        for k in ("aval", "prom", "acima", "aval_meta", "meta_x"):
            s[k] += o[k]
        s["n_ops"] += 1
    for s in sups.values():
        s["csat"] = s["prom"] / s["aval"] * 100 if s["aval"] else None
        s["meta"] = s["meta_x"] / s["aval_meta"] if s["aval_meta"] else None
        s["imp"] = s["acima"] / n_tot * 100 if s["aval_meta"] else None
    return {"n": n_tot, "csat": p_tot / n_tot * 100, "meta": meta_cons, "ops": list(ops.values()),
            "sups": list(sups.values())}


def _pessoas_sql_params(eps: str | None, fila: str | None, people: dict[str, dict[str, str]], dia_meta: date,
                        emails: set[str] | None, d1: bool) -> dict[str, str]:
    """Parâmetros do csat_pessoas.sql: metas das filas, vínculo operador → supervisor do MOP e recortes."""
    esc = lambda v: str(v).replace("'", "''")
    eps_lista, eps_like = _csat_eps_params(eps)
    metas = [(f, _meta_fila(f, dia_meta)) for f in FILA_GRUPO_META]
    metas_v = ", ".join(f"('{esc(f)}', {m:g})" for f, m in metas if m is not None) or "('__sem_meta__', 0)"
    por_sup: dict[str, list[str]] = {}
    for e, p in people.items():
        if emails is not None and e not in emails:
            continue
        u = _EMAIL_SAFE_RE.sub("", e.split("@")[0].lower())
        if u:
            por_sup.setdefault(p.get("supervisor") or "Sem supervisor no MOP", []).append(u)
    mop_v = ", ".join(f"('{esc(sup)}', '{'|'.join(sorted(us))}')" for sup, us in sorted(por_sup.items())) \
        or "('Sem supervisor no MOP', '')"
    return {"eps_lista": eps_lista, "eps_like": eps_like, "metas_values": metas_v, "mop_values": mop_v,
            "filtro_fila": f"fila_relatorio = '{esc(fila)}'" if fila else "1 = 1",
            "filtro_equipe": "mp.u IS NOT NULL" if emails is not None else "1 = 1",
            "min_aval": str(PESSOAS_MIN_AVAL_D1 if d1 else PESSOAS_MIN_AVAL), "top_ops": str(PESSOAS_OPS_MAX)}


def _pessoas_from_rows(rows: list[dict[str, str]], eps_nome: str, people: dict[str, dict[str, str]]) -> dict[str, Any] | None:
    """Monta o mesmo dicionário de _pessoas_impacto_calc a partir da saída agregada do csat_pessoas.sql."""
    mine = [r for r in rows if _compact(r.get("eps", "")) == _compact(eps_nome)]
    tot = next((r for r in mine if r.get("tipo", "").upper() == "TOTAL"), None)
    n = _sql_num(tot.get("avaliacoes")) if tot else None
    if not n:
        return None
    n_meta, meta_x = _sql_num(tot.get("aval meta")) or 0, _sql_num(tot.get("meta x")) or 0
    by_user = {e.split("@")[0]: e for e in people}

    def item(r: dict[str, str]) -> dict[str, Any]:
        a, p = _sql_num(r.get("avaliacoes")) or 0, _sql_num(r.get("promotoras")) or 0
        am, mx = _sql_num(r.get("aval meta")) or 0, _sql_num(r.get("meta x")) or 0
        return {"aval": a, "prom": p, "acima": _sql_num(r.get("acima")) or 0, "aval_meta": am,
                "csat": p / a * 100 if a else None, "meta": mx / am if am else None,
                "imp": _sql_num(r.get("impacto pp")) if am else None, "n_ops": int(_sql_num(r.get("n ops")) or 0)}

    ops, sups = [], []
    for r in mine:
        tipo = r.get("tipo", "").upper()
        if tipo == "OP":
            u = r.get("nome", "").strip().lower()
            email = by_user.get(u) or u  # fora do MOP: fica o usuário do e-mail
            o = item(r)
            o.update(email=email, fila=r.get("fila", ""), nome=(people.get(email) or {}).get("nome", ""),
                     sup=(people.get(email) or {}).get("supervisor") or "")
            ops.append(o)
        elif tipo == "SUP":
            s_ = item(r)
            s_["sup"] = r.get("nome", "") or "Sem supervisor no MOP"
            sups.append(s_)
    fora = next((int(_sql_num(r.get("n ops")) or 0) for r in mine if r.get("tipo", "").upper() == "FORA"), 0)
    sem_mop = [r.get("nome", "") for r in mine if r.get("tipo", "").upper() == "SEMMOP"]
    return {"sem_mop_ex": sem_mop, "n": n, "csat": (_sql_num(tot.get("promotoras")) or 0) / n * 100, "meta": meta_x / n_meta if n_meta else None,
            "ops": ops, "sups": sups, "fora": fora}


def _pp_signed(v: float | None, dec: int = 2) -> str:
    if v is None:
        return "—"
    return ("+" if v > 0 else "−" if v < 0 else "") + _bfmt(abs(v), dec) + " p.p."


def _render_pessoas_impacto(calc: dict[str, Any], alvo: str, label: str, d1: bool, eps: str | None,
                            titulo_equipe: str = "", so_sup: bool = False, so_ops: bool = False) -> str:
    gap = calc["csat"] - calc["meta"] if calc["meta"] is not None else None
    dot = _status_dot(calc["csat"] / calc["meta"] * 100 if calc["meta"] else None)
    head = (f"{dot} *Quem mais pesa no CSAT ·* `{alvo}`" + (f" · {titulo_equipe}" if titulo_equipe else "")
            + f" — {label}")
    linhas = [head, f"CSAT *{_bfmt(calc['csat'])}%*" + (f" (meta {_bfmt(calc['meta'])}% · {_pp_signed(gap, 1)})"
                                                         if calc["meta"] is not None else "")
              + f" · n={_fmt_int(calc['n'])}"]
    minimo = PESSOAS_MIN_AVAL_D1 if d1 else PESSOAS_MIN_AVAL
    allowed = _operator_names_allowed(eps)

    def who(o: dict[str, Any]) -> str:
        return _operator_label(o["email"], o["nome"] if allowed else "")

    sem = next((s for s in calc["sups"] if s["sup"] == "Sem supervisor no MOP"), None)
    peq = [s for s in calc["sups"] if s is not sem and s["aval"] < PESSOAS_SUP_MIN_AVAL]
    sups = sorted([s for s in calc["sups"] if s["imp"] is not None and s is not sem and s not in peq],
                  key=lambda s: s["imp"])
    if sups and not so_ops and not titulo_equipe:
        linhas += ["", "👥 *Por supervisor* — quem mais puxa para baixo"]
        for i, s in enumerate([s for s in sups if s["imp"] < -0.005][:PESSOAS_SUP_MAX], 1):
            falt = max(0, math.ceil(-s["acima"] - 1e-9))
            linhas.append(f"{i}. {_nice_name(s['sup'])} · *{_pp_signed(s['imp'])}* · CSAT {_bfmt(s['csat'])}% "
                          f"(meta {_bfmt(s['meta'])}%) · {s['n_ops']} operador(es) · n={_fmt_int(s['aval'])}"
                          + (f" · {falt} positivas faltantes" if falt else ""))
        if not any(s["imp"] < -0.005 for s in sups):
            linhas.append("Nenhuma equipe abaixo da meta no recorte. 👏")
    ops = sorted([o for o in calc["ops"] if o["imp"] is not None and o["aval"] >= minimo], key=lambda o: o["imp"])
    fora = calc["fora"] if calc.get("fora") is not None else sum(1 for o in calc["ops"] if o["aval"] < minimo)
    if not so_sup:
        neg = [o for o in ops if o["imp"] < -0.005]
        linhas += ["", "🧑‍💻 *Por operador* — quem mais puxa para baixo"]
        for i, o in enumerate(neg[:PESSOAS_OPS_MAX], 1):
            linhas.append(f"{i}. {who(o)} · {o['fila']} · *{_pp_signed(o['imp'])}* · CSAT {_bfmt(o['csat'])}% "
                          f"(meta {_bfmt(o['meta'])}%) · n={_fmt_int(o['aval'])}")
        if not neg:
            linhas.append("Ninguém abaixo da meta da fila no recorte. 👏")
        pos = [o for o in reversed(ops) if o["imp"] > 0.005][:3]
        if pos:
            linhas += ["", "💪 *Quem mais segura o resultado*"]
            linhas += [f"• {who(o)} · {o['fila']} · {_pp_signed(o['imp'])} · CSAT {_bfmt(o['csat'])}% · "
                       f"n={_fmt_int(o['aval'])}" for o in pos]
    linhas += ["", f"_Impacto = peso da pessoa nas avaliações de `{alvo}` × (CSAT dela − meta da fila dela), em p.p. do "
                   f"consolidado (mesma régua do Cockpit para filas); a soma de todo mundo dá o gap para a meta."
               + (f" Operadores com menos de {minimo} avaliações ficam fora do ranking ({fora}), mas contam na equipe."
                  if fora else "")
               + (f" Equipes com menos de {PESSOAS_SUP_MIN_AVAL} avaliações ficam fora do ranking de supervisor ({len(peq)})."
                  if peq and not so_ops and not titulo_equipe else "") + "_"]
    if sem and sem["aval"] and not titulo_equipe:
        linhas.insert(2, f"⚠️ {sem['n_ops']} operador(es) com {_fmt_int(sem['aval'])} avaliações "
                         f"({_bfmt(sem['aval'] / calc['n'] * 100, 0)}% do total) não estão no MOP de hoje (saíram, mudaram de "
                         "e-mail ou estão sem supervisor): contam no consolidado, mas ficam fora do ranking de supervisor.")
    return "\n".join(linhas)


def _send_pessoas_impacto(event: dict[str, Any], client: Any, eps: str | None, question: str,
                          say: Callable[..., Any], progress: Callable[[str], Any] | None = None) -> str | None:
    if eps is None:
        eps = _eps_of_question(question)
    ini, fim, label = _capa_period(question, event)
    d1 = ini == fim
    fila = _fila_in_question(question, eps)
    people = _mop_people(eps)
    t = _norm_text(question)
    emails: set[str] | None = None
    titulo_equipe = ""
    if people and (_TEAM_RE.search(t) or re.search(r"\b(minha|meu|nossa|nosso|meus)\b", t)):
        kind, leader = _resolve_team(question, event, people)
        if kind in {"sup", "coord"} and leader:
            field = "supervisor" if kind == "sup" else "coordenador"
            emails = {e for e, p in people.items() if _norm_text(p[field]) == _norm_text(leader)}
            titulo_equipe = f"{'Equipe' if kind == 'sup' else 'Coordenação'} de {_nice_name(leader)}"
            if eps is None:
                eps_t = {people[e].get("eps") for e in emails} - {"", None}
                eps = eps_t.pop() if len(eps_t) == 1 else None
    rows, problema = _csat_fixed_rows("csat_pessoas.sql", ini, fim,
                                      _pessoas_sql_params(eps, fila, people, fim, emails, d1),
                                      progress, f"CSAT por operador ({ini} a {fim})")
    if rows is None:
        return problema
    so_sup = bool(re.search(r"\b(supervisor\w*|supervisora\w*|equipes)\b", t)) and not re.search(
        r"\b(operador\w*|analista\w*|atendente\w*)\b", t)
    so_ops = bool(re.search(r"\b(operador\w*|analista\w*|atendente\w*)\b", t)) and not re.search(
        r"\b(supervisor\w*|supervisora\w*|coordenador\w*|equipes?)\b", t)
    textos = []
    for eps_nome in ([eps] if eps else ["AeC", "CSU"]):
        calc = _pessoas_from_rows(rows, eps_nome, people)
        sem = next((s for s in (calc or {}).get("sups", []) if s["sup"] == "Sem supervisor no MOP"), None)
        akey = f"pessoas_semmop:{eps_nome}:{_as_date(_today_brazil()).isoformat()}"
        if calc and sem and sem["aval"] > 0.1 * calc["n"] and not STATE.get(akey):
            STATE.set(akey, "1")
            _alert(f"📋 MOP da {eps_nome}: {sem['n_ops']} operadores que atenderam em {label} não estão no MOP de hoje "
                   f"({_bfmt(sem['aval'] / calc['n'] * 100, 0)}% das avaliações). Exemplos (usuário do e-mail): "
                   + ", ".join(calc.get("sem_mop_ex", [])[:8]) + ". Se forem ativos, vale corrigir o e-mail no MOP.")
        if calc:
            textos.append(_render_pessoas_impacto(calc, fila or eps_nome, label, d1, eps, titulo_equipe, so_sup, so_ops))
    if not textos:
        tipos = {r.get("tipo", "").upper() for r in rows}
        if rows and "TOTAL" in tipos and not tipos & {"OP", "SUP"}:  # voltou só o total: a Indicadores tirou as pessoas
            _alert(f"⚠️ CSAT por operador ({ini} a {fim}): voltaram só as linhas TOTAL, sem operador nem supervisor "
                   "(a Lyra Indicadores tirou a identificação? confira se ela está na v2.5.6).")
            return "A consulta voltou sem as linhas dos operadores. Já avisei o time; tenta de novo daqui a pouco?"
        if rows and "TOTAL" not in tipos:  # voltou algo, mas não o que o SQL devolve
            _alert(f"⚠️ CSAT por operador ({ini} a {fim}): a resposta não trouxe as linhas TOTAL do SQL fixo. "
                   f"Colunas: {sorted(rows[0].keys())[:8]} · 1ª linha: {_mask_pii(str(list(rows[0].values())[:5]))}")
            return "A consulta voltou num formato que eu não consegui ler. Já avisei o time; tenta de novo daqui a pouco?"
        return f"Não achei avaliações de {fila or eps or 'AeC/CSU'} em {label}. Quer outro período?"
    event["_catalog"] = "csat|pessoas|impacto"
    _say_sections(say, "\n\n".join(textos), event)
    return None


# --- quem mais pesa no TMA: analista e supervisor (seção 7.1d, SQL fixo) ---------
TMA_PESSOAS_MIN_TICKETS = 20
TMA_PESSOAS_MIN_TICKETS_D1 = 5


def _is_tma_pessoas_request(question: str) -> bool:
    """"Quais analistas/supervisores mais impactam o TMA?" (e "TMA por analista")."""
    t = _norm_text(question)
    if not re.search(r"\btma\b|tempo medio de atendimento", t) or re.search(r"\b(csat|casos?|tickets? (de|do|da)|motivos?)\b", t):
        return False
    if not _PESSOAS_RE.search(t):
        return False
    return bool(_PESSOAS_IMPACTO_RE.search(t) or re.search(r"\bpor (analista|operador|atendente|supervisor\w*)\b", t))


def _tma_pessoas_text(rows: list[dict[str, str]], eps_nome: str, people: dict[str, dict[str, str]], alvo: str,
                      label: str, eps: str | None, titulo_equipe: str, so_sup: bool, so_ops: bool, minimo: int) -> str:
    mine = [r for r in rows if _compact(r.get("eps", "")) == _compact(eps_nome)]
    tot = next((r for r in mine if r.get("tipo", "").upper() == "TOTAL"), None)
    tk = _sql_num(tot.get("tickets")) if tot else None
    if not tk:
        return ""
    tma = (_sql_num(tot.get("tempo")) or 0) / tk
    by_user = {e.split("@")[0]: e for e in people}
    allowed = _operator_names_allowed(eps)
    sec = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + _bfmt(abs(v), 1) + " s"
    linhas = [f"⏱️ *Quem mais pesa no TMA ·* `{alvo}`" + (f" · {titulo_equipe}" if titulo_equipe else "")
              + f" *— {label}* · TMA {_fmt_int(tma)} s · {_fmt_int(tk)} tickets"]
    sups = [r for r in mine if r.get("tipo", "").upper() == "SUP"]
    sem = next((r for r in sups if r.get("nome") == "Sem supervisor no MOP"), None)
    sups = sorted([r for r in sups if r is not sem and (_sql_num(r.get("tickets")) or 0) >= 100],
                  key=lambda r: -(_sql_num(r.get("impacto s")) or 0))
    if sups and not so_ops and not titulo_equipe:
        linhas += ["", "👥 *Por supervisor* — quem mais puxa o TMA para cima"]
        for i, r in enumerate([r for r in sups if (_sql_num(r.get("impacto s")) or 0) > 0.05][:PESSOAS_SUP_MAX], 1):
            t_eq = (_sql_num(r.get("tempo")) or 0) / max(_sql_num(r.get("tickets")) or 1, 1)
            linhas.append(f"{i}. {_nice_name(r.get('nome', ''))} · *{sec(_sql_num(r.get('impacto s')) or 0)}* · "
                          f"TMA da equipe {_fmt_int(t_eq)} s · {int(_sql_num(r.get('n ops')) or 0)} analista(s) · "
                          f"{_fmt_int(_sql_num(r.get('tickets')) or 0)} tickets")
        if not any((_sql_num(r.get("impacto s")) or 0) > 0.05 for r in sups):
            linhas.append("Nenhuma equipe puxando o TMA para cima. 👏")
    ops = [r for r in mine if r.get("tipo", "").upper() == "OP"]

    def who(r: dict[str, str]) -> str:
        u = r.get("nome", "").strip().lower()
        email = by_user.get(u) or u
        return _operator_label(email, (people.get(email) or {}).get("nome", "") if allowed else "")

    def op_line(r: dict[str, str]) -> str:
        t_op = (_sql_num(r.get("tempo")) or 0) / max(_sql_num(r.get("tickets")) or 1, 1)
        it = (_sql_num(r.get("tratados")) or 0) / max(_sql_num(r.get("tickets")) or 1, 1)
        return (f"{who(r)} · {r.get('fila', '')} · *{sec(_sql_num(r.get('impacto s')) or 0)}* · TMA {_fmt_int(t_op)} s "
                f"(fila {_fmt_int(_sql_num(r.get('tma fila s')) or 0)} s) · {_bfmt(it, 2)} interações/ticket · "
                f"{_fmt_int(_sql_num(r.get('tickets')) or 0)} tickets")

    if not so_sup:
        up = sorted([r for r in ops if (_sql_num(r.get("impacto s")) or 0) > 0.05], key=lambda r: -(_sql_num(r.get("impacto s")) or 0))
        linhas += ["", "🧑‍💻 *Por analista* — quem mais puxa o TMA para cima"]
        linhas += [f"{i}. {op_line(r)}" for i, r in enumerate(up[:PESSOAS_OPS_MAX], 1)] or ["Ninguém puxando o TMA para cima. 👏"]
        down = sorted([r for r in ops if (_sql_num(r.get("impacto s")) or 0) < -0.05], key=lambda r: _sql_num(r.get("impacto s")) or 0)[:3]
        if down:
            linhas += ["", "💪 *Quem mais segura o TMA*"] + [f"• {op_line(r)}" for r in down]
    fora = next((int(_sql_num(r.get("n ops")) or 0) for r in mine if r.get("tipo", "").upper() == "FORA"), 0)
    if sem and not titulo_equipe and (_sql_num(sem.get("tickets")) or 0) > 0.1 * tk:
        linhas.insert(1, f"⚠️ {int(_sql_num(sem.get('n ops')) or 0)} analista(s) com {_fmt_int(_sql_num(sem.get('tickets')) or 0)} "
                         "tickets não estão no MOP de hoje: contam no TMA, mas ficam fora do ranking de supervisor.")
    linhas += ["", f"_Impacto = TMA de `{alvo}` − TMA sem a pessoa (ou sem a equipe), em segundos; positivo puxa para cima. "
                   "Régua por analista (seção 7.1d): o ticket conta para cada analista que o atendeu, então o TMA aqui fica um "
                   "pouco diferente do oficial." + (f" Com menos de {minimo} tickets fica fora do ranking ({fora})." if fora else "")
               + "_"]
    return "\n".join(linhas)


def _send_tma_pessoas(event: dict[str, Any], client: Any, eps: str | None, question: str,
                      say: Callable[..., Any], progress: Callable[[str], Any] | None = None) -> str | None:
    if eps is None:
        eps = _eps_of_question(question)
    ini, fim, label = _capa_period(question, event)
    d1 = ini == fim
    fila = _fila_in_question(question, eps)
    people = _mop_people(eps)
    t = _norm_text(question)
    emails, titulo_equipe = None, ""
    if people and (_TEAM_RE.search(t) or re.search(r"\b(minha|meu|nossa|nosso|meus)\b", t)):
        kind, leader = _resolve_team(question, event, people)
        if kind in {"sup", "coord"} and leader:
            field = "supervisor" if kind == "sup" else "coordenador"
            emails = {e for e, p in people.items() if _norm_text(p[field]) == _norm_text(leader)}
            titulo_equipe = f"{'Equipe' if kind == 'sup' else 'Coordenação'} de {_nice_name(leader)}"
    base_p = _pessoas_sql_params(eps, None, people, fim, emails, d1)
    minimo = TMA_PESSOAS_MIN_TICKETS_D1 if d1 else TMA_PESSOAS_MIN_TICKETS
    tpl = _query_text("tma_pessoas.sql")
    if not tpl:
        return "A visão de TMA por analista não está configurada (falta queries/tma_pessoas.sql)."
    params = {"data_inicio": ini.isoformat(), "data_fim": fim.isoformat(), "eps_like": base_p["eps_like"],
              "filtro_fila": f"fila = '{fila}'" if fila else "1 = 1", "mop_values": base_p["mop_values"],
              "filtro_equipe": base_p["filtro_equipe"], "min_tickets": str(minimo), "top_ops": str(PESSOAS_OPS_MAX)}
    sql = tpl
    for k, v in params.items():
        sql = sql.replace("{" + k + "}", v)
    sql = _compact_sql(sql)
    key = f"tma_pessoas:{hash(sql)}"
    hit = _CSAT_ROWS_CACHE.get(key)
    if hit and time.time() - hit[0] < 1800:
        rows, problema = hit[1], ""
    else:
        rows, problema = _run_app_sql(sql, progress, f"TMA por analista ({ini} a {fim})", acesso=True)
        if rows is not None:
            _CSAT_ROWS_CACHE[key] = (time.time(), rows)
    if rows is None:
        return problema
    so_sup = bool(re.search(r"\b(supervisor\w*|equipes)\b", t)) and not re.search(r"\b(operador\w*|analista\w*|atendente\w*)\b", t)
    so_ops = bool(re.search(r"\b(operador\w*|analista\w*|atendente\w*)\b", t)) and not re.search(r"\b(supervisor\w*|coordenador\w*|equipes?)\b", t)
    textos = [x for x in (_tma_pessoas_text(rows, e, people, fila or e, label, eps, titulo_equipe, so_sup, so_ops, minimo)
                          for e in ([eps] if eps else ["AeC", "CSU"])) if x]
    if not textos:
        if rows and not any(r.get("tipo", "").upper() == "TOTAL" for r in rows):
            _alert(f"⚠️ TMA por analista ({ini} a {fim}): a resposta não veio no formato do SQL fixo. "
                   f"Colunas: {sorted(rows[0].keys())[:8]}")
            return "A consulta voltou num formato que eu não consegui ler. Já avisei o time; tenta de novo daqui a pouco?"
        return f"Não achei atendimento de {fila or eps or 'AeC/CSU'} em {label}. Quer outro período?"
    event["_catalog"] = "tma|pessoas|impacto"
    _say_sections(say, "\n\n".join(textos), event)
    return None


# --- variação e motivos de CSAT por SQL fixo -----------------------------------
def _csat_variacao_fixa(eps: str | None, fila: str, cur: tuple[date, date], ref: tuple[date, date],
                        progress: Callable[[str], Any] | None = None) -> dict[str, Any] | None:
    """Mesmo JSON da seção 7.2 (efeito mix e performance por motivo), calculado aqui a partir do SQL fixo.
    Sem response rate: o denominador da RR ainda não está definido para a consulta fixa."""
    eps_lista, _ = _csat_eps_params(eps or _eps_of_question(fila))
    ini, fim = min(cur[0], ref[0]), max(cur[1], ref[1])
    fila_sql = fila.replace("'", "''")
    rows, _ = _csat_fixed_rows("csat_variacao.sql", ini, fim, {
        "ref_inicio": ref[0].isoformat(), "ref_fim": ref[1].isoformat(), "cur_inicio": cur[0].isoformat(),
        "cur_fim": cur[1].isoformat(), "eps_lista": eps_lista, "filtro_fila": f"fila_relatorio = '{fila_sql}'"},
        progress, f"Variação do CSAT fixa ({fila})")
    if not rows:
        return None
    per: dict[str, dict[str, list[float]]] = {"atual": {}, "ref": {}}
    for r in rows:
        k = r.get("periodo", "").strip().lower()
        if k not in per:
            continue
        a, p = _sql_num(r.get("avaliacoes")) or 0, _sql_num(r.get("promotoras")) or 0
        acc = per[k].setdefault(r.get("motivo") or "sem motivo", [0.0, 0.0])
        acc[0] += a
        acc[1] += p
    n_c, n_r = sum(v[0] for v in per["atual"].values()), sum(v[0] for v in per["ref"].values())
    if not n_c or not n_r:
        return None
    c_c = sum(v[1] for v in per["atual"].values()) / n_c * 100
    c_r = sum(v[1] for v in per["ref"].values()) / n_r * 100
    mix, perf, top_mix, top_perf = 0.0, 0.0, [], []
    for m in set(per["atual"]) | set(per["ref"]):
        ac, pc = per["atual"].get(m, [0.0, 0.0])
        ar, pr = per["ref"].get(m, [0.0, 0.0])
        sh_c, sh_r = ac / n_c, ar / n_r
        cs_r = pr / ar * 100 if ar else None
        cs_c = pc / ac * 100 if ac else None
        # mix: Δ participação × (CSAT ref do motivo − CSAT ref da fila); performance: share atual × ΔCSAT do motivo
        e_mix = (sh_c - sh_r) * ((cs_r if cs_r is not None else c_r) - c_r)
        e_perf = sh_c * (cs_c - cs_r) if cs_c is not None and cs_r is not None else sh_c * ((cs_c or 0) - c_r)
        mix += e_mix
        perf += e_perf
        top_mix.append({"motivo": m, "share_ref": sh_r * 100, "share_atual": sh_c * 100, "csat_ref": cs_r, "efeito_pp": e_mix})
        if cs_c is not None and cs_r is not None:
            top_perf.append({"motivo": m, "csat_ref": cs_r, "csat_atual": cs_c, "share_atual": sh_c * 100, "efeito_pp": e_perf})
    sgn = lambda total: (lambda x: x["efeito_pp"] * (1 if total > 0 else -1))
    top_mix.sort(key=sgn(mix), reverse=True)
    top_perf.sort(key=sgn(perf), reverse=True)
    return {"csat_ref": c_r, "csat_atual": c_c, "n_ref": n_r, "n_atual": n_c, "mix_pp": mix, "performance_pp": perf,
            "top_mix": top_mix[:3], "top_performance": top_perf[:3], "_fixa": True}


def _csat_motivos_texto(eps: str | None, fila: str | None, ini: date, fim: date, label: str,
                        progress: Callable[[str], Any] | None = None, top: int = 5) -> str:
    """Motivos que mais pesam no CSAT (seção 6): participação nas avaliações da fila × (CSAT do motivo − CSAT da fila)."""
    eps_lista, _ = _csat_eps_params(eps)
    rows, _ = _csat_fixed_rows("csat_motivos.sql", ini, fim, {"eps_lista": eps_lista}, progress,
                               f"Motivos de CSAT fixos ({ini} a {fim})")
    if not rows:
        return ""
    blocos = []
    filas = sorted({r.get("fila", "") for r in rows if r.get("fila")})
    for f in ([fila] if fila else filas):
        rs = [r for r in rows if _norm_text(r.get("fila", "")) == _norm_text(f)]
        n = sum(_sql_num(r.get("avaliacoes")) or 0 for r in rs)
        if not n:
            continue
        c_f = sum(_sql_num(r.get("promotoras")) or 0 for r in rs) / n * 100
        itens = []
        for r in rs:
            a, p = _sql_num(r.get("avaliacoes")) or 0, _sql_num(r.get("promotoras")) or 0
            if a:
                itens.append((a / n * (p / a * 100 - c_f), r.get("motivo") or "sem motivo", a, p / a * 100))
        itens.sort()
        neg = [x for x in itens if x[0] < 0][:top]
        if not neg:
            continue
        blocos.append(f"`{f}` · CSAT {_bfmt(c_f)}% · n={_fmt_int(n)}\n" + "\n".join(
            f"• {_motivo_label(m)}: {_pp_signed(imp)} · CSAT {_bfmt(cs)}% · {_bfmt(a / n * 100)}% das avaliações"
            for imp, m, a, cs in neg))
    if not blocos:
        return ""
    return (f"🎯 *Motivos que mais pesam no CSAT* — {label}\n_impacto = participação do motivo nas avaliações da fila × "
            "(CSAT do motivo − CSAT da fila)_\n\n" + "\n\n".join(blocos))


# --- classificação da pergunta e registro do que ficou fora do catálogo ---------
_CAT_IND = (("tma", r"\btma\b|tempo medio|tempo de atendimento"), ("sla", r"\bsla\b|primeira resposta|1a resposta"),
            ("csat", r"\bcsat\b|satisfac\w*|avaliac\w*|promotor\w*|detrator\w*|\bnotas?\b"))
CATALOG_LOG_KEY = "catalogo:fora"
CATALOG_LOG_MAX = 400
CATALOG_REPEAT_MIN = 3
CATALOG_REPEAT_DAYS = 14


def _catalog_shape(question: str, event: dict[str, Any] | None = None) -> dict[str, str] | None:
    """indicador × nível × período × tipo da pergunta (None = não é pergunta de indicador)."""
    t = _norm_text(question)
    ind = "+".join(k for k, rx in _CAT_IND if re.search(rx, t))
    if not ind:
        return None
    nivel = ("caso" if re.search(r"\b(casos?|tickets?|chamados?)\b", t) else
             "operador" if re.search(r"\b(operador\w*|analista\w*|atendente\w*)\b", t) else
             "supervisor" if re.search(r"\b(supervisor\w*|coordenador\w*|equipes?|times?)\b", t) else
             "motivo" if re.search(r"\b(motivos?|ofensor\w*)\b", t) else
             "fila" if re.search(r"\b(fila|filas|celula\w*)\b", t) or _fila_in_question(question, None) else "eps")
    try:
        ini, fim, _ = _capa_period(question, event or {})
        d1 = _as_date(_today_brazil()) - timedelta(days=1)
        periodo = ("dia a dia" if _DIARIO_RE.search(t) else "ontem" if ini == fim == d1 else
                   "mes fechado" if fim < d1 and ini.day == 1 else "semana" if re.search(r"\bsemana\b", t) else
                   "mes ate ontem" if ini.day == 1 and fim == d1 else "datas")
    except Exception:
        periodo = "?"
    tipo = ("lista" if re.search(r"\b(lista\w*|base|planilha|excel|nominal|quais (casos|tickets))\b", t) else
            "variacao" if re.search(r"\b(caiu|cair|subiu|piorou|melhorou|variac\w*|por que|porque|pq|compar\w*|evoluc\w*)\b", t) else
            "impacto" if re.search(r"\b(impact\w*|pesa\w*|puxa\w*|ofensor\w*|piores?|quem mais|maior\w* gap)\b", t) else
            "resultado")
    return {"ind": ind, "nivel": nivel, "periodo": periodo, "tipo": tipo, "key": f"{ind}|{nivel}|{periodo}|{tipo}"}


def _catalog_log(shape: dict[str, str], question: str, event: dict[str, Any]) -> None:
    try:
        log = json.loads(STATE.get(CATALOG_LOG_KEY) or "[]")
    except ValueError:
        log = []
    log.append({"d": _as_date(_today_brazil()).isoformat(), "k": shape["key"], "q": _mask_pii(question)[:160],
                "c": str(event.get("channel") or "")})
    try:
        STATE.set(CATALOG_LOG_KEY, json.dumps(log[-CATALOG_LOG_MAX:], ensure_ascii=False))
    except Exception:
        logger.warning("Could not log off-catalog question", exc_info=True)


def _catalog_candidates(today: date) -> list[tuple[str, int, list[str]]]:
    try:
        log = json.loads(STATE.get(CATALOG_LOG_KEY) or "[]")
    except ValueError:
        return []
    desde = (today - timedelta(days=CATALOG_REPEAT_DAYS)).isoformat()
    grupos: dict[str, list[str]] = {}
    for e in log:
        if e.get("d", "") >= desde:
            grupos.setdefault(e.get("k", "?"), []).append(e.get("q", ""))
    return sorted(((k, len(qs), qs[-3:]) for k, qs in grupos.items() if len(qs) >= CATALOG_REPEAT_MIN),
                  key=lambda x: -x[1])


def _catalog_weekly_tick(now: datetime) -> None:
    """Segunda de manhã: lista para o responsável os formatos de pergunta fora do catálogo que se repetiram."""
    if now.weekday() != 0 or now.hour < 9:
        return
    key = f"catalogo:semana:{now.date().isoformat()}"
    if STATE.get(key):
        return
    STATE.set(key, "ok")
    cands = _catalog_candidates(now.date())
    if not cands:
        return
    linhas = [f"🧩 Candidatos ao catálogo de consultas (perguntas fora do catálogo que se repetiram {CATALOG_REPEAT_MIN}+ "
              f"vezes nos últimos {CATALOG_REPEAT_DAYS} dias):"]
    for k, n, ex in cands[:10]:
        ind, nivel, periodo, tipo = (k.split("|") + ["?"] * 4)[:4]
        linhas.append(f"• *{ind.upper()} · {nivel} · {periodo} · {tipo}* — {n}x. Ex.: " + " / ".join(f"_{q}_" for q in ex))
    linhas.append("Se fizer sentido, eu transformo em consulta fixa.")
    _alert("\n".join(linhas))


FREE_ANALYSIS_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — ANÁLISE FORA DO CATÁLOGO: esta pergunta não tem consulta pronta no app. Monte a "
    "análise pedindo à Lyra Indicadores, SEMPRE a partir da base oficial e das regras dela (CSAT: seção 9 e regras de "
    "fila; TMA/SLA: SQL de eficiência do Anexo, com o corte de SLA por célula). Reaproveite as mesmas fórmulas de "
    "resultado, meta e impacto que ela já usa; não invente régua nova. Se precisar de uma conta que não está nas regras, "
    "diga em meia frase como calculou.\n\n")
FREE_ANALYSIS_NOTE = "_Análise feita na hora (fora das consultas prontas)._"


# ---------------------------------------------------------------------------
# Checagem de crise (Lyra Crises): antes de cobrar a EPS, a Lyra confere se teve crise no período. Crise do lado do
# iFood (Rosie, plataforma, Salesforce, clima...) é registro: a cobrança vira "o que a operação fez durante a crise".
# ---------------------------------------------------------------------------
CRISIS_CHECK = os.getenv("CRISIS_CHECK", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
CRISIS_CHECK_TTL = int(os.getenv("CRISIS_CHECK_TTL", "1800"))  # status/prints reaproveitam a checagem por 30 min
CRISIS_STATUS_WINDOW_HOURS = 3


def _crisis_prompt(start: datetime, end: datetime, eps: str | None) -> str:
    f = lambda d: d.strftime("%d/%m/%Y %H:%M")
    return (
        "TAREFA INTERNA DO APP — checagem de crise. Não é mensagem para o Slack. Responda APENAS com JSON válido.\n"
        "Chame o subagente *Lyra Crises* com 'Pedido: checagem de crise' e "
        f"'Período: {f(start)} a {f(end)} (BRT)'"
        + (f" e 'EPS: {eps}'" if eps else "") + ". Devolva exatamente o JSON que ele responder:\n"
        '{"crise": true|false, "resumo": "<sistema e o que aconteceu, 1 frase>", "inicio": "~hhhmm", "fim": "~hhhmm ou '
        'em andamento", "impacto": "<efeito no atendimento: transbordo, fila, filas afetadas>", "filas": ["<fila>"], '
        '"status": "Estabilizado|Estabilizando|Em andamento|Em investigação"}\n'
        "Sem crise ou sem fonte: {\"crise\": false}. Se a consulta falhar: responda só 'ERRO: <motivo>'."
    )


def _crisis_check(start: datetime, end: datetime, eps: str | None = None,
                  ttl: float | None = CRISIS_CHECK_TTL) -> dict[str, Any] | None:
    """{crise, resumo, inicio, fim, impacto, filas, status} quando teve crise no período; None se não teve, se a
    checagem estiver desligada ou se falhar (falha nunca trava a cobrança)."""
    if not CRISIS_CHECK:
        return None
    try:
        answer = _ask_cached(_crisis_prompt(start, end, eps), ttl_seconds=ttl)
    except Exception:
        logger.warning("Crisis check failed", exc_info=True)
        return None
    if _is_error_answer(answer):
        logger.warning("Crisis check returned error: %s", str(answer)[:200])
        return None
    try:
        data = json.loads(_strip_json_code_blocks(answer))
    except Exception:
        m = re.search(r"\{.*\}", answer or "", re.S)
        try:
            data = json.loads(m.group(0)) if m else None
        except Exception:
            data = None
    if not isinstance(data, dict) or not data.get("crise") or not str(data.get("resumo") or "").strip():
        return None
    data["filas"] = [str(x) for x in (data.get("filas") or []) if str(x).strip()]
    return data


def _crisis_line(c: dict[str, Any], when: str = "") -> str:
    ini, fim = str(c.get("inicio") or "").strip(), str(c.get("fim") or "").strip()
    if "andamento" in _norm_text(fim):
        janela = f"desde {ini}, em andamento" if ini else "em andamento"
    else:
        janela = " ".join(x for x in (f"das {ini}" if ini else "", f"às {fim}" if fim else "") if x)
    txt = f"🚨 *Crise{(' ' + when) if when else ''}:* {str(c['resumo']).strip().rstrip('.')}"
    if janela:
        txt += f" ({janela})"
    if c.get("impacto"):
        txt += f" — {str(c['impacto']).strip().rstrip('.')}"
    return txt + "."


def _crisis_hits_fila(c: dict[str, Any], fila: str) -> bool:
    """Sem filas informadas, a crise vale para todas as filas da EPS."""
    filas = c.get("filas") or []
    return not filas or any(_norm_text(f) in _norm_text(fila) or _norm_text(fila) in _norm_text(f) for f in filas)


def _apply_crisis_to_body(body: str, fila: str, c: dict[str, Any] | None) -> str:
    """Report: fila cobrada no D-1 em que teve crise -> registra a crise e troca a cobrança por "o que a operação fez
    durante a crise"."""
    if not c or "👉 *Cobrança:*" not in body or not _crisis_hits_fila(c, fila):
        return body
    out = []
    for line in body.split("\n"):
        if line.startswith("👉 *Cobrança:*"):
            out.append(_crisis_line(c, "no D-1"))
            out.append("👉 *Cobrança:* A queda coincide com a crise, que é do lado do iFood. O que a operação fez durante "
                       "ela (escala, priorização da fila, comunicação com o cliente) e o que muda se acontecer de novo? "
                       "Retorno aqui na thread até 14h.")
        else:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Report diário (um por EPS + consolidado opcional)
# ---------------------------------------------------------------------------
class ReportGenerationError(RuntimeError):
    """O Toqan não devolveu um report publicável."""


_FILA_HEADER_RE = re.compile(
    r"^\s*(?:[🔴🟢⚪🟡]\s*)?\*{0,2}\s*(?:Governan[çc]a\s*·\s*)?\*{0,2}\s*`?(?P<fila>[^`*\n·—]+?)`?\s*\*{0,2}\s*[·—–-]\s*\d{1,2}/\d{1,2}\b.*$",
    re.MULTILINE,
)


def _split_blocks(answer: str, use_headers: bool = False) -> list[tuple[str, str]]:
    """[(fila, texto do bloco)] a partir dos marcadores ===FILA: x===. Vazio se não houver marcador."""
    marks = list(FILA_BLOCK_RE.finditer(answer or ""))
    if not marks and use_headers:  # report diário sem marcadores: usa os títulos de fila que o modelo escreveu
        marks = list(_FILA_HEADER_RE.finditer(answer or ""))
    blocks = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(answer)
        text = answer[m.end():end].strip()
        if text:
            blocks.append((m.group("fila").strip(), text))
    return blocks


def _tag_block(fila: str, text: str) -> tuple[str, bool]:
    """Marca o owner na linha *Cobrança:* (ou 👉) do bloco. Devolve (texto, tem_cobrança)."""
    lines = text.splitlines()
    has_cobranca = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("👉") or _norm_text(stripped.lstrip("•").strip().strip("*")).startswith("cobranca"):
            has_cobranca = True
            mentions = [m for m in (_owner_mention(o) for o in _owners_for(fila)) if m and m not in line]
            if mentions:
                lines[i] = line.rstrip() + " " + " ".join(mentions)
    return "\n".join(lines), has_cobranca


_BLOCK_D1_RE = re.compile(rf"\*?\s*({_NUM})\s*%\s*\*?\s*em\s+D\s*[-–]?\s*1", re.IGNORECASE)
_BLOCK_MES_RE = re.compile(rf"\bm[eê]s\s*:?\s*\*?\s*({_NUM})\s*%", re.IGNORECASE)

# --- layout do bloco: montado pelo app (não depende do modelo seguir o formato) ---
_SNUM = r"[-−–]?\s*\d{1,4}(?:[.,]\d+)?"
_X_D1_AFTER_RE = re.compile(rf"D\s*[-–]?\s*1\s*:?\s*\*?\s*({_NUM})\s*%", re.IGNORECASE)
_X_N_RE = re.compile(r"\bn\s*=\s*(\d[\d.]*)", re.IGNORECASE)
_X_VAR_RE = re.compile(rf"([▲▼])\s*({_NUM})")
_X_META_RE = re.compile(rf"\bmeta\s*:?\s*\*?\s*({_NUM})\s*%", re.IGNORECASE)
_X_OFENSOR_RE = re.compile(r"maior\s+(?:ofensor|impacto)\s*:?\s*\*?\s*:?\s*(.+)", re.IGNORECASE)
_X_PP_RE = re.compile(rf"({_SNUM})\s*p\.?\s*p", re.IGNORECASE)
_X_Q4_RE = re.compile(r"(?:\bQ4\s*:?\s*(\d+))|(?:(\d+)\s*(?:operadores\s*)?no\s*Q4)", re.IGNORECASE)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("−", "-").replace("–", "-").replace(" ", "").replace("%", "")
    if text.count(",") == 1 and "." in text:  # 1.240,5
        text = text.replace(".", "")
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _bfmt(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def _fmt_meta(value: float) -> str:
    return _bfmt(value, 0) if float(value).is_integer() else _bfmt(value)


def _fmt_int(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", ".")


def _block_data_from_json(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _block_data_from_text(text: str) -> dict[str, Any]:
    """Extrai os números de um bloco em texto livre (quando o modelo não devolve o JSON)."""
    clean = text.replace("**", "*")
    data: dict[str, Any] = {}
    if re.search(r"sem\s+volume", clean, re.IGNORECASE) and not _X_N_RE.search(clean):
        return {"sem_volume": True}
    d1 = _BLOCK_D1_RE.search(clean) or _X_D1_AFTER_RE.search(clean)
    data["d1"] = _num(d1.group(1)) if d1 else None
    for key, rx in (("n", _X_N_RE), ("meta", _X_META_RE), ("mes", _BLOCK_MES_RE)):
        m = rx.search(clean)
        data[key] = _num(m.group(1).replace(".", "") if key == "n" else m.group(1)) if m else None
    var = _X_VAR_RE.search(clean)
    if var:
        data["var"] = (_num(var.group(2)) or 0) * (-1 if var.group(1) == "▼" else 1)
    for line in clean.splitlines():
        m = _X_OFENSOR_RE.search(line)
        if m:
            rest = m.group(1).strip().strip("*")
            pp = _X_PP_RE.search(rest)
            if pp:
                value = _num(pp.group(1)) or 0
                data["ofensor_pp"] = -abs(value)
            name = re.split(r"\s*(?:·|\(|—| - |,\s*tira|\btira\b|\|)", rest, maxsplit=1)[0]
            data["ofensor"] = re.sub(r"^D\s*-\s*1\s*:?\s*", "", name.strip(" *:."), flags=re.IGNORECASE)
            mes_part = re.search(r"\|\s*m[eê]s\s*:?\s*(.+)", rest, re.IGNORECASE)
            if mes_part:
                data["ofensor_mes"] = re.split(r"\s*(?:·|\(|—|\btira\b)", mes_part.group(1), maxsplit=1)[0].strip(" *:.")
                pp_mes = _X_PP_RE.search(mes_part.group(1))
                if pp_mes:
                    data["ofensor_mes_pp"] = -abs(_num(pp_mes.group(1)) or 0)
            break
    q4 = _X_Q4_RE.search(clean)
    if q4:
        data["q4"] = _num(q4.group(1) or q4.group(2))
    for q in ("q1", "q2", "q3"):
        m = re.search(rf"\b{q}\s*:?\s*(\d+)", clean, re.IGNORECASE)
        if m:
            data[q] = _num(m.group(1))
    reinc = re.search(r"(\d+)\s*reincident", clean, re.IGNORECASE)
    if reinc:
        data["reincidentes"] = _num(reinc.group(1))
    cob = re.search(r"cobran[çc]a\s*:?\s*\*?\s*:?\s*(.+?)(?:\s*(?:Plano|Status|O prazo da ação) |$)", clean, re.IGNORECASE)
    if cob:
        data["cobranca"] = cob.group(1).strip(" *")
    pin = re.search(r"📌\s*(.+)", clean)
    if pin:
        data["compromisso"] = pin.group(1).split("—")[0].strip(" *")
    for line in clean.splitlines():
        if line.strip().startswith("👉") or "cobran" in _norm_text(line)[:12]:
            questions = re.findall(r"[^.?!—:]*\?", line)
            if questions:
                data["pergunta"] = questions[0].strip(" *")
            break
    return data


def _block_status(data: dict[str, Any]) -> str:
    if data.get("sem_volume") or data.get("d1") is None:
        return "sem_volume"
    if data.get("meta") is None:
        return "sem_meta"
    return "abaixo" if data["d1"] < data["meta"] else "ok"


QUAD_KEYS = ("q1", "q2", "q3", "q4")
DISPERSION_ALERT_PP = 5.0  # variação de Q3+Q4 (p.p. dos operadores) que conta como mudança de dispersão


def _quad(data: dict[str, Any], key: str) -> dict[str, float] | None:
    """Quantidade de operadores por quadrante ({q1..q4}) no mês ou no D-1."""
    raw = data.get(key)
    if key == "quad_mes" and not isinstance(raw, dict) and any(data.get(q) is not None for q in QUAD_KEYS):
        raw = {q: data.get(q) for q in QUAD_KEYS}  # formato antigo: q1..q4 soltos
    if not isinstance(raw, dict):
        return None
    values = {q: _num(raw.get(q)) or 0.0 for q in QUAD_KEYS}
    return values if sum(values.values()) > 0 else None


def _quad_shares(quad: dict[str, float]) -> dict[str, float]:
    total = sum(quad.values())
    return {q: 100.0 * v / total for q, v in quad.items()}


def _quad_line(label: str, quad: dict[str, float]) -> str:
    shares = _quad_shares(quad)
    parts = " · ".join(f"{q.upper()} {round(shares[q]):d}%" for q in QUAD_KEYS)
    return f"`{label} │ {parts}`"


DISPERSION_ALERT = 0.05  # variação do índice (CSAT Q4 ÷ CSAT Q1) que conta como mudança


def _disp_index(data: dict[str, Any], key: str) -> float | None:
    """Dispersão (régua do Cockpit) = CSAT dos operadores do Q4 ÷ CSAT dos operadores do Q1. Perto de 1 = homogêneo."""
    raw = data.get(key)
    if not isinstance(raw, dict):
        return None
    q1, q4 = _num(raw.get("q1")), _num(raw.get("q4"))
    if not q1 or q4 is None:
        return None
    return q4 / q1


def _dispersion(data: dict[str, Any]) -> tuple[str, float, float] | None:
    """('aumentou' | 'diminuiu' | 'estável', índice mês, índice D-1). Índice caindo = dispersão aumentando."""
    mes, d1 = _disp_index(data, "disp_mes"), _disp_index(data, "disp_d1")
    if mes is None or d1 is None:
        return None
    delta = d1 - mes
    trend = "aumentou" if delta <= -DISPERSION_ALERT else "diminuiu" if delta >= DISPERSION_ALERT else "estável"
    return trend, mes, d1


def _same_reason(a: Any, b: Any) -> bool:
    na, nb = _norm_text(a), _norm_text(b)
    return bool(na) and bool(nb) and (na == nb or na in nb or nb in na)


def _fmt_tempo(seconds: float) -> str:
    """Tempos sempre em segundos (preferência do time), ex.: 802 s."""
    return f"{_fmt_int(seconds)} s"


def _tma_data(fila: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """TMA = tempo por interação × interações por ticket, no D-1 e no mês, contra o plan da célula."""
    if not TMA_IN_REPORT or any(_norm_text(fila) == _norm_text(f) for f in NO_TMA_FILAS):
        return None
    tpi_d1, int_d1 = _num(data.get("tma_tpi_d1")), _num(data.get("tma_int_d1"))
    if tpi_d1 is None or int_d1 is None:
        return None
    tpi_mes, int_mes = _num(data.get("tma_tpi_mes")), _num(data.get("tma_int_mes"))
    plan_key = next((k for k in TMA_PLAN if _norm_text(k) == _norm_text(fila)), None)  # nome exato: "Review" ≠ "CX Review - AeC"
    plan = TMA_PLAN.get(plan_key) if plan_key else None
    out: dict[str, Any] = {
        "d1": tpi_d1 * int_d1, "tpi_d1": tpi_d1, "int_d1": int_d1,
        "mes": (tpi_mes * int_mes) if tpi_mes is not None and int_mes is not None else None,
        "tratados": _num(data.get("tma_tratados_d1")),
        "plan": None,
    }
    if plan:
        tempo_unico, inter_plan = plan
        out.update(plan=tempo_unico, int_plan=inter_plan, tpi_plan=tempo_unico / inter_plan if inter_plan else None)
    return out


def _tma_status(tma: dict[str, Any] | None) -> str:
    if not tma:
        return "sem_dado"
    if tma.get("plan") is None:
        return "sem_plan"
    return "acima" if tma["d1"] > tma["plan"] else "ok"


def _render_block(fila: str, data: dict[str, Any], day: date) -> tuple[str, str] | None:
    """(título no canal, corpo na thread). None = fila sem CSAT no D-1 (não entra no report).
    Corpo em duas seções bem separadas: D-1 (o que é cobrado) e Mês (contexto), depois leitura e cobrança."""
    status = _block_status(data)
    if status == "sem_volume":
        return None
    dd = day.strftime("%d/%m")
    d1, meta, mes = data["d1"], data.get("meta"), data.get("mes")
    tma = _tma_data(fila, data)
    tstatus = _tma_status(tma)
    off = status == "abaixo" or tstatus == "acima"
    has_target = meta is not None or tstatus in {"ok", "acima"}
    emoji = "🔴" if off else ("🟢" if has_target else "⚪")
    title = f"{emoji} *Governança ·* `{fila}` *— D-1 {dd}* · CSAT D-1 {_bfmt(d1)}%" + (
        f" (meta {_fmt_meta(meta)}%)" if meta is not None else "")
    if tma:
        title += f" · TMA {_fmt_tempo(tma['d1'])}" + (f" (plan {_fmt_tempo(tma['plan'])})" if tma.get("plan") else "")

    def csat_vs_meta(value: float) -> str:
        if meta is None:
            return "⚪ sem meta"
        if value < meta:
            return f"🔴 {_bfmt(meta - value)} p.p. abaixo da meta {_fmt_meta(meta)}%"
        return "🟢 na meta" if value == meta else f"🟢 {_bfmt(value - meta)} p.p. acima da meta {_fmt_meta(meta)}%"

    def tma_vs_plan(value: float) -> str:
        if not tma or tma.get("plan") is None:
            return "⚪ plan a definir"
        diff = value - tma["plan"]
        if diff > 0:
            return f"🔴 {_fmt_tempo(diff)} acima do plan {_fmt_tempo(tma['plan'])}"
        return f"🟢 {_fmt_tempo(-diff)} abaixo do plan {_fmt_tempo(tma['plan'])}" if diff < -0.5 else "🟢 no plan"

    def problema(name_key: str, pp_key: str) -> str:
        text = str(data.get(name_key) or "").strip()
        if text and data.get(pp_key) is not None:
            text += f" · tira {_bfmt(abs(_num(data[pp_key]) or 0))} p.p."
        return text

    def quad_text(quad: dict[str, float] | None, disp_key: str) -> str:
        if not quad:
            return ""
        shares = _quad_shares(quad)
        text = " · ".join(f"{q.upper()} {round(shares[q]):d}%" for q in QUAD_KEYS)
        idx = _disp_index(data, disp_key)
        return text + (f" · dispersão {_bfmt(idx, 2)}" if idx is not None else "")

    lines: list[str] = []
    # ---- D-1: o que está sendo cobrado
    lines.append(f"📍 *D-1 · {dd}* — é o que estamos cobrando")
    extra = []
    if data.get("n") is not None:
        extra.append(f"n={_fmt_int(data['n'])}")
    if data.get("var") is not None:
        extra.append(f"{'▼' if data['var'] < 0 else '▲'} {_bfmt(abs(data['var']))} p.p. vs dia anterior")
    lines.append(f"• CSAT do D-1 *{_bfmt(d1)}%* → {csat_vs_meta(d1)}" + (f" ({' · '.join(extra)})" if extra else ""))
    if tma:
        lines.append(f"• TMA do D-1 *{_fmt_tempo(tma['d1'])}* → {tma_vs_plan(tma['d1'])}"
                     + (f" ({_fmt_int(tma['tratados'])} tratados)" if tma.get("tratados") is not None else ""))
    p_d1 = problema("ofensor", "ofensor_pp")
    if p_d1:
        lines.append(f"• Problema do D-1: {p_d1}")
    quad_mes, quad_d1 = _quad(data, "quad_mes"), _quad(data, "quad_d1")
    q_d1 = quad_text(quad_d1, "disp_d1")
    if q_d1:
        lines.append(f"• Quadrantes do D-1: {q_d1}")

    # ---- Mês: contexto
    month_lines = []
    if mes is not None:
        month_lines.append(f"• CSAT do mês *{_bfmt(mes)}%* → {csat_vs_meta(mes)}")
    if tma and tma.get("mes") is not None:
        month_lines.append(f"• TMA do mês *{_fmt_tempo(tma['mes'])}* → {tma_vs_plan(tma['mes'])}")
    p_mes = problema("ofensor_mes", "ofensor_mes_pp")
    if p_mes:
        month_lines.append(f"• Problema do mês: {p_mes}")
    q_mes = quad_text(quad_mes, "disp_mes")
    if q_mes:
        month_lines.append(f"• Quadrantes do mês: {q_mes}")
    if month_lines:
        lines.append("")
        lines.append(f"🗓️ *Mês · 01 a {dd}* — contexto")
        lines.extend(month_lines)

    # ---- Leitura (o que os números dizem)
    leitura = []
    if p_d1 and p_mes:
        leitura.append("Mesmo problema no D-1 e no mês: é estrutural, não pontual."
                       if _same_reason(data.get("ofensor"), data.get("ofensor_mes"))
                       else "O problema do D-1 é diferente do mês: vale entender o que mudou ontem.")
    disp = _dispersion(data)
    reinc = data.get("reincidentes")
    reinc_txt = ""
    if reinc is not None:
        n_re = int(_num(reinc) or 0)
        reinc_txt = f" {n_re} reincidente{'s' if n_re != 1 else ''} no Q4."
    if disp:
        trend, idx_mes, idx_d1 = disp
        change = f"{_bfmt(idx_mes, 2)} no mês → {_bfmt(idx_d1, 2)} no D-1"
        leitura.append({"aumentou": f"📈 Dispersão aumentou ({change}): piora no comportamento operacional.",
                        "diminuiu": f"📉 Dispersão diminuiu ({change}): operação mais homogênea.",
                        "estável": f"Dispersão estável ({change})."}[trend] + reinc_txt)
    elif reinc_txt:
        leitura.append(reinc_txt.strip())
    if tstatus == "acima" and tma.get("tpi_plan") and tma.get("int_plan"):
        r_int = tma["int_d1"] / tma["int_plan"]
        r_tpi = tma["tpi_d1"] / tma["tpi_plan"]
        if r_int >= r_tpi:
            leitura.append(f"TMA puxado por *mais interações por ticket* ({_bfmt(tma['int_d1'], 2)} vs "
                           f"{_bfmt(tma['int_plan'], 2)} do plan): cliente voltando = não resolveu no primeiro contato.")
        else:
            leitura.append(f"TMA puxado por *tempo por interação* ({_fmt_tempo(tma['tpi_d1'])} vs "
                           f"{_fmt_tempo(tma['tpi_plan'])} do plan): atendimento mais longo = condução, procedimento ou ferramenta.")
    if leitura:
        lines.append("")
        lines.append("💡 *Leitura*")
        lines.extend(f"↳ {t}" for t in leitura)

    # ---- Compromisso e cobrança / destaque
    # Ação já rodando para o mesmo problema: cobra status e efeito, não ação nova (prazo vencido: resultado ou novo plano).
    compromisso = str(data.get("compromisso") or "").strip()
    cobre = bool(compromisso) and data.get("compromisso_cobre") is not False
    vencido = False
    pm = re.search(r"prazo\s*(\d{1,2})/(\d{1,2})", compromisso)
    if pm:
        try:
            prazo = date(day.year, int(pm.group(2)), int(pm.group(1)))
            if prazo.month == 12 and day.month == 1:
                prazo = prazo.replace(year=day.year - 1)
            vencido = prazo <= day  # venceu até o D-1
        except ValueError:
            pass
    if compromisso or off or has_target:
        lines.append("")
    if compromisso:
        label = "📌 *Ação com prazo vencido:*" if vencido else "📌 *Ação em andamento:*"
        lines.append(f"{label} {compromisso}" + ("" if off and cobre else " — qual o status?"))
    if off:
        cobranca = str(data.get("cobranca") or data.get("pergunta") or "").strip()
        cobranca = re.split(r"\s*(Plano|Status) aqui na thread", cobranca, maxsplit=1)[0].strip()
        if not cobranca:
            gaps = []
            if status == "abaixo":
                gaps.append(f"CSAT {_bfmt(meta - d1)} p.p. abaixo da meta")
            if tstatus == "acima":
                gaps.append(f"TMA {_fmt_tempo(tma['d1'] - tma['plan'])} acima do plan")
            cobranca = (f"{' e '.join(gaps)} no D-1 — a ação em andamento está segurando o problema?" if cobre
                        else f"{' e '.join(gaps)} no D-1 — o que está sendo feito pra corrigir?")
        if not cobranca.endswith("?"):
            cobranca = cobranca.rstrip(".") + "?"
        if cobre and not vencido:
            suffix = "Status aqui na thread até 14h: *o que já foi feito · efeito até agora · próximo passo*."
        elif cobre:
            suffix = ("O prazo da ação venceu: foi feita e qual o resultado? Se não resolveu, novo plano aqui na thread "
                      "até 14h: *ação · responsável · prazo*.")
        else:
            suffix = "Plano aqui na thread até 14h: *ação · responsável · prazo*."
        lines.append(f"👉 *Cobrança:* {cobranca} {suffix}")
    elif has_target:
        elogio = str(data.get("elogio") or "").strip() or ("CSAT e TMA dentro do esperado, bom trabalho, time."
                                                             if tma else "CSAT dentro do esperado, bom trabalho, time.")
        if not tma:
            elogio = re.sub(r"\s*(e|,)?\s*TMA[^.,;]*", "", elogio).strip() or "CSAT dentro do esperado, bom trabalho, time."
        lines.append(f"✅ *Destaque:* {elogio}")
    return title, "\n".join(lines).strip()


_LAST_BLOCK_DATA: dict[str, dict[str, Any]] = {}
REPORT_METAS_FROM_APP = os.getenv("REPORT_METAS_FROM_APP", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}


def _prepare_blocks(blocks: list[tuple[str, str]], day: date) -> list[tuple[str, str, str]]:
    """[(fila, título, corpo)] no layout fixo. Filas sem CSAT no D-1 ficam fora.
    Ordem: fora do alvo (maior gap de CSAT, depois maior excesso de TMA), no alvo, sem meta."""
    prepared = []
    for fila, text in blocks:
        data = _block_data_from_json(text) or _block_data_from_text(text)
        meta_mes = _meta_fila(fila, day)
        if meta_mes is not None and REPORT_METAS_FROM_APP:
            data["meta"] = meta_mes  # meta combinada do mês (a mesma de toda a Lyra)
        status = _block_status(data)
        if status == "sem_volume":
            continue
        rendered = _render_block(fila, data, day)
        if rendered is None:
            continue
        title, body = rendered
        _LAST_BLOCK_DATA[fila] = data
        tma = _tma_data(fila, data)
        tstatus = _tma_status(tma)
        csat_gap = (data["meta"] - data["d1"]) if status == "abaixo" else 0.0
        tma_excess = (tma["d1"] / tma["plan"] - 1) if tstatus == "acima" else 0.0
        off = status == "abaixo" or tstatus == "acima"
        order = 0 if off else (1 if (data.get("meta") is not None or tstatus == "ok") else 2)
        prepared.append((order, -csat_gap, -tma_excess, fila, title, body))
    prepared.sort(key=lambda item: item[:3])
    return [(fila, title, body) for *_, fila, title, body in prepared]


def _block_csat(fila: str, text: str) -> dict[str, float] | None:
    """D-1 e mês do bloco: "*93,5%* em D-1 … mês 94,6%" (aceita o formato antigo "Mês X% · D-1 Y%")."""
    d1 = _BLOCK_D1_RE.search(text or "") or _X_D1_AFTER_RE.search(text or "")
    if d1:
        mes = _BLOCK_MES_RE.search(text or "")
        mes_val = _to_float(mes.group(1)) if mes else None
        d1_val = _to_float(d1.group(1))
        return {"d1": d1_val, "mes": mes_val if mes_val is not None else d1_val}
    parsed = _parse_report_csat(text)
    return next(iter(parsed.values()), None) if parsed else None


def _report_blocks(value: str) -> list[dict[str, Any]]:
    """Estado do report: lista de blocos [{fila, ts, cobranca}] (aceita o formato antigo, só o ts)."""
    if not value:
        return []
    if value.startswith("["):
        try:
            data = json.loads(value)
            return [b for b in data if isinstance(b, dict) and b.get("ts")]
        except json.JSONDecodeError:
            return []
    return [{"fila": "", "ts": value, "cobranca": True}]


REPORT_NO_TMA_NOTE = ("TMA FORA DO REPORT HOJE: NÃO rode o SQL de TMA. Na Lyra Indicadores, peça os dados do report "
                      "diário SEM a seção TMA POR FILA (escreva 'TMA: não solicitado').")


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
    filas_tenant = _celulas_of(tenant.eps) if tenant.eps else list(TMA_PLAN)
    plan_lines = [f"- {f}: {_fmt_tempo(TMA_PLAN[f][0])}" for f in filas_tenant if f in TMA_PLAN]
    if not TMA_IN_REPORT:
        parts.append(REPORT_NO_TMA_NOTE)
    elif plan_lines:
        parts.append("PLAN DE TMA (TMA acima do plan = fora do alvo):\n" + "\n".join(plan_lines))
    parts.append("SE O TMA FALHAR OU VIER VAZIO: não devolva ERRO por causa do TMA. Deixe o TMA da fila como 'sem dado' "
                 "e siga com o CSAT; ERRO só se a consulta de CSAT falhar.")
    parts.append(DAILY_REPORT_PROMPT)
    return "\n\n".join(parts)


ESTEIRA_ENABLED = os.getenv("ESTEIRA_ENABLED", "0").strip() not in {"0", "false", "não", "nao"}
ESTEIRA_PILARES_EPS = {"operador", "tempo"}
_ESTEIRA_ORDER = ["Operador", "Tempo", "Política iFood", "Parceiro / logística", "Produto / sistema"]


def _esteira_prompt(tenant: Tenant, fila: str, gap: float, day: date) -> str:
    """Esteira do mês consolidado (dia 1 até D-1)."""
    return (
        f"{_scope_instruction(tenant.eps)}\n\n"
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Chame o subagente *Lyra Qualidade* com exatamente:\n"
        f"EPS: {tenant.eps or 'iFood'}\nPedido: esteira de impacto\nFila: {fila}\n"
        f"Período: mês ({day.replace(day=1).strftime('%d/%m')} a {day.strftime('%d/%m')})\n"
        f"Gap: {_bfmt(gap, 2)} p.p.\n\n"
        "Devolva SOMENTE o JSON que ela responder (ou a linha ERRO: que vier), sem comentar."
    )


# Metas de CSAT combinadas (out/2026 a mar/2027), por grupo de meta e mês. Mês fora da tabela: usa o mais próximo.
_META_MONTHS = [(2026, 10), (2026, 11), (2026, 12), (2027, 1), (2027, 2), (2027, 3)]
META_GRUPOS: dict[str, list[float]] = {          # Out, Nov, Dez, Jan, Fev, Mar
    "CX Suporte": [74, 74, 74, 75, 75, 75],
    "Review": [71, 72, 72, 73, 73, 74],
    "CX Madrugada": [53, 54, 55, 56, 57, 59],
    "Revisão Manual": [92, 92, 92, 92, 92, 93],
    "CX Super Cliente": [91, 92, 92, 92, 93, 93],
    "Super clientes PF": [97, 97, 97, 97, 97, 97],
    "PF Cancelamento": [91, 92, 92, 93, 93, 94],
    "BKO PF": [69, 70, 71, 72, 72, 73],
    "CX Denúncia": [68, 69, 70, 71, 71, 72],
    "Geral": [79, 79, 79, 80, 80, 81],
}
FILA_GRUPO_META = {
    "CX Suporte": "CX Suporte", "CX Review - AeC": "Review", "CX Review - CSU": "Review", "Madrugada": "CX Madrugada",
    "PF Revisão Manual": "Revisão Manual", "CX Super Cliente - AeC": "CX Super Cliente",
    "CX Super Cliente - CSU": "CX Super Cliente", "PF Super Clientes": "Super clientes PF",
    "PF Cancelamento": "PF Cancelamento", "CX Denúncia": "CX Denúncia",
    # BKO PF (tipo de atendimento BKO da query oficial, fora o CX Denúncia, que tem meta própria) — visão iFood
    "Payments Experts (G+A)": "BKO PF", "Recuperação de Conta": "BKO PF", "MPOS - Início (Bloqueio a realizar)": "BKO PF",
    "PF Account": "BKO PF",
}
# Metas combinadas com as EPSs por segmento (consolidado da EPS) e as filas de cada segmento.
META_EPS_SEGMENTO: dict[str, dict[str, list[float]]] = {
    "AeC": {"Alpha": [72, 72, 73, 73, 73, 74], "Super": [91, 92, 92, 92, 93, 93]},
    "CSU": {"Alpha": [76, 77, 78, 78, 79, 79], "Super": [91, 92, 92, 92, 93, 93], "Super PF": [97, 97, 97, 97, 97, 97]},
}
FILA_SEGMENTO = {
    "CX Suporte": "Alpha", "CX Review - AeC": "Alpha", "Madrugada": "Alpha", "CX Super Cliente - AeC": "Super",
    "CX Review - CSU": "Alpha", "PF Cancelamento": "Alpha", "PF Revisão Manual": "Alpha", "CX Denúncia": "Alpha",
    "CX Super Cliente - CSU": "Super", "PF Super Clientes": "Super PF",
}


def _meta_index(day: date | None = None) -> int:
    day = day or (_as_date(_today_brazil()) - timedelta(days=1))
    key = (day.year, day.month)
    if key in _META_MONTHS:
        return _META_MONTHS.index(key)
    return 0 if key < _META_MONTHS[0] else len(_META_MONTHS) - 1


def _meta_fila(fila: str, day: date | None = None) -> float | None:
    """Meta de CSAT da fila no mês (tabela combinada). None = fila sem meta (Fraudes DX, Contestações)."""
    grupo = FILA_GRUPO_META.get(fila) or next((g for f, g in FILA_GRUPO_META.items() if _norm_text(f) == _norm_text(fila)), None)
    return float(META_GRUPOS[grupo][_meta_index(day)]) if grupo else None


def _meta_segmento(eps: str, segmento: str, day: date | None = None) -> float | None:
    seg = (META_EPS_SEGMENTO.get(eps) or {}).get(segmento)
    return float(seg[_meta_index(day)]) if seg else None


def _metas_text(eps: str | None = None, day: date | None = None) -> str:
    """Bloco de metas do mês para os prompts (a Indicadores usa estas metas, não as antigas). Com EPS, só as dela."""
    i = _meta_index(day)
    filas_eps = set(_celulas_of(eps)) if eps else None
    filas = " · ".join(f"{f} {META_GRUPOS[g][i]:.0f}%" for f, g in FILA_GRUPO_META.items()
                       if filas_eps is None or f in filas_eps)
    segs = " · ".join(f"{e} {s} {v[i]:.0f}%" for e, d in META_EPS_SEGMENTO.items() for s, v in d.items()
                      if eps is None or _eps_matches(e, eps))
    sem_meta = " Fraudes DX e Contestações: sem meta." if eps is None or _eps_matches("CSU", eps) else ""
    geral = f" Meta geral do CX: {META_GRUPOS['Geral'][i]:.0f}%." if eps is None else ""
    return (f"METAS DE CSAT DO MÊS (combinadas; substituem qualquer meta antiga): {filas}.{sem_meta} "
            f"Metas combinadas da EPS por segmento: {segs}.{geral}")


class _MetasNow(dict):
    """Compatível com o antigo FILA_METAS: devolve a meta do mês corrente."""
    def get(self, key: Any, default: Any = None) -> Any:  # type: ignore[override]
        v = _meta_fila(str(key))
        return v if v is not None else default


FILA_METAS: dict[str, float] = _MetasNow()
ESTEIRA_MAX_POLLS = 72  # 12 min: a esteira não pode segurar a conversa
ESTEIRA_MIN_GAP_PP = 0.3  # abaixo disso o gap é pequeno demais para dividir em p.p.: mostra só %
_CAUSE_RE = re.compile(
    r"\b(efeito mix|variacao de mix|mix de motivo\w*|teve mix|tivemos (variacao de )?mix|mudou o mix)\b"
    r"|\bo que (voce )?(identific\w*|viu|explica|impact\w*|puxou|derrubou)\b.*\b(csat|gap|abaixo|meta|queda|caiu|pp|p p)\b"
    r"|\b(por que|porque|pq|motivo|motivos|causa|causas|explica|o que (esta|ta) puxando|de onde vem)\b.*"
    r"\b(csat|caiu|cai|caindo|piorou|queda|gap|detrator|detratores|ruim|abaixo)\b"
    r"|\b(csat|gap|detratores)\b.*\b(por que|porque|pq|causa|causas|motivo)\b"
)


_KNOWLEDGE_RE = re.compile(
    r"\b(clube|assinatura|estorno|estornar|reembolso|reembolsar|cobranca (duplicada|nao reconhecida)|ype|recolhimento|"
    r"cnl|m111|cliente nao localizado|voucher|cupom|retratacao|bko|backoffice|oraculo|rosie|will|wills|nexus|clubia|"
    r"agentforce|matriz de decisao|platina|vip|gold|silver|bronze|off-target|super cliente|pos-entrega|pos entrega|"
    r"item faltante|item errado|eta|allocating|one hub|politica|processo|fluxo de atendimento|pode cancelar|pode estornar)\b"
)


_DATA_WORDS_RE = re.compile(r"\b(csat|tma|tmi|nps|meta|plan|report|volume|quadrante|dispersao|operadores|ranking|"
                            r"grafico|planilha|excel|response rate|reabertura|sla|mop|span)\b")


_SPEAKER_CACHE: dict[str, str] = {}


def _first_name(user: str) -> str:
    """Primeiro nome da pessoa no Slack (cache em memória); vazio se não achar."""
    if not user:
        return ""
    _speaker_line({"user": user})
    return _SPEAKER_CACHE.get(user) or ""


def _speaker_line(event: dict[str, Any]) -> str:
    """Primeiro nome de quem está falando, para a Lyra conversar como gente (cache em memória)."""
    user = str(event.get("user") or "")
    if not user:
        return ""
    if user not in _SPEAKER_CACHE:
        nome = ""
        try:
            info = _resp_get(slack_app.client.users_info(user=user), "user", {}) or {}
            prof = info.get("profile") or {}
            nome = str(prof.get("display_name") or prof.get("real_name") or info.get("real_name") or "")
        except Exception:
            nome = ""
        nome = re.split(r"[\s._]", nome.strip())[0].capitalize() if nome.strip() else ""
        _SPEAKER_CACHE[user] = nome
    nome = _SPEAKER_CACHE.get(user) or ""
    return f"INFORMAÇÃO INTERNA PARA A LYRA: quem está falando com você é {nome}.\n\n" if nome else ""


# --- Base de processos (Repositório de Processos CX) + respostas do time ------------------------------------------
# O repositório (knowledge/repositorio_processos_cx.xlsx, troque o arquivo no GitHub para atualizar) é quebrado em
# trechos (uma linha de cada aba, com o nome das colunas) e buscado por palavra-chave (BM25). As respostas que o
# Gustavo/Michael dão nas threads em que a Lyra escalou entram na aba "Respostas do time" e na mesma busca.
KNOWLEDGE_XLSX = os.getenv("KNOWLEDGE_XLSX", os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge",
                                                          "repositorio_processos_cx.xlsx"))
KNOWLEDGE_SKIP_TABS = {"macros (case rules)", "atualizacoes repositorio", "figmas estudos & apresentacoes",
                       "voucher na camada de l3", "macro",
                       # informação interna do time: não entra na base de ninguém
                       "organograma do time", "matriz raci", "responsaveis por bu", "repositorio de habilidades",
                       "quem e o seu helio"}
KB_MAX_CHARS = int(os.getenv("KB_MAX_CHARS", "7000"))
TEAM_ANSWERS_TITLE = "Respostas do time"
TEAM_ANSWERS_HEADERS = ["Data", "EPS", "Pergunta", "Resposta", "Quem respondeu", "Thread", "Status"]
_KB: dict[str, Any] = {"chunks": None, "idf": {}, "avgdl": 1.0, "team": None, "team_at": 0.0}
_KB_LOCK = threading.Lock()
_KB_STOP = set("a o e de da do das dos em no na nos nas um uma para por com que se ao aos as os ou mais como "
               "qual quais quando onde porque pq nao sim ja tem ser esta sao foi pelo pela isso esse essa "
               "ele ela eles elas voce voces me meu minha seu sua the of".split())


_KB_PEOPLE_COL_RE = re.compile(r"respons|suporte nas valida|\bdono\b|criado por|modificado|focal")


def _kb_tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]{3,}|\b[a-z][0-9]\b", _norm_text(text)) if w not in _KB_STOP]


def _kb_load_repo() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    if not os.path.exists(KNOWLEDGE_XLSX):
        logger.warning("Repositório de processos não encontrado em %s", KNOWLEDGE_XLSX)
        return chunks
    import openpyxl
    wb = openpyxl.load_workbook(KNOWLEDGE_XLSX, read_only=True, data_only=True)
    for ws in wb.worksheets:
        if _norm_text(ws.title) in KNOWLEDGE_SKIP_TABS:
            continue
        all_rows = [[str(c).strip() if c is not None else "" for c in row] for row in ws.iter_rows(values_only=True)]
        # cabeçalho = entre as 15 primeiras linhas, a que tem mais células curtas (rótulos de coluna)
        best, h_idx = 0, -1
        for i, cells in enumerate(all_rows[:15]):
            short = [c for c in cells if c and len(c) < 80 and not re.fullmatch(r"[\d.,]+", c)]
            if len(short) >= 4 and len(short) > best:
                best, h_idx = len(short), i
        header: list[str] | None = None
        for i, cells in enumerate(all_rows):
            filled = [c for c in cells if c]
            if not filled:
                continue
            if i == h_idx:
                header = cells
                continue
            if _norm_text(filled[0]).startswith("responsavel"):
                continue  # linha "Responsável: <pessoa>": informação interna do time
            if header:
                parts = [f"{header[i] or '-'}: {c}" if i < len(header) and header[i] else c
                         for i, c in enumerate(cells) if c
                         and not (i < len(header) and _KB_PEOPLE_COL_RE.search(_norm_text(header[i])))]
            else:
                parts = filled
            text = " | ".join(p.replace("\n", " / ") for p in parts)[:1800]
            if len(text) >= 25:
                chunks.append({"aba": ws.title, "texto": text, "tok": _kb_tokens(f"{ws.title} {text}")})
    return chunks


def _kb_team_rows() -> list[dict[str, Any]]:
    if _KB["team"] is not None and time.time() - _KB["team_at"] < 300:
        return _KB["team"]
    rows: list[dict[str, Any]] = []
    google_client = _safe_google_client()
    if google_client is not None:
        try:
            ws = _ensure_worksheet(_open_spreadsheet(google_client), TEAM_ANSWERS_TITLE, TEAM_ANSWERS_HEADERS)
            for _, r in _worksheet_rows_with_header(ws):
                if _norm_text(r.get("Status")) in {"", "ativo"} and r.get("Resposta"):
                    txt = f"Pergunta: {r.get('Pergunta')} | Resposta do time iFood ({r.get('Quem respondeu')}): {r.get('Resposta')}"
                    rows.append({"aba": "Respostas do time", "texto": txt[:1800], "tok": _kb_tokens(txt)})
        except Exception:
            logger.warning("Could not read team answers", exc_info=True)
    _KB["team"], _KB["team_at"] = rows, time.time()
    return rows


def _kb_ready() -> list[dict[str, Any]]:
    with _KB_LOCK:
        if _KB["chunks"] is None:
            try:
                _KB["chunks"] = _kb_load_repo()
            except Exception:
                logger.exception("Could not load knowledge repository")
                _KB["chunks"] = []
            logger.info("Base de processos: %s trechos", len(_KB["chunks"]))
        return _KB["chunks"]


def _kb_search(query: str, k: int = 6) -> list[dict[str, Any]]:
    docs = _kb_ready() + _kb_team_rows()
    q = set(_kb_tokens(query))
    if not docs or not q:
        return []
    n = len(docs)
    df: dict[str, int] = {}
    for d in docs:
        for w in set(d["tok"]) & q:
            df[w] = df.get(w, 0) + 1
    avgdl = sum(len(d["tok"]) for d in docs) / n or 1.0
    scored = []
    for d in docs:
        tf: dict[str, int] = {}
        for w in d["tok"]:
            if w in q:
                tf[w] = tf.get(w, 0) + 1
        if not tf:
            continue
        dl = len(d["tok"]) or 1
        score = sum(math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5)) * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * dl / avgdl))
                    for w, f in tf.items())
        if d["aba"] == "Respostas do time":
            score *= 1.5  # o que o time já respondeu vale mais
        scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    return [d for sc, d in scored[:k] if sc > 0]


def _kb_context(query: str) -> str:
    """Trechos do Repositório de Processos CX e das respostas do time que tocam a pergunta."""
    try:
        hits = _kb_search(query)
    except Exception:
        logger.warning("KB search failed", exc_info=True)
        return ""
    if not hits:
        return ""
    out, total = [], 0
    for h in hits:
        piece = f"[{h['aba']}] {h['texto']}"
        if total + len(piece) > KB_MAX_CHARS:
            break
        out.append(piece)
        total += len(piece)
    return ("INFORMAÇÃO INTERNA PARA A LYRA — TRECHOS DA BASE DE PROCESSOS (Repositório de Processos CX e respostas que "
            "o time iFood já deu). Use se responderem a pergunta; se não responderem, ignore. Não invente além deles:\n"
            + "\n".join(out) + "\n\n")


# --- Pedido de treinamento: começa pelo problema da fila, não pela lista do Q4 --------------------------------------
_TRAINING_RE = re.compile(
    r"\bquem\b[^?]{0,40}\b(trein\w*|reciclag\w*|capacit\w*|feedback|acompanhar|desenvolver)\b"
    r"|\b(lista|prioridade|plano|sugest\w*|indica\w*)\b[^?]{0,20}\b(treinamento|reciclagem|capacitacao)\b"
    r"|\b(preciso|quero|vou|devo|bora)\b[^?]{0,20}\b(treinar|reciclar|capacitar)\b"
    r"|\b(tema|temas|assunto|assuntos|ponto|pontos|o que|foco)\b[^?]{0,30}\b(trein\w*|reciclag\w*|capacit\w*)\b"
    r"|\b(trein\w*|reciclag\w*|capacit\w*)\b[^?]{0,30}\b(focar|foco|priorizar|prioridade)\b")
TRAINING_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — PEDIDO DE TREINAMENTO da fila {fila}. Treinamento bom ataca um problema da "
    "operação; não entregue só a lista dos piores. Faça nesta ordem:\n"
    "1. *Problema:* chame a Lyra Indicadores para a fila {fila}: CSAT vs meta e os motivos de contato que mais tiram "
    "CSAT (impacto por motivo). Se o mês tiver menos de 10 dias, use os últimos 30 dias para ter amostra e diga isso.\n"
    "2. *Causa:* chame a Lyra Qualidade para os detratores desses motivos na fila: o que é do *Operador* (conduta, "
    "procedimento, comunicação) e o que não é (Política iFood, Parceiro/logística, Produto). Se o problema principal "
    "NÃO for do operador, diga com franqueza que treinamento não resolve e o que resolve.\n"
    "3. *Quem:* peça à Lyra Indicadores os operadores da fila com mais detratores nesses motivos (mínimo de 10 "
    "avaliações no período), com supervisor. Se a pessoa pediu lista nominal/completa, traga todos; se passar de 25, "
    "diga que manda a planilha completa e mostre os 10 primeiros.\n"
    "4. *Monte:* problema (com número) → o que treinar (conteúdo concreto, a partir dos comentários) → quem (nominal) → "
    "como medir (indicador e prazo, ex.: CSAT do motivo em 2 semanas).\n"
    "Motivo para treinar tem que IMPACTAR a operação: peso nas avaliações × distância (impacto negativo relevante em "
    "p.p.) — motivo com CSAT baixo e pouco volume NÃO entra.\n"
    "A resposta SEMPRE abre com a seção *Motivos ofensores*: os 3 motivos de contato que mais tiram CSAT da fila no "
    "período, cada um com participação nas avaliações, CSAT do motivo (n) e impacto em p.p. no CSAT da fila. Depois, "
    "cada tema de treinamento diz a qual motivo ofensor ele responde (tema sem motivo ligado só entra se o comentário "
    "mostrar o problema em vários motivos, e aí diga isso).\n"
    "Seja crítica: amostra pequena, operador com n baixo, ou causa fora do operador precisam ser ditos.\n\n")


_TRAINING_THEME_RE = re.compile(r"\b(will\w*|rosie|agentforce|macro\w*|tabula\w*|processo\w*|politica\w*|ferramenta\w*|"
                                r"sistema\w*|oraculo|bko|salesforce|matriz|cupo\w*|voucher\w*|cancelamento|reembolso|"
                                r"estorno|clube|script|procedimento\w*|fluxo\w*)\b")
TRAINING_THEME_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — TREINAMENTO DE TEMA ({tema}), não de CSAT da fila. O nominal é a lista de quem "
    "deve ser treinado NESSE tema. Quando a operação fala 'Will' sem dizer qual, é o Will de Negativas (pós-atendimento). "
    "Critério padrão do Will de Negativas: operador que marcou o caso como resolvido ANTES de acionar o Will (a "
    "pesquisa sobe ali e a nota fica com ele) — peça à Lyra Indicadores `Pedido: resolvido antes do Will` com "
    "`Lista: completa`. Faça assim:\n"
    "1. Entenda o uso certo: chame a Lyra Conhecimento sobre {tema} (como funciona, o que a operação deve fazer).\n"
    "2. Critério: a lista precisa de um critério objetivo de quem usa errado/não usa (ex.: casos elegíveis ao Will "
    "tratados manualmente, transbordo indevido, macro errada). Se a pessoa não disse o critério, NÃO monte lista pelo "
    "CSAT: pergunte em 1 mensagem curta qual é o critério (e qual Will/fluxo), sugerindo 2 opções concretas.\n"
    "3. Com o critério: peça à Lyra Indicadores os operadores que se encaixam, com n. Se ela não tiver esse dado, diga "
    "com franqueza qual dado falta e de onde viria — nunca substitua por ranking de CSAT.\n"
    "4. Feche com o conteúdo do treinamento (o uso certo, do passo 1) e como medir depois.\n\n")


def _training_question(eps: str | None) -> str | None:
    """Pergunta de volta, com dado: qual fila? Mostra as filas que mais tiram CSAT no mês."""
    try:
        rows = _scope_rows(_day_table() or [], eps)
    except Exception:
        rows = []
    items = []
    for r in rows:
        c, n, _ = _agg([r], "mes")
        imp = _impact(rows, [r], "mes") if len(rows) > 1 else None
        if c is not None and r.get("meta") and c < r["meta"]:
            items.append((imp if imp is not None else c - r["meta"], r, c, n))
    items.sort(key=lambda x: x[0])
    linhas = [f"• *{r['fila']}* · {_bfmt(c)}% contra meta {_bfmt(r['meta'])}% (n={_fmt_int(n)})"
              for _, r, c, n in items[:3]]
    base = ("Bora, mas antes me ajuda a mirar: treinamento que funciona ataca um problema específico, não só quem "
            "está no fim da lista. ")
    if linhas:
        return (base + "Pelo mês, quem mais está puxando o CSAT pra baixo é:\n" + "\n".join(linhas)
                + "\n\nQual fila você quer atacar? Com ela, eu levanto o motivo que mais gera detrator, se a causa é "
                  "mesmo do operador (ou é política/parceiro), quem concentra esses casos e o que treinar.")
    return (base + "Qual fila você quer atacar? Com ela, eu levanto o motivo que mais gera detrator, se a causa é "
                   "do operador, quem concentra esses casos e o que treinar.")


# "Nominal" no CX = a lista completa, nome por nome, de quem atende ao critério (não um top N).
_NOMINAL_RE = re.compile(r"\b(nominal|nominalmente|lista completa|todos os nomes|nome a nome|nome por nome)\b")
NOMINAL_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA: a pessoa pediu o NOMINAL — a lista nome a nome do recorte pedido, COMPLETA (não "
    "um top 10). O recorte vem da conversa: num pedido de treinamento, é a lista de quem deve ser treinado (pelo "
    "critério do treinamento); sem esse contexto (ex.: 'nominal da Review'), é a lista de TODOS os operadores daquela "
    "fila/EPS no período, com o resultado de cada um, ordenada do pior para o melhor e com o quadrante — não suponha "
    "que é treinamento. Cada linha: nome · e-mail · supervisor · fila · o número (com n). Se o recorte for ambíguo "
    "(qual indicador? qual período?), use CSAT do mês e diga o recorte usado. Se passar de 25 nomes, mostre os 10 "
    "primeiros e diga que a lista completa vai em planilha. Ao chamar a Lyra Indicadores, inclua a linha "
    "`Lista: completa` no pedido (sem ela, ela corta em 15).\n\n")


_ROSIE_EVAL_RE = re.compile(r"\b(avaliad\w*|avaliac\w*|nota\w*)\b[^?]{0,40}\brosie\b|\brosie\b[^?]{0,40}\b(avaliad\w*|avaliac\w*)\b")
ROSIE_EVAL_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA: pergunta sobre avaliações dadas na Rosie. Chame a Lyra Indicadores com "
    "`Pedido: avaliações na Rosie` (seção 7.1b dela: avaliação anterior à primeira atribuição a analista), com a fila e "
    "o período que a conversa já trouxe (ex.: CX Suporte, outubro fechado) — se não houver, EPS do canal no mês. Responda a "
    "representatividade (avaliações na Rosie ÷ total, com n), o CSAT delas e o CSAT da fila sem elas. Diga em meia "
    "frase o critério usado (horário da avaliação x horário da atribuição ao analista) e o porquê: a pesquisa só sobe "
    "quando o caso muda para resolvido, e às vezes (não é regra, mas acontece) a Rosie marca resolvido e transborda — a nota fica "
    "com o analista, último proprietário do ticket. Se o peso for relevante, diga que isso é do fluxo da Rosie (iFood), "
    "não da EPS, e que tirar essas notas da régua é decisão do time iFood.\n\n")


# "equipe pior em TMA e CSAT": cruza os dois indicadores por equipe
_COMBO_RE = re.compile(r"(?=.*\btma\b)(?=.*\bcsat\b)(?=.*\b(equipe\w*|supervisor\w*|time|times|operador\w*|analista\w*)\b)")
COMBO_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA: a pessoa quer cruzar CSAT e TMA por equipe. Peça à Lyra Indicadores, para a fila e o "
    "período (mês, se não disser), por equipe (supervisor do MOP): CSAT com n e TMA. Compare o CSAT com a META da fila e "
    "o TMA com o PLAN da fila (os dois estão nos números oficiais deste contexto — não diga que não tem o plan). Responda: "
    "(1) as equipes ruins NOS DOIS (CSAT abaixo da meta E TMA acima do plan), da pior para a melhor; (2) se nenhuma for "
    "ruim nos dois, a pior em cada um, dizendo que são equipes diferentes; (3) o tamanho do desvio de cada uma "
    "(p.p. e segundos). Operadores sem supervisor no MOP não são uma equipe: chame de 'sem supervisor cadastrado no MOP' "
    "e aponte como lacuna de cadastro, fora do ranking.\n"
    "Se a pergunta for por ANALISTA/OPERADOR (não por equipe), siga a regra de TMA POR ANALISTA abaixo.\n\n")


# TMA por analista: o dado existe (entradas_filas tem o e-mail de quem atendeu) — nunca dizer que só há por fila
_ANALYST_TMA_RE = re.compile(r"(?=.*\btma\b)(?=.*\b(analista\w*|operador\w*|atendente\w*|agente\w*)\b)")
ANALYST_TMA_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — TMA POR ANALISTA: o TMA EXISTE por analista. Peça à Lyra Indicadores "
    "`Pedido: TMA por analista` (seção 7.1d dela), com o período da conversa (mês até D-1, se não disser) e, se a conversa "
    "já trouxe uma lista de operadores, a linha `Só estes operadores (e-mails): ...`. Nunca responda que o TMA só existe "
    "por fila. Para 'quem mais impacta': impacto no TMA da EPS em segundos (tirar o analista e ver para onde iria o "
    "TMA), do maior para o menor; compare cada um com o TMA da fila pela mesma régua e com o plan da fila. Traga também "
    "o TMA consolidado da EPS (sai do SQL oficial — nunca diga que não está disponível). Se a pergunta cruza CSAT e TMA, "
    "faça os dois rankings por analista (top 3 de cada, como pedido) e diga quem aparece nos dois.\n\n")


# "desses mesmos operadores": a lista é a da resposta anterior, inteira
_SAME_SET_RE = re.compile(r"\b(mesm[oa]s|desses|destes|dessas|destas|esses|estes|essas|estas)\s+(\w+\s+)?"
                          r"(operador\w*|analista\w*|atendente\w*|pessoas|nomes|agentes)\b")
SAME_SET_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA: a pessoa se refere aos MESMOS operadores de uma resposta anterior desta conversa. "
    "Pegue os e-mails dessa resposta e peça à Lyra Indicadores só eles (`Só estes operadores (e-mails): ...`) com "
    "`Lista: completa` — mostre TODOS, um por um, sem corte de 15. Quem não atingir o mínimo de avaliações aparece no "
    "fim com '(amostra pequena, n=X)'; quem não tiver avaliação no período aparece como 'sem avaliações no período'.\n\n")


CHAT_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA: esta é uma mensagem de conversa, não um pedido de análise. Responda como você "
    "(seção Personalidade): gente do time, bem-humorada quando couber (uma tirada, no máximo), sem frase de robô. "
    "Até 3 linhas, SEM chamar subagentes e SEM consultar dados. Se precisar de número, use só os números "
    "oficiais já enviados neste contexto (tabela do dia). Se a pessoa quiser algo que precisa de análise, diga em 1 "
    "frase o que você pode trazer e pergunte qual ela quer.\n\n")
_FILA_HINT_RE = re.compile(r"\b(review|super|vip|suporte|denuncia|madrugada|fila|filas|operador\w*|equipe|supervisor\w*|"
                           r"causa\w*|plano|acao|acoes|detrator\w*|promotor\w*|semana|mes|ontem|hoje)\b")


def _is_small_talk(question: str) -> bool:
    """Mensagem curta sem pedido de dado, análise ou processo (ex.: 'tudo bem?', 'valeu', 'o que você acha?')."""
    t = _norm_text(question)
    return (0 < len(t.split()) <= 12 and not _DATA_WORDS_RE.search(t) and not _FILA_HINT_RE.search(t)
            and not _DEFINITION_RE.search(t)
            and not _is_analytical(question) and not _is_plan_request(question) and not _is_knowledge_question(question)
            and not re.search(r"\d", t))


_DEFINITION_RE = re.compile(r"\b(o que (e|eh|significa|quer dizer|faz)|quem e (o|a)|como funciona|significa|"
                            r"qual a diferenca|o que sao)\b")


def _is_knowledge_question(question: str) -> bool:
    """Dúvida de processo/política/agente de IA: a resposta vem da Lyra Conhecimento, não de dado nem de chute."""
    text = _norm_text(question)
    if _DEFINITION_RE.search(text) and not _DATA_WORDS_RE.search(text):
        return True  # "o que é o Almir?", "o que significa NCPO?": base de processos + Conhecimento
    if _DATA_WORDS_RE.search(text):  # "CSAT da Super Cliente", "TMA do VIP": é dado, não processo
        return False
    return bool(_KNOWLEDGE_RE.search(text)) and not _is_cause_request(question)


_CLUBE_RE = re.compile(r"\b(clube|assinatura|turbine|payer|payer_id|fingerprint|spotify|decolar|uber one|uber|santander|"
                       r"sympla|crm bonus|easy live|youtube premium|amazon prime|mec)\b")


def _is_clube_question(question: str) -> bool:
    return bool(_CLUBE_RE.search(_norm_text(question)))


CLUBE_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA: este é um assunto de Clube iFood. Chame a *ClubIA* com a pergunta completa "
    "(e todos os dados que a pessoa mandou: payer_id, valor, data, 4 últimos dígitos) e devolva a resposta dela como "
    "veio (📥 Dados coletados / ⚡ Ação para operações), sem cortar validações, textos rápidos e macros. NÃO chame a "
    "Lyra Conhecimento para Clube e não complete com conhecimento geral.\n\n"
)

_IDENTITY_RE = re.compile(r"\b(quem (e|eh) (voce|vc|tu|a lyra)|quem (e|eh) a lyra|o que (voce|vc) faz|o que a lyra faz|"
                          r"(por que|pq|porque) (o nome |seu nome |o seu nome )?lyra|de onde vem (o nome|seu nome)|"
                          r"se apresenta|apresente se|me fala de voce|fala sobre voce|de onde (voce|vc|a lyra) (veio|vem|surgiu)|"
                          r"quem (te )?(criou|fez|construiu|desenvolveu)|quem criou a lyra|como (voce|vc) (surgiu|nasceu)|"
                          r"(qual|me conta) (e )?(a )?(sua )?historia|o que significa lyra|significado (do nome|de lyra))\b")


_SELF_TOPIC_RE = re.compile(r"\b(constelacao|vega|orfeu|lira|seu nome|teu nome|nome lyra|aprende\w*|feedbacks?|memoria|"
                            r"lembra\w*|criou|criada|criado|robo|bot|ia|inteligencia artificial|agente|funciona|"
                            r"consegue fazer|sabe fazer|limitac\w*|erra|errou|treinad\w*|seus dados|de onde (tira|vem) (os|seus))\b")
_SELF_REF_RE = re.compile(r"\b(voce|vc|tu|te|seu|sua|seus|suas|lyra)\b")


def _is_identity_question(question: str) -> bool:
    """Pergunta sobre a própria Lyra (quem é, origem do nome, como aprende, o que faz, limites). Nunca vai para a
    base de processos."""
    t = _norm_text(question).replace("-", " ")
    if _IDENTITY_RE.search(t):
        return True
    return bool(_SELF_TOPIC_RE.search(t)) and (bool(_SELF_REF_RE.search(t)) or len(t.split()) <= 4)


def _identity_thread(event: dict[str, Any], question: str) -> bool:
    """Continuação curta numa thread que começou com "quem é você?" ("e a constelação?")."""
    thread_ts = str(event.get("thread_ts") or "")
    if not thread_ts or thread_ts == str(event.get("ts") or "") or len(_norm_text(question).split()) > 8:
        return False
    try:
        root = next((m for m in _fetch_thread(str(event.get("channel") or ""), thread_ts) if m.get("ts") == thread_ts), {})
    except Exception:
        return False
    return _is_identity_question(_strip_mentions(str(root.get("text") or "")))


IDENTITY_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — APRESENTAÇÃO: a pessoa quer saber quem você é. Responda sem chamar subagente, "
    "em até 6 linhas, tom leve e próximo:\n"
    "1) Você é a Lyra, a primeira agente que faz a gestão de EPS no iFood CX (hoje AeC e CSU): acompanha resultado, "
    "cobra e critica plano de ação, registra compromissos e cuida da governança, para o time focar no estratégico sem "
    "perder a governança das EPSs. Na apresentação completa, diga em meia frase que você aprende com o time do iFood. "
    "Se perguntarem de onde você veio ou quem te criou: você foi criada pelo time de CX "
    "do iFood, que gere as EPSs, para assumir o dia a dia dessa gestão (não diga que não sabe e não mande para o One Hub).\n"
    "2) O nome: Lyra (Lira) é a constelação da lira de Orfeu, o músico da mitologia grega que encantava tudo com a sua "
    "música. A estrela mais brilhante dela é a Vega, uma das mais brilhantes do céu, que já foi a estrela-guia do norte "
    "e volta a ser daqui a uns 12 mil anos. Como a lira, você afina vários instrumentos juntos (seus especialistas de "
    "indicadores, qualidade, processos, Clube e crises); como a Vega, ajuda a operação a se orientar.\n"
    "Se a pergunta for sobre um ponto específico (o nome, a constelação, como você aprende, o que você faz, de onde vêm "
    "seus números, seus limites), responda SÓ esse ponto, em 2 a 4 linhas, usando o que está aqui:\n"
    "• Como você aprende: você aprende com o time do iFood. Quem é do iFood pode te corrigir ou ensinar direto na "
    "conversa (ex.: \"da próxima vez traz o n junto do CSAT\", \"não chama de ofensor, chama de Q4\"): você anota e "
    "passa a usar nas próximas conversas. Dá para ver o que você aprendeu (\"o que você aprendeu?\") e tirar um "
    "aprendizado. Meta, regra de cálculo e política não mudam por aprendizado: são regras do iFood. Mudanças maiores "
    "(coisas novas que você passa a fazer) vêm do time de CX que cuida de você.\n"
    "• De onde vêm seus números: das bases oficiais de atendimento do iFood (as mesmas do Cockpit do time), do MOP e "
    "dos controles que as EPSs postam. Você não inventa número: o que não tem, você diz que não tem.\n"
    "• Limites: você não decide política nem compensação (isso é do iFood), não pune ninguém e não fala de uma EPS no "
    "canal da outra.\n"
    "NUNCA responda pergunta sobre você com 'não sei' nem mande para o One Hub.\n"
    "3) Na apresentação completa, feche com 2 ou 3 exemplos curtos do que a pessoa pode te pedir (ex.: \"como está a CX Suporte ontem?\", "
    "\"quem são os reincidentes da AeC?\", \"teve crise ontem?\").\n\n"
)

KNOWLEDGE_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA: esta é uma dúvida de processo, política ou agente de IA. Se vieram TRECHOS DA BASE "
    "DE PROCESSOS neste contexto e eles respondem, responda com eles (são o Repositório de Processos CX oficial e "
    "respostas do time). Senão, chame o subagente "
    "*Lyra Conhecimento* com `Pedido: <a pergunta, completa>` (uma chamada por pergunta, se houver mais de uma) e "
    "responda com o que ela devolver. NÃO use outra busca nem conhecimento geral (CDC, \"geralmente\", outras empresas). "
    "Responda SÓ a pergunta atual (não repita ressalvas de perguntas anteriores da conversa). Se a base não tiver a "
    "resposta ou faltar a condição pedida: diga em 1 frase o que a base traz e o que não traz, a referência (One Hub / "
    "Matriz CX), SEM prometer 'vou confirmar', e termine com uma linha final `ESCALAR: experiencia: <a dúvida em 1 "
    "linha>` (política, processo de atendimento, CSAT) ou `ESCALAR: eficiencia: <a dúvida>` (TMA, SLA, fila, "
    "ferramentas). O app chama a pessoa certa do time.\n\n"
)


_PLAN_RE = re.compile(r"\b(sugir\w*|sugere|sugestao|sugestoes|monta|monte|montar|cria|crie|criar|estrutur\w*|propo\w*|"
                      r"me ajuda|ajuda a|ideia|ideias|o que (eu )?(faco|fazer|podemos fazer))\b.*\b(acao|acoes|plano|planos)\b"
                      r"|\b(acao|acoes|plano)\b.*\b(sugir\w*|sugere|sugestao|ideia)"
                      r"|\b(como|o que)\b.*\b(melhorar|melhoro|melhoramos|recuperar|subir|aumentar|atacar|resolver)\b.*"
                      r"\b(csat|resultado|nota|fila|tma|sla)\b")


def _is_plan_request(question: str) -> bool:
    return bool(_PLAN_RE.search(_norm_text(question)))


PLAN_MAX_POLLS = 48  # 8 min: depois disso, plano rápido com os números da tabela do dia


def _plan_fila_row(question: str, eps: str | None) -> dict[str, Any] | None:
    fila = _fila_in_question(question, eps) or _fila_in_question(question, None)
    if not fila:
        return None
    rows = _day_table(fetch=False) or []
    return next((r for r in rows if _norm_text(r["fila"]) == _norm_text(fila)), None)


def _plan_context(question: str, eps: str | None) -> str:
    """Pedido de plano: os números da fila já vão prontos (tabela do dia), para a Lyra não gastar consulta com eles."""
    r = _plan_fila_row(question, eps)
    if not r:
        return ""
    c, n, _ = _agg([r])
    if c is None:
        return ""
    return ("INFORMAÇÃO INTERNA PARA A LYRA — NÚMEROS DA FILA (oficiais, já calculados; NÃO chame a Lyra Indicadores para "
            f"eles): {r['fila']} ({r['eps']}) no mês: CSAT {_bfmt(c)}% (n={_fmt_int(n)}), meta {_bfmt(r['meta'])}%"
            + (f", motivo que mais tira: {r['motivo']} ({_bfmt(r['motivo_pp'], 2)} p.p.)" if r.get("motivo") else "")
            + ". Para o plano, chame só a *Lyra Qualidade* com `Pedido: plano de ação` (fila e motivo acima) e, se alguma "
            "ação tocar política (compensação, cupom, estorno, cancelamento), a *Lyra Conhecimento*.\n\n")


def _plan_fallback_prompt(question: str, eps: str | None) -> str:
    """Plano rápido sem subagentes, quando a análise completa estoura o tempo."""
    r = _plan_fila_row(question, eps)
    dados = ""
    if r:
        c, n, _ = _agg([r])
        dados = (f"Fila {r['fila']} ({r['eps']}) no mês: CSAT {_bfmt(c)}% (n={_fmt_int(n)}), meta {_bfmt(r['meta'])}%"
                 + (f", motivo que mais tira: {r['motivo']}" if r.get("motivo") else "") + ".")
    return (f"{_scope_instruction(eps)}\n\nINFORMAÇÃO INTERNA PARA A LYRA: responda SEM chamar subagentes, em até 8 "
            "linhas, um plano de ação inicial para a pergunta abaixo, usando só os números dados (não invente outros). "
            "No máximo 3 ações da operação (o quê · para quem · responsável · prazo · como medir), sem política nem "
            "compensação, sem RH. Termine dizendo que a análise detalhada por pilar (causa raiz) pode ser pedida em "
            "seguida.\n" + (f"Dados: {dados}\n" if dados else "") + f"Pergunta: {question}")


PLAN_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA: pedido de sugestão de plano de ação. Antes de responder, chame a *Lyra Conhecimento* "
    "com `Pedido: quais fluxos e políticas valem para <o motivo/problema da fila> e o que é decisão da operação x do iFood` "
    "e siga as regras de plano do seu prompt: nenhum passo de compensação/voucher/cupom/estorno/cancelamento fora da matriz "
    "de decisão; causa só a que o dado mostra (use a Leitura do report desta thread; FORA de uma thread de report, NÃO peça a Leitura nem o motivo para a pessoa: busque você mesma — chame a *Lyra Indicadores* com `Pedido: problema da fila` (motivo de maior impacto no mês e no D-1, quadrantes e dispersão) e a *Lyra Qualidade* com `Pedido: plano de ação` — e monte o plano em cima disso, dizendo o recorte usado); número no recorte certo (fila x motivo); "
    "interações por ticket não é reabertura nem FCR; régua nova só como 'sugestão a validar'; não diga que tem/segue planilha "
    "ou arquivo; nada de sanção ou RH. No máximo 3 ações (o quê · quem · prazo · como medir), curtas.\n\n"
)

_FILE_WORDS_RE = re.compile(r"(planilha|arquivo|excel|\.xlsx|\.csv|\.pdf|\.pptx|anexo)", re.IGNORECASE)
_FILE_PROMISE_RE = re.compile(r"\b(tem uma|tenho uma|segue|seguem|anexei|anexo|te mandei|te enviei|enviei|mandei|"
                              r"deixei|preparei|montei|gerei|disponivel|baixar|se quiser)\b")


def _strip_file_promises(answer: str) -> str:
    """O modelo às vezes diz que 'tem uma planilha' que ninguém gerou: quem manda arquivo é o app. Tira essas linhas."""
    if not answer:
        return answer
    kept = [line for line in answer.split("\n")
            if not (_FILE_WORDS_RE.search(line) and _FILE_PROMISE_RE.search(_norm_text(line)))]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip() if len(kept) != len(answer.split("\n")) else answer


def _is_cause_request(question: str) -> bool:
    return bool(_CAUSE_RE.search(_norm_text(question)))


_MIX_ONLY_RE = re.compile(r"\bmix\b")
_ESTEIRA_REQ_RE = re.compile(r"\b(esteira|esteia|estera|esteria|esteiras|cascata)\b(?!.*\bcomo funciona\b)")
# "quais motivos mais pesam no CSAT por frente/fila": ranking de motivos, não análise de queda
_MOTIVOS_RE = re.compile(r"\bmotivos?\b.*\b(mais pesam|pesam|pesa|mais impactam|impactam|ofensor\w*|maior impacto|"
                         r"mais tiram|tiram|derrubam|puxam|mais detrat\w*)\b|\bmotivos? ofensor\w*|\bofensor\w* d[eo] csat\b")
_EFICIENCIA_RE = re.compile(r"\b(tma|sla|primeira resposta)\b")
EFICIENCIA_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — RESULTADO DE EFICIÊNCIA (TMA e/ou SLA de 1ª resposta). Peça à Lyra Indicadores, "
    "no período da pergunta (padrão: mês até D-1): TMA oficial por célula pelo SQL da seção 7.1 dela (com tratados e o "
    "consolidado da EPS) e/ou SLA de 1ª resposta por célula pela regra oficial da seção 7 dela (base entradas_filas — "
    "nunca diga que o SLA não está disponível por causa de outra tabela). Responda uma linha por fila (nome em código): "
    "TMA <s> s x plan <s> s (desvio) · <tratados> tratados | SLA <x,x>% x meta <m>% · <interações> interações. Feche "
    "com o consolidado da EPS e 1 linha dizendo qual fila mais preocupa e por quê.\n\n")
TRAINING_EFIC_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — TREINAMENTO PARA {ind}. Os DADOS abaixo já são os motivos de contato que IMPACTAM "
    "a operação nesse indicador (pesam em horas de operação ou em interações fora do prazo além da média da célula). "
    "Use SÓ esses motivos — nunca indique motivo só por ter número ruim com pouco volume. Abra com a seção *Motivos "
    "ofensores* copiando os números dos DADOS (até 3 por fila). Depois, para cada motivo, o tema de treinamento: o que "
    "treinar, concreto e ligado ao motivo (TMA: roteiro e decisão mais rápida, quando encerrar, consulta de status; SLA: "
    "primeira resposta e priorização na entrada), quem (se pedirem nominal: Lyra Indicadores `TMA por analista` ou `SLA "
    "por operador`) e como medir (o indicador do motivo em 2 semanas). Pode chamar a Lyra Qualidade para ler conversas "
    "desses motivos e dar exemplos. Curto, sem inventar número.\n\n")
MOTIVOS_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — MOTIVOS QUE MAIS PESAM NO CSAT. 'Frente' = fila (célula) da EPS; se a conversa "
    "indicar segmento (Alpha/Super) ou BU, agrupe assim e diga o agrupamento usado. Peça à Lyra Indicadores, para cada "
    "fila da EPS (período: mês até D-1, salvo se a pessoa disser outro), os 3 motivos de contato com maior impacto "
    "negativo (seção 6 dela): participação nas avaliações, CSAT do motivo (n) e impacto em p.p. no CSAT da fila. "
    "Responda um bloco curto por fila (nome da fila em código), da fila mais longe da meta para a mais perto, e feche "
    "com 1 linha: o motivo que aparece em mais filas. NÃO faça análise de variação nem esteira.\n\n")
_D1_RE = re.compile(r"\b(ontem|d ?- ?1|d1|dia anterior)\b")


def _d1_context(question: str, event: dict[str, Any]) -> bool:
    """A conversa é sobre ontem (D-1)? Pela pergunta ou, se ela não disser o período, pelo que veio antes na thread."""
    q = _norm_text(question)
    if _D1_RE.search(q):
        return True
    if re.search(r"\b(mes|semana|novembro|outubro|dezembro|janeiro|mtd)\b", q) or not event.get("thread_ts"):
        return False
    try:
        ctx = _norm_text(_thread_context(event)[-2500:])
    except Exception:
        return False
    d1 = [m.start() for m in _D1_RE.finditer(ctx)]
    mes = [m.start() for m in re.finditer(r"\b(mes|mtd)\b", ctx)]
    return bool(d1) and (not mes or d1[-1] > mes[-1])


def _above_meta_note(fila: str | None, eps: str | None, kind: str) -> str | None:
    """Fila que bateu a própria meta no período: explica que o impacto negativo no consolidado é de peso (fila de meta
    baixa), não de desempenho, e aponta quem ficou abaixo da própria meta. None = fila abaixo da meta (segue a análise)."""
    if not fila:
        return None
    try:
        rows = _day_table() or []
    except Exception:
        return None
    row = next((r for r in rows if r.get("fila") == fila), None)
    if not row or row.get("meta") is None or not row.get(f"{kind}_aval"):
        return None
    c, n, _ = _agg([row], kind)
    if c is None or c < row["meta"]:
        return None
    conj = [r for r in rows if r.get("eps") == row.get("eps")]
    total, n_tot, meta_cons = _agg(conj, kind)
    imp = _impact(conj, [row], kind) if len(conj) > 1 else None
    per = "ontem" if kind == "d1" else "no mês"
    linhas = [f"`{fila}` não foi mal pra régua dela: {per} fez {_bfmt(c)}% (n={_fmt_int(n)}), acima da meta de "
              f"{_fmt_meta(row['meta'])}%."]
    if imp is not None and imp < 0 and meta_cons is not None:
        linhas.append(f"O impacto de {f'{imp:+.2f}'.replace('.', ',').replace('-', '−')} p.p. "
                      f"no consolidado da {row.get('eps')} é de peso, não de desempenho: a meta dela é bem mais baixa que a "
                      f"consolidada ({_bfmt(meta_cons)}%), então na régua de impacto ela sempre aparece puxando pra baixo "
                      f"quando tem volume.")
    abaixo = []
    for r in conj:
        rc, rn, _ = _agg([r], kind)
        if rc is not None and r.get("meta") is not None and rc < r["meta"] and n_tot:
            abaixo.append((rn / n_tot * (rc - r["meta"]), r["fila"], rc, rn, r["meta"]))
    abaixo.sort()
    if abaixo:
        linhas.append(f"Quem ficou abaixo da própria meta {per}: " + "; ".join(
            f"`{f}` {_bfmt(rc)}% x {_fmt_meta(m)}% (n={_fmt_int(rn)})" for _, f, rc, rn, m in abaixo[:3])
            + ". Quer que eu abra a causa de alguma delas?")
    else:
        linhas.append(f"Todas as filas da {row.get('eps')} bateram a própria meta {per}.")
    return "\n".join(linhas)
_SEGMENT_SUPER_RE = re.compile(r"\b(super|super cx|cx super|vip|platin\w*)\b")


def _fila_ref(question: str, eps: str | None, event: dict[str, Any]) -> str | None:
    """Fila da pergunta: citada no texto; 'Super' = a fila Super Cliente da EPS; senão a última fila citada na thread
    ('nesse segmento', 'essa fila')."""
    fila = _fila_in_question(question, eps)
    if fila:
        return fila
    candidates = _celulas_of(eps) if eps else [f for cel in EPS_CELULAS.values() for f in cel]
    qn = _norm_text(question)
    for palavra, chave in (("review", "review"), ("suporte", "suporte"), ("madrugada", "madrugada"),
                           ("denuncia", "denuncia"), ("cancelamento", "cancelamento"), ("revisao", "revisao manual"),
                           ("fraude", "fraudes")):
        hits = [f for f in candidates if chave in _norm_text(f)]
        if re.search(rf"\b{palavra}\w*", qn) and len(hits) == 1:
            return hits[0]
    supers = [f for f in candidates if "super cliente" in _norm_text(f)]
    if _SEGMENT_SUPER_RE.search(qn) and len(supers) == 1:
        return supers[0]
    if not event.get("thread_ts"):
        return None
    try:
        ctx = _norm_text(_thread_context(event)[-3000:])
    except Exception:
        return None
    best, pos = None, -1
    for f in candidates:
        i = ctx.rfind(_norm_text(f))
        if i > pos:
            best, pos = f, i
    if len(supers) == 1:
        m = list(re.finditer(r"\b(super|platin\w*|vip)\b", ctx))
        if m and m[-1].start() > pos:
            best = supers[0]
    return best


def _fila_in_question(question: str, eps: str | None) -> str | None:
    candidates = _celulas_of(eps) if eps else [f for cel in EPS_CELULAS.values() for f in cel]
    text = _norm_text(question)
    hits = [f for f in candidates if _norm_text(f) in text]
    if hits:
        return max(hits, key=len)
    return _match_fila(question, candidates) if candidates else None


def _esteira_on_demand_prompt(eps: str | None, fila: str, day: date, d1_only: bool) -> str:
    meta = FILA_METAS.get(fila)
    periodo = f"D-1 {day.strftime('%d/%m')}" if d1_only else f"mês ({day.replace(day=1).strftime('%d/%m')} a {day.strftime('%d/%m')})"
    return (
        f"{_scope_instruction(eps)}\n\n"
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Chame o subagente *Lyra Qualidade* com exatamente:\n"
        f"EPS: {eps or 'iFood'}\nPedido: esteira de impacto\nFila: {fila}\nPeríodo: {periodo}\n"
        + (f"Meta: {_fmt_meta(meta)}%\nGap: calcule (meta − CSAT da fila no período; 0 se estiver na meta) e devolva no campo \"gap\"\n"
           if meta is not None else "Gap: 0\n")
        + "\nDevolva SOMENTE o JSON que ela responder (ou a linha ERRO: que vier), sem comentar."
    )


_N3_LINE_RE = re.compile(r"^.*(ESCALAR\s*N3\s*:|\b(sinaliz\w*|levar|encaminh\w*)\b[^\n]{0,60}\b(revis[aã]o\s+)?N3\b).*$",
                         re.I | re.M)


def _route_n3_flags(answer: str, origem: str, event: dict[str, Any] | None = None) -> str:
    """Sinal sensível (discriminação, fraude, assédio...) NÃO vai na thread: sai da resposta e vai por alerta privado
    para o time (com o que a Lyra viu e os tickets), para o N3 avaliar."""
    text = str(answer or "")
    # bloco "⚠️ Sinalização N3" com o conteúdo em bullets nas linhas seguintes: sai o bloco inteiro
    lines, keep, flags, i = text.splitlines(), [], [], 0
    while i < len(lines):
        line = lines[i]
        if _N3_LINE_RE.match(line):
            flags.append(line.strip())
            i += 1
            while i < len(lines) and re.match(r"\s*([•\-–*]|\d+[.)])\s+", lines[i]):
                flags.append(lines[i].strip())
                i += 1
            continue
        keep.append(line)
        i += 1
    if not flags:
        return text
    text = "\n".join(keep)
    link = ""
    if event:
        link = _permalink(str(event.get("channel") or ""), str(event.get("thread_ts") or event.get("ts") or ""))
    itens = [re.sub(r"^[•\-–*\s]+", "", re.sub(r"(?i)ESCALAR\s*N3\s*:\s*", "", f)) for f in flags[:8]]
    itens = [i for i in itens if i and not re.fullmatch(r"\W*\*?\s*sinaliza\w*\s+N3\s*\*?\W*", i, re.I)]
    _alert("🚨 *Para o N3 avaliar* — " + origem + (f" (<{link}|conversa>)" if link else "") + "\n"
           + "\n".join("• " + i for i in itens))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _post_esteira_on_demand(event: dict[str, Any], eps: str | None, question: str) -> bool:
    """Pergunta de causa ('por que o CSAT caiu?'): posta a esteira de impacto da fila na thread. True = postou."""
    block = _report_block_for(str(event.get("channel") or ""), str(event.get("thread_ts") or ""))
    fila = block[1].get("fila") if block else _fila_ref(question, eps, event)
    if not fila:
        return False
    text_q = _norm_text(question)
    d1_only = bool(re.search(r"\b(ontem|d-1|d1|dia anterior)\b", text_q)) and "mes" not in text_q
    day = _today_brazil().date() - timedelta(days=1)
    try:
        answer = ask_toqan(_esteira_on_demand_prompt(eps, fila, day, d1_only), max_attempts=ESTEIRA_MAX_POLLS)
        answer = _route_n3_flags(answer, f"esteira de `{fila}` ({eps or 'iFood'})", event)
        if _is_error_answer(answer):
            return False
        data = _block_data_from_json(answer) or {}
        gap = _num(data.get("gap")) or 0.0
        text = _render_esteira(data, gap, periodo="do D-1" if d1_only else "do mês", fila=fila)
        if not text:
            return False
        _post_sections(str(event.get("channel") or ""), text, thread_ts=_reply_ts(event))
        return True
    except Exception:
        logger.exception("On-demand esteira failed (%s)", fila)
        return False


def _variation_periods(question: str) -> tuple[tuple[date, date], tuple[date, date], str, str]:
    """(período atual, referência, rótulo atual, rótulo referência). Padrão: mês até D-1 x mês anterior até o mesmo dia."""
    d1 = _today_brazil().date() - timedelta(days=1)
    text = _norm_text(question)
    fmt = lambda a, b: f"{a.strftime('%d/%m')}–{b.strftime('%d/%m')}" if a != b else a.strftime("%d/%m")
    if re.search(r"\b(ontem|d-1|d1|dia anterior)\b", text):
        ref = (d1.replace(day=1), d1 - timedelta(days=1)) if d1.day > 1 else (d1 - timedelta(days=7), d1 - timedelta(days=1))
        return (d1, d1), ref, f"D-1 ({fmt(d1, d1)})", f"mês até D-2 ({fmt(*ref)})"
    if re.search(r"\bsemana\b", text):
        cur = (d1 - timedelta(days=6), d1)
        ref = (d1 - timedelta(days=13), d1 - timedelta(days=7))
        return cur, ref, f"últimos 7 dias ({fmt(*cur)})", f"7 dias anteriores ({fmt(*ref)})"
    cur = (d1.replace(day=1), d1)
    prev_end = d1.replace(day=1) - timedelta(days=1)
    if d1.day <= EARLY_MONTH_DAYS:  # começo do mês: compara com o mês anterior fechado
        ref = (prev_end.replace(day=1), prev_end)
        return cur, ref, f"este mês ({fmt(*cur)})", f"{_MESES[prev_end.month - 1]} fechado ({fmt(*ref)})"
    ref_end = prev_end.replace(day=min(d1.day, prev_end.day))
    ref = (prev_end.replace(day=1), ref_end)
    return cur, ref, f"este mês ({fmt(*cur)})", f"mês anterior ({fmt(*ref)})"


def _variation_prompt(eps: str | None, fila: str, cur: tuple[date, date], ref: tuple[date, date]) -> str:
    iso = lambda d: d.isoformat()
    return (
        f"{_scope_instruction(eps)}\n\n"
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Chame a *Lyra Indicadores* com:\n"
        f"EPS: {eps or 'iFood'}\nPedido: variação do CSAT\nFila: {fila}\n"
        f"Período atual: {iso(cur[0])} a {iso(cur[1])}\nReferência: {iso(ref[0])} a {iso(ref[1])}\n\n"
        "Use EXATAMENTE esses dois períodos e as fórmulas da seção 7.2 dela (efeito mix e efeito performance por motivo "
        "de contato; response rate). Os DOIS períodos filtram pela data da avaliação (csat_timestamp − 3h) entre as "
        "datas, e a response rate usa no denominador os tickets da fila nas MESMAS datas. Antes de devolver, confira: "
        "períodos do mesmo tamanho têm n da mesma ordem (razão acima de 1,5x = revise o filtro) e response rate acima de "
        "60% é erro de recorte. Devolva APENAS JSON válido:\n"
        '{"csat_ref": 94.8, "csat_atual": 93.7, "n_ref": 4120, "n_atual": 3980, "mix_pp": -0.8, "performance_pp": -0.3, '
        '"top_mix": [{"motivo": "pedido atrasado", "share_ref": 18.0, "share_atual": 26.0, "csat_ref": 85.8, "efeito_pp": -0.7}], '
        '"top_performance": [{"motivo": "cobrança não reconhecida", "csat_ref": 92.0, "csat_atual": 88.0, "share_atual": 9.0, "efeito_pp": -0.36}], '
        '"rr_ref": 27.1, "rr_atual": 26.9, '
        '"leitura": "1 frase factual sobre o que os números mostram, sem afirmar nada que eles não mostrem"}\n'
        "Percentuais em %, p.p. com sinal. Até 3 motivos em cada lista: os que mais contribuíram NA DIREÇÃO do efeito "
        "(efeito negativo: os que mais tiraram; positivo: os que mais somaram). motivo = nome de negócio em português "
        "(ex.: 'Item errado'), nunca o código (order__wrong_item). Se a consulta falhar: só ERRO: <motivo>."
    )


MIX_DOMINANT_SHARE = float(os.environ.get("MIX_DOMINANT_SHARE", "0.8"))  # mix responde por ≥80% da queda
MIX_PERF_TOLERANCE_PP = 0.2  # performance estável (queda de até 0,2 p.p.)


def _mix_dominant(data: dict[str, Any]) -> bool:
    """Queda explicada pelo efeito mix: mudou o tipo de contato, não o atendimento. Nesse caso não se cobra plano."""
    c_ref, c_cur = _num(data.get("csat_ref")), _num(data.get("csat_atual"))
    mix, perf = _num(data.get("mix_pp")), _num(data.get("performance_pp"))
    if None in (c_ref, c_cur, mix, perf):
        return False
    total = c_cur - c_ref
    if total >= 0 or mix >= 0:
        return False
    return abs(mix) >= MIX_DOMINANT_SHARE * abs(total) and perf >= -MIX_PERF_TOLERANCE_PP


_MOTIVO_LABELS = {
    "order__wrong_item": "Item errado", "order__missing_item": "Item faltante", "order__not_delivered": "Pedido não entregue",
    "order__late": "Pedido atrasado", "order__late_order": "Pedido atrasado", "order__chat_ifood_vip": "Chat iFood VIP",
    "order__want_to_exchange": "Quer trocar o pedido", "order__logistics_handshake": "Problema na entrega (handshake)",
    "order__cancel": "Cancelamento de pedido", "order__cancel_order": "Cancelamento de pedido",
    "order__inedible_item": "Item impróprio para consumo", "order__damaged_item": "Item danificado",
    "order__refund": "Reembolso", "order__charge": "Cobrança do pedido", "ifood_box__cannot_unlock_box": "iFood Box não abre",
    "club__unrecognized_charge": "Cobrança não reconhecida do Clube", "club__cancel": "Cancelamento do Clube",
}


def _motivo_label(raw: Any) -> str:
    """Código do motivo de contato (order__wrong_item) -> nome de negócio. Código desconhecido vira texto legível."""
    text = str(raw or "").strip()
    key = text.lower()
    if key in _MOTIVO_LABELS:
        return _MOTIVO_LABELS[key]
    if "__" in text or re.fullmatch(r"[a-z0-9_]+", text):
        parts = [p for p in text.split("__") if p]
        body = (parts[-1] if parts else text).replace("_", " ").strip()
        prefix = parts[0].replace("_", " ") if len(parts) > 1 and parts[0] not in {"order"} else ""
        return (f"{body} ({prefix})" if prefix else body).capitalize()
    return text


def _render_variation(fila: str, data: dict[str, Any], label_cur: str, label_ref: str,
                      with_esteira: bool = True) -> str | None:
    c_ref, c_cur = _num(data.get("csat_ref")), _num(data.get("csat_atual"))
    if c_ref is None or c_cur is None:
        return None
    total = c_cur - c_ref
    mix, perf = _num(data.get("mix_pp")), _num(data.get("performance_pp"))
    sign = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + _bfmt(abs(v), 2 if abs(v) < 0.1 else 1)
    arrow = "📉" if total < 0 else "📈" if total > 0 else "➖"
    lines = [f"{arrow} *Variação do CSAT ·* `{fila}` — {label_ref} → {label_cur}"]

    def tag(label: str, fallback: str) -> str:  # "mês anterior (01/10–02/10)" -> "01–02/10"
        m = re.search(r"\((\d{1,2})/(\d{1,2})\s*[–-]\s*(\d{1,2})/(\d{1,2})\)", label or "")
        if m:
            return f"{m.group(1)}–{m.group(3)}/{m.group(4)}" if m.group(2) == m.group(4) else \
                f"{m.group(1)}/{m.group(2)}–{m.group(3)}/{m.group(4)}"
        m = re.search(r"\((\d{1,2}/\d{1,2})\)", label or "")
        return m.group(1) if m else fallback

    t_ref, t_cur = tag(label_ref, "antes"), tag(label_cur, "agora")
    n_txt = ""
    if data.get("n_ref") is not None and data.get("n_atual") is not None:
        n_txt = f" · n {_fmt_int(_num(data['n_ref']) or 0)} → {_fmt_int(_num(data['n_atual']) or 0)}"
    lines.append(f"CSAT *{_bfmt(c_ref)}% → {_bfmt(c_cur)}%* ({sign(total)} p.p.){n_txt}")
    n_ref_v, n_cur_v = _num(data.get("n_ref")), _num(data.get("n_atual"))
    rr_a, rr_b = _num(data.get("rr_ref")), _num(data.get("rr_atual"))
    suspeita = bool((n_ref_v and n_cur_v and (n_cur_v / n_ref_v > 2 or n_cur_v / n_ref_v < 0.5))
                    or any(v is not None and (v < 0 or v > 100) for v in (rr_a, rr_b))
                    or (rr_a is not None and rr_b is not None and abs(rr_b - rr_a) > 30))
    if suspeita:
        lines.append(f"⚠️ *Comparação suspeita:* a amostra ({_fmt_int(n_ref_v or 0)} → {_fmt_int(n_cur_v or 0)} avaliações)"
                     + (f" e a response rate ({_bfmt(rr_a)}% → {_bfmt(rr_b)}%)" if rr_a is not None and rr_b is not None else "")
                     + " mudaram demais para o mesmo número de dias: pode ser erro no recorte do período de referência ou "
                       "mudança de fila entre os meses. Não dá pra concluir mix x performance com esses números; já "
                       "avisei o time.")
        try:
            _alert(f"⚠️ Variação do CSAT com base suspeita em `{fila}`: n {n_ref_v} → {n_cur_v}, RR {rr_a} → {rr_b} "
                   f"({label_ref} x {label_cur}). Conferir o filtro de datas da seção 7.2 da Lyra Indicadores.")
        except Exception:
            pass
        return "\n".join(lines)
    if mix is not None:
        lines.append("")
        rows_mix = []
        for m in (data.get("top_mix") or []):
            if not isinstance(m, dict):
                continue
            sr, sa, cm = _num(m.get("share_ref")), _num(m.get("share_atual")), _num(m.get("csat_ref"))
            # efeito do motivo no CSAT da fila = Δ participação × (CSAT do motivo − CSAT da fila), recalculado aqui
            ef = (sa - sr) / 100 * (cm - c_ref) if None not in (sr, sa, cm) else _num(m.get("efeito_pp"))
            rows_mix.append((ef, m, sr, sa, cm))
        if abs(mix) < 0.1:
            lines.append(f"🔀 *Efeito mix: {sign(mix)} p.p.* — o tipo de contato que chegou praticamente não mudou")
        else:
            lines.append(f"🔀 *Efeito mix: {sign(mix)} p.p.* — mudou o tipo de contato que chegou")
            lines.append(f"_participação de cada motivo nas avaliações: {t_ref} → {t_cur} · p.p. = efeito no CSAT da fila_")
            rows_mix.sort(key=lambda x: (x[0] or 0) * (1 if mix > 0 else -1), reverse=True)
            for ef, m, sr, sa, cm in rows_mix[:3]:
                part = (f"• {_motivo_label(m.get('motivo'))}: {_bfmt(sr or 0)}% → {_bfmt(sa or 0)}% das avaliações")
                if cm is not None:
                    part += f" (CSAT {_bfmt(cm)}%)"
                if ef is not None:
                    part += f" · {sign(ef)} p.p."
                lines.append(part)
    if perf is not None:
        lines.append("")
        lines.append(f"🎯 *Efeito performance: {sign(perf)} p.p.* — mudou o atendimento do mesmo motivo")
        lines.append(f"_CSAT de cada motivo: {t_ref} → {t_cur} · p.p. = quanto isso mexeu no CSAT da fila_")
        top_perf = sorted([m for m in (data.get("top_performance") or []) if isinstance(m, dict)],
                          key=lambda m: (_num(m.get("efeito_pp")) or 0) * (1 if perf > 0 else -1), reverse=True)
        for m in top_perf[:3]:
            part = f"• {_motivo_label(m.get('motivo'))}: CSAT {_bfmt(_num(m.get('csat_ref')) or 0)}% → {_bfmt(_num(m.get('csat_atual')) or 0)}%"
            if m.get("efeito_pp") is not None:
                part += f" · {sign(_num(m['efeito_pp']) or 0)} p.p."
            lines.append(part)
    if mix is not None and perf is not None and abs((mix + perf) - total) > 0.3:
        lines.append(f"⚠️ Mix + performance ({sign(mix + perf)} p.p.) não fecham com a variação ({sign(total)} p.p.): vou revisar a conta.")
    rr_ref, rr_cur = _num(data.get("rr_ref")), _num(data.get("rr_atual"))
    if rr_ref is not None and rr_cur is not None:
        d = rr_cur - rr_ref
        note = "mudou a amostra: parte da variação pode ser de quem respondeu" if abs(d) >= 3 else "estável, não distorce a leitura"
        lines.append("")
        lines.append(f"📨 *Response rate ({t_ref} → {t_cur}):* {_bfmt(rr_ref)}% → {_bfmt(rr_cur)}% ({sign(d)} p.p.) — {note}")
    leitura = str(data.get("leitura") or "").strip()
    if leitura:
        lines.append("")
        lines.append(f"💡 {leitura}")
    if total >= 0:
        lines.append(f"👉 *Leitura:* o CSAT não caiu: {'subiu ' + sign(total) + ' p.p.' if total > 0 else 'ficou estável'} "
                     f"contra {label_ref}" + (", puxado pelo atendimento (efeito performance positivo)" if perf and perf > 0
                                               else "") + ". Nada a cobrar da EPS nessa comparação.")
    elif _mix_dominant(data):
        lines.append(f"👉 *Leitura:* a queda vem do efeito mix ({sign(mix)} p.p.): chegou mais contato de motivo com CSAT "
                     "naturalmente menor, e o atendimento de cada motivo se manteve. Não é caso de plano de ação da EPS; "
                     "é contexto para acompanhar o volume desses motivos.")
    elif perf is not None:
        if with_esteira:
            quem = (f"o efeito performance ({sign(perf)} p.p.) e os pilares Operador e Tempo da esteira"
                    if perf < 0 else "os pilares Operador e Tempo da esteira (a performance não piorou)")
            lines.append(f"👉 *Da EPS cobrar:* {quem}. Mix e amostra são contexto, não culpa da operação.")
        else:
            lines.append(f"👉 *Leitura:* a queda veio do atendimento (efeito performance {sign(perf)} p.p.), não do mix. "
                         "Quer que eu traga a esteira de impacto pra ver em quais pilares (operador, tempo, política...)?")
    return "\n".join(lines)


def _render_esteira(data: dict[str, Any], gap: float, periodo: str = "do mês", fila: str = "") -> str | None:
    """Esteira de impacto (cascata): gap da meta dividido entre os pilares pela proporção de detratores."""
    pilares = [p for p in (data.get("pilares") or []) if isinstance(p, dict) and (_num(p.get("detratores")) or 0) > 0
               and _norm_text(p.get("pilar")) != _norm_text("Sem causa clara")]
    total = sum(_num(p.get("detratores")) or 0 for p in pilares)
    if not pilares or total <= 0:
        return None
    rank = {_norm_text(n): i for i, n in enumerate(_ESTEIRA_ORDER)}
    pilares.sort(key=lambda p: (-(_num(p.get("detratores")) or 0), rank.get(_norm_text(p.get("pilar")), 99)))
    width = max(len(str(p.get("pilar"))) for p in pilares)
    has_gap = gap >= ESTEIRA_MIN_GAP_PP
    rows, eps_pp, eps_pct = [], 0.0, 0.0
    top_share = max((_num(p.get("detratores")) or 0) for p in pilares) / total
    for p in pilares:
        share = (_num(p.get("detratores")) or 0) / total
        impact = gap * share
        filled = max(1, round(share / top_share * 10))  # maior pilar = barra cheia
        bar = "█" * filled + "░" * (10 - filled)
        rows.append(f"{str(p.get('pilar')).ljust(width)}  {bar}  " + (f"{_bfmt(impact, 2)} p.p.  " if has_gap else "")
                    + f"{round(share * 100):d}%")
        if any(_norm_text(p.get("pilar")).startswith(k) for k in ESTEIRA_PILARES_EPS):
            eps_pp += impact
            eps_pct += share
    n_txt = f"{_fmt_int(total)} detratores classificados"
    alvo = f" · `{fila}`" if fila else ""
    if has_gap:
        head = f"de onde vem o gap de {_bfmt(gap, 1)} p.p."
    elif gap > 0:
        head = f"gap pequeno ({_bfmt(gap, 1)} p.p.); peso de cada causa nos detratores"
    else:
        head = "na meta; peso de cada causa nos detratores"
    lines = [f"🧱 *Esteira de impacto {periodo}*{alvo} — {head} ({n_txt})",
             "```" + "\n".join(rows) + "```"]
    top = pilares[0]
    if top.get("padrao"):
        lines.append(f"↳ *{top.get('pilar')}* é o maior pilar: {str(top['padrao']).strip().rstrip('.')}.")
    leitura = str(data.get("leitura") or "").strip()
    if leitura:
        lines.append(f"↳ {leitura}")
    tempos = data.get("tempos") or {}
    d_fr, p_fr = _num(tempos.get("primeira_resposta_detratores_s")), _num(tempos.get("primeira_resposta_promotores_s"))
    if d_fr is not None and p_fr:
        lines.append(f"⏱️ Primeira resposta: detratores {_fmt_tempo(d_fr)} x promotores {_fmt_tempo(p_fr)}"
                     + (f" ({_bfmt(d_fr / p_fr, 1)}x)" if p_fr else ""))
    if eps_pct > 0:
        parte = f"{_bfmt(eps_pp, 2)} p.p. do gap ({round(eps_pct * 100):d}%)" if has_gap else f"{round(eps_pct * 100):d}% dos detratores"
        lines.append(f"👉 *Da EPS (Operador + Tempo): {parte}.* "
                     "É isso que o plano precisa atacar. Política, parceiro e produto viram insumo para o iFood.")
    return "\n".join(lines)


def _post_esteiras(tenant: Tenant, posted: list[dict[str, Any]], day: date) -> None:
    """Depois do report: para cada fila com CSAT do D-1 abaixo da meta, posta na thread a esteira do mês consolidado
    (gap = meta − CSAT do mês; mês na meta = só o peso de cada causa)."""
    problems: list[str] = []
    for block in posted:
        data = _LAST_BLOCK_DATA.get(block.get("fila", ""), {})
        d1, meta, mes = _num(data.get("d1")), _num(data.get("meta")), _num(data.get("mes"))
        if not block.get("cobranca") or d1 is None or meta is None or d1 >= meta:
            continue
        gap = max(0.0, meta - mes) if mes is not None else meta - d1
        try:
            answer = ask_toqan(_esteira_prompt(tenant, block["fila"], gap, day))
            if _is_error_answer(answer):
                problems.append(f"{block['fila']}: {answer.strip()[:150]}")
                continue
            parsed = _block_data_from_json(answer)
            text = _render_esteira(parsed or {}, gap)
            if text:
                _post_sections(tenant.channel, text, thread_ts=block["ts"])
            else:
                problems.append(f"{block['fila']}: a Lyra Qualidade não devolveu os pilares ({answer.strip()[:120]!r})")
        except Exception as exc:
            logger.exception("[%s] Esteira de impacto failed (%s)", tenant.key, block.get("fila"))
            problems.append(f"{block.get('fila')}: {type(exc).__name__}")
    if problems:
        _alert(f"[{tenant.key}] Esteira de impacto não saiu para: " + " | ".join(problems[:4]))


def _run_daily_report(now: datetime | None = None, tenant: Tenant | None = None) -> str:
    """Gera e publica o report de um tenant; devolve o ts da mensagem principal.
    O report é prioridade no Toqan (não entra na fila das tarefas de fundo)."""
    prev = getattr(_TOQAN_TL, "interactive", False)
    _TOQAN_TL.interactive = True
    try:
        return _run_daily_report_inner(now, tenant)
    finally:
        _TOQAN_TL.interactive = prev


def _run_daily_report_inner(now: datetime | None = None, tenant: Tenant | None = None) -> str:
    now = now or _now_brazil()
    tenant = tenant or TENANTS[0]
    google_client = _safe_google_client()
    compromissos_text = _get_open_compromissos(google_client, now, tenant.key) if google_client else ""

    crisis: dict[str, Any] = {}
    d1 = now.date() - timedelta(days=1)
    d1_start = datetime(d1.year, d1.month, d1.day, 0, 0, tzinfo=now.tzinfo)

    def check_crisis() -> None:  # em paralelo com a consulta do report
        crisis["c"] = _crisis_check(d1_start, d1_start + timedelta(hours=23, minutes=59), tenant.eps, ttl=None)
        try:
            crisis["table"] = _day_table()  # tabela do dia (ritmo do mês na cobrança e respostas rápidas)
        except Exception:
            logger.warning("Day table in report failed", exc_info=True)

    crisis_thread = threading.Thread(target=check_crisis, daemon=True)
    crisis_thread.start()
    answer = ask_toqan(_report_prompt(tenant, compromissos_text))
    if _is_error_answer(answer) and "tma" in _norm_text(answer):
        # o TMA não pode derrubar o report: tenta de novo sem TMA
        logger.warning("[%s] Report failed on TMA, retrying without TMA: %s", tenant.key, answer.strip()[:200])
        answer = ask_toqan(_report_prompt(tenant, compromissos_text) + "\n\n" + REPORT_NO_TMA_NOTE)
    if _is_error_answer(answer):
        raise ReportGenerationError(answer.strip()[:300] or "resposta vazia")

    blocks = _prepare_blocks(_split_blocks(answer, use_headers=True), now.date() - timedelta(days=1))
    crisis_thread.join(timeout=300)
    if crisis.get("c"):
        blocks = [(fila, title, _apply_crisis_to_body(body, fila, crisis["c"])) for fila, title, body in blocks]
    if crisis.get("table"):
        def with_ritmo(fila: str, body: str) -> str:
            line = _ritmo_for_report(fila, crisis["table"], d1)
            if not line or "👉 *Cobrança:*" not in body:
                return body
            return body.replace("👉 *Cobrança:*", line + "\n👉 *Cobrança:*", 1)
        blocks = [(fila, title, with_ritmo(fila, body)) for fila, title, body in blocks]
    if blocks:
        posted: list[dict[str, Any]] = []
        csat: dict[str, dict[str, float]] = {}
        for fila, title, body in blocks:
            tagged, has_cobranca = _tag_block(fila, body)
            response = slack_app.client.chat_postMessage(channel=tenant.channel, text=title)
            ts = _resp_get(response, "ts") or (_resp_get(response, "message", {}) or {}).get("ts")
            if not ts:
                continue
            if tagged:
                try:  # detalhe e cobrança dentro da thread do título
                    _post_sections(tenant.channel, tagged, thread_ts=ts)
                except Exception:
                    logger.exception("Could not post block detail in thread (%s)", fila)
            posted.append({"fila": fila, "ts": str(ts), "cobranca": has_cobranca})
            values = _block_csat(fila, body)
            if values:
                csat[fila] = values
        if not posted:
            raise ReportGenerationError("Slack não devolveu o ts de nenhum bloco")
        STATE.set(f"report:{tenant.key}:{now.date().isoformat()}", json.dumps(posted, ensure_ascii=False))
        if ESTEIRA_ENABLED:
            threading.Thread(target=_post_esteiras, args=(tenant, list(posted), now.date() - timedelta(days=1)),
                             daemon=True).start()
        report_ts = posted[0]["ts"]
        if not csat:
            _alert(f"[{tenant.key}] Não consegui ler o CSAT D-1 dos blocos — pré/pós dos compromissos não será calculado hoje.")
    else:
        # formato antigo: mensagem principal + ===THREAD===
        main, thread = _split_report(answer)
        if not main:
            raise ReportGenerationError("mensagem principal vazia")
        csat = _parse_report_csat(answer)
        main = _tag_owners(main)
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
# Saúde dos agentes (Lyra, Nexus, Vera, ClubIA...) e do token do Databricks
# ---------------------------------------------------------------------------
def _parse_any_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _looks_like_token_error(text: str) -> bool:
    low = str(text or "").casefold()
    return any(hint in low for hint in TOKEN_ERROR_HINTS)


def _monitored_agents() -> list[tuple[str, str | None]]:
    """(nome, api_key). A Lyra usa a TOQAN_API_KEY (None)."""
    return [("Lyra", None)] + [(name, key) for name, key in MONITORED_AGENTS.items()]


def _ask_agent(api_key: str | None, prompt: str) -> str:
    conversation_id, request_id = create_conversation(prompt, api_key)
    return get_answer(conversation_id, request_id, api_key=api_key, max_attempts=AGENT_CHECK_MAX_POLLS)


def _check_agent(name: str, api_key: str | None) -> tuple[str, str]:
    """('ok' | 'token' | 'erro' | 'fora', detalhe). Nunca levanta exceção."""
    no_data = name.casefold() in NO_DATA_AGENTS
    try:
        answer = _ask_agent(api_key, PING_PROMPT if no_data else HEALTHCHECK_PROMPT).strip()
    except ToqanAPIError as exc:
        if "timed out" in str(exc):
            return "fora", "não respondeu em 5 minutos"
        return "fora", f"API do Toqan: {str(exc)[:120]}"
    except Exception as exc:
        return "fora", f"{type(exc).__name__}: {str(exc)[:120]}"
    first = next((line.strip() for line in answer.splitlines() if line.strip()), "")
    if first.upper().lstrip("*_ ").startswith("OK"):
        return "ok", first[:60]
    if not first:
        return "fora", "resposta vazia"
    if no_data:
        return "ok", "respondeu (sem dados)"
    if _looks_like_token_error(answer):
        return "token", first[:200]
    if first.upper().lstrip("*_ ").startswith("ERRO"):
        return "erro", first[:200]
    # respondeu, mas fora do padrão: está vivo; não alarma
    return "ok", "respondeu (fora do padrão)"


_STATUS_LABEL = {
    "ok": "✅ funcionando",
    "token": "🔴 token do Databricks expirado/sem permissão",
    "erro": "🟡 erro ao consultar dados",
    "fora": "🔴 sem resposta",
}


def _token_expiry() -> date | None:
    renewed = _parse_any_date(STATE.get("token_renewed") or DATABRICKS_TOKEN_RENEWED or "")
    return renewed + timedelta(days=DATABRICKS_TOKEN_VALIDITY_DAYS) if renewed else None


def _mark_token_renewed(day: date) -> date:
    STATE.set("token_renewed", day.isoformat())
    return day + timedelta(days=DATABRICKS_TOKEN_VALIDITY_DAYS)


def _run_agent_checks(now: datetime, remind: bool = False) -> dict[str, tuple[str, str]]:
    """Testa todos os agentes e grava o status. Avisa quando quebra, quando volta e,
    com remind=True (testes agendados), de novo enquanto continuar parado."""
    results: dict[str, tuple[str, str]] = {}
    broke: list[str] = []
    still: list[str] = []
    recovered: list[str] = []
    token_fixed = False
    for name, key in _monitored_agents():
        status, detail = _check_agent(name, key)
        results[name] = (status, detail)
        previous = STATE.get(f"agent_status:{name}")
        STATE.set(f"agent_status:{name}", status)
        if status != "ok" and previous != status:
            STATE.set(f"agent_down_since:{name}", now.strftime("%d/%m %Hh%M"))
            broke.append(f"• *{name}:* {_STATUS_LABEL[status]} — {detail}")
        elif status != "ok" and remind:
            since = STATE.get(f"agent_down_since:{name}") or "?"
            still.append(f"• *{name}:* {_STATUS_LABEL[status]} desde {since} — {detail}")
        elif status == "ok" and previous and previous != "ok":
            recovered.append(name)
            token_fixed = token_fixed or previous == "token"
    if broke:
        text = "Agente(s) com problema:\n" + "\n".join(broke)
        if any(results[n][0] == "token" for n, _ in _monitored_agents()):
            others = [a for a in SHARED_TOKEN_AGENTS if a not in results]
            if others:
                text += f"\n⚠️ O token é o mesmo de {', '.join(others)} — eles também devem estar sem acesso aos dados."
            text += "\nPra token: Databricks → Settings → Developer → Access tokens, gere um novo e atualize no Toqan. Depois me manda \"troquei o token\"."
        _alert(text)
    if still:
        _alert("Continua parado (ninguém resolveu ainda):\n" + "\n".join(still)
               + "\nSe for token: confira se trocou em TODOS os agentes no Toqan — é comum esquecer um.")
    if recovered:
        _alert(f"Voltou a funcionar ✅ {', '.join(recovered)}")
    if token_fixed:
        expiry = _mark_token_renewed(now.date())  # voltou depois de erro de token = token trocado
        logger.info("Token renewal inferred; next expiry %s", expiry)
    return results


def _agents_summary(results: dict[str, tuple[str, str]]) -> str:
    lines = ["*Status dos agentes:*"]
    for name, (status, detail) in results.items():
        note = f" — {detail}" if status != "ok" else (
            " (respondeu, mas não confirmou a consulta — confira o prompt dele)" if detail.startswith("respondeu (fora")
            else " (não usa token — só confiro se responde)" if detail == "respondeu (sem dados)" else "")
        lines.append(f"• *{name}:* {_STATUS_LABEL[status]}{note}")
    pending = [n for n, (st, _) in results.items() if st == "token"]
    if pending:
        lines.append(f"⚠️ Ainda sem acesso: *{', '.join(pending)}*. Faltou trocar o token nele(s) no Toqan?")
    if len(results) == 1:
        lines.append("_Só estou testando a Lyra. Pra eu testar cada agente/subagente, preencha MONITORED_AGENTS no Railway._")
    expiry = _token_expiry()
    if expiry:
        lines.append(f"Token do Databricks: vence em {_format_date(expiry)} (lembro você na véspera).")
    lines.append(f"_App v{APP_VERSION} · no ar desde {_BOOT_AT[:16].replace('T', ' ')}_")
    return "\n".join(lines)


def _token_reminder_tick(now: datetime) -> None:
    expiry = _token_expiry()
    if not expiry or now.time() < TOKEN_REMINDER_TIME:
        return
    today = now.date()
    key = f"token_reminder:{today.isoformat()}"
    if STATE.get(key):
        return
    days_left = (expiry - today).days
    if days_left == 1:
        _alert(f"Lembrete: o token do Databricks (Lyra, Nexus, Vera, ClubIA…) vence amanhã ({_format_date(expiry)}). "
               "Bom momento pra gerar o novo e atualizar no Toqan — depois me manda \"troquei o token\".")
    elif days_left == 0:
        _alert("O token do Databricks vence HOJE. Gere o novo e atualize no Toqan — depois me manda \"troquei o token\".")
    elif days_left < 0:
        _alert(f"O token do Databricks venceu em {_format_date(expiry)}. Se já trocou, me manda \"troquei o token\".")
    STATE.set(key, str(days_left))


_ACCESS_ERROR_RE = re.compile(
    r"(databricks|consulta|acesso|query|sql|dados).{0,80}(token|401|403|unauthori|expir|permiss|credencia|invalid access)"
    r"|(token|401|403|unauthori|expir|permiss|credencia|invalid access).{0,80}(databricks|consulta|acesso|query|sql|dados)",
    re.IGNORECASE | re.DOTALL,
)
PASSIVE_CHECK_COOLDOWN = timedelta(hours=1)


def _passive_access_check(answer: str) -> None:
    """Uma conversa voltou com erro de acesso aos dados: testa os agentes na hora (no máx. 1x por hora)."""
    if not answer or not _ACCESS_ERROR_RE.search(answer[:1500]):
        return
    now = _now_brazil()
    last = STATE.get("passive_check_at")
    if last:
        try:
            if now - datetime.fromisoformat(last) < PASSIVE_CHECK_COOLDOWN:
                return
        except ValueError:
            pass
    STATE.set("passive_check_at", now.isoformat())

    def run() -> None:
        try:
            results = _run_agent_checks(now)
            if all(st == "ok" for st, _ in results.values()):
                _alert("Uma conversa voltou com erro de acesso aos dados, mas no teste agora todos responderam. Fico de olho.")
        except Exception:
            logger.exception("Passive access check failed")

    threading.Thread(target=run, daemon=True).start()


def _agent_health_tick(now: datetime) -> None:
    _token_reminder_tick(now)
    today = now.date()
    due = [t for t in AGENT_CHECK_TIMES if now.time() >= t]
    if not due:
        return
    slot = max(due)
    key = f"agent_check:{today.isoformat()}:{slot.strftime('%H%M')}"
    if STATE.get(key):
        return
    STATE.set(key, "rodando")
    _run_agent_checks(now, remind=True)
    STATE.set(key, "ok")


_DATA_TEST_RE = re.compile(
    r"\b(testa|teste|testar|verifica|verificar|checa|checar|status|como estao|como esta)\b.*"
    r"\b(databricks|token|dados|base|agentes?|nexus|vera|clubia|lyra)\b"
)
_TOKEN_RENEWED_RE = re.compile(r"\b(troquei|renovei|atualizei|gerei|trocamos|renovamos)\b.*\btokens?\b")


def _is_data_test_request(question: str) -> bool:
    return bool(_DATA_TEST_RE.search(_norm_text(question)))


def _is_token_renewed_message(question: str) -> bool:
    return bool(_TOKEN_RENEWED_RE.search(_norm_text(question)))


_RUN_REPORT_RE = re.compile(r"\b(roda|rode|rodar|dispara|dispare|disparar|gera|gere|gerar|manda|mande|solta|solte)\b.*\breport\b")


def _report_targets(question: str) -> list[Tenant] | None:
    """Tenants pedidos em "roda o report [da aec|da csu]"; None se não for esse comando."""
    text = _norm_text(question)
    if not _RUN_REPORT_RE.search(text):
        return None
    named = [t for t in TENANTS if t.eps and re.search(rf"\b{_compact(t.eps)}\b", text.replace(" ", " "))]
    return named or list(TENANTS)


PREWARM_BASES = os.getenv("PREWARM_BASES", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}


def _prewarm_bases(eps: str) -> None:
    """Depois do report: puxa 1x as bases de operadores da semana (lista, equipe e 4 semanas), uma de cada vez, para
    as perguntas do dia saírem do cache em vez de abrir uma consulta pesada por pessoa."""
    eps_scope = eps if eps in EPS_CELULAS else None
    if eps_scope is None:
        return
    spec = _period_spec("mês")
    jobs = [lambda: _fetch_weekly_rows(eps_scope),
            lambda: _fetch_operator_rows(eps_scope, spec["cur"]),
            lambda: _fetch_operator_rows(eps_scope, spec["prev"]),
            lambda: _ask_cached(_operators_prompt(eps_scope, _operators_period("mês")[0]))]
    for job in jobs:
        try:
            job()
        except Exception:
            logger.warning("[%s] Prewarm failed", eps, exc_info=True)
    logger.info("[%s] Bases de operadores pré-carregadas", eps)


def _run_report_now(targets: list[Tenant]) -> list[str]:
    """Roda o report na hora (teste manual). Devolve uma linha de resultado por tenant."""
    lines = []
    now = _now_brazil()
    for tenant in targets:
        try:
            _run_daily_report(now, tenant)
            lines.append(f"• *{tenant.key}:* report postado no canal ✅")
        except Exception as exc:
            detail = f"{type(exc).__name__}: {str(exc)[:200]}"
            if _looks_like_token_error(str(exc)):
                detail += " (parece o token do Databricks)"
            lines.append(f"• *{tenant.key}:* não saiu — {detail}")
    return lines


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


def _run_thread_read(tenant: Tenant, report_value: str, phase: str, state_key: str, today: date) -> None:
    """Lê a thread de cada bloco (fila) do report."""
    errors = []
    for block in _report_blocks(report_value):
        try:
            result = _read_report_thread(
                tenant.channel, block["ts"], phase, today, tenant.key,
                fila=block.get("fila", ""), register_no_reply=bool(block.get("cobranca", True)),
            )
            logger.info("[%s] Thread read %s %s: %s", tenant.key, phase, block.get("fila"), result)
        except Exception as exc:
            logger.exception("[%s] Thread read %s failed", tenant.key, phase)
            errors.append(f"{block.get('fila') or 'report'}: {type(exc).__name__}: {str(exc)[:120]}")
    STATE.set(state_key, "erro" if errors else "ok")
    if errors:
        _alert(f"[{tenant.key}] Falha ao ler thread(s) do report ({phase}): " + " | ".join(errors[:3]))


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
                    _rts = _run_daily_report(now, tenant)
                    _report_next_attempt_at.pop(tenant.key, None)
                    _post_yesterday_digest(tenant, _rts)
                    if PREWARM_BASES:
                        threading.Thread(target=_prewarm_bases, args=(tenant.eps or "",), daemon=True).start()
                except Exception as exc:
                    failures += 1
                    STATE.set(fail_key, str(failures))
                    _report_next_attempt_at[tenant.key] = now + timedelta(minutes=REPORT_RETRY_MINUTES)
                    logger.exception("[%s] Daily report attempt %d failed", tenant.key, failures)
                    detail = f"{type(exc).__name__}: {str(exc)[:250]}"
                    if _looks_like_token_error(str(exc)):
                        detail += " — parece o token do Databricks: gere um novo e atualize no Toqan"
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

    # 2b) Escalation: 5h depois do report, cobra quem foi marcado e não respondeu
    blocks = _report_blocks(STATE.get(_skey("report", tenant, today)))
    if blocks:
        esc_key = _skey("escalation", tenant, today)
        posted_at = _posted_at(blocks[0]["ts"]) or now
        if now >= posted_at + ESCALATION_DELAY and not STATE.get(esc_key):
            results = []
            for block in blocks:
                if not block.get("cobranca", True):
                    continue
                try:
                    results.append(_escalation_check(tenant, block["ts"], today))
                except Exception as exc:
                    results.append("erro")
                    _alert(f"[{tenant.key}] Falha na cobrança de 5h ({block.get('fila')}): {type(exc).__name__}")
            STATE.set(esc_key, ",".join(results) or "sem cobrança")

    # 3) Leituras da thread de hoje
    report_ts = STATE.get(_skey("report", tenant, today))
    if report_ts:
        first_block = _report_blocks(report_ts)
        posted = (_posted_at(first_block[0]["ts"]) if first_block else None) or now
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
    try:
        _reminders_tick(now)
    except Exception:
        logger.exception("Reminders tick failed")
    try:
        _team_routines_tick(now)
    except Exception:
        logger.exception("Team routines tick failed")
    try:
        _catalog_weekly_tick(now)
    except Exception:
        logger.exception("Catalog weekly tick failed")
    try:
        _agent_health_tick(now)
    except Exception:
        logger.exception("Agent health check failed")


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
    threading.Thread(target=_status_catchup, name="lyra-status-catchup", daemon=True).start()
    if MELHORIAS_POLL_SECONDS > 0 and MELHORIAS_CHANNELS:
        threading.Thread(target=_melhorias_poll_loop, name="lyra-melhorias-poll", daemon=True).start()
    threading.Thread(target=_kb_ready, name="lyra-kb", daemon=True).start()  # base de processos em memória
    if CREAD:
        threading.Thread(target=_cread_loop, name="lyra-cread", daemon=True).start()
    if TABLE_ENABLED:  # deploy/restart zera o cache: já monta a tabela do dia para a 1ª pergunta não esperar
        def _warm_tables() -> None:
            _day_table()
            d1 = _as_date(_today_brazil()) - timedelta(days=1)
            if d1.day <= 10:  # começo do mês: "mês passado" é pergunta frequente, deixa pronto
                _day_table(_prev_month_bounds(d1))
        threading.Thread(target=_warm_tables, name="lyra-warm-table", daemon=True).start()
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
SLACK_SECTION_MAX = 2900


def _section_blocks(text: str) -> list[dict[str, Any]] | None:
    """Mensagem montada pelo app em seções (separadas por linha em branco) -> Block Kit com divisória entre elas.
    None = uma seção só (vai como texto normal)."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    if len(parts) < 2:
        return None
    blocks: list[dict[str, Any]] = []
    for i, part in enumerate(parts):
        if i:
            blocks.append({"type": "divider"})
        chunk = ""
        for line in part.split("\n"):
            if chunk and len(chunk) + len(line) + 1 > SLACK_SECTION_MAX:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
                chunk = ""
            chunk = f"{chunk}\n{line}" if chunk else line[:SLACK_SECTION_MAX]
        if chunk:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
    return blocks if len(blocks) <= 50 else None


def _post_sections(channel: str, text: str, thread_ts: str | None = None) -> Any:
    """Posta com divisórias entre as seções (D-1 | Mês | Leitura | Cobrança…). Se o Slack recusar os blocos, vai como texto."""
    kwargs: dict[str, Any] = {"channel": channel, "text": text}
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    blocks = _section_blocks(text)
    if blocks:
        try:
            return slack_app.client.chat_postMessage(**kwargs, blocks=blocks)
        except Exception:
            logger.warning("Blocks rejected; posting as plain text", exc_info=True)
    return slack_app.client.chat_postMessage(**kwargs)


def _say_sections(say: Callable[..., Any], answer: str, event: dict[str, Any], in_thread: bool = True) -> None:
    kwargs: dict[str, Any] = {"text": answer}
    ts = _reply_ts(event) if (in_thread or event.get("channel_type") == "im") else None
    if ts:
        kwargs["thread_ts"] = ts
    blocks = _section_blocks(answer)
    if blocks:
        try:
            say(**kwargs, blocks=blocks)
            return
        except Exception:
            logger.warning("Blocks rejected; replying as plain text", exc_info=True)
    say(**kwargs)


def _reply_ts(event: dict[str, Any]) -> str | None:
    """Onde a Lyra responde: sempre na thread da pergunta, em canal e na DM (duas perguntas seguidas não se misturam)."""
    return event.get("thread_ts") or event.get("ts")


def _say(say: Callable[..., Any], answer: str, event: dict[str, Any], in_thread: bool) -> None:
    ts = _reply_ts(event) if (in_thread or event.get("channel_type") == "im") else None
    if ts:
        say(text=answer, thread_ts=ts)
    else:
        say(text=answer)


ALERT_CHANNEL_IDS = {t for t in _parse_id_list(ALERT_CHANNEL) if t[:1] in {"C", "G"}}
MONITORING_HELP = ("Aqui eu cuido do monitoramento dos agentes. Pode pedir *status dos agentes* "
                   "ou avisar *troquei o token* que eu testo todos na hora.")


_DIAG_RE = re.compile(r"\b(diagnostico|diagnostica|diagnóstico|checa os canais|confere os canais)\b")


def _diagnostics_text() -> str:
    """Como a Lyra está ligada aos canais: versão, canais de controle (membro? modo teste?), o que viu e respondeu."""
    def member(ch: str) -> str:
        if not ch:
            return "—"
        try:
            info = slack_app.client.conversations_info(channel=ch)
            c = _resp_get(info, "channel", {}) or {}
            return ("✅ está no canal" if c.get("is_member") else "❌ NÃO está no canal (adicione a @Lyra)") + \
                (f" · #{c.get('name')}" if c.get("name") else "")
        except Exception as exc:
            msg = str(exc)
            return "❌ sem acesso ao canal (adicione a @Lyra)" if "not_in_channel" in msg or "channel_not_found" in msg \
                else ("⚠️ não consegui checar (falta o escopo channels:read/groups:read no app do Slack)"
                      if "missing_scope" in msg else f"⚠️ não consegui checar ({type(exc).__name__}: {msg[:80]})")

    boot_br = datetime.fromisoformat(_BOOT_AT).astimezone(BRAZIL_TIMEZONE).strftime("%d/%m %H:%M")
    lines = [f"🩺 *Diagnóstico da Lyra* · app v{APP_VERSION} · no ar desde {boot_br} (horário de Brasília)", ""]
    q_dir = os.path.dirname(CAPA_SQL_PATH)
    q_need = ["capa.sql", "capa_diaria.sql", "capa_planos.json", "motivos_eficiencia.sql", "csat_base.sql",
              "csat_operadores.sql", "csat_motivos.sql", "csat_variacao.sql"]
    q_miss = [f for f in q_need if not os.path.exists(os.path.join(q_dir, f))]
    lines.append("🧮 *Consultas prontas* · " + ("✅ pasta queries completa" if not q_miss else
                                               "❌ faltam em queries/: " + ", ".join(q_miss))
                 + " · " + ("✅ chave da Lyra Indicadores (direto)" if TOQAN_INDICADORES_KEY else
                            "⚠️ sem TOQAN_INDICADORES_KEY: o SQL vai pela Lyra principal (mais lento)")
                 + f" · CSAT fixo: {CSAT_SQL_FIXO}")
    lines.append("")
    lines.append("📍 *Controles das EPSs (STATUS_CHANNELS)*")
    if not STATUS_CHANNELS:
        lines.append("• ❌ STATUS_CHANNELS vazio no Railway: a Lyra não lê nenhum controle.")
    for eps, ch in STATUS_CHANNELS.items():
        modo = (f"teste → responde em <#{STATUS_TEST_CHANNELS.get(eps) or EPS_CHANNELS.get(eps)}>" if _status_shadow(eps)
                else "oficial → responde na thread da EPS")
        lines.append(f"• *{eps}* <#{ch}> · {member(ch)} · {modo}")
        lines.append(f"   última mensagem vista: {STATE.get(f'seen:{ch}') or 'nenhuma desde o deploy/estado'} · "
                     f"última resposta: {STATE.get(f'replied:{ch}') or 'nenhuma'}")
    lines.append(f"• Leitura de prints: {'ligada' if PRINT_READING else 'DESLIGADA (PRINT_READING=0)'}")
    lines += ["", "📣 *Report e conversa (EPS_CHANNELS)*"]
    for eps, ch in EPS_CHANNELS.items():
        lines.append(f"• *{eps}* <#{ch}> · {member(ch)}")
    if MELHORIAS_CHANNELS:
        lines += ["", "🛠️ *Canais de melhorias*"]
        for eps, ch in MELHORIAS_CHANNELS.items():
            lines.append(f"• *{eps}* <#{ch}> · {member(ch)} · chamado de moedas vai para "
                         f"{('<#' + _chamado_destino(eps)[0] + '>') if _chamado_destino(eps)[0] else '—'}"
                         f"{' (teste)' if _chamado_destino(eps)[1] else ''}"
                         f" · respostas da thread: {'no canal de teste (modo teste)' if MELHORIAS_SHADOW else 'na própria thread'}")
            lines.append(f"   última mensagem vista: {STATE.get(f'seen:{ch}') or 'nenhuma desde o deploy/estado'} · "
                         f"último chamado: {STATE.get(f'flowlast:{ch}') or 'nenhum'}")
    return "\n".join(lines)


def _monitoring_channel_reply(question: str, say: Callable[..., Any], event: dict[str, Any], in_thread: bool) -> None:
    """Canal de alerta do time: só comandos de monitoramento (sem dados de EPS)."""
    if _DIAG_RE.search(_norm_text(question)):
        _say(say, _diagnostics_text(), event, True)
    elif _is_token_renewed_message(question):
        expiry = _mark_token_renewed(_now_brazil().date())
        _say(say, f"Anotado ✅ Token novo vale até {_format_date(expiry)}; lembro um dia antes. "
                  "Vou testar os agentes agora…", event, True)
        _say(say, _agents_summary(_run_agent_checks(_now_brazil())), event, True)
    elif _is_data_test_request(question):
        _say(say, "Testando os agentes, leva uns minutos… ⏳", event, True)
        _say(say, _agents_summary(_run_agent_checks(_now_brazil())), event, True)
    else:
        _say(say, MONITORING_HELP, event, in_thread)


THREAD_CONTEXT_MAX_CHARS = int(os.getenv("THREAD_CONTEXT_MAX_CHARS", "12000"))


def _thread_context(event: dict[str, Any]) -> str:
    """Conversa dentro de uma thread: manda junto o que já foi dito ali (ex.: o bloco do report da fila),
    para a Lyra não perguntar o que já está na tela. Marca a mensagem como respondida (sem crítica duplicada depois)."""
    if event.get("_thread_ctx") is not None:  # menção espelhada no canal de teste: contexto é o da thread original
        return str(event["_thread_ctx"])
    thread_ts = str(event.get("thread_ts") or "")
    channel = str(event.get("channel") or "")
    if not thread_ts or thread_ts == str(event.get("ts") or "") or event.get("channel_type") == "im":
        return ""
    try:
        messages = _fetch_thread(channel, thread_ts)
    except Exception:
        logger.warning("Could not read thread context", exc_info=True)
        return ""
    parts = []
    for m in messages:
        if m.get("ts") == event.get("ts"):
            continue
        who = "Lyra" if (m.get("bot_id") or m.get("subtype") == "bot_message") else "Liderança"
        text = _strip_mentions(str(m.get("text") or "")).strip()
        if text:
            parts.append(f"[{who}] {text}")
    if not parts:
        return ""
    body = "\n".join(parts)
    if len(body) > THREAD_CONTEXT_MAX_CHARS:
        half = THREAD_CONTEXT_MAX_CHARS // 2  # começo (o post/report) e fim (a conversa recente)
        body = body[:half] + "\n[…]\n" + body[-half:]
    block = _report_block_for(channel, thread_ts)
    head = "INFORMAÇÃO INTERNA PARA A LYRA — CONTEXTO DA THREAD (já está na tela de quem fala com você; use, não peça de novo)"
    if block:
        head += f". Esta thread é o report da fila {block[1].get('fila')}: avalie o que a pessoa disse com esses números"
        key = f"answered:{thread_ts}"
        answered = {t for t in STATE.get(key).split(",") if t}
        STATE.set(key, ",".join(sorted(answered | {str(event.get('ts'))})))
        # registra o compromisso na hora (a crítica já vai na resposta da conversa, não repete)
        tenant, blk, _ = block

        def register() -> None:
            try:
                time.sleep(LIVE_REPLY_DELAY_SECONDS)
                _read_report_thread(tenant.channel, thread_ts, "live", _today_brazil(), tenant.key,
                                    fila=blk.get("fila", ""), register_no_reply=False)
            except Exception:
                logger.exception("[%s] Commitment registration after mention failed", tenant.key)

        threading.Thread(target=register, daemon=True).start()
    return f"{head}:\n{body}\n\n"


DM_CONTEXT_MESSAGES = 12
DM_CONTEXT_HOURS = 3


_FOLLOWUP_RE = re.compile(r"^(e|e a|e o|e da|e do|e na|e no|e pra|e para|agora|mesma|mesmo|tambem|isso|dessa|desse|"
                          r"desses|dessas|dela|dele|deles|ontem|hoje|no mes|na semana|da aec|da csu|e ontem)\b")


def _is_followup_text(text: str) -> bool:
    """Mensagem que só completa a anterior ("e a da CSU?", "ontem", "e no mês?"): curta ou começando como
    continuação. Pergunta completa vira conversa nova, sem carregar as anteriores."""
    t = _norm_text(_strip_mentions(text))
    return len(t.split()) <= 3 or bool(_FOLLOWUP_RE.match(t))


def _dm_context(event: dict[str, Any]) -> str:
    """DM: manda junto as últimas mensagens da conversa (ou da thread da DM), para 'ontem' ou 'da AeC' completar o
    pedido anterior em vez de virar pergunta nova."""
    if event.get("channel_type") != "im":
        return ""
    channel = str(event.get("channel") or "")
    thread_ts = str(event.get("thread_ts") or "")
    try:
        if thread_ts and thread_ts != str(event.get("ts") or ""):
            messages = _fetch_thread(channel, thread_ts)
        else:
            if not _is_followup_text(str(event.get("text") or "")):
                return ""  # pergunta completa na conversa principal: não mistura com as anteriores
            oldest = str(time.time() - DM_CONTEXT_HOURS * 3600)
            resp = slack_app.client.conversations_history(channel=channel, limit=DM_CONTEXT_MESSAGES + 1, oldest=oldest)
            messages = list(reversed(resp.get("messages") or []))
    except Exception:
        logger.warning("Could not read DM context", exc_info=True)
        return ""
    parts = []
    for m in messages[-(DM_CONTEXT_MESSAGES + 1):]:
        if m.get("ts") == event.get("ts"):
            continue
        who = "Lyra" if (m.get("bot_id") or m.get("subtype") == "bot_message") else "Pessoa"
        text = _strip_mentions(str(m.get("text") or "")).strip()
        if text:
            parts.append(f"[{who}] {text}")
    if not parts:
        return ""
    body = "\n".join(parts)
    if len(body) > THREAD_CONTEXT_MAX_CHARS:
        body = body[-THREAD_CONTEXT_MAX_CHARS:]
    return ("INFORMAÇÃO INTERNA PARA A LYRA — CONVERSA ATÉ AQUI (a mensagem nova pode só completar o pedido anterior, "
            f"ex.: 'ontem' ou 'da AeC'; junte as duas e responda):\n{body}\n\n")


def _last_dm_human_text(event: dict[str, Any]) -> str:
    """Última mensagem da pessoa antes desta, na DM (para juntar um complemento curto ao pedido anterior)."""
    if event.get("channel_type") != "im":
        return ""
    try:
        resp = slack_app.client.conversations_history(channel=str(event.get("channel") or ""), limit=6,
                                                       oldest=str(time.time() - DM_CONTEXT_HOURS * 3600))
    except Exception:
        return ""
    for m in resp.get("messages") or []:  # mais recente primeiro
        if m.get("ts") == event.get("ts") or m.get("bot_id") or m.get("subtype") == "bot_message":
            continue
        return _strip_mentions(str(m.get("text") or "")).strip()
    return ""


def _date_context(question: str) -> str:
    """Data de hoje para a conversa (o agente não sabe que dia é) e correção de data no futuro digitada errado
    (ex.: "29/11" pedido em 30/10 = 29/10)."""
    today = _as_date(_today_brazil())
    yesterday = today - timedelta(days=1)
    weekday = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][today.weekday()]
    note = (f"INFORMAÇÃO INTERNA PARA A LYRA — hoje é {today.strftime('%d/%m/%Y')} ({weekday}); ontem (D-1) = "
            f"{yesterday.strftime('%d/%m/%Y')}.")
    fixes = []
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", question or ""):
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else today.year
        y = y + 2000 if y < 100 else y
        try:
            asked = date(y, mo, d)
        except ValueError:
            continue
        if asked < today:
            continue
        guess = None
        if (asked.year, asked.month) != (today.year, today.month):  # mês digitado errado: mesmo dia, mês atual/anterior
            for back in range(0, 2):
                mm, yy = today.month - back, today.year
                if mm < 1:
                    mm, yy = mm + 12, yy - 1
                try:
                    cand = date(yy, mm, d)
                except ValueError:
                    continue
                if cand < today:
                    guess = cand
                    break
        if guess:
            fixes.append(f"{m.group(0)} ainda não aconteceu; quase certamente é {guess.strftime('%d/%m/%Y')}: use essa "
                         f"data e avise em meia frase (\"considerei {guess.strftime('%d/%m')}\")")
        else:
            fixes.append(f"{m.group(0)} ainda não aconteceu: diga que ainda não tem dado desse dia e traga o D-1")
    if fixes:
        note += " " + "; ".join(fixes) + "."
    return note + "\n\n"


# Operador por nome: all = em qualquer conversa (cada EPS só vê os dela); internal = só visão completa (e-mail iFood /
# canal interno); off = só planilha. O report diário continua gerencial (sem nomes) em qualquer caso.
OPERATOR_NAMES = os.getenv("OPERATOR_NAMES", "all").strip().lower()
_NAMES_CACHE: dict[str, Any] = {"at": 0.0, "map": {}}


def _operator_label(email: str, nome: str = "") -> str:
    """Como o operador aparece no Slack: "Nome · email" (só o e-mail se não achar o nome no MOP). Sem código."""
    email = email.strip().lower()
    return f"{_nice_name(nome)} · {email}" if nome else email


def _email_of(user: str, names: dict[str, str]) -> str | None:
    return next((k for k in names if "@" in k and k.split("@")[0] == user), None)


def _operator_names_allowed(eps: str | None) -> bool:
    if OPERATOR_NAMES in {"off", "0", "nao", "não", "false"}:
        return False
    return OPERATOR_NAMES == "all" or eps is None


def _operator_name_map() -> dict[str, str]:
    """usuário do e-mail (e e-mail completo) -> Nome, pelo MOP. Cache de 30 min."""
    if time.time() - _NAMES_CACHE["at"] < 1800 and _NAMES_CACHE["map"]:
        return _NAMES_CACHE["map"]
    values = _read_mop_values() or []
    result: dict[str, str] = {}
    if values:
        name_col, email_col = _find_col(values[0], "Nome"), _find_col(values[0], "Email")
        for row in values[1:]:
            if name_col is None or email_col is None or max(name_col, email_col) >= len(row):
                continue
            email, nome = str(row[email_col]).strip().lower(), str(row[name_col]).strip()
            if "@" in email and nome:
                result[email] = nome.title() if nome.isupper() else nome
                result.setdefault(email.split("@")[0], result[email])
    _NAMES_CACHE.update(at=time.time(), map=result)
    return result


def _with_operator_names(text: str) -> str:
    """Troca o usuário/e-mail de operador citado na resposta por "Nome (`usuário`)", pelo MOP."""
    names = _operator_name_map()
    if not names or not text:
        return text

    def repl(m: "re.Match[str]") -> str:
        token = m.group(1).lower()
        nome = names.get(token) or names.get(token.split("@")[0])
        if not nome or len(token) < 5:
            return m.group(0)
        email = token if "@" in token else _email_of(token, names) or token
        return _operator_label(email, nome)

    return re.sub(r"`?\b([a-z0-9][a-z0-9._-]{3,}(?:@[a-z0-9.-]+\.[a-z]{2,})?)\b`?", repl, text)


FULL_ACCESS_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — ACESSO A OPERADORES: aqui PODE identificar operador pelo usuário do e-mail "
    "(a parte antes do @; o app completa com o nome) quando a pergunta for sobre operadores (quem melhorou/piorou, "
    "ranking, impacto), sempre dentro do ESCOPO desta conversa. "
    "Ao chamar a Lyra Indicadores, inclua a linha 'Acesso: completo'. Ranking ou comparação de operador só com "
    "avaliações mínimas (D-1: 3+; semana ou mês: 5+) e diga o mínimo usado; no máximo 15 nomes e, se houver mais, "
    "quantos ficaram de fora. Comparação entre períodos por operador: use semana contra semana (ou mês) e só quem tem "
    "o mínimo nos dois períodos.\n\n")


ANSWER_LAYOUT_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — VISUAL DA RESPOSTA: resposta curta (1 a 3 frases) fica em texto corrido. "
    "Resposta grande (ranking, comparação, análise com mais de um bloco) segue o visual do report diário:\n"
    "1ª linha = título: <🔴 se está fora da meta/piorou, 🟢 se está bem> *<Rótulo> ·* `<fila ou EPS>` *— <período>* "
    "· <número principal>. Ex.: 📉 *Maior piora em CSAT ·* `CX Suporte` *— 23–29/10 vs 16–22/10* · 5 operadores\n"
    "Depois, seções separadas por UMA linha em branco (viram divisórias), cada uma com cabeçalho curto: "
    "📍 *Resultado* · 👥 *Por supervisor* · 👤 *Operadores* · 💡 *Leitura* (1 a 3 linhas começando com ↳: o que o "
    "número quer dizer e onde agir).\n"
    "Linhas curtas: • <o quê> *<valor>* → 🔴/🟢 <vs meta ou vs período anterior> (n=<avaliações>). Ranking numerado "
    "(1., 2., ...), um item por linha, no máximo 10. A regra do recorte (mínimo de avaliações, quantos ficaram de fora) vai "
    "em UMA linha em itálico logo abaixo do título, sem linha em branco antes da lista. A Leitura fala do resultado, nunca "
    "do escopo ou da segregação entre EPSs. Operador: só o usuário do e-mail, sem crase (o app põe o nome). "
    "Nome de pessoa sem CAIXA ALTA. Sem crase em nada além do nome da fila/EPS no título. Não repita a mesma "
    "informação em duas seções. Não escreva mensagens de andamento ('processando', 'aguarde').\n\n")


def _looks_sectioned(answer: str | None) -> bool:
    """Resposta no visual do report (título + seções): vai com divisórias."""
    parts = [p for p in re.split(r"\n\s*\n", answer or "") if p.strip()]
    return len(parts) >= 3 or (len(parts) >= 2 and bool(re.match(r"^\W{1,3}\s*\*", (answer or "").lstrip())))


_RECENT_ANSWERS: dict[str, tuple[float, str]] = {}
RECENT_ANSWER_TTL = int(os.getenv("RECENT_ANSWER_TTL", "1800"))  # pergunta repetida em 30 min reaproveita a resposta


def _recent_answer(prompt: str) -> str | None:
    hit = _RECENT_ANSWERS.get(f"{_as_date(_today_brazil())}|{hash(prompt)}")
    return hit[1] if hit and hit[0] > time.time() else None


def _remember_answer(prompt: str, answer: str | None) -> None:
    if not answer or _is_error_answer(answer) or RECENT_ANSWER_TTL <= 0:
        return
    now = time.time()
    for k in [k for k, v in _RECENT_ANSWERS.items() if v[0] <= now]:
        _RECENT_ANSWERS.pop(k, None)
    _RECENT_ANSWERS[f"{_as_date(_today_brazil())}|{hash(prompt)}"] = (now + RECENT_ANSWER_TTL, answer)


DEFAULTS_INSTRUCTION = (
    "INFORMAÇÃO INTERNA PARA A LYRA — RESPONDA, NÃO DEVOLVA PERGUNTA: se faltar o indicador, use CSAT; se faltar o "
    "período, use o MÊS (do dia 1 até ontem) — vale para resultado, ranking, 'qual mais impacta', 'qual a pior'; D-1 só "
    "se pedirem ontem/D-1; se faltar a fila, traga todas as filas do escopo. Diga em meia frase o recorte que usou. "
    "Só pergunte quando for impossível responder sem a informação.\n\n")


# ---------------------------------------------------------------------------
# Aprendizados: quem é do iFood pode ensinar a Lyra na conversa ("da próxima vez traz o n", "não chama de ofensor,
# chama de Q4"). O app guarda na aba "Aprendizados" e manda os ativos junto de toda conversa do escopo. Não vale para
# meta, regra de cálculo, política nem regra de cobrança.
# ---------------------------------------------------------------------------
LEARNINGS_WORKSHEET_TITLE = "Aprendizados"
LEARNINGS_HEADERS = ["ID", "Data", "Aprendizado", "Escopo", "Quem ensinou", "Origem", "Status"]
LEARNINGS_MAX_ACTIVE = int(os.getenv("LEARNINGS_MAX_ACTIVE", "30"))
LEARNINGS_ENABLED = os.getenv("LEARNINGS", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
_LEARNINGS_CACHE: dict[str, Any] = {"at": 0.0, "rows": None}
_LEARNINGS_LOCK = threading.Lock()
_TEACH_RE = re.compile(
    r"\b(aprend[ae]|anota|anote|guarda|guarde|grava|lembr[ae] (que|disso|de)|da proxima vez|das proximas vezes|"
    r"a partir de agora|de agora em diante|nao e assim|nao eh assim|na verdade|o certo e|o correto e|esta errad\w*|"
    r"ta errad\w*|voce errou|vc errou|errou|corrig\w*|sempre que|nunca mais|nao chama de|chama de|chame de|"
    r"prefiro que|quero que (voce|vc) (sempre|nunca)|se atente|atente|considere sempre|sempre considere|"
    r"sempre (use|olhe|traga|mostre|considere|veja)|nunca (use|traga|mostre|considere|chame)|nao e (uma|um|da|do)|"
    r"nao eh (uma|um|da|do)|isso nao e|isso nao eh)\b|^nao (e|eh)\b")
_TEACH_STRONG_RE = re.compile(
    r"\b(aprend[ae]|anota|anote|guarda|guarde|lembr[ae] (que|disso)|da proxima vez|das proximas vezes|a partir de agora|"
    r"de agora em diante|nao e assim|nao eh assim|o certo e|o correto e|nao chama de|chame de|prefiro que|"
    r"quero que (voce|vc) (sempre|nunca)|voce errou|vc errou|se atente|considere sempre|sempre considere)\b")
_LEARN_LIST_RE = re.compile(r"\b(o que (voce|vc) (ja )?aprendeu|seus aprendizados|lista (os|de) aprendizados|"
                            r"quais (sao )?(os )?(seus )?aprendizados)\b")
_LEARN_FORGET_RE = re.compile(r"\b(esquece|esqueca|apaga|apague|remove|remova|desativa|desative)\b.*\baprendizado\s*#?(\d+)")


def _is_ifood_user(user: str) -> bool:
    if not user:
        return False
    try:
        allowed, eps = _dm_scope(user)
    except Exception:
        return False
    return allowed and eps is None


def _learnings_ws() -> Any | None:
    google_client = _safe_google_client()
    if google_client is None:
        return None
    try:
        return _ensure_worksheet(_open_spreadsheet(google_client), LEARNINGS_WORKSHEET_TITLE, LEARNINGS_HEADERS)
    except Exception:
        logger.warning("Could not open Aprendizados worksheet", exc_info=True)
        return None


def _learnings_rows(force: bool = False) -> list[tuple[int, dict[str, str]]]:
    with _LEARNINGS_LOCK:
        if not force and _LEARNINGS_CACHE["rows"] is not None and time.time() - _LEARNINGS_CACHE["at"] < 300:
            return _LEARNINGS_CACHE["rows"]
    ws = _learnings_ws()
    rows = _worksheet_rows_with_header(ws) if ws is not None else []
    with _LEARNINGS_LOCK:
        _LEARNINGS_CACHE.update(at=time.time(), rows=rows)
    return rows


def _active_learnings(eps: str | None) -> list[dict[str, str]]:
    """Ativos do escopo (Todos + a EPS do canal; visão completa vê todos), os mais recentes primeiro."""
    out = []
    for _, r in _learnings_rows():
        if _norm_text(r.get("Status")) != "ativo":
            continue
        escopo = str(r.get("Escopo") or "Todos").strip()
        if eps and _norm_text(escopo) not in {"todos", _norm_text(eps)}:
            continue
        out.append(r)
    out.sort(key=lambda r: _to_int(r.get("ID")), reverse=True)
    return out[:LEARNINGS_MAX_ACTIVE]


def _learnings_instruction(eps: str | None) -> str:
    if not LEARNINGS_ENABLED:
        return ""
    try:
        items = _active_learnings(eps)
    except Exception:
        return ""
    if not items:
        return ""
    lines = "\n".join(f"- {r.get('Aprendizado')}" + (f" (vale para {r.get('Escopo')})" if not eps and
                       _norm_text(r.get('Escopo')) not in {'todos', ''} else "") for r in items)
    return ("INFORMAÇÃO INTERNA PARA A LYRA — APRENDIZADOS DO TIME (correções que o time do iFood te ensinou; siga, "
            "desde que não contrariem números, metas, regras de cálculo ou política):\n" + lines + "\n\n")


def _extract_learning(text: str, context: str, critique: bool = False) -> dict[str, Any]:
    prompt = (
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Não chame subagentes. Responda APENAS com JSON válido.\n"
        + ("ATENÇÃO: a pessoa deu 👎 numa resposta da Lyra e esta mensagem explica o que ficou errado. Mesmo que ela "
           "fale do caso concreto, extraia a LIÇÃO GERAL sobre como a Lyra deveria ter agido (ex.: 'Em pedido de "
           "ajuda pouco claro, pergunte primeiro o que aconteceu e o que a operação já checou antes de orientar.'). "
           "Só responda nenhum se não houver lição nenhuma.\n" if critique else "")
        + "Uma pessoa do time do iFood mandou a mensagem abaixo para a Lyra (agente de gestão das EPSs). Decida se ela "
        "está ENSINANDO algo para as próximas vezes (correção de forma de responder, termo, preferência, contexto da "
        "operação) e escreva o aprendizado em UMA frase imperativa, curta e geral (ex.: 'Sempre traga o n junto do CSAT "
        "do mês.').\n"
        "BLOQUEADO se tentar mudar meta, régua de quadrante, fórmula/regra de cálculo, política de atendimento, "
        "compensação ou o que é cobrado da EPS (isso é regra do iFood, não aprendizado).\n"
        "NENHUM se for só uma pergunta, um comentário, um plano de ação ou algo que vale só para esta conversa.\n"
        + (f"Contexto da conversa:\n{context[-1500:]}\n" if context else "")
        + f"Mensagem: {text}\n"
        'Formato: {"tipo": "aprendizado"|"bloqueado"|"nenhum", "aprendizado": "<frase>", "escopo": "Todos"|"AeC"|"CSU", '
        '"pergunta": true|false}\n'
        "escopo: a EPS só se o ensinamento for claramente só de uma; senão Todos. pergunta: true se a mensagem também "
        "faz uma pergunta que precisa de resposta."
    )
    try:
        data = json.loads(_strip_json_code_blocks(ask_toqan(prompt, max_attempts=60)))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.warning("Learning extraction failed", exc_info=True)
        return {}


def _save_learning(text: str, escopo: str, user: str, link: str) -> int | None:
    ws = _learnings_ws()
    if ws is None:
        return None
    rows = _learnings_rows(force=True)
    new_id = max([_to_int(r.get("ID")) for _, r in rows] + [0]) + 1
    ws.append_row([str(new_id), _now_brazil().strftime("%d/%m/%Y %H:%M"), text, escopo, f"<@{user}>" if user else "",
                   link, "ativo"], value_input_option="RAW")
    _learnings_rows(force=True)
    return new_id


def _handle_learning(event: dict[str, Any], question: str, eps: str | None, say: Callable[..., Any],
                     in_thread: bool) -> bool:
    """Lista/esquece/aprende. True = já respondeu (não segue para a resposta normal)."""
    if not LEARNINGS_ENABLED:
        return False
    t = _norm_text(question)
    user = str(event.get("user") or "")
    if _LEARN_LIST_RE.search(t):
        items = _active_learnings(eps)
        if not items:
            _say(say, "Ainda não tenho aprendizados anotados por aqui. Quem é do iFood pode me corrigir na conversa "
                      "(ex.: \"da próxima vez traz o n junto do CSAT\") que eu anoto e passo a usar.", event, in_thread)
        else:
            body = "\n".join(f"{r.get('ID')}. {r.get('Aprendizado')}" + (f" _({r.get('Escopo')})_"
                              if _norm_text(r.get('Escopo')) not in {'todos', ''} else "") for r in items)
            _say_sections(say, f"🧠 *Aprendizados ·* `{eps or 'todos'}` *—* {len(items)} ativos\n\n{body}\n\n"
                               "_Para tirar um: \"esquece o aprendizado 3\"._", event, in_thread)
        return True
    m = _LEARN_FORGET_RE.search(t)
    if m:
        if not _is_ifood_user(user):
            _say(say, "Só o time do iFood consegue mexer nos meus aprendizados.", event, in_thread)
            return True
        ws = _learnings_ws()
        hit = next(((n, r) for n, r in _learnings_rows(force=True) if str(r.get("ID")) == m.group(2)), None)
        if ws is None or not hit:
            _say(say, f"Não achei o aprendizado {m.group(2)}.", event, in_thread)
            return True
        ws.update_cell(hit[0], LEARNINGS_HEADERS.index("Status") + 1, "inativo")
        _learnings_rows(force=True)
        _say(say, f"Pronto, esqueci o aprendizado {m.group(2)}: _{hit[1].get('Aprendizado')}_", event, in_thread)
        return True
    forced = _feedback_pending(event)  # resposta ao "o que ficou errado?" depois de um 👎
    if not forced:
        if not _TEACH_RE.search(t):
            return False
        if _is_question_like(question) and not _TEACH_STRONG_RE.search(t):
            return False  # "quem errou mais?" é pergunta, não ensinamento
    if not _is_ifood_user(user):
        return False
    context = _thread_context(event) or _dm_context(event)
    got = _extract_learning(question, context, critique=forced)
    tipo = str(got.get("tipo") or "").lower()
    if tipo == "bloqueado":
        _say(say, "Isso mexe em meta, regra de cálculo, política ou no que é cobrado da EPS, então não guardo como "
                  "aprendizado: é regra do iFood e muda pelo time que cuida de mim.", event, in_thread)
        return not got.get("pergunta")
    texto = str(got.get("aprendizado") or "").strip()
    if tipo != "aprendizado" or not texto:
        if forced:
            _alert(f"👎 com comentário de <@{user}>: {question[:300]}")
            _say(say, "Valeu pelo retorno, registrei para o time revisar.", event, in_thread)
            return True
        return False
    escopo = str(got.get("escopo") or "Todos").strip()
    if escopo not in {"Todos", *EPS_CELULAS}:
        escopo = "Todos"
    if eps and escopo == "Todos" and str(event.get("channel_type")) != "im":
        escopo = eps  # ensinado no canal de uma EPS vale para ela
    new_id = None
    try:
        new_id = _save_learning(texto, escopo, user, _permalink(str(event.get("channel") or ""), str(event.get("ts") or "")))
    except Exception:
        logger.warning("Could not save learning", exc_info=True)
    if new_id is None:
        _alert(f"Aprendizado não foi salvo (planilha indisponível): {texto}")
        return False
    _say(say, f"Anotado ✅ Aprendizado {new_id}: _{texto}_" + (f" (vale para {escopo})" if escopo != "Todos" else ""),
         event, in_thread)
    _alert(f"Aprendizado {new_id} novo ({escopo}) por <@{user}>: {texto}")
    return not got.get("pergunta")


# ---------------------------------------------------------------------------
# Lembretes: "me lembra amanhã às 14h de auditar a conversa" -> DM no horário.
# ---------------------------------------------------------------------------
_REMIND_RE = re.compile(r"\b(me lembra|me lembre|lembra me|me avisa|me avise|me cobra|me cobre)\b")
_WEEKDAYS = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}


def _parse_reminder(text: str, now: datetime) -> tuple[datetime, str] | None:
    """(quando, o quê) ou None se não deu para entender o horário."""
    t = _norm_text(text)
    m = _REMIND_RE.search(t)
    if not m:
        return None
    rest = t[m.end():]
    day = None
    if re.search(r"\bdepois de amanha\b", rest):
        day = now.date() + timedelta(days=2)
    elif re.search(r"\bamanha\b", rest):
        day = now.date() + timedelta(days=1)
    elif re.search(r"\bhoje\b", rest):
        day = now.date()
    md = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", rest)
    if md:
        try:
            year = int(md.group(3)) if md.group(3) else now.year
            year = year + 2000 if year < 100 else year
            day = date(year, int(md.group(2)), int(md.group(1)))
            if day < now.date() and not md.group(3):
                day = date(year + 1, day.month, day.day)
        except ValueError:
            return None
    wd = re.search(r"\b(segunda|terca|quarta|quinta|sexta|sabado|domingo)\b", rest)
    if day is None and wd:
        delta = (_WEEKDAYS[wd.group(1)] - now.weekday()) % 7 or 7
        day = now.date() + timedelta(days=delta)
    hm = re.search(r"\b(?:as|a|para as|pras)?\s*(\d{1,2})(?:h|:)(\d{2})?\b|\bas (\d{1,2})\b", rest)
    rel = re.search(r"\bdaqui a (\d{1,3}) ?(min|minuto|minutos|h|hora|horas)\b", rest)
    if rel:
        n = int(rel.group(1))
        when = now + (timedelta(minutes=n) if rel.group(2).startswith("min") else timedelta(hours=n))
    else:
        if hm:
            hh = int(hm.group(1) or hm.group(3))
            mm = int(hm.group(2) or 0) if hm.group(1) else 0
        elif day is not None:
            hh, mm = 9, 0
        else:
            return None
        if hh > 23 or mm > 59:
            return None
        if day is None:
            day = now.date()
        when = datetime(day.year, day.month, day.day, hh, mm, tzinfo=now.tzinfo)
        if when <= now and not md and not re.search(r"\bhoje\b", rest):
            when += timedelta(days=1)
    what = re.sub(r"^\W*(de|da|do|que|pra|para|sobre)\s+", "", re.split(r"\b(?:de|da|do|que|pra|para|sobre)\b", rest, 1)[-1]
                  if re.search(r"\b(?:de|da|do|que|pra|para|sobre)\b", rest) else rest).strip(" .?!")
    original = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    return when, (what or original)[:300]


def _handle_reminder(event: dict[str, Any], question: str, say: Callable[..., Any], in_thread: bool) -> bool:
    if not _REMIND_RE.search(_norm_text(question)):
        return False
    now = _now_brazil()
    got = _parse_reminder(question, now)
    if not got:
        _say(say, "Consigo te lembrar, só me diz quando: ex. \"me lembra amanhã às 14h de auditar a conversa\" ou "
                  "\"me lembra sexta às 10h de cobrar a AeC\".", event, in_thread)
        return True
    when, what = got
    if when <= now:
        _say(say, "Esse horário já passou. Me diz um horário daqui pra frente?", event, in_thread)
        return True
    # o que lembrar: o texto original da pessoa, para não perder detalhe
    what_raw = re.sub(r"<@[A-Z0-9]+>", "", question).strip()
    items = []
    try:
        items = json.loads(STATE.get("reminders") or "[]")
    except ValueError:
        items = []
    items.append({"at": when.isoformat(), "user": event.get("user"), "channel": event.get("channel"),
                  "ts": _reply_ts(event), "what": what_raw[:400]})
    STATE.set("reminders", json.dumps(items, ensure_ascii=False))
    dia = "hoje" if when.date() == now.date() else ("amanhã" if when.date() == now.date() + timedelta(days=1)
                                                     else when.strftime("%d/%m"))
    _say(say, f"Combinado ⏰ Te lembro {dia} às {when.strftime('%Hh%M').replace('h00', 'h')} por DM.", event, in_thread)
    return True


def _reminders_tick(now: datetime) -> None:
    raw = STATE.get("reminders")
    if not raw:
        return
    try:
        items = json.loads(raw)
    except ValueError:
        return
    keep, due = [], []
    for it in items:
        try:
            (due if datetime.fromisoformat(it["at"]) <= now else keep).append(it)
        except (KeyError, ValueError):
            continue
    if not due:
        return
    STATE.set("reminders", json.dumps(keep, ensure_ascii=False))
    for it in due:
        link = _permalink(str(it.get("channel") or ""), str(it.get("ts") or "")) if it.get("ts") else ""
        text = f"⏰ *Lembrete:* {it.get('what')}" + (f"\n<{link}|ver a conversa>" if link else "")
        try:
            dm = slack_app.client.conversations_open(users=it.get("user"))
            channel = (_resp_get(dm, "channel") or {}).get("id")
            slack_app.client.chat_postMessage(channel=channel or it.get("channel"), text=text)
        except Exception:
            logger.warning("Reminder DM failed; posting in the original thread", exc_info=True)
            try:
                slack_app.client.chat_postMessage(channel=it.get("channel"), thread_ts=it.get("ts"), text=f"<@{it.get('user')}> {text}")
            except Exception:
                logger.exception("Reminder failed")


# ---------------------------------------------------------------------------
# Tabela do dia: CSAT do mês e do D-1 por fila (as duas EPSs) numa consulta só, guardada até a meia-noite.
# Perguntas comuns (resultado por fila, como está uma fila, qual fila/EPS mais impacta, pior fila) saem daqui em
# segundos e com o mesmo número em toda resposta. Impacto = CSAT do conjunto − CSAT do conjunto sem a fila.
# ---------------------------------------------------------------------------
TABLE_HEADER = ["eps", "fila", "meta", "mes_aval", "mes_prom", "d1_aval", "d1_prom", "motivo_mes", "motivo_mes_pp"]
TABLE_ENABLED = os.getenv("DAY_TABLE", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
EARLY_MONTH_DAYS = 5  # até o dia 5, o mês vem com o mês anterior fechado de contexto
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]


def _table_prompt(start: date, end: date, d1: date) -> str:
    f = lambda d: d.strftime("%d/%m/%Y")
    return (
        f"{_scope_instruction(None)}\n\n"
        "TAREFA INTERNA DO APP — tabela de CSAT por fila. Não é mensagem para o Slack.\n"
        "Chame a *Lyra Indicadores* com 'EPS: iFood', 'Pedido: tabela do dia (CSV)', "
        f"'Mês: {f(start)} a {f(end)}' e 'D-1: {f(d1)}' (e a linha Madrugada: se ela veio acima).\n"
        "Uma linha por fila das EPSs (AeC e CSU, filas oficiais da seção 4 dela; NUNCA Agentforce CX). Responda APENAS o "
        "CSV separado por ';', escrito no corpo da resposta (nunca arquivo), com este cabeçalho exato:\n"
        f"{';'.join(TABLE_HEADER)}\n"
        "meta em %; *_aval = avaliações; *_prom = promotoras (notas 4 e 5); motivo_mes = motivo de contato de maior "
        "impacto negativo na fila no mês (nome de negócio); motivo_mes_pp = impacto dele em p.p. (negativo). Fila sem "
        "avaliação no período: 0. Se a consulta falhar: só 'ERRO: <motivo>'."
    )


def _parse_table(answer: str, period_end: date | None = None) -> list[dict[str, Any]]:
    import csv as _csv
    text = _strip_json_code_blocks(answer or "").replace("```", "")
    lines = [l for l in text.splitlines() if l.strip()]
    i = next((n for n, l in enumerate(lines) if l.lower().startswith("eps") and "fila" in l.lower()), None)
    if i is None:
        return []
    delim = max((";", ",", "\t"), key=lines[i].count)
    rows = list(_csv.reader(io.StringIO("\n".join(lines[i:])), delimiter=delim))
    head = [_norm_text(h).replace(" ", "_") for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = {h: (r[k].strip() if k < len(r) else "") for k, h in enumerate(head)}
        eps = next((e for e in EPS_CELULAS if _norm_text(e) == _norm_text(d.get("eps"))), None)
        fila = str(d.get("fila") or "").strip()
        if not eps or not fila or "agentforce" in _norm_text(fila):
            continue
        num = lambda k: _to_float(str(d.get(k) or "").replace(",", ".")) or 0.0
        meta_app = _meta_fila(fila, period_end) if period_end else _meta_fila(fila)
        out.append({"eps": eps, "fila": fila,
                    "meta": meta_app if meta_app is not None else _to_float(str(d.get("meta") or "").replace(",", ".")),
                    "mes_aval": num("mes_aval"), "mes_prom": num("mes_prom"), "d1_aval": num("d1_aval"),
                    "d1_prom": num("d1_prom"), "motivo": _motivo_label(d.get("motivo_mes")) if d.get("motivo_mes") else "",
                    "motivo_pp": _to_float(str(d.get("motivo_mes_pp") or "").replace(",", "."))})
    return out


def _month_bounds(d1: date) -> tuple[date, date]:
    return d1.replace(day=1), d1


def _prev_month_bounds(d1: date) -> tuple[date, date]:
    end = d1.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def _day_table(period: tuple[date, date] | None = None, fetch: bool = True) -> list[dict[str, Any]] | None:
    """Tabela das duas EPSs. period=None: mês até o D-1 (com o D-1). fetch=False: só se já estiver em cache."""
    if not TABLE_ENABLED:
        return None
    d1 = _as_date(_today_brazil()) - timedelta(days=1)
    start, end = period or _month_bounds(d1)
    prompt = _table_prompt(start, end, end if period else d1)
    answer = _ask_base(prompt) if fetch else _cached_only(prompt)
    if answer is None or _is_error_answer(answer):
        return None
    rows = _parse_table(answer, end)
    if not rows:
        _alert_unreadable("Tabela do dia", None, answer)
        with _BASE_LOCK:
            for k in [k for k, v in _BASE_CACHE.items() if v[1] == answer]:
                _BASE_CACHE.pop(k, None)
        return None
    return rows


def _agg(rows: list[dict[str, Any]], kind: str = "mes") -> tuple[float | None, float, float | None]:
    """(CSAT, n, meta consolidada pelo mix) de um conjunto de filas."""
    aval = sum(r[f"{kind}_aval"] for r in rows)
    prom = sum(r[f"{kind}_prom"] for r in rows)
    with_meta = [r for r in rows if r.get("meta") is not None and r[f"{kind}_aval"] > 0]
    am = sum(r[f"{kind}_aval"] for r in with_meta)
    meta = sum(r[f"{kind}_aval"] * r["meta"] for r in with_meta) / am if am else None
    return (prom / aval * 100 if aval else None), aval, meta


def _impact(rows: list[dict[str, Any]], target: list[dict[str, Any]], kind: str = "mes") -> float | None:
    """Régua do Cockpit: peso de `target` nas pesquisas do conjunto × (CSAT de `target` − meta consolidada do conjunto),
    em p.p. Negativo = puxa o conjunto para baixo da meta. A soma das filas = CSAT do conjunto − meta consolidada."""
    total_csat, n_total, meta = _agg(rows, kind)
    t_csat, n_t, _ = _agg(target, kind)
    if t_csat is None or meta is None or not n_total:
        return None
    return n_t / n_total * (t_csat - meta)


def _without(rows: list[dict[str, Any]], target: list[dict[str, Any]], kind: str = "mes") -> float | None:
    """CSAT do conjunto − CSAT do conjunto sem `target` (o "quanto iria sem a fila", usado na Leitura)."""
    total, _, _ = _agg(rows, kind)
    rest = [r for r in rows if r not in target]
    without, n_without, _ = _agg(rest, kind)
    if total is None or without is None or not n_without:
        return None
    return total - without


def _ritmo(row_or_rows: Any, d1: date, meta_override: float | None = None) -> dict[str, float] | None:
    """Quanto precisa nos dias que faltam para fechar o mês na meta (pelo ritmo de avaliações do mês)."""
    rows = row_or_rows if isinstance(row_or_rows, list) else [row_or_rows]
    csat, aval, meta = _agg(rows, "mes")
    if meta_override is not None:
        meta = meta_override
    import calendar
    days_month = calendar.monthrange(d1.year, d1.month)[1]
    remaining = days_month - d1.day
    if csat is None or meta is None or remaining <= 0 or d1.day < 3 or aval <= 0:
        return None
    prom = sum(r["mes_prom"] for r in rows)
    rem_aval = aval / d1.day * remaining
    need = (meta / 100 * (aval + rem_aval) - prom) / rem_aval * 100
    return {"need": need, "remaining": remaining, "csat": csat, "meta": meta}


def _ritmo_text(rt: dict[str, float] | None) -> str:
    if not rt:
        return ""
    n = int(rt["remaining"])
    dias = f"{n} dia{'s' if n != 1 else ''} que falta{'m' if n != 1 else ''}"
    if rt["need"] <= rt["meta"] and rt["csat"] >= rt["meta"]:
        return f"no ritmo atual fecha o mês na meta (está {_bfmt(rt['csat'] - rt['meta'])} p.p. acima)"
    if rt["need"] > 100:
        return f"mesmo com 100% nos {dias} o mês não fecha na meta {_bfmt(rt['meta'])}%"
    return f"para fechar o mês na meta precisa de *{_bfmt(max(rt['need'], 0))}%* nos {dias} (hoje está em {_bfmt(rt['csat'])}%)"


def _scope_rows(rows: list[dict[str, Any]], eps: str | None) -> list[dict[str, Any]]:
    return [r for r in rows if eps is None or _eps_matches(r["eps"], eps)]


_TABLE_BLOCK_RE = re.compile(r"\b(motivo|motivos|operador\w*|analista\w*|atendente\w*|quem|nomes?|nominal|supervisor\w*|coordenador\w*|"
                             r"equipe|por que|porque|pq|semana|semanal|tma|sla|nps|reabertura|volume|grafico|excel|"
                             r"planilha|quadrante|q4|reincid\w*|ofensor\w*|dispersao|compar\w*|evolucao|tendencia|turno\w*|horari\w*|"
                             r"por hora|faixa\w*|regia\w*|cidade\w*|produto\w*|"
                             r"\d{1,2}/\d{1,2}|bu|food|multi)\b")
_TABLE_RESULT_RE = re.compile(r"\b(resultado|csat|como (esta|estao|ta|tao|foi|foram|anda|andam))\b")
_TABLE_IMPACT_RE = re.compile(r"\b(mais impacta\w*|maior impacto|mais impacto|impacta mais|pior|piores|"
                              r"puxa\w* (pra|para) baixo)\b")


def _table_intent(question: str, eps: str | None) -> tuple[str, str | None, str | None] | None:
    """('resultado'|'fila'|'impacto_fila'|'impacto_eps', eps, fila) ou None (vai para a análise livre)."""
    if not TABLE_ENABLED:
        return None
    t = _norm_text(question)
    if _TABLE_BLOCK_RE.search(t) or _is_analytical(question) and not _TABLE_IMPACT_RE.search(t):
        return None
    eps_q = eps or _eps_in_text(question)
    fila = _fila_in_question(question, eps_q) or (_status_fila(question, eps_q) if eps_q else None)
    if fila and not eps_q:
        eps_q = next((e for e, cel in EPS_CELULAS.items() if fila in cel), None)
    if _TABLE_IMPACT_RE.search(t):
        if re.search(r"\beps\b", t) and not fila:
            return ("impacto_eps", eps_q, None) if eps is None else None
        if re.search(r"\bfila", t) or eps_q:
            return ("impacto_fila", eps_q, None)
        return None
    if _TABLE_RESULT_RE.search(t):
        if fila:
            return ("fila", eps_q, fila)
        if re.search(r"\b(por fila|das filas|filas|da aec|da csu|aec|csu|geral|consolidado)\b", t) or eps_q \
                or len(t.split()) <= 6:
            return ("resultado", eps_q, None)
    return None


# "o que aconteceu hoje?", "o que rolou no canal?", "pendências": registro do dia da leitura contínua
_DAYLOG_RE = re.compile(r"\b(o que (aconteceu|rolou|teve) (hoje|no canal|na operacao|ontem)|o que rolou|"
                        r"pendencias (de hoje|do dia|abertas|do canal|em aberto)|o que (esta|ta|ficou) em aberto|"
                        r"resumo do canal|como (foi|ta|esta) o canal)\b")
# "novidades?", "como estamos?", "me atualiza": resposta rápida com a tabela do dia (sem chamar os subagentes)
_NEWS_RE = re.compile(r"\b(novidade\w*|o que (tem|ha) de novo|como (estamos|que estamos|ta a operacao|esta a operacao|"
                      r"tao as coisas|estao as coisas)|me atualiza|me da um resumo|resumo (do dia|de hoje|rapido)|"
                      r"como (foi|ta|esta) (o dia|hoje))\b")
NEWS_FOLLOWUP = ("💬 Quer que eu aprofunde em alguma fila? Posso puxar as causas, a variação da semana, "
                 "os operadores ou montar um plano.")
_CAUSE_FOLLOW_RE = re.compile(r"\b(causa|causas|por que|porque|pq|explica\w*|o que (esta|ta) puxando|de onde vem)\b")


def _table_answer(question: str, eps: str | None, focus: dict[str, Any] | None = None) -> str | None:
    """Resposta pronta da tabela do dia (None = não é pergunta de tabela ou a tabela não está disponível).
    `focus` recebe a fila em destaque (a que mais impacta / a citada), para emendar a análise de causa."""
    nq = _norm_text(question)
    intent = _table_intent(nq[:_CAUSE_FOLLOW_RE.search(nq).start()] if _CAUSE_FOLLOW_RE.search(nq) else question, eps)
    if not intent:
        return None
    kind_q, eps_q, fila_q = intent
    rows = _day_table()
    if not rows:
        return None
    d1 = _as_date(_today_brazil()) - timedelta(days=1)
    use_d1 = bool(re.search(r"\b(ontem|d 1|d1)\b", _norm_text(question)))
    prev_end = d1.replace(day=1) - timedelta(days=1)
    use_prev = not use_d1 and bool(re.search(
        rf"\b(mes passado|mes anterior|ultimo mes|mes fechado|fechamento do mes|{_norm_text(_MESES[prev_end.month - 1])})\b",
        _norm_text(question)))
    if use_prev:  # "mês passado": responde o mês anterior fechado
        rows = _day_table(_prev_month_bounds(d1))
        if not rows:
            return None
        d1 = prev_end
    kind = "d1" if use_d1 else "mes"
    when = (f"{_MESES[d1.month - 1]} fechado" if use_prev else f"D-1 {d1.strftime('%d/%m')}" if use_d1 else (
        f"mês 01 a {d1.strftime('%d/%m')}" if d1.day > 1 else f"mês ({d1.strftime('%d/%m')})"))
    prev_rows = None
    if not use_d1 and not use_prev and d1.day <= EARLY_MONTH_DAYS:
        prev_rows = _day_table(_prev_month_bounds(d1))
    prev_name = _MESES[(d1.replace(day=1) - timedelta(days=1)).month - 1]

    def prev_of(fila: str | None = None, eps_: str | None = None) -> str:
        if not prev_rows:
            return ""
        sel = [r for r in prev_rows if (fila is None or _norm_text(r["fila"]) == _norm_text(fila))
               and (eps_ is None or _eps_matches(r["eps"], eps_))]
        c, n, _ = _agg(sel, "mes")
        return f" · {prev_name} fechado {_bfmt(c)}% (n={_fmt_int(n)})" if c is not None else ""

    def fila_line(r: dict[str, Any], base: list[dict[str, Any]]) -> str:
        c, n, _ = _agg([r], kind)
        if c is None:
            return f"⚪ {r['fila']} · sem avaliação"
        imp = _impact(base, [r], kind)
        dot = _status_dot(c / r["meta"] * 100) if r.get("meta") else "⚪"
        parts = [f"{dot} {r['fila']} · *{_bfmt(c)}%*", f"meta {_bfmt(r['meta'])}%" if r.get("meta") else "sem meta",
                 f"n={_fmt_int(n)}"]
        if imp is not None and len(base) > 1:
            parts.append(f"impacto {'+' if imp >= 0 else '−'}{_bfmt(abs(imp), 2)} p.p.")
        return " · ".join(parts) + prev_of(r["fila"])

    if kind_q == "impacto_eps":
        base = rows
        lines = []
        items = []
        for e in EPS_CELULAS:
            sel = [r for r in base if _eps_matches(r["eps"], e)]
            if not sel:
                continue
            imp = _impact(base, sel, kind)
            c, n, _ = _agg(sel, kind)
            items.append((imp if imp is not None else 0, e, c, n))
        if not items:
            return None
        total, n_total, _ = _agg(base, kind)
        items.sort()
        worst = items[0]
        without, _, _ = _agg([r for r in base if not _eps_matches(r["eps"], worst[1])], kind)
        lines.append(f"{'🔴' if worst[0] < 0 else '🟢'} *EPS que mais puxa o CSAT ·* `{worst[1]}` *— {when}* · "
                     f"consolidado {_bfmt(total)}% (n={_fmt_int(n_total)})")
        lines.append("")
        lines.append("📍 *Resultado*")
        for imp, e, c, n in items:
            lines.append(f"• {e} *{_bfmt(c)}%* (n={_fmt_int(n)}) · impacto {'+' if imp >= 0 else '−'}{_bfmt(abs(imp), 2)} p.p."
                         + prev_of(None, e))
        lines.append("")
        lines.append("💡 *Leitura*")
        lines.append(f"↳ Impacto pela régua do Cockpit (peso × CSAT vs meta consolidada): {worst[1]} "
                     f"{'+' if worst[0] >= 0 else '−'}{_bfmt(abs(worst[0]), 2)} p.p.")
        lines.append(f"↳ Sem a {worst[1]}, o consolidado iria de {_bfmt(total)}% para {_bfmt(without)}%. "
                     "Agentforce CX (IA) fica fora.")
        return "\n".join(lines)

    base = _scope_rows(rows, eps_q)
    if not base:
        return None
    if kind_q == "fila":
        r = next((x for x in base if _norm_text(x["fila"]) == _norm_text(fila_q)), None)
        if not r:
            return None
        if focus is not None:
            focus.update(fila=r["fila"], eps=r["eps"])
        c, n, _ = _agg([r], kind)
        if c is None:
            return f"⚪ *{r['fila']} ·* `{r['eps']}` *— {when}* · sem avaliação de CSAT no período."
        lines = [f"{_status_dot(c / r['meta'] * 100) if r.get('meta') else '⚪'} *Resultado ·* `{r['fila']}` *— {when}* · "
                 f"CSAT {_bfmt(c)}%" + (f" (meta {_bfmt(r['meta'])}%)" if r.get("meta") else ""), ""]
        lines.append(f"📍 *Resultado · {when}*")
        lines.append(f"• CSAT *{_bfmt(c)}%* → {_vs_meta(c, r.get('meta'))} (n={_fmt_int(n)})" + prev_of(r["fila"]))
        if not use_d1 and not use_prev and r["d1_aval"]:
            cd, nd, _ = _agg([r], "d1")
            lines.append(f"• D-1 {d1.strftime('%d/%m')}: {_bfmt(cd)}% (n={_fmt_int(nd)})")
        imp = _impact(base, [r], kind)
        if imp is not None and len(base) > 1:
            lines.append(f"• Impacto na {r['eps']}: {'+' if imp >= 0 else '−'}{_bfmt(abs(imp), 2)} p.p.")
        if r.get("motivo") and not use_d1:
            lines.append(f"• Motivo que mais tira: {r['motivo']}" + (f" (−{_bfmt(abs(r['motivo_pp']), 2)} p.p.)"
                                                                   if r.get("motivo_pp") is not None else ""))
        rt = _ritmo_text(_ritmo(r, d1)) if not use_d1 and not use_prev and r.get("meta") else ""
        if rt:
            lines += ["", "💡 *Leitura*", f"↳ {rt[0].upper() + rt[1:]}."]
        return "\n".join(lines)

    groups = [base] if eps_q else [[r for r in base if _eps_matches(r["eps"], e)] for e in EPS_CELULAS]
    groups = [g for g in groups if g]
    out = []
    for g in groups:
        e = g[0]["eps"]
        c, n, meta = _agg(g, kind)
        if kind_q == "impacto_fila":
            ranked = sorted([(_impact(g, [r], kind), r) for r in g if r[f"{kind}_aval"] > 0],
                            key=lambda x: (x[0] if x[0] is not None else 0))
            if not ranked:
                continue
            worst_imp, worst = ranked[0]
            if focus is not None and "fila" not in focus:
                focus.update(fila=worst["fila"], eps=e)
            without, _, _ = _agg([r for r in g if r is not worst], kind)
            lines = [f"{'🔴' if (worst_imp or 0) < 0 else '🟢'} *Fila que mais impacta ·* `{e}` *— {when}* · "
                     f"{worst['fila']}", f"_impacto = peso da fila × (CSAT da fila − meta consolidada da {e}, "
                     f"{_bfmt(meta)}%) · régua do Cockpit_", ""]
            lines.append(f"📍 *Ranking* — CSAT da {e} {_bfmt(c)}% (n={_fmt_int(n)}) · "
                         f"{'+' if c - meta >= 0 else '−'}{_bfmt(abs(c - meta))} p.p. vs meta consolidada")
            for i, (imp, r) in enumerate(ranked, 1):
                cr, nr, _ = _agg([r], kind)
                lines.append(f"{i}. {r['fila']} · *{'+' if (imp or 0) >= 0 else '−'}{_bfmt(abs(imp or 0), 2)} p.p.* · "
                             f"CSAT {_bfmt(cr)}% (n={_fmt_int(nr)})" + prev_of(r["fila"]))
            leitura = [f"Sem a {worst['fila']}, a {e} iria de {_bfmt(c)}% para {_bfmt(without)}%."]
            if worst.get("motivo") and not use_d1:
                leitura.append(f"Na {worst['fila']}, o motivo que mais tira é {worst['motivo']}.")
            lines += ["", "💡 *Leitura*"] + [f"↳ {x}" for x in leitura]
        else:
            lines = [f"{_status_dot(c / meta * 100) if meta else '⚪'} *Resultado por fila ·* `{e}` *— {when}* · "
                     f"CSAT {_bfmt(c)}%" + (f" (meta {_bfmt(meta)}%)" if meta else ""), ""]
            lines.append(f"📍 *Por fila* — do maior impacto negativo para o menor")
            for r in sorted(g, key=lambda r: (_impact(g, [r], kind) or 0)):
                lines.append(fila_line(r, g))
            segs = _segment_lines(g, e, kind, d1, with_ritmo=not use_d1 and not use_prev)
            if segs:
                lines += ["", f"🎯 *Metas combinadas da {e}*"] + segs
        out.append("\n".join(lines))
    return "\n\n".join(out) if out else None


def _segment_lines(g: list[dict[str, Any]], eps: str, kind: str, d1: date, with_ritmo: bool = False) -> list[str]:
    """Resultado por segmento contra a meta combinada da EPS (Alpha, Super, Super PF)."""
    out = []
    for seg in (META_EPS_SEGMENTO.get(eps) or {}):
        sel = [r for r in g if FILA_SEGMENTO.get(r["fila"]) == seg]
        c, n, _ = _agg(sel, kind)
        meta = _meta_segmento(eps, seg, d1)
        if c is None or meta is None:
            continue
        line = f"• {seg} *{_bfmt(c)}%* → {_vs_meta(c, meta)} (n={_fmt_int(n)})"
        if with_ritmo:
            rt = _ritmo(sel, d1, meta)
            if rt and not (rt["need"] <= rt["meta"] and rt["csat"] >= rt["meta"]):
                line += f" · {_ritmo_text(rt)}"
        out.append(line)
    return out


def _table_context(eps: str | None) -> str:
    """Números oficiais do mês por fila (só se a tabela do dia já estiver em cache), para as respostas livres usarem
    os mesmos números das respostas prontas."""
    try:
        rows = _day_table(fetch=False)
    except Exception:
        return ""
    if not rows:
        return ""
    sel = _scope_rows(rows, eps)
    if not sel:
        return ""
    def _plan(fila: str) -> str:
        k = next((k for k in TMA_PLAN if _norm_text(k) == _norm_text(fila)), None)
        return f" · plan de TMA {_fmt_tempo(TMA_PLAN[k][0])}" if k and fila not in NO_TMA_FILAS else ""
    body = "; ".join(f"{r['eps']} · {r['fila']}: CSAT {_bfmt(_agg([r])[0])}% (meta {_fmt_meta(r.get('meta'))}%, "
                     f"n={_fmt_int(r['mes_aval'])}){_plan(r['fila'])}"
                     for r in sel if r["mes_aval"])
    return ("INFORMAÇÃO INTERNA PARA A LYRA — NÚMEROS OFICIAIS DO MÊS ATÉ ONTEM, com a meta de CSAT e o plan de TMA de "
            "cada fila (use estes; se o subagente trouxer outro número ou outra meta para a mesma fila e período, fique "
            f"com este; o plan de TMA vale para a fila e para as equipes dela): {body}\n\n")


def _ritmo_for_report(fila: str, rows: list[dict[str, Any]] | None, d1: date) -> str:
    if not rows:
        return ""
    r = next((x for x in rows if _norm_text(x["fila"]) == _norm_text(fila)), None)
    if not r or not r.get("meta"):
        return ""
    rt = _ritmo(r, d1)
    return f"🎯 *Ritmo do mês:* {_ritmo_text(rt)}." if rt else ""


# ---------------------------------------------------------------------------
# Registro das conversas (auditoria e saúde) e avaliações 👍/👎
# ---------------------------------------------------------------------------
CONVERSAS_WORKSHEET_TITLE = "Conversas"
CONVERSAS_HEADERS = ["Data", "Hora", "Quem", "Escopo", "Canal", "Rota", "Pergunta", "Resposta", "Segundos", "Status", "Link"]
AVALIACOES_WORKSHEET_TITLE = "Avaliações"
AVALIACOES_HEADERS = ["Data", "Quem", "Reação", "Pergunta", "Resposta", "Escopo", "Link"]
CONVERSATION_LOG = os.getenv("CONVERSATION_LOG", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
_NAO_SEI_RE = re.compile(r"(nao esta na minha base|nao sei|nao consegui|nao tenho (essa|esse|a|o) |one hub)")
_WS_CACHE: dict[str, Any] = {}


def _lyra_ws(title: str, headers: list[str]) -> Any | None:
    if title in _WS_CACHE:
        return _WS_CACHE[title]
    google_client = _safe_google_client()
    if google_client is None:
        return None
    try:
        ws = _ensure_worksheet(_open_spreadsheet(google_client), title, headers)
        _WS_CACHE[title] = ws
        return ws
    except Exception:
        logger.warning("Could not open worksheet %s", title, exc_info=True)
        return None


def _log_conversation(event: dict[str, Any], eps: str | None, question: str, answers: list[str], seconds: float,
                      failed: bool) -> None:
    if not CONVERSATION_LOG or not question:
        return
    answer = "\n---\n".join(a for a in answers if a)
    route = str(event.get("_route") or "livre")
    status = "erro" if failed or answer.strip() in {ERROR_MESSAGE, TIMEOUT_ERROR_MESSAGE, EMPTY_ANSWER_MESSAGE} else (
        "nao_sei" if _NAO_SEI_RE.search(_norm_text(answer)) else "ok")
    now = _now_brazil()

    def run() -> None:
        ws = _lyra_ws(CONVERSAS_WORKSHEET_TITLE, CONVERSAS_HEADERS)
        if ws is None:
            return
        try:
            link = _permalink(str(event.get("channel") or ""), str(event.get("ts") or ""))
            ws.append_row([now.strftime("%d/%m/%Y"), now.strftime("%H:%M"), str(event.get("user") or ""),
                           eps or "iFood", str(event.get("channel_type") or "canal"), route, question[:1500],
                           answer[:3000], str(round(seconds)), status, link], value_input_option="RAW")
        except Exception:
            logger.warning("Could not log conversation", exc_info=True)

    threading.Thread(target=run, daemon=True).start()


_THUMBS = {"+1": "👍", "thumbsup": "👍", "-1": "👎", "thumbsdown": "👎"}
FEEDBACK_REACTIONS = os.getenv("FEEDBACK_REACTIONS", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}


def _add_feedback_reactions(channel: str, ts: str) -> None:
    """Deixa 👍 e 👎 prontos na resposta: quem leu só clica (o voto da própria Lyra não conta)."""
    for name in ("+1", "-1"):
        try:
            slack_app.client.reactions_add(channel=channel, timestamp=ts, name=name)
        except Exception:
            logger.debug("Could not add feedback reaction", exc_info=True)


def _handle_reaction(event: dict[str, Any]) -> None:
    """👍/👎 numa resposta da Lyra: registra; 👎 de alguém do iFood abre a pergunta "o que ficou errado?"."""
    name = str(event.get("reaction") or "").split("::")[0]
    thumb = _THUMBS.get(name)
    item = event.get("item") or {}
    bot = _bot_user_id()
    if not thumb or item.get("type") != "message" or (bot and event.get("item_user") != bot) \
            or (bot and event.get("user") == bot):
        return
    channel, ts, user = str(item.get("channel") or ""), str(item.get("ts") or ""), str(event.get("user") or "")
    text, thread_ts = "", ""
    try:
        hist = slack_app.client.conversations_history(channel=channel, latest=ts, oldest=ts, inclusive=True, limit=1)
        msgs = _resp_get(hist, "messages", []) or []
        if not msgs:
            hist = slack_app.client.conversations_replies(channel=channel, ts=ts, inclusive=True, limit=1)
            msgs = [m for m in (_resp_get(hist, "messages", []) or []) if str(m.get("ts")) == ts]
        if msgs:
            text, thread_ts = str(msgs[0].get("text") or ""), str(msgs[0].get("thread_ts") or "")
    except Exception:
        logger.warning("Could not read rated message", exc_info=True)
    question = ""
    if thread_ts and thread_ts != ts:
        try:
            root = next((m for m in _fetch_thread(channel, thread_ts) if m.get("ts") == thread_ts), {})
            question = _strip_mentions(str(root.get("text") or ""))
        except Exception:
            pass
    allowed, scope = (False, None)
    try:
        allowed, scope = _dm_scope(user)
    except Exception:
        pass
    ws = _lyra_ws(AVALIACOES_WORKSHEET_TITLE, AVALIACOES_HEADERS)
    if ws is not None:
        try:
            ws.append_row([_now_brazil().strftime("%d/%m/%Y %H:%M"), f"<@{user}>", thumb, question[:1000], text[:2000],
                           scope or ("iFood" if allowed else "?"), _permalink(channel, ts)], value_input_option="RAW")
        except Exception:
            logger.warning("Could not log rating", exc_info=True)
    if thumb == "👎" and allowed and scope is None:
        root = thread_ts or ts
        STATE.set(f"fb_pending:{channel}:{root}", user)
        try:
            slack_app.client.chat_postMessage(channel=channel, thread_ts=root,
                                              text=f"<@{user}> o que ficou errado? Me conta aqui que eu anoto para a próxima.")
        except Exception:
            logger.warning("Could not ask for feedback", exc_info=True)


def _feedback_pending(event: dict[str, Any]) -> bool:
    channel = str(event.get("channel") or "")
    root = str(event.get("thread_ts") or "")
    key = f"fb_pending:{channel}:{root}"
    if root and STATE.get(key) and STATE.get(key) == str(event.get("user") or ""):
        STATE.set(key, "")
        return True
    return False


# ---------------------------------------------------------------------------
# Rotinas do time: auditoria diária, saúde semanal, fechamento do mês
# ---------------------------------------------------------------------------
AUDIT_TIME = datetime_time(18, 0)
AUDIT_SAMPLE = int(os.getenv("AUDIT_SAMPLE", "10"))
WEEKLY_HEALTH_TIME = datetime_time(9, 40)
MONTH_CLOSE_TIME = datetime_time(10, 0)


def _rows_between(title: str, headers: list[str], start: date, end: date) -> list[dict[str, str]]:
    ws = _lyra_ws(title, headers)
    if ws is None:
        return []
    out = []
    for _, r in _worksheet_rows_with_header(ws):
        d = _parse_any_date(str(r.get("Data") or "").split(" ")[0])
        if d and start <= d <= end:
            out.append(r)
    return out


def _daily_audit(now: datetime) -> None:
    import random
    rows = [r for r in _rows_between(CONVERSAS_WORKSHEET_TITLE, CONVERSAS_HEADERS, now.date(), now.date())
            if r.get("Resposta") and r.get("Rota") not in {"lembrete", "aprendizado"}]
    if not rows:
        return
    sample = random.sample(rows, min(AUDIT_SAMPLE, len(rows)))
    items = [{"id": i + 1, "escopo": r.get("Escopo"), "pergunta": str(r.get("Pergunta"))[:500],
              "resposta": str(r.get("Resposta"))[:1500]} for i, r in enumerate(sample)]
    prompt = (
        "TAREFA INTERNA DO APP — auditoria de qualidade. Não chame subagentes. Responda APENAS com JSON válido.\n"
        "Avalie cada resposta da Lyra (agente de gestão das EPSs AeC e CSU do iFood) contra estas regras:\n"
        "1) respondeu o que foi perguntado; 2) percentual com n; 3) recorte dito (padrão: mês); 4) escopo 'AeC' ou 'CSU' "
        "não mostra dado da outra EPS; 5) não promete o que não faz ('vou lembrar', 'te mando depois'); 6) não expõe "
        "bastidor (subagente, SQL, tabela, inconsistência da conta); 7) não chuta política (sem base, diz que não sabe); "
        "8) Agentforce CX não é tratada como fila de EPS; 9) formato limpo (negrito com um asterisco, sem tabela).\n"
        f"Respostas: {json.dumps(items, ensure_ascii=False)}\n"
        'Formato: {"itens": [{"id": 1, "ok": true, "regra": "<nº da regra violada ou vazio>", "motivo": "<1 frase>"}]}'
    )
    try:
        data = json.loads(_strip_json_code_blocks(ask_toqan(prompt, max_attempts=60)))
        res = data.get("itens") if isinstance(data, dict) else None
    except Exception:
        logger.warning("Audit failed", exc_info=True)
        return
    if not isinstance(res, list):
        return
    bad = [x for x in res if isinstance(x, dict) and not x.get("ok")]
    lines = [f"🔎 *Auditoria do dia · {now.strftime('%d/%m')}* — {len(res) - len(bad)} de {len(res)} respostas ok "
             f"(amostra de {len(rows)} conversas)"]
    for x in bad[:8]:
        i = int(x.get("id") or 0) - 1
        link = sample[i].get("Link") if 0 <= i < len(sample) else ""
        q = str(sample[i].get("Pergunta"))[:80] if 0 <= i < len(sample) else ""
        lines.append(f"• _{q}_ — regra {x.get('regra')}: {x.get('motivo')}" + (f" <{link}|ver>" if link else ""))
    _alert("\n".join(lines))


def _weekly_health(now: datetime) -> None:
    start = now.date() - timedelta(days=7)
    end = now.date() - timedelta(days=1)
    conv = _rows_between(CONVERSAS_WORKSHEET_TITLE, CONVERSAS_HEADERS, start, end)
    rates = _rows_between(AVALIACOES_WORKSHEET_TITLE, AVALIACOES_HEADERS, start, end)
    if not conv and not rates:
        _alert(f"🩺 *Saúde da Lyra · {start.strftime('%d/%m')} a {end.strftime('%d/%m')}* — nenhuma conversa registrada.")
        return
    secs = sorted(_to_float(r.get("Segundos")) or 0 for r in conv)
    avg = sum(secs) / len(secs) if secs else 0
    p90 = secs[int(0.9 * (len(secs) - 1))] if secs else 0
    by_scope: dict[str, int] = {}
    by_route: dict[str, int] = {}
    for r in conv:
        by_scope[r.get("Escopo") or "?"] = by_scope.get(r.get("Escopo") or "?", 0) + 1
        by_route[r.get("Rota") or "?"] = by_route.get(r.get("Rota") or "?", 0) + 1
    errs = sum(1 for r in conv if r.get("Status") == "erro")
    naosei = sum(1 for r in conv if r.get("Status") == "nao_sei")
    up = sum(1 for r in rates if r.get("Reação") == "👍")
    down = [r for r in rates if r.get("Reação") == "👎"]
    lines = [f"🩺 *Saúde da Lyra · {start.strftime('%d/%m')} a {end.strftime('%d/%m')}*", "",
             f"• Conversas: *{len(conv)}* de {len({r.get('Quem') for r in conv})} pessoas · "
             + " · ".join(f"{k} {v}" for k, v in sorted(by_scope.items(), key=lambda x: -x[1])),
             f"• Tempo de resposta: média {_bfmt(avg / 60)} min · 90% em até {_bfmt(p90 / 60)} min",
             f"• Erros: {errs} · \"não sei\": {naosei} · 👍 {up} · 👎 {len(down)}",
             "• Mais pedidas: " + " · ".join(f"{k} {v}" for k, v in sorted(by_route.items(), key=lambda x: -x[1])[:5])]
    if down:
        lines += ["", "👎 *Respostas para revisar*"]
        for r in down[:8]:
            lines.append(f"• _{str(r.get('Pergunta') or r.get('Resposta'))[:90]}_" +
                         (f" <{r.get('Link')}|ver>" if r.get("Link") else ""))
    _alert("\n".join(lines))


def _eps_weekly_series(eps: str) -> list[str]:
    """CSAT da EPS nas 4 últimas semanas (s4 → s1), pela Indicadores (pedido 8.4c)."""
    import csv as _csv
    rng = _weeks_ranges()
    sem = "; ".join(f"s{i + 1} = {a.strftime('%d/%m/%Y')} a {b.strftime('%d/%m/%Y')}" for i, (a, b) in enumerate(rng))
    prompt = (f"{_scope_instruction(eps)}\n\nTAREFA INTERNA DO APP — CSAT por semana. Não é mensagem para o Slack.\n"
              f"Chame a *Lyra Indicadores* com 'EPS: {eps}', 'Pedido: CSAT por semana (CSV)' e 'Semanas: {sem}'. "
              "Responda APENAS o CSV no corpo da resposta, cabeçalho: semana;aval;prom. Falhou: 'ERRO: <motivo>'.")
    try:
        answer = _ask_base(prompt)
    except Exception:
        return []
    if _is_error_answer(answer):
        return []
    vals: dict[int, float] = {}
    for row in _csv.reader(io.StringIO(_strip_json_code_blocks(answer).replace("```", "")), delimiter=";"):
        if len(row) >= 3:
            m = re.search(r"([1-4])", row[0])
            a, p = _to_float(row[1].replace(",", ".")), _to_float(row[2].replace(",", "."))
            if m and a:
                vals[int(m.group(1))] = (p or 0) / a * 100
    return [f"{_bfmt(vals[i])}%" for i in (4, 3, 2, 1) if i in vals]


def _first_business_day(year: int, month: int) -> date:
    d = date(year, month, 1)
    while not _is_business_day(d):
        d += timedelta(days=1)
    return d


def _month_close_text(tenant: Tenant, today: date) -> str | None:
    eps = tenant.eps
    if not eps:
        return None
    start, end = _prev_month_bounds(today)
    rows = _day_table((start, end))
    if not rows:
        return None
    g = _scope_rows(rows, eps)
    if not g:
        return None
    mes = _MESES[start.month - 1]
    c, n, meta = _agg(g, "mes")
    lines = [f"📅 {_status_dot(c / meta * 100) if meta else '⚪'} *Fechamento de {mes} ·* `{eps}` *—* CSAT {_bfmt(c)}%"
             + (f" (meta {_bfmt(meta)}%)" if meta else "") + f" · n={_fmt_int(n)}", ""]
    segs = _segment_lines(g, eps, "mes", end)
    if segs:
        lines += ["🎯 *Metas combinadas*"] + segs + [""]
    lines.append("📍 *Por fila*")
    ranked = sorted(g, key=lambda r: (_impact(g, [r]) or 0))
    for r in ranked:
        cr, nr, _ = _agg([r])
        if cr is None:
            continue
        lines.append(f"{_status_dot(cr / r['meta'] * 100) if r.get('meta') else '⚪'} {r['fila']} · *{_bfmt(cr)}%* · "
                     + (f"meta {_bfmt(r['meta'])}%" if r.get("meta") else "sem meta") + f" · n={_fmt_int(nr)}")
    weeks = None
    try:
        weeks = _fetch_weekly_rows(eps)
    except Exception:
        weeks = None
    serie = _eps_weekly_series(eps)
    if len(serie) >= 2:
        lines += ["", "📈 *Últimas 4 semanas* (CSAT da EPS, da mais antiga para a mais recente)", "• " + " → ".join(serie)]
    if weeks:
        rein = sum(1 for w in weeks.values() if w["n"] == 4 and w["q4"] == 4)
        if rein:
            lines.append(f"• 🔁 {rein} reincidente(s) 4 semanas no Q4")
    try:
        gc = _safe_google_client()
        ws = _ensure_worksheet(_open_spreadsheet(gc), "Compromissos", COMPROMISSOS_HEADERS) if gc else None
        comp = [r for _, r in _worksheet_rows_with_header(ws)] if ws is not None else []
    except Exception:
        comp = []
    comp = [r for r in comp if _eps_matches(r.get("EPS") or "", eps)
            and (_parse_any_date(str(r.get("Data Inicio") or "")) or date.min) >= start
            and (_parse_any_date(str(r.get("Data Inicio") or "")) or date.max) <= end]
    if comp:
        ok = sum(1 for r in comp if _norm_text(r.get("Sucesso")) in {"sim", "ok", "cumprido", "melhorou"})
        nr = sum(1 for r in comp if _norm_text(r.get("Ação Tomada")) == _norm_text(SEM_RESPOSTA))
        lines += ["", "📌 *Compromissos do mês*",
                  f"• {len(comp)} registrados · {ok} com resultado positivo · {nr} cobrança(s) sem resposta"]
    pontos = []
    for r in ranked[:2]:
        imp = _impact(g, [r])
        if imp is not None and imp < 0:
            pontos.append(f"{r['fila']}: tirou {_bfmt(abs(imp), 2)} p.p. da {eps}"
                          + (f", puxada por {r['motivo']}" if r.get("motivo") else "") + ".")
    if weeks and any(w["n"] == 4 and w["q4"] == 4 for w in weeks.values()):
        pontos.append("Reincidentes 4 semanas: plano individual com a supervisão (\"reincidentes da " + eps + "\" traz a lista).")
    if pontos:
        lines += ["", "🎯 *3 pontos para o mês*"] + [f"{i}. {p}" for i, p in enumerate(pontos[:3], 1)]
    lines += ["", "_Plano do mês aqui na thread: *ação · responsável · prazo*._"]
    return "\n".join(lines)


def _team_routines_tick(now: datetime) -> None:
    today = now.date()
    if now.time() >= AUDIT_TIME and not STATE.get(f"audit:{today.isoformat()}"):
        STATE.set(f"audit:{today.isoformat()}", "1")
        threading.Thread(target=_daily_audit, args=(now,), daemon=True).start()
    if today.weekday() == 0 and now.time() >= WEEKLY_HEALTH_TIME and not STATE.get(f"health:{today.isoformat()}"):
        STATE.set(f"health:{today.isoformat()}", "1")
        threading.Thread(target=_weekly_health, args=(now,), daemon=True).start()
    if today == _first_business_day(today.year, today.month) and now.time() >= MONTH_CLOSE_TIME:
        for tenant in TENANTS:
            key = _skey("month_close", tenant, today)
            if not tenant.eps or STATE.get(key):
                continue
            STATE.set(key, "1")

            def run(t: Tenant = tenant) -> None:
                try:
                    text = _month_close_text(t, today)
                    if text:
                        _post_sections(t.channel, text)
                    else:
                        _alert(f"[{t.key}] Fechamento do mês não saiu (tabela do mês anterior indisponível).")
                except Exception as exc:
                    _alert(f"[{t.key}] Fechamento do mês falhou: {type(exc).__name__}")
            threading.Thread(target=run, daemon=True).start()


def _process_event(event: dict[str, Any], say: Callable[..., Any], in_thread: bool, client: Any = None) -> None:
    """Processa a mensagem e registra a conversa (pergunta, resposta, tempo, rota) para auditoria e saúde."""
    started = time.time()
    said: list[str] = []
    said_ts: list[str] = []
    orig_say = say

    def say(*args: Any, **kwargs: Any) -> Any:  # noqa: F811 — guarda o que foi respondido
        text = kwargs.get("text") if "text" in kwargs else (args[0] if args else "")
        said.append(str(text or ""))
        resp = orig_say(*args, **kwargs)
        try:
            ts = _resp_get(resp, "ts") if resp is not None else None
            if ts:
                said_ts.append(str(ts))
        except Exception:
            pass
        return resp

    failed = {"v": False}
    _TOQAN_TL.interactive = True  # conversa com gente: prioridade no Toqan
    try:
        _process_event_inner(event, say, in_thread, client, failed)
        if FEEDBACK_REACTIONS and said_ts and not failed["v"] and \
                str(event.get("_route") or "livre") not in {"lembrete", "aprendizado", "report_manual", "mop_upload"}:
            _add_feedback_reactions(str(event.get("channel") or ""), said_ts[-1])
    finally:
        _TOQAN_TL.interactive = False
        if not event.get("_skip_log"):
            try:
                question = _strip_mentions(str(event.get("text") or ""))
                _log_conversation(event, event.get("_eps"), question, said, time.time() - started, failed["v"])
            except Exception:
                logger.warning("Conversation log failed", exc_info=True)


def _pending_question(event: dict[str, Any]) -> str:
    """Última mensagem da mesma pessoa na thread, depois da última resposta da Lyra (a pergunta que ela não viu)."""
    try:
        msgs = _fetch_thread(str(event.get("channel") or ""), str(event.get("thread_ts") or ""))
    except Exception:
        return ""
    bot, user = _bot_user_id(), event.get("user")
    pending = ""
    for m in msgs:
        if str(m.get("ts")) == str(event.get("ts")):
            break
        if m.get("bot_id") or (bot and m.get("user") == bot):
            pending = ""
        elif m.get("user") == user:
            txt = _strip_mentions(str(m.get("text") or "")).strip()
            if txt:
                pending = txt
    if pending:
        event["text"] = f"{event.get('text') or ''} {pending}".strip()
    return pending


def _process_event_inner(event: dict[str, Any], say: Callable[..., Any], in_thread: bool, client: Any,
                         failed: dict[str, bool]) -> None:
    """Processa upload de MOP ou repassa a mensagem para o Toqan."""
    event_key = _event_key(event)
    with _IN_FLIGHT_LOCK:
        if event_key in _IN_FLIGHT:
            return
        _IN_FLIGHT.add(event_key)

    question = _strip_mentions(str(event.get("text") or ""))
    if not question.strip() and event.get("thread_ts") and not event.get("files"):
        question = _pending_question(event) or question  # só "@Lyra" na thread: responde a mensagem que ficou sem resposta
    try:
        allowed, eps = _event_scope(event)
        event["_eps"] = eps
        if not allowed:
            event["_skip_log"] = True
        if not allowed and str(event.get("channel") or "") in ALERT_CHANNEL_IDS:
            _monitoring_channel_reply(question, say, event, in_thread)
            return
        if not allowed:
            is_im = event.get("channel_type") == "im"
            _say(say, DM_NOT_ALLOWED_MESSAGE if is_im else
                 f"{CHANNEL_NOT_CONFIGURED_MESSAGE} (canal `{event.get('channel')}`)", event, in_thread)
            logger.warning("Channel not configured: %s (scopes: %s)", event.get("channel"), sorted(CHANNEL_SCOPE))
            return
        mop_answer = _process_mop_upload(event, client, eps)
        if mop_answer is not None:
            event["_route"] = "mop_upload"
            _say(say, mop_answer, event, in_thread=True)
            return
        if not question:
            _say(say, "Oi! Sou a Lyra. Como posso ajudar?", event, in_thread)
            return

        if eps is None and _is_token_renewed_message(question):
            expiry = _mark_token_renewed(_now_brazil().date())
            reminder = expiry - timedelta(days=1)
            _say(say, f"Anotado ✅ Token novo vale até {_format_date(expiry)}; te lembro dia {_format_date(reminder)}. "
                      "Vou testar os agentes agora…", event, in_thread)
            _say(say, _agents_summary(_run_agent_checks(_now_brazil())), event, in_thread)
            return
        targets = _report_targets(question) if eps is None else None
        if targets:
            event["_route"] = "report_manual"
            _say(say, f"Rodando o report agora ({', '.join(t.key for t in targets)}), as EPSs em paralelo. Te aviso aqui "
                      "quando cada uma sair (costuma levar de 5 a 20 min).", event, in_thread)
            results: dict[str, str] = {}

            def run_one(t: Tenant) -> None:
                results[t.key] = "\n".join(_run_report_now([t]))
                _say(say, results[t.key], event, in_thread)
                if PREWARM_BASES and "✅" in results[t.key]:
                    _prewarm_bases(t.eps or "")

            workers = [threading.Thread(target=run_one, args=(t,), daemon=True) for t in targets]
            for w in workers:
                w.start()
            for w in workers:
                w.join()
            return
        if eps is None and _DIAG_RE.search(_norm_text(question)):
            event["_route"] = "diagnostico"
            _say_sections(say, _diagnostics_text(), event, in_thread)
            return
        if eps is None and _is_data_test_request(question):
            _say(say, _agents_summary(_run_agent_checks(_now_brazil())), event, in_thread)
            return

        try:
            if _handle_reminder(event, question, say, in_thread):
                event["_route"] = "lembrete"
                return
        except Exception:
            logger.warning("Reminder handling failed", exc_info=True)
        try:
            if _handle_learning(event, question, eps, say, in_thread):
                event["_route"] = "aprendizado"
                return
        except Exception:
            logger.warning("Learning handling failed", exc_info=True)
        if _TRAINING_RE.search(_norm_text(question)):
            thread_txt = _thread_context(event) if event.get("thread_ts") else ""
            fila_t = (_fila_in_question(question, eps) or (_status_fila(question, eps) if eps else None)
                      or _fila_in_question(thread_txt[-2000:], eps))
            theme = _TRAINING_THEME_RE.search(_norm_text(question))
            if theme and not fila_t:  # treinamento de tema (Will, macro, processo…): não é pelo CSAT da fila
                event["_route"] = "treinamento:tema"
                event["_training_theme"] = theme.group(0)
            elif not fila_t:  # "quem eu treino?": treinamento começa pelo problema, não pela lista
                ask = _training_question(eps)
                if ask:
                    event["_route"] = "treinamento:pergunta"
                    _say(say, ask, event, in_thread)
                    return
            else:
                event["_route"] = "treinamento"
                question = (f"{question}\n(Fila: {fila_t})")
                event["_training"] = fila_t
        if CREAD and _DAYLOG_RE.search(_norm_text(question)):
            _ontem = "ontem" in _norm_text(question)
            day_txt = _daylog_text([eps] if eps else list(EPS_CELULAS),
                                   day=(_as_date(_today_brazil()) - timedelta(days=1)) if _ontem else None,
                                   title="No canal ontem" if _ontem else "No canal hoje")
            event["_route"] = "registro do dia"
            _say_sections(say, day_txt or "Hoje ainda não registrei nada relevante nas conversas do canal: só os "
                                          "controles de rotina. 🌙", event)
            return
        if _NEWS_RE.search(_norm_text(question)) and not _is_analytical(question):
            news = None
            try:
                news = _table_answer("resultado", eps)
            except Exception:
                logger.warning("News answer failed", exc_info=True)
            if news:  # "o que tem de novidade?": responde na hora com a tabela do dia, sem análise pesada
                event["_route"] = "novidades"
                canal = _daylog_text([eps] if eps else list(EPS_CELULAS), limit=5) if CREAD else ""
                _say_sections(say, news + ("\n\n" + canal if canal else "") + "\n\n" + NEWS_FOLLOWUP, event)
                return
        if not _report_block_for(str(event.get("channel") or ""), str(event.get("thread_ts") or "")):
            focus: dict[str, Any] = {}
            try:
                table = _table_answer(question, eps, focus)
            except Exception:
                logger.warning("Day table answer failed", exc_info=True)
                table = None
            if table:
                event["_route"] = "tabela"
                geral = not re.search(r"\b(csat|nota\w*|avaliac\w*|tma|sla|tempo|primeira resposta|fila\w*|ranking|impact\w*)\b",
                                      _norm_text(question)) and bool(_capa_template()[0])
                _say_sections(say, table + ("\n\n_TMA e SLA vêm logo abaixo, só um minutinho._ ⏳" if geral else ""), event)
                if geral:  # "como tá a AeC?": o retrato inclui eficiência, não só CSAT
                    try:
                        ini_c, fim_c, label_c = _capa_period("", event)
                        rows_c, _ = _capa_rows(ini_c, fim_c, None)
                        resumo = _capa_resumo(rows_c, eps or _eps_in_text(question), label_c) if rows_c else ""
                        _say(say, resumo or "TMA e SLA não voltaram agora; se quiser, me pede \"TMA e SLA\" daqui a pouco.",
                             event, True)
                    except Exception:
                        logger.warning("CAPA summary after table failed", exc_info=True)
                if not (_CAUSE_FOLLOW_RE.search(_norm_text(question)) and focus.get("fila")):
                    return
                # pergunta dupla ("qual fila mais impacta e quais as causas?"): emenda a análise de causa da fila
                event["_route"] = "tabela+causa"
                question = f"Quais as principais causas do CSAT da {focus['fila']} no mês? Por que está assim?"
        in_report_thread = bool(_report_block_for(str(event.get("channel") or ""), str(event.get("thread_ts") or "")))
        asks = _is_question_like(question)
        analytical = _is_analytical(question)  # "por que", "quem piorou", "quanto contribuiu": análise livre
        progress = _Progress(event)
        efic_extra = ""
        ind_e = _efic_indicator(question)
        if ind_e and re.search(r"\b(motivo\w*|ofensor\w*|trein\w*|reciclag\w*|capacit\w*|por que|porque|pq|"
                               r"o que (puxa|explica|pesa|impacta))\b", _norm_text(question)) and not re.search(
                r"\b(analista\w*|operador\w*|casos?|tickets?)\b", _norm_text(question)):
            event["_route"] = f"motivos_{ind_e}"
            ini_e, fim_e, label_e = _capa_period(question, event)
            fila_e2 = _fila_ref(question, eps, {})
            nome_ind = "TMA" if ind_e == "tma" else "SLA de 1ª resposta"
            _say(say, f"Vou levantar os motivos de contato que mais pesam no {nome_ind}"
                      + (f" de `{fila_e2}`" if fila_e2 else "") + f" ({label_e}). Leva alguns minutos ⏳", event, in_thread=True)
            rows_e, prob_e = _motivos_efic_rows(eps, ini_e, fim_e)
            texto_e = _render_motivos_efic(rows_e, ind_e, label_e, fila_e2) if rows_e else ""
            if not texto_e:
                progress.done()
                _say(say, prob_e or f"Nenhum motivo está pesando contra o {nome_ind} nesse recorte.", event, in_thread=True)
                return
            if _TRAINING_RE.search(_norm_text(question)) or re.search(r"\btrein\w*", _norm_text(question)):
                efic_extra = TRAINING_EFIC_INSTRUCTION.replace("{ind}", nome_ind) + (
                    "DADOS (calculados pelo app com as regras da CAPA — use só estes números):\n" + texto_e + "\n\n")
            else:
                progress.done()
                _say(say, texto_e, event, in_thread=True)
                return
        if not efic_extra and _is_capa_request(question):
            event["_route"] = "capa"
            _say(say, "Já puxo TMA e SLA pra você ⏳", event, in_thread=True)
            resp_capa = _send_capa(event, client, eps, question)
            progress.done()
            if resp_capa:
                _say(say, resp_capa, event, in_thread=True)
            return
        if _is_case_list_request(question):
            event["_route"] = "avaliacoes"
            _say(say, f"Vou montar a base caso a caso de {({'csat': 'CSAT', 'sla': 'SLA de 1ª resposta', 'tma': 'TMA'})[_case_indicator(question)]} "
                      "e a abertura por operador. Leva alguns minutos ⏳", event, in_thread=True)
            problem = _send_case_list(event, client, eps, question)
            progress.done()
            if problem:
                _say(say, problem, event, in_thread=True)
            return
        if not efic_extra and _is_tma_pessoas_request(question) and (asks or not in_report_thread):
            event["_route"] = "tma_pessoas"
            progress("Vou ver quem mais pesa no TMA (analistas e supervisores), já te mando. ⏳")
            try:
                problem = _send_tma_pessoas(event, client, eps, question, say, progress)
            finally:
                progress.done()
            if problem:
                _say(say, problem, event, in_thread)
            return
        if not efic_extra and _is_pessoas_impacto_request(question) and (asks or not in_report_thread):
            event["_route"] = "pessoas_impacto"
            progress("Vou ver quem mais pesa no CSAT (operadores e supervisores), já te mando. ⏳")
            try:
                problem = _send_pessoas_impacto(event, client, eps, question, say, progress)
            finally:
                progress.done()
            if problem:
                _say(say, problem, event, in_thread)
            return
        count_ref = bool(event.get("thread_ts")) and bool(re.search(
            r"\bquant[oa]s\b.*\b(desses|dessas|destes|destas|deles|delas|casos?|tickets?|pendent\w*)\b", _norm_text(question)))
        count_extra = ""
        if count_ref and _TEAM_RE.search(_norm_text(question)):
            leader_c, team_c, prob_c = _case_team(question, event, eps)
            if team_c:
                count_extra = (f"INFORMAÇÃO INTERNA PARA A LYRA: a pessoa quer a MESMA contagem da resposta anterior desta "
                         f"conversa (ex.: casos pendentes), só da equipe de {leader_c}. Refaça a mesma consulta pedindo à "
                         f"Lyra Indicadores o filtro do operador dono do caso por estes e-mails: {', '.join(team_c)}. "
                         "Responda o número e, se couber em poucas linhas, quantos por operador. NÃO traga CSAT nem "
                         "visão de equipe.\n\n")
                event["_route"] = "contagem_equipe"
        if count_extra or efic_extra:
            pass
        elif _is_team_request(question) and not analytical and (asks or not in_report_thread):
            event["_route"] = "equipe"
            progress("Vou montar o resultado da equipe, já te mando. ⏳")
            try:
                problem = _send_team_view(event, client, eps, question, say, in_thread)
            finally:
                progress.done()
            if problem:
                _say(say, problem, event, in_thread)
            return

        if _is_reincidentes_request(question) and not analytical and (asks or not in_report_thread):
            event["_route"] = "reincidentes"
            progress("Vou puxar as últimas 4 semanas dos operadores, já te mando. ⏳")
            try:
                problem = _send_reincidentes(event, client, eps, question, say, in_thread)
            finally:
                progress.done()
            if problem:
                _say(say, problem, event, in_thread)
            return

        op_question = question
        if not _is_operators_excel_request(question) and len(question.split()) <= 4:
            prev = _last_dm_human_text(event)  # "ontem" respondendo a um pedido de operadores
            if prev and _is_operators_excel_request(prev):
                op_question = f"{prev} {question}"
        wants_file = bool(re.search(r"\b(excel|planilha|xlsx|arquivo)\b", _norm_text(op_question)))
        if (_is_operators_excel_request(op_question) and (wants_file or not analytical)
                and (asks or not in_report_thread)):
            if _operator_names_allowed(eps) and not wants_file:  # direto no chat, com nome (cada EPS só vê os dela)
                event["_route"] = "operadores"
                progress("Vou puxar o resultado por operador, já te mando. ⏳")
                try:
                    problem = _send_operators_inline(event, client, eps, op_question, say, in_thread)
                finally:
                    progress.done()
                if problem:
                    _say(say, problem, event, in_thread)
                return
            _say(say, "Resultado individual vai em planilha, para não expor operadores aqui. Já te mando. ⏳",
                 event, in_thread=True)
            problem = _send_operators_excel(event, client, eps, op_question)
            if problem:
                _say(say, problem, event, in_thread)
            return

        if _is_mop_export_request(question):
            event["_route"] = "mop"
            problem = _send_mop_export(event, client, eps or _eps_in_text(question))
            if problem:
                _say(say, problem, event, in_thread)
            return

        if _is_deck_request(question):
            event["_route"] = "material"
            fila_d = _fila_ref(question, eps, event)
            if fila_d:
                _say(say, f"Bora! Vou montar o material de `{fila_d}` em pptx: resultado do mês, movimentos de mix e "
                          "performance e próximos passos. Leva alguns minutos ⏳", event, in_thread=True)
            problem = _send_deck(event, client, eps, question)
            progress.done()
            if problem:
                _say(say, problem, event, in_thread=True)
            return

        if _is_chart_request(question):
            event["_route"] = "grafico"
            _say(say, "Vou montar o gráfico, já te mando aqui. ⏳", event, in_thread=True)
            problem = _send_chart(event, client, eps, question, send_progress=lambda m: _say(say, m, event, in_thread=True))
            if problem:
                _say(say, problem, event, in_thread)
            return

        if _is_data_excel_request(question):
            event["_route"] = "planilha"
            _say(say, "Vou montar a planilha, já te mando aqui. ⏳", event, in_thread=True)
            problem = _send_data_excel(event, client, eps, question)
            if problem:
                _say(say, problem, event, in_thread)
            return

        send_progress = progress  # uma mensagem de andamento só, editada e apagada quando a resposta chega

        extra = count_extra or efic_extra
        if _ESTEIRA_REQ_RE.search(_norm_text(question)):
            fila_e = _fila_ref(question, eps, event)
            if fila_e:
                d1_e = _d1_context(question, event)
                _say(say, f"Vou montar a esteira de impacto de `{fila_e}` ({'D-1' if d1_e else 'mês'}). Leva alguns minutos ⏳",
                     event, in_thread=True)
                ok = _post_esteira_on_demand(event, eps, f"{question} ontem" if d1_e else question)
                progress.done()
                if not ok:
                    _say(say, f"Não consegui montar a esteira de `{fila_e}` agora. Tenta de novo daqui a pouco?", event,
                         in_thread=True)
                return
        if _is_cause_request(question) and not _MOTIVOS_RE.search(_norm_text(question)):
            fila_q = _fila_ref(question, eps, event)
            mix_only = bool(_MIX_ONLY_RE.search(_norm_text(question)))
            d1_ctx = _d1_context(question, event)
            block_q = _report_block_for(str(event.get("channel") or ""), str(event.get("thread_ts") or ""))
            if fila_q or block_q:
                # esteira (Qualidade) em paralelo com a análise de variação (Indicadores): a pessoa não fica esperando
                fila_v = block_q[1].get("fila") if block_q else fila_q
                note = None if mix_only else _above_meta_note(fila_v, eps, "d1" if d1_ctx else "mes")
                if note:  # a fila bateu a própria meta: o "ruim" é peso no consolidado, não desempenho
                    progress.done()
                    _say(say, note, event, in_thread=True)
                    return
                _say(say, (f"Vou olhar o mix de motivos de `{fila_v}` (este mês x referência). Já te trago ⏳" if mix_only else
                           f"Vou levantar as causas em `{fila_v}`: primeiro a variação (mix de motivos e response rate); "
                           "se não for só mix, em seguida a esteira de impacto por pilar. Leva alguns minutos ⏳"),
                     event, in_thread=True)
                cur, ref, l_cur, l_ref = _variation_periods(f"{question} ontem" if d1_ctx else question)
                var_data = {}
                if CSAT_SQL_FIXO == "on":
                    var_data = _csat_variacao_fixa(eps, fila_v, cur, ref, send_progress) or {}
                if not var_data:
                    var_answer = ask_toqan(_variation_prompt(eps, fila_v, cur, ref), progress_callback=send_progress,
                                           max_attempts=INTERACTIVE_MAX_POLLS)
                    var_data = {} if _is_error_answer(var_answer) else (_block_data_from_json(var_answer) or {})
                if not var_data and CSAT_SQL_FIXO == "fallback":  # a análise do agente não voltou: conta pelo SQL fixo
                    var_data = _csat_variacao_fixa(eps, fila_v, cur, ref, send_progress) or {}
                progress.done()
                rendered = _render_variation(fila_v, var_data, l_cur, l_ref, with_esteira=not mix_only) if var_data else None
                if rendered:
                    _say_sections(say, rendered, event)
                    rose = (_num(var_data.get("csat_atual")) or 0) >= (_num(var_data.get("csat_ref")) or 0)
                    if not mix_only and not _mix_dominant(var_data) and not rose:
                        threading.Thread(target=_post_esteira_on_demand, args=(event, eps, question), daemon=True).start()
                    return
                if not mix_only:
                    threading.Thread(target=_post_esteira_on_demand, args=(event, eps, question), daemon=True).start()
                extra = ("INFORMAÇÃO INTERNA PARA A LYRA: a esteira de impacto (pilares Operador, Tempo, Política, Parceiro, "
                         "Produto) é postada separadamente pelo app nesta thread. NÃO chame a Lyra Qualidade e NÃO liste pilares: "
                         "chame só a Lyra Indicadores (Pedido: variação do CSAT) e responda a variação (efeito mix x performance "
                         "e response rate). Feche com 1 frase sobre o que é da EPS cobrar.\n\n")
        if not extra and (_is_identity_question(question) or _identity_thread(event, question)):
            extra = IDENTITY_INSTRUCTION
            event["_route"] = "apresentacao"
        elif not extra and _is_plan_request(question):
            extra = PLAN_INSTRUCTION
        elif not extra and _is_clube_question(question) and not _DATA_WORDS_RE.search(_norm_text(question)):
            extra = CLUBE_INSTRUCTION
        elif not extra and _is_knowledge_question(question):
            extra = KNOWLEDGE_INSTRUCTION
        elif not extra and _EFICIENCIA_RE.search(_norm_text(question)) and not re.search(
                r"\b(analista\w*|operador\w*|equipe|time d[aeo]|supervisor\w*|casos?|tickets?|por que|porque|pq)\b",
                _norm_text(question)) and not re.search(r"\bcsat\b", _norm_text(question)):
            extra = EFICIENCIA_INSTRUCTION
            event["_route"] = "eficiencia"
        elif not extra and _MOTIVOS_RE.search(_norm_text(question)):
            extra = MOTIVOS_INSTRUCTION
            event["_route"] = "motivos"
            if CSAT_SQL_FIXO == "on" and not _efic_indicator(question):
                ini_m, fim_m, label_m = _capa_period(question, event)
                dados_m = _csat_motivos_texto(eps, _fila_ref(question, eps, event), ini_m, fim_m, label_m, send_progress)
                if dados_m:
                    extra += ("DADOS (calculados pelo app com o SQL fixo do CSAT — use só estes números, sem nova "
                              "consulta):\n" + dados_m + "\n\n")
        elif not extra and _ROSIE_EVAL_RE.search(_norm_text(question)):
            extra = ROSIE_EVAL_INSTRUCTION
        elif not extra and (_COMBO_RE.search(_norm_text(question)) or (
                event.get("thread_ts") and re.search(r"\btma\b|\bcsat\b", _norm_text(question))
                and _COMBO_RE.search(_norm_text(_thread_context(event)[-1500:])))):
            extra = COMBO_INSTRUCTION
            if re.search(r"\b(analista\w*|operador\w*)\b", _norm_text(question)):
                extra += ANALYST_TMA_INSTRUCTION
        elif not extra and (_ANALYST_TMA_RE.search(_norm_text(question)) or (
                event.get("thread_ts") and re.search(r"\btma\b", _norm_text(question))
                and _SAME_SET_RE.search(_norm_text(question)))):
            extra = ANALYST_TMA_INSTRUCTION
        elif not extra and event.get("_training"):
            extra = TRAINING_INSTRUCTION.format(fila=event["_training"])
        elif not extra and event.get("_training_theme"):
            extra = TRAINING_THEME_INSTRUCTION.format(tema=event["_training_theme"])
        elif not extra and _is_small_talk(question):
            extra = CHAT_INSTRUCTION  # conversa curta: responde rápido, sem subagentes
            event["_route"] = "conversa"
        shape = _catalog_shape(question, event) if not extra else None
        free_note = bool(shape)
        if shape:  # pergunta de indicador sem consulta pronta: análise livre com trilho, registrada para o catálogo
            event["_route"] = event.get("_route") or f"livre:{shape['key']}"
            _catalog_log(shape, question, event)
        context = _thread_context(event) or _dm_context(event)
        prompt = (f"{_scope_instruction(eps)}\n\n{_speaker_line(event)}{_date_context(question)}{context}{extra}"
                  f"{DEFAULTS_INSTRUCTION if not extra else ''}{FREE_ANALYSIS_INSTRUCTION if shape else ''}{FULL_ACCESS_INSTRUCTION if _operator_names_allowed(eps) else ''}"
                  f"{ANSWER_LAYOUT_INSTRUCTION}{_learnings_instruction(eps)}{_table_context(eps)}"
                  f"{_inject_mop_context(question, eps)}"
                  f"{_kb_context(question) if extra == KNOWLEDGE_INSTRUCTION else ''}"
                  f"{NOMINAL_INSTRUCTION if _NOMINAL_RE.search(_norm_text(question)) else ''}"
                  f"{SAME_SET_INSTRUCTION if event.get('thread_ts') and _SAME_SET_RE.search(_norm_text(question)) else ''}")
        is_plan = extra == PLAN_INSTRUCTION
        if is_plan:
            prompt = _plan_context(question, eps) + prompt
        answer = _recent_answer(prompt)
        if answer is None:
            try:
                if is_plan:
                    try:
                        answer = ask_toqan(prompt, progress_callback=send_progress, max_attempts=PLAN_MAX_POLLS)
                    except ToqanAPIError as exc:
                        if "timed out" not in str(exc):
                            raise
                        send_progress("A análise completa está pesada agora; vou te mandar o plano com o que já tenho. ⏳")
                        answer = ask_toqan(_plan_fallback_prompt(question, eps), max_attempts=60)
                else:
                    answer = ask_toqan(prompt, progress_callback=send_progress, max_attempts=INTERACTIVE_MAX_POLLS)
            finally:
                progress.done()
            _remember_answer(prompt, answer)
        _passive_access_check(answer)
        answer = _strip_file_promises(answer)
        answer = _route_n3_flags(answer, f"pergunta de {_first_name(str(event.get('user') or '')) or 'alguém'}: "
                                          f"_{question[:120]}_", event)
        esc_q = _parse_escalation(answer or "")
        _promessa = re.compile(r"[^.\n]*\b(vou|vamos|irei) (confirmar|validar|checar|verificar)[^.\n]*\.?", re.I)
        if not esc_q and _promessa.search(answer or ""):
            ch_p, th_p = str(event.get("channel") or ""), str(event.get("thread_ts") or event.get("ts") or "")
            if STATE.get(f"escalated:{ch_p}:{th_p}"):  # o dono já foi chamado nessa thread: não promete de novo
                answer = _promessa.sub("", answer).strip() + " O time já foi chamado aqui na thread pra confirmar."
            else:  # prometeu confirmar: confirma de verdade, chamando o dono do tema
                esc_q = ("experiencia", question[:200])
        if esc_q:  # dúvida que a base não responde: chama o dono do tema de verdade (e aprende com a resposta)
            answer = re.split(r"`?ESCALAR\s*:", answer, maxsplit=1)[0].strip()
            answer = re.sub(r"[^.\n]*\b(vou|vamos) (confirmar|validar|checar)[^.\n]*\.?", "", answer).strip()
        if _operator_names_allowed(eps):
            try:
                answer = _with_operator_names(answer)
            except Exception:
                logger.warning("Could not add operator names", exc_info=True)
        conv_blocks = _split_blocks(answer or "")
        if conv_blocks:
            day = _today_brazil() - timedelta(days=1)
            for fila, title, body in _prepare_blocks(conv_blocks, _as_date(day)):
                _say_sections(say, title + ("\n\n" + _tag_block(fila, body)[0] if body else ""), event)
            return
        if THREAD_DELIMITER in (answer or ""):
            # report pedido em conversa: principal + detalhe, sem o marcador aparecer
            main, detail = _split_report(answer)
            _say(say, _tag_owners(main) or EMPTY_ANSWER_MESSAGE, event, in_thread)
            if detail:
                _say(say, detail, event, in_thread=True)
            return
        if free_note and answer and not esc_q and not _is_error_answer(answer) and re.search(r"\d", answer):
            answer = answer.rstrip() + "\n\n" + FREE_ANALYSIS_NOTE
        if _looks_sectioned(answer):
            _say_sections(say, answer, event, in_thread)
        else:
            _say(say, answer or EMPTY_ANSWER_MESSAGE, event, in_thread)
        if esc_q:
            ch_q = str(event.get("channel") or "")
            dono = "o Gustavo" if esc_q[0] == "experiencia" else "o Michael"
            if ch_q.startswith("D"):
                _say(say, f"Isso quem fecha é {dono} — vou deixar a dúvida com ele. 🙂", event, in_thread=True)
                _alert(f"❓ Dúvida sem resposta na base (DM, {dono[2:]}): _{esc_q[1]}_ "
                       f"({_permalink(ch_q, str(event.get('thread_ts') or event.get('ts') or ''))})")
            elif not STATE.get(f"escalated:{ch_q}:{event.get('thread_ts') or event.get('ts') or ''}"):
                _escalate(ch_q, str(event.get("thread_ts") or event.get("ts") or ""), eps, esc_q[0], esc_q[1],
                          lambda t: _say(say, t, event, in_thread=True), shadow=bool(eps and _status_shadow(eps)),
                          decisao=bool(answer))
        if (_NOMINAL_RE.search(_norm_text(question)) or (event.get("thread_ts") and _SAME_SET_RE.search(_norm_text(question)))) \
                and re.search(r"ficaram de fora|limite de exibi|nao aparecem|não aparecem|planilha|excel|lista completa",
                                                                  _norm_text(answer or "")):
            # nominal grande: manda a lista completa em planilha sem a pessoa precisar pedir de novo
            _say(say, "Segue a lista completa em planilha, já te mando aqui. ⏳", event, in_thread=True)
            problem = _send_data_excel(event, client, eps, f"{question} — lista completa, todos os nomes, mesmo "
                                                            "critério da resposta acima")
            if problem:
                _say(say, problem, event, in_thread)
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
        failed["v"] = True
        logger.exception("Lyra could not process Slack event")
        timed_out = "timed out" in str(exc)
        _say(say, TIMEOUT_ERROR_MESSAGE if timed_out else ERROR_MESSAGE, event, in_thread)
        if timed_out:
            _alert(f"⏱️ Pergunta sem resposta por tempo esgotado: _{str(event.get('text') or '')[:200]}_ "
                   f"({_permalink(str(event.get('channel') or ''), str(event.get('thread_ts') or event.get('ts') or ''))})")
    except Exception:
        failed["v"] = True
        logger.exception("Lyra could not process Slack event")
        _say(say, ERROR_MESSAGE, event, in_thread)
    finally:
        with _IN_FLIGHT_LOCK:
            _IN_FLIGHT.discard(event_key)


def _dispatch(event: dict[str, Any], say: Callable[..., Any], client: Any, ack: Callable[[], Any]) -> None:
    ack()
    channel = event.get("channel")
    timestamp = event.get("ts")
    if channel and event.get("channel_type") != "im" and not event.get("_thread_ctx"):
        try:  # a conversa nesta thread segue sem precisar marcar a Lyra de novo
            STATE.set(f"convo:{channel}:{event.get('thread_ts') or timestamp}", "1")
        except Exception:
            pass
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


def _maybe_convo_followup(event: dict[str, Any], say: Callable[..., Any], client: Any) -> bool:
    """Conversa que começou com a @Lyra numa thread de canal: as próximas mensagens da thread são para ela, mesmo
    sem marcar de novo — a não ser que a pessoa marque outra pessoa (aí a conversa é com ela)."""
    channel = str(event.get("channel") or "")
    thread_ts = str(event.get("thread_ts") or "")
    if not thread_ts or thread_ts == str(event.get("ts") or "") or event.get("bot_id") \
            or event.get("subtype") not in (None, "file_share"):
        return False
    if not STATE.get(f"convo:{channel}:{thread_ts}"):
        return False
    bot = _bot_user_id()
    text = str(event.get("text") or "")
    if bot and f"<@{bot}>" in text:
        return False  # marcou a Lyra: o evento de menção já responde
    if any(uid != bot for uid in _MENTION_ID_RE.findall(text)):
        return False  # falando com outra pessoa
    if _report_block_for(channel, thread_ts):
        return False  # thread do report tem leitura própria
    if channel in _STATUS_CHANNEL_EPS and (STATE.get(f"topic:{channel}:{thread_ts}") == "controle"
                                           or _looks_like_status(text) or _image_files(event)):
        return False  # thread de controle: atualização da EPS segue para a leitura de controle
    if not _shadow_mention(event, client, lambda: None):
        _dispatch(event, say, client, lambda: None)
    return True


def _shadow_mention(event: dict[str, Any], client: Any, ack: Callable[[], Any]) -> bool:
    """Fase de testes: menção à Lyra no canal de indicadores da EPS. A pergunta e a resposta vão para o canal de
    testes da EPS (uma thread espelho por conversa, com o link da original); nada aparece no canal da EPS."""
    channel = str(event.get("channel") or "")
    eps = _STATUS_CHANNEL_EPS.get(channel)
    if not eps or not _status_shadow(eps):
        return False
    test_ch = STATUS_TEST_CHANNELS.get(eps) or EPS_CHANNELS.get(eps)
    if not test_ch:
        return False
    ack()
    root = str(event.get("thread_ts") or event.get("ts") or "")
    STATE.set(f"convo:{channel}:{root}", "1")
    try:
        ctx = _thread_context(event) if event.get("thread_ts") else ""
        key = f"mention_shadow:{channel}:{root}"
        parent = STATE.get(key)
        if not parent:
            link = _permalink(channel, root)
            resp = slack_app.client.chat_postMessage(
                channel=test_ch, text=f"🧪 *Teste · {eps}* — marcaram a Lyra no canal de indicadores"
                                      + (f" (<{link}|thread original>)" if link else "")
                                      + ". Eu responderia aqui; nada foi postado no canal da EPS.")
            parent = str(_resp_get(resp, "ts") or "")
            if parent:
                STATE.set(key, parent)
        question = _strip_mentions(str(event.get("text") or "")).strip()
        user = str(event.get("user") or "")
        q = slack_app.client.chat_postMessage(channel=test_ch, thread_ts=parent or None,
                                              text=f"🗨️ {('<@' + user + '>') if user else 'Pergunta'}: {question[:1500]}")
        mirror = dict(event)
        mirror.update({"channel": test_ch, "ts": str(_resp_get(q, "ts") or parent), "thread_ts": parent,
                       "_thread_ctx": ctx, "channel_type": "channel"})

        def mirror_say(text: str = "", thread_ts: str | None = None, **kwargs: Any) -> Any:
            return slack_app.client.chat_postMessage(channel=test_ch, text=text, thread_ts=thread_ts or parent, **kwargs)

        _dispatch(mirror, mirror_say, client, lambda: None)
    except Exception:
        logger.exception("[%s] Menção espelhada falhou", eps)
    return True


@slack_app.event("app_mention")
def handle_app_mention(event, say, client, ack):
    if _shadow_mention(event, client, ack):
        return
    if _is_flow_channel(str(event.get("channel") or "")):
        ack()  # o evento "message" do mesmo post já trata (chamado de moedas ou resposta pela base)
        return
    if MOP_FLOW_CHANNEL and event.get("channel") == MOP_FLOW_CHANNEL:
        # No canal do fluxo a Lyra só processa o Excel do MOP; não conversa ali.
        ack()
        if _mop_attachment(event) is not None:
            threading.Thread(target=_handle_mop_flow_event, args=(event, say, client), daemon=True).start()
        return
    _dispatch(event, say, client, ack)


LIVE_REPLY_DELAY_SECONDS = int(os.getenv("LIVE_REPLY_DELAY_SECONDS", "60"))
_LIVE_PENDING: set[str] = set()
_LIVE_LOCK = threading.Lock()
_BOT_USER_ID: str | None = None


def _bot_user_id() -> str:
    global _BOT_USER_ID
    if _BOT_USER_ID is None:
        try:
            _BOT_USER_ID = str(_resp_get(slack_app.client.auth_test(), "user_id") or "")
        except Exception:
            _BOT_USER_ID = ""
    return _BOT_USER_ID


def _report_block_for(channel: str, thread_ts: str) -> tuple[Tenant, dict[str, Any], date] | None:
    """Bloco do report (de hoje ou de ontem) cuja thread recebeu a mensagem."""
    today = _today_brazil().date()
    for tenant in TENANTS:
        if tenant.channel != channel:
            continue
        for day in (today, today - timedelta(days=1)):
            for block in _report_blocks(STATE.get(_skey("report", tenant, day))):
                if block.get("ts") == thread_ts:
                    return tenant, block, day
    return None


def _maybe_live_thread_reply(event: dict[str, Any]) -> None:
    """Resposta na thread de um bloco do report: a Lyra lê, registra e comenta o plano (sem esperar 11h/18h)."""
    thread_ts = str(event.get("thread_ts") or "")
    if not thread_ts or thread_ts == str(event.get("ts") or "") or event.get("subtype") not in (None, "file_share"):
        return
    bot = _bot_user_id()
    if bot and f"<@{bot}>" in str(event.get("text") or ""):
        return  # marcou a Lyra: a conversa é tratada pela menção
    found = _report_block_for(str(event.get("channel") or ""), thread_ts)
    if not found:
        return
    tenant, block, day = found
    with _LIVE_LOCK:
        if thread_ts in _LIVE_PENDING:
            return  # já tem leitura agendada: junta as mensagens seguidas numa resposta só
        _LIVE_PENDING.add(thread_ts)

    def run() -> None:
        try:
            time.sleep(LIVE_REPLY_DELAY_SECONDS)
            with _LIVE_LOCK:
                _LIVE_PENDING.discard(thread_ts)
            _read_report_thread(tenant.channel, thread_ts, "live", _today_brazil(), tenant.key,
                                fila=block.get("fila", ""), register_no_reply=False)
        except Exception:
            logger.exception("[%s] Live thread read failed", tenant.key)

    threading.Thread(target=run, daemon=True).start()



# ---------------------------------------------------------------------------
# Status de hora em hora das EPSs ("Controle de SLA ..." nos canais de indicadores)
# ---------------------------------------------------------------------------
# A EPS posta na thread "Status atual na última hora - HH:MM - CSAT x% - SLA y%" + motivo, próximos passos e
# previsão. A Lyra lê, compara com a meta da fila e cobra só quando há o que cobrar: CSAT (ou SLA) fora da meta,
# justificativa copiada hora após hora, próximo passo genérico ou previsão sem prazo. Causa do lado do iFood
# (cupom, Rosie, sistema) fica só no registro da EPS: não vira cobrança de SLA.
STATUS_CHANNELS = _parse_channel_map(os.getenv("STATUS_CHANNELS", ""))  # "CSU:C0...,AeC:C0..."
_STATUS_CHANNEL_EPS = {channel: eps for eps, channel in STATUS_CHANNELS.items()}
# Canais de indicadores das EPSs: fora dos controles, a Lyra só fala quando marcada — e aí responde na thread, com o
# contexto daquela conversa e só com dados da EPS do canal.
for _eps, _channel in STATUS_CHANNELS.items():
    CHANNEL_SCOPE.setdefault(_channel, next((k for k in EPS_CELULAS if k.casefold() == _eps.casefold()), _eps))
STATUS_REPLY_DELAY_SECONDS = int(os.getenv("STATUS_REPLY_DELAY_SECONDS", "90"))
# Fase de testes: lê o canal real da EPS, mas responde no canal de testes da EPS (EPS_CHANNELS), sem marcar ninguém.
# STATUS_SHADOW=0 = responde na própria thread da EPS, marcando quem postou.
# Também aceita a lista de EPS que seguem em teste (ex.: STATUS_SHADOW=AeC: a AeC fica em teste e a CSU vale).
_SHADOW_RAW = os.getenv("STATUS_SHADOW", "1").strip()
_SHADOW_OFF = {"0", "false", "nao", "não", "off"}
_SHADOW_ON = {"1", "true", "sim", "on"}
STATUS_SHADOW = _SHADOW_RAW.lower() not in _SHADOW_OFF
_SHADOW_EPS = (set() if _SHADOW_RAW.lower() in _SHADOW_OFF | _SHADOW_ON
               else {p.strip().casefold() for p in _SHADOW_RAW.split(",") if p.strip()})
# Canal de testes de cada EPS para o modo teste. Vazio = usa EPS_CHANNELS (que na virada passa a ser o canal oficial).
STATUS_TEST_CHANNELS = _parse_channel_map(os.getenv("STATUS_TEST_CHANNELS", ""))


def _status_shadow(eps: str) -> bool:
    if _SHADOW_EPS:
        return eps.casefold() in _SHADOW_EPS
    return STATUS_SHADOW
STATUS_REPEAT_LIMIT = 3  # mesma justificativa em 3 status seguidos = cobrar atualização real
STATUS_RERAISE_EVERY = 4  # CSAT/SLA fora da meta e justificativa repetida só voltam a ser cobrados a cada 4 status


def _parse_sla_metas(raw: str) -> dict[str, float]:
    """'CX Super Cliente - CSU:90,CX Review - CSU:85' -> {fila: 90.0, ...}"""
    result: dict[str, float] = {}
    for part in raw.split(","):
        if ":" in part:
            fila, value = part.rsplit(":", 1)
            num = _num(value)
            if fila.strip() and num is not None:
                result[fila.strip()] = num
    return result


# Meta de SLA de 1ª resposta: 90% nas filas Platina/VIP (segmento Super) e 80% nas Alpha. SLA_METAS no Railway
# sobrescreve fila a fila ("CX Review - CSU:85,...").
SLA_META_SUPER = float(os.getenv("SLA_META_SUPER", "90"))
SLA_META_ALPHA = float(os.getenv("SLA_META_ALPHA", "80"))
SLA_METAS = {fila: (SLA_META_SUPER if seg.startswith("Super") else SLA_META_ALPHA) for fila, seg in FILA_SEGMENTO.items()}
SLA_METAS.update(_parse_sla_metas(os.getenv("SLA_METAS", "")))
_STATUS_RE = re.compile(
    r"s?tatus atual na [uú]ltima hora\s*[-–:]?\s*(\d{1,2})(?:[:h](\d{2}))?\s*h?\s*[-–:]?\s*CSAT\s*:?\s*([\d.,]+)\s*%?"
    r"(?:\s*[-–|·/]?\s*SLA\s*:?\s*([\d.,]+)\s*%?)?", re.IGNORECASE)
_STATUS_FIELDS = {
    "motivo": re.compile(r"motivo da n[aã]o entrega\s*(?:\(\s*se\s*:?\s*houver\s*\))?\s*[:\-–]?\s*(.*)", re.IGNORECASE),
    "passos": re.compile(r"pr[oó]ximos passos(?: para resolu[cç][aã]o)?\s*[:\-–]?\s*(.*)", re.IGNORECASE),
    "previsao": re.compile(r"previs[aã]o de conclus[aã]o\s*[:\-–]?\s*(.*)", re.IGNORECASE),
}
_IFOOD_SIDE_RE = re.compile(r"\b(cupom|cupons|rosie|sistema|sistemico|sistemica|instabilidade|ifood|fora do ar|bug|"
                            r"ferramenta|oraculo|salesforce|lentidao|indisponibilidade)\b")
_NO_DATA_STATUS_RE = re.compile(r"\b(sem dados|nrt|dados nao carregad\w*|nao carregou|parcial .* repetida|"
                                r"painel fora|dashboard fora|relatorio fora|base nao atualiz\w*)\b")
STATUS_DROP_PP = 2.0  # CSAT caiu ≥ 2 p.p. de um status pro outro com o mesmo próximo passo
_GENERIC_STEP_RE = re.compile(r"\b(captacao\w*|captar|acompanhamento|monitoramento|em andamento|na meta|"
                              r"tentativas? de reversao|reversao|tratativa|alinhamento|reforco|seguimos|atencao)\b")
_DEADLINE_RE = re.compile(r"\d{1,2}\s*(h\b|:\d{2})|\d{1,2}/\d{1,2}|\bate (as|o fim|amanha)\b")
_STATUS_FILA_ALIASES = (("super cliente", "CX Super Cliente"), ("vip", "CX Super Cliente"), ("cx super", "CX Super Cliente"),
                        ("super cx", "CX Super Cliente"), ("review", "CX Review"),
                        ("denuncia", "CX Denúncia"), ("madrugada", "Madrugada"), ("suporte", "CX Suporte"))
_STATUS_PENDING: set[str] = set()


def _status_fila(title: str, eps: str) -> str | None:
    """Fila do título da thread ("Controle de SLA CX VIP - 08/10/26" -> CX Super Cliente - CSU)."""
    celulas = _celulas_of(eps)
    text = _norm_text(title)
    exact = [f for f in celulas if _norm_text(f) in text]
    if exact:
        return max(exact, key=len)
    for alias, base in _STATUS_FILA_ALIASES:
        if re.search(rf"\b{alias}\b", text):
            hit = next((f for f in celulas if _norm_text(f).startswith(_norm_text(base))), None)
            if hit:
                return hit
    return None


# Formato "bloco" (ex.: Controle de SLA/CSAT Review da CSU): "20/10 – 9h:00 / CSAT: 87,05% / Promotoras: 14 /
# Detratoras: 6 / SLA Primeira Resposta: 100% / Volume da fila: 0 / Cenário atual: ... / Ações em andamento: * ..."
_BLOCK_HEAD_RE = re.compile(r"\b\d{1,2}/\d{1,2}\s*[–\-—]\s*(\d{1,2})\s*(?:h\s*:?\s*(\d{2})?|:\s*(\d{2}))", re.IGNORECASE)
_BLOCK_CSAT_RE = re.compile(r"\bCSAT\s*:\s*([\d.,]+)\s*%", re.IGNORECASE)
_BLOCK_FIELDS = {
    "promotoras": re.compile(r"promotor\w*\s*:\s*(\d+)", re.IGNORECASE),
    "detratoras": re.compile(r"detrator\w*\s*:\s*(\d+)", re.IGNORECASE),
    "sla": re.compile(r"SLA\s*(?:de\s*)?(?:primeira|1[ªa°º]?)\s*resposta\s*:\s*([\d.,]+)\s*%", re.IGNORECASE),
    "volume": re.compile(r"volume da fila\s*:\s*(\d+)", re.IGNORECASE),
}
STATUS_CSAT_CHECK_PP = 1.5  # CSAT informado x promotoras ÷ (promotoras + detratoras)


def _looks_like_status(text: str) -> bool:
    raw = str(text or "")
    return bool(_STATUS_RE.search(raw) or (_BLOCK_CSAT_RE.search(raw) and (_BLOCK_HEAD_RE.search(raw)
                                                                          or re.search(r"cen[aá]rio atual", raw, re.I))))


def _parse_block_status(raw: str) -> dict[str, Any] | None:
    cm = _BLOCK_CSAT_RE.search(raw)
    if not cm or not _looks_like_status(raw):
        return None
    hm = _BLOCK_HEAD_RE.search(raw)
    status: dict[str, Any] = {"hora": f"{int(hm.group(1)):02d}:{hm.group(2) or hm.group(3) or '00'}" if hm else "--:--",
                              "csat": _num(cm.group(1)), "formato": "bloco", "previsao": None}
    for key, rx in _BLOCK_FIELDS.items():
        fm = rx.search(raw)
        status[key] = _num(fm.group(1)) if fm else None
    cen = re.search(r"cen[aá]rio atual\s*:?\s*\n*\s*([^\n]+)", raw, re.IGNORECASE)
    status["motivo"] = cen.group(1).strip() if cen else ""
    acoes = re.split(r"a[cç][oõ]es em andamento\s*:?", raw, maxsplit=1, flags=re.IGNORECASE)
    items = []
    if len(acoes) > 1:
        for line in acoes[1].split("\n"):
            line = re.sub(r"^[\s*•\-–]+", "", line).strip()
            if line and not re.match(r"\d+\s*anexos?$", line, re.IGNORECASE):
                items.append(line)
    status["acoes"] = items
    status["passos"] = " | ".join(items)
    return status


def _parse_status(text: str) -> dict[str, Any] | None:
    raw = re.sub(r"\s*\(editado\)\s*", " ", str(text or ""))
    m = _STATUS_RE.search(raw)
    if not m:
        return _parse_block_status(raw)
    status: dict[str, Any] = {
        "hora": f"{int(m.group(1)):02d}:{m.group(2) or '00'}",
        "csat": _num(m.group(3)), "sla": _num(m.group(4)) if m.group(4) else None,
    }
    for key, rx in _STATUS_FIELDS.items():
        fm = rx.search(raw)
        status[key] = re.sub(r"^[•\-\s]+|[\s.]+$", "", fm.group(1)).strip() if fm else ""
    return status


# --- Leitura livre de controle (qualquer formato, texto e/ou imagem) -------------------------------------------
# Os formatos fixos acima são lidos por regra. Quando a EPS manda em outro formato (mudou o modelo, só imagem,
# tópicos em vez de linha única), a Lyra lê com o agente e devolve os mesmos campos; as regras de cobrança são as
# mesmas. A leitura de cada mensagem fica guardada (não lê de novo a cada status).
LLM_CONTROL_READ = os.getenv("LLM_CONTROL_READ", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
_CONTROL_HINT_RE = re.compile(r"\b(csat|sla|nps|tma|tme|fila|volume|promotor\w*|detrator\w*|backlog|produtividade|"
                              r"status|resultado|indicador\w*)\b")


def _strip_md(text: str) -> str:
    return re.sub(r"[*_`~]", "", str(text or ""))


def _maybe_control(message: dict[str, Any]) -> bool:
    """Mensagem com cara de atualização de indicador (número + indicador) ou com print anexado."""
    text = _norm_text(_strip_md(message.get("text")))
    return bool(_image_files(message)) or bool(_CONTROL_HINT_RE.search(text) and re.search(r"\d", text))


def _status_complete(status: dict[str, Any] | None) -> bool:
    """A leitura por regra pegou o essencial? Senão, vale a leitura livre."""
    return bool(status and status.get("csat") is not None and status.get("hora") not in (None, "", "--:--")
                and (status.get("motivo") or status.get("passos")))


def _control_prompt(title: str, fila: str, text: str, has_images: bool) -> str:
    meta, sla_meta = _meta_fila(fila), SLA_METAS.get(fila)
    return (
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. NÃO chame subagentes e NÃO consulte dados.\n"
        f"Leia esta atualização de controle que a EPS postou na thread \"{_strip_md(title)[:80]}\" (fila {fila}). "
        "O formato muda de pessoa para pessoa: pode ser linha única, tópicos, bloco, só imagem (print de painel) ou "
        "texto + imagem. Extraia os números do texto E das imagens anexadas" + (" (há imagens)" if has_images else "")
        + ". Nunca chute número: o que não estiver escrito é null.\n"
        + (f"Meta de CSAT da fila: {_fmt_meta(meta)}%. " if meta is not None else "")
        + (f"Meta de SLA: {_fmt_meta(sla_meta)}%. " if sla_meta is not None else "")
        + "\nDevolva APENAS JSON válido, números com ponto decimal, percentuais sem %:\n"
        '{"e_status": true, "hora": "11:00", "csat": 87.2, "sla": 90.64, "promotoras": null, "detratoras": null, '
        '"volume_fila": null, "motivo": "resumo do motivo/cenário que a EPS deu", "acoes": ["ação 1"], '
        '"previsao": null, "outros": [{"indicador": "TMA", "valor": "9 min"}], "ruim": [], "bom": []}\n'
        "Regras:\n"
        "- e_status=false se NÃO for atualização de hora em hora (conversa, dúvida, agradecimento, aviso, diagnóstico, "
        "análise do mês, fechamento, report de casos).\n"
        "- hora = hora de referência do status (ex.: 'Status atual – 11h' → '11:00'; '04/11 – 09:00' → '09:00').\n"
        "- sla = SLA de 1ª resposta; se só houver 'SLA', use esse.\n"
        "- motivo = o porquê que a EPS deu (cenário, motivo da não entrega, pontos de atenção), em até 200 caracteres. "
        "acoes = ações/próximos passos como a EPS escreveu. previsao = prazo que a EPS deu, se houver.\n"
        "- ruim = até 3 problemas CONCRETOS, com número, que a EPS NÃO explicou ou que contradizem o próprio texto "
        "(ex.: diz 'fila controlada' mas o print mostra 40 casos em espera; CSAT informado diferente do print; "
        "indicador do print muito pior que o do texto). NÃO repita CSAT/SLA abaixo da meta (o app já cobra) nem o que "
        "a EPS já justificou. Na dúvida, deixe vazio.\n"
        "- bom = até 2 pontos positivos concretos, curtos, que NÃO sejam CSAT/SLA x meta (isso já aparece na nota). "
        "Números com vírgula decimal (92,2%). Sem ponto final.\n\n"
        f"Texto da mensagem:\n{_strip_md(text)[:2500] or '(sem texto, só imagem)'}"
    )


_CONTROL_READ_SEM = threading.BoundedSemaphore(int(os.getenv("CONTROL_READ_PARALLEL", "1")))  # imagens
_TEXT_READ_SEM = threading.BoundedSemaphore(2)  # texto não fica na fila atrás das imagens
# Disjuntor das imagens: quando o Toqan recusa imagem várias vezes seguidas, pausa a leitura de imagem por um tempo
# (não entope a fila nem gera alerta em série) e avisa uma vez.
IMAGE_BREAKER_FAILS = 3
IMAGE_BREAKER_MINUTES = int(os.getenv("IMAGE_BREAKER_MINUTES", "30"))
_IMG_FAILS = {"n": 0, "until": 0.0}


def _images_paused() -> bool:
    return time.time() < _IMG_FAILS["until"]


def _image_result(ok: bool, detail: str = "") -> None:
    if ok:
        _IMG_FAILS["n"] = 0
        return
    _IMG_FAILS["n"] += 1
    if _IMG_FAILS["n"] >= IMAGE_BREAKER_FAILS and not _images_paused():
        _IMG_FAILS["until"] = time.time() + IMAGE_BREAKER_MINUTES * 60
        _IMG_FAILS["n"] = 0
        _alert(f"O Toqan recusou {IMAGE_BREAKER_FAILS} leituras de imagem seguidas ({detail[:100]}). Pausei a leitura "
               f"de prints por {IMAGE_BREAKER_MINUTES} min; o que vier em texto continua sendo lido normalmente.")
LLM_READ_LAST = 2  # só as últimas mensagens da thread vão para a leitura livre (as antigas ficam com a regra)
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock(key: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.Lock())


def _safe_status_retry(channel: str, thread_ts: str, eps: str) -> None:
    try:
        skey = f"status:{channel}:{thread_ts}"
        try:
            raised = json.loads(STATE.get(skey) or "{}")
        except ValueError:
            raised = {}
        raised.pop("_last_idx", None)  # força reler a última atualização (mantém o histórico de cobranças)
        STATE.set(skey, json.dumps(raised))
        _read_status_thread(channel, thread_ts, eps)
    except Exception:
        logger.exception("[%s] Status retry failed", eps)


def _llm_status(channel: str, title: str, fila: str, message: dict[str, Any]) -> dict[str, Any] | None:
    """Leitura livre de uma mensagem de controle; guarda o resultado por mensagem (e por edição)."""
    ts = str(message.get("ts") or "")
    edited = str((message.get("edited") or {}).get("ts") or "")
    key = f"llmstatus:{channel}:{ts}:{edited}"
    cached = STATE.get(key)
    if cached:
        try:
            got = json.loads(cached)
            return got or None
        except ValueError:
            pass
    images = _image_files(message)[:3]
    text_len = len(_strip_mentions(_strip_md(message.get("text"))).strip())
    if text_len >= 40 or _images_paused():
        images = []  # tem texto: lê o texto (o Toqan recusa imagem com frequência; o texto é o que vale)
    sem = _CONTROL_READ_SEM if images else _TEXT_READ_SEM
    try:
        sem.acquire()
        if images:
            file_ids = []
            for f in images:
                content = _download_slack_bytes(f)
                if content:
                    file_ids.append(toqan_upload_file(content, str(f.get("name") or "print.png"),
                                                      str(f.get("mimetype") or "image/png")))
            prompt = _control_prompt(title, fila, str(message.get("text") or ""), bool(file_ids))
            try:
                answer = (ask_toqan_with_files(prompt, file_ids, max_attempts=PRINT_MAX_POLLS) if file_ids
                          else ask_toqan(prompt, max_attempts=PRINT_MAX_POLLS))
                _image_result(True)
            except Exception as img_exc:
                _image_result(False, str(img_exc))
                raise
        else:
            answer = ask_toqan(_control_prompt(title, fila, str(message.get("text") or ""), False),
                               max_attempts=PRINT_MAX_POLLS)
    except Exception as exc:
        logger.warning("Leitura livre de controle falhou (%s)", ts, exc_info=True)
        rkey = f"llmretry:{channel}:{ts}"
        tries = int(STATE.get(rkey) or 0)
        thread_ts = str(message.get("thread_ts") or "")
        eps = _STATUS_CHANNEL_EPS.get(channel)
        if tries < PRINT_RETRY_MAX and thread_ts and eps:  # tenta sozinha de novo daqui a pouco
            STATE.set(rkey, str(tries + 1))
            threading.Timer(PRINT_RETRY_SECONDS, lambda: _safe_status_retry(channel, thread_ts, eps)).start()
            return None
        akey = f"llmstatus_alert:{channel}:{_now_brazil().strftime('%Y%m%d%H')}"
        if not STATE.get(akey):  # um alerta por canal por hora, não um por mensagem
            STATE.set(akey, "1")
            _alert(f"Controle ({fila}): não consegui ler uma atualização fora do padrão ({type(exc).__name__}: "
                   f"{str(exc)[:120]}). Tento de novo na próxima mensagem da thread.")
        return None  # não guarda: tenta de novo depois
    finally:
        sem.release()
    data = _block_data_from_json(answer) or {}
    status: dict[str, Any] | None = None
    if data.get("e_status") and data.get("hora") and (_num(data.get("csat")) is not None or _num(data.get("sla")) is not None):
        hm = re.match(r"\s*(\d{1,2})(?:\s*[:h]\s*(\d{2}))?", str(data.get("hora") or ""))
        acoes = [str(a).strip() for a in (data.get("acoes") or []) if str(a).strip()]
        status = {
            "hora": f"{int(hm.group(1)):02d}:{hm.group(2) or '00'}" if hm else "--:--",
            "csat": _num(data.get("csat")), "sla": _num(data.get("sla")),
            "promotoras": _num(data.get("promotoras")), "detratoras": _num(data.get("detratoras")),
            "volume": _num(data.get("volume_fila")), "motivo": str(data.get("motivo") or "").strip(),
            "acoes": acoes, "passos": " | ".join(acoes),
            "previsao": (str(data.get("previsao")).strip() or None) if data.get("previsao") else None,
            "formato": "livre",
            "ruim": [str(r).strip() for r in (data.get("ruim") or []) if str(r).strip()][:3],
            "bom": [str(b).strip() for b in (data.get("bom") or []) if str(b).strip()][:2],
        }
    STATE.set(key, json.dumps(status or {}))
    return status


def _status_issues(statuses: list[dict[str, Any]], fila: str) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    """Pontos a cobrar no status mais recente: [(tipo, texto)]."""
    last = statuses[-1]
    meta, sla_meta = FILA_METAS.get(fila), SLA_METAS.get(fila)
    ifood_side = bool(_IFOOD_SIDE_RE.search(_norm_text(last.get("motivo"))))

    def csat_off(s: dict[str, Any]) -> bool:
        return meta is not None and s.get("csat") is not None and s["csat"] < meta

    def sla_off(s: dict[str, Any]) -> bool:
        return sla_meta is not None and s.get("sla") is not None and s["sla"] < sla_meta

    issues: list[tuple[str, str]] = []
    prom, detr = last.get("promotoras"), last.get("detratoras")
    if last.get("csat") is not None and prom is not None and detr is not None and prom + detr >= 5:
        calc = prom / (prom + detr) * 100
        if abs(calc - last["csat"]) > STATUS_CSAT_CHECK_PP:
            issues.append(("dados", f"O CSAT informado ({_bfmt(last['csat'])}%) não bate com {int(prom)} promotoras e "
                                    f"{int(detr)} detratoras, que dão {_bfmt(calc)}%. Qual é o recorte de cada número?"))
    if last.get("ruim"):  # leitura livre: o que está ruim e a EPS não explicou
        issues.append(("leitura", "; ".join(r.rstrip(". ") for r in last["ruim"][:2]) + ". O que explica e qual a ação?"))
    if not (csat_off(last) or sla_off(last)):
        return issues, last
    if _NO_DATA_STATUS_RE.search(_norm_text(last.get("motivo"))):
        return issues, last  # sem dado novo (NRT fora): número repetido não é cobrança da EPS
    if csat_off(last):
        streak = 0
        for s in reversed(statuses):
            if not csat_off(s):
                break
            streak += 1
        quando = f"há {streak} status seguidos" if streak > 1 else "neste status"
        issues.append(("csat", f"CSAT {_bfmt(last['csat'])}% contra a meta de {_fmt_meta(meta)}% da fila, abaixo {quando}. "
                               "O que está sendo feito pra recuperar e com qual efeito esperado?"))
    if sla_off(last) and not ifood_side:
        issues.append(("sla", f"SLA {_bfmt(last['sla'])}% contra a meta de {_fmt_meta(sla_meta)}%. Qual a causa e a ação?"))
    if len(statuses) > 1:
        prev = statuses[-2]
        if (csat_off(last) and prev.get("csat") is not None and last.get("csat") is not None
                and prev["csat"] - last["csat"] >= STATUS_DROP_PP
                and _norm_text(prev.get("passos")) == _norm_text(last.get("passos")) and last.get("passos")):
            issues.append(("piorou", f"O CSAT caiu de {_bfmt(prev['csat'])}% para {_bfmt(last['csat'])}% e o próximo passo "
                                     "continua o mesmo. O que muda no plano a partir de agora?"))
    key = lambda s: (_norm_text(s.get("motivo")), _norm_text(s.get("passos")))
    repeat = 0
    for s in reversed(statuses):
        if key(s) != key(last) or not key(last)[0]:
            break
        repeat += 1
    if repeat >= STATUS_REPEAT_LIMIT and (repeat - STATUS_REPEAT_LIMIT) % STATUS_RERAISE_EVERY == 0:
        issues.append(("repeat", f"A justificativa e os próximos passos são os mesmos há {repeat} status. "
                                 "O que mudou de uma hora pra outra: o que foi feito e qual o resultado?"))
    if last.get("acoes"):  # formato bloco: avalia ação por ação, cita só o título da vaga
        vagas = [a.split(":", 1)[0].strip() for a in last["acoes"]
                 if _GENERIC_STEP_RE.search(_norm_text(a)) and not re.search(r"\d", a)]
        if vagas:
            issues.append(("passos", "Ações sem dono nem prazo: " + ", ".join(f"\"{v}\"" for v in vagas[:3])
                                     + ". O que exatamente, com quem e até quando?"))
    else:
        passos = _norm_text(last.get("passos"))
        if passos and _GENERIC_STEP_RE.search(passos) and not re.search(r"\d", passos):
            issues.append(("passos", f"\"{last['passos']}\" não diz o que vai ser feito. Qual a ação, com quem e até que horas?"))
    previsao = _norm_text(last.get("previsao"))
    if last.get("previsao") is None and last.get("formato") == "bloco":
        pass  # o formato bloco não tem campo de previsão
    elif not previsao or not _DEADLINE_RE.search(previsao):
        txt = f"\"{last['previsao']}\" não é prazo" if last.get("previsao") else "Sem previsão de conclusão"
        issues.append(("prazo", f"{txt}: até que horas a fila volta pra meta?"))
    return issues, last


SHADOW_ACK = os.getenv("SHADOW_ACK", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}


def _shadow_note(channel: str, thread_ts: str, eps: str, title: str, text: str, once_key: str | None = None) -> None:
    """Modo teste: mostra no canal de teste o que a Lyra leu mesmo quando não há cobrança (ou quando não sabe ler
    aquele controle), para o time ver que ela está acompanhando. Na operação oficial não posta nada."""
    if not SHADOW_ACK or not _status_shadow(eps):
        return
    if once_key:
        if STATE.get(once_key):
            return
        STATE.set(once_key, "1")
    _post_status_reply(channel, thread_ts, eps, title, text, [], None, crisis_check=False)


# --- Leitura contínua dos canais das EPSs ---------------------------------------------------------------------------
# Toda conversa dos canais de indicadores é lida (uma leitura por thread, CREAD_DELAY_SECONDS depois da última
# mensagem). A Lyra extrai três coisas e age: (1) cobrança do iFood para a EPS — se a EPS não responder em 30 min,
# reforça; quando responder, confere se tem causa, ação e prazo; (2) compromisso com prazo da EPS — no prazo, cobra
# se foi feito; (3) problema operacional relatado — vai para o registro do dia. Tudo entra no registro do dia
# ("o que aconteceu hoje?") e as pendências de ontem saem numa resposta na thread do report.
CREAD = os.getenv("CONTINUOUS_READ", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
CREAD_DELAY_SECONDS = int(os.getenv("CREAD_DELAY_SECONDS", "180"))
CREAD_FOLLOWUP_MINUTES = int(os.getenv("CREAD_FOLLOWUP_MINUTES", "30"))
_CREAD_TIMERS: dict[str, threading.Timer] = {}
_CREAD_LOCK = threading.Lock()
_PENDING_LOCK = threading.Lock()
_TRIVIAL_RE = re.compile(r"^\W*(ok|okay|blz|beleza|valeu|obrigad\w*|obg|bom dia|boa tarde|boa noite|ciente|top|show|"
                         r"perfeito|certo|combinado|feito|sim|nao|isso|entendi|anotado|tmj|vlw)\W*$")


def _cread_schedule(channel: str, root: str, eps: str) -> None:
    """Cada mensagem nova reinicia o relógio da thread: a leitura acontece quando a conversa assenta."""
    if not CREAD or not root:
        return
    key = f"{channel}:{root}"
    with _CREAD_LOCK:
        old = _CREAD_TIMERS.pop(key, None)
        if old:
            old.cancel()
        t = threading.Timer(CREAD_DELAY_SECONDS, _cread_safe, args=(channel, root, eps))
        t.daemon = True
        _CREAD_TIMERS[key] = t
        t.start()


def _cread_safe(channel: str, root: str, eps: str) -> None:
    with _CREAD_LOCK:
        _CREAD_TIMERS.pop(f"{channel}:{root}", None)
    try:
        _cread(channel, root, eps)
    except Exception:
        logger.exception("[%s] Leitura contínua falhou (%s)", eps, root)


def _who_label(user: str) -> str:
    if not user:
        return "?"
    return "iFood" if _is_ifood_user(user) else "EPS"


def _hhmm(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), BRAZIL_TIMEZONE).strftime("%H:%M")
    except Exception:
        return "--:--"


def _cread(channel: str, root: str, eps: str) -> None:
    msgs = _fetch_thread(channel, root)
    if not msgs:
        return
    bot = _bot_user_id()
    skey = f"cread:{channel}:{root}"
    last = float(STATE.get(skey) or 0)
    newest = max(float(m.get("ts") or 0) for m in msgs)
    STATE.set(skey, str(newest))
    human = [m for m in msgs if not (m.get("bot_id") or (bot and m.get("user") == bot))]
    new = [m for m in human if float(m.get("ts") or 0) > last
           and not _TRIVIAL_RE.match(_norm_text(_strip_mentions(_strip_md(m.get("text")))))
           and _strip_mentions(_strip_md(m.get("text"))).strip()]
    if not new:
        return
    new_ts = {str(m.get("ts")) for m in new}
    title = _strip_md(str(msgs[0].get("text") or ""))[:150]
    parent_user = str(msgs[0].get("user") or "")
    # thread aberta pela EPS que não é controle de hora em hora = report/informativo da EPS para o iFood: não se cobra
    eps_report = bool(parent_user) and not _is_ifood_user(parent_user) and not msgs[0].get("bot_id") \
        and not _is_control_title(title) and bool(_EPS_REPORT_RE.search(_norm_text(title)))
    lines = []
    for m in msgs[-40:]:
        is_bot = m.get("bot_id") or (bot and m.get("user") == bot)
        quem = "Lyra" if is_bot else f"{_who_label(str(m.get('user') or ''))} <@{m.get('user')}>"
        txt = _strip_md(str(m.get("text") or "")).replace("\n", " ")[:600]
        lines.append(f"{'[NOVA] ' if str(m.get('ts')) in new_ts else ''}ts={m.get('ts')} {_hhmm(str(m.get('ts')))} "
                     f"{quem}: {txt}")
    prompt = (
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. NÃO chame subagentes. Responda APENAS com JSON.\n"
        f"Conversa no canal de indicadores da {eps} (thread \"{title}\"). Cada linha diz se quem fala é do iFood ou da "
        "EPS. Leia as mensagens marcadas [NOVA] (as outras são contexto) e extraia SÓ:\n"
        "- cobranca_ifood: alguém do iFood cobrando/perguntando algo à EPS (ex.: 'estamos com fila em Review, o que "
        "está acontecendo?'). Informe o ts da mensagem, se a EPS JÁ respondeu depois dela, se é cobrança de PROBLEMA "
        "(indicador ruim, fila, falha: precisa de plano) ou só pedido/pergunta, e em 'reforco' UMA frase curta para "
        "reforçar se ficar sem resposta, adequada ao que foi pedido (pedido de ação: 'Conseguem confirmar quando isso "
        "foi feito?'; problema: 'Qual a situação, o que está sendo feito e até que horas?'). Comentário, elogio ou "
        "agradecimento do iFood NÃO é cobrança.\n"
        "- compromisso: alguém da EPS prometendo algo com prazo de hora HOJE (ex.: 'normaliza até 14h', 'até 15h "
        "mando o plano'). Prazo no formato HH:MM. Sem hora clara, ignore.\n"
        "- problema: problema operacional relatado (sistema fora, instabilidade, pico, falta de gente, ferramenta).\n"
        "Ignore atualização de indicador de hora em hora (status, CSAT/SLA, prints): isso já é lido em outro lugar.\n"
        "Formato: {\"itens\": [{\"tipo\": \"cobranca_ifood\", \"ts\": \"...\", \"de\": \"<@U...>\", \"para\": "
        "[\"<@U...>\"], \"texto\": \"...\", \"respondida\": false, \"problema\": true, \"reforco\": \"...\"}, {\"tipo\": \"compromisso\", \"ts\": \"...\", "
        "\"quem\": \"<@U...>\", \"o_que\": \"...\", \"prazo\": \"14:00\"}, {\"tipo\": \"problema\", \"resumo\": \"...\"}], "
        "\"resumo\": \"1 linha do que aconteceu nas mensagens novas (ou vazio se for só conversa)\"}\n\n"
        "Conversa:\n" + "\n".join(lines)
    )
    try:
        data = _block_data_from_json(ask_toqan(prompt, max_attempts=40)) or {}
    except Exception:
        logger.warning("[%s] Leitura contínua: Toqan falhou (%s)", eps, root, exc_info=True)
        STATE.set(skey, str(last))  # tenta de novo na próxima mensagem
        return
    now = _now_brazil()
    problemas = []
    for it in data.get("itens") or []:
        tipo = str(it.get("tipo") or "")
        if tipo == "cobranca_ifood" and not it.get("respondida") and str(it.get("ts")) in new_ts and not eps_report:
            _pending_add({"k": "cobr", "ch": channel, "root": root, "eps": eps, "title": title,
                          "ts": str(it.get("ts")), "de": _uid(it.get("de")), "para": [_uid(x) for x in it.get("para") or []],
                          "texto": str(it.get("texto") or "")[:300], "problema": bool(it.get("problema", True)),
                          "reforco": str(it.get("reforco") or "")[:200],
                          "due": (now + timedelta(minutes=CREAD_FOLLOWUP_MINUTES)).timestamp()})
        elif tipo == "compromisso" and str(it.get("ts")) in new_ts:
            mh = re.match(r"\s*(\d{1,2})(?:\s*[:h]\s*(\d{2}))?", str(it.get("prazo") or ""))
            if not mh:
                continue
            due = now.replace(hour=min(int(mh.group(1)), 23), minute=int(mh.group(2) or 0), second=0, microsecond=0)
            if due <= now:
                continue
            _pending_add({"k": "comp", "ch": channel, "root": root, "eps": eps, "title": title,
                          "ts": str(it.get("ts")), "quem": _uid(it.get("quem")), "o_que": str(it.get("o_que") or "")[:200],
                          "prazo": due.strftime("%H:%M"), "due": (due + timedelta(minutes=5)).timestamp()})
        elif tipo == "problema" and it.get("resumo"):
            problemas.append(str(it["resumo"])[:200])
    resumo = str(data.get("resumo") or "").strip()
    if resumo or problemas:
        _daylog_add(eps, {"h": now.strftime("%H:%M"), "t": title[:80], "r": resumo[:240], "p": problemas,
                          "link": _permalink(channel, root)})


_EPS_REPORT_RE = re.compile(r"\b(report|relatorio|close the loop\w*|devolutiva|monitoria|diagnostico|analise|"
                            r"resultado\w*|resumo|book|fechamento)\b")


def _uid(x: Any) -> str:
    m = re.search(r"U[A-Z0-9]{6,}", str(x or ""))
    return m.group(0) if m else ""


def _pending_add(item: dict[str, Any]) -> None:
    with _PENDING_LOCK:
        try:
            items = json.loads(STATE.get("cread_pending") or "[]")
        except ValueError:
            items = []
        if any(p.get("k") == item["k"] and p.get("ts") == item["ts"] for p in items):
            return
        items.append(item)
        STATE.set("cread_pending", json.dumps(items[-200:]))


def _pending_pop_due() -> list[dict[str, Any]]:
    now = time.time()
    with _PENDING_LOCK:
        try:
            items = json.loads(STATE.get("cread_pending") or "[]")
        except ValueError:
            items = []
        due = [p for p in items if float(p.get("due") or 0) <= now]
        STATE.set("cread_pending", json.dumps([p for p in items if float(p.get("due") or 0) > now]))
    return due


def _daylog_key(eps: str, day: date | None = None) -> str:
    return f"daylog:{eps}:{_as_date(day or _today_brazil()).strftime('%Y%m%d')}"


def _daylog_add(eps: str, entry: dict[str, Any], day: date | None = None) -> None:
    with _PENDING_LOCK:
        key = _daylog_key(eps, day)
        try:
            log = json.loads(STATE.get(key) or "[]")
        except ValueError:
            log = []
        log.append(entry)
        STATE.set(key, json.dumps(log[-120:]))


def _daylog(eps: str, day: date | None = None) -> list[dict[str, Any]]:
    try:
        return json.loads(STATE.get(_daylog_key(eps, day)) or "[]")
    except ValueError:
        return []


def _tag(uid: str, eps: str) -> str:
    """No teste não marca ninguém (a mensagem vai para o canal de teste)."""
    if not uid:
        return ""
    return f"<@{uid}>" if not _status_shadow(eps) else (f"*{_first_name(uid)}*" if _first_name(uid) else "")


def _cread_check_once() -> None:
    for p in _pending_pop_due():
        try:
            _cread_followup(p)
        except Exception:
            logger.exception("Acompanhamento falhou: %s", p.get("k"))


def _cread_followup(p: dict[str, Any]) -> None:
    ch, root, eps, title = p["ch"], p["root"], p["eps"], p.get("title") or ""
    msgs = _fetch_thread(ch, root)
    bot = _bot_user_id()
    after = [m for m in msgs if float(m.get("ts") or 0) > float(p["ts"])
             and not (m.get("bot_id") or (bot and m.get("user") == bot))]
    post = lambda t: _post_status_reply(ch, root, eps, title, t, [], None, crisis_check=False)
    if p["k"] == "cobr":
        resp = [m for m in after if not _is_ifood_user(str(m.get("user") or ""))]
        de = _tag(p.get("de", ""), eps) or "o time iFood"
        if not resp:
            alvos = [t for t in dict.fromkeys(_tag(u, eps) for u in p.get("para") or [] if u) if t]
            alvo = ", ".join(alvos[:3]) or "Time"
            reforco = str(p.get("reforco") or "").strip() or "Qual a situação, o que está sendo feito e até que horas?"
            post(f"{alvo}, {de} pediu às {_hhmm(p['ts'])} e ainda está sem retorno: _{str(p.get('texto')).rstrip('.')}_. "
                 f"{reforco}")
            _daylog_add(eps, {"h": _now_brazil().strftime("%H:%M"), "t": title[:80], "pend": "cobrança sem resposta",
                              "r": f"{p.get('texto')}"[:200], "link": _permalink(ch, root)})
            return
        if not p.get("problema", True):
            return  # pedido/pergunta simples respondido: não pede causa/plano/prazo
        texto = "\n".join(_strip_md(str(m.get("text") or ""))[:500] for m in resp[:4])
        try:
            data = _block_data_from_json(ask_toqan(
                "TAREFA INTERNA DO APP. Não chame subagentes. Responda APENAS JSON.\n"
                f"Pergunta do iFood à operação: {p.get('texto')}\nResposta da operação: {texto}\n"
                "A cobrança era de um PROBLEMA operacional. A resposta traz a causa, a ação e o prazo? Se a resposta "
                "resolve ou explica a questão, ok=true. "
                '{"ok": true|false, "falta": "o que falta, como pergunta curta e natural (ex.: \'Qual a causa?\')"}',
                max_attempts=30)) or {}
        except Exception:
            return
        if data.get("ok") is False and data.get("falta"):
            quem = _tag(str(resp[0].get("user") or ""), eps)
            falta = str(data['falta']).strip().rstrip('.?')
            post(f"{quem + ', ' if quem else ''}valeu pelo retorno! Pra fechar: {falta[:1].lower() + falta[1:]}?")
        return
    if p["k"] == "comp":
        texto = "\n".join(f"{_who_label(str(m.get('user') or ''))}: {_strip_md(str(m.get('text') or ''))[:400]}"
                          for m in after[-10:]) or "(nada depois do compromisso)"
        try:
            data = _block_data_from_json(ask_toqan(
                "TAREFA INTERNA DO APP. Não chame subagentes. Responda APENAS JSON.\n"
                f"Compromisso da operação: {p.get('o_que')} (prazo {p.get('prazo')}).\nMensagens depois:\n{texto}\n"
                'Foi confirmado que foi cumprido? {"cumprido": "sim"|"nao"|"sem_info"}', max_attempts=30)) or {}
        except Exception:
            data = {}
        if str(data.get("cumprido")) == "sim":
            return
        quem = _tag(p.get("quem", ""), eps)
        post(f"{quem + ', ' if quem else ''}deu {p.get('prazo')}: _{p.get('o_que')}_. Foi feito? Se não, o que "
             "aconteceu e qual o novo prazo?")
        _daylog_add(eps, {"h": _now_brazil().strftime("%H:%M"), "t": title[:80], "pend": "compromisso sem confirmação",
                          "r": f"{p.get('o_que')} (até {p.get('prazo')})"[:200], "link": _permalink(ch, root)})


def _cread_loop() -> None:
    time.sleep(90)
    while True:
        try:
            _cread_check_once()
        except Exception:
            logger.exception("Leitura contínua: verificação falhou")
        time.sleep(120)


def _daylog_text(eps_list: list[str], day: date | None = None, title: str = "No canal hoje", limit: int = 12) -> str:
    out = []
    for eps in eps_list:
        log = _daylog(eps, day)
        if not log:
            continue
        pend = [e for e in log if e.get("pend")]
        fatos = [e for e in log if not e.get("pend") and e.get("r")]
        probs = [p for e in log for p in (e.get("p") or [])]
        bloco = [f"*{title} · {eps}*"]
        bloco += [f"• {e['h']} · {e['r']}" for e in fatos[-limit:]]
        if probs:
            bloco.append("⚠️ *Problemas relatados:* " + "; ".join(dict.fromkeys(probs))[:500])
        if pend:
            bloco.append("📌 *Em aberto:* " + " · ".join(f"{e['pend']}: {e['r']}" for e in pend[-6:]))
        out.append("\n".join(bloco))
    return "\n\n".join(out)


def _post_yesterday_digest(tenant: "Tenant", report_ts: str) -> None:
    """Depois do report: pendências de ontem no canal (cobranças sem resposta, compromissos sem confirmação,
    problemas) numa resposta na thread do report — o report em si não muda."""
    if not CREAD or not tenant.eps or not report_ts:
        return
    y = _as_date(_today_brazil()) - timedelta(days=1)
    log = _daylog(tenant.eps, y)
    pend = [e for e in log if e.get("pend")]
    probs = [p for e in log for p in (e.get("p") or [])]
    if not pend and not probs:
        return
    linhas = ["📌 *Do canal ontem — o que ficou em aberto*"]
    linhas += [f"• {e['pend'].capitalize()}: {e['r']}" + (f" (<{e['link']}|thread>)" if e.get("link") else "") for e in pend[-8:]]
    if probs:
        linhas.append("• Problemas relatados: " + "; ".join(dict.fromkeys(probs))[:400])
    linhas.append("Algum desses ainda está aberto? Me conta aqui o status.")
    try:
        _post_sections(tenant.channel, "\n".join(linhas), thread_ts=report_ts)
    except Exception:
        logger.warning("[%s] Não consegui postar as pendências de ontem", tenant.key, exc_info=True)


# --- Threads de assunto nos canais de indicadores (não são controle): ex. "Palitagem - Cálculo do SLA" ------------
# A Lyra lê uma vez quando a EPS abre o assunto. Se for dúvida/divergência para o iFood e a base tiver a resposta,
# responde; se não tiver, marca o dono do tema (experiência: Gustavo; eficiência: Michael). Conversa/ritual sem
# pergunta: fica quieta. Depois disso, só responde quando marcada.
OWNER_EXPERIENCIA = os.getenv("OWNER_EXPERIENCIA", "").strip()   # CSAT, aderência
OWNER_EFICIENCIA = os.getenv("OWNER_EFICIENCIA", "").strip()     # TMA, SLA, volume, fila, produtividade...
OWNER_EXPERIENCIA_NOME = os.getenv("OWNER_EXPERIENCIA_NOME", "Gustavo")
OWNER_EFICIENCIA_NOME = os.getenv("OWNER_EFICIENCIA_NOME", "Michael")
TOPIC_THREADS = os.getenv("TOPIC_THREADS", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}


def _topic_prompt(eps: str, title: str, conversa: str, n_imgs: int) -> str:
    return (
        f"{_scope_instruction(eps)}\n\n"
        f"INFORMAÇÃO INTERNA PARA A LYRA — a {eps} abriu esta thread no canal de indicadores. NÃO é um controle de "
        "hora em hora. Título: \"" + _strip_md(title)[:150] + "\"\n"
        f"Conversa na thread:\n{conversa if len(conversa) <= 12000 else conversa[:7000] + chr(10) + '[…]' + chr(10) + conversa[-5000:]}\n"
        + (f"(Há {n_imgs} imagem(ns) anexada(s) que você NÃO vê.)\n" if n_imgs else "")
        + _kb_context(f"{_strip_md(title)} {conversa[-1500:]}")
        + "Decida e responda em UM destes formatos, sem nada antes:\n"
        "1. `SILENCIO` — se for só informativo, ritual, aviso ou conversa entre a operação, sem dúvida, divergência "
        "ou pedido para o iFood.\n"
        "2. A resposta, em até 6 linhas, se for dúvida/divergência (ex.: como o iFood calcula um indicador, por que o "
        "número deles difere do nosso, regra de processo) E a base responder: consulte a *Lyra Conhecimento* (regras, "
        "definições, processos) e, se for número ou cálculo, a *Lyra Indicadores*. Use só o que elas devolverem.\n"
        "3. *Report ou análise da EPS* (ex.: Close the Looping, diagnóstico, devolutiva de monitoria, análise de casos, "
        "plano): é a EPS reportando ao iFood — NÃO é cobrança. Se o report não tem erro de conta, método, meta ou regra, "
        "responda `SILENCIO` (não peça amostra, plano, dono, prazo nem 'como medir'). Só fale se houver ERRO, em até 5 "
        "linhas, só sobre o erro: se a CONTA e o MÉTODO se "
        "sustentam (refaça as contas com os números dados; ex.: expurgar só as detratoras de um grupo e manter as "
        "promotoras dele infla o resultado — o certo é tirar o grupo inteiro); se a META e os termos batem com os "
        "oficiais (metas do contexto; 'dispersão' no time é CSAT Q4 ÷ CSAT Q1, não distância da meta; o CSAT de caso "
        "resolvido pelo Will fica com o Will (Agentforce CX), nunca com o operador; a pesquisa só sobe quando o caso muda "
        "para resolvido: às vezes (não é o fluxo padrão) a Rosie marca resolvido e transborda (a nota cai no analista), e no Will de Negativas, "
        "que é pós-atendimento, nota no operador = o operador marcou resolvido ANTES de acionar o Will — erro de "
        "procedimento, caso de treinamento, não de expurgo). Se a análise PROPÕE mudar regra do iFood (expurgo, atribuição de "
        "nota, meta, cálculo), isso não é decisão sua nem da EPS: termine o feedback com uma linha final "
        "`ESCALAR: experiencia|eficiencia: <a decisão que o time precisa tomar>`.\n"
        "4. `ESCALAR: experiencia: <a dúvida em 1 linha>` ou `ESCALAR: eficiencia: <a dúvida em 1 linha>` — só para "
        "DÚVIDA de regra/cálculo/processo que a base não responde (NÃO SEI) ou que depende de decisão do time. "
        "experiencia = CSAT, avaliações, detratoras, aderência a processo/política. eficiencia = TMA, SLA, volume, fila, "
        "produtividade, HC, palitagem e o resto.\n"
        "Se o conteúdo principal estiver em imagem que você não vê, diga em 1 frase que não consegue ver a imagem e "
        "peça o texto ou o Excel — não escale e não chute o conteúdo. Nunca chute número nem regra."
    )


def _topic_thread(channel: str, thread_ts: str, eps: str, messages: list[dict[str, Any]]) -> str | None:
    if not TOPIC_THREADS or not messages:
        return None
    key = f"topic:{channel}:{thread_ts}"
    if STATE.get(key):
        return None  # já avaliou esta thread; daqui pra frente só quando marcada
    parent = messages[0]
    bot = _bot_user_id()
    if parent.get("bot_id") or (bot and parent.get("user") == bot) or _is_ifood_user(str(parent.get("user") or "")):
        STATE.set(key, "ifood")  # aberta pelo iFood (cobrança/pergunta para a EPS): não é com a Lyra
        return None
    human = [m for m in messages if not (m.get("bot_id") or (bot and m.get("user") == bot))]
    if any(_is_ifood_user(str(m.get("user") or "")) for m in human[1:]):
        STATE.set(key, "ifood")  # o time iFood já está na conversa
        return None
    STATE.set(key, "lendo")
    title = str(parent.get("text") or "")
    conversa = "\n".join(f"EPS: {_strip_mentions(_strip_md(m.get('text'))).strip()[:6000]}"
                         + (f"\n[planilha anexada]\n{_alt_control_text(m, False)[:4000]}" if _sheet_files(m) else "")
                         for m in human
                         if str(m.get("text") or "").strip())
    n_imgs = sum(len(_image_files(m)) for m in human)
    try:
        answer = _clean_answer(ask_toqan(_topic_prompt(eps, title, conversa, n_imgs)))
    except Exception:
        logger.warning("[%s] Leitura de assunto falhou (%s)", eps, thread_ts, exc_info=True)
        STATE.set(key, "")
        return None
    STATE.set(key, "lido")
    text = answer.strip()
    if not text or text.upper().startswith("SILENCIO") or _is_error_answer(text):
        logger.info("[%s] Assunto %s: sem resposta (silêncio)", eps, thread_ts)
        return None
    esc = _parse_escalation(text)
    post = lambda t: _post_status_reply(channel, thread_ts, eps, title, t, [], None, crisis_check=False)
    if esc:
        body = re.split(r"`?ESCALAR\s*:", text, maxsplit=1)[0].strip()
        if body:  # feedback do report + decisão de regra para o dono do tema
            post(body)
        return _escalate(channel, thread_ts, eps, esc[0], esc[1], post, shadow=_status_shadow(eps), decisao=bool(body))
    return post(text)


_CONTROL_TITLE_RE = re.compile(r"\b(controle|status|acompanhamento|report cx|hora ?a ?hora|hora/hora|intra ?hora|"
                               r"intrahora|volume|produtividade|monitoramento de (fila|sla|csat))\b")


def _is_control_title(title: str) -> bool:
    """Título de controle de hora em hora (Controle de SLA, Acompanhamento de Fila, Report CX Review…).
    Diagnóstico, análise, Close the Looping, palitagem etc. são assunto, mesmo citando a fila."""
    return bool(_CONTROL_TITLE_RE.search(_norm_text(_strip_md(title))))


def _parse_escalation(text: str) -> tuple[str, str] | None:
    m = re.search(r"`?ESCALAR\s*:\s*(experiencia|experiência|eficiencia|eficiência)\s*:\s*(.*)", text or "", re.I | re.S)
    if not m:
        return None
    return ("experiencia" if _norm_text(m.group(1)).startswith("experiencia") else "eficiencia",
            m.group(2).strip().strip("`").strip()[:300])


def _escalate(channel: str, thread_ts: str, eps: str | None, theme: str, duvida: str,
              post: Callable[[str], Any], shadow: bool, decisao: bool = False) -> Any:
    """Marca o dono do tema (Gustavo: experiência; Michael: eficiência) e passa a ouvir a resposta dele para aprender."""
    exp = theme == "experiencia"
    uid, nome = ((OWNER_EXPERIENCIA, OWNER_EXPERIENCIA_NOME) if exp else (OWNER_EFICIENCIA, OWNER_EFICIENCIA_NOME))
    quem = f"*{nome}* (em produção eu marco)" if shadow or not uid else f"<@{uid}>"
    STATE.set(f"escalated:{channel}:{thread_ts}", json.dumps({"duvida": duvida, "eps": eps or "", "tema": theme}))
    if decisao:  # o feedback já foi postado: só chama o dono, curto, como uma pessoa faria
        return post(f"{quem}, consegue avaliar aqui?")
    return post(f"{quem}, consegue ajudar aqui?")


def _learn_from_owner_reply(event: dict[str, Any], post: Callable[[str], Any]) -> None:
    """Resposta de alguém do iFood numa thread que a Lyra escalou: vira pergunta e resposta na aba
    "Respostas do time" e entra na busca da base de processos."""
    channel, thread_ts = str(event.get("channel") or ""), str(event.get("thread_ts") or "")
    raw = STATE.get(f"escalated:{channel}:{thread_ts}")
    user = str(event.get("user") or "")
    text = _strip_mentions(str(event.get("text") or "")).strip()
    if not raw or not text or not _is_ifood_user(user):
        return
    dkey = f"learned:{channel}:{event.get('ts')}"
    if STATE.get(dkey):
        return
    STATE.set(dkey, "1")
    try:
        info = json.loads(raw)
    except ValueError:
        return
    prompt = ("TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Não chame subagentes. Responda APENAS com JSON.\n"
              "A Lyra escalou uma dúvida da operação e alguém do time iFood respondeu. Transforme em pergunta e resposta "
              "GERAIS, que sirvam para a próxima vez (sem IDs de cliente/pedido/ticket, sem nome de cliente). Se a mensagem "
              "não responde a dúvida (ex.: 'vou verificar', 'me chama no privado', só agradecimento), tipo = nenhum.\n"
              f"Dúvida: {info.get('duvida')}\nResposta do time: {text[:2500]}\n"
              'Formato: {"tipo": "resposta"|"nenhum", "pergunta": "...", "resposta": "..."}')
    try:
        data = _block_data_from_json(ask_toqan(prompt, max_attempts=60)) or {}
    except Exception:
        logger.warning("Owner answer extraction failed", exc_info=True)
        return
    if data.get("tipo") != "resposta" or not str(data.get("resposta") or "").strip():
        return
    nome = ""
    try:
        prof = (_resp_get(slack_app.client.users_info(user=user), "user", {}) or {}).get("profile") or {}
        nome = str(prof.get("real_name") or prof.get("display_name") or "")
    except Exception:
        pass
    google_client = _safe_google_client()
    if google_client is None:
        return
    try:
        ws = _ensure_worksheet(_open_spreadsheet(google_client), TEAM_ANSWERS_TITLE, TEAM_ANSWERS_HEADERS)
        ws.append_row([_now_brazil().strftime("%d/%m/%Y %H:%M"), info.get("eps") or "", str(data.get("pergunta"))[:500],
                       str(data.get("resposta"))[:2000], nome or f"<@{user}>", _permalink(channel, thread_ts), "ativo"],
                      value_input_option="RAW")
        _KB["team"] = None  # recarrega na próxima busca
    except Exception:
        logger.warning("Could not save team answer", exc_info=True)
        return
    primeiro = (nome.split() or ["o time"])[0]
    post(f"📚 Anotado, {primeiro}! Guardei essa resposta na minha base: na próxima dúvida parecida eu mesma respondo.")


def _read_status_thread(channel: str, thread_ts: str, eps: str) -> str | None:
    """Lê a thread de status e, se houver o que cobrar, responde. Devolve o texto postado (ou None).
    Uma leitura por thread por vez: vários prints chegando juntos esperam a vez e reaproveitam a leitura."""
    with _thread_lock(f"{channel}:{thread_ts}"):
        return _read_status_thread_locked(channel, thread_ts, eps)


def _read_status_thread_locked(channel: str, thread_ts: str, eps: str) -> str | None:
    messages = _fetch_thread(channel, thread_ts)
    if not messages:
        return None
    fila = _status_fila(str(messages[0].get("text") or ""), eps)
    if not fila:
        # Thread que não é controle (conversa, caso, alinhamento): ignora calada. Só avisa quando é claramente um
        # status no formato da EPS e o título não diz a fila.
        if any(_looks_like_status(_strip_md(m.get("text"))) for m in messages[1:]):
            _shadow_note(channel, thread_ts, eps, str(messages[0].get("text") or ""),
                         "🤔 Vi este controle, mas não reconheci a fila no título — não consigo cobrar ainda.",
                         once_key=f"shadow_nofila:{channel}:{thread_ts}")
            return None
        if _print_control_kind(str(messages[0].get("text") or "")):
            return None  # Volume/Produtividade/Acompanhamento: quem lê é o leitor de print
        return _topic_thread(channel, thread_ts, eps, messages)  # assunto aberto pela EPS (ex.: palitagem)
    if not _is_control_title(str(messages[0].get("text") or "")):
        return _topic_thread(channel, thread_ts, eps, messages)  # análise/diagnóstico citando a fila: não é status
    if not STATE.get(f"topic:{channel}:{thread_ts}"):
        STATE.set(f"topic:{channel}:{thread_ts}", "controle")  # thread de controle: não vira assunto
    bot = _bot_user_id()
    title = str(messages[0].get("text") or "")
    print_thread = bool(_print_control_kind(title))  # Volume/Produtividade/Acompanhamento: quem lê é o leitor de print
    statuses: list[dict[str, Any]] = []
    unread = 0
    human = [m for m in messages[1:] if not (m.get("bot_id") or (bot and m.get("user") == bot))]
    recent_ts = {str(m.get("ts")) for m in human[-LLM_READ_LAST:]}
    for m in human:
        found: list[dict[str, Any]] = []
        for chunk in re.split(r"(?=s?tatus atual na [uú]ltima hora)", _strip_md(m.get("text")), flags=re.IGNORECASE):
            parsed = _parse_status(chunk)
            if parsed:
                found.append(parsed)
        complete = bool(found) and all(_status_complete(s) for s in found)
        if LLM_CONTROL_READ and not print_thread and str(m.get("ts")) in recent_ts and _maybe_control(m) \
                and (not complete or _image_files(m)):
            livre = _llm_status(channel, title, fila, m)  # formato novo / só imagem / faltou campo / print junto
            if livre and complete:  # a regra leu o texto: mantém os números dela e soma o que veio do print
                for k, v in livre.items():
                    if k in ("ruim", "bom") or found[-1].get(k) in (None, "", []):
                        found[-1][k] = v
            elif livre:
                found = [livre]
            elif not found:
                unread += 1
        for parsed in found:
            parsed["user"] = m.get("user")
            statuses.append(parsed)
    if not statuses:
        if unread:  # mensagem sem CSAT/SLA numa thread de controle (conversa, base anexada): não é status, fica calada
            logger.info("[%s] Controle %s: mensagem sem CSAT/SLA, ignorada", eps, thread_ts)
        return None
    issues, last = _status_issues(statuses, fila)
    skey = f"status:{channel}:{thread_ts}"
    try:
        raised = json.loads(STATE.get(skey) or "{}")
    except ValueError:
        raised = {}
    idx = len(statuses)
    if raised.get("_last_idx") == idx:
        return None  # este status já foi lido
    last["ruim_txt"] = " ".join(last.get("ruim") or [])
    field = {"passos": "passos", "prazo": "previsao", "leitura": "ruim_txt"}
    new: list[tuple[str, str]] = []
    for kind, txt in issues:
        prev = raised.get(kind) if isinstance(raised.get(kind), dict) else None
        if kind in field:  # mesmo texto genérico de novo já é coberto pela cobrança de justificativa repetida
            ok = prev is None or prev.get("txt") != _norm_text(last.get(field[kind]))
        elif kind == "repeat":
            ok = True  # _status_issues só devolve no 3º, 7º, 11º status iguais
        else:
            ok = prev is None or idx - int(prev.get("idx", -99)) >= STATUS_RERAISE_EVERY
        if ok:
            new.append((kind, txt))
            raised[kind] = {"idx": idx, "txt": _norm_text(last.get(field.get(kind, ""), ""))}
    raised["_last_idx"] = idx
    STATE.set(skey, json.dumps(raised))
    if not new:
        meta = _meta_fila(fila)
        below = meta is not None and last.get("csat") is not None and last["csat"] < meta
        csat_txt = f"CSAT {_bfmt(last['csat'])}%" if last.get("csat") is not None else "sem CSAT"
        bom_items = [re.sub(r"[\s.;,]+$", "", str(b)).strip() for b in (last.get("bom") or [])]
        bom_items = [b for b in bom_items if b and not re.search(r"\b(csat|sla)\b.*\bmeta\b", _norm_text(b))]
        bom = f" Ponto positivo: {'; '.join(bom_items)}." if bom_items and not below else ""
        _shadow_note(channel, thread_ts, eps, title,
                     f"{'⏳' if below else '✅'} Li o status das {last['hora']} da {fila}: {csat_txt}"
                     + (f" (meta {_bfmt(meta)}%)" if meta is not None and last.get("csat") is not None else "")
                     + (f" · SLA {_bfmt(last['sla'])}%" if last.get("sla") is not None else "")
                     + (" — segue abaixo da meta; já cobrei há pouco e aguardo a resposta antes de cobrar de novo."
                        if below else " — nada a cobrar." + bom))
        return None
    head = f"👀 *{fila} · status das {last['hora']}*" + (f" — CSAT {_bfmt(last['csat'])}%"
                                                         if last.get("csat") is not None else "")
    if last.get("sla") is not None:
        head += f" · SLA {_bfmt(last['sla'])}%"
    return _post_status_reply(channel, thread_ts, eps, str(messages[0].get("text") or ""), head,
                              _compact_status_bullets(new, last, fila), last.get("user"))


def _compact_status_bullets(new: list[tuple[str, str]], last: dict[str, Any], fila: str) -> list[str]:
    """Cobrança enxuta: (1) resultado e causa — CSAT/SLA fora da meta numa pergunta só; (2) plano e prazo — ação
    genérica e prazo vago numa pergunta só. O resto (dados que não batem, leitura, repetição) segue como está."""
    kinds = {k for k, _ in new}
    out: list[str] = []
    res = []
    if "csat" in kinds and last.get("csat") is not None:
        res.append(f"CSAT {_bfmt(last['csat'])}% (meta {_fmt_meta(FILA_METAS.get(fila))}%)")
    if "sla" in kinds and last.get("sla") is not None:
        res.append(f"SLA {_bfmt(last['sla'])}% (meta {_fmt_meta(SLA_METAS.get(fila))}%)")
    if res:
        piorou = " e caindo com o mesmo plano" if "piorou" in kinds else ""
        out.append(f"{' e '.join(res)} abaixo da meta{piorou}: o que causou e o que está sendo feito pra recuperar?")
    plano = []
    if "passos" in kinds:
        acao = (last.get("acoes") or [last.get("passos") or ""])
        txt = re.sub(r"\s+", " ", str(acao[0] if acao else "")).strip()[:60]
        if txt:
            plano.append(f"\"{txt}\" não é ação")
    if "prazo" in kinds:
        plano.append(f"\"{last['previsao']}\" não é prazo" if last.get("previsao") else "falta o prazo")
    if plano:
        out.append(f"{' e '.join(plano)}: o que exatamente vai ser feito, com quem e até que horas?")
    for k, txt in new:
        if k not in {"csat", "sla", "piorou", "passos", "prazo"} or (k in {"csat", "sla"} and not res):
            out.append(txt)
    return out


def _post_status_reply(channel: str, thread_ts: str, eps: str, thread_title: str, head: str,
                       bullets: list[str], user: str | None, crisis_check: bool = True) -> str:
    """Responde a um controle da EPS. Fase de testes (STATUS_SHADOW): vai para o canal de testes da EPS, numa
    thread por controle, sem marcar ninguém; senão, na própria thread da EPS marcando quem postou.
    Antes de cobrar, confere crise nas últimas horas (checagem reaproveitada por 30 min)."""
    try:
        STATE.set(f"replied:{channel}", f"{_now_brazil().strftime('%d/%m %H:%M')} · {head[:60]}")
    except Exception:
        pass
    lines = [f"• {b}" for b in bullets]
    if crisis_check and bullets:
        now = _now_brazil()
        slot_end = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0)
        c = _crisis_check(slot_end - timedelta(hours=CRISIS_STATUS_WINDOW_HOURS), slot_end, eps)
        if c:
            lines = [f"• {_crisis_line(c, 'agora' if 'andamento' in _norm_text(c.get('fim') or c.get('status')) else 'nas últimas horas')}",
                     "• Do lado do iFood, fica registrado. O que a operação está fazendo para segurar a fila durante a "
                     "crise (escala, priorização, comunicação)?"] + lines
    test_channel = (STATUS_TEST_CHANNELS.get(eps) or EPS_CHANNELS.get(eps)) if _status_shadow(eps) else None
    if test_channel:
        text = head + ("\n\n" + "\n".join(lines) if lines else "")
        parent_key = f"status_shadow:{channel}:{thread_ts}"
        parent_ts = STATE.get(parent_key)
        if not parent_ts:
            link = _permalink(channel, thread_ts)
            title = re.sub(r"[`*_]", "", thread_title).strip()[:120]
            intro = (f"🧪 *Teste · {eps}* — o que eu cobraria em _{title}_"
                     + (f" (<{link}|thread original>)" if link else "") + ". Nada foi postado no canal da EPS.")
            resp = slack_app.client.chat_postMessage(channel=test_channel, text=intro)
            parent_ts = str(_resp_get(resp, "ts") or "")
            if parent_ts:
                STATE.set(parent_key, parent_ts)
        _post_sections(test_channel, text, thread_ts=parent_ts or None)
        return text
    who = f"<@{user}> " if user else ""
    text = head + "\n\n" + "\n".join(lines + [f"{who}me responde aqui na thread."])
    _post_sections(channel, text, thread_ts=thread_ts)
    return text


# --- Controles em print (Volume, Produtividade): a Lyra lê a imagem e cobra; se não der pra ler, avisa -----------
PRINT_CONTROLS = (("hora", re.compile(r"acompanhamento de fila|hora ?/ ?hora|intra ?hora|intrahora")),
                  ("volume", re.compile(r"\bvolume\b")), ("produtividade", re.compile(r"\bprodutividade\b")))
# Acompanhamento de Fila da AeC (print de hora em hora, P = planejado, R = realizado). Lê só o CONSOLIDADO da hora.
HORA_TMA_RATIO = 1.10   # TMA realizado > 110% do planejado
HORA_SLA_PP = 2.0       # SLA 1ª resposta abaixo da meta (SLA_METAS) ou do P SLA em mais de 2 p.p.
HORA_MIN_CASES = 10     # TMA/SLA só com pelo menos 10 casos tratados/recebidos na hora
_HORA_SEGMENTOS = (("madrugada", "Madrugada"), ("review", "CX Review - AeC"), ("super", "CX Super Cliente - AeC"),
                   ("suporte", "CX Suporte"))
PRINT_MAX_POLLS = int(os.getenv("PRINT_MAX_POLLS", "60"))  # 10 min
# PRINT_READING=0 desliga a leitura dos prints (Volume/Produtividade). Falha técnica nunca vai para a EPS: só alerta.
PRINT_READING = os.getenv("PRINT_READING", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
VOL_BACKLOG_RATIO = float(os.getenv("VOL_BACKLOG_RATIO", "0.8"))  # produção < 80% da entrada = fila acumulando
HC_SHORT_RATIO = 0.9   # logados < 90% do projetado com volume no projetado ou acima
HC_EXCESS_RATIO = 1.2  # logados ≥ 120% do projetado (e +2 pessoas) com volume abaixo
PROD_TEAM_RATIO = float(os.getenv("PROD_TEAM_RATIO", "0.7"))  # equipe < 70% da média da célula na mesma hora
_PRINT_PENDING: set[str] = set()


def _print_control_kind(title: str) -> str | None:
    text = _norm_text(title)
    return next((kind for kind, rx in PRINT_CONTROLS if rx.search(text)), None)


def _image_files(message: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in (message.get("files") or []) if isinstance(f, dict)
            and str(f.get("mimetype") or "").startswith("image/")]


def _last_interval(data: dict[str, Any], fila: str) -> dict[str, Any]:
    """Tabela de uma célula por intervalo: fica com o último intervalo que tem número (a hora mais recente)."""
    rows = []
    for l in data.get("linhas") or []:
        iv = str(l.get("intervalo") or l.get("segmento") or "").strip()
        if not re.match(r"\d{1,2}\s*[:h]", iv):
            continue  # linha sem intervalo (total do dia)
        if _num(l.get("r_vol")) is None and _num(l.get("tratados")) is None:
            continue
        rows.append((int(re.match(r"(\d{1,2})", iv).group(1)), l))
    if not rows:
        return {"tipo": "hora", "linhas": []}
    hora, last = max(rows, key=lambda r: r[0])
    last = dict(last)
    last["segmento"] = fila
    return {"tipo": "hora", "ate": f"{hora:02d}:00", "linhas": [last]}


def _print_prompt(kind: str, by_interval: bool = False) -> str:
    common = (
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. NÃO chame subagentes e NÃO consulte dados: só LEIA as "
        "imagens anexadas (prints de um controle da EPS) e transcreva os números. Se não conseguir ler TODOS os números "
        "com certeza (imagem pequena, cortada, borrada, ou você não consegue ver imagens), responda SOMENTE "
        "`ILEGIVEL: <motivo curto>`. Nunca chute número. Devolva APENAS JSON válido, números com ponto decimal.\n")
    if kind == "hora":
        return common + (
            "O print é o acompanhamento de fila de hora em hora da EPS: uma linha por Segmento (ex.: IFOOD_CX_REVIEW) ou "
            "por Intervalo, com as colunas P SLA, R SLA 1 Resp, R SLA Res, P Vol, R Vol, Δ, Tratados, P TMA, R TMA, Δ, "
            "P HC Prod, R HC Prod, Δ, P Prod/HC, R Prod/HC (P = planejado, R = realizado). Ignore as colunas Δ. "
            "Percentuais sem o símbolo %, TMA em segundos como está no print.\n"
            '{"tipo": "hora", "linhas": [{"segmento": "IFOOD_CX_REVIEW", "p_sla": 99.43, "r_sla_1resp": 100, '
            '"r_sla_res": null, "p_vol": 52, "r_vol": 5, "tratados": 5, "p_tma": 589.34, "r_tma": 350, "p_hc": 15.48, '
            '"r_hc": 10, "p_prod_hc": 3.35, "r_prod_hc": 0.51}]}\n'
            "Célula vazia: null. Uma linha por segmento ou intervalo que aparecer."
            + ("\nEste print é de UMA célula, uma linha por Intervalo (00:00, 01:00…). Em cada linha use "
               '"intervalo": "07:00" no lugar de "segmento". A linha sem intervalo (total) pode ser ignorada. '
               "Transcreva TODAS as linhas com intervalo, até a última que aparecer." if by_interval else ""))
    if kind == "volume":
        return common + (
            "Os prints trazem, por célula (ex.: CX Review, Super CX), por hora: volume projetado e real (tabela 'Volume por "
            "Hora'), produtividade projetada e real e HC projetado e real (tabela 'Produtividade e HCs por Hora'). Junte "
            "tudo por célula e hora. Só as horas com algum número.\n"
            '{"tipo": "volume", "data": "20/10/2026", "ate": "08:00", "celulas": [{"celula": "CX Review", "horas": '
            '[{"hora": "00:00", "vol_proj": 29, "vol_real": 13, "prod_proj": 29, "prod_real": 13, "hc_proj": 12, "hc_real": 14}], '
            '"total": {"vol_proj": 103, "vol_real": 77, "prod_proj": 103, "prod_real": 48}}]}\n'
            "Campo que não aparece no print: null. total = linha 'Total Geral' de cada tabela.")
    return common + (
        "O print é uma tabela de produtividade por hora: supervisor (linha agrupadora), atendentes (e-mail) e a contagem "
        "por hora, com Total Geral. NÃO devolva e-mails: só a contagem de cada atendente.\n"
        '{"tipo": "produtividade", "celula": "CX Review", "ate": "09:00", "supervisores": [{"supervisor": "NOME DO SUPERVISOR", '
        '"operadores": [{"horas": {"00:00": 2, "01:00": 1}, "total": 3}]}]}\n'
        "Hora sem número: não inclua. total = coluna Total Geral do atendente.")


PRINT_RECHECK = ("\nATENÇÃO: a leitura anterior deste print não fechou. Leia linha por linha, alinhando cada número "
                 "à coluna de hora certa (siga a linha do atendente até o fim). Confira: a soma das horas de cada linha "
                 "tem que dar o Total Geral da linha. Coluna sem número = não inclua.")
PROD_MISMATCH_TOLERANCE = float(os.getenv("PROD_MISMATCH_TOLERANCE", "0.3"))


def _prod_mismatch(data: dict[str, Any]) -> tuple[int, int]:
    ops = [o for s_ in (data.get("supervisores") or []) for o in (s_.get("operadores") or [])]
    wrong = sum(1 for o in ops if o.get("total") is not None
                and abs(sum(_num(v) or 0 for v in (o.get("horas") or {}).values()) - (_num(o["total"]) or 0)) > 0.5)
    return wrong, len(ops)


def _prod_drop_mismatch(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    sups = []
    for sup in data.get("supervisores") or []:
        ops = [o for o in (sup.get("operadores") or []) if o.get("total") is None
               or abs(sum(_num(v) or 0 for v in (o.get("horas") or {}).values()) - (_num(o["total"]) or 0)) <= 0.5]
        if ops:
            sups.append({**sup, "operadores": ops})
    out["supervisores"] = sups
    return out


def _validate_print(kind: str, data: dict[str, Any]) -> str | None:
    """Confere a leitura pelos totais do próprio print. Devolve o problema (ou None se a leitura fecha)."""
    if kind == "hora":
        linhas = data.get("linhas") or []
        if not linhas:
            return "não achei as linhas da tabela"
        if not any(_hora_fila(str(l.get("segmento") or "")) for l in linhas):
            return "não reconheci os segmentos"
        return None
    if kind == "volume":
        cels = data.get("celulas") or []
        if not cels:
            return "não achei as células"
        for cel in cels:
            horas, total = cel.get("horas") or [], cel.get("total") or {}
            for key in ("vol_real", "prod_real"):
                vals = [_num(h.get(key)) for h in horas if h.get(key) is not None]
                if total.get(key) is not None and vals and abs(sum(vals) - (_num(total[key]) or 0)) > 0.5:
                    return f"a soma das horas de {cel.get('celula')} não bate com o total ({key})"
        return None
    sups = data.get("supervisores") or []
    ops = [o for s in sups for o in (s.get("operadores") or [])]
    if not ops:
        return "não achei os atendentes"
    wrong = sum(1 for o in ops if o.get("total") is not None
                and abs(sum(_num(v) or 0 for v in (o.get("horas") or {}).values()) - (_num(o["total"]) or 0)) > 0.5)
    return f"{wrong} atendentes com soma diferente do total" if wrong > 1 else None


def _hh(hora: Any) -> str:
    m = re.match(r"\s*(\d{1,2})", str(hora or ""))
    return f"{int(m.group(1))}h" if m else str(hora)


def _judge_volume(data: dict[str, Any]) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    for cel in data.get("celulas") or []:
        name = str(cel.get("celula") or "célula")
        horas = [{k: (_num(v) if k != "hora" else v) for k, v in h.items()} for h in (cel.get("horas") or [])]
        vol = sum(h.get("vol_real") or 0 for h in horas)
        prod_vals = [h.get("prod_real") for h in horas if h.get("prod_real") is not None]
        if vol >= 20 and prod_vals and sum(prod_vals) < VOL_BACKLOG_RATIO * vol:
            issues.append((f"fila:{name}", f"*{name}:* produziram {_fmt_int(sum(prod_vals))} de {_fmt_int(vol)} casos que "
                                            f"entraram ({_bfmt(sum(prod_vals) / vol * 100, 0)}%). Está acumulando fila? Qual o plano?"))
        falta = [h for h in horas if h.get("hc_proj") and h.get("hc_real") is not None and h.get("vol_proj")
                 and h["hc_real"] < HC_SHORT_RATIO * h["hc_proj"] and (h.get("vol_real") or 0) >= h["vol_proj"]]
        if falta:
            ex = falta[0]
            issues.append((f"falta:{name}", f"*{name}:* menos gente que o projetado com volume no projetado ou acima "
                                             f"({', '.join(_hh(h['hora']) for h in falta[:4])}; ex.: {_hh(ex['hora'])}, "
                                             f"{_fmt_int(ex['hc_real'])} logados contra {_fmt_int(ex['hc_proj'])}). Risco de SLA: qual o ajuste?"))
        sobra = [h for h in horas if h.get("hc_proj") is not None and h.get("hc_real") is not None and h.get("vol_proj")
                 and h["hc_real"] >= HC_EXCESS_RATIO * h["hc_proj"] and h["hc_real"] - h["hc_proj"] >= 2
                 and (h.get("vol_real") or 0) < h["vol_proj"]]
        if sobra:
            ex = max(sobra, key=lambda h: h["hc_real"] - h["hc_proj"])
            issues.append((f"sobra:{name}", f"*{name}:* mais gente que o projetado com volume abaixo "
                                             f"({', '.join(_hh(h['hora']) for h in sobra[:4])}; ex.: {_hh(ex['hora'])}, "
                                             f"{_fmt_int(ex['hc_real'])} logados contra {_fmt_int(ex['hc_proj'])} projetados pra "
                                             f"{_fmt_int(ex.get('vol_real') or 0)} entradas). A escala acompanhou o volume?"))
        parado = [h for h in horas if (h.get("hc_real") or 0) >= 2 and (h.get("vol_real") or 0) >= 3 and h.get("prod_real") == 0]
        if parado:
            ex = parado[0]
            issues.append((f"parado:{name}", f"*{name}:* às {_hh(ex['hora'])} tinha {_fmt_int(ex['hc_real'])} pessoas logadas, "
                                              f"{_fmt_int(ex['vol_real'])} entradas e nenhuma produção. O que aconteceu?"))
    return issues


def _hora_fila(segmento: str) -> str | None:
    text = _norm_text(segmento).replace("_", " ")
    return next((fila for key, fila in _HORA_SEGMENTOS if key in text), None)


def _judge_hora(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Acompanhamento de fila hora a hora (AeC): falta de HC, TMA acima do plan e SLA 1ª resposta abaixo da meta."""
    issues: list[tuple[str, str]] = []
    hora = str(data.get("ate") or "").strip()
    quando = f" às {_hh(hora)}" if hora else ""
    for linha in data.get("linhas") or []:
        fila = _hora_fila(str(linha.get("segmento") or ""))
        if not fila:
            continue
        v = {k: _num(linha.get(k)) for k in ("p_sla", "r_sla_1resp", "p_vol", "r_vol", "tratados", "p_tma", "r_tma",
                                              "p_hc", "r_hc")}
        if v["p_hc"] and v["r_hc"] is not None and v["p_vol"] and v["r_vol"] is not None \
                and v["r_hc"] < HC_SHORT_RATIO * v["p_hc"] and v["r_vol"] >= v["p_vol"]:
            issues.append((f"falta:{fila}", f"*{fila}:* HC abaixo do planejado{quando} ({_bfmt(v['r_hc'])} contra "
                                             f"{_bfmt(v['p_hc'])}) com volume no previsto ou acima ({_fmt_int(v['r_vol'])} "
                                             f"contra {_fmt_int(v['p_vol'])}). Qual o ajuste de escala?"))
        if v["p_tma"] and v["r_tma"] and (v["tratados"] or 0) >= HORA_MIN_CASES and v["r_tma"] > HORA_TMA_RATIO * v["p_tma"]:
            issues.append((f"tma:{fila}", f"*{fila}:* TMA de {_fmt_int(v['r_tma'])} s{quando}, "
                                           f"{_bfmt((v['r_tma'] / v['p_tma'] - 1) * 100, 0)}% acima do plan de "
                                           f"{_fmt_int(v['p_tma'])} s. O que está alongando o atendimento?"))
        if (v["r_vol"] or 0) >= HORA_MIN_CASES and v["tratados"] is not None \
                and v["tratados"] < VOL_BACKLOG_RATIO * v["r_vol"]:
            issues.append((f"fila:{fila}", f"*{fila}:* entraram {_fmt_int(v['r_vol'])} casos{quando} e foram tratados "
                                           f"{_fmt_int(v['tratados'])} ({_bfmt(v['tratados'] / v['r_vol'] * 100, 0)}%). "
                                           "A fila está acumulando: qual o plano para zerar?"))
        meta = SLA_METAS.get(fila) or v["p_sla"]
        casos = max(v["r_vol"] or 0, v["tratados"] or 0)
        if meta and v["r_sla_1resp"] is not None and casos >= HORA_MIN_CASES and v["r_sla_1resp"] < meta - HORA_SLA_PP:
            issues.append((f"sla:{fila}", f"*{fila}:* SLA de 1ª resposta em {_bfmt(v['r_sla_1resp'])}%{quando}, abaixo "
                                           f"da meta de {_bfmt(meta)}%. O que está segurando a primeira resposta?"))
    return issues


def _judge_produtividade(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Compara cada equipe com a média da célula NA MESMA HORA (madrugada x dia não se misturam)."""
    cells: list[tuple[str, str, float]] = []
    for sup in data.get("supervisores") or []:
        for op in sup.get("operadores") or []:
            for hora, val in (op.get("horas") or {}).items():
                v = _num(val)
                if v:
                    cells.append((str(sup.get("supervisor") or "?"), _hh(hora), v))
    by_hour: dict[str, list[float]] = {}
    for _, hora, v in cells:
        by_hour.setdefault(hora, []).append(v)
    hour_avg = {h: sum(vs) / len(vs) for h, vs in by_hour.items() if len(vs) >= 3}
    issues: list[tuple[str, str]] = []
    teams: dict[str, list[tuple[float, float]]] = {}
    for sup, hora, v in cells:
        if hora in hour_avg:
            teams.setdefault(sup, []).append((v, hour_avg[hora]))
    for sup, pairs in teams.items():
        if len(pairs) < 4:
            continue
        mine = sum(v for v, _ in pairs) / len(pairs)
        ref = sum(a for _, a in pairs) / len(pairs)
        if ref and mine < PROD_TEAM_RATIO * ref:
            issues.append((f"equipe:{sup}", f"Equipe de {sup.title()}: {_bfmt(mine)} por pessoa/hora contra {_bfmt(ref)} da "
                                            "célula nas mesmas horas. O que está segurando a produção da equipe?"))
    return issues


PRINT_RETRY_MAX = int(os.getenv("PRINT_RETRY_MAX", "3"))
PRINT_RETRY_SECONDS = int(os.getenv("PRINT_RETRY_SECONDS", "180"))


def _safe_print_retry(channel: str, thread_ts: str, msg_ts: str, eps: str) -> None:
    try:
        _read_print_message(channel, thread_ts, msg_ts, eps)
    except Exception:
        logger.exception("[%s] Print retry failed", eps)


_SHEET_EXT_RE = re.compile(r"\.(xlsx|xlsm|csv)$", re.I)


def _sheet_files(message: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in (message.get("files") or []) if isinstance(f, dict)
            and (_SHEET_EXT_RE.search(str(f.get("name") or "")) or "spreadsheet" in str(f.get("mimetype") or "")
                 or str(f.get("mimetype") or "") == "text/csv")]


def _alt_control_text(message: dict[str, Any], asked: bool) -> str:
    """Controle em Excel/CSV (sempre lido) ou em texto (lido quando a Lyra pediu outro formato e a mensagem tem
    números de tabela). Devolve o conteúdo em texto, ou ""."""
    for f in _sheet_files(message)[:1]:
        content = _download_slack_bytes(f)
        if not content:
            continue
        name = str(f.get("name") or "")
        try:
            if name.lower().endswith(".csv") or str(f.get("mimetype") or "") == "text/csv":
                return content.decode("utf-8", errors="replace")[:15000]
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets[:3]:
                out.append(f"## aba {ws.title}")
                for row in ws.iter_rows(values_only=True):
                    if any(v is not None and str(v).strip() for v in row):
                        out.append(";".join("" if v is None else str(v) for v in row))
                    if len(out) > 400:
                        break
            return "\n".join(out)[:15000]
        except Exception:
            logger.warning("Não consegui abrir a planilha do controle", exc_info=True)
            return ""
    text = str(message.get("text") or "")
    if asked and len(re.findall(r"\d+(?:[.,]\d+)?", text)) >= 8:
        return _strip_md(text)[:8000]
    return ""


def _read_print_message(channel: str, thread_ts: str, msg_ts: str, eps: str) -> str | None:
    done_key = f"printread:{channel}:{msg_ts}"
    if STATE.get(done_key):
        return None  # esse print já foi lido (evita cobrar de novo depois de um restart)
    messages = _fetch_thread(channel, thread_ts)
    if not messages:
        return None
    STATE.set(done_key, "1")
    title = str(messages[0].get("text") or "")
    kind = _print_control_kind(title)
    msg = next((m for m in messages if str(m.get("ts")) == msg_ts), None)
    if not msg:
        return None
    if not kind:
        if LLM_CONTROL_READ and _status_fila(title, eps):
            STATE.set(done_key, "")
            return _read_status_thread(channel, thread_ts, eps)  # controle com print (ou texto + print): leitura livre
        STATE.set(done_key, "")
        return _read_status_thread(channel, thread_ts, eps)  # sem fila no título: assunto (lê uma vez) ou status
    images = _image_files(msg)
    alt = ""  # controle mandado em Excel/CSV ou em texto (quando o print não deu pra ler)
    if not images:
        alt = _alt_control_text(msg, bool(STATE.get(f"print_ilegivel:{channel}:{thread_ts}")))
        if not alt:
            STATE.set(done_key, "")
            return None
    hora_txt = ""
    cell_fila = ""  # tabela de uma célula por intervalo (mensagem "CX REVIEW:", "CX SUPER:", "CX SUPORTE:")
    if kind == "hora":
        msg_text = _norm_text(msg.get("text"))
        if "consolidado" not in msg_text:
            cell_fila = _hora_fila(msg_text) or ""
            if not cell_fila and not alt:
                return None
        mh = re.search(r"(\d{1,2})\s*[:h]\s*(\d{2})?", str(msg.get("text") or ""))
        hora_txt = f"{int(mh.group(1)):02d}:{mh.group(2) or '00'}" if mh and not cell_fila else ""
        images = images[:1]
    user = msg.get("user")
    head_base = f"📷 *{re.sub(r'[`*_]', '', title).strip()[:60]} · {eps}*"
    problem = ""
    misread = ""  # a imagem estava legível, mas a transcrição não fechou com os totais: só alerta interno
    tech_problem = ""  # falha nossa (download, Toqan, JSON): só alerta, nunca cobra a EPS
    data: dict[str, Any] | None = None
    if images and not alt and _images_paused():
        STATE.set(done_key, "")
        logger.info("[%s] Leitura de print pausada (disjuntor do Toqan); fica para a próxima", eps)
        return None
    _CONTROL_READ_SEM.acquire()  # uma leitura de imagem por vez no Toqan
    try:
        file_ids = []
        for f in images[:4]:
            content = _download_slack_bytes(f)
            if content:
                file_ids.append(toqan_upload_file(content, str(f.get("name") or "print.png"), str(f.get("mimetype") or "image/png")))

        def _ask_print(prompt: str) -> str:
            if alt:
                return ask_toqan(prompt + "\n\nATENÇÃO: o controle veio em PLANILHA ou TEXTO, não em imagem. Transcreva "
                                 "a partir deste conteúdo (ignore a parte do pedido que fala de imagem):\n" + alt,
                                 max_attempts=PRINT_MAX_POLLS)
            return ask_toqan_with_files(prompt, file_ids, max_attempts=PRINT_MAX_POLLS)

        if not file_ids and not alt:
            tech_problem = "não consegui baixar a imagem do Slack"
        else:
            answer = _ask_print(_print_prompt(kind, by_interval=bool(cell_fila)))
            if answer.strip().upper().startswith("ILEGIVEL") or answer.strip().upper().startswith("ILEGÍVEL"):
                problem = answer.split(":", 1)[-1].strip()[:150] or "imagem ilegível"
            else:
                data = _block_data_from_json(answer)
                if not data:
                    tech_problem = "a resposta do Toqan não veio como tabela"
                else:
                    if cell_fila:
                        data = _last_interval(data, cell_fila)
                    problem = _validate_print(kind, data) or ""
                    if problem and kind in ("produtividade", "volume"):
                        # a imagem está boa, a transcrição é que errou: tenta de novo conferindo as somas
                        answer2 = _ask_print(_print_prompt(kind) + PRINT_RECHECK)
                        data2 = _block_data_from_json(answer2)
                        if data2 and not _validate_print(kind, data2):
                            data, problem = data2, ""
                        elif kind == "produtividade":
                            best = data2 if data2 and _prod_mismatch(data2)[0] < _prod_mismatch(data)[0] else data
                            wrong, total = _prod_mismatch(best)
                            if total and wrong <= PROD_MISMATCH_TOLERANCE * total:
                                data, problem = _prod_drop_mismatch(best), ""  # usa só as linhas que fecham
                        if problem:
                            misread = problem  # erro de leitura nosso: não vira pedido de print para a EPS
    except Exception as exc:
        logger.exception("[%s] Print read failed", eps)
        detail = str(exc)[:160]
        hint = (" — o Toqan demorou mais que o limite para ler o print" if "timed out" in detail
                else " — o upload da imagem para o Toqan falhou" if "upload" in detail.lower()
                else " — parece o token do Databricks/Toqan" if _looks_like_token_error(detail) else "")
        tech_problem = f"falha ao ler a imagem ({type(exc).__name__}: {detail}){hint}"
    finally:
        _CONTROL_READ_SEM.release()
    if images and not alt:
        _image_result(not tech_problem, tech_problem)
    if tech_problem and _images_paused():
        STATE.set(done_key, "")
        return None  # Toqan recusando imagem: sem fila de novas tentativas nem alerta em série
    if tech_problem:
        STATE.set(done_key, "")  # falha nossa: libera para tentar de novo
        tries_key = f"printretry:{channel}:{msg_ts}"
        tries = int(STATE.get(tries_key) or 0)
        if tries < PRINT_RETRY_MAX:  # Toqan ocupado/recusou: tenta sozinha de novo daqui a pouco, sem alertar ainda
            STATE.set(tries_key, str(tries + 1))
            logger.warning("[%s] Print não lido (%s); nova tentativa %s/%s em %ss", eps, tech_problem[:120],
                           tries + 1, PRINT_RETRY_MAX, PRINT_RETRY_SECONDS)
            threading.Timer(PRINT_RETRY_SECONDS, lambda: _safe_print_retry(channel, thread_ts, msg_ts, eps)).start()
            return None
        _alert(f"Print de controle ({eps} · {re.sub(r'[`*_]', '', title).strip()[:60]}): {tech_problem}. Nada foi postado para a EPS.")
        return None
    if misread:
        _alert(f"Print de controle ({eps} · {re.sub(r'[`*_]', '', title).strip()[:60]}): li, mas a transcrição não fechou "
               f"com os totais do print ({misread}). Não cobrei nada da EPS.")
        return None
    if problem or not data:
        ikey = f"print_ilegivel:{channel}:{thread_ts}"
        if STATE.get(ikey):  # já pediu print legível nessa thread hoje: não repete a cada hora
            _alert(f"Print de controle ({eps}) ilegível de novo: {problem or 'sem dados'}.")
            return None
        STATE.set(ikey, "1")
        return _post_status_reply(channel, thread_ts, eps, title, head_base,
                                  [f"Não consegui ler esse {'arquivo' if alt else 'print'} ({problem or 'sem dados'}). "
                                   "Consegue me mandar de outro jeito aqui na thread? Pode ser o Excel do controle, os "
                                   "números em texto ou um print mais nítido, sem cortar a tabela."], user, crisis_check=False)
    if kind == "hora" and hora_txt and not data.get("ate"):
        data["ate"] = hora_txt
    issues = (_judge_hora(data) if kind == "hora" else _judge_volume(data) if kind == "volume"
              else _judge_produtividade(data))
    skey = f"print:{channel}:{thread_ts}"
    try:
        raised = json.loads(STATE.get(skey) or "{}")
    except ValueError:
        raised = {}
    idx = int(raised.get("_n", 0)) + 1
    new = [(k, txt) for k, txt in issues if idx - int(raised.get(k, -99)) >= STATUS_RERAISE_EVERY]
    raised["_n"] = idx
    for k, _ in new:
        raised[k] = idx
    STATE.set(skey, json.dumps(raised))
    if not new:
        ate0 = str(data.get("ate") or "").strip()
        _shadow_note(channel, thread_ts, eps, title,
                     f"✅ Li o {'controle' if alt else 'print'}{(' até ' + ate0) if ate0 else ''}: nada a cobrar"
                     + (" (o que já cobrei antes segue valendo)." if issues else "."),
                     once_key=f"shadow_ok:{channel}:{thread_ts}:{cell_fila or 'consolidado'}:{ate0 or msg_ts}")
        return None
    ate = str(data.get("ate") or "").strip()
    return _post_status_reply(channel, thread_ts, eps, title, head_base + (f" — até {ate}" if ate else ""),
                              [txt for _, txt in new], user)


STATUS_CATCHUP_HOURS = float(os.getenv("STATUS_CATCHUP_HOURS", "2"))


def _status_catchup() -> None:
    """Depois de um deploy/restart: relê os controles das últimas horas que chegaram enquanto o app estava fora
    (status e prints). O que já foi lido não é lido de novo."""
    time.sleep(45)
    oldest = str(time.time() - STATUS_CATCHUP_HOURS * 3600)
    for eps, channel in STATUS_CHANNELS.items():
        try:
            hist = slack_app.client.conversations_history(channel=channel, oldest=str(time.time() - 24 * 3600), limit=100)
        except Exception:
            logger.warning("[%s] Status catch-up: could not read channel", eps, exc_info=True)
            continue
        for parent in (_resp_get(hist, "messages", []) or []):
            if not parent.get("reply_count") or float(parent.get("latest_reply") or 0) < float(oldest):
                continue
            thread_ts = str(parent.get("ts") or "")
            try:
                replies = _fetch_thread(channel, thread_ts)
            except Exception:
                continue
            recent = [m for m in replies if float(m.get("ts") or 0) >= float(oldest) and str(m.get("ts")) != thread_ts
                      and not m.get("bot_id")]
            try:
                for m in recent:
                    if _image_files(m) and PRINT_READING:
                        _read_print_message(channel, thread_ts, str(m.get("ts")), eps)
                if any(_looks_like_status(str(m.get("text") or "")) or (LLM_CONTROL_READ and _maybe_control(m)
                                                                         and not _image_files(m)) for m in recent):
                    _read_status_thread(channel, thread_ts, eps)
            except Exception:
                logger.exception("[%s] Status catch-up failed for %s", eps, thread_ts)
    logger.info("Status catch-up done")


def _mark_seen(channel: str, what: str) -> None:
    try:
        STATE.set(f"seen:{channel}", f"{_now_brazil().strftime('%d/%m %H:%M')} · {what}")
    except Exception:
        pass


def _maybe_status_reply(event: dict[str, Any]) -> bool:
    channel = str(event.get("channel") or "")
    eps = _STATUS_CHANNEL_EPS.get(channel)
    thread_ts = str(event.get("thread_ts") or "")
    if eps:
        kind = ("print" if _image_files(event) else "status" if _looks_like_status(str(event.get("text") or ""))
                else "mensagem fora do padrão de status") if thread_ts and thread_ts != str(event.get("ts") or "") \
            else ("post novo com print" if _image_files(event) else "post novo (não é resposta em thread)")
        _mark_seen(channel, kind)
        if not thread_ts and _image_files(event) and not event.get("bot_id") and PRINT_READING:
            thread_ts = str(event.get("ts") or "")  # print postado direto no canal (sem thread): lê do mesmo jeito
            msg_ts = thread_ts
            with _LIVE_LOCK:
                if msg_ts in _PRINT_PENDING:
                    return True
                _PRINT_PENDING.add(msg_ts)

            def run_top() -> None:
                try:
                    time.sleep(min(STATUS_REPLY_DELAY_SECONDS, 30))
                    _read_print_message(channel, thread_ts, msg_ts, eps)
                except Exception:
                    logger.exception("[%s] Print control read failed", eps)

            threading.Thread(target=run_top, daemon=True).start()
            return True
    if not eps or not thread_ts or thread_ts == str(event.get("ts") or ""):
        return False
    if event.get("bot_id"):
        return False
    _bot = _bot_user_id()
    if STATE.get(f"escalated:{channel}:{thread_ts}") and _is_ifood_user(str(event.get("user") or "")):
        def _post_learn(t: str, c=channel, r=thread_ts, e=eps) -> Any:
            return _post_status_reply(c, r, e, "", t, [], None, crisis_check=False)
        threading.Thread(target=_learn_from_owner_reply, args=(event, _post_learn), daemon=True).start()
        return True
    if _bot and f"<@{_bot}>" in str(event.get("text") or ""):
        return True  # marcaram a Lyra: quem responde é a menção (no teste, espelhada no canal de testes)
    if _image_files(event) or _sheet_files(event) or (STATE.get(f"print_ilegivel:{channel}:{thread_ts}")
                                                      and len(re.findall(r"\d+", str(event.get("text") or ""))) >= 8):
        if not PRINT_READING:
            return False
        msg_ts = str(event.get("ts") or "")
        with _LIVE_LOCK:
            if msg_ts in _PRINT_PENDING:
                return True
            _PRINT_PENDING.add(msg_ts)

        def run_print() -> None:
            try:
                time.sleep(min(STATUS_REPLY_DELAY_SECONDS, 30))
                _read_print_message(channel, thread_ts, msg_ts, eps)
            except Exception:
                logger.exception("[%s] Print control read failed", eps)

        threading.Thread(target=run_print, daemon=True).start()
        return True
    if not (_looks_like_status(str(event.get("text") or "")) or (LLM_CONTROL_READ and _maybe_control(event))):
        bot = _bot_user_id()
        if (bot and f"<@{bot}>" in str(event.get("text") or "")) \
                or not (TOPIC_THREADS and not STATE.get(f"topic:{channel}:{thread_ts}")):
            return False  # marcaram a Lyra (a menção responde) ou thread já avaliada: só responde se marcada
    with _LIVE_LOCK:
        if thread_ts in _STATUS_PENDING:
            return True
        _STATUS_PENDING.add(thread_ts)

    def run() -> None:
        try:
            time.sleep(STATUS_REPLY_DELAY_SECONDS)  # espera edição/complemento antes de ler
            with _LIVE_LOCK:
                _STATUS_PENDING.discard(thread_ts)
            _read_status_thread(channel, thread_ts, eps)
        except Exception:
            logger.exception("[%s] Status thread read failed", eps)

    threading.Thread(target=run, daemon=True).start()
    return True

# ---------------------------------------------------------------------------
# Chamados de moedas: Fluxo Owners CX -> #rewards-engine-support-cx
# ---------------------------------------------------------------------------
# A operação abre pelo "Fluxo Owners CX" (OWNERS_FLOW_CHANNEL). Quando o tópico é Moedas, a Lyra
# confere os dados mínimos, pede o que faltar na thread e abre o chamado no canal do Rewards
# (REWARDS_CHANNEL): pelo webhook do fluxo "Rewards Engine CX Support" (REWARDS_WEBHOOK_URL) ou,
# sem webhook, postando o chamado direto no canal. Depois devolve o retorno do Rewards na thread de origem.
OWNERS_FLOW_CHANNEL = os.getenv("OWNERS_FLOW_CHANNEL", "").strip()
REWARDS_CHANNEL = os.getenv("REWARDS_CHANNEL", "C08M93FKB63").strip()
# Canais de melhorias das EPSs (Fluxo Owners CX): a Lyra lê todas as threads. Moedas = chamado no formato do Reward
# Engine; demais tópicos (Ajuda, Escalar Ticket...) = resposta na thread pela base de conhecimento.
MELHORIAS_CHANNELS = _parse_channel_map(os.getenv("MELHORIAS_CHANNELS", "AeC:C0C5NDFB87R,CSU:C0C6Y5W8ETS"))
# Para onde vai o chamado de moedas, por EPS. Enquanto estiver preenchido (padrão = canais de teste das EPSs), o
# chamado NÃO vai para o Rewards de verdade. No go-live: CHAMADOS_DESTINO=AeC:<canal real>,CSU:<canal real> (ou vazio
# = REWARDS_CHANNEL / webhook do fluxo).
CHAMADOS_DESTINO = _parse_channel_map(os.getenv("CHAMADOS_DESTINO", "AeC:C0C9F5BLVN1,CSU:C0C9L8NRPPC"))
REWARDS_WEBHOOK_URL = os.getenv("REWARDS_WEBHOOK_URL", "").strip()
REWARDS_PROBLEM_TYPES = [t.strip() for t in os.getenv(
    "REWARDS_PROBLEM_TYPES", "Missão concluída, mas moedas não creditadas").split(";") if t.strip()]
CHAMADOS_WORKSHEET_TITLE = "Chamados Moedas"
CHAMADOS_HEADERS = ["Data", "Ticket SF", "ID do Cliente", "ID do Pedido", "Missão", "Tipo de problema",
                    "Prioridade", "Segmento", "Título", "Solicitante", "Status", "Aberto em", "Finalizado em",
                    "Thread origem", "Thread Rewards"]
_FIELD_LINE_RE = re.compile(r"^\s*\*(?P<label>[^*]+?)\*\s*:?\s*(?P<value>.*)$")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
_EMOJI_CODE_RE = re.compile(r":[a-z0-9_+\-]+:")
_CHAMADOS_LOCK = threading.Lock()


def _blocks_flat(blocks: Any) -> str:
    """Texto dos blocks do Slack (mensagem de fluxo de trabalho), com negrito como *rótulo*."""
    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if not isinstance(node, dict):
            return
        t = node.get("type")
        if t == "text":
            txt = str(node.get("text") or "")
            bold = (node.get("style") or {}).get("bold")
            out.append("\n".join(f"*{part.strip()}*" if bold and part.strip() else part for part in txt.split("\n")))
        elif t == "user":
            out.append(f"<@{node.get('user_id')}>")
        elif t == "emoji":
            out.append(f":{node.get('name')}:")
        elif t == "link":
            out.append(str(node.get("text") or node.get("url") or ""))
        elif t in ("section", "header", "context") and isinstance(node.get("text"), dict):
            out.append(str(node["text"].get("text") or "") + "\n")
        for key in ("elements", "fields"):
            if key in node:
                walk(node[key])
        if t in ("rich_text_section", "rich_text_list", "rich_text_preformatted", "rich_text_quote"):
            out.append("\n")

    walk(blocks)
    return re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()


def _flow_text(message: dict[str, Any] | None) -> str:
    """Texto da mensagem do fluxo: o campo text ou, se ele vier resumido, o conteúdo dos blocks."""
    text = str((message or {}).get("text") or "")
    blocks = _blocks_flat((message or {}).get("blocks") or [])
    return blocks if len(_parse_flow_fields(blocks)) > len(_parse_flow_fields(text)) else text


def _parse_flow_fields(text: str) -> dict[str, str]:
    """Campos do fluxo: '*Rótulo:* valor' ou '*Rótulo*' com o valor nas linhas seguintes."""
    fields: dict[str, str] = {}
    current = None
    for raw in str(text or "").splitlines():
        line = raw.rstrip()
        m = _FIELD_LINE_RE.match(line)
        if m:
            current = _norm_text(m.group("label").split("(")[0].strip().rstrip(":"))
            fields[current] = m.group("value").strip()
            continue
        if current is not None and line.strip():
            fields[current] = (fields[current] + "\n" + line.strip()).strip()
    return {k: _EMOJI_CODE_RE.sub("", v).strip() for k, v in fields.items()}


def _flow_value(fields: dict[str, str], *labels: str) -> str:
    for label in labels:
        for key, value in fields.items():
            if key.startswith(_norm_text(label)):
                value = value.strip()
                return "" if value in {".", "-", "—"} else value
    return ""


def _flow_eps(channel: str) -> str | None:
    return next((e for e, c in MELHORIAS_CHANNELS.items() if c == channel), None)


def _is_flow_channel(channel: str) -> bool:
    return bool(channel) and (channel == OWNERS_FLOW_CHANNEL or channel in MELHORIAS_CHANNELS.values())


def _chamado_destino(eps: str | None) -> tuple[str, bool]:
    """(canal do chamado, é teste?). Teste = canal diferente do Rewards real: posta direto, sem webhook."""
    dest = CHAMADOS_DESTINO.get(eps or "") or (next(iter(CHAMADOS_DESTINO.values())) if CHAMADOS_DESTINO and not eps else "")
    if dest and dest != REWARDS_CHANNEL:
        return dest, True
    return REWARDS_CHANNEL, False


def _flow_topic(fields: dict[str, str], parent_fields: dict[str, str]) -> str:
    return " ".join(x for x in [_flow_value(parent_fields, "topico"), _flow_value(fields, "topico"),
                                _flow_value(fields, "tipo"), _flow_value(parent_fields, "tipo")] if x).strip()


def _is_moedas_flow(fields: dict[str, str], parent_fields: dict[str, str]) -> bool:
    topic = " ".join([_flow_value(fields, "tipo"), _flow_value(parent_fields, "topico"), _flow_value(fields, "topico")])
    return "moeda" in _norm_text(topic)


def _flow_requester(parent: dict[str, Any] | None, parent_text: str) -> str:
    """Quem abriu o chamado: menção antes do primeiro campo do fluxo ("<@U..> enviou…"), ou o autor da mensagem quando
    não é o bot do fluxo. Menções no fim da descrição são os owners marcados, não o solicitante."""
    head = re.split(r"\*[^*\n]+\*", parent_text or "", maxsplit=1)[0]
    ids = _MENTION_ID_RE.findall(head)
    if ids:
        return ids[0]
    user = str((parent or {}).get("user") or "")
    if user and not (parent or {}).get("bot_id") and user != _bot_user_id():
        return user
    return ""


def _chamado_from_flow(fields: dict[str, str], parent_fields: dict[str, str], parent_text: str,
                       parent: dict[str, Any] | None = None) -> dict[str, str]:
    ids = [_flow_requester(parent, parent_text)] if _flow_requester(parent, parent_text) else []
    return {
        "ticket": re.sub(r"\D", "", _flow_value(fields, "ticket sf", "ticket", "numero do ticket")),
        "cliente": _flow_value(fields, "id do cliente"),
        "pedido": _flow_value(fields, "id do pedido"),
        "missao": _flow_value(fields, "id ou nome da missao", "missao"),
        "segmento": _flow_value(fields, "qual segmento", "segmento"),
        "prioridade": _flow_value(fields, "prioridade") or _flow_value(parent_fields, "prioridade"),
        "titulo": _flow_value(fields, "titulo") or _flow_value(parent_fields, "titulo"),
        "descricao": _MENTION_RE.sub("", _flow_value(fields, "descricao", "descreva o problema")).strip(),
        "solicitante": ids[0] if ids else "",
    }


def _triage_chamado(chamado: dict[str, str], extra_replies: list[str], evidencia: str = "") -> dict[str, Any]:
    """Classifica o tipo de problema, acha a missão e lista o que falta (via Toqan, JSON)."""
    prompt = (
        "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Responda APENAS com JSON válido.\n\n"
        "Você faz a triagem de um chamado de MOEDAS (Rewards) aberto pela operação de atendimento iFood, "
        "antes de ele ir para o time de Rewards.\n"
        f"Chamado: {json.dumps(chamado, ensure_ascii=False)}\n"
        + (f"Complementos que a operação mandou na thread:\n" + "\n---\n".join(extra_replies) + "\n" if extra_replies else "")
        + (f"O que aparece no print anexado: {evidencia}\n" if evidencia else "")
        + f"Tipos de problema aceitos pelo Rewards: {json.dumps(REWARDS_PROBLEM_TYPES, ensure_ascii=False)}\n\n"
        'Formato: {"tipo_problema":"...","missao":"...","faltando":["..."],"descricao_rewards":"...","pergunta":"..."}\n'
        "Todo caso de moedas vai para o Rewards (se o cliente abriu contato, ele precisa da solução): entenda o problema "
        "e descreva bem; não oriente nem segure o chamado.\n"
        "Regras:\n"
        "- tipo_problema: o tipo da lista que melhor descreve; se nenhum servir, 'Outro: <resumo curto>'.\n"
        "- missao: ID ou nome da missão citado no chamado ou nos complementos; vazio se não houver.\n"
        "- faltando: dados mínimos que o Rewards exige e que NÃO estão no chamado nem nos complementos: "
        "número do ticket, ID do cliente (UUID), o que aconteceu e a missão quando o problema é de missão. 'Quando' e "
        "'onde' NÃO bloqueiam: se não disserem quando, use a data do chamado; o onde (tela/fluxo) tire da descrição ou do "
        "print (ex.: Lojinha > resgate em saldo). Não peça o que já está lá nem o que o print mostra. Print é opcional.\n"
        "- descricao_rewards: descrição limpa para o Rewards (o que, quando, como, onde), juntando chamado, complementos e o "
        "que o print mostra (ex.: a mensagem de erro/aviso exata do app), sem saudação. NÃO repita ticket, cliente, "
        "pedido nem missão (já vão em campos próprios). Do print, só o que é do problema de moedas: ignore campos vazios "
        "ou alheios (forma de pagamento, bandeira, endereço). Ignore conversa interna da operação (avisos ao time, "
        "'já comunicamos', pedidos de reforço). 2 a 4 frases.\n"
        "- pergunta: se faltar algo, UMA mensagem curta e educada pedindo exatamente o que falta; senão vazio."
    )
    parsed: Any = None
    try:
        parsed = json.loads(_strip_json_code_blocks(ask_toqan(prompt)))
    except Exception:
        logger.warning("Triage was not JSON", exc_info=True)
    if not isinstance(parsed, dict):
        parsed = {}
    faltando = [str(f) for f in (parsed.get("faltando") or []) if str(f).strip()]
    if not chamado.get("ticket"):
        faltando.insert(0, "número do ticket")
    if not _UUID_RE.search(chamado.get("cliente", "")):
        faltando.insert(0, "ID do cliente (UUID)")
    return {
        "tipo_problema": str(parsed.get("tipo_problema") or "").strip() or (REWARDS_PROBLEM_TYPES[0] if REWARDS_PROBLEM_TYPES else ""),
        "missao": str(parsed.get("missao") or chamado.get("missao") or "").strip(),
        "faltando": list(dict.fromkeys(faltando)),
        "descricao": str(parsed.get("descricao_rewards") or chamado.get("descricao") or "").strip(),
        "pergunta": str(parsed.get("pergunta") or "").strip(),
    }


def _download_slack_bytes(file_info: dict[str, Any]) -> bytes | None:
    url = file_info.get("url_private_download") or file_info.get("url_private")
    token = os.getenv("SLACK_BOT_TOKEN")
    if not url or not token:
        return None
    try:
        req = urllib.request.Request(str(url), headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.read() or None
    except Exception:
        logger.warning("Could not download evidence file", exc_info=True)
        return None


def _post_rewards_chamado(chamado: dict[str, str], triage: dict[str, Any], origin_link: str,
                          eps: str | None = None, files: list[dict[str, Any]] | None = None) -> str | None:
    """Abre o chamado no Rewards (ou no canal de teste da EPS). Devolve o ts da mensagem do chamado no canal."""
    dest, teste = _chamado_destino(eps)
    payload = {
        "numero_ticket": chamado["ticket"], "id_cliente": chamado["cliente"], "id_pedido": chamado.get("pedido", ""),
        "missao": triage["missao"], "descricao": triage["descricao"], "tipo_problema": triage["tipo_problema"],
        "solicitante": chamado.get("solicitante", ""), "origem": origin_link,
    }
    if REWARDS_WEBHOOK_URL and not teste:
        req = urllib.request.Request(REWARDS_WEBHOOK_URL, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as response:
            response.read()
        # o fluxo posta sozinho: procura a mensagem pelo número do ticket
        for _ in range(6):
            time.sleep(5)
            try:
                hist = slack_app.client.conversations_history(channel=REWARDS_CHANNEL, limit=20)
                for m in _resp_get(hist, "messages", []) or []:
                    if chamado["ticket"] and chamado["ticket"] in str(m.get("text") or ""):
                        return str(m.get("ts"))
            except Exception:
                logger.warning("Could not read Rewards channel history", exc_info=True)
                break
        return None
    uploads = []
    for f in (files or [])[:10]:
        content = _download_slack_bytes(f)
        if content:
            uploads.append({"content": content, "filename": f.get("name") or "evidencia.png",
                            "title": f.get("title") or f.get("name") or "Evidência"})
    text = _rewards_chamado_text(chamado, triage, origin_link, eps, teste, len(uploads))
    if uploads:
        # igual ao formulário do Reward Engine: o chamado e as evidências na MESMA mensagem
        try:
            slack_app.client.files_upload_v2(channel=dest, file_uploads=uploads, initial_comment=text)
            for _ in range(6):
                time.sleep(3)
                hist = slack_app.client.conversations_history(channel=dest, limit=10)
                for m in _resp_get(hist, "messages", []) or []:
                    if chamado["ticket"] and chamado["ticket"] in str(m.get("text") or "") and m.get("files"):
                        return str(m.get("ts"))
            return None
        except Exception:
            logger.warning("Could not post chamado with evidence; posting text only", exc_info=True)
    resp = slack_app.client.chat_postMessage(channel=dest, text=text)
    return str(_resp_get(resp, "ts") or "") or None


def _rewards_chamado_text(chamado: dict[str, str], triage: dict[str, Any], origin_link: str,
                          eps: str | None, teste: bool, n_evid: int = 0) -> str:
    """Mesmo layout do formulário Reward Engine CX Support: rótulo em negrito numa linha, resposta na de baixo."""
    campos = [
        ("Número do Ticket", chamado.get("ticket") or "."),
        ("ID do Cliente", chamado.get("cliente") or "."),
        ("ID do Pedido", chamado.get("pedido") or "."),
        ("Id ou Nome da Missão", triage.get("missao") or "."),
        ("Descreva o problema", triage.get("descricao") or "."),
        ("Tipo de problema", triage.get("tipo_problema") or "."),
        ("Evidências", f"{n_evid} anexo(s) nesta mensagem" if n_evid else "."),
    ]
    linhas = []
    if teste:
        linhas.append(f"🧪 _Teste {eps or ''} — em produção este chamado vai para o <#{REWARDS_CHANNEL}>_")
    linhas.append("*Reward Engine CX Support*")
    for rotulo, valor in campos:
        linhas += [f"*{rotulo}*", str(valor).strip()]
    rodape = []
    if chamado.get("solicitante"):
        rodape.append(f"a pedido de <@{chamado['solicitante']}>")
    if origin_link:
        rodape.append(f"<{origin_link}|thread de origem>")
    if rodape:
        linhas.append("_Aberto pela Lyra " + " · ".join(rodape) + "_")
    return "\n".join(linhas)


def _permalink(channel: str, ts: str) -> str:
    try:
        return str(_resp_get(slack_app.client.chat_getPermalink(channel=channel, message_ts=ts), "permalink") or "")
    except Exception:
        return ""


def _chamados_ws() -> Any | None:
    google_client = _safe_google_client()
    if google_client is None:
        return None
    try:
        return _ensure_worksheet(_open_spreadsheet(google_client), CHAMADOS_WORKSHEET_TITLE, CHAMADOS_HEADERS)
    except Exception:
        logger.warning("Could not open Chamados worksheet", exc_info=True)
        return None


MELHORIAS_SHADOW = os.getenv("MELHORIAS_SHADOW", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}


def _flow_post(channel: str, thread_ts: str, text: str) -> None:
    """Resposta numa thread dos canais de melhorias. Em modo teste (MELHORIAS_SHADOW), vai para o canal de teste da
    EPS, numa thread por chamado com o link da original — nada aparece no canal de melhorias."""
    eps = _flow_eps(channel)
    test_ch = (STATUS_TEST_CHANNELS.get(eps or "") or EPS_CHANNELS.get(eps or "") or CHAMADOS_DESTINO.get(eps or "")) \
        if (MELHORIAS_SHADOW and eps) else ""
    if not test_ch:
        slack_app.client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
        return
    key = f"melh_shadow:{channel}:{thread_ts}"
    parent = STATE.get(key)
    if not parent:
        link = _permalink(channel, thread_ts)
        resp = slack_app.client.chat_postMessage(
            channel=test_ch, text=f"🧪 *Teste · Melhorias {eps}* — o que eu responderia na thread"
                                  + (f" <{link}|do canal de melhorias>" if link else "") + ". Nada foi postado lá.")
        parent = str(_resp_get(resp, "ts") or "")
        if parent:
            STATE.set(key, parent)
    if parent:
        STATE.set(f"mirror:{test_ch}:{parent}", f"{channel}|{thread_ts}")
    slack_app.client.chat_postMessage(channel=test_ch, thread_ts=parent or None, text=text)


def _maybe_mirror_learning(event: dict[str, Any]) -> None:
    """Resposta do time iFood na cópia da thread (canal de teste) de um caso que a Lyra escalou: aprende igual."""
    ch, root = str(event.get("channel") or ""), str(event.get("thread_ts") or "")
    orig = STATE.get(f"mirror:{ch}:{root}") if root else ""
    if not orig or event.get("bot_id"):
        return
    o_ch, o_ts = orig.split("|", 1)
    if not STATE.get(f"escalated:{o_ch}:{o_ts}"):
        return
    ev = dict(event)
    ev.update(channel=o_ch, thread_ts=o_ts)
    threading.Thread(target=_learn_from_owner_reply,
                     args=(ev, lambda t, c=ch, r=root: slack_app.client.chat_postMessage(channel=c, thread_ts=r, text=t)),
                     daemon=True).start()


# Rede de segurança: o Slack nem sempre entrega o evento da mensagem do fluxo de trabalho. A Lyra também relê os
# canais de melhorias a cada MELHORIAS_POLL_SECONDS e trata o chamado novo ou a thread que mudou desde a última leitura.
MELHORIAS_POLL_SECONDS = int(os.getenv("MELHORIAS_POLL_SECONDS", "0"))  # 0 = desligado (só evento)
MELHORIAS_POLL_HOURS = float(os.getenv("MELHORIAS_POLL_HOURS", "24"))


def _melhorias_poll_once() -> None:
    oldest = str(time.time() - MELHORIAS_POLL_HOURS * 3600)
    for eps, channel in MELHORIAS_CHANNELS.items():
        try:
            hist = slack_app.client.conversations_history(channel=channel, oldest=oldest, limit=100)
        except Exception:
            logger.warning("[melhorias %s] não consegui ler o canal", eps, exc_info=True)
            continue
        for parent in (_resp_get(hist, "messages", []) or []):
            ts = str(parent.get("ts") or "")
            if not ts or not (parent.get("bot_id") or parent.get("subtype") == "bot_message"):
                continue  # chamado = mensagem do fluxo
            stamp = str(parent.get("latest_reply") or ts)
            seen_key = f"flowpoll:{channel}:{ts}"
            if STATE.get(seen_key) == stamp:
                continue  # nada novo nessa thread desde a última leitura
            STATE.set(seen_key, stamp)
            if STATE.get(f"chamado:{ts}") in {"aberto", "fora", "respondido", "processando"}:
                continue
            try:
                _handle_owners_flow(channel, ts)
            except Exception:
                logger.exception("[melhorias %s] releitura falhou (%s)", eps, ts)


def _melhorias_poll_loop() -> None:
    time.sleep(60)
    first = True
    while True:
        try:
            if first:  # na subida só marca o que já existe como visto, para não reprocessar o histórico inteiro
                cutoff = time.time() - 2 * 3600
                for eps, channel in MELHORIAS_CHANNELS.items():
                    try:
                        hist = slack_app.client.conversations_history(channel=channel, oldest=str(time.time() - MELHORIAS_POLL_HOURS * 3600), limit=100)
                    except Exception:
                        continue
                    for m in (_resp_get(hist, "messages", []) or []):
                        if float(m.get("latest_reply") or m.get("ts") or 0) < cutoff:
                            STATE.set(f"flowpoll:{channel}:{m.get('ts')}", str(m.get("latest_reply") or m.get("ts")))
                first = False
            _melhorias_poll_once()
        except Exception:
            logger.exception("Melhorias poll failed")
        time.sleep(MELHORIAS_POLL_SECONDS)


# --- Sugestões de melhoria (tópico "Melhorias" do Fluxo Owners CX): vão para a planilha "Melhorias sugeridas" ------
MELHORIAS_WORKSHEET_TITLE = "Melhorias sugeridas"
MELHORIAS_HEADERS = ["Data", "EPS", "Segmento", "Solicitante", "Título", "Descrição", "Resumo", "Categoria",
                     "Prioridade", "Ticket SF", "ID do Cliente", "ID do Pedido", "Thread", "Status", "Retorno iFood"]
MELHORIA_CATEGORIAS = ("App/Produto", "Política/Processo", "Ferramenta interna", "Comunicação com o cliente",
                       "Logística/Entrega", "Parceiro/Restaurante", "Outro")


def _is_melhoria_flow(fields: dict[str, str], parent_fields: dict[str, str]) -> bool:
    return "melhoria" in _norm_text(_flow_topic(fields, parent_fields))


def _melhoria_resumo(titulo: str, descricao: str) -> tuple[str, str]:
    """(resumo de 1 linha, categoria). Sem resposta do agente: título e 'Outro'."""
    prompt = ("TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. NÃO chame subagentes. Responda APENAS com JSON.\n"
              "Uma operação de atendimento sugeriu uma melhoria ao iFood. Resuma em UMA linha (até 140 caracteres: o "
              "problema e a sugestão) e classifique numa categoria desta lista: "
              + json.dumps(list(MELHORIA_CATEGORIAS), ensure_ascii=False)
              + '.\nFormato: {"resumo": "...", "categoria": "..."}\n'
              f"Título: {titulo[:200]}\nDescrição: {descricao[:2500]}")
    try:
        data = _block_data_from_json(ask_toqan(prompt, max_attempts=60)) or {}
    except Exception:
        logger.warning("Resumo de melhoria falhou", exc_info=True)
        data = {}
    cat = str(data.get("categoria") or "").strip()
    return (str(data.get("resumo") or titulo).strip()[:200], cat if cat in MELHORIA_CATEGORIAS else "Outro")


def _register_melhoria(channel: str, thread_ts: str, eps: str | None, fields: dict[str, str],
                       parent_fields: dict[str, str], parent_text: str, parent: dict[str, Any] | None) -> None:
    """Registra a sugestão na planilha e avisa na thread (no modo teste, no canal de teste)."""
    solicitante = _flow_requester(parent, parent_text)
    titulo = _flow_value(fields, "titulo") or _flow_value(parent_fields, "titulo")
    descricao = _MENTION_RE.sub("", _flow_value(fields, "descricao", "descreva")).strip()
    resumo, categoria = _melhoria_resumo(titulo, descricao)
    nome = ""
    if solicitante:
        try:
            info = _resp_get(slack_app.client.users_info(user=solicitante), "user", {}) or {}
            nome = str((info.get("profile") or {}).get("real_name") or info.get("real_name") or "")
        except Exception:
            nome = ""
    ws = None
    google_client = _safe_google_client()
    if google_client is not None:
        try:
            ws = _ensure_worksheet(_open_spreadsheet(google_client), MELHORIAS_WORKSHEET_TITLE, MELHORIAS_HEADERS)
        except Exception:
            logger.warning("Could not open Melhorias worksheet", exc_info=True)
    if ws is None:
        _alert(f"Melhoria sugerida ({eps}) não foi registrada: sem acesso à planilha. Título: {titulo[:80]}")
        return
    ws.append_row([_format_date(_now_brazil()), eps or "", _flow_value(fields, "qual segmento", "segmento"),
                   nome or solicitante, titulo, descricao, resumo, categoria,
                   _flow_value(fields, "prioridade") or _flow_value(parent_fields, "prioridade"),
                   re.sub(r"\D", "", _flow_value(fields, "ticket sf", "ticket")), _flow_value(fields, "id do cliente"),
                   _flow_value(fields, "id do pedido"), _permalink(channel, thread_ts), "nova", ""],
                  value_input_option="RAW")
    quem = f"<@{solicitante}> " if solicitante else ""
    _flow_post(channel, thread_ts, f"{quem}Sugestão registrada ✅ Entrou na planilha de melhorias do time iFood "
                                   f"(*{categoria}*: {resumo}). O time avalia e o retorno vem por aqui.")


def _flow_mark(channel: str, what: str) -> None:
    logger.info("[melhorias %s] %s", channel, what)
    try:
        STATE.set(f"flowlast:{channel}", f"{_now_brazil().strftime('%d/%m %H:%M')} · {what}")
    except Exception:
        pass


FLOW_IFOOD_NUDGE_HOURS = int(os.getenv("FLOW_IFOOD_NUDGE_HOURS", "48"))
_TICKET_NUM_RE = re.compile(r"\b\d{8}\b")


def _flow_ifood_replies(messages: list[dict[str, Any]], thread_ts: str) -> list[dict[str, Any]]:
    """Respostas de gente do iFood (não bot, não o fluxo) na thread do chamado."""
    bot = _bot_user_id()
    return [m for m in messages if m.get("ts") != thread_ts and not (m.get("bot_id") or m.get("subtype") == "bot_message")
            and m.get("user") != bot and _is_ifood_user(str(m.get("user") or ""))]


def _flow_ifood_followup(channel: str, thread_ts: str, eps: str | None, messages: list[dict[str, Any]],
                         fields: dict[str, str], parent_fields: dict[str, str]) -> None:
    """Caso já com o iFood: se o último retorno do iFood tem mais de FLOW_IFOOD_NUDGE_HOURS e a operação continuou
    mandando casos, cobra quem assumiu (uma vez por janela), com os casos novos. Senão, silêncio."""
    ifood = _flow_ifood_replies(messages, thread_ts)
    if not ifood:
        return
    last = ifood[-1]
    last_ts = float(last.get("ts") or 0)
    bot = _bot_user_id()
    after = [m for m in messages if float(m.get("ts") or 0) > last_ts
             and not (m.get("bot_id") or m.get("subtype") == "bot_message") and m.get("user") != bot]
    if not after or time.time() - last_ts < FLOW_IFOOD_NUDGE_HOURS * 3600:
        _flow_mark(channel, "caso já com o iFood: acompanhando em silêncio")
        return
    nkey = f"flow_nudge:{thread_ts}"
    if time.time() - float(STATE.get(nkey) or 0) < FLOW_IFOOD_NUDGE_HOURS * 3600:
        return
    STATE.set(nkey, str(time.time()))
    tickets = list(dict.fromkeys(t for m in after for t in _TICKET_NUM_RE.findall(str(m.get("text") or ""))))
    titulo = (_flow_value(fields, "titulo") or _flow_value(parent_fields, "titulo") or "este caso").strip()
    quem = str(last.get("user") or "")
    dia = datetime.fromtimestamp(last_ts, BRAZIL_TIMEZONE).strftime("%d/%m")
    n = len(tickets) or len(after)
    casos = (f": {', '.join(tickets[:8])}" + (f" e mais {len(tickets) - 8}" if len(tickets) > 8 else "")) if tickets else ""
    _flow_post(channel, thread_ts,
               f"<@{quem}>, desde o seu último retorno aqui ({dia}) a operação trouxe mais {n} caso(s) de "
               f"*{titulo}*{casos}. Tem atualização?")
    _flow_mark(channel, "caso com o iFood: cobrei atualização de quem assumiu")


def _handle_owners_flow(channel: str, thread_ts: str, mention_text: str = "", trigger_user: str = "") -> None:
    """Lê o chamado do Fluxo Owners CX (mensagem + thread). Moedas: triagem e chamado no Rewards. Outros tópicos:
    responde na thread pela base de conhecimento (e de novo quando marcarem a Lyra na thread)."""
    key = f"chamado:{thread_ts}"
    eps = _flow_eps(channel)
    with _CHAMADOS_LOCK:
        state = STATE.get(key)
        if state == "aguardando_info" and trigger_user and _is_ifood_user(trigger_user) and not mention_text:
            return  # o time iFood entrou na conversa: não é a resposta do solicitante
        if state in {"respondido", "com_ifood"} and mention_text:
            STATE.set(key, "processando")
        elif state in {"aberto", "processando", "fora", "respondido"}:
            return
        else:
            STATE.set(key, "processando")
    try:
        messages = _fetch_thread(channel, thread_ts)
        parent = next((m for m in messages if m.get("ts") == thread_ts), {})
        parent_text = _flow_text(parent)
        flow_msgs = [m for m in messages if m.get("bot_id") or m.get("subtype") == "bot_message"]
        details = next((m for m in flow_msgs if m.get("ts") != thread_ts and "descri" in _norm_text(_flow_text(m))), None)
        if details is None and "descri" in _norm_text(parent_text):
            details = parent  # fluxo que posta tudo na mensagem principal
        if details is None:
            STATE.set(key, state or "")
            _flow_mark(channel, "esperando o fluxo postar os detalhes (campo Descrição) na thread")
            return  # o fluxo ainda não postou os detalhes na thread
        fields = _parse_flow_fields(_flow_text(details))
        parent_fields = _parse_flow_fields(parent_text)
        if not mention_text and not _is_moedas_flow(fields, parent_fields) and _flow_ifood_replies(messages, thread_ts):
            # o time iFood já assumiu o caso: a Lyra não refaz a triagem nem pergunta de novo à operação;
            # só acompanha (se o retorno prometido atrasar e a operação seguir mandando casos, cobra quem assumiu)
            _flow_ifood_followup(channel, thread_ts, eps, messages, fields, parent_fields)
            STATE.set(key, "com_ifood")
            return
        if not _is_moedas_flow(fields, parent_fields):
            if eps is None:  # canal antigo do fluxo (OWNERS_FLOW_CHANNEL): só moedas
                STATE.set(key, "fora")
                return
            if _is_melhoria_flow(fields, parent_fields) and not mention_text:
                _register_melhoria(channel, thread_ts, eps, fields, parent_fields, parent_text, parent)
                STATE.set(key, "respondido")
                _flow_mark(channel, "melhoria registrada na planilha")
                return
            _answer_flow_question(channel, thread_ts, eps, messages, fields, parent_fields, mention_text)
            if STATE.get(f"chamado_ask:{thread_ts}"):
                STATE.set(f"chamado_ask:{thread_ts}", "")
                STATE.set(key, "aguardando_info")  # a resposta do solicitante faz ela ler de novo
                _flow_mark(channel, f"{_flow_topic(fields, parent_fields) or 'ajuda'}: perguntei detalhes a quem abriu")
            else:
                STATE.set(key, "respondido")
                _flow_mark(channel, f"{_flow_topic(fields, parent_fields) or 'ajuda'}: respondido"
                           + (" (escalado)" if STATE.get(f"escalated:{channel}:{thread_ts}") else ""))
            return
        bot = _bot_user_id()
        replies = [str(m.get("text") or "") for m in messages
                   if m.get("ts") != thread_ts and not (m.get("bot_id") or m.get("subtype") == "bot_message")
                   and m.get("user") != bot]
        chamado = _chamado_from_flow(fields, parent_fields, parent_text, parent)
        imgs = [f for m in messages for f in _image_files(m)][:3]
        evidencia = _describe_evidence(imgs) if imgs else ""
        triage = _triage_chamado(chamado, replies, evidencia)
        if triage["faltando"]:
            if state != "aguardando":
                quem = f"<@{chamado['solicitante']}> " if chamado.get("solicitante") else ""
                pergunta = triage["pergunta"] or ("Pra eu abrir o chamado no time de Rewards, me manda aqui: "
                                                 + ", ".join(triage["faltando"]) + ".")
                _flow_post(channel, thread_ts, f"{quem}{pergunta}")
            _flow_mark(channel, "moedas: pedi os dados que faltam (" + ", ".join(triage["faltando"])[:80] + ")")
            STATE.set(key, "aguardando")
            return
        origin = _permalink(channel, thread_ts)
        files = [f for m in messages for f in (m.get("files") or []) if isinstance(f, dict)]
        dest, teste = _chamado_destino(eps)
        rewards_ts = _post_rewards_chamado(chamado, triage, origin, eps, files)
        link = _permalink(dest, rewards_ts) if rewards_ts else ""
        _flow_post(
            channel, thread_ts,
            (("🧪 [teste] " if teste else "") + (f"<@{chamado['solicitante']}> " if chamado.get("solicitante") else "")
             + "Caso escalado para o time de Rewards ✅"
                  + (f" <{link}|ver chamado>" if link else f" (<#{dest}>)")
                  + f"\n*Tipo:* {triage['tipo_problema']}" + (f" · *Missão:* {triage['missao']}" if triage["missao"] else "")
                  + "\nTe aviso aqui quando o Rewards responder."))
        STATE.set(key, "aberto")
        _flow_mark(channel, "moedas: chamado aberto")
        if rewards_ts:
            STATE.set(f"rewards:{rewards_ts}", json.dumps({"channel": channel, "ts": thread_ts,
                                                            "solicitante": chamado.get("solicitante", "")}))
            STATE.set(f"rewards_dest:{dest}", "1")
        ws = _chamados_ws()
        if ws is not None:
            now = _now_brazil()
            ws.append_row([_format_date(now), chamado["ticket"], chamado["cliente"], chamado.get("pedido", ""),
                           triage["missao"], triage["tipo_problema"], chamado.get("prioridade", ""),
                           chamado.get("segmento", ""), chamado.get("titulo", ""), chamado.get("solicitante", ""),
                           "aberto", now.strftime("%d/%m/%Y %H:%M"), "", thread_ts, rewards_ts or ""],
                          value_input_option="RAW")
    except Exception as exc:
        logger.exception("Owners flow handling failed")
        STATE.set(key, "")
        _flow_mark(channel, f"falhou ({type(exc).__name__})")
        _alert(f"Falha ao abrir chamado de moedas ({thread_ts}): {type(exc).__name__}: {str(exc)[:150]}")


def _describe_evidence(images: list[dict[str, Any]]) -> str:
    """Lê o print anexado ao chamado (texto do erro, tela). Melhor esforço: se o Toqan não ler, devolve ""."""
    try:
        file_ids = []
        for f in images[:3]:
            content = _download_slack_bytes(f)
            if content:
                file_ids.append(toqan_upload_file(content, str(f.get("name") or "print.png"),
                                                  str(f.get("mimetype") or "image/png")))
        if not file_ids:
            return ""
        ans = ask_toqan_with_files(
            "TAREFA INTERNA DO APP — NÃO é mensagem para o Slack. Não chame subagentes. Descreva em até 3 linhas o que "
            "o print mostra para entender o problema: a tela do app, a mensagem de erro EXATA entre aspas e o tipo de "
            "pagamento/bandeira se aparecer. NUNCA transcreva número de cartão, CPF, nome, telefone ou endereço.",
            file_ids, max_attempts=24)
        ans = _clean_answer(ans)
        ans = re.sub(r"\b(?:\d[ -]?){12,19}\b", "[número omitido]", ans)  # trava: nada de número de cartão
        return "" if _is_error_answer(ans) else ans[:500]
    except Exception:
        logger.warning("Não consegui ler o print do chamado", exc_info=True)
        return ""


def _answer_flow_question(channel: str, thread_ts: str, eps: str | None, messages: list[dict[str, Any]],
                          fields: dict[str, str], parent_fields: dict[str, str], mention_text: str = "") -> None:
    """Tópico que não é Moedas (Ajuda, Escalar Ticket...): a Lyra tenta ajudar na thread pela base de conhecimento."""
    topic = _flow_topic(fields, parent_fields) or "dúvida da operação"
    pedido = "\n".join(f"{k}: {v}" for k, v in {**parent_fields, **fields}.items() if v and not re.match(r"^<@", v))
    bot = _bot_user_id()
    conversa = "\n".join(
        f"{'Lyra' if m.get('user') == bot else 'Operação'}: {_MENTION_RE.sub('', str(m.get('text') or '')).strip()[:600]}"
        for m in messages if m.get("ts") != thread_ts and not (m.get("bot_id") and m.get("user") != bot))
    imgs = [f for m in messages for f in _image_files(m)][:3]
    anexos = ""
    if imgs:
        leitura = _describe_evidence(imgs)
        anexos = (f"A operação anexou {len(imgs)} imagem(ns) ao pedido. "
                  + (f"O que dá para ver nelas: {leitura}\n" if leitura else
                     "Você não consegue ver as imagens: NÃO peça print de novo; pergunte só o que um print não responde.\n"))
    prompt = (
        f"{_scope_instruction(eps)}\n\n"
        f"INFORMAÇÃO INTERNA PARA A LYRA — CANAL DE MELHORIAS DA {eps or 'EPS'}: a operação abriu um pedido pelo fluxo "
        f"Owners CX (tópico: {topic}). Ajude a operação na thread, como analista do time iFood.\n"
        f"Pedido aberto:\n{pedido[:2500]}\n" + anexos
        + (f"Conversa na thread até aqui:\n{conversa[-2500:]}\n" if conversa else "")
        + (f"Nova mensagem para você: {mention_text}\n" if mention_text else "")
        + "Quem abriu o pedido É a operação de atendimento (a EPS), com o cliente já em atendimento: NUNCA diga para "
        "'orientar o cliente a contatar o atendimento'. Aja como o analista do iFood que atende esse canal: primeiro "
        "entenda o caso. Se o pedido não deixar claro o problema (o que exatamente aconteceu, o que o cliente tentou, "
        "o que já foi checado, dados do caso como código/valor do cupom, mensagem de erro, print), responda SOMENTE, "
        "sem nada antes: `PERGUNTAR: <até 3 perguntas objetivas, numa mensagem curta e cordial>` — inclua a pergunta "
        "do que a própria operação já checou (ex.: 'o cupom está dentro das regras do pedido: validade, valor mínimo, "
        "forma de pagamento, loja?').\n"
        "Com o caso claro: responda pelo que a base devolver (trechos da base de processos abaixo; ClubIA para Clube; Lyra "
        "Conhecimento para os demais processos, política, matriz de decisão e agentes). "
        "Se for pedido para escalar um ticket, diga o que a operação precisa fazer e o que já pode adiantar pelo "
        "processo. Resposta curta (até 6 linhas), sem título, sem dado pessoal de cliente.\n"
        "NUNCA pergunte o que o pedido ou os prints já mostram (valor, data, horário, status, mensagem do app). Use os "
        "prints: compare o que eles mostram com o pedido e aponte divergências (ex.: valor pago ≠ valor da fatura, data "
        "depois do vencimento, recebedor diferente do esperado), sem nome, CPF ou dado pessoal do cliente.\n"
        "*Peça Agora Pague Depois* (pagamento que não baixou, fatura, cobrança): com o pedido e os prints, escreva 1 a 2 "
        "linhas com o que eles mostram (data e valor do pagamento x valor e vencimento da fatura, divergências) e "
        "termine com `ESCALAR: experiencia: <o caso em 1 linha>` — quem resolve baixa de pagamento é o time iFood.\n"
        "Quando escalar depois de um resumo útil, escreva o resumo ANTES da linha `ESCALAR:` (o app posta os dois).\n"
        "Se a base NÃO tiver a resposta (NÃO SEI) ou depender de decisão do time, responda SOMENTE, sem nada antes: "
        "`ESCALAR: experiencia: <a dúvida em 1 linha>` ou `ESCALAR: eficiencia: <a dúvida em 1 linha>` — experiencia = "
        "CSAT, avaliações, aderência, processo e política de atendimento, jornada do cliente; eficiencia = TMA, SLA, "
        "fila, volume, produtividade, HC, ferramentas e sistemas. Sem chute.\n\n"
        + _kb_context(f"{topic} {pedido} {mention_text}")
        + (CLUBE_INSTRUCTION if _is_clube_question(f"{topic} {pedido} {mention_text}") else KNOWLEDGE_INSTRUCTION))
    answer = _clean_answer(ask_toqan(prompt))
    if _is_error_answer(answer) or not answer.strip():
        _alert(f"Canal de melhorias {eps or ''}: não consegui responder a thread {thread_ts} ({str(answer)[:120]})")
        return
    esc = _parse_escalation(answer)
    m_ask = re.match(r"\s*`?PERGUNTAR\s*:\s*(.*)", answer, re.S | re.I)
    ja_perguntou = bool(STATE.get(f"chamado_ask:{thread_ts}"))
    if m_ask and (ja_perguntou or (imgs and not anexos.count("O que dá para ver"))):
        # já perguntou uma vez (ou a operação mandou prints que não consegui ler): não repete pergunta, chama o time
        esc = ("experiencia", f"{topic}: {_flow_value(fields, 'titulo') or _flow_value(parent_fields, 'titulo') or pedido[:120]}")
        answer = ("Os prints vieram, mas não consegui ler os detalhes deles daqui." if imgs and "O que dá para ver"
                  not in anexos else "") + "\nESCALAR: experiencia: x"
    if esc:
        resumo = _strip_file_promises(re.split(r"`?ESCALAR\s*:", answer, maxsplit=1)[0]).strip()
        if resumo and not re.match(r"\s*`?PERGUNTAR", resumo, re.I):
            _flow_post(channel, thread_ts, resumo)
        if STATE.get(f"escalated:{channel}:{thread_ts}"):
            return  # o dono do tema já foi chamado nessa thread
        _escalate(channel, thread_ts, eps, esc[0], esc[1], lambda t: _flow_post(channel, thread_ts, t),
                  shadow=bool(MELHORIAS_SHADOW and eps), decisao=bool(resumo))
        return
    if m_ask:  # caso pouco claro: pergunta ao solicitante antes de responder ou escalar
        parent = messages[0] if messages else {}
        quem = _flow_requester(parent, str(parent.get("text") or ""))
        _flow_post(channel, thread_ts, (f"<@{quem}> " if quem else "") + m_ask.group(1).strip().strip("`"))
        STATE.set(f"chamado_ask:{thread_ts}", "1")
        return
    _flow_post(channel, thread_ts, _strip_file_promises(answer))


def _handle_rewards_reply(event: dict[str, Any]) -> None:
    """Resposta no chamado do Rewards: devolve na thread de origem (Fluxo Owners CX)."""
    thread_ts = str(event.get("thread_ts") or "")
    origin_raw = STATE.get(f"rewards:{thread_ts}") if thread_ts else ""
    if not origin_raw or event.get("user") == _bot_user_id():
        return
    try:
        origin = json.loads(origin_raw)
    except json.JSONDecodeError:
        return
    text = _MENTION_RE.sub("", str(event.get("text") or "")).strip()
    if not text:
        return
    finished = "solicitacao foi finalizada" in _norm_text(text)
    is_flow = bool(event.get("bot_id") or event.get("subtype") == "bot_message")
    if is_flow and not finished:
        return  # avisos automáticos do fluxo (início de atendimento etc.)
    quem = f"<@{origin['solicitante']}> " if origin.get("solicitante") else ""
    if finished:
        msg = f"✅ {quem}o time de Rewards finalizou o chamado."
    else:
        quoted = "\n".join("> " + l for l in text[:1500].splitlines() if l.strip())
        msg = f"{quem}segue retorno do time de Rewards:\n{quoted}"
    _flow_post(origin["channel"], origin["ts"], msg)
    if finished:
        ws = _chamados_ws()
        if ws is not None:
            try:
                for n, row in _worksheet_rows_with_header(ws):
                    if _row_value(row, "Thread Rewards") == thread_ts:
                        ws.update_cell(n, CHAMADOS_HEADERS.index("Status") + 1, "finalizado")
                        ws.update_cell(n, CHAMADOS_HEADERS.index("Finalizado em") + 1, _now_brazil().strftime("%d/%m/%Y %H:%M"))
            except Exception:
                logger.warning("Could not update Chamados row", exc_info=True)


def _route_chamados_event(event: dict[str, Any]) -> bool:
    """Eventos dos canais de chamados. True = já tratado."""
    channel = str(event.get("channel") or "")
    if _is_flow_channel(channel):
        root = str(event.get("thread_ts") or event.get("ts") or "")
        if event.get("thread_ts") and not event.get("bot_id") and STATE.get(f"escalated:{channel}:{root}"):
            threading.Thread(target=_learn_from_owner_reply,
                             args=(event, lambda t, c=channel, r=root: _flow_post(c, r, t)), daemon=True).start()
        _mark_seen(channel, ("fluxo (bot)" if event.get("bot_id") else "mensagem") + (" na thread" if event.get("thread_ts") else " nova"))
        logger.info("[melhorias %s] evento recebido (thread %s, bot=%s)", channel, root, bool(event.get("bot_id")))
        bot = _bot_user_id()
        if event.get("user") != bot and root and event.get("subtype") not in {"message_changed", "message_deleted"}:
            text = str(event.get("text") or "")
            mention = _strip_mentions(text) if (bot and f"<@{bot}>" in text and event.get("thread_ts")) else ""

            # espera o fluxo postar os detalhes na thread e junta mensagens seguidas
            def run() -> None:
                if mention:
                    time.sleep(2)
                else:
                    time.sleep(LIVE_REPLY_DELAY_SECONDS if event.get("thread_ts") and not event.get("bot_id") else 5)
                _handle_owners_flow(channel, root, mention, str(event.get("user") or "") if not event.get("bot_id") else "")
            threading.Thread(target=run, daemon=True).start()
        return True
    thread_ts = str(event.get("thread_ts") or "")
    is_dest = channel == REWARDS_CHANNEL or channel in CHAMADOS_DESTINO.values()
    if channel and is_dest and thread_ts and STATE.get(f"rewards:{thread_ts}"):
        threading.Thread(target=_handle_rewards_reply, args=(event,), daemon=True).start()
        return True
    return False


@slack_app.event("reaction_added")
def handle_reaction_added(event, ack):
    ack()
    threading.Thread(target=_handle_reaction, args=(event,), daemon=True).start()


@slack_app.event("reaction_removed")
def handle_reaction_removed(event, ack):
    ack()


@slack_app.event("message")
def handle_message(event, say, client, ack):
    logger.info("evento message · canal=%s · %s · subtype=%s · thread=%s", event.get("channel"),
                "bot" if event.get("bot_id") else "pessoa", event.get("subtype") or "-",
                "sim" if event.get("thread_ts") and event.get("thread_ts") != event.get("ts") else "não")
    if _route_chamados_event(event):
        ack()
        return
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
        if not is_im:
            try:
                _cr_eps = _STATUS_CHANNEL_EPS.get(str(event.get("channel") or ""))
                if _cr_eps and not event.get("bot_id") and event.get("subtype") in (None, "file_share"):
                    _cread_schedule(str(event.get("channel")), str(event.get("thread_ts") or event.get("ts") or ""), _cr_eps)
                _maybe_mirror_learning(event)
                if _maybe_convo_followup(event, say, client):
                    return
                if _maybe_status_reply(event):
                    return
                _maybe_live_thread_reply(event)
            except Exception:
                logger.exception("Live thread check failed")


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
        "version": APP_VERSION,
        "started_at": _BOOT_AT,
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
    # Em produção o Railway usa o gunicorn (Procfile + gunicorn.conf.py), que liga o agendador. `python app.py`
    # continua funcionando (teste local ou volta rápida para o modelo antigo). Sempre UMA réplica.
    _start_scheduler()
    flask_app.run(host="0.0.0.0", port=PORT)
