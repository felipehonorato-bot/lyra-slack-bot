-- MES_PLANO: 2026-11
-- Visão da CAPA v2 (eficiência CX) — handoff validado contra '11 - NOVEMBRO v1' e já executado no Databricks.
-- Fórmulas sem alteração. O app troca {data_inicio}, {data_fim} e {mes_plano}.
-- Manutenção mensal: MES_PLANO, plano_ticket, celulas, de_para.
-- Colunas extras no fim (SOMA TEMPO ATRIBUIÇÃO, SLA BASE, SLA DENTRO): só para o consolidado da EPS com somas.
-- =====================================================================
-- VISÃO DA CAPA — NOVEMBRO/26 (reproduz a aba CAPA do "11 - NOVEMBRO v1")
-- Base: query nova (formulario, ticket_last_eps, segmentation, last_queue_name_ajust), sem alteração
--       exceto o bloco 'parametros' (novembro/26 fixo, realizado e plano até D-1).
-- Saída: 1 linha por célula, colunas na ordem da CAPA + coluna SLA pela regra:
--        CX Super Cliente (AeC/CSU) = SLA 2 min (coluna M) | demais células = SLA 5 min (coluna O)
-- Roda direto na origem (sem CREATE TABLE/VIEW): DE PARA e plano entram como VALUES.
-- v2: ajuste da Genie no plano_celula (LATERAL VIEW logo após a tabela) + colunas numéricas como DOUBLE (exportam como número, não texto).
-- =====================================================================

WITH parametros AS (
    SELECT
        DATE'{data_inicio}'                                     AS data_inicio,  -- preenchido pelo app
        LEAST(DATE'{data_fim}', DATE_SUB(CURRENT_DATE(), 1))    AS data_fim      -- até D-1 (igual ao corte do plano na CAPA)
),

--AJUSTE PARA AGENTFORCE PARA META TMA
ultimas_filas_humanas AS (
    -- Busca a última fila humana válida (ignorando Agentforce E Awaiting)
    SELECT 
        support_ticket_id,
        queue_name AS ultima_fila_humana,
        ROW_NUMBER() OVER (
            PARTITION BY support_ticket_id 
            ORDER BY timestamp DESC
        ) AS rn
    FROM cx_gci_bi.entradas_filas
    WHERE queue_name NOT IN (
      -- AgentForce CX
      'Agentforce CX', 'Agentforce Will - Problemas com o pedido','Agentforce CX Triagem',
      -- AgentForce PX
      'Agente Afonso Multicategorias','Agentforce Afonso Restaurantes',
      -- AgentForce DX
      'Agentforce DX',
      -- AgentForce Beneficios
      'AgentForce Beni Colaboradores',
      -- AgentForce Integradoras
      'Agentforce Integradoras',
       'Awaiting')
),
ultima_fila_ticket AS (
    -- Busca a última fila absoluta registrada para o ticket (útil quando for 100% Agentforce)
    SELECT 
        support_ticket_id,
        queue_name AS ultima_fila_absoluta,
        ROW_NUMBER() OVER (
            PARTITION BY support_ticket_id 
            ORDER BY timestamp DESC
        ) AS rn
    FROM cx_gci_bi.entradas_filas
),

base_dados AS (
    SELECT 
        t1.*,
        COALESCE(cx_support.order_business_unit, t1.BU) as BU_final,
        CASE 
            WHEN EXTRACT(HOUR FROM t1.timestamp) BETWEEN 2 AND 7
                 AND (EXTRACT(HOUR FROM t1.timestamp) != 2 OR EXTRACT(MINUTE FROM t1.timestamp) >= 30)
                 AND (EXTRACT(HOUR FROM t1.timestamp) != 7 OR EXTRACT(MINUTE FROM t1.timestamp) <= 30)
            THEN 'célula da madrugada'
            ELSE t1.queue_name
        END as fila_oficial,
        -- Prioridade do last_queue_name_ajust: 
        -- 1. Última fila humana válida
        -- 2. Última fila absoluta do ticket (Agentforce) caso não haja atendimento humano
        COALESCE(u.ultima_fila_humana, ult.ultima_fila_absoluta, t1.queue_name) AS last_queue_name_ajust
    FROM cx_gci_bi.entradas_filas t1
    CROSS JOIN parametros p
    LEFT JOIN saex.gold.cx_support as cx_support
        ON cx_support.support_ticket_id = t1.support_ticket_id

    -- JOINs para tratativa do last_queue_name_ajust
    LEFT JOIN ultimas_filas_humanas u 
       ON t1.support_ticket_id = u.support_ticket_id 
      AND u.rn = 1
    LEFT JOIN ultima_fila_ticket ult 
       ON t1.support_ticket_id = ult.support_ticket_id 
      AND ult.rn = 1

    WHERE t1.pilar IN ('CX', 'DX')
        AND DATE(t1.timestamp) BETWEEN p.data_inicio AND p.data_fim
),

casos_planejado AS (
    SELECT
        'casos_planejado' As index,
        NULL AS faixa, NULL as ticket_id,
        DATE(t1.timestamp_ref) AS data,
        CONCAT(LPAD(HOUR(t1.timestamp_ref), 2, '0'), ':00:00') as hora,
        NULL as hora_curva,
        t1.pilar,
        t1.celula_agrup AS fila,
        t1.celula_agrup AS fila_oficial,
        lower(t1.celula_agrup) as celula,    
        'Humano' as automation_type,
        NULL as support_contact_reason, NULL as ticket_reclassification,
        NULL AS eps, NULL as e_mail, NULL as segmentation, NULL AS BU_final,
        NULL AS formulario,
        sum(t1.criados_plan) AS quantidade
    FROM saex_ops.reguas_planejamento t1
    CROSS JOIN parametros p
    WHERE DATE(t1.timestamp_ref) BETWEEN p.data_inicio AND p.data_fim
        AND t1.pilar IN ('CX', 'DX')
    GROUP BY DATE(t1.timestamp_ref), t1.pilar, t1.celula_agrup, 
        CONCAT(LPAD(HOUR(t1.timestamp_ref), 2, '0'), ':00:00')
),

