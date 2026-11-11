-- Por que o TMA ou o SLA de 1ª resposta mudou: efeito mix x efeito performance por motivo de contato (mesma lógica da
-- variação do CSAT). Mesma base, madrugada, DE PARA, corte de SLA e faixas da CAPA (queries/motivos_eficiencia.sql).
-- O app calcula: TMA por interação = Σ tempo ÷ Σ tratados; SLA = Σ dentro ÷ Σ interações com 1ª resposta medida.
-- Mix = Σ (participação atual − participação ref) × (valor ref do motivo − valor ref total);
-- Performance = Σ participação atual × (valor atual do motivo − valor ref do motivo). Mix + performance = variação total.
-- Parâmetros: {cur_inicio}, {cur_fim}, {ref_inicio}, {ref_fim}, {eps_lista}, {filtro_celula}, {por_celula} (true/false).
WITH parametros AS (
    SELECT LEAST(DATE'{ref_inicio}', DATE'{cur_inicio}') AS data_inicio,
           LEAST(GREATEST(DATE'{ref_fim}', DATE'{cur_fim}'), DATE_SUB(CURRENT_DATE(), 1)) AS data_fim
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
        t1.time_to_first_answer AS ttfa,
        CASE WHEN DATE(t1.timestamp) BETWEEN DATE'{cur_inicio}' AND DATE'{cur_fim}' THEN 'atual'
             WHEN DATE(t1.timestamp) BETWEEN DATE'{ref_inicio}' AND DATE'{ref_fim}' THEN 'ref' END AS periodo
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
        f.periodo, c.eps, CASE WHEN {por_celula} THEN dp.celula_capa ELSE c.eps END AS celula, f.motivo,
        SUM(f.tratado) AS tratados,
        SUM(COALESCE(f.tempo, 0)) AS tempo,
        SUM(CASE WHEN f.faixa IN ('0-2min','2-3min','3-5min','5-8min','8-10min','10-30min','30-1hr','+1hr') THEN 1 ELSE 0 END) AS sla_base,
        SUM(CASE WHEN c.corte_sla_min = 2 AND f.faixa = '0-2min' THEN 1
                 WHEN c.corte_sla_min = 5 AND f.faixa IN ('0-2min','2-3min','3-5min') THEN 1 ELSE 0 END) AS sla_dentro
    FROM faixas f
    JOIN de_para dp ON CONCAT(f.fila, f.fila_oficial) = dp.chave
    JOIN celulas c ON c.celula_capa = dp.celula_capa
    WHERE f.periodo IS NOT NULL AND c.eps IN ({eps_lista}) AND {filtro_celula}
    GROUP BY f.periodo, c.eps, CASE WHEN {por_celula} THEN dp.celula_capa ELSE c.eps END, f.motivo
)
SELECT periodo AS `PERIODO`, eps AS `EPS`, celula AS `CELULA`, motivo AS `MOTIVO`,
       CAST(tratados AS DOUBLE) AS `TRATADOS`, CAST(tempo AS DOUBLE) AS `TEMPO`,
       CAST(sla_base AS DOUBLE) AS `SLA_BASE`, CAST(sla_dentro AS DOUBLE) AS `SLA_DENTRO`
FROM por_motivo
WHERE tratados > 0 OR sla_base > 0
ORDER BY periodo, celula, tratados DESC
