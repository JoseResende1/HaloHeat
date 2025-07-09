import json
import os

CONFIG_FILE = "wifi_config.json"

def load_wifi_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

def save_wifi_config(ssid, password, hostname):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"ssid": ssid, "password": password, "hostname": hostname}, f)
    print("Sucesso a gravar")

def reset_wifi_config():
    try:
        os.remove(CONFIG_FILE)
    except:
        pass
