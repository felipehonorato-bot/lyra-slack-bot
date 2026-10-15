# Lyra Slack Bot (v3.2)

## Segregação por EPS (v3.2)

AeC e CSU dividem as filas e **nada de uma aparece para a outra**. Cada EPS tem um
canal (`EPS_CHANNELS`) e tudo fica isolado:

| O quê | Como isola |
| --- | --- |
| Report diário | Um por EPS, no canal dela. Dados filtrados pelo e-mail do operador (`aec` / `csu`), só as células da EPS |
| Compromissos | Coluna `EPS` na aba; cada report só vê e cobra os da própria EPS |
| Conversa | O canal define a EPS; o agente recebe um bloco ESCOPO e recusa dado da outra |
| MOP | Upload no canal da EPS troca só as linhas dela (coluna EPS ou e-mail); o resumo injetado também é filtrado |
| DM | Só `DM_ALLOWED_USERS` (padrão: quem está em `ALERT_CHANNEL`) |
| Canal não configurado | A Lyra responde que não está configurada ali |

As células de cada EPS ficam em `EPS_CELULAS` no `app.py`.

Lyra é o bot de gestão das EPSs do iFood CX no Slack. O app (Flask + Slack Bolt,
no Railway) faz três coisas:

1. **Relay de conversa:** menções `@Lyra` em canal e DMs vão para o agente Lyra no
   Toqan, que consulta o Databricks e responde. O app não tem LLM nem credencial de
   Databricks — **o acesso ao Databricks é configurado dentro do Toqan**.
2. **Rotinas automáticas** (agendador único, horário de Brasília).
3. **Planilha** (Google Sheets): MOP, Compromissos e Estado.

## Rotinas

| Horário | O que acontece |
| --- | --- |
| 08h45 | Relê a thread do report de ontem (respostas tardias) |
| 09h00 | Report de CSAT: mensagem principal + thread. Até 3 tentativas (a cada 10 min); recupera até 13h após restart |
| 11h00 (mín. 2h após o post) | Lê a thread, registra compromissos, pergunta prazo que faltar, marca "sem resposta" |
| 18h00 | Segunda leitura da thread |
| 14h00 no 1º dia útil e dia 15 | Cobrança do MOP (pula fim de semana e feriado nacional) |

O estado de cada rotina fica na aba **Estado Lyra**. Um redeploy no meio do dia não
perde as leituras nem duplica o report.

## Planilha

- **Aba gid 0 — MOP:** substituída quando alguém marca `@Lyra` com um `.xlsx`. O app
  lê valores (não fórmulas), acha a aba com as colunas Nome e Email, salva a versão
  anterior em **MOP backup** e restaura se a gravação falhar.
- **Compromissos:** `Problema Identificado, Ação Tomada, Data Inicio, Data Fim,
  Duração, Resultado Pré, Resultado Pós, Sucesso, Fila, Responsável, Thread`.
  As 3 últimas colunas são criadas automaticamente; linhas antigas continuam válidas.
  Pré = CSAT D-1 da fila no report do dia; Pós = CSAT D-1 da fila no primeiro
  report após o prazo. Sucesso = Sim se Pós > Pré.
- **Estado Lyra:** controle interno do agendador. Não editar.

## Contrato com o agente (prompt v3.1)

O report precisa vir com `===THREAD===` separando mensagem principal e thread, e a
thread começa com todas as filas no formato `• *Fila:* Mês X% · D-1 Y% (n=…)`. Se a
consulta falhar, o agente responde `ERRO: …` e o app não publica nada no canal.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `SLACK_BOT_TOKEN` | Sim | Bot User OAuth Token |
| `SLACK_SIGNING_SECRET` | Sim | Signing secret do app |
| `TOQAN_API_KEY` | Sim | Chave da API do Toqan |
| `GOOGLE_CREDENTIALS_JSON` | Sim | JSON da service account (base64 ou cru), com acesso de editor à planilha |
| `EPS_CHANNELS` | Sim (v3.2) | `AeC:C…,CSU:C…` — canal de cada EPS |
| `CONSOLIDATED_CHANNEL` | Não | Canal interno com report AeC + CSU. Vazio = desligado |
| `INTERNAL_CHANNELS` | Não | Outros canais internos com visão completa |
| `DM_ALLOWED_USERS` | Não | IDs de usuários que podem usar DM. Vazio = só o `ALERT_CHANNEL` |
| `DAILY_REPORT_CHANNEL` | Não | Só no modo antigo (sem `EPS_CHANNELS`) |
| `ALERT_CHANNEL` | Recomendada | Canal ou ID de usuário que recebe alertas técnicos |
| `MOP_ALLOWED_CHANNELS` | Recomendada | IDs de canal liberados para upload do MOP (vírgula). Vazio = qualquer canal |
| `MOP_SPREADSHEET_ID` | Não | ID da planilha (padrão já no código) |
| `DEBUG_TOKEN` | Não | Libera `GET /debug/status` com header `X-Debug-Token` |
| `PORT` | Não | Fornecida pelo Railway |

## Configuração do Slack

**Bot scopes** (OAuth & Permissions) — depois de adicionar, reinstale o app:

- `app_mentions:read`, `chat:write`
- `channels:history` (ler a thread do report em canal público) e `groups:history` (se o canal for privado)
- `im:history`, `im:read`
- `files:read` (baixar o Excel do MOP)
- `reactions:write` (👀 / ✅)

**Eventos:** `app_mention` e `message.im`. Request URL: `https://<railway-url>/slack/events`.
Convide a Lyra para o canal do report, para o canal do MOP e para o `ALERT_CHANNEL`.

## Deploy no Railway

- `Procfile`: `web: python app.py` — **não troque por gunicorn**: o agendador roda
  dentro deste processo.
- **Use 1 réplica.** Mais de uma réplica duplica as rotinas.
- Depois do deploy: `GET /health` deve mostrar `"scheduler_alive": true`.

## Rodar local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha os valores
python app.py
curl http://localhost:3000/health
```

## Segurança

- Nunca versione `.env` ou tokens.
- Endpoints de debug só respondem com `DEBUG_TOKEN` configurado e enviado no header.
- Os logs não registram conteúdo de planilha, de Excel nem dados de clientes.
