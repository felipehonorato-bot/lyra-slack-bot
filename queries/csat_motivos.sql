-- CSAT por fila e motivo de contato. O app calcula o impacto do motivo (seção 6 da Indicadores):
-- participação do motivo nas avaliações da fila × (CSAT do motivo − CSAT da fila). Parâmetros: {data_inicio}, {data_fim}, {eps_lista}.
{base}
SELECT eps_fila AS `EPS`, fila_relatorio AS `FILA`, COALESCE(motivo, 'sem motivo') AS `MOTIVO`,
       COUNT(*) AS `AVALIACOES`, SUM(CASE WHEN nota IN (4, 5) THEN 1 ELSE 0 END) AS `PROMOTORAS`
FROM filas
WHERE eps_fila IN ({eps_lista})
GROUP BY eps_fila, fila_relatorio, COALESCE(motivo, 'sem motivo')
ORDER BY eps_fila, fila_relatorio
