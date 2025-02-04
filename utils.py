# utils.py
import openai
import requests
import pandas as pd
import plotly.express as px
import streamlit as st
from typing import List

def summarize_portfolio(df):
    """
    Recibe un DataFrame con columnas:
      ['chain', 'common_name', 'module', 'token_symbol', 'balance_usd']
    Devuelve un string describiendo sucintamente las posiciones del usuario.
    """
    if df.empty:
        return "El portafolio está vacío o no hay posiciones mayores a \$5."

    summary_lines = []
    total_balance = df['balance_usd'].sum()
    summary_lines.append(f"Balance total estimado: ${format_number(total_balance)}\n")

    grouped = df.groupby('common_name')['balance_usd'].sum().reset_index()
    summary_lines.append("Resumen por Protocolo:")
    for _, row in grouped.iterrows():
        summary_lines.append(f" - {row['common_name']}: ${format_number(row['balance_usd'])}")

    summary_lines.append("\nPosiciones detalladas (token/protocolo):")
    for idx, row in df.iterrows():
        summary_lines.append(f" • {row['token_symbol']} en {row['common_name']} con balance de ${format_number(row['balance_usd'])}")

    return "\n".join(summary_lines)

def get_openai_api_key():
    """
    Obtiene la API key de OpenAI desde Streamlit secrets o
    la pide al usuario en la barra lateral.
    """
    if "openai_api_key" in st.secrets:
        return st.secrets["openai_api_key"]
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")
    return api_key

def format_number(value):
    """Formatea números grandes con separadores o sufijos."""
    if abs(value) >= 1e6:
        return f"{value:,.2f}".rstrip('0').rstrip('.')
    else:
        return f"{value:.6f}".rstrip('0').rstrip('.')

