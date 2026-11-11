-- CSAT dia a dia por fila (consulta fixa do catálogo): mesma base oficial do report (csat_base.sql), dia = data da
-- avaliação (csat_timestamp − 3h). O app soma as filas para o consolidado e compara com a meta de cada fila.
-- Parâmetros: {base_inicio}, {base_fim}, {lista_madrugada}, {eps_lista}, {filtro_fila}.
{base}
SELECT eps_fila AS `EPS`, fila_relatorio AS `FILA`, CAST(data_ref AS STRING) AS `DATA`, COUNT(*) AS `AVALIACOES`,
       SUM(CASE WHEN nota IN (4, 5) THEN 1 ELSE 0 END) AS `PROMOTORAS`
FROM filas
WHERE eps_fila IN ({eps_lista}) AND {filtro_fila}
GROUP BY eps_fila, fila_relatorio, CAST(data_ref AS STRING)
ORDER BY 1, 3, 2
