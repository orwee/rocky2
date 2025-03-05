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
            "value": 288.083017,
            "apy": 5.2,  # APY inicial para la posición 0
            "tvl": 500000  # TVL inicial para la posición 0
        },
        {
            "num_posicion": 1,
            "wallet": "Wallet #1",
            "blockchain": "mnt",
            "protocol": "Pendle V2",
            "type": "Liquidity Pool",
            "token": "cmETH/PT-cmETH",
            "value": 318.715554,
            "apy": 8.7,  # APY inicial para la posición 1
            "tvl": 750000  # TVL inicial para la posición 1
        }
    ]
else:
    # Verificar que cada posición tenga los campos apy y tvl
    for position in st.session_state.portfolio:
        if 'apy' not in position:
            position['apy'] = 5.0  # Valor predeterminado
        if 'tvl' not in position:
            position['tvl'] = 100000  # Valor predeterminado

# Inicializar variables de contexto
if 'context' not in st.session_state:
    st.session_state.context = {
        'position': None,
        'chain': None,
        'protocol': None,
        'token': None,
        'type': None,
        'min_apy': 0.0,  # Valor inicial para APY
        'min_tvl': 0.0,  # Valor inicial para TVL
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
    """Filtra los resultados de DeFiLlama de forma progresiva con diagnóstico"""
    original_data = data.copy()
    filtered_data = data.copy()
    filters_applied = []
    intermediate_counts = {"Datos originales": len(filtered_data)}

    # Aplicar filtro de blockchain primero (si existe)
    if context.get('chain'):
        chain = normalize_chain_name(context['chain'])
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

        # Actualizar filtrados sólo si encontramos resultados
        if chain_filtered:
            filtered_data = chain_filtered

    # Aplicar filtro de token (si existe)
    if context.get('token') and filtered_data:
        token = context['token'].upper()
        token_filtered = [p for p in filtered_data if token in p['symbol'].upper()]
        intermediate_counts["Después de filtrar por token"] = len(token_filtered)

        # Si hay resultados, actualizar datos filtrados
        if token_filtered:
            filtered_data = token_filtered
            filters_applied.append(f"Token: contiene '{token}'")
        else:
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

    # Limitar a 10 resultados
    filtered_data = filtered_
