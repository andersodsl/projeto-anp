import os
import re
import pandas as pd

CAMINHO = "data/raw/dados-cadastrais-revendedores-varejistas-combustiveis-automoveis.csv"
SAIDA = "data/processed/postos_limpo.csv"

UFS = {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
       "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"}
PLACEHOLDERS = {"", "-", "--", "N/A", "NA", "NULL", "NONE", "NAO INFORMADO", "NÃO INFORMADO"}


def limpar_texto(valor):
    """Tira espaços duplicados/pontas e troca placeholders por nulo."""
    if pd.isna(valor):
        return None
    valor = re.sub(r"\s+", " ", valor).strip()
    return None if valor.upper() in PLACEHOLDERS else valor


def cnpj_valido(cnpj):
    """Confere tamanho e dígitos verificadores do CNPJ."""
    if not isinstance(cnpj, str) or not re.fullmatch(r"\d{14}", cnpj) or len(set(cnpj)) == 1:
        return False

    def digito(base, pesos):
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6] + p1
    return cnpj[12] == digito(cnpj[:12], p1) and cnpj[13] == digito(cnpj[:13], p2)


def limpar_cep(cep):
    """Devolve (cep_corrigido, foi_corrigido). CEP inválido vira None."""
    if pd.isna(cep):
        return None, False
    digitos = re.sub(r"\D", "", cep)
    corrigido = False
    if len(digitos) == 7:          # perdeu o zero à esquerda (ex.: 7401790 -> 07401790)
        digitos, corrigido = digitos.zfill(8), True
    if len(digitos) != 8 or set(digitos) == {"0"}:
        return None, False
    return digitos, corrigido


# ---------------------------------------------------------------- leitura
bruto = pd.read_csv(CAMINHO, sep=";", dtype=str)
df = bruto.copy()
for coluna in df.columns:
    df[coluna] = df[coluna].map(limpar_texto)

# ---------------------------------------------------------------- campos
out = pd.DataFrame()
out["cnpj"] = df["CNPJ"].str.replace(r"\D", "", regex=True)
out["cnpj_raiz"] = out["cnpj"].str[:8]
out["codigo_isimp"] = df["CODIGOISIMP"]
out["razao_social"] = df["RAZAOSOCIAL"]
out["autorizacao"] = df["AUTORIZACAO"]
out["tipo_autorizacao"] = df["AUTORIZACAO"].str.extract(r"^([A-Z]+)/")[0]

publicacao = pd.to_datetime(df["DATAPUBLICACAO"], format="%d/%m/%Y", errors="coerce")
vinculacao = pd.to_datetime(df["DATAVINCULACAO"], format="%d/%m/%Y", errors="coerce")
out["data_publicacao"] = publicacao.dt.strftime("%Y-%m-%d")
out["data_vinculacao"] = vinculacao.dt.strftime("%Y-%m-%d")

# preenchidos depois, no standardize.py
for coluna in ["tipo_logradouro", "logradouro", "numero", "sem_numero", "km"]:
    out[coluna] = None
out["endereco_original"] = df["ENDERECO"]          # entrada do standardize.py

out["complemento"] = df["COMPLEMENTO"]
ceps = df["CEP"].map(limpar_cep)
out["cep"] = ceps.map(lambda x: x[0])
cep_corrigido = ceps.map(lambda x: x[1])

out["bairro"] = df["BAIRRO"]
out["municipio"] = df["MUNICIPIO"].str.upper()
out["uf"] = df["UF"].str.upper()
out["bandeira_original"] = df["BANDEIRA"]
out["bandeira"] = df["BANDEIRA"]                   # a Naira aplica o dicionário de sinônimos

# ---------------------------------------------------------------- inconsistências
problemas = pd.DataFrame({
    "cnpj_invalido": ~out["cnpj"].map(cnpj_valido),
    "cep_invalido": out["cep"].isna(),
    "uf_invalida": ~out["uf"].isin(UFS),
    "data_publicacao_ausente": publicacao.isna(),
    "data_vinculacao_ausente": vinculacao.isna(),
    "bairro_ausente": out["bairro"].isna(),
    "autorizacao_fora_do_padrao": out["tipo_autorizacao"].isna(),
    "autorizacao_repetida": out["autorizacao"].notna() & out["autorizacao"].duplicated(keep=False),
})
out["flag_inconsistente"] = problemas.any(axis=1)
out["motivo_inconsistencia"] = problemas.apply(lambda linha: ";".join(linha.index[linha]), axis=1).replace("", None)

# ---------------------------------------------------------------- saída
colunas = ["cnpj", "cnpj_raiz", "codigo_isimp", "razao_social", "autorizacao", "tipo_autorizacao",
           "data_publicacao", "data_vinculacao", "tipo_logradouro", "logradouro", "numero",
           "sem_numero", "km", "complemento", "cep", "bairro", "municipio", "uf",
           "bandeira_original", "bandeira", "flag_inconsistente", "motivo_inconsistencia",
           "endereco_original"]
os.makedirs("data/processed", exist_ok=True)
out[colunas].to_csv(SAIDA, index=False, sep=";", encoding="utf-8")

# ---------------------------------------------------------------- exemplos antes/depois
os.makedirs("exemplos", exist_ok=True)
antes_depois_cep = pd.DataFrame({"cep_antes": bruto["CEP"], "cep_depois": out["cep"],
                                 "municipio": out["municipio"], "uf": out["uf"]})
antes_depois_cep[cep_corrigido].to_csv("exemplos/antes_depois_cep.csv", index=False, sep=";", encoding="utf-8-sig")
mudou = bruto["RAZAOSOCIAL"] != out["razao_social"]
pd.DataFrame({"razao_antes": bruto["RAZAOSOCIAL"], "razao_depois": out["razao_social"]})[mudou] \
    .to_csv("exemplos/antes_depois_razao_social.csv", index=False, sep=";", encoding="utf-8-sig")

# ---------------------------------------------------------------- resumo
print(f"Registros: {len(out)}")
print(f"CEPs corrigidos (zero à esquerda): {int(cep_corrigido.sum())}")
print(f"Razões sociais ajustadas (espaços): {int(mudou.sum())}")
print(f"Registros com alguma inconsistência: {int(out['flag_inconsistente'].sum())}")
print("\nInconsistências por tipo:")
print(problemas.sum().sort_values(ascending=False).to_string())
print(f"\nArquivo gerado: {SAIDA}")