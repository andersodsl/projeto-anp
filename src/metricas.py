import os
import pandas as pd

CAMINHO = "data/processed/postos_limpo.csv"
DICIONARIO = "data/bandeiras.csv"
PASTA_SAIDA = "resultados"
BRANCA = "BANDEIRA BRANCA"


def carregar(caminho=CAMINHO):
    """Lê o CSV tratado. dtype=str evita perder zeros (CEP, CNPJ)."""
    df = pd.read_csv(caminho, sep=";", dtype=str)
    df["flag_inconsistente"] = df["flag_inconsistente"] == "True"
    if os.path.exists(DICIONARIO):                      # unifica os sinônimos de bandeira
        dic = pd.read_csv(DICIONARIO, sep=";", dtype=str, encoding="utf-8-sig").dropna()
        dic = dic.apply(lambda coluna: coluna.str.strip())
        df["bandeira"] = df["bandeira_original"].replace(dict(zip(dic["sinonimo"], dic["bandeira_canonica"])))
    return df


def classificar_hhi(valor):
    """Faixas usuais do HHI (escala de 0 a 10.000)."""
    if valor < 1500:
        return "pouco concentrado"
    if valor <= 2500:
        return "moderadamente concentrado"
    return "muito concentrado"


def _grupo_bandeira(df):
    """Cada empresa de bandeira branca conta como concorrente separada.
    Sem isso, os 22 mil postos sem marca virariam um único 'concorrente' e inflariam o HHI."""
    return df["bandeira"].where(df["bandeira"] != BRANCA, BRANCA + " " + df["cnpj_raiz"])


def hhi_por_municipio(df, por="rede"):
    """HHI = soma dos quadrados das participações (em %) de cada concorrente no município.
    por='rede'     -> concorrente = empresa dona do posto (raiz do CNPJ)
    por='bandeira' -> concorrente = bandeira (provisório até o dicionário de sinônimos)"""
    d = df[["uf", "municipio", "cnpj_raiz", "bandeira"]].copy()
    d["grupo"] = d["cnpj_raiz"] if por == "rede" else _grupo_bandeira(d)

    c = d.groupby(["uf", "municipio", "grupo"]).size().rename("postos").reset_index()
    c["total"] = c.groupby(["uf", "municipio"])["postos"].transform("sum")
    c["participacao"] = c["postos"] / c["total"] * 100
    c["quadrado"] = c["participacao"] ** 2

    r = c.groupby(["uf", "municipio"]).agg(
        total_postos=("postos", "sum"),
        concorrentes=("grupo", "nunique"),
        maior_participacao=("participacao", "max"),
        hhi=("quadrado", "sum"),
    ).reset_index()
    r["maior_participacao"] = r["maior_participacao"].round(1)
    r["hhi"] = r["hhi"].round(0).astype(int)
    r["classificacao"] = r["hhi"].map(classificar_hhi)
    return r.sort_values(["hhi", "total_postos"], ascending=[False, False]).reset_index(drop=True)


def ranking_redes(df, topo=20):
    """Empresas (raiz do CNPJ) com mais postos."""
    d = df.assign(uf_municipio=df["uf"] + "/" + df["municipio"])
    r = d.groupby("cnpj_raiz").agg(
        razao_social=("razao_social", "first"),
        postos=("cnpj", "count"),
        municipios=("uf_municipio", "nunique"),
        bandeiras=("bandeira_original", "nunique"),
    ).reset_index()
    return r.sort_values("postos", ascending=False).head(topo).reset_index(drop=True)


def municipios_so_bandeira_branca(df):
    """Municípios em que todos os postos são de bandeira branca."""
    d = df.assign(branca=df["bandeira"] == BRANCA)
    g = d.groupby(["uf", "municipio"]).agg(postos=("cnpj", "count"), brancas=("branca", "sum")).reset_index()
    r = g[g["postos"] == g["brancas"]][["uf", "municipio", "postos"]]
    return r.sort_values("postos", ascending=False).reset_index(drop=True)


def postos_inconsistentes(df):
    """Postos com flag_inconsistente e o motivo."""
    cols = ["cnpj", "razao_social", "uf", "municipio", "motivo_inconsistencia"]
    return df[df["flag_inconsistente"]][cols].reset_index(drop=True)


def resumo_motivos(df):
    """Quantos postos há por tipo de inconsistência (um posto pode ter mais de um motivo)."""
    m = df[df["flag_inconsistente"]]["motivo_inconsistencia"].str.split(";").explode()
    return m.value_counts().rename_axis("motivo").reset_index(name="postos")


if __name__ == "__main__":
    df = carregar()
    os.makedirs(PASTA_SAIDA, exist_ok=True)

    hhi_rede = hhi_por_municipio(df, "rede")
    hhi_band = hhi_por_municipio(df, "bandeira")
    ranking = ranking_redes(df)
    so_branca = municipios_so_bandeira_branca(df)
    inconsistentes = postos_inconsistentes(df)
    motivos = resumo_motivos(df)

    hhi_rede.to_csv(f"{PASTA_SAIDA}/hhi_por_rede.csv", index=False, sep=";", encoding="utf-8-sig")
    hhi_band.to_csv(f"{PASTA_SAIDA}/hhi_por_bandeira.csv", index=False, sep=";", encoding="utf-8-sig")
    ranking.to_csv(f"{PASTA_SAIDA}/ranking_redes.csv", index=False, sep=";", encoding="utf-8-sig")
    so_branca.to_csv(f"{PASTA_SAIDA}/municipios_so_bandeira_branca.csv", index=False, sep=";", encoding="utf-8-sig")
    inconsistentes.to_csv(f"{PASTA_SAIDA}/postos_inconsistentes.csv", index=False, sep=";", encoding="utf-8-sig")

    print(f"Postos: {len(df)} | Empresas (raiz CNPJ): {df['cnpj_raiz'].nunique()} | "
          f"Municípios: {len(hhi_rede)} | UFs: {df['uf'].nunique()}")

    print("\nHHI por REDE - classificação dos municípios:")
    print(hhi_rede["classificacao"].value_counts().to_string())
    grandes = hhi_rede[hhi_rede["total_postos"] >= 10]
    print("\nMunicípios MAIS concentrados por rede (mínimo 10 postos):")
    print(grandes.head(8).to_string(index=False))
    print("\nMunicípios MENOS concentrados por rede (mínimo 10 postos):")
    print(grandes.tail(5).to_string(index=False))

    print("\nHHI por BANDEIRA (provisório) - classificação dos municípios:")
    print(hhi_band["classificacao"].value_counts().to_string())

    print("\nTop 10 redes com mais postos:")
    print(ranking.head(10).to_string(index=False))

    print(f"\nMunicípios só com bandeira branca: {len(so_branca)}")
    print(so_branca.head(8).to_string(index=False))

    print(f"\nPostos inconsistentes: {len(inconsistentes)}")
    print(motivos.to_string(index=False))
    print(f"\nArquivos salvos em {PASTA_SAIDA}/")
