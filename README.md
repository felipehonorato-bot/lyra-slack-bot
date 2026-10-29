# Lyra Slack Bot (v4.6)

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
| 07h30, 11h30, 15h30, 19h30 | Testa Lyra (que testa os dois subagentes) + cada agente de `MONITORED_AGENTS` com uma consulta mínima. Avisa no `ALERT_CHANNEL` quando um agente para (token, erro ou sem resposta), **repete o aviso a cada teste enquanto continuar parado** e avisa quando volta |
| Na hora | Se uma conversa volta com erro de acesso aos dados, testa todos os agentes na hora (no máx. 1x por hora) |
| 09h30 | Lembrete do token do Databricks no 6º dia (véspera do vencimento) e no 7º |
| DM: "troquei o token" | Registra a troca (validade de 7 dias), testa todos os agentes e responde o status |
| DM: "como estão os agentes?" | Testa todos e responde o status |
| Report + 5h | Quem foi marcado nas cobranças e não respondeu na thread recebe "algum retorno?" |
| Canal da EPS: "manda a planilha dos operadores" | Excel com e-mail, fila, CSAT, meta, atingimento e quadrante (semana), só da EPS do canal |
| DM: "roda o report" / "roda o report da csu" | Roda o report na hora, nos canais das EPS (teste manual) |
| 08h45 | Relê a thread do report de ontem (respostas tardias) |
| 09h00 | Report de CSAT: um título por fila com CSAT no D-1 (`🔴 Governança · Fila — dd/mm · D-1 x% · meta y%`); na thread: CSAT vs meta, TMA vs plan (com o que puxou: interações ou tempo por interação), problema do D-1 x do mês, quadrantes mês x D-1 com dispersão e a cobrança. O layout é montado pelo app, não pelo modelo. Até 3 tentativas (a cada 10 min); recupera até 13h após restart |
| Sob demanda | Quando perguntam a causa ("por que o CSAT caiu?"), a Lyra Qualidade monta a *esteira de impacto* da fila (gap da meta dividido entre Operador, Tempo, Política iFood, Parceiro e Produto) e a Lyra posta na thread, junto com efeito mix e response rate. Se a queda vem do efeito mix (≥ `MIX_DOMINANT_SHARE`, padrão 80%, com performance estável), ela só explica o mix: sem esteira e sem cobrar plano. `ESTEIRA_ENABLED=1` também posta automático depois do report |
| A cada status da EPS | Nas threads "Controle de SLA ..." dos canais de indicadores (`STATUS_CHANNELS`), a Lyra lê o status de hora em hora e cobra só quando há o que cobrar: CSAT abaixo da meta da fila (e SLA, se houver `SLA_METAS`), mesma justificativa há 3 status, próximo passo genérico, previsão sem prazo. Causa do iFood (cupom, Rosie, sistema) não vira cobrança de SLA. O mesmo ponto só volta a ser cobrado a cada 4 status. Com `STATUS_SHADOW=1` (padrão, fase de testes) ela lê o canal real mas responde no canal de testes da EPS, sem marcar ninguém |
| Ao vivo (1 min após a resposta) | Quando alguém responde na thread de uma fila, a Lyra registra o compromisso e comenta o plano como analista (concreto? ataca o problema? responsável, prazo, como medir?) |
| 11h00 (mín. 2h após o post) | Lê a thread, registra compromissos, pergunta prazo que faltar, marca "sem resposta" |
| 18h00 | Segunda leitura da thread |
| Fluxo Owners CX (tópico Moedas) | Confere os dados mínimos, pede o que faltar na thread, abre o chamado no #rewards-engine-support-cx (com as evidências), devolve o retorno do Rewards na thread de origem e registra na aba *Chamados Moedas* |
| 18h00 no 1º dia útil e dia 15 | Se o MOP não foi atualizado (até 2 dias antes conta), DM para o `ALERT_CHANNEL`. Nada no canal |

O estado de cada rotina fica na aba **Estado Lyra**. Um redeploy no meio do dia não
perde as leituras nem duplica o report.

## Planilhas

São duas, e a service account `lyra-mop@lyra-510815.iam.gserviceaccount.com` precisa ser **Editor** nas duas:

- **Planilha da Lyra** (`LYRA_SPREADSHEET_ID`): abas Compromissos, Estado Lyra e MOP backup.
- **Planilha do MOP** (`MOP_SPREADSHEET_ID`, aba `MOP_WORKSHEET_GID` = "MOP Consolidado"): o MOP oficial. A aba "Instruções" não é tocada.


