-- Quem mais pesa no CSAT (operador e supervisor), já agregado no SQL para a saída ficar pequena (~60 linhas).
-- Impacto = peso da pessoa nas avaliações do conjunto × (CSAT dela − meta da fila dela), em p.p.: por pessoa,
-- (promotoras − meta × avaliações) ÷ avaliações do conjunto × 100, somando as filas em que atendeu. Supervisor = soma
-- dos operadores dele (vínculo do MOP, mandado pelo app). Só sai o usuário do e-mail (parte antes do @).
-- Parâmetros: {base_inicio}, {base_fim}, {lista_madrugada}, {eps_lista}, {eps_like}, {filtro_fila}, {metas_values},
-- {mop_values}, {filtro_equipe}, {min_aval}, {top_ops}, {op_ini} (paginação da lista completa; padrão 1).
-- RK: na linha TOTAL, quantos entram no ranking; na linha OP, a posição (1 = quem mais puxa para baixo).
{base},
metas AS (
    SELECT fila, CAST(meta AS DOUBLE) AS meta FROM VALUES {metas_values} AS t(fila, meta)
),
mop AS (
    SELECT sup, u FROM (SELECT sup, explode(split(users, '[|]')) AS u FROM VALUES {mop_values} AS t(sup, users))
),
escopo AS (
    SELECT f.*, split(agente_email, '@')[0] AS usuario, CASE WHEN nota IN (4, 5) THEN 1 ELSE 0 END AS promotora
    FROM filas f
    WHERE eps_fila IN ({eps_lista}) AND {filtro_fila}
),
tot AS (   -- o conjunto (EPS ou fila): todos os tickets, qualquer e-mail
    SELECT e.eps_fila AS eps, COUNT(*) AS n, SUM(e.promotora) AS prom,
           SUM(CASE WHEN m.meta IS NOT NULL THEN 1 ELSE 0 END) AS n_meta, SUM(m.meta) AS meta_x
    FROM escopo e LEFT JOIN metas m ON m.fila = e.fila_relatorio
    GROUP BY e.eps_fila
),
op_fila AS (
    SELECT eps_fila AS eps, usuario, fila_relatorio AS fila, COUNT(*) AS aval, SUM(promotora) AS prom
    FROM escopo
    WHERE agente_email RLIKE '{eps_like}'
    GROUP BY eps_fila, usuario, fila_relatorio
),
op AS (
    SELECT o.eps, o.usuario, MAX_BY(o.fila, o.aval) AS fila, SUM(o.aval) AS aval, SUM(o.prom) AS prom,
           SUM(CASE WHEN m.meta IS NOT NULL THEN o.prom - m.meta / 100 * o.aval ELSE 0 END) AS acima,
           SUM(CASE WHEN m.meta IS NOT NULL THEN o.aval ELSE 0 END) AS aval_meta,
           SUM(CASE WHEN m.meta IS NOT NULL THEN m.meta * o.aval ELSE 0 END) AS meta_x
    FROM op_fila o LEFT JOIN metas m ON m.fila = o.fila
    GROUP BY o.eps, o.usuario
),
pessoas AS (
    SELECT op.*, COALESCE(mp.sup, 'Sem supervisor no MOP') AS sup, op.acima / t.n * 100 AS imp
    FROM op JOIN tot t ON t.eps = op.eps LEFT JOIN mop mp ON mp.u = op.usuario
    WHERE {filtro_equipe}
),
sups AS (
    SELECT p.eps, p.sup, COUNT(*) AS n_ops, SUM(p.aval) AS aval, SUM(p.prom) AS prom, SUM(p.acima) AS acima,
           SUM(p.aval_meta) AS aval_meta, SUM(p.meta_x) AS meta_x, SUM(p.acima) / MAX(t.n) * 100 AS imp
    FROM pessoas p JOIN tot t ON t.eps = p.eps
    GROUP BY p.eps, p.sup
),
sem_mop AS (   -- amostra de quem atendeu e não está no MOP de hoje (para o time corrigir o MOP)
    SELECT * FROM pessoas WHERE sup = 'Sem supervisor no MOP'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY eps ORDER BY aval DESC) <= 8
),
elegiveis AS (   -- quem entra no ranking (o app usa o total para saber se a lista completa veio inteira)
    SELECT p.*, ROW_NUMBER() OVER (PARTITION BY eps ORDER BY imp ASC) AS rk,
           ROW_NUMBER() OVER (PARTITION BY eps ORDER BY imp DESC) AS rk_desc
    FROM pessoas p
    WHERE aval >= {min_aval} AND aval_meta > 0
),
ops_rank AS (
    SELECT * FROM elegiveis WHERE rk BETWEEN {op_ini} AND {top_ops} OR rk_desc <= 3
),
n_rank AS (SELECT eps, COUNT(*) AS n FROM elegiveis GROUP BY eps)
SELECT 'TOTAL' AS `TIPO`, t.eps AS `EPS`, '' AS `NOME`, '' AS `FILA`, t.n AS `AVALIACOES`, t.prom AS `PROMOTORAS`,
       CAST(NULL AS DOUBLE) AS `ACIMA`, t.n_meta AS `AVAL_META`, t.meta_x AS `META_X`, CAST(NULL AS BIGINT) AS `N_OPS`,
       CAST(NULL AS DOUBLE) AS `IMPACTO_PP`, CAST(COALESCE(r.n, 0) AS BIGINT) AS `RK`
FROM tot t LEFT JOIN n_rank r ON r.eps = t.eps
UNION ALL
SELECT 'FORA', eps, '', '', NULL, NULL, NULL, NULL, NULL, COUNT(*), NULL, NULL
FROM pessoas WHERE aval < {min_aval} GROUP BY eps
UNION ALL
SELECT 'SUP', eps, sup, '', aval, prom, acima, aval_meta, meta_x, n_ops, imp, NULL FROM sups
UNION ALL
SELECT 'OP', eps, usuario, fila, aval, prom, acima, aval_meta, meta_x, 1, imp, rk FROM ops_rank
UNION ALL
SELECT 'SEMMOP', eps, usuario, fila, aval, prom, NULL, NULL, NULL, 1, NULL, NULL FROM sem_mop
