import pandas as pd

CAMINHO = "data/raw/dados-cadastrais-revendedores-varejistas-combustiveis-automoveis.csv"

# dtype=str: lê tudo como texto, para não perder zeros à esquerda (CNPJ, CEP)
df = pd.read_csv(CAMINHO, sep=";", dtype=str)

print("Linhas e colunas:", df.shape)
print()
print("Colunas:")
print(list(df.columns))
print()
print("Primeiras linhas:")
print(df.head())
print()
print("% de valores nulos por coluna:")
print((df.isna().mean() * 100).round(2))
print()
print("Valores distintos por coluna:")
print(df.nunique())