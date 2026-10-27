"""Carga do postos_limpo.csv no PostgreSQL (banco 'anp', criado com sql/schema.sql).

Como usar (PowerShell, na pasta do projeto, com o venv ativo):
    $env:DB_PASSWORD = "sua_senha_do_postgres"
    python src/load.py

Se existir data/bandeiras.csv (colunas sinonimo;bandeira_canonica), o dicionário de sinônimos
é aplicado. Sem ele, cada nome de bandeira fica como está (sem sinônimos).
"""
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text

CSV = "data/processed/postos_limpo.csv"
DICIONARIO = "data/bandeiras.csv"

NOMES_UF = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará",
    "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}


def criar_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        senha = os.environ.get("DB_PASSWORD")
        if not senha:
            sys.exit('Defina a senha antes: $env:DB_PASSWORD = "sua_senha"')
        url = "postgresql+psycopg2://{u}:{s}@{h}:{p}/{d}".format(
            u=os.environ.get("DB_USER", "postgres"), s=senha,
            h=os.environ.get("DB_HOST", "localhost"), p=os.environ.get("DB_PORT", "5432"),
            d=os.environ.get("DB_NAME", "anp"))
    return create_engine(url)


def limpar_tabelas(conn):
    """Esvazia tudo para poder rodar o script mais de uma vez."""
    tabelas = "posto, empresa, bandeira_sinonimo, bandeira, endereco, bairro, municipio, uf"
    if conn.dialect.name == "postgresql":
        conn.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    else:
        for t in tabelas.split(", "):
            conn.execute(text(f"DELETE FROM {t}"))


def inserir(conn, df, tabela):
    df.to_sql(tabela, conn, if_exists="append", index=False, method="multi", chunksize=1000)
    print(f"  {tabela}: {len(df)} linhas")


def vazio_para_none(serie):
    return serie.astype(object).where(serie.notna(), None)


def main():
    df = pd.read_csv(CSV, sep=";", dtype=str)
    df["sem_numero"] = df["sem_numero"] == "True"
    df["flag_inconsistente"] = df["flag_inconsistente"] == "True"
    for coluna in ["data_publicacao", "data_vinculacao"]:
        df[coluna] = vazio_para_none(pd.to_datetime(df[coluna], errors="coerce").dt.date)

    # dicionário de sinônimos de bandeira (opcional)
    if os.path.exists(DICIONARIO):
        dic = pd.read_csv(DICIONARIO, sep=";", dtype=str).dropna()
        mapa = dict(zip(dic["sinonimo"], dic["bandeira_canonica"]))
        print(f"Dicionário de bandeiras: {len(mapa)} entradas")
    else:
        mapa = {}
        print("Sem data/bandeiras.csv: bandeiras carregadas como estão")
    df["bandeira_canonica"] = df["bandeira_original"].map(lambda b: mapa.get(b, b))

    engine = criar_engine()
    with engine.begin() as conn:          # tudo numa transação: se der erro, nada é gravado
        limpar_tabelas(conn)
        print("Carregando:")

        # 1) uf
        ufs = pd.DataFrame({"sigla": sorted(df["uf"].unique())})
        ufs["nome"] = ufs["sigla"].map(NOMES_UF)
        inserir(conn, ufs, "uf")
        uf_id = pd.read_sql("SELECT id AS uf_id, sigla AS uf FROM uf", conn)

        # 2) municipio
        mun = df[["municipio", "uf"]].drop_duplicates().merge(uf_id, on="uf")
        inserir(conn, mun.rename(columns={"municipio": "nome"})[["nome", "uf_id"]], "municipio")
        mun_id = pd.read_sql("SELECT m.id AS municipio_id, m.nome AS municipio, u.sigla AS uf "
                             "FROM municipio m JOIN uf u ON u.id = m.uf_id", conn)

        # 3) bairro (só os que existem)
        bai = df[df["bairro"].notna()][["bairro", "municipio", "uf"]].drop_duplicates().merge(mun_id, on=["municipio", "uf"])
        inserir(conn, bai.rename(columns={"bairro": "nome"})[["nome", "municipio_id"]], "bairro")
        bai_id = pd.read_sql("SELECT b.id AS bairro_id, b.nome AS bairro, b.municipio_id FROM bairro b", conn)

        # 4) bandeira e sinônimos
        band = pd.DataFrame({"nome": sorted(df["bandeira_canonica"].dropna().unique())})
        inserir(conn, band, "bandeira")
        band_id = pd.read_sql("SELECT id AS bandeira_id, nome AS bandeira_canonica FROM bandeira", conn)
        sin = (df[df["bandeira_original"] != df["bandeira_canonica"]][["bandeira_original", "bandeira_canonica"]]
               .drop_duplicates().merge(band_id, on="bandeira_canonica")
               .rename(columns={"bandeira_original": "sinonimo"})[["sinonimo", "bandeira_id"]])
        inserir(conn, sin, "bandeira_sinonimo")

        # 5) empresa (raiz do CNPJ)
        emp = df[["cnpj_raiz", "razao_social"]].drop_duplicates("cnpj_raiz")
        inserir(conn, emp, "empresa")

        # 6) endereco (um por posto, na mesma ordem do CSV)
        end = df.merge(mun_id, on=["municipio", "uf"], how="left")
        end = end.merge(bai_id, on=["bairro", "municipio_id"], how="left")
        end = end[["tipo_logradouro", "logradouro", "numero", "sem_numero", "km", "complemento",
                   "cep", "municipio_id", "bairro_id"]].copy()
        b = end["bairro_id"]
        end["bairro_id"] = b.astype("Int64").astype(object).where(b.notna(), None)
        inserir(conn, end, "endereco")
        ids = pd.read_sql("SELECT id FROM endereco ORDER BY id", conn)["id"].tolist()
        if len(ids) != len(df):
            sys.exit("Erro: quantidade de endereços diferente da de postos")

        # 7) posto
        posto = df.merge(band_id, on="bandeira_canonica", how="left")[
            ["cnpj", "cnpj_raiz", "codigo_isimp", "autorizacao", "tipo_autorizacao", "data_publicacao",
             "data_vinculacao", "bandeira_original", "bandeira_id", "flag_inconsistente", "motivo_inconsistencia"]].copy()
        posto.insert(7, "endereco_id", ids)
        inserir(conn, posto, "posto")

        # conferência
        print("\nConferência (obtido / esperado pelo CSV):")
        esperado = {"uf": df["uf"].nunique(), "municipio": len(mun), "bairro": len(bai), "bandeira": len(band),
                    "empresa": len(emp), "endereco": len(df), "posto": len(df)}
        ok = True
        for tabela, qtd in esperado.items():
            n = conn.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar()
            marca = "ok" if n == qtd else "DIFERENTE"
            ok &= n == qtd
            print(f"  {tabela:10} {n:>6} / {qtd:<6} {marca}")
    print("\nCarga concluída." if ok else "\nAtenção: há contagens diferentes.")


if __name__ == "__main__":
    main()