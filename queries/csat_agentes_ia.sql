-- CSAT dos agentes de IA (fila Agentforce CX), por agente (ticket_extra_info['AgenteIA__c']). Só visão iFood: nunca
-- soma em AeC/CSU. Camadas L2 e L3: os Wills de L2 (Cancelamento Clube, PF Cancelamento, Pedidos em Preparo…) e o Will
-- de Negativas, que é IA mas aparece em L3 porque entra depois do atendimento humano.
-- VIA_MADRUGADA = avaliações cujo último operador é da célula Madrugada do MOP (pela regra antiga contavam na Madrugada).
-- Parâmetros: {base_inicio}, {base_fim}, {lista_madrugada}.
WITH base AS (
    SELECT support_ticket_id,
           ticket_extra_info['AgenteIA__c']                AS agente_ia_designado,
           CAST(csat_timestamp - INTERVAL 3 HOURS AS DATE) AS data_ref,
           CAST(csat_rating AS INT)                        AS nota,
           lower(ticket_last_agent_email)                  AS agente_email
    FROM saex.gold.cx_support
    WHERE contact_layer IN ('L2', 'L3')
      AND ticket_last_form.queue_name = 'Agentforce CX'
      AND dt >= date_format(add_months(trunc(DATE'{base_inicio}', 'MM'), -2), 'yyyy-MM-dd')
      AND CAST(csat_timestamp - INTERVAL 3 HOURS AS DATE) BETWEEN DATE'{base_inicio}' AND DATE'{base_fim}'
      AND has_valid_csat = true
      AND csat_rating IS NOT NULL
),
ia AS (   -- uma avaliação por ticket
    SELECT COALESCE(NULLIF(trim(agente_ia_designado), ''), 'Sem agente designado') AS agente,
           CASE WHEN nota IN (4, 5) THEN 1 ELSE 0 END AS promotora,
           CASE WHEN agente_email IN ({lista_madrugada}) THEN 1 ELSE 0 END AS madrugada
    FROM base
    QUALIFY ROW_NUMBER() OVER (PARTITION BY support_ticket_id ORDER BY data_ref DESC) = 1
)
SELECT agente AS `AGENTE`, COUNT(*) AS `AVALIACOES`, SUM(promotora) AS `PROMOTORAS`, SUM(madrugada) AS `VIA_MADRUGADA`
FROM ia GROUP BY agente
ORDER BY `AVALIACOES` DESC