tmi_planejado AS (
    SELECT
        'tmi_planejados' As index,
        NULL AS faixa, NULL as ticket_id,
        DATE(t1.timestamp_ref) AS data,
        CONCAT(LPAD(HOUR(t1.timestamp_ref), 2, '0'), ':00:00') as hora,
        NULL as hora_curva,
        t1.pilar,
        t1.celula_agrup AS fila,
        t1.celula_agrup AS fila_oficial,
        lower(t1.celula_agrup) as celula,          
        'Humano' as automation_type,
        NULL as support_contact_reason, NULL as ticket_reclassification,       
        NULL AS eps, NULL as e_mail, NULL as segmentation, NULL AS BU_final,
        NULL AS formulario,
        sum(t1.tmt_plan*t1.criados_plan) AS quantidade  
    FROM saex_ops.reguas_planejamento t1
    CROSS JOIN parametros p
    WHERE DATE(t1.timestamp_ref) BETWEEN p.data_inicio AND p.data_fim
        AND t1.pilar IN ('CX', 'DX')
    GROUP BY DATE(t1.timestamp_ref), t1.pilar, t1.celula_agrup,
        CONCAT(LPAD(HOUR(t1.timestamp_ref), 2, '0'), ':00:00')
),

entradas AS (
    SELECT 
        'entrantes' AS index, NULL AS faixa, NULL as ticket_id,
        DATE(t1.timestamp) AS data,
        CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':00:00') as hora,
        CASE
            WHEN MINUTE(t1.timestamp) < 30 THEN CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':30:00')
        END AS hora_curva,
        t1.pilar, t1.queue_name AS fila, t1.fila_oficial, t1.celula, t1.automation_type,
        t1.support_contact_reason, t1.ticket_reclassification,        
        t1.ticket_last_eps AS eps,
        t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END AS segmentation,
        t1.BU_final,
        t1.formulario,
        COUNT(*) AS quantidade
    FROM base_dados t1
    GROUP BY DATE(t1.timestamp), t1.pilar, t1.queue_name, t1.fila_oficial, t1.celula,
        CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':00:00'),
        CASE
            WHEN MINUTE(t1.timestamp) < 30 THEN CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':30:00')
        END,
        t1.automation_type, t1.support_contact_reason, t1.ticket_reclassification,
        t1.ticket_last_eps, t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END,
        t1.BU_final, t1.formulario
),

tratados AS (
    SELECT 
        'tratados' AS index, NULL AS faixa, NULL as ticket_id,
        DATE(t1.timestamp_assigned) AS data,
        CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00') as hora,
        CASE
            WHEN MINUTE(t1.timestamp_assigned) < 30 THEN CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':30:00')
        END AS hora_curva,
        t1.pilar, t1.queue_name AS fila, t1.fila_oficial, t1.celula, t1.automation_type,
        t1.support_contact_reason, t1.ticket_reclassification,        
        t1.ticket_last_eps AS eps,
        t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END AS segmentation,
        t1.BU_final,
        t1.formulario,
        COUNT(*) AS quantidade
    FROM base_dados t1
    CROSS JOIN parametros p
    WHERE t1.timestamp_assigned IS NOT NULL
        AND DATE(t1.timestamp_assigned) BETWEEN p.data_inicio AND p.data_fim
    GROUP BY DATE(t1.timestamp_assigned), t1.pilar, t1.queue_name, t1.fila_oficial, t1.celula,
        CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00'),
        CASE
            WHEN MINUTE(t1.timestamp_assigned) < 30 THEN CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':30:00')
        END,
        t1.automation_type, t1.support_contact_reason, t1.ticket_reclassification,
        t1.ticket_last_eps, t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END,
        t1.BU_final, t1.formulario
),

tm_atribuicao AS (
    SELECT 
        'tm_atribuicao' AS index, NULL AS faixa, NULL as ticket_id,
        DATE(t1.timestamp_assigned) AS data,
        CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00') as hora,
        CASE
            WHEN MINUTE(t1.timestamp_assigned) < 30 THEN CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':30:00')
        END AS hora_curva,
        t1.pilar, t1.queue_name AS fila, t1.fila_oficial, t1.celula, t1.automation_type,
        t1.support_contact_reason, t1.ticket_reclassification,        
        t1.ticket_last_eps AS eps,
        t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END AS segmentation,
        t1.BU_final,
        t1.formulario,
        sum(t1.tempo_atribuicao_com_operador) AS quantidade
    FROM base_dados t1
    CROSS JOIN parametros p
    WHERE t1.timestamp_assigned IS NOT NULL
        AND DATE(t1.timestamp_assigned) BETWEEN p.data_inicio AND p.data_fim
    GROUP BY DATE(t1.timestamp_assigned), t1.pilar, t1.queue_name, t1.fila_oficial, t1.celula,
        CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00'),
        CASE
            WHEN MINUTE(t1.timestamp_assigned) < 30 THEN CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':30:00')
        END,
        t1.automation_type, t1.support_contact_reason, t1.ticket_reclassification,
        t1.ticket_last_eps, t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END,
        t1.BU_final, t1.formulario
),

