-- Variação do CSAT entre dois períodos por motivo (seção 7.2 da Indicadores): o app calcula efeito mix
-- (Σ (share atual − share ref) × CSAT ref do motivo) e efeito performance (Σ share atual × (CSAT atual − CSAT ref do motivo)).
-- Parâmetros: {ref_inicio}, {ref_fim}, {cur_inicio}, {cur_fim}, {eps_lista}, {filtro_fila}.
{base}
SELECT
    CASE WHEN data_ref BETWEEN DATE'{cur_inicio}' AND DATE'{cur_fim}' THEN 'atual'
         WHEN data_ref BETWEEN DATE'{ref_inicio}' AND DATE'{ref_fim}' THEN 'ref' END AS `PERIODO`,
    eps_fila AS `EPS`, fila_relatorio AS `FILA`, COALESCE(motivo, 'sem motivo') AS `MOTIVO`,
    COUNT(*) AS `AVALIACOES`, SUM(CASE WHEN nota IN (4, 5) THEN 1 ELSE 0 END) AS `PROMOTORAS`
FROM filas
WHERE eps_fila IN ({eps_lista}) AND {filtro_fila}
  AND (data_ref BETWEEN DATE'{cur_inicio}' AND DATE'{cur_fim}' OR data_ref BETWEEN DATE'{ref_inicio}' AND DATE'{ref_fim}')
GROUP BY 1, eps_fila, fila_relatorio, COALESCE(motivo, 'sem motivo')
