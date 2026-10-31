import os
import re
import pandas as pd

ARQUIVO = "data/processed/postos_limpo.csv"

TIPOS = {
    "AV": "AVENIDA", "AV.": "AVENIDA", "AVENIDA": "AVENIDA",
    "R": "RUA", "R.": "RUA", "RUA": "RUA",
    "ROD": "RODOVIA", "ROD.": "RODOVIA", "RODV": "RODOVIA", "RODV.": "RODOVIA", "RODOVIA": "RODOVIA",
    "EST": "ESTRADA", "EST.": "ESTRADA", "ESTRADA": "ESTRADA",
    "PRAÇA": "PRACA", "PRACA": "PRACA",
    "TRAV": "TRAVESSA", "TRAV.": "TRAVESSA", "TV": "TRAVESSA", "TRAVESSA": "TRAVESSA",
    "ALAMEDA": "ALAMEDA", "QUADRA": "QUADRA", "SITIO": "SITIO", "VIA": "VIA",
    "LARGO": "LARGO", "FAZENDA": "FAZENDA", "VILA": "VILA", "SETOR": "SETOR",
    "LOTEAMENTO": "LOTEAMENTO", "DISTRITO": "DISTRITO", "MARGEM": "MARGEM",
    "LOC": "LOCALIDADE", "LOC.": "LOCALIDADE", "LOCALIDADE": "LOCALIDADE",
}

PALAVRAS_NUM = {
    "ZERO": 0, "UM": 1, "HUM": 1, "DOIS": 2, "TRES": 3, "TRÊS": 3, "QUATRO": 4, "CINCO": 5,
    "SEIS": 6, "SETE": 7, "OITO": 8, "NOVE": 9, "DEZ": 10, "ONZE": 11, "DOZE": 12,
    "TREZE": 13, "QUATORZE": 14, "CATORZE": 14, "QUINZE": 15, "DEZESSEIS": 16,
    "DEZESSETE": 17, "DEZOITO": 18, "DEZENOVE": 19, "VINTE": 20, "TRINTA": 30,
    "QUARENTA": 40, "CINQUENTA": 50, "SESSENTA": 60, "SETENTA": 70, "OITENTA": 80,
    "NOVENTA": 90, "CEM": 100, "CENTO": 100, "DUZENTOS": 200, "TREZENTOS": 300,
    "QUATROCENTOS": 400, "QUINHENTOS": 500, "SEISCENTOS": 600, "SETECENTOS": 700,
    "OITOCENTOS": 800, "NOVECENTOS": 900,
}
_ALTERNATIVAS = "|".join(sorted(PALAVRAS_NUM, key=len, reverse=True))
BR_EXTENSO = re.compile(rf"\bBR[\s-]+((?:(?:{_ALTERNATIVAS}|E)\b\s*)+)")
BR_NUMERO = re.compile(r"\bBR\.?\s*-?\s*(\d{2,3})\b")             
KM = re.compile(r"[\s,\-–]*\bKM\.?\s*[-,]?\s*(\d+(?:[.,]\d+)?(?:\+\d+)?)")   
SEM_NUMERO = re.compile(r"^(S\s*[/.]?\s*N\s*[º°O]?\.?|SNR|S/|SEM\s+N[UÚ]MERO)$")  


def br_por_extenso(m):
    palavras = [p for p in m.group(1).split() if p != "E"]
    valor = sum(PALAVRAS_NUM[p] for p in palavras)
    return f"BR {valor:03d} " if valor else m.group(0)


def normalizar_numero(texto):
    texto = texto.strip(" .-")
    m = re.fullmatch(r"(\d+)[\s-]*([A-Z])", texto)
    return f"{m.group(1)}{m.group(2)}" if m else texto


def extrair_km(texto):
    m = KM.search(texto)
    if not m:
        return None, texto
    return m.group(1).replace(",", "."), texto[:m.start()] + texto[m.end():]


