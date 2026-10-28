"""Leitura dos postos direto do banco PostgreSQL (junta as 6 tabelas em uma só visão)."""
import pandas as pd
from sqlalchemy import text
from load import criar_engine

CONSULTA = """
SELECT p.cnpj, p.cnpj_raiz, emp.razao_social, u.sigla AS uf, m.nome AS municipio,
       b.nome AS bandeira, p.bandeira_original, p.tipo_autorizacao,
       p.flag_inconsistente, p.motivo_inconsistencia
FROM posto p
JOIN empresa emp ON emp.cnpj_raiz = p.cnpj_raiz
JOIN endereco e ON e.id = p.endereco_id
JOIN municipio m ON m.id = e.municipio_id
JOIN uf u ON u.id = m.uf_id
LEFT JOIN bandeira b ON b.id = p.bandeira_id
"""


def carregar_postos():
    df = pd.read_sql(text(CONSULTA), criar_engine())
    df["flag_inconsistente"] = df["flag_inconsistente"].astype(bool)
    return df
