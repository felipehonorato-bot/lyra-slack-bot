-- Quem mais pesa no TMA (analista e supervisor), regra da seção 7.1d da Lyra Indicadores, já agregado no SQL.
-- TMA do analista = Σ tempo de atribuição com ele ÷ tickets distintos dele (o ticket conta para cada analista que o
-- atendeu). Impacto = TMA do conjunto − TMA do conjunto sem a pessoa (ou sem a equipe inteira), em segundos.
-- Positivo = puxa o TMA para cima. Supervisor pelo vínculo do MOP (mandado pelo app). Só o usuário do e-mail.
-- Parâmetros: {data_inicio}, {data_fim}, {eps_like}, {filtro_fila}, {mop_values}, {filtro_equipe}, {min_tickets}, {top_ops}.
WITH base AS (
    SELECT lower(e.e_mail) AS email, e.support_ticket_id, e.queue_name,
           CAST(e.tempo_atribuicao_com_operador AS DOUBLE) AS tempo
    FROM cx_gci_bi.entradas_filas e
    WHERE e.pilar IN ('CX', 'DX')
      AND e.timestamp_assigned IS NOT NULL
      AND DATE(e.timestamp_assigned) BETWEEN DATE'{data_inicio}' AND DATE'{data_fim}'
      AND e.e_mail IS NOT NULL AND lower(e.e_mail) RLIKE '{eps_like}'
),
celula AS (   -- DE PARA da fila para a célula (o mesmo do TMA oficial, ramo diurno)
    SELECT b.*,
        CASE WHEN b.email LIKE '%aec%' THEN 'AeC' ELSE 'CSU' END AS eps,
        split(b.email, '@')[0] AS usuario,
        CASE
            WHEN b.queue_name IN ('Arbitragem', 'Food delivery', 'Groceries', 'Pós Entrega', 'Retroalimentação',
                                  'CX Problemas com a entrega', 'Teste Oráculo', 'TesteAtendimentoOráculo', 'CX Suporte') THEN 'CX Suporte'
            WHEN b.queue_name IN ('CX Review - AeC', 'CX Review - CSU', 'CX Super Cliente - AeC', 'CX Super Cliente - CSU',
                                  'CX Denúncia') THEN b.queue_name
            WHEN b.queue_name IN ('PF Cancelamento Food', 'PF Cancelamento Multi', 'PF Cancelamento') THEN 'PF Cancelamento'
            WHEN b.queue_name IN ('PF Clube Vip + Super clientes', 'PF Clube Vip + Super clientes Medicament') THEN 'PF Super Clientes'
            WHEN b.queue_name = 'PF Revisão Manual (Multi + Food)' THEN 'PF Revisão Manual'
            WHEN b.queue_name = 'DX - PF' THEN 'Fraudes DX'
        END AS fila
    FROM base b
),
mop AS (
    SELECT sup, u FROM (SELECT sup, explode(split(users, '[|]')) AS u FROM VALUES {mop_values} AS t(sup, users))
),
escopo AS (
    SELECT * FROM celula WHERE fila IS NOT NULL AND {filtro_fila}
),
op AS (
    SELECT eps, usuario, COUNT(*) AS tratados, COUNT(DISTINCT support_ticket_id) AS tickets, SUM(tempo) AS tempo
    FROM escopo GROUP BY eps, usuario
),
fila_op AS (
    SELECT eps, usuario, fila FROM (
        SELECT eps, usuario, fila, ROW_NUMBER() OVER (PARTITION BY eps, usuario ORDER BY COUNT(*) DESC) AS rn
        FROM escopo GROUP BY eps, usuario, fila
    ) WHERE rn = 1
),
tot AS (
    SELECT eps, SUM(tratados) AS tratados, SUM(tickets) AS tickets, SUM(tempo) AS tempo, COUNT(*) AS n_ops
    FROM op GROUP BY eps
),
pessoas AS (
    SELECT o.*, f.fila, COALESCE(mp.sup, 'Sem supervisor no MOP') AS sup
    FROM op o JOIN fila_op f ON f.eps = o.eps AND f.usuario = o.usuario
    LEFT JOIN mop mp ON mp.u = o.usuario
    WHERE {filtro_equipe}
),
por_fila AS (   -- TMA da fila pela mesma régua (soma dos analistas da fila)
    SELECT eps, fila, SUM(tempo) / NULLIF(SUM(tickets), 0) AS tma_fila FROM pessoas GROUP BY eps, fila
),
sups AS (
    SELECT p.eps, p.sup, COUNT(*) AS n_ops, SUM(p.tratados) AS tratados, SUM(p.tickets) AS tickets, SUM(p.tempo) AS tempo,
           MAX(t.tempo / t.tickets) - (MAX(t.tempo) - SUM(p.tempo)) / NULLIF(MAX(t.tickets) - SUM(p.tickets), 0) AS impacto
    FROM pessoas p JOIN tot t ON t.eps = p.eps
    GROUP BY p.eps, p.sup
),
imp AS (
    SELECT p.*, t.tempo / t.tickets - (t.tempo - p.tempo) / NULLIF(t.tickets - p.tickets, 0) AS impacto, pf.tma_fila
    FROM pessoas p JOIN tot t ON t.eps = p.eps JOIN por_fila pf ON pf.eps = p.eps AND pf.fila = p.fila
    WHERE p.tickets >= {min_tickets}
),
ranked AS (
    SELECT * FROM imp
    QUALIFY ROW_NUMBER() OVER (PARTITION BY eps ORDER BY impacto DESC) <= {top_ops}
         OR ROW_NUMBER() OVER (PARTITION BY eps ORDER BY impacto ASC) <= 3
)
SELECT 'TOTAL' AS `TIPO`, eps AS `EPS`, '' AS `NOME`, '' AS `FILA`, tratados AS `TRATADOS`, tickets AS `TICKETS`,
       tempo AS `TEMPO`, n_ops AS `N_OPS`, CAST(NULL AS DOUBLE) AS `IMPACTO_S`, CAST(NULL AS DOUBLE) AS `TMA_FILA_S`
FROM tot
UNION ALL
SELECT 'FORA', eps, '', '', NULL, NULL, NULL, COUNT(*), NULL, NULL FROM pessoas WHERE tickets < {min_tickets} GROUP BY eps
UNION ALL
SELECT 'SUP', eps, sup, '', tratados, tickets, tempo, n_ops, impacto, NULL FROM sups
UNION ALL
SELECT 'OP', eps, usuario, fila, tratados, tickets, tempo, 1, impacto, tma_fila FROM ranked
