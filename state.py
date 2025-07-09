import _thread
lock = _thread.allocate_lock()

operating_mode = "STANDALONE"      # ou "ONLINE"
menu_state = "BLOQUEADO"         # "OPERATIONAL", "MENU_AJUSTE", "MENU_TRIAC", "MENU_CONFORTO"
last_menu_time = 0
percentage = 0
triac_on = True
triac_click_count = 0
comfort_mode = "TEMPERATE"         # "TEMPERATE", "MEDIUM", "WARM"
temperature_ds = None
ir_temperature = None
# Limites padrão (para standalone)
DEFAULT_TEMPERATURE_THRESHOLDS = {
    "TEMPERATE": (16, 18),
    "MEDIUM": (18, 20),
    "WARM": (23, 27)
}

# Limites para uso no modo ONLINE (modificáveis via API)
online_temperature_thresholds = {
    "TEMPERATE": (16, 18),
    "MEDIUM": (18, 20),
    "WARM": (20, 22)
}