tmi AS (
    SELECT 
        'tmi' AS index, NULL AS faixa, NULL as ticket_id,
        DATE(t1.timestamp_assigned) AS data,
        CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00') as hora,
        CASE
            WHEN MINUTE(t1.timestamp) < 30 THEN
                CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00')
            ELSE
                CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':30:00')
        END AS hora_curva,
        t1.pilar, t1.queue_name AS fila, t1.fila_oficial, t1.celula, t1.automation_type,
        t1.support_contact_reason, t1.ticket_reclassification,        
        t1.ticket_last_eps AS eps,
        t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END AS segmentation,
        t1.BU_final,
        t1.formulario,
        sum(t1.tmi) AS quantidade
    FROM base_dados t1
    CROSS JOIN parametros p
    WHERE t1.timestamp_assigned IS NOT NULL
        AND DATE(t1.timestamp_assigned) BETWEEN p.data_inicio AND p.data_fim
    GROUP BY DATE(t1.timestamp_assigned), t1.pilar, t1.queue_name, t1.fila_oficial, t1.celula,
        CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00'),
        CASE
            WHEN MINUTE(t1.timestamp) < 30 THEN
                CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':00:00')
            ELSE
                CONCAT(LPAD(HOUR(t1.timestamp_assigned), 2, '0'), ':30:00')
        END,
        t1.automation_type, t1.support_contact_reason, t1.ticket_reclassification,
        t1.ticket_last_eps, t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END,
        t1.BU_final, t1.formulario
),

