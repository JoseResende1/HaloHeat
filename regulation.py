import state

def calc_effective_percentage(base_percentage, temperature, comfort_mode):
    """
    Calcula a potência efetiva com base na potência base, temperatura e modo de conforto.
    
    Se operating_mode é "ONLINE", usa os limites definidos em state.online_temperature_thresholds.
    Caso contrário, usa os limites padrão.
    """
    # Se não houver leitura de temperatura, retorna a potência base
    if temperature is None:
        return base_percentage

    if state.operating_mode == "ONLINE":
        thresholds = state.online_temperature_thresholds.get(comfort_mode, (16, 18))
    else:
        thresholds = state.DEFAULT_TEMPERATURE_THRESHOLDS.get(comfort_mode, (16, 18))
    
    low, high = thresholds

    if temperature <= low:
        return base_percentage
    elif temperature >= high:
        return 0
    else:
        # Regulação linear: entre low e high, a potência diminui de base_percentage até 0
        factor = 1 - ((temperature - low) / (high - low))
        return base_percentage * factor
