"""Aplicação Streamlit: concentração de mercado de postos de combustíveis por município.
Rodar:  streamlit run src/app.py   (com $env:DB_PASSWORD definido e o banco 'anp' carregado)"""
import streamlit as st
from db import carregar_postos
from metricas import (hhi_por_municipio, ranking_redes, municipios_so_bandeira_branca,
                      postos_inconsistentes, resumo_motivos, BRANCA)

st.set_page_config(page_title="Concentração de postos de combustíveis", layout="wide")


@st.cache_data(show_spinner="Lendo o banco de dados...")
def dados():
    df = carregar_postos()
    return df, hhi_por_municipio(df, "rede"), hhi_por_municipio(df, "bandeira")


st.title("Concentração de mercado de combustíveis por município")
st.caption("Base: cadastro de revendedores varejistas de combustíveis automotivos (ANP, dados.gov.br), "
           "lida do banco PostgreSQL.")

try:
    df, hhi_rede, hhi_band = dados()
except Exception as erro:
    st.error("Não consegui ler o banco. Confira se o PostgreSQL está ligado, se o banco 'anp' foi carregado "
             "(python src/load.py) e se a variável DB_PASSWORD foi definida no terminal.")
    st.exception(erro)
    st.stop()

# ---------------------------------------------------------------- filtros
st.sidebar.header("Filtros")
uf = st.sidebar.selectbox("UF", sorted(df["uf"].unique()))
municipios = sorted(df[df["uf"] == uf]["municipio"].unique())
municipio = st.sidebar.selectbox("Município", municipios)
st.sidebar.caption(f"{len(df):,} postos | {df['uf'].nunique()} UFs".replace(",", "."))

aba1, aba2, aba3, aba4 = st.tabs(["Município", "Rankings", "Qualidade dos dados", "Sobre"])

# ---------------------------------------------------------------- aba 1
with aba1:
    sel = df[(df["uf"] == uf) & (df["municipio"] == municipio)]
    filtro = lambda h: h[(h["uf"] == uf) & (h["municipio"] == municipio)].iloc[0]
    r, b = filtro(hhi_rede), filtro(hhi_band)

    st.subheader(f"{municipio} - {uf}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Postos", int(r["total_postos"]))
    with c2:
        st.metric("Redes (empresas)", int(r["concorrentes"]))
    with c3:
        st.metric("HHI por rede", int(r["hhi"]), r["classificacao"], delta_color="off")
    with c4:
        st.metric("HHI por bandeira", int(b["hhi"]), b["classificacao"], delta_color="off")
    if r["total_postos"] < 5:
        st.warning("Município com poucos postos: o HHI fica alto só por haver poucos concorrentes.")

    esq, dir_ = st.columns(2)
    with esq:
        st.markdown("**Postos por bandeira**")
        por_band = sel.groupby("bandeira").size().rename("postos").reset_index().sort_values("postos", ascending=False)
        por_band["%"] = (por_band["postos"] / por_band["postos"].sum() * 100).round(1)
        st.bar_chart(por_band.set_index("bandeira")["postos"])
        st.dataframe(por_band, hide_index=True)
    with dir_:
        st.markdown("**Postos por rede (empresa dona)**")
        por_rede = (sel.groupby("cnpj_raiz").agg(rede=("razao_social", "first"), postos=("cnpj", "count"))
                    .reset_index().sort_values("postos", ascending=False).head(10))
        por_rede["%"] = (por_rede["postos"] / len(sel) * 100).round(1)
        st.bar_chart(por_rede.set_index("rede")["postos"])
        st.dataframe(por_rede[["rede", "postos", "%"]], hide_index=True)

    with st.expander("O que é o HHI?"):
        st.write("O HHI (índice Herfindahl-Hirschman) é a soma dos quadrados das participações (em %) de cada "
                 "concorrente no município. Vai de 0 (mercado pulverizado) a 10.000 (um único concorrente). "
                 "Faixas usadas: abaixo de 1.500 pouco concentrado, de 1.500 a 2.500 moderado, acima de 2.500 "
                 "muito concentrado. Como a base é um cadastro (sem vendas), a participação é medida pelo número "
                 "de postos. No HHI por bandeira, cada empresa de bandeira branca conta como concorrente separada.")

# ---------------------------------------------------------------- aba 2
with aba2:
    st.subheader("Municípios mais e menos concentrados")
    medida = st.radio("Medir concentração por", ["Rede (empresa)", "Bandeira"], horizontal=True)
    base = hhi_rede if medida.startswith("Rede") else hhi_band
    minimo = st.slider("Mínimo de postos no município", 2, 50, 10)
    so_uf = st.checkbox(f"Mostrar só {uf}")
    tabela = base[base["total_postos"] >= minimo]
    if so_uf:
        tabela = tabela[tabela["uf"] == uf]
    colunas = ["uf", "municipio", "total_postos", "concorrentes", "maior_participacao", "hhi", "classificacao"]
    esq, dir_ = st.columns(2)
    with esq:
        st.markdown("**Mais concentrados**")
        st.dataframe(tabela.head(15)[colunas], hide_index=True)
    with dir_:
        st.markdown("**Menos concentrados**")
        st.dataframe(tabela.tail(15).iloc[::-1][colunas], hide_index=True)

    st.subheader("Maiores redes do país")
    st.dataframe(ranking_redes(df, 20), hide_index=True)

    st.subheader("Municípios só com bandeira branca")
    so_branca = municipios_so_bandeira_branca(df)
    st.write(f"{len(so_branca)} municípios têm apenas postos de bandeira branca (sem marca).")
    st.dataframe(so_branca[so_branca["uf"] == uf] if so_uf else so_branca.head(30), hide_index=True)

# ---------------------------------------------------------------- aba 3
with aba3:
    st.subheader("Postos com cadastro inconsistente")
    inc = postos_inconsistentes(df)
    motivos = resumo_motivos(df)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Postos inconsistentes", len(inc))
        st.dataframe(motivos, hide_index=True)
    with c2:
        st.bar_chart(motivos.set_index("motivo")["postos"])
    escolha = st.selectbox("Filtrar por motivo", ["(todos)"] + motivos["motivo"].tolist())
    lista = inc if escolha == "(todos)" else inc[inc["motivo_inconsistencia"].str.contains(escolha, na=False)]
    st.dataframe(lista, hide_index=True)
    st.download_button("Baixar lista (CSV)", lista.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       "postos_inconsistentes.csv", "text/csv")

# ---------------------------------------------------------------- aba 4
with aba4:
    st.subheader("Sobre a base e o tratamento")
    st.write("Base: cadastro de revendedores varejistas de combustíveis automotivos da ANP (dados.gov.br), "
             f"com {len(df):,} postos.".replace(",", "."))
    st.write("Tratamento em Python: limpeza e validação (CNPJ, CEP, datas), endereço separado em colunas, "
             "sinônimos de bandeira e de endereço unificados, e carga em um banco PostgreSQL normalizado "
             "(uf, município, bairro, endereço, bandeira, empresa, posto).")
    st.info("Limitação: a base não tem vendas nem preços. A concentração mede a presença de postos, "
            "não a participação real de mercado.")