casos_unicos AS (
    SELECT 
        'casos_unicos' AS index, NULL AS faixa, t.ticket_id,
        DATE(t.ticket_created_time) AS data,
        CONCAT(LPAD(HOUR(t.ticket_created_time), 2, '0'), ':00:00') as hora,
        NULL as hora_curva,
        t.pilar, t.last_queue_name_ajust AS fila, 
        CASE 
            WHEN EXTRACT(HOUR FROM t.ticket_created_time) BETWEEN 2 AND 7
                 AND (EXTRACT(HOUR FROM t.ticket_created_time) != 2 OR EXTRACT(MINUTE FROM t.ticket_created_time) >= 30)
                 AND (EXTRACT(HOUR FROM t.ticket_created_time) != 7 OR EXTRACT(MINUTE FROM t.ticket_created_time) <= 30)
            THEN 'célula da madrugada'
            ELSE t.last_queue_name_ajust
        END as fila_oficial,       
        --t.fila_oficial,
        t.celula_fechamento AS celula,
        t.automation_type, t.support_contact_reason, t.ticket_reclassification,
        t.ticket_last_eps as eps, NULL as e_mail,
        CASE WHEN LOWER(COALESCE(t.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END AS segmentation,
        t.BU_final,
        t.formulario,
        COUNT(DISTINCT t.ticket_id) as quantidade
    FROM base_dados t
    CROSS JOIN parametros p
    WHERE t.ticket_created_time IS NOT NULL
        AND DATE(t.ticket_created_time) BETWEEN p.data_inicio AND p.data_fim
    GROUP BY DATE(t.ticket_created_time), t.pilar, t.last_queue_name_ajust, 
        CASE 
            WHEN EXTRACT(HOUR FROM t.ticket_created_time) BETWEEN 2 AND 7
                 AND (EXTRACT(HOUR FROM t.ticket_created_time) != 2 OR EXTRACT(MINUTE FROM t.ticket_created_time) >= 30)
                 AND (EXTRACT(HOUR FROM t.ticket_created_time) != 7 OR EXTRACT(MINUTE FROM t.ticket_created_time) <= 30)
            THEN 'célula da madrugada'
            ELSE t.last_queue_name_ajust
        END,
        --t.fila_oficial,        
        t.celula_fechamento,
        CONCAT(LPAD(HOUR(t.ticket_created_time), 2, '0'), ':00:00'),
        t.automation_type, t.support_contact_reason, t.ticket_reclassification,
        t.ticket_last_eps,
        CASE WHEN LOWER(COALESCE(t.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END,
        t.BU_final, t.formulario, t.ticket_id
),

sla_1_resposta AS (
    SELECT 
        'sla_interacao' AS index,
        CASE
            WHEN t1.time_to_first_answer IS NULL THEN 'sem faixa'
            WHEN t1.time_to_first_answer < 0 THEN 'Undefined'
            WHEN t1.time_to_first_answer BETWEEN 0 AND 120 THEN '0-2min'
            WHEN t1.time_to_first_answer BETWEEN 121 AND 180 THEN '2-3min'
            WHEN t1.time_to_first_answer BETWEEN 181 AND 300 THEN '3-5min'
            WHEN t1.time_to_first_answer BETWEEN 301 AND 480 THEN '5-8min'
            WHEN t1.time_to_first_answer BETWEEN 481 AND 600 THEN '8-10min'
            WHEN t1.time_to_first_answer BETWEEN 601 AND 1800 THEN '10-30min'
            WHEN t1.time_to_first_answer BETWEEN 1801 AND 3600 THEN '30-1hr'
            WHEN t1.time_to_first_answer > 3600 THEN '+1hr'
            ELSE null
        END AS faixa,
        NULL as ticket_id,
        DATE(t1.timestamp) AS data,
        CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':00:00') as hora,
        CASE
            WHEN MINUTE(t1.timestamp) < 30 THEN CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':30:00')
        END AS hora_curva,
        t1.pilar, t1.queue_name AS fila, t1.fila_oficial, t1.celula, t1.automation_type,
        t1.support_contact_reason, t1.ticket_reclassification,        
        t1.ticket_last_eps AS eps,
        t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END AS segmentation,
        t1.BU_final,
        t1.formulario,
        COUNT(*) AS quantidade
    FROM base_dados t1
    WHERE t1.time_to_first_answer IS NOT NULL
    GROUP BY DATE(t1.timestamp), t1.pilar, t1.queue_name, t1.fila_oficial, t1.celula,
        CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':00:00'),
        CASE
            WHEN MINUTE(t1.timestamp) < 30 THEN CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(t1.timestamp), 2, '0'), ':30:00')
        END,
        CASE
            WHEN t1.time_to_first_answer IS NULL THEN 'sem faixa'
            WHEN t1.time_to_first_answer < 0 THEN 'Undefined'
            WHEN t1.time_to_first_answer BETWEEN 0 AND 120 THEN '0-2min'
            WHEN t1.time_to_first_answer BETWEEN 121 AND 180 THEN '2-3min'
            WHEN t1.time_to_first_answer BETWEEN 181 AND 300 THEN '3-5min'
            WHEN t1.time_to_first_answer BETWEEN 301 AND 480 THEN '5-8min'
            WHEN t1.time_to_first_answer BETWEEN 481 AND 600 THEN '8-10min'
            WHEN t1.time_to_first_answer BETWEEN 601 AND 1800 THEN '10-30min'
            WHEN t1.time_to_first_answer BETWEEN 1801 AND 3600 THEN '30-1hr'
            WHEN t1.time_to_first_answer > 3600 THEN '+1hr'
            ELSE null
        END,
        t1.automation_type, t1.support_contact_reason, t1.ticket_reclassification,
        t1.ticket_last_eps, t1.e_mail,
        CASE WHEN LOWER(COALESCE(t1.segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END,
        t1.BU_final, t1.formulario
),

tempos_por_ticket AS (
    SELECT 
        ticket_id,
        DATE(ticket_created_time) AS data,
        CONCAT(LPAD(HOUR(ticket_created_time), 2, '0'), ':00:00') as hora,
        CASE
            WHEN MINUTE(ticket_created_time) < 30 THEN CONCAT(LPAD(HOUR(ticket_created_time), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(ticket_created_time), 2, '0'), ':30:00')
        END AS hora_curva,
        pilar, queue_name AS fila, fila_oficial, celula, automation_type,
        support_contact_reason, ticket_reclassification,        
        ticket_last_eps as eps,
        CASE WHEN LOWER(COALESCE(segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END AS segmentation,
        BU_final,
        formulario,
        SUM(tempo_atribuicao_com_operador) AS total_tempo_atribuicao,
        SUM(waiting_time) AS total_waiting_time
    FROM base_dados
    CROSS JOIN parametros p
    WHERE ticket_created_time IS NOT NULL
        AND DATE(ticket_created_time) BETWEEN p.data_inicio AND p.data_fim
    GROUP BY ticket_id, DATE(ticket_created_time), 
        CONCAT(LPAD(HOUR(ticket_created_time), 2, '0'), ':00:00'),
        CASE
            WHEN MINUTE(ticket_created_time) < 30 THEN CONCAT(LPAD(HOUR(ticket_created_time), 2, '0'), ':00:00')
            ELSE CONCAT(LPAD(HOUR(ticket_created_time), 2, '0'), ':30:00')
        END,
        pilar, queue_name, fila_oficial, celula, automation_type, 
        support_contact_reason, ticket_reclassification, ticket_last_eps,
        CASE WHEN LOWER(COALESCE(segmentation, '')) LIKE '%platinum%' THEN 'platinum' ELSE 'outros' END,
        BU_final, formulario
),

sla_resolucao AS (
    SELECT 
        'sla_resolucao' AS index,
        CASE
            WHEN (total_tempo_atribuicao + total_waiting_time) IS NULL THEN 'sem faixa'
            WHEN (total_tempo_atribuicao + total_waiting_time) < 0 THEN 'Undefined'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 0 AND 120 THEN '0-2min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 121 AND 180 THEN '2-3min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 181 AND 300 THEN '3-5min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 301 AND 480 THEN '5-8min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 481 AND 600 THEN '8-10min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 601 AND 1800 THEN '10-30min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 1801 AND 3600 THEN '30-1hr'
            WHEN (total_tempo_atribuicao + total_waiting_time) > 3600 THEN '+1hr'
            ELSE null
        END AS faixa,
        ticket_id, data, hora, hora_curva, pilar, fila, fila_oficial, celula,
        automation_type, support_contact_reason, ticket_reclassification, 
        eps, NULL as e_mail, segmentation, BU_final,
        formulario,
        COUNT(DISTINCT ticket_id) as quantidade
    FROM tempos_por_ticket
    GROUP BY 
        CASE
            WHEN (total_tempo_atribuicao + total_waiting_time) IS NULL THEN 'sem faixa'
            WHEN (total_tempo_atribuicao + total_waiting_time) < 0 THEN 'Undefined'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 0 AND 120 THEN '0-2min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 121 AND 180 THEN '2-3min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 181 AND 300 THEN '3-5min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 301 AND 480 THEN '5-8min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 481 AND 600 THEN '8-10min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 601 AND 1800 THEN '10-30min'
            WHEN (total_tempo_atribuicao + total_waiting_time) BETWEEN 1801 AND 3600 THEN '30-1hr'
            WHEN (total_tempo_atribuicao + total_waiting_time) > 3600 THEN '+1hr'
            ELSE null
        END,
        ticket_id, data, hora, hora_curva, pilar, fila, fila_oficial, celula, automation_type, 
        support_contact_reason, ticket_reclassification, eps, segmentation, BU_final, formulario
),

todos_dados AS (
    SELECT * FROM entradas
    UNION ALL SELECT * FROM tratados
    UNION ALL SELECT * FROM tm_atribuicao
    UNION ALL SELECT * FROM tmi
    UNION ALL SELECT * FROM casos_planejado
    UNION ALL SELECT * FROM tmi_planejado
    UNION ALL SELECT * FROM casos_unicos
    UNION ALL SELECT * FROM sla_1_resposta
    UNION ALL SELECT * FROM sla_resolucao
),

-- =====================================================================
-- VISÃO DA CAPA
-- =====================================================================

-- 1) Pivot por fila com somas brutas (sem HAVING, igual à query nova)
por_fila AS (
    SELECT
        fila, fila_oficial,
        SUM(CASE WHEN index = 'entrantes'     THEN quantidade ELSE 0 END) AS entradas,
        SUM(CASE WHEN index = 'tratados'      THEN quantidade ELSE 0 END) AS tratados,
        SUM(CASE WHEN index = 'casos_unicos'  THEN quantidade ELSE 0 END) AS casos_unicos,
        SUM(CASE WHEN index = 'tm_atribuicao' THEN quantidade ELSE 0 END) AS soma_tempo_atribuicao,
        SUM(CASE WHEN index = 'tmi'           THEN quantidade ELSE 0 END) AS soma_tempo_interacao,
        SUM(CASE WHEN index = 'sla_interacao' AND faixa = '0-2min' THEN quantidade ELSE 0 END) AS sla_i_dentro_2min,
        SUM(CASE WHEN index = 'sla_interacao' AND faixa IN ('0-2min','2-3min') THEN quantidade ELSE 0 END) AS sla_i_dentro_3min,
        SUM(CASE WHEN index = 'sla_interacao' AND faixa IN ('0-2min','2-3min','3-5min') THEN quantidade ELSE 0 END) AS sla_i_dentro_5min,
        SUM(CASE WHEN index = 'sla_interacao' AND faixa IN ('0-2min','2-3min','3-5min','5-8min') THEN quantidade ELSE 0 END) AS sla_i_dentro_8min,
        SUM(CASE WHEN index = 'sla_interacao' AND faixa IN ('0-2min','2-3min','3-5min','5-8min','8-10min') THEN quantidade ELSE 0 END) AS sla_i_dentro_10min,
        SUM(CASE WHEN index = 'sla_interacao' AND faixa IN ('0-2min','2-3min','3-5min','5-8min','8-10min','10-30min','30-1hr','+1hr') THEN quantidade ELSE 0 END) AS sla_i_base,
        SUM(CASE WHEN index = 'sla_resolucao' AND faixa IN ('0-2min','2-3min','3-5min','5-8min','8-10min') THEN quantidade ELSE 0 END) AS sla_r_dentro_10min,
        SUM(CASE WHEN index = 'sla_resolucao' AND faixa IN ('0-2min','2-3min','3-5min','5-8min','8-10min','10-30min','30-1hr','+1hr') THEN quantidade ELSE 0 END) AS sla_r_base
    FROM todos_dados
    WHERE pilar IN ('CX', 'DX')
    GROUP BY fila, fila_oficial
),

-- 2) DE PARA da planilha de novembro: CONCAT(fila, fila_oficial) -> célula da CAPA
de_para AS (
    SELECT * FROM VALUES
    ('ArbitragemArbitragem', 'CX Suporte'),
    ('CX Problemas com a entregaCX Problemas com a entrega', 'CX Suporte'),
    ('CX SuporteAgentforce CX', 'CX Suporte'),
    ('CX SuporteCX Suporte', 'CX Suporte'),
    ('Food deliveryFood delivery', 'CX Suporte'),
    ('GroceriesGroceries', 'CX Suporte'),
    ('Pós EntregaPós Entrega', 'CX Suporte'),
    ('RetroalimentaçãoRetroalimentação', 'CX Suporte'),
    ('Teste OráculoTeste Oráculo', 'CX Suporte'),
    ('Teste Oráculocélula da madrugada', 'CX Suporte'),
    ('TesteAtendimentoOráculoTesteAtendimentoOráculo', 'CX Suporte'),
    ('cx_critical_casesAeCoutros', 'CX Suporte'),
    ('cx_critical_casesCSUoutros', 'CX Suporte'),
    ('cx_live_cellAeCoutros', 'CX Suporte'),
    ('cx_live_cellCSUoutros', 'CX Suporte'),
    ('Arbitragemcélula da madrugada', 'Madrugada'),
    ('CX Problemas com a entregacélula da madrugada', 'Madrugada'),
    ('CX Review - AeCcélula da madrugada', 'Madrugada'),
    ('CX Review - CSUcélula da madrugada', 'Madrugada'),
    ('CX Reviewcélula da madrugada', 'Madrugada'),
    ('CX Suportecélula da madrugada', 'Madrugada'),
    ('Food deliverycélula da madrugada', 'Madrugada'),
    ('Groceriescélula da madrugada', 'Madrugada'),
    ('Pós Entregacélula da madrugada', 'Madrugada'),
    ('Retroalimentaçãocélula da madrugada', 'Madrugada'),
    ('Review Foodcélula da madrugada', 'Madrugada'),
    ('Review Groceriescélula da madrugada', 'Madrugada'),
    ('Reviewcélula da madrugada', 'Madrugada'),
    ('CX Review - AeCAgentforce CX', 'CX Review - AeC'),
    ('CX Review - AeCCX Review - AeC', 'CX Review - AeC'),
    ('CX Review - CSUAgentforce CX', 'CX Review - CSU'),
    ('CX Review - CSUCX Review - CSU', 'CX Review - CSU'),
    ('CX Super Cliente - AeCAgentforce CX', 'CX Super Cliente - AeC'),
    ('CX Super Cliente - AeCCX Super Cliente - AeC', 'CX Super Cliente - AeC'),
    ('CX Super Cliente - AeCcélula da madrugada', 'CX Super Cliente - AeC'),
    ('cx_live_cellAeCplatinum', 'CX Super Cliente - AeC'),
    ('CX Super Cliente - CSUAgentforce CX', 'CX Super Cliente - CSU'),
    ('CX Super Cliente - CSUCX Super Cliente - CSU', 'CX Super Cliente - CSU'),
    ('CX Super Cliente - CSUcélula da madrugada', 'CX Super Cliente - CSU'),
    ('cx_live_cellCSUplatinum', 'CX Super Cliente - CSU'),
    ('live_cell_delayCSUplatinum', 'CX Super Cliente - CSU'),
    ('PF Cancelamento FoodPF Cancelamento Food', 'PF Cancelamento'),
    ('PF Cancelamento Foodcélula da madrugada', 'PF Cancelamento'),
    ('PF Cancelamento MultiPF Cancelamento Multi', 'PF Cancelamento'),
    ('PF Cancelamento Multicélula da madrugada', 'PF Cancelamento'),
    ('PF CancelamentoAgentforce CX', 'PF Cancelamento'),
    ('PF CancelamentoPF Cancelamento', 'PF Cancelamento'),
    ('PF Cancelamentocélula da madrugada', 'PF Cancelamento'),
    ('PF Clube Vip + Super clientes MedicamentPF Clube Vip + Super clientes Medicament', 'PF Super Clientes'),
    ('PF Clube Vip + Super clientesPF Clube Vip + Super clientes', 'PF Super Clientes'),
    ('PF Clube Vip + Super clientescélula da madrugada', 'PF Super Clientes'),
    ('PF Super ClientesAgentforce CX', 'PF Super Clientes'),
    ('PF Super Clientescélula da madrugada', 'PF Super Clientes'),
    ('PF Revisão Manual (Multi + Food)PF Revisão Manual (Multi + Food)', 'PF Revisão Manual'),
    ('PF Revisão Manual (Multi + Food)célula da madrugada', 'PF Revisão Manual'),
    ('PF Revisão ManualAgentforce CX', 'PF Revisão Manual'),
    ('PF Revisão Manualcélula da madrugada', 'PF Revisão Manual'),
    ('CX DenúnciaCX Denúncia', 'CX Denúncia'),
    ('CX Denúnciacélula da madrugada', 'CX Denúncia'),
    ('DX - PFDX - PF', 'Fraudes DX'),
    ('DX - PFcélula da madrugada', 'Fraudes DX'),
    ('DX - PF ContestaçãoDX - PF Contestação', 'DX - PF Contestação'),
    ('DX - PF Contestação Bloqueio temporárioDX - PF Contestação Bloqueio temporário', 'DX - PF Contestação Bloqueio temporário'),
    ('Fila desativada 37 - CanarinhosFila desativada 37 - Canarinhos', 'Fila desativada 37 - Canarinhos'),
    ('Fila desativada 37 - Canarinhoscélula da madrugada', 'Fila desativada 37 - Canarinhos')
    AS t(chave, celula_capa)
),

-- 3) Células da CAPA: ordem, EPS, corte de SLA (2 = coluna M | 5 = coluna O),
--    média de interações plan (CAPA col. D) e tempo de atendimento plan (PLAN col. H)
celulas AS (
    SELECT * FROM VALUES
    ( 1, 'AEC', 'CX Suporte',                              5, 1.80, 288.8888889),
    ( 2, 'AEC', 'Madrugada',                               5, 1.89, 297.3544974),
    ( 3, 'AEC', 'CX Review - AeC',                         5, 2.05, 302.4390244),
    ( 4, 'CSU', 'CX Review - CSU',                         5, 2.05, 302.4390244),
    ( 5, 'AEC', 'CX Super Cliente - AeC',                  2, 1.73, 419.0751445),
    ( 6, 'CSU', 'CX Super Cliente - CSU',                  2, 1.73, 393.0635838),
    ( 7, 'CSU', 'PF Cancelamento',                         5, 1.23, 365.8536585),
    ( 8, 'CSU', 'PF Super Clientes',                       5, 1.23, 325.2032520),  -- trocar para 2 se entrar na regra "super"
    ( 9, 'CSU', 'PF Revisão Manual',                       5, 1.27, 322.8346457),
    (10, 'CSU', 'CX Denúncia',                             5, 1.00, 540.0000000),
    (11, 'CSU', 'Fraudes DX',                              5, 1.00, 550.0000000),
    (12, 'CSU', 'DX - PF Contestação',                     5, 1.00,        NULL),
    (13, 'CSU', 'DX - PF Contestação Bloqueio temporário', 5, 1.00,        NULL),
    (14, 'AEC', 'Fila desativada 37 - Canarinhos',         5, 1.00,        NULL)
    AS t(ordem, eps, celula_capa, corte_sla_min, media_interacoes_plan, tempo_atendimento_plan)
),

