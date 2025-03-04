import streamlit as st
import pandas as pd
import requests
import json
import time
import re

# Configuración de la página
st.set_page_config(page_title="Crypto Portfolio DeFi Alternatives", layout="wide")

# Función para consultar la API de DeFiLlama
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

# Inicialización del portafolio en session_state
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = [
        {
            "num_posicion": 0,
            "wallet": "Wallet #1",
            "blockchain": "avax",
            "protocol": "Struct Finance",
            "type": "Yield",
            "token": "USDC",
            "value": 288.083017
        },
        {
            "num_posicion": 1,
            "wallet": "Wallet #1",
            "blockchain": "mnt",
            "protocol": "Pendle V2",
            "type": "Liquidity Pool",
            "token": "cmETH/PT-cmETH",
            "value": 318.715554
        }
    ]

# Inicializar variables de contexto
if 'context' not in st.session_state:
    st.session_state.context = {
        'position': None,
        'chain': None,
        'protocol': None,
        'token': None,
        'type': None,
        'min_apy': None,
        'min_tvl': None,
        'filters': [],
        'query_history': []
    }

if 'alternatives' not in st.session_state:
    st.session_state.alternatives = []

if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "¡Hola! Soy tu asistente DeFi. Puedes preguntarme sobre alternativas a tus posiciones. Por ejemplo: 'Busca alternativas a mi posición 1 con mayor APY' o 'Muestra opciones en Arbitrum'."}
    ]

# Función para normalizar nombres de blockchain
def normalize_chain_name(chain):
    chain_mapping = {
        'avax': 'Avalanche',
        'ethereum': 'Ethereum',
        'eth': 'Ethereum',
        'arbitrum': 'Arbitrum',
        'arb': 'Arbitrum',
        'optimism': 'Optimism',
        'op': 'Optimism',
        'polygon': 'Polygon',
        'poly': 'Polygon',
        'mnt': 'Mantle',
        'mantle': 'Mantle',
        'bsc': 'BSC'
    }
    return chain_mapping.get(chain.lower(), chain.capitalize())

# Función para filtrar datos de DeFiLlama según el contexto
def filter_defi_llama_data(data, context):
    """Filtra los resultados de DeFiLlama según el contexto actual"""
    filtered_data = data.copy()
    filters_applied = []

    # Aplicar filtros por blockchain
    if context.get('chain'):
        chain = normalize_chain_name(context['chain'])
        filtered_data = [p for p in filtered_data if p['chain'].lower() == chain.lower()]
        filters_applied.append(f"Blockchain: {chain}")

    # Aplicar filtros por APY mínimo
    if context.get('min_apy') is not None:
        filtered_data = [p for p in filtered_data if p['apy'] >= context['min_apy']]
        filters_applied.append(f"Min APY: {context['min_apy']:.2f}%")

    # Aplicar filtros por TVL mínimo
    if context.get('min_tvl') is not None:
        filtered_data = [p for p in filtered_data if p['tvlUsd'] >= context['min_tvl']]
        filters_applied.append(f"Min TVL: ${context['min_tvl']:,.2f}")

    # Aplicar filtros por protocolo
    if context.get('protocol'):
        filtered_data = [p for p in filtered_data if context['protocol'].lower() in p['project'].lower()]
        filters_applied.append(f"Protocol: {context['protocol']}")

    # Aplicar filtros por token
    if context.get('token'):
        # Para tokens, buscar coincidencias parciales
        token = context['token'].upper()
        filtered_data = [p for p in filtered_data if token in p['symbol'].upper()]
        filters_applied.append(f"Token: {token}")

    # Aplicar filtros por tipo
    if context.get('type') == 'Yield':
        # Para tipo Yield, preferir exposición única
        filtered_data = [p for p in filtered_data if p.get('exposure') == 'single']
        filters_applied.append(f"Type: Yield (single exposure)")
    elif context.get('type') == 'Liquidity Pool':
        # Para Liquidity Pools, preferir exposición múltiple
        filtered_data = [p for p in filtered_data if p.get('exposure') != 'single']
        filters_applied.append(f"Type: Liquidity Pool (multiple exposure)")

    # Ordenar por APY descendente
    filtered_data.sort(key=lambda x: x['apy'], reverse=True)

    # Limitar a 10 resultados para mejorar visualización
    filtered_data = filtered_data[:10]

    return filtered_data, filters_applied