- **Aba gid 0 — MOP:** atualizada pelo Excel postado na thread do chamado "MOP - Atualização Mensal & Quinzenal" do fluxo Reportar Oráculo (`MOP_FLOW_CHANNEL`), sem precisar marcar a Lyra. Arquivo com as duas EPS substitui tudo; com uma EPS só, troca só as linhas dela. Também aceita `@Lyra` + `.xlsx` no canal de uma EPS (troca só aquela EPS). O app
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
| `MOP_FLOW_CHANNEL` | Recomendada | Canal do fluxo Reportar Oráculo; o Excel de MOP postado lá é lido sozinho |
| `MONITORED_AGENTS` | Recomendada | Todo agente do Toqan que tem conexão própria com o Databricks: `Lyra Indicadores:<api_key>,Lyra Qualidade:<api_key>,Nexus:<api_key>,Vera:<api_key>,ClubIA:<api_key>` (a Lyra principal entra sempre) |
| `NO_DATA_AGENTS` | Não | Agentes monitorados que não usam o Databricks: o teste só confere se respondem (padrão `Em preparo`) |
| `SHARED_TOKEN_AGENTS` | Não | Agentes que usam o mesmo token do Databricks; aparecem no alerta de token (padrão `Nexus,Vera,ClubIA`) |
| `AGENT_CHECK_HOURS` | Não | Horas dos testes, sempre no minuto 30 (padrão `7,11,15,19`) |
| `DATABRICKS_TOKEN_VALIDITY_DAYS` | Não | Validade do token em dias (padrão `7`) |
| `DATABRICKS_TOKEN_RENEWED` | Não | Data da última troca do token (só para começar; depois vale o "troquei o token" na DM) |
| `TMA_PLAN` | Não | Plan de TMA por célula (tempo único em segundos / média de interações), quando mudar o planejamento: `CX Suporte:520/1.8;Madrugada:562/1.89` (padrão = aba PLAN de setembro) |
| `OWNERS_FLOW_CHANNEL` | Para chamados | Canal do Fluxo Owners CX: chamado de Moedas é triado e aberto no Rewards |
| `REWARDS_CHANNEL` | Não | Canal do Rewards (padrão `C08M93FKB63`, #rewards-engine-support-cx) |
| `REWARDS_WEBHOOK_URL` | Recomendada | Webhook do fluxo Rewards Engine CX Support (abre o chamado pelo próprio fluxo). Vazio = a Lyra posta o chamado direto no canal |
| `REWARDS_PROBLEM_TYPES` | Não | Opções do campo "Tipo de problema" do Rewards, separadas por `;` |
| `FILA_OWNERS` | Não | Owners marcados nas cobranças: `CX Suporte:U1|U2;Madrugada:U3` (padrão já no código) |
| `ALERT_CHANNEL` | Recomendada | Quem recebe os alertas técnicos: ID de usuário e/ou canal, separados por vírgula (ex.: `U0B1E6UJ8P8,C0XXXX`) |
| `MOP_ALLOWED_CHANNELS` | Recomendada | IDs de canal liberados para upload do MOP (vírgula). Vazio = qualquer canal |
| `LYRA_SPREADSHEET_ID` | Não | Planilha da Lyra: Compromissos, Estado Lyra, MOP backup (padrão `1Up11…`) |
| `MOP_SPREADSHEET_ID` / `MOP_WORKSHEET_GID` | Não | Planilha e aba do MOP oficial (padrão `1cy23…` / `464304384`, aba "MOP Consolidado") |
| `DEBUG_TOKEN` | Não | Libera `GET /debug/status` com header `X-Debug-Token` |
| `PORT` | Não | Fornecida pelo Railway |

## Configuração do Slack

**Bot scopes** (OAuth & Permissions) — depois de adicionar, reinstale o app:

- `app_mentions:read`, `chat:write`
- `channels:history` (ler a thread do report em canal público) e `groups:history` (se o canal for privado)
- `im:history`, `im:read`
- `files:read` (baixar o Excel do MOP)
- `files:write` (enviar o Excel do MOP quando pedem "me manda o MOP")
- `reactions:write` (👀 / ✅)
- `users:read` (achar no Slack o owner cadastrado por nome, ex.: `@Adriana Ventura da Silva`)

**Eventos:** `app_mention`, `message.im` e `message.channels` (ou `message.groups`, se o canal do fluxo for privado). Request URL: `https://<railway-url>/slack/events`.
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