-- 4) Plano diário de ticket único (aba PLAN col. D), 01 a 30/11 — 1 valor por dia, na ordem
plano_ticket AS (
    SELECT * FROM VALUES
    ('CX Suporte'            , ARRAY(8665, 6057, 5606, 5926, 5752, 7489, 7868, 8630, 5691, 5264, 5516, 5475, 7302, 7412, 8113, 5597, 5153, 5347, 5328, 6780, 7145, 7946, 5318, 4954, 5024, 5236, 8486, 9802, 10894, 7057)),
    ('Madrugada'             , ARRAY(761, 578, 553, 580, 563, 669, 678, 700, 540, 516, 539, 529, 638, 633, 654, 534, 509, 529, 520, 610, 619, 645, 509, 488, 501, 504, 723, 802, 826, 671)),
    ('CX Review - AeC'       , ARRAY(2563, 2171, 2152, 2243, 2176, 2309, 2223, 2084, 2009, 1991, 2074, 2013, 2134, 2056, 1927, 2003, 1984, 2068, 2005, 2126, 2048, 1920, 1912, 1894, 1972, 1913, 2256, 2349, 2083, 2505)),
    ('CX Review - CSU'       , ARRAY(1381, 1169, 1159, 1208, 1172, 1243, 1197, 1123, 1082, 1072, 1117, 1084, 1149, 1107, 1038, 1079, 1068, 1113, 1080, 1144, 1102, 1034, 1030, 1020, 1062, 1030, 1214, 1265, 1121, 1349)),
    ('CX Super Cliente - AeC', ARRAY(1036, 837, 786, 844, 826, 886, 904, 847, 792, 744, 798, 781, 837, 856, 801, 811, 764, 820, 802, 860, 880, 821, 777, 732, 785, 770, 1063, 1139, 932, 820)),
    ('CX Super Cliente - CSU', ARRAY(1924, 1556, 1459, 1567, 1534, 1646, 1679, 1572, 1471, 1380, 1481, 1451, 1556, 1589, 1487, 1507, 1419, 1522, 1491, 1595, 1634, 1524, 1443, 1358, 1457, 1428, 1975, 2117, 1731, 1525)),
    ('PF Cancelamento'       , ARRAY(3116, 2510, 2368, 2156, 2226, 2397, 2702, 2530, 2482, 2340, 2130, 2198, 2367, 2669, 2497, 2431, 2291, 2086, 2153, 2318, 2613, 2445, 2552, 2405, 2189, 2259, 3015, 3674, 3641, 3169)),
    ('PF Super Clientes'     , ARRAY(985, 870, 870, 897, 878, 940, 1013, 805, 859, 859, 885, 866, 927, 1000, 794, 868, 868, 895, 875, 937, 1010, 802, 927, 926, 954, 933, 1238, 1443, 1215, 1213)),
    ('PF Revisão Manual'     , ARRAY(559, 430, 406, 408, 409, 456, 476, 447, 381, 359, 361, 361, 403, 421, 395, 390, 368, 370, 370, 413, 432, 405, 432, 407, 410, 410, 457, 478, 448, 460)),
    ('CX Denúncia'           , ARRAY(1951, 1286, 1219, 1246, 1278, 1398, 1549, 1617, 1255, 1136, 1230, 1183, 1274, 1445, 1485, 1263, 1194, 1226, 1197, 1280, 1388, 1464, 1213, 1134, 1249, 1219, 1268, 1400, 1456, 1251)),
    ('Fraudes DX'            , ARRAY(1711, 1047, 946, 1057, 1169, 1378, 1392, 1386, 993, 935, 965, 993, 1142, 1411, 1489, 966, 941, 940, 1051, 1079, 1464, 1378, 932, 834, 1002, 1111, 1248, 1235, 1408, 961))
    AS t(celula_capa, tickets_dia)
),

