import os
import pandas as pd

CAMINHO = "data/raw/dados-cadastrais-revendedores-varejistas-combustiveis-automoveis.csv"
df = pd.read_csv(CAMINHO, sep=";", dtype=str)

# Os exemplos ficam numa pasta na raiz, para poderem subir ao GitHub e ser mostrados ao professor
os.makedirs("exemplos", exist_ok=True)


def salvar(nome, filtro, colunas, ordenar=None):
    achados = df[filtro]
    if ordenar:
        achados = achados.sort_values(ordenar)
    achados = achados[colunas]
    print(f"\n=== {nome}: {len(achados)} registros ===")
    print(achados.head(5).to_string())
    achados.to_csv(f"exemplos/{nome}.csv", index=False, sep=";", encoding="utf-8-sig")


# 1. Bairro nulo
salvar("bairro_nulo", df["BAIRRO"].isna(),
       ["RAZAOSOCIAL", "ENDERECO", "BAIRRO", "MUNICIPIO", "UF"])

# 2. CEP com 7 digitos (perdeu o zero à esquerda)
salvar("cep_7_digitos", df["CEP"].str.len() == 7,
       ["RAZAOSOCIAL", "CEP", "MUNICIPIO", "UF"])

# 3. CEP invalido (curto demais)
salvar("cep_invalido", df["CEP"].str.len() < 7,
       ["RAZAOSOCIAL", "CEP", "MUNICIPIO", "UF"])

# 4. Datas nulas ou em formato invalido
pub = pd.to_datetime(df["DATAPUBLICACAO"], format="%d/%m/%Y", errors="coerce")
vin = pd.to_datetime(df["DATAVINCULACAO"], format="%d/%m/%Y", errors="coerce")
salvar("data_invalida", pub.isna() | vin.isna(),
       ["RAZAOSOCIAL", "DATAPUBLICACAO", "DATAVINCULACAO"])

# 5. AUTORIZACAO repetida em CNPJs diferentes
salvar("autorizacao_repetida", df["AUTORIZACAO"].duplicated(keep=False),
       ["AUTORIZACAO", "RAZAOSOCIAL", "CNPJ", "MUNICIPIO", "UF"],
       ordenar="AUTORIZACAO")

# 6. Espacos duplos ou sobrando na razao social
salvar("razao_social_espacos",
       df["RAZAOSOCIAL"].str.contains("  ", na=False) | (df["RAZAOSOCIAL"] != df["RAZAOSOCIAL"].str.strip()),
       ["RAZAOSOCIAL", "CNPJ"])

# 7. Bandeiras com caracteres estranhos (ATEM' S, D`MAIS, SABBÁ...)
estranhas = df["BANDEIRA"].str.contains(r"[^A-Z0-9 ]", na=False)
salvar("bandeira_estranha", estranhas, ["BANDEIRA", "RAZAOSOCIAL", "UF"])
print("\nBandeiras estranhas:", df[estranhas]["BANDEIRA"].value_counts().to_dict())