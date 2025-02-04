# pages/2_oportunities_chat.py
import streamlit as st
import re
import requests
import pandas as pd
import plotly.express as px
from utils import get_defi_llama_yields, format_number, get_openai_api_key

def render_opportunities_chat():
    st.set_page_config(page_title="Oportunidades DeFi - Chat", layout="wide")
    st.title("Chat de Oportunidades DeFi")

    # Inicializa el historial de chat específico para oportunidades
    if "opp_chat_messages" not in st.session_state:
        st.session_state["opp_chat_messages"] = [
            {"role": "assistant", "content": "¡Hola! Soy tu asesor de oportunidades DeFi. Puedes preguntarme sobre oportunidades de inversión utilizando criterios como:\n\n• blockchain: ethereum\n• project/proyecto: lido\n• token: STETH\n• apy: >3\n• tvl: >=1000000\n\nIncluso puedes pedir, por ejemplo, 'busca oportunidades en blockchain: ethereum con apy: >3' o 'muestra gráfico del pool: 747c1d2a-c668-4682-b9f9-296708a3dd90'."}
        ]

    # Mostrar el historial de chat
    for msg in st.session_state["opp_chat_messages"]:
        st.chat_message(msg["role"]).write(msg["content"])

    # Capturar el input del usuario
    user_input = st.chat_input("Escribe tu consulta sobre oportunidades:")
    if user_input:
        st.session_state["opp_chat_messages"].append({"role": "user", "content": user_input})
        st.chat_message("user").write(user_input)

        # Para extraer filtros del mensaje de forma básica (usando expresiones regulares)
        filters = {}
        lower_input = user_input.lower()

        # Extraer cadena (blockchain)
        m_chain = re.search(r"(chain|blockchain)\s*[:=]\s*([\w]+)", lower_input)
        if m_chain:
            filters["chain"] = m_chain.group(2)
        # Extraer proyecto
        m_project = re.search(r"(project|proyecto)\s*[:=]\s*([\w]+)", lower_input)
        if m_project:
            filters["project"] = m_project.group(2)
        # Extraer token/símbolo
        m_token = re.search(r"(token|symbol)\s*[:=]\s*([\w]+)", lower_input)
        if m_token:
            filters["token"] = m_token.group(2)
        # Extraer filtro de apy (por ejemplo, "apy: >3")
        m_apy = re.search(r"apy\s*([><]=?)\s*(\d+(\.\d+)?)", lower_input)
        if m_apy:
            filters["apy"] = (m_apy.group(1), float(m_apy.group(2)))
        # Extraer filtro de tvl (por ejemplo, "tvl: >=1000000")
        m_tvl = re.search(r"tvl\s*([><]=?)\s*(\d+(\.\d+)?)", lower_input)
        if m_tvl:
            filters["tvlUsd"] = (m_tvl.group(1), float(m_tvl.group(2)))

        # Obtener la API key de OpenAI (si fuera necesaria para ampliar la respuesta)
        openai_api_key = get_openai_api_key()

        # Llama a la API de DeFi Llama para obtener la data de oportunidades
        llama_data = get_defi_llama_yields()
        if "error" in llama_data:
            ai_response = "Hubo un error al obtener datos de oportunidades desde DeFi Llama."
        else:
            opps = llama_data.get("data", [])
            filtered_opps = []
            for opp in opps:
                include = True
                # Filtro por cadena
                if "chain" in filters:
                    if filters["chain"] not in opp.get("chain", "").lower():
                        include = False
                # Filtro por proyecto
                if "project" in filters:
                    if filters["project"] not in opp.get("project", "").lower():
                        include = False
                # Filtro por token/símbolo
                if "token" in filters:
                    if filters["token"] not in opp.get("symbol", "").upper():
                        include = False
                # Filtro por APY
                if "apy" in filters:
                    op_apy, threshold_apy = filters["apy"]
                    current_apy = opp.get("apy", 0)
                    if op_apy in [">", ">="] and not (current_apy >= threshold_apy):
                        include = False
                    elif op_apy in ["<", "<="] and not (current_apy <= threshold_apy):
                        include = False
                    elif op_apy == "=" and not (current_apy == threshold_apy):
                        include = False
                # Filtro por TVL
                if "tvlUsd" in filters:
                    op_tvl, threshold_tvl = filters["tvlUsd"]
                    current_tvl = opp.get("tvlUsd", 0)
                    if op_tvl in [">", ">="] and not (current_tvl >= threshold_tvl):
                        include = False
                    elif op_tvl in ["<", "<="] and not (current_tvl <= threshold_tvl):
                        include = False
                    elif op_tvl == "=" and not (current_tvl == threshold_tvl):
                        include = False

                if include:
                    filtered_opps.append(opp)
            # Ordenar por APY descendente
            filtered_opps.sort(key=lambda x: x.get("apy", 0), reverse=True)

            if filtered_opps:
                response_text = "He encontrado las siguientes oportunidades:\n\n"
                for opp in filtered_opps:
                    response_text += (
                        f"• {opp.get('project')} en {opp.get('chain')}, token {opp.get('symbol')}, "
                        f"APY: {opp.get('apy', 0):.2f}% - TVL: ${format_number(opp.get('tvlUsd', 0))}\n"
                        f"  (Pool ID: {opp.get('pool')})\n\n"
                    )
                ai_response = response_text
            else:
                ai_response = "No se encontraron oportunidades que cumplan esos criterios."

        # Si el usuario además solicita un gráfico (por ejemplo, incluye "grafico" o "gráfico")
        if "grafico" in lower_input or "gráfico" in lower_input:
            # Intentar extraer un pool ID (por ejemplo, "pool: 747c1d2a-c668-4682-b9f9-296708a3dd90")
            m_pool = re.search(r"pool\s*[:=]\s*([\w-]+)", lower_input)
            if m_pool:
                pool_id = m_pool.group(1)
                chart_url = f"https://yields.llama.fi/chart/{pool_id}"
                try:
                    chart_response = requests.get(chart_url, headers={"accept": "*/*"})
                    if chart_response.status_code == 200:
                        chart_data = chart_response.json()
                        if chart_data.get("status") == "success" and chart_data.get("data"):
                            df_chart = pd.DataFrame(chart_data["data"])
                            df_chart["timestamp"] = pd.to_datetime(df_chart["timestamp"])
                            fig = px.line(
                                df_chart,
                                x="timestamp",
                                y="apy",
                                title=f"Evolución del APY para el Pool {pool_id}",
                                labels={"timestamp": "Fecha", "apy": "APY (%)"}
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            ai_response += "\n\nAdemás, te muestro el gráfico del pool solicitado."
                        else:
                            ai_response += "\n\nNo se pudieron cargar datos históricos para el gráfico."
                    else:
                        ai_response += "\n\nError al obtener el gráfico desde DeFi Llama."
                except Exception as e:
                    ai_response += f"\n\nError al procesar el gráfico: {e}"

        st.session_state["opp_chat_messages"].append({"role": "assistant", "content": ai_response})
        st.chat_message("assistant").write(ai_response)

def main():
    render_opportunities_chat()

if __name__ == "__main__":
    main()
