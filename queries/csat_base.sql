-- BASE OFICIAL DO CSAT (regra da Lyra Indicadores, seção 9) — fragmento usado pelas consultas fixas de CSAT.
-- O app troca {base_inicio}, {base_fim} (datas da avaliação) e {lista_madrugada} (operadores da célula Madrugada no MOP).
WITH base AS (
    SELECT
        support_ticket_id,
        ticket_extra_info['AgenteIA__c']                        AS agente_ia_designado,
        CAST(csat_timestamp - INTERVAL 3 HOURS AS DATE)         AS data_ref,
        CAST(csat_rating AS INT)                                AS nota,
        ticket_last_form.queue_name                             AS fila,
        lower(ticket_last_agent_email)                          AS agente_email,
        ticket_contact_reason                                   AS motivo
    FROM saex.gold.cx_support
    WHERE contact_layer = 'L3'                                                      -- só atendimento humano
      AND dt >= date_format(add_months(trunc(DATE'{base_inicio}', 'MM'), -2), 'yyyy-MM-dd')  -- partição (com folga)
      AND CAST(csat_timestamp - INTERVAL 3 HOURS AS DATE) BETWEEN DATE'{base_inicio}' AND DATE'{base_fim}'
      AND has_valid_csat = true
      AND csat_rating IS NOT NULL
),
dedup AS (   -- uma avaliação por ticket
    SELECT * FROM (
        SELECT b.*, ROW_NUMBER() OVER (PARTITION BY support_ticket_id ORDER BY data_ref DESC) AS rn FROM base b
    ) WHERE rn = 1
),
filas_norm AS (   -- FILA (regra oficial): Madrugada pelo operador primeiro, depois a fila normalizada
    SELECT d.*,
        CASE
            WHEN agente_email IN ({lista_madrugada}) THEN 'Madrugada'
            WHEN fila = 'PF Clube Vip + Super clientes' THEN 'PF Super Clientes'
            WHEN fila IN ('PF Revisão Manual (Multi + Food)', 'Revisão Manual Multi + Food)') THEN 'PF Revisão Manual'
            WHEN fila = 'CX Review' THEN 'Review'
            WHEN fila = 'Agentforce CX' AND agente_ia_designado = 'WillNegativas' THEN 'Agentforce CX'
            WHEN fila = 'Agentforce CX' THEN NULL
            ELSE fila
        END AS fila_relatorio
    FROM dedup d
),
filas AS (   -- EPS pela fila do report
    SELECT n.*,
        CASE
            WHEN fila_relatorio IN ('CX Suporte', 'Madrugada', 'CX Review - AeC', 'CX Super Cliente - AeC') THEN 'AeC'
            WHEN fila_relatorio IN ('CX Review - CSU', 'CX Super Cliente - CSU', 'PF Cancelamento', 'PF Super Clientes',
                                    'PF Revisão Manual', 'CX Denúncia', 'Fraudes DX', 'DX - PF Contestação',
                                    'DX - PF Contestação Bloqueio temporário') THEN 'CSU'
        END AS eps_fila
    FROM filas_norm n
)
