-- ============================================================
-- VALIDACAO DO BANCO (rodar depois da carga com load.py)
-- Compara o banco com o CSV tratado e com os arquivos da pasta resultados/.
-- No pgAdmin: selecione UMA consulta por vez e aperte F5.
-- ============================================================

-- 1) Contagem por tabela
--    esperado: uf 27 | municipio 5525 | bairro 27260 | empresa 38728 | endereco 45773 | posto 45773
--    (bandeira: 64 menos os sinonimos agrupados pelo dicionario)
SELECT 'uf' AS tabela, COUNT(*) AS total FROM uf
UNION ALL SELECT 'municipio', COUNT(*) FROM municipio
UNION ALL SELECT 'bairro', COUNT(*) FROM bairro
UNION ALL SELECT 'bandeira', COUNT(*) FROM bandeira
UNION ALL SELECT 'bandeira_sinonimo', COUNT(*) FROM bandeira_sinonimo
UNION ALL SELECT 'empresa', COUNT(*) FROM empresa
UNION ALL SELECT 'endereco', COUNT(*) FROM endereco
UNION ALL SELECT 'posto', COUNT(*) FROM posto;

-- 2) Postos sem bandeira (esperado: 0)
SELECT COUNT(*) AS postos_sem_bandeira FROM posto WHERE bandeira_id IS NULL;

-- 3) Postos cuja raiz do CNPJ nao bate com o CNPJ (esperado: 0)
SELECT COUNT(*) AS raiz_diferente FROM posto WHERE SUBSTR(cnpj, 1, 8) <> cnpj_raiz;

-- 4) Postos inconsistentes (esperado: 273)
SELECT COUNT(*) AS inconsistentes FROM posto WHERE flag_inconsistente;

-- 5) Postos sem bairro (esperado: 124)
SELECT COUNT(*) AS sem_bairro
FROM posto p JOIN endereco e ON e.id = p.endereco_id
WHERE e.bairro_id IS NULL;

-- 6) Enderecos sem numero (esperado: 11461) e com KM (esperado: 6377)
SELECT SUM(CASE WHEN sem_numero THEN 1 ELSE 0 END) AS sem_numero,
       SUM(CASE WHEN km IS NOT NULL THEN 1 ELSE 0 END) AS com_km
FROM endereco;

-- 7) Maior rede (esperado: SIM REDE DE POSTOS LTDA, 213 postos)
SELECT e.razao_social, COUNT(*) AS postos
FROM posto p JOIN empresa e ON e.cnpj_raiz = p.cnpj_raiz
GROUP BY e.cnpj_raiz, e.razao_social
ORDER BY postos DESC
LIMIT 5;

-- 8) Total de postos por UF (confira com a contagem do CSV)
SELECT u.sigla, COUNT(*) AS postos
FROM posto p
JOIN endereco e ON e.id = p.endereco_id
JOIN municipio m ON m.id = e.municipio_id
JOIN uf u ON u.id = m.uf_id
GROUP BY u.sigla
ORDER BY postos DESC;

-- 9) HHI por rede em cada municipio (compare com resultados/hhi_por_rede.csv)
--    esperado: Flores da Cunha (RS) 2639 | Curitiba 42 | Sao Paulo 19 | Rio de Janeiro 17
WITH por_rede AS (
    SELECT e.municipio_id, p.cnpj_raiz, COUNT(*) AS postos
    FROM posto p JOIN endereco e ON e.id = p.endereco_id
    GROUP BY e.municipio_id, p.cnpj_raiz
),
com_total AS (
    SELECT municipio_id, postos, SUM(postos) OVER (PARTITION BY municipio_id) AS total
    FROM por_rede
)
SELECT u.sigla AS uf, m.nome AS municipio, MAX(c.total) AS total_postos,
       ROUND(SUM((c.postos * 100.0 / c.total) * (c.postos * 100.0 / c.total))) AS hhi
FROM com_total c
JOIN municipio m ON m.id = c.municipio_id
JOIN uf u ON u.id = m.uf_id
GROUP BY u.sigla, m.nome
HAVING MAX(c.total) >= 10
ORDER BY hhi DESC
LIMIT 10;

-- 10) Municipios so com bandeira branca (esperado: 1491)
--     Vale se 'BANDEIRA BRANCA' continuar com esse nome no dicionario de bandeiras.
SELECT COUNT(*) AS municipios_so_bandeira_branca
FROM (
    SELECT e.municipio_id
    FROM posto p
    JOIN endereco e ON e.id = p.endereco_id
    JOIN bandeira b ON b.id = p.bandeira_id
    GROUP BY e.municipio_id
    HAVING SUM(CASE WHEN b.nome = 'BANDEIRA BRANCA' THEN 0 ELSE 1 END) = 0
) t;

-- 11) Bandeiras e sinonimos aplicados (o que o dicionario unificou)
SELECT s.sinonimo, b.nome AS bandeira_canonica
FROM bandeira_sinonimo s JOIN bandeira b ON b.id = s.bandeira_id
ORDER BY b.nome, s.sinonimo;
