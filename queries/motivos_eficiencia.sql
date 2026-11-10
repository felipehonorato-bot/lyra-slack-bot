-- Motivos de contato que mais pesam no TMA e no SLA de 1ª resposta, por célula da CAPA.
-- Mesma base, madrugada, DE PARA, corte de SLA e faixas da visão da CAPA (queries/capa.sql). O app troca {data_inicio} e {data_fim}.
-- Impacto no TMA (horas de operação) = tratados do motivo × (tempo de atribuição por interação do motivo − o da célula) ÷ 3600
--   (tempo de atribuição enquanto o tmi estiver zerado).
-- Impacto no SLA (interações) = fora do prazo do motivo − interações do motivo × taxa fora do prazo da célula.
-- Corte: 2 min na CX Super Cliente AeC/CSU, 5 min nas demais. Positivo = o motivo pesa contra a célula.
WITH parametros AS (
    SELECT DATE'{data_inicio}' AS data_inicio,
           LEAST(DATE'{data_fim}', DATE_SUB(CURRENT_DATE(), 1)) AS data_fim
),
base AS (
    SELECT
        t1.queue_name AS fila,
        CASE
            WHEN EXTRACT(HOUR FROM t1.timestamp) BETWEEN 2 AND 7
                 AND (EXTRACT(HOUR FROM t1.timestamp) != 2 OR EXTRACT(MINUTE FROM t1.timestamp) >= 30)
                 AND (EXTRACT(HOUR FROM t1.timestamp) != 7 OR EXTRACT(MINUTE FROM t1.timestamp) <= 30)
            THEN 'célula da madrugada'
            ELSE t1.queue_name
        END AS fila_oficial,
        COALESCE(t1.support_contact_reason, 'sem motivo') AS motivo,
        CASE WHEN t1.timestamp_assigned IS NOT NULL
                  AND DATE(t1.timestamp_assigned) BETWEEN p.data_inicio AND p.data_fim THEN 1 ELSE 0 END AS tratado,
        CASE WHEN t1.timestamp_assigned IS NOT NULL
                  AND DATE(t1.timestamp_assigned) BETWEEN p.data_inicio AND p.data_fim
             THEN t1.tempo_atribuicao_com_operador END AS tempo,
        t1.time_to_first_answer AS ttfa
    FROM cx_gci_bi.entradas_filas t1
    CROSS JOIN parametros p
    WHERE t1.pilar IN ('CX', 'DX')
        AND DATE(t1.timestamp) BETWEEN p.data_inicio AND p.data_fim
),
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
celulas AS (
    SELECT * FROM VALUES
    ('AEC', 'CX Suporte', 5), ('AEC', 'Madrugada', 5), ('AEC', 'CX Review - AeC', 5), ('CSU', 'CX Review - CSU', 5),
    ('AEC', 'CX Super Cliente - AeC', 2), ('CSU', 'CX Super Cliente - CSU', 2), ('CSU', 'PF Cancelamento', 5),
    ('CSU', 'PF Super Clientes', 5), ('CSU', 'PF Revisão Manual', 5), ('CSU', 'CX Denúncia', 5), ('CSU', 'Fraudes DX', 5),
    ('CSU', 'DX - PF Contestação', 5), ('CSU', 'DX - PF Contestação Bloqueio temporário', 5)
    AS t(eps, celula_capa, corte_sla_min)
),
faixas AS (
    SELECT b.*, CASE
            WHEN b.ttfa IS NULL THEN 'sem faixa'
            WHEN b.ttfa < 0 THEN 'Undefined'
            WHEN b.ttfa BETWEEN 0 AND 120 THEN '0-2min'
            WHEN b.ttfa BETWEEN 121 AND 180 THEN '2-3min'
            WHEN b.ttfa BETWEEN 181 AND 300 THEN '3-5min'
            WHEN b.ttfa BETWEEN 301 AND 480 THEN '5-8min'
            WHEN b.ttfa BETWEEN 481 AND 600 THEN '8-10min'
            WHEN b.ttfa BETWEEN 601 AND 1800 THEN '10-30min'
            WHEN b.ttfa BETWEEN 1801 AND 3600 THEN '30-1hr'
            WHEN b.ttfa > 3600 THEN '+1hr'
        END AS faixa
    FROM base b
),
por_motivo AS (
    SELECT
        c.eps, dp.celula_capa AS celula, f.motivo, c.corte_sla_min,
        SUM(f.tratado) AS tratados,
        SUM(COALESCE(f.tempo, 0)) AS tempo,
        SUM(CASE WHEN f.faixa IN ('0-2min','2-3min','3-5min','5-8min','8-10min','10-30min','30-1hr','+1hr') THEN 1 ELSE 0 END) AS sla_base,
        SUM(CASE WHEN c.corte_sla_min = 2 AND f.faixa = '0-2min' THEN 1
                 WHEN c.corte_sla_min = 5 AND f.faixa IN ('0-2min','2-3min','3-5min') THEN 1 ELSE 0 END) AS sla_dentro
    FROM faixas f
    JOIN de_para dp ON CONCAT(f.fila, f.fila_oficial) = dp.chave
    JOIN celulas c ON c.celula_capa = dp.celula_capa
    GROUP BY c.eps, dp.celula_capa, f.motivo, c.corte_sla_min
),
por_celula AS (
    SELECT celula, SUM(tratados) AS c_tratados, SUM(tempo) AS c_tempo, SUM(sla_base) AS c_base, SUM(sla_dentro) AS c_dentro
    FROM por_motivo GROUP BY celula
),
impacto AS (
    SELECT
        m.*,
        m.tempo / NULLIF(m.tratados, 0)                                         AS tma_motivo_s,
        c.c_tempo / NULLIF(c.c_tratados, 0)                                     AS tma_celula_s,
        (m.tempo - m.tratados * c.c_tempo / NULLIF(c.c_tratados, 0)) / 3600     AS impacto_tma_h,
        m.sla_dentro / NULLIF(m.sla_base, 0)                                    AS sla_motivo,
        c.c_dentro / NULLIF(c.c_base, 0)                                        AS sla_celula,
        (m.sla_base - m.sla_dentro) - m.sla_base * (1 - c.c_dentro / NULLIF(c.c_base, 0)) AS impacto_sla_fora,
        m.tratados / NULLIF(c.c_tratados, 0)                                    AS peso_tratados,
        m.sla_base / NULLIF(c.c_base, 0)                                        AS peso_sla
    FROM por_motivo m
    JOIN por_celula c ON c.celula = m.celula
)
SELECT
    eps AS `EPS`, celula AS `CÉLULA`, motivo AS `MOTIVO`,
    CAST(tratados AS DOUBLE) AS `TRATADOS`,
    CAST(ROUND(peso_tratados, 4) AS DOUBLE) AS `PESO TRATADOS`,
    CAST(ROUND(tma_motivo_s, 0) AS DOUBLE) AS `TEMPO ATRIBUIÇÃO MOTIVO`,
    CAST(ROUND(tma_celula_s, 0) AS DOUBLE) AS `TEMPO ATRIBUIÇÃO CÉLULA`,
    CAST(ROUND(impacto_tma_h, 1) AS DOUBLE) AS `IMPACTO TMA (H)`,
    CAST(sla_base AS DOUBLE) AS `INTERAÇÕES SLA`,
    CAST(ROUND(peso_sla, 4) AS DOUBLE) AS `PESO SLA`,
    CAST(ROUND(sla_motivo, 4) AS DOUBLE) AS `SLA MOTIVO`,
    CAST(ROUND(sla_celula, 4) AS DOUBLE) AS `SLA CÉLULA`,
    CONCAT(corte_sla_min, ' min') AS `CORTE SLA`,
    CAST(ROUND(impacto_sla_fora, 0) AS DOUBLE) AS `IMPACTO SLA (FORA)`
FROM impacto
WHERE eps IN ({eps_lista})
QUALIFY ROW_NUMBER() OVER (PARTITION BY celula ORDER BY impacto_tma_h DESC) <= 5
     OR ROW_NUMBER() OVER (PARTITION BY celula ORDER BY impacto_sla_fora DESC) <= 5
ORDER BY celula, impacto_tma_h DESC
