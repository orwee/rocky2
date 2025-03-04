def filter_defi_llama_data(data, context):
    """Filtra los resultados de DeFiLlama según el contexto actual"""
    filtered_data = data.copy()
    filters_applied = []

    # Aplicar filtros por blockchain de manera más flexible
    if context.get('chain'):
        chain = normalize_chain_name(context['chain'])
        # Más flexible: buscar subcadenas en lugar de coincidencia exacta
        chain_matches = [p for p in filtered_data if chain.lower() in p['chain'].lower()]
        # Si no hay coincidencias, mantener todos los datos
        if chain_matches:
            filtered_data = chain_matches
            filters_applied.append(f"Blockchain: {chain}")

    # Aplicar filtros por token de manera más flexible para USDC
    if context.get('token'):
        token = context['token'].upper()
        # Caso especial para USDC en distintas cadenas
        if token == "USDC":
            token_matches = [p for p in filtered_data if
                            any(t in p['symbol'].upper() for t in ["USDC", "USDC.E", "AXLUSDC"])]
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

    # Ordenar por APY descendente
    filtered_data.sort(key=lambda x: x['apy'], reverse=True)

    # Limitar a 10 resultados para mejorar visualización
    filtered_data = filtered_data[:10]

    return filtered_data, filters_applied