def get_user_defi_positions(address, api_key):
    api_key=st.secrets["merlin_api_key"]
    """
    Llama a la API de Merlin (o la tuya) para obtener posiciones DeFi de un usuario.
    Retorna un objeto JSON con la información o un dict con 'error'.
    """
    base_url = "https://api-v1.mymerlin.io/api/merlin/public/userDeFiPositions/all"
    url = f"{base_url}/{address}"
    headers = {"Authorization": f"{api_key}"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Error {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": f"Exception occurred: {str(e)}"}

def process_defi_data(result):
    """
    Procesa la respuesta de get_user_defi_positions y la convierte en un DataFrame.
    Filtra sólo balances > $5.
    """
    if not result or not isinstance(result, list):
        return pd.DataFrame(columns=['chain', 'common_name', 'module', 'token_symbol', 'balance_usd'])

    data = []
    for protocol in result:
        chain = str(protocol.get('chain', ''))
        common_name = str(protocol.get('commonName', ''))

        for portfolio in protocol.get('portfolio', []):
            module = str(portfolio.get('module', ''))

            if 'detailed' in portfolio and 'supply' in portfolio['detailed']:
                supply_tokens = portfolio['detailed']['supply']
                if isinstance(supply_tokens, list):
                    # caso Liquidity Pool
                    if module == 'Liquidity Pool' and len(supply_tokens) >= 2:
                        try:
                            balance_usd_0 = float(supply_tokens[0].get('balanceUSD', 0))
                            balance_usd_1 = float(supply_tokens[1].get('balanceUSD', 0))
                            data.append({
                                'chain': chain,
                                'common_name': common_name,
                                'module': module,
                                'token_symbol': f"{supply_tokens[0].get('tokenSymbol', '')}/{supply_tokens[1].get('tokenSymbol', '')}",
                                'balance_usd': balance_usd_0 + balance_usd_1
                            })
                        except:
                            continue
                    else:
                        for token in supply_tokens:
                            try:
                                data.append({
                                    'chain': chain,
                                    'common_name': common_name,
                                    'module': module,
                                    'token_symbol': str(token.get('tokenSymbol', '')),
                                    'balance_usd': float(token.get('balanceUSD', 0))
                                })
                            except:
                                continue

    if not data:
        return pd.DataFrame(columns=['chain', 'common_name', 'module', 'token_symbol', 'balance_usd'])

    df = pd.DataFrame(data)
    df['balance_usd'] = pd.to_numeric(df['balance_usd'], errors='coerce').fillna(0)
    df = df[df['balance_usd'] > 5]  # Filtrar balances mínimos
    df['balance_usd'] = df['balance_usd'].round(6)
    return df

def get_defi_llama_yields():
    """Consulta pools de https://yields.llama.fi/pools."""
    url = "https://yields.llama.fi/pools"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Error {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": f"Exception occurred: {str(e)}"}

def get_alternatives_for_token(token_symbol, llama_data, n=3):
    """
    Dado un token_symbol y la data de DeFi Llama,
    encuentra pools con APY altos que contengan ese token.
    """
    if not llama_data or 'data' not in llama_data:
        return []
    tokens = token_symbol.split('/')
    alternatives = []
    for pool in llama_data['data']:
        if any(token.upper() in pool['symbol'].upper() for token in tokens):
            alternatives.append({
                'symbol': pool.get('symbol', ''),
                'project': pool.get('project', ''),
                'chain': pool.get('chain', ''),
                'apy': pool.get('apy', 0),
                'tvlUsd': pool.get('tvlUsd', 0)
            })
    alternatives.sort(key=lambda x: x['apy'], reverse=True)
    return alternatives[:n]

def generate_investment_analysis(current_position, alternatives, api_key):
    """
    Llama a la API de OpenAI para generar un análisis breve
    comparando la posición actual vs. las alternativas.
    """
    if not api_key:
        return "Error: Falta la OpenAI API key."

    openai.api_key = api_key

    prompt = f"""
    Eres un asesor DeFi experto.
    Analiza brevemente esta posición y posibles alternativas:

    Posición actual:
    - Token: {current_position['token_symbol']}
    - Protocolo: {current_position['common_name']}
    - Balance USD: ${format_number(current_position['balance_usd'])}

    Alternativas disponibles:
    {chr(10).join([f"- {alt['project']} en {alt['chain']}: {alt['symbol']} (APY: {alt['apy']:.2f}%, TVL: ${format_number(alt['tvlUsd'])})" for alt in alternatives])}

    Da un comentario conciso (máx 100 palabras) y una recomendación final.
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Ajusta según tu versión
            messages=[
                {"role": "system", "content": "Eres un asesor DeFi experto y muy conciso."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Error al generar el análisis: {e}"

########################################################################
#                           LÓGICA DE CHAT                             #
########################################################################

def init_chat_history():
    """Inicializa (o recupera) el historial de chat en session_state."""
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {"role": "assistant", "content": "¡Hola! Soy tu asistente DeFi. Pregúntame sobre tu portafolio o alternativas de inversión."}
        ]

def render_chat():
    if st.session_state['combined_df'] is None:
        st.warning("Por favor, primero analiza tu portafolio en la página de Portfolio.")
        return
    """Muestra el historial de chat y maneja las interacciones."""
    for msg in st.session_state["messages"]:
        st.chat_message(msg["role"]).write(msg["content"])

    user_input = st.chat_input("Escribe tu pregunta o solicitud aquí...")
    if user_input:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        st.chat_message("user").write(user_input)

        openai_api_key = get_openai_api_key()
        if not openai_api_key:
            ai_response = "Por favor, agrega tu OpenAI API key para continuar."
        else:
            # Verificar si el usuario está pidiendo alternativas
            keywords = ["alternativas", "alternatives", "alternativa", "alternative"]
            if any(keyword in user_input.lower() for keyword in keywords):
                try:
                    token = None
                    current_position = None

                    # Si menciona una posición específica
                    if any(word in user_input.lower() for word in ["posicion", "posición", "position"]):
                        # Extraer el número de posición
                        completion = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "Extrae el número de la posición mencionada en el mensaje. Responde solo con el número."},
                                {"role": "user", "content": user_input}
                            ]
                        )
                        position_num = completion["choices"][0]["message"]["content"].strip()

                        # Obtener el DataFrame del estado de la sesión
                        if "combined_df" in st.session_state:
                            df = st.session_state["combined_df"]
                            try:
                                position_idx = int(position_num) - 1
                                if 0 <= position_idx < len(df):
                                    current_position = df.iloc[position_idx].to_dict()
                                    token = current_position['token_symbol']

                                    # Mostrar la posición actual
                                    st.info(f"Posición actual:\n"
                                           f"Token: {token}\n"
                                           f"Protocolo: {current_position['common_name']}\n"
                                           f"Balance: ${format_number(current_position['balance_usd'])}\n"
                                           f"Wallet: {current_position['wallet']}")
                                else:
                                    ai_response = f"No encontré la posición {position_num} en tu portafolio."
                                    raise ValueError("Posición fuera de rango")
                            except:
                                ai_response = "Por favor, especifica un número de posición válido."
                                raise ValueError("Número de posición inválido")
                        else:
                            ai_response = "No encuentro tu portafolio. ¿Has analizado tus wallets primero?"
                            raise ValueError("No hay portafolio")
                    else:
                        # Si solo menciona un token
                        completion = openai.ChatCompletion.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "Extrae solo el símbolo del token mencionado en el mensaje. Responde únicamente con el símbolo."},
                                {"role": "user", "content": user_input}
                            ]
                        )
                        token = completion["choices"][0]["message"]["content"].strip()

                    if token:
                        # Obtener alternativas de DeFi Llama
                        llama_data = get_defi_llama_yields()
                        if 'error' not in llama_data:
                            # Filtrar alternativas por el token de la posición seleccionada
                            alternatives = get_alternatives_for_token(token, llama_data)

                            if alternatives:
                                if current_position:
                                    # Si tenemos la posición actual, usar generate_investment_analysis
                                    analysis = generate_investment_analysis(current_position, alternatives, openai_api_key)
                                    response_parts = [f"🔍 Análisis y alternativas para tu posición en {token}:\n\n{analysis}\n\n📊 Detalles de las alternativas:\n"]
                                else:
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
                                ai_response = f"No encontré alternativas para {token}. ¿Podrías verificar el símbolo del token?"
                        else:
                            ai_response = "Lo siento, no pude consultar las alternativas en este momento. Por favor, inténtalo más tarde."

                except Exception as e:
                    if not 'ai_response' in locals():
                        ai_response = f"Lo siento, hubo un error al procesar tu solicitud: {str(e)}"
            else:
                # Comportamiento normal del chat
                messages_for_openai = []
                messages_for_openai.append({
                    "role": "system",
                    "content": (
                        "Actúa como un asesor experto en DeFi. "
                        "A continuación tienes un resumen del portafolio del usuario. Úsalo para responder de forma contextual.\n\n"
                        f"{st.session_state.get('portfolio_summary', 'No hay resumen de portafolio disponible.')}"
                    )
                })
                messages_for_openai.extend(st.session_state["messages"])

                try:
                    completion = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=messages_for_openai
                    )
                    ai_response = completion["choices"][0]["message"]["content"]
                except Exception as e:
                    ai_response = f"Error al generar respuesta: {e}"

        st.session_state["messages"].append({"role": "assistant", "content": ai_response})
        st.chat_message("assistant").write(ai_response)
