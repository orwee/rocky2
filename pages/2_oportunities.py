# opportunities.py
import streamlit as st
import re
import requests
import pandas as pd
import plotly.express as px
import openai
from utils import (
    get_defi_llama_yields,
    format_number,
    get_alternatives_for_token,
    get_openai_api_key
)

def render_opportunities_chat():
    st.set_page_config(page_title="Oportunidades DeFi - Chat", layout="wide")
    st.title("Chat de Oportunidades DeFi")

    # Inicializar el historial de chat para oportunidades si no existe
    if "opp_chat_messages" not in st.session_state:
        st.session_state["opp_chat_messages"] = [
            {"role": "assistant", "content": (
                "¡Hola! Soy tu asesor DeFi. Pregunta, por ejemplo:\n"
                "• 'muestra alternativas para BTC'\n"
                "• 'filtra por la chain: arbitrum'\n"
                "• 'muestra el grafico del pool: 747c1d2a-c668-4682-b9f9-296708a3dd90'\n"
                "Recuerda que siempre se muestran máximo 3 oportunidades."
            )}
        ]

    # Mostrar el historial de chat
    for msg in st.session_state["opp_chat_messages"]:
        st.chat_message(msg["role"]).write(msg["content"])

    # Capturar la entrada del usuario
    user_input = st.chat_input("Escribe tu consulta:")
    if user_input:
        st.session_state["opp_chat_messages"].append({"role": "user", "content": user_input})
        st.chat_message("user").write(user_input)

        openai_api_key = get_openai_api_key()
        if not openai_api_key:
            ai_response = "Por favor, agrega tu OpenAI API key para continuar."
        else:
            # Inicializamos banderas para mostrar gráfico
            show_graph = False
            pool_id_requested = None

            # Verificar si en el mensaje se solicita mostrar un gráfico
            if "grafico" in user_input.lower() or "gráfico" in user_input.lower():
                m_pool = re.search(r"pool\s*[:=]\s*([\w-]+)", user_input.lower())
                if m_pool:
                    pool_id_requested = m_pool.group(1)
                    show_graph = True
                elif "primer" in user_input.lower() and st.session_state.get("last_alternatives"):
                    pool_id_requested = st.session_state["last_alternatives"][0].get("pool")
                    show_graph = True

            # Si el mensaje contiene filtro por chain (e.g. "chain: arbitrum")
            chain_match = re.search(r"(?:chain|blockchain)\s*(?:[:=]\s*|\s+de\s+)(\w+)", user_input.lower())
            if chain_match:
                chain_filter = chain_match.group(1).lower()
                llama_data = get_defi_llama_yields()
                if "error" in llama_data:
                    ai_response = "Error al obtener datos de DeFi Llama."
                else:
                    alternatives = []
                    for pool in llama_data.get("data", []):
                        if chain_filter in pool.get("chain", "").lower():
                            alternatives.append({
                                "symbol": pool.get("symbol", ""),
                                "project": pool.get("project", ""),
                                "chain": pool.get("chain", ""),
                                "apy": pool.get("apy", 0),
                                "tvlUsd": pool.get("tvlUsd", 0),
                                "pool": pool.get("pool", "N/A")
                            })
                    alternatives.sort(key=lambda x: x.get("apy", 0), reverse=True)
                    alternatives = alternatives[:3]
                    # Guardar en session_state para posibles solicitudes de gráfico
                    st.session_state["last_alternatives"] = alternatives
                    if alternatives:
                        response_text = "He encontrado las siguientes oportunidades filtradas por chain:\n\n"
                        for alt in alternatives:
                            response_text += (
                                f"• {alt['project']} en {alt['chain']}, token {alt['symbol']}, "
                                f"APY: {alt['apy']:.2f}% - TVL: ${format_number(alt['tvlUsd'])} (Pool ID: {alt['pool']})\n\n"
                            )
                        ai_response = response_text
                    else:
                        ai_response = f"No se encontraron oportunidades para chain: {chain_filter}"

                # Si se solicita gráfico y se determina el pool id, mostrar el gráfico
                if show_graph and pool_id_requested:
                    chart_url = f"https://yields.llama.fi/chart/{pool_id_requested}"
                    try:
                        chart_response = requests.get(chart_url, headers={"accept": "*/*"})
                        if chart_response.status_code == 200:
                            chart_data = chart_response.json()
                            if chart_data.get("status") == "success" and chart_data.get("data"):
                                df_chart = pd.DataFrame(chart_data["data"])
                                df_chart["timestamp"] = pd.to_datetime(df_chart["timestamp"], unit="s")
                                fig = px.line(
                                    df_chart,
                                    x="timestamp",
                                    y="apy",
                                    title=f"Evolución del APY para el Pool {pool_id_requested}",
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
                return

            # Procesamos las alternativas basadas en el token
            token = None
            token_match = re.search(r"alternativas\s+para\s+(\w+)", user_input, re.IGNORECASE)
            if token_match:
                token = token_match.group(1).upper()
            else:
                try:
                    completion = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "Extrae solo el símbolo del token mencionado en el mensaje. Responde únicamente con el símbolo."},
                            {"role": "user", "content": user_input}
                        ]
                    )
                    token = completion["choices"][0]["message"]["content"].strip()
                except Exception as e:
                    token = ""

            if token:
                llama_data = get_defi_llama_yields()
                if "error" in llama_data:
                    ai_response = "No se pudo consultar DeFi Llama."
                else:
                    alternatives = get_alternatives_for_token(token, llama_data)
                    st.session_state["last_alternatives"] = alternatives
                    if alternatives:
                        response_parts = [f"📊 Mejores alternativas para {token}:\n"]
                        for alt in alternatives:
                            response_parts.append(
                                f"• {alt['project']} en {alt['chain']}:\n"
                                f"  - Pool: {alt['symbol']}\n"
                                f"  - APY: {alt['apy']:.2f}%\n"
                                f"  - TVL: ${format_number(alt['tvlUsd'])}\n"
                            )
                        ai_response = "\n".join(response_parts)
                    else:
                        ai_response = f"No se encontraron alternativas para {token}."
            else:
                ai_response = "No se pudo extraer el símbolo del token de tu mensaje."

            # Si en este flujo se solicita gráfico y aún no se obtuvo el pool id, se usa el primer resultado registrado
            if show_graph and not pool_id_requested and st.session_state.get("last_alternatives"):
                pool_id_requested = st.session_state["last_alternatives"][0].get("pool")
                chart_url = f"https://yields.llama.fi/chart/{pool_id_requested}"
                try:
                    chart_response = requests.get(chart_url, headers={"accept": "*/*"})
                    if chart_response.status_code == 200:
                        chart_data = chart_response.json()
                        if chart_data.get("status") == "success" and chart_data.get("data"):
                            df_chart = pd.DataFrame(chart_data["data"])
                            df_chart["timestamp"] = pd.to_datetime(df_chart["timestamp"], unit="s")
                            fig = px.line(
                                df_chart,
                                x="timestamp",
                                y="apy",
                                title=f"Evolución del APY para el Pool {pool_id_requested}",
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
