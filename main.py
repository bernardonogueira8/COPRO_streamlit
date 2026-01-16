import streamlit as st
import pandas as pd

# Configuração da página para aproveitar o espaço lateral
st.set_page_config(page_title="Dashboard Auditoria APAC", layout="wide")

st.title("📊 Sistema de Auditoria de APACs")
st.write("Bernardo, painel atualizado com análise detalhada por profissional e erro.")

# --- FUNÇÃO DE CARREGAMENTO COM CACHE ---


@st.cache_data
def carregar_dados(file):
    df_apac = pd.read_excel(file, sheet_name="Relação_APAC", header=12)
    df_erros = pd.read_excel(file, sheet_name="Erros Encontrados", header=12)
    df_sintese = pd.read_excel(file, sheet_name="Memória_Síntese", header=12)
    return df_apac, df_erros, df_sintese


arquivo_upload = st.file_uploader("Suba a planilha raw.xlsx", type=["xlsx"])

if arquivo_upload:
    with st.status("Processando dados...", expanded=False) as status:
        apac_raw, erros_raw, sintese_raw = carregar_dados(arquivo_upload)

        # --- TRATAMENTO E FILTROS ---
        subst = {
            "SEM ERRO RELACIONADO A TETO FINANCEIRO (VERIFICAR PLANILHAS ERROS ENCONTRADOS E SEM ORÇAMENTO)": "SEM ERRO RELACIONADO A TETO FINANCEIRO",
            "APROVADO PARCIALMENTE (ULTRAPASSOU TETO FINANCEIRO)": "ULTRAPASSOU TETO FINANCEIRO"
        }

        proc_df = sintese_raw[['Unidade', 'Procedimento', 'Valor Glosa', 'Mensagem']].query(
            "`Valor Glosa` > 0").copy()
        proc_df['Mensagem'] = proc_df['Mensagem'].replace(subst)

        # Agrupamentos para Resumo
        glosa_unid = apac_raw.groupby('Unidade', as_index=False).agg(
            {'Valor Glosa': 'sum'}).query("`Valor Glosa` > 0")
        total_glosa = glosa_unid['Valor Glosa'].sum()
        glosa_unid = glosa_unid.assign(pct=lambda x: (
            x['Valor Glosa']/total_glosa)*100).sort_values('Valor Glosa', ascending=False)

        # --- CRUZAMENTO PARA ANÁLISE DETALHADA DO PROFISSIONAL ---
        df_merge = pd.merge(
            apac_raw, erros_raw[['APAC', 'Erro']], on='APAC', how='left')

        # Nova análise solicitada: Unidade, CNS Profissional, Erro, Total de erros, Soma Glosa
        analise_prof_detalhada = df_merge.groupby(['Unidade', 'CNS Profissional', 'Erro'], as_index=False).agg(
            Total_de_erros=('Erro', 'count'),
            Soma_Glosa=('Valor Glosa', 'sum')
        ).query("Soma_Glosa > 0").sort_values(by=['Unidade', 'Soma_Glosa'], ascending=[True, False])

        # Rankings e Tipos
        ranking_erros = df_merge.groupby('Erro', as_index=False).agg(
            Frequencia=('Erro', 'count'), Glosa_Total=('Valor Glosa', 'sum')
        ).sort_values('Glosa_Total', ascending=False)

        proc_por_tipo = df_merge.dropna(subset=['Erro']).groupby('Tipo APAC', as_index=False).agg(
            Qtd_APACs_com_Erro=('APAC', 'nunique'), Total_Erros=('Erro', 'count')
        )

        top_msg_unid = proc_df.groupby(
            ['Unidade', 'Mensagem']).size().reset_index(name='Freq')
        top_msg_unid = top_msg_unid.sort_values(['Unidade', 'Freq'], ascending=[
                                                True, False]).drop_duplicates('Unidade')

        rank_proc_sintese = proc_df.groupby('Procedimento', as_index=False).agg(
            {'Valor Glosa': 'sum'}).sort_values('Valor Glosa', ascending=False)

        status.update(label="✅ Processamento concluído!", state="complete")

    # --- VARIÁVEIS PARA O RESUMO ---
    u_crit = glosa_unid.iloc[0] if not glosa_unid.empty else None
    p_crit = rank_proc_sintese.iloc[0] if not rank_proc_sintese.empty else None

    # --- MÉTRICAS GERAIS (KPIs) ---
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Total de Glosa", f"R$ {total_glosa:,.2f}")
    m2.metric("Total de Erros", len(erros_raw))
    m3.metric("Qtd de APACs Analisadas", len(apac_raw))

    # --- RESUMO EXECUTIVO (CONFORME SOLICITADO - NÃO MUDAR) ---
    st.subheader("📝 Resumo Executivo e Estratificação")
    st.markdown(f"""
    * **Unidades com Glosa:** {len(glosa_unid)} unidades apresentaram glosas, totalizando **R$ {total_glosa:,.2f}**.
    * **Volume de Erros:** Tivemos um total de **{len(erros_raw)}** erros registrados.
    * **Recorrência:** O erro mais comum foi: **"{erros_raw['Erro'].mode()[0]}"**.
    * **Impacto Profissional:** **{len(analise_prof_detalhada[analise_prof_detalhada['Total_de_erros'] > 0])}** profissionais tiveram erros vinculados às suas APACs com glosa.
    * **Unidade Crítica (Volume):** A unidade com o maior número de ocorrências de erro foi **{erros_raw['Unidade'].mode()[0]}**.
    * **Unidade Crítica (Financeiro):** A unidade com o maior valor em Glosa é **{u_crit['Unidade']}**, totalizando **R$ {u_crit['Valor Glosa']:,.2f}** ({u_crit['pct']:.2f}% do total geral).
    * **Procedimento Crítico:** O procedimento **{p_crit['Procedimento']}** é o mais crítico com valor de **R$ {p_crit['Valor Glosa']:,.2f}**, representando **{(p_crit['Valor Glosa'] / proc_df['Valor Glosa'].sum() * 100):.2f}%** das glosas de síntese.
    * **Mensagem Mais Recorrente:** "{proc_df['Mensagem'].mode()[0]}".
    """)

    st.divider()

    # --- BLOCO 1: RANKING DE ERROS E TIPOS ---
    st.subheader("🏆 Rankings e Tipos de Erros")
    st.info("**A soma através desta tabela pode sofrer alterações, pois o valor é por APAC e cada APAC pode ter mais de um erro.**")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("**Ranking de Erros (Impacto Financeiro)**")
        st.dataframe(ranking_erros.style.format(
            {'Glosa_Total': 'R$ {:,.2f}'}), width='stretch')
    with col2:
        st.write("**Problemas por Tipo de APAC**")
        st.dataframe(proc_por_tipo, width='stretch')

    st.divider()

    # --- BLOCO 2: ANÁLISE DETALHADA POR PROFISSIONAL E UNIDADE ---
    st.subheader("👨‍⚕️ Análise por Profissional e Unidade")
    st.write("**Detalhamento de Erros por CNS e Unidade**")
    st.dataframe(
        analise_prof_detalhada.style.format({'Soma_Glosa': 'R$ {:,.2f}'}),
        width='stretch'
    )

    st.write("**Glosa Total por Unidade**")
    st.dataframe(
        glosa_unid.style.format(
            {'Valor Glosa': 'R$ {:,.2f}', 'pct': '{:.2f}%'}),
        width='stretch'
    )

    st.divider()

    # --- BLOCO 3: MEMÓRIA DE SÍNTESE ---
    st.subheader("🔍 Memória de Síntese -  Analise sobre Teto Financeiro")
    st.info("**Informação 'SEM ERRO RELACIONADO A TETO FINANCEIRO', não requer atenção para FPO.**")
    st.warning(
        "**Informação 'ULTRAPASSOU TETO FINANCEIRO', requer atenção devido a uma inconsistência na FPO.**")
    col5, col6 = st.columns(2)
    with col5:
        st.write("**Top Mensagem por Unidade**")
        st.dataframe(top_msg_unid, width='stretch')
    with col6:
        st.write("**Procedimento por Valor de Glosa**")
        st.dataframe(rank_proc_sintese.style.format(
            {'Valor Glosa': 'R$ {:,.2f}'}), width='stretch')

else:
    st.info("Aguardando upload do arquivo Excel.")