-- 5) Plano acumulado até data_fim (D-1): interações plan = ticket único x média de interações
plano_celula AS (
    SELECT
        pt.celula_capa,
        SUM(e.ticket) AS ticket_unico_plan
    FROM plano_ticket pt
    CROSS JOIN parametros p
    LATERAL VIEW POSEXPLODE(pt.tickets_dia) e AS pos, ticket
    WHERE DATE_ADD(DATE'{mes_plano}-01', e.pos) BETWEEN p.data_inicio AND p.data_fim
    GROUP BY pt.celula_capa
),

-- 6) Realizado por célula
real_celula AS (
    SELECT
        dp.celula_capa,
        SUM(f.entradas)              AS entradas,
        SUM(f.tratados)              AS tratados,
        SUM(f.casos_unicos)          AS casos_unicos,
        SUM(f.soma_tempo_atribuicao) AS soma_tempo_atribuicao,
        SUM(f.soma_tempo_interacao)  AS soma_tempo_interacao,
        SUM(f.sla_i_dentro_2min)     AS sla_i_dentro_2min,
        SUM(f.sla_i_dentro_3min)     AS sla_i_dentro_3min,
        SUM(f.sla_i_dentro_5min)     AS sla_i_dentro_5min,
        SUM(f.sla_i_dentro_8min)     AS sla_i_dentro_8min,
        SUM(f.sla_i_dentro_10min)    AS sla_i_dentro_10min,
        SUM(f.sla_i_base)            AS sla_i_base,
        SUM(f.sla_r_dentro_10min)    AS sla_r_dentro_10min,
        SUM(f.sla_r_base)            AS sla_r_base
    FROM por_fila f
    JOIN de_para dp
      ON CONCAT(f.fila, f.fila_oficial) = dp.chave
    GROUP BY dp.celula_capa
),