# Función para procesar consultas del usuario
def process_user_query(query):
    """Procesa consultas del usuario, actualiza el contexto y realiza búsquedas"""
    # Añadir consulta al historial
    st.session_state.context['query_history'].append(query)

    # Normalizar consulta
    query = query.lower()
    context_updated = False

    # Detectar referencias a posiciones específicas
    position_match = re.search(r'posici[oó]n\s+(\d+)', query)
    if position_match:
        pos = int(position_match.group(1))
        # Verificar que la posición existe en el portafolio
        if pos < len(st.session_state.portfolio):
            position = st.session_state.portfolio[pos]
            st.session_state.context['position'] = pos
            st.session_state.context['chain'] = position['blockchain']
            st.session_state.context['protocol'] = position['protocol']
            st.session_state.context['token'] = position['token']
            st.session_state.context['type'] = position['type']
            context_updated = True

            # Mensaje sobre la posición seleccionada
            position_msg = f"He seleccionado tu posición {pos}: {position['token']} en {position['protocol']} ({position['blockchain']})"
            st.session_state.messages.append({"role": "assistant", "content": position_msg})

    # Detectar solicitudes de blockchain específica
    chain_match = re.search(r'(?:en|blockchain|chain|cadena)\s+(\w+)', query)
    if chain_match:
        chain = chain_match.group(1)
        st.session_state.context['chain'] = chain
        context_updated = True

    # Detectar solicitudes de APY mayor
    if any(term in query for term in ['más apy', 'mayor apy', 'mejor apy', 'apy más alto']):
        # Si tenemos alternativas, usar el APY más alto como referencia
        if st.session_state.alternatives:
            current_apy = st.session_state.alternatives[0]['apy']
            st.session_state.context['min_apy'] = current_apy
        else:
            # Valor predeterminado si no hay referencia
            st.session_state.context['min_apy'] = 5.0
        context_updated = True

    # Detectar solicitudes de TVL mayor
    if any(term in query for term in ['más tvl', 'mayor tvl', 'mejor tvl', 'tvl más alto']):
        # Si tenemos alternativas, usar el TVL más alto como referencia
        if st.session_state.alternatives:
            current_tvl = st.session_state.alternatives[0]['tvlUsd']
            st.session_state.context['min_tvl'] = current_tvl
        else:
            # Valor predeterminado si no hay referencia
            st.session_state.context['min_tvl'] = 100000  # $100K
        context_updated = True

    # Si el contexto se actualizó o no hay alternativas, consultar la API
    if context_updated or not st.session_state.alternatives:
        with st.spinner('Consultando alternativas en DeFiLlama...'):
            # Consultar la API de DeFiLlama
            llama_data = get_defi_llama_yields()

            if "error" in llama_data:
                error_msg = f"Error al consultar la API: {llama_data['error']}"
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                return

            # Obtener datos y filtrar según contexto
            data = llama_data.get("data", [])
            filtered_data, filters_applied = filter_defi_llama_data(data, st.session_state.context)

            # Guardar alternativas y filtros
            st.session_state.alternatives = filtered_data
            st.session_state.context['filters'] = filters_applied

            # Añadir mensaje con resultados
            if filtered_data:
                result_msg = f"He encontrado {len(filtered_data)} alternativas basadas en tus criterios."
                if filters_applied:
                    result_msg += f" Filtros aplicados: {', '.join(filters_applied)}"
                st.session_state.messages.append({"role": "assistant", "content": result_msg})
            else:
                no_results_msg = "No encontré alternativas que cumplan con todos tus criterios. Intenta con filtros menos restrictivos."
                st.session_state.messages.append({"role": "assistant", "content": no_results_msg})