def processar(endereco, complemento):
    vazio = {"tipo_logradouro": None, "logradouro": None, "numero": None, "sem_numero": None,
             "km": None, "complemento": complemento, "tags": "", "resto_original": None}
    if pd.isna(endereco):
        return vazio
    tags = []
    e = re.sub(r"\s+", " ", endereco).strip().upper()

    m = re.match(r"^(.*),\s*([^,]*)$", e)
    logr, resto = (m.group(1), m.group(2)) if m else (e, "")
    resto_original = resto

    novo = BR_EXTENSO.sub(br_por_extenso, logr)
    if novo != logr:
        tags.append("br_por_extenso")
    novo2 = BR_NUMERO.sub(r"BR \1", novo)
    if novo2 != novo:
        tags.append("br_formato")
    logr = re.sub(r"\s+", " ", novo2).strip()

    km, logr = extrair_km(logr)
    if km is None:
        km, resto = extrair_km(resto)
    if km is not None:
        tags.append("km_extraido")
    compl = None if pd.isna(complemento) else complemento
    if km is None and compl:
        km, sem_km = extrair_km(compl)
        if km is not None:
            compl = sem_km.strip(" ,-") or None
            tags.append("km_do_complemento")

    resto = resto.strip(" ,-")
    numero, sem_numero = None, True
    if resto and SEM_NUMERO.match(resto):
        if resto != "S/N":
            tags.append("sem_numero_variante")
    elif resto and re.search(r"\d", resto):
        numero, sem_numero = normalizar_numero(resto), False
        if numero != resto:
            tags.append("numero_sufixo")
    elif resto:                                 
        logr = f"{logr}, {resto}"

    tokens = logr.split()
    while len(tokens) > 1 and tokens[0] in TIPOS and tokens[1] in TIPOS and TIPOS[tokens[0]] == TIPOS[tokens[1]]:
        tokens.pop(0)
        tags.append("tipo_duplicado")
    if len(tokens) > 1 and tokens[0] == "BR" and TIPOS.get(tokens[1]) == "RODOVIA":
        tokens.pop(0)
    tipo = None
    if tokens:
        primeiro = tokens[0]
        if primeiro == "BR":
            tipo = "RODOVIA"
            tags.append("tipo_inferido_br")
        elif primeiro in TIPOS:
            tipo = TIPOS[primeiro]
            if primeiro != tipo:
                tags.append("tipo_abreviado")
            if len(tokens) > 1:
                tokens = tokens[1:]
    logradouro = " ".join(tokens).strip(" ,-.") or None

    return {"tipo_logradouro": tipo, "logradouro": logradouro, "numero": numero,
            "sem_numero": sem_numero, "km": km, "complemento": compl,
            "tags": ";".join(tags), "resto_original": resto_original}

df = pd.read_csv(ARQUIVO, sep=";", dtype=str)
res = pd.DataFrame([processar(e, c) for e, c in zip(df["endereco_original"], df["complemento"])])

for coluna in ["tipo_logradouro", "logradouro", "numero", "sem_numero", "km", "complemento"]:
    df[coluna] = res[coluna]
df.to_csv(ARQUIVO, index=False, sep=";", encoding="utf-8")

os.makedirs("exemplos", exist_ok=True)
comparativo = pd.DataFrame({
    "endereco_antes": df["endereco_original"],
    "tipo": res["tipo_logradouro"], "logradouro": res["logradouro"], "numero": res["numero"],
    "sem_numero": res["sem_numero"], "km": res["km"], "regras_aplicadas": res["tags"],
})
amostras = []
for regra in ["sem_numero_variante", "br_por_extenso", "br_formato", "tipo_duplicado",
              "tipo_abreviado", "numero_sufixo", "km_extraido", "km_do_complemento"]:
    achados = comparativo[comparativo["regras_aplicadas"].str.contains(regra, na=False)]
    amostras.append(achados.head(15).assign(regra=regra))
pd.concat(amostras).to_csv("exemplos/antes_depois_endereco.csv", index=False, sep=";", encoding="utf-8-sig")

sem = res.loc[res["sem_numero"] == True, "resto_original"].fillna("(vazio)").value_counts()
sem.rename_axis("grafia_original").reset_index(name="quantidade") \
    .to_csv("exemplos/sinonimos_sem_numero.csv", index=False, sep=";", encoding="utf-8-sig")

print(f"Registros: {len(df)}")
print("\nRegras aplicadas (quantos registros):")
for regra in ["sem_numero_variante", "br_por_extenso", "br_formato", "tipo_duplicado", "tipo_abreviado",
              "numero_sufixo", "km_extraido", "km_do_complemento"]:
    print(f"  {regra}: {int(res['tags'].str.contains(regra).sum())}")
print(f"\nSem número: {int((res['sem_numero'] == True).sum())}")
print(f"Com KM: {int(res['km'].notna().sum())}")
print(f"Sem tipo de logradouro identificado: {int(res['tipo_logradouro'].isna().sum())}")
print("\nTipos de logradouro (top 10):")
print(res["tipo_logradouro"].value_counts().head(10).to_string())
print("\nGrafias de 'sem número' encontradas:")
print(sem.head(10).to_string())
print(f"\nArquivo atualizado: {ARQUIVO}")