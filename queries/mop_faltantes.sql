-- Quem atendeu na semana e não está no MOP (cobrança semanal do MOP). O app manda os usuários de e-mail que estão
-- no MOP de cada EPS; volta só quem atendeu e não está lá (lista pequena).
-- Parâmetros: {data_inicio}, {data_fim}, {eps_like}, {mop_values}, {min_tratados}.
WITH mop AS (
    SELECT explode(split(users, '[|]')) AS u FROM VALUES {mop_values} AS t(users)
),
base AS (
    SELECT CASE WHEN lower(e_mail) LIKE '%aec%' THEN 'AeC' ELSE 'CSU' END AS eps,
           split(lower(e_mail), '@')[0] AS usuario, lower(e_mail) AS email,
           COUNT(*) AS tratados, MAX(DATE(timestamp_assigned)) AS ultimo
    FROM cx_gci_bi.entradas_filas
    WHERE pilar IN ('CX', 'DX') AND timestamp_assigned IS NOT NULL
      AND DATE(timestamp_assigned) BETWEEN DATE'{data_inicio}' AND DATE'{data_fim}'
      AND e_mail IS NOT NULL AND lower(e_mail) RLIKE '{eps_like}'
    GROUP BY 1, 2, 3
)
SELECT eps AS `EPS`, email AS `EMAIL`, tratados AS `TRATADOS`, CAST(ultimo AS STRING) AS `ULTIMO_DIA`
FROM base
WHERE usuario NOT IN (SELECT u FROM mop) AND tratados >= {min_tratados}
ORDER BY eps, tratados DESC
