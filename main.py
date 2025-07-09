import _thread
import time
import uasyncio as asyncio
import wifi_manager
import triac_control
import button_control
import server
import state
import settings
import temperature_sensor  # módulo que lê a temperatura do DS18B20

def main():
    settings.load_settings(state)
    wifi_active = wifi_manager.connect_to_wifi()

    # Verifica atualizações OTA se estiver ligado ao Wi-Fi
    if wifi_active:
        try:
            import ota_updater
            ota_updater.update()
        except Exception as e:
            print(f"[OTA] Erro ao verificar atualizações: {e}")

    # Inicia as threads do TRIAC, botão e temperatura
    _thread.start_new_thread(triac_control.triac_control_thread, ())
    _thread.start_new_thread(button_control.button_control_thread, ())
    _thread.start_new_thread(temperature_sensor.temperature_thread, ())

    if wifi_active:
        print("[ESP32] Sistema iniciado com Wi-Fi!")
        asyncio.run(server.main_http_server())
    else:
        print("[ESP32] Sistema iniciado em modo standalone!")
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()


