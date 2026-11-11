-- CSAT por operador e fila + total de cada fila (consulta fixa do catálogo). O app calcula CSAT, meta da fila e o
-- impacto de cada operador no consolidado: peso dele nas avaliações do conjunto × (CSAT dele − meta da fila), somando
-- as filas em que ele atendeu. Supervisor = soma dos operadores dele (MOP). Linhas EMAIL = 'TOTAL' trazem o total de
-- cada fila (todos os tickets da fila, qualquer e-mail), que é a base do consolidado.
-- Parâmetros: {base_inicio}, {base_fim}, {lista_madrugada}, {eps_lista}, {eps_like}, {filtro_operadores}.
{base},
escopo AS (
    SELECT * FROM filas WHERE eps_fila IN ({eps_lista})
),
por_op_fila AS (
    SELECT eps_fila AS eps, agente_email AS email, fila_relatorio AS fila,
           COUNT(*) AS aval, SUM(CASE WHEN nota IN (4, 5) THEN 1 ELSE 0 END) AS prom
    FROM escopo
    WHERE agente_email RLIKE '{eps_like}' AND {filtro_operadores}
    GROUP BY eps_fila, agente_email, fila_relatorio
),
tot_fila AS (
    SELECT eps_fila AS eps, 'TOTAL' AS email, fila_relatorio AS fila,
           COUNT(*) AS aval, SUM(CASE WHEN nota IN (4, 5) THEN 1 ELSE 0 END) AS prom
    FROM escopo
    GROUP BY eps_fila, fila_relatorio
)
SELECT eps AS `EPS`, email AS `EMAIL`, fila AS `FILA`, aval AS `AVALIACOES`, prom AS `PROMOTORAS`
FROM (SELECT * FROM tot_fila UNION ALL SELECT * FROM por_op_fila) t
ORDER BY eps, fila, email