# Diseño de la interfaz de usuario
st.title("🚀 Explorador de Alternativas DeFi")

# Diseño en columnas
col1, col2 = st.columns([1, 2])

# Columna 1: Portafolio y Contexto
with col1:
    st.subheader("📊 Mi Portafolio")
    # Crear DataFrame para mostrar el portafolio
    portfolio_df = pd.DataFrame(st.session_state.portfolio)
    # Formateamos el valor para mejor visualización
    portfolio_df['value'] = portfolio_df['value'].apply(lambda x: f"${x:,.2f}")
    st.dataframe(portfolio_df, hide_index=True)

    st.subheader("🔍 Contexto Actual")
    # Mostrar posición seleccionada y contexto actual
    if st.session_state.context['position'] is not None:
        pos = st.session_state.context['position']
        position = st.session_state.portfolio[pos]

        st.markdown(f"""
        **Posición seleccionada:** {pos}
        **Wallet:** {position['wallet']}
        **Blockchain:** {position['blockchain']}
        **Protocolo:** {position['protocol']}
        **Tipo:** {position['type']}
        **Token:** {position['token']}
        **Valor:** ${position['value']}
        """)
    else:
        st.info("Aún no has seleccionado ninguna posición de tu portafolio.")

    # Mostrar filtros aplicados
    st.subheader("🏷️ Filtros Aplicados")
    if st.session_state.context['filters']:
        for filter_item in st.session_state.context['filters']:
            st.markdown(f"- {filter_item}")
    else:
        st.markdown("No hay filtros aplicados.")

    # Historial de consultas
    st.subheader("📝 Historial de Consultas")
    if st.session_state.context['query_history']:
        for idx, query in enumerate(st.session_state.context['query_history'], 1):
            st.markdown(f"{idx}. {query}")
    else:
        st.markdown("No hay consultas registradas.")

# Columna 2: Chat y Alternativas
with col2:
    # Área de chat
    st.subheader("💬 Chat")
    chat_container = st.container()

    with chat_container:
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f"**Usuario:** {message['content']}")
            else:
                st.markdown(f"**Asistente:** {message['content']}")

    # Alternativas de inversión
    st.subheader("💰 Alternativas de Inversión")
    if st.session_state.alternatives:
        # Preparar datos para mostrar
        display_data = []
        for alt in st.session_state.alternatives:
            display_data.append({
                'Chain': alt['chain'],
                'Protocol': alt['project'],
                'Token': alt['symbol'],
                'APY (%)': round(alt['apy'], 2),
                'TVL (USD)': f"${alt['tvlUsd']:,.2f}",
                'Exposure': alt.get('exposure', 'N/A'),
                'IL Risk': alt.get('ilRisk', 'N/A')
            })

        # Mostrar como DataFrame
        alt_df = pd.DataFrame(display_data)
        st.dataframe(alt_df, hide_index=True)
    else:
        st.info("Aún no hay alternativas para mostrar. Haz una consulta en el chat.")

    # Formulario para consultas del usuario
    with st.form(key="query_form"):
        user_query = st.text_input("Escribe tu consulta (por ejemplo: 'Busca alternativas a mi posición 0 con mayor APY')", key="query_input")
        submit_button = st.form_submit_button("Enviar Consulta")

        if submit_button and user_query:
            # Añadir mensaje del usuario al chat
            st.session_state.messages.append({"role": "user", "content": user_query})

            # Procesar la consulta
            process_user_query(user_query)

            # Recargar para actualizar la UI
            st.rerun()

# Información para depuración (opcional)
with st.expander("Ver Estado del Contexto (Debug)"):
    st.json(st.session_state.context)
