import utime
import _thread
from machine import Pin
import neopixel
import state
from regulation import calc_effective_percentage  # Função comum

# Configuração dos pinos e LEDs
zero_cross_pin = Pin(27, Pin.IN)
triac_trigger_pin = Pin(14, Pin.OUT)
led_pin = 23
num_leds = 8
np = neopixel.NeoPixel(Pin(led_pin), num_leds)

def trigger_triac():
    triac_trigger_pin.on()
    utime.sleep_us(200)
    triac_trigger_pin.off()

def update_leds(perc):
    num_active_leds = round((perc / 100) * num_leds)
    for i in range(num_leds):
        if i < num_active_leds:
            np[i] = (0, 3, 0)
        else:
            np[i] = (0, 0, 0)
    np.write()

def triac_control_thread():
    while True:
        # Enquanto não estiver no estado operacional (por exemplo, em menus), suspende o disparo
        if state.menu_state != "OPERATIONAL":
            utime.sleep_ms(50)
            continue

        # Aguarda zero-crossing
        while zero_cross_pin.value() == 0:
            pass
        while zero_cross_pin.value() == 1:
            pass
        utime.sleep_us(10)

        with state.lock:
            base_percentage = state.percentage
            current_temperature = state.temperature
            comfort_mode = state.comfort_mode
            triac_on_local = state.triac_on

        # Calcula a potência efetiva usando a função comum
        effective_percentage = calc_effective_percentage(base_percentage, current_temperature, comfort_mode)
        #print(effective_percentage)
        
        # Cálculo do delay (exemplo simplificado)
        if effective_percentage <= 0 or not triac_on_local:
            delay = -1
        elif effective_percentage >= 100:
            delay = 10
        else:
            delay = int((100 - effective_percentage) * 100)

        #print(f"[TRIAC] Base: {base_percentage}%, Effective: {effective_percentage:.1f}%, Temp: {current_temperature}, Delay: {delay} us")
        if delay > 0:
            utime.sleep_us(delay)
            trigger_triac()