-- 7) Indicadores (mesmas fórmulas da CAPA de novembro)
capa AS (
    SELECT
        c.ordem, c.eps, c.celula_capa, c.corte_sla_min,
        c.media_interacoes_plan,
        r.entradas / NULLIF(r.casos_unicos, 0)                           AS media_interacoes_real,
        pc.ticket_unico_plan * c.media_interacoes_plan                    AS interacoes_plan,
        r.entradas                                                        AS interacoes_real,
        r.tratados                                                        AS interacoes_tratadas,
        c.tempo_atendimento_plan,
        r.soma_tempo_interacao  / NULLIF(r.tratados, 0)                   AS tempo_interacao,
        r.soma_tempo_atribuicao / NULLIF(r.tratados, 0)                   AS tempo_atribuicao,
        r.sla_i_dentro_2min  / NULLIF(r.sla_i_base, 0)                    AS sla_2min,
        r.sla_i_dentro_3min  / NULLIF(r.sla_i_base, 0)                    AS sla_3min,
        r.sla_i_dentro_5min  / NULLIF(r.sla_i_base, 0)                    AS sla_5min,
        r.sla_i_dentro_8min  / NULLIF(r.sla_i_base, 0)                    AS sla_8min,
        r.sla_i_dentro_10min / NULLIF(r.sla_i_base, 0)                    AS sla_10min,
        r.sla_r_dentro_10min / NULLIF(r.sla_r_base, 0)                    AS sla_resolucao,
        pc.ticket_unico_plan,
        r.casos_unicos                                                    AS ticket_unico_real,
        r.soma_tempo_atribuicao / NULLIF(r.casos_unicos, 0)               AS tempo_atribuicao_ticket,
        r.soma_tempo_atribuicao,
        r.sla_i_base,
        CASE WHEN c.corte_sla_min = 2 THEN r.sla_i_dentro_2min ELSE r.sla_i_dentro_5min END AS sla_dentro_corte
    FROM celulas c
    LEFT JOIN real_celula  r  ON r.celula_capa  = c.celula_capa
    LEFT JOIN plano_celula pc ON pc.celula_capa = c.celula_capa
)

