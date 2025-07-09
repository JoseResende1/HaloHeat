# settings.py
import json

SETTINGS_FILE = "settings.json"

def save_settings(state):
    settings = {
        "percentage": state.percentage,
        "comfort_mode": state.comfort_mode,
        "online_temperature_thresholds": state.online_temperature_thresholds
    }
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
        print("Configurações salvas com sucesso!")
    except Exception as e:
        print("Erro ao salvar configurações:", e)

def load_settings(state):
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
        state.percentage = settings.get("percentage", state.percentage)
        state.comfort_mode = settings.get("comfort_mode", state.comfort_mode)
        state.online_temperature_thresholds = settings.get("online_temperature_thresholds", state.online_temperature_thresholds)
        print("Configurações carregadas:", settings)
    except Exception as e:
        print("Não foi possível carregar configurações. Usando valores padrão.", e)
