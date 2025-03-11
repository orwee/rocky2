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
            "num_posicion": 1,
            "wallet": "Wallet #1",
            "blockchain": "mnt",
            "protocol": "Pendle V2",
            "type": "Liquidity Pool",
            "token": "cmETH/PT-cmETH",
            "value": 318.715554
        },
        {
            "num_posicion": 0,
            "wallet": "Wallet #1",
            "blockchain": "avax",
            "protocol": "Struct Finance",
            "type": "Yield",
            "token": "USDC",
            "value": 288.083017
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

if 'debug_info' not in st.session_state:
    st.session_state.debug_info = {
        "intermediate_counts": {},
        "final_count": 0
    }

# Función mejorada para normalizar nombres de blockchain
def normalize_chain_name(chain):
    chain_mapping = {
        'avax': 'Avalanche',
        'avalanche': 'Avalanche',
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
        'bsc': 'BSC',
        'binance': 'BSC'
    }
    return chain_mapping.get(chain.lower(), chain.capitalize())

# Función mejorada para filtrar datos de DeFiLlama con enfoque progresivo
def filter_defi_llama_data(data, context):
    """Filtra los resultados de DeFiLlama según el contexto actual"""
    """Filtra los resultados de DeFiLlama de forma progresiva con diagnóstico"""
    original_data = data.copy()
    filtered_data = data.copy()
    filters_applied = []
    intermediate_counts = {"Datos originales": len(filtered_data)}

    # Aplicar filtros por blockchain de manera más flexible
    # Aplicar filtro de blockchain primero (si existe)
    if context.get('chain'):
        chain = normalize_chain_name(context['chain'])
        # Más flexible: buscar subcadenas en lugar de coincidencia exacta
        chain_matches = [p for p in filtered_data if chain.lower() in p['chain'].lower()]
        # Si no hay coincidencias, mantener todos los datos
        if chain_matches:
            filtered_data = chain_matches
        chain_filtered = [p for p in filtered_data if p['chain'].lower() == chain.lower()]
        intermediate_counts["Después de filtrar por blockchain"] = len(chain_filtered)

        # Si no hay resultados, intentar una búsqueda más flexible
        if not chain_filtered:
            chain_filtered = [p for p in original_data if context['chain'].lower() in p['chain'].lower()]
            if chain_filtered:
                filters_applied.append(f"Blockchain: contiene '{context['chain']}'")
                intermediate_counts["Después de filtrar por blockchain (flexible)"] = len(chain_filtered)
        else:
            filters_applied.append(f"Blockchain: {chain}")

    # Aplicar filtros por token de manera más flexible para USDC
    if context.get('token'):
        # Actualizar filtrados sólo si encontramos resultados
        if chain_filtered:
            filtered_data = chain_filtered

    # Aplicar filtro de token (si existe)
    if context.get('token') and filtered_data:
        token = context['token'].upper()
        # Caso especial para USDC en distintas cadenas
        if token == "USDC":
            token_matches = [p for p in filtered_data if
                            any(t in p['symbol'].upper() for t in ["USDC", "USDC.E", "AXLUSDC"])]
        token_filtered = [p for p in filtered_data if token in p['symbol'].upper()]
        intermediate_counts["Después de filtrar por token"] = len(token_filtered)

        # Si hay resultados, actualizar datos filtrados
        if token_filtered:
            filtered_data = token_filtered
            filters_applied.append(f"Token: contiene '{token}'")
        else:
            token_matches = [p for p in filtered_data if token in p['symbol'].upper()]

        # Si hay coincidencias de token, aplicar el filtro
        if token_matches:
            filtered_data = token_matches
            filters_applied.append(f"Token: {token}")

    # Aplicar filtros por APY mínimo
    if context.get('min_apy') is not None:
        filtered_data = [p for p in filtered_data if p['apy'] >= context['min_apy']]
        filters_applied.append(f"Min APY: {context['min_apy']:.2f}%")

    # Aplicar filtros por TVL mínimo
    if context.get('min_tvl') is not None:
        filtered_data = [p for p in filtered_data if p['tvlUsd'] >= context['min_tvl']]
        filters_applied.append(f"Min TVL: ${context['min_tvl']:,.2f}")

    # Aplicar filtros por protocolo (más flexible)
    if context.get('protocol'):
        protocol_matches = [p for p in filtered_data if context['protocol'].lower() in p['project'].lower()]
        if protocol_matches:
            filtered_data = protocol_matches
            # Si no hay resultados, intentar una búsqueda más flexible
            token_filtered = [p for p in filtered_data if any(token_part in p['symbol'].upper()
                                                            for token_part in token.split('/'))]
            if token_filtered:
                filtered_data = token_filtered
                filters_applied.append(f"Token: contiene parte de '{token}'")
                intermediate_counts["Después de filtrar por token (flexible)"] = len(token_filtered)

    # Aplicar filtro de protocolo (si existe)
    if context.get('protocol') and filtered_data:
        protocol = context['protocol'].lower()
        protocol_filtered = [p for p in filtered_data if protocol in p['project'].lower()]
        intermediate_counts["Después de filtrar por protocolo"] = len(protocol_filtered)

        if protocol_filtered:
            filtered_data = protocol_filtered
            filters_applied.append(f"Protocol: {context['protocol']}")

    # Aplicar filtros por tipo de manera opcional
    if context.get('type') == 'Yield':
        yield_matches = [p for p in filtered_data if p.get('exposure') == 'single']
        if yield_matches:
            filtered_data = yield_matches
            filters_applied.append(f"Type: Yield (single exposure)")
    elif context.get('type') == 'Liquidity Pool':
        lp_matches = [p for p in filtered_data if p.get('exposure') != 'single']
        if lp_matches:
            filtered_data = lp_matches
            filters_applied.append(f"Type: Liquidity Pool (multiple exposure)")
    # Aplicar filtro de tipo (si existe)
    if context.get('type') and filtered_data:
        if context['type'] == 'Yield':
            type_filtered = [p for p in filtered_data if p.get('exposure') == 'single']
            intermediate_counts["Después de filtrar por tipo Yield"] = len(type_filtered)
            if type_filtered:
                filtered_data = type_filtered
                filters_applied.append(f"Type: Yield (single exposure)")
        elif context['type'] == 'Liquidity Pool':
            type_filtered = [p for p in filtered_data if p.get('exposure') != 'single']
            intermediate_counts["Después de filtrar por tipo Liquidity Pool"] = len(type_filtered)
            if type_filtered:
                filtered_data = type_filtered
                filters_applied.append(f"Type: Liquidity Pool (multiple exposure)")

    # Aplicar filtro de TVL mínimo (si existe)
    if context.get('min_tvl') is not None and filtered_data:
        tvl_filtered = [p for p in filtered_data if p['tvlUsd'] >= context['min_tvl']]
        intermediate_counts["Después de filtrar por TVL mínimo"] = len(tvl_filtered)

        if tvl_filtered:
            filtered_data = tvl_filtered
            filters_applied.append(f"Min TVL: ${context['min_tvl']:,.2f}")
        else:
            # Si no hay resultados, intentar con la mitad del TVL mínimo
            relaxed_tvl = context['min_tvl'] / 2
            tvl_filtered = [p for p in filtered_data if p['tvlUsd'] >= relaxed_tvl]
            if tvl_filtered:
                filtered_data = tvl_filtered
                filters_applied.append(f"Min TVL: ${relaxed_tvl:,.2f} (reducido)")
                intermediate_counts["Después de reducir TVL mínimo"] = len(tvl_filtered)

    # Aplicar filtro de APY mínimo (si existe)
    if context.get('min_apy') is not None and filtered_data:
        apy_filtered = [p for p in filtered_data if p['apy'] >= context['min_apy']]
        intermediate_counts["Después de filtrar por APY mínimo"] = len(apy_filtered)

        if apy_filtered:
            filtered_data = apy_filtered
            filters_applied.append(f"Min APY: {context['min_apy']:.2f}%")
        else:
            # Si no hay resultados, intentar con la mitad del APY mínimo
            relaxed_apy = context['min_apy'] / 2
            apy_filtered = [p for p in filtered_data if p['apy'] >= relaxed_apy]
            if apy_filtered:
                filtered_data = apy_filtered
                filters_applied.append(f"Min APY: {relaxed_apy:.2f}% (reducido)")
                intermediate_counts["Después de reducir APY mínimo"] = len(apy_filtered)

    # Guardar información de diagnóstico
    st.session_state.debug_info = {
        "intermediate_counts": intermediate_counts,
        "final_count": len(filtered_data)
    }

    # Ordenar por APY descendente
    filtered_data.sort(key=lambda x: x['apy'], reverse=True)

    # Limitar a 10 resultados para mejorar visualización
    # Limitar a 10 resultados
    filtered_data = filtered_data[:10]

    return filtered_data, filters_applied

# Función mejorada para procesar consultas del usuario
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

    # Detectar protocolo específico
    protocol_match = re.search(r'(?:protocol|protocolo|en)\s+(\w+)', query)
    if protocol_match and protocol_match.group(1) not in ['en', 'la', 'el', 'los', 'las']:
        protocol = protocol_match.group(1)
        if protocol not in ['blockchain', 'chain', 'cadena']:  # Evitar conflicto con blockchain
            st.session_state.context['protocol'] = protocol
            context_updated = True

    # Detectar solicitudes de APY mayor
    if any(term in query for term in ['más apy', 'mayor apy', 'mejor apy', 'apy más alto']):
        # Si tenemos alternativas, usar el APY más alto como referencia
        if st.session_state.alternatives:
            current_apy = max([alt['apy'] for alt in st.session_state.alternatives[:3]])
            st.session_state.context['min_apy'] = current_apy
        else:
            # Buscar en la posición seleccionada o usar valor predeterminado
            if st.session_state.context['position'] is not None:
                # Aquí podríamos buscar el APY actual de la posición si estuviera disponible
                st.session_state.context['min_apy'] = 3.0  # Valor predeterminado bajo para encontrar resultados
            else:
                st.session_state.context['min_apy'] = 3.0
        context_updated = True

    # Detectar solicitudes de TVL mayor
    if any(term in query for term in ['más tvl', 'mayor tvl', 'mejor tvl', 'tvl más alto']):
        # Si tenemos alternativas, usar el TVL más alto como referencia
        if st.session_state.alternatives:
            current_tvl = max([alt['tvlUsd'] for alt in st.session_state.alternatives[:3]])
            st.session_state.context['min_tvl'] = current_tvl
        else:
            # Valor predeterminado
            st.session_state.context['min_tvl'] = 50000  # $50K
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
                # Mensaje de diagnóstico si no hay resultados
                diagnostic_msg = "No encontré alternativas que cumplan con todos tus criterios. "

                # Añadir información de diagnóstico
                if st.session_state.debug_info["intermediate_counts"]:
                    diagnostic_msg += "Diagnóstico de búsqueda:\n"
                    for step, count in st.session_state.debug_info["intermediate_counts"].items():
                        diagnostic_msg += f"- {step}: {count} resultados\n"

                    # Sugerencias según los resultados intermedios
                    if "Después de filtrar por blockchain" in st.session_state.debug_info["intermediate_counts"] and \
                       st.session_state.debug_info["intermediate_counts"]["Después de filtrar por blockchain"] == 0:
                        diagnostic_msg += "\nLa blockchain especificada no parece tener datos. Prueba con otra blockchain como 'Ethereum' o 'Arbitrum'."

                    elif "Después de filtrar por token" in st.session_state.debug_info["intermediate_counts"] and \
                        st.session_state.debug_info["intermediate_counts"]["Después de filtrar por token"] == 0:
                        diagnostic_msg += "\nNo encontré pools con ese token específico. Intenta con otros tokens populares como 'ETH', 'BTC' o 'USDC'."

                    elif "Después de filtrar por APY mínimo" in st.session_state.debug_info["intermediate_counts"] and \
                        st.session_state.debug_info["intermediate_counts"]["Después de filtrar por APY mínimo"] == 0:
                        diagnostic_msg += "\nEl APY solicitado es demasiado alto para las alternativas disponibles. Prueba sin filtrar por APY."

                st.session_state.messages.append({"role": "assistant", "content": diagnostic_msg})

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

    # Información de diagnóstico (para usuarios avanzados)
    with st.expander("🛠️ Diagnóstico de Búsqueda"):
        if st.session_state.debug_info["intermediate_counts"]:
            st.subheader("Proceso de Filtrado")
            for step, count in st.session_state.debug_info["intermediate_counts"].items():
                st.markdown(f"**{step}:** {count} resultados")
        else:
            st.info("No hay información de diagnóstico disponible todavía. Realiza una consulta primero.")

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

# Información para depuración (opcional, se puede quitar en producción)
with st.expander("Ver Estado del Contexto (Debug)"):
    st.json(st.session_state.context)