SELECT
    eps                                                                 AS `EPS`,
    celula_capa                                                         AS `CÉLULA`,
    CAST(ROUND(media_interacoes_plan, 2) AS DOUBLE)                                     AS `MÉDIA INTERAÇÕES PLAN`,
    CAST(ROUND(media_interacoes_real, 2) AS DOUBLE)                                     AS `MÉDIA INTERAÇÕES REAL`,
    CAST(ROUND(interacoes_plan, 0) AS DOUBLE)                                           AS `INTERAÇÕES PLAN`,
    CAST(interacoes_real AS DOUBLE)                                                     AS `INTERAÇÕES REAL`,
    CAST(interacoes_tratadas AS DOUBLE)                                                 AS `INTERAÇÕES TRATADAS`,
    CAST(ROUND(interacoes_real / NULLIF(interacoes_plan, 0) - 1, 4) AS DOUBLE)          AS `INTERAÇÕES DESVIO`,
    CAST(ROUND(tempo_atendimento_plan, 0) AS DOUBLE)                                    AS `TEMPO ATENDIMENTO PLAN`,
    CAST(ROUND(tempo_interacao, 0) AS DOUBLE)                                           AS `TEMPO INTERAÇÃO`,
    CAST(ROUND(tempo_atribuicao, 0) AS DOUBLE)                                          AS `TEMPO ATRIBUIÇÃO`,
    CAST(ROUND(sla_2min, 4) AS DOUBLE)                                                  AS `SLA 2 MIN`,
    CAST(ROUND(sla_3min, 4) AS DOUBLE)                                                  AS `SLA 3 MIN`,
    CAST(ROUND(sla_5min, 4) AS DOUBLE)                                                  AS `SLA 5 MIN`,
    CAST(ROUND(sla_8min, 4) AS DOUBLE)                                                  AS `SLA 8 MIN`,
    CAST(ROUND(sla_10min, 4) AS DOUBLE)                                                 AS `SLA 10 MIN`,
    CONCAT(corte_sla_min, ' min')                                       AS `CORTE SLA`,
    CAST(ROUND(CASE WHEN corte_sla_min = 2 THEN sla_2min ELSE sla_5min END, 4) AS DOUBLE) AS `SLA`,
    CAST(ROUND(sla_resolucao, 4) AS DOUBLE)                                             AS `SLA RESOLUÇÃO`,
    CAST(ROUND(ticket_unico_plan, 0) AS DOUBLE)                                         AS `TICKET ÚNICO PLAN`,
    CAST(ticket_unico_real AS DOUBLE)                                                   AS `TICKET ÚNICO REAL`,
    CAST(ROUND(ticket_unico_real / NULLIF(ticket_unico_plan, 0) - 1, 4) AS DOUBLE)      AS `TICKET ÚNICO DESVIO`,
    CAST(ROUND(tempo_atendimento_plan * media_interacoes_plan, 0) AS DOUBLE)            AS `TEMPO ATENDIMENTO PLAN (TICKET)`,
    CAST(ROUND(tempo_atribuicao_ticket, 0) AS DOUBLE)                                   AS `TEMPO ATRIBUIÇÃO (TICKET)`,
    CAST(soma_tempo_atribuicao AS DOUBLE)                                               AS `SOMA TEMPO ATRIBUIÇÃO`,
    CAST(sla_i_base AS DOUBLE)                                                          AS `SLA BASE`,
    CAST(sla_dentro_corte AS DOUBLE)                                                    AS `SLA DENTRO`
FROM capa
ORDER BY ordem;
