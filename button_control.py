import utime
import _thread
import machine
from machine import Pin
import config
import state
import neopixel

# Configuração dos LEDs e botão
np = neopixel.NeoPixel(Pin(23), 8)
button_pin = Pin(26, Pin.IN, Pin.PULL_DOWN)

# Parâmetros
LONG_PRESS_DURATION = 1500  # 5s para standby/reset
MENU_TIMEOUT = 4000         # Timeout dos menus

def update_comfort_led():
    """ Atualiza o LED 0 com base no modo atual """
    if not state.triac_on:
        np[0] = (1, 0, 0)  # standby: vermelho fixo
    elif state.comfort_mode == "TEMPERATE":
        np[0] = (3, 3, 0)
    elif state.comfort_mode == "MEDIUM":
        np[0] = (4, 2, 0)
    elif state.comfort_mode == "WARM":
        np[0] = (5, 1, 0)
    else:
        np[0] = (0, 0, 0)
    np.write()

def unlock_effect():
    steps = 40
    for i in range(steps + 1):
        r = int(10 - (10 * i / steps))
        g = int(0 + (40 * i / steps))
        np[0] = (r, g, 0)
        np.write()
        utime.sleep_ms(15)
    for _ in range(3):
        np[0] = (0, 20, 0)
        np.write()
        utime.sleep_ms(100)
        np[0] = (0, 0, 0)
        np.write()
        utime.sleep_ms(100)

def button_control_thread():
    last_menu_state = None
    last_blink_time = utime.ticks_ms()
    blink_state = False

    last_comfort_mode_shown = None
    last_comfort_check = utime.ticks_ms()

    while True:
        now = utime.ticks_ms()

        # === Atualiza LED se houver mudança de estado ===
        if state.menu_state != last_menu_state:
            print(f"[STATE] {last_menu_state} -> {state.menu_state}")
            last_menu_state = state.menu_state
            blink_state = False
            update_comfort_led()
            last_comfort_mode_shown = state.comfort_mode
            if state.menu_state == "BLOQUEADO":
                np[0] = (3, 0, 5)
                np.write()

        # === Atualização periódica de LED no modo OPERATIONAL ===
        if state.menu_state == "OPERATIONAL" and state.triac_on:
            if utime.ticks_diff(now, last_comfort_check) > 1000:
                last_comfort_check = now
                if state.comfort_mode != last_comfort_mode_shown:
                    update_comfort_led()
                    last_comfort_mode_shown = state.comfort_mode

        # === LED pisca no menu conforto ===
        if state.menu_state == "MENU_CONFORTO" and state.triac_on:
            if utime.ticks_diff(now, last_blink_time) > 200:
                blink_state = not blink_state
                if blink_state:
                    update_comfort_led()
                else:
                    np[0] = (0, 0, 0)
                    np.write()
                last_blink_time = now

        # === BOTÃO PRESSIONADO ===
        if button_pin.value() == 1:
            utime.sleep_ms(50)
            press_time = utime.ticks_ms()
            while button_pin.value() == 1:
                elapsed = utime.ticks_diff(utime.ticks_ms(), press_time)
                if elapsed > LONG_PRESS_DURATION:
                    if state.menu_state == "BLOQUEADO":
                        print("[BOTÃO] Desbloqueio por 5s")
                        unlock_effect()
                        with state.lock:
                            state.menu_state = "OPERATIONAL"
                            state.triac_on = True
                    elif not state.triac_on:
                        print("[BOTÃO] Saindo de standby")
                        with state.lock:
                            state.triac_on = True
                            state.menu_state = "OPERATIONAL"
                            # A percentagem volta a ser 100%, mas será modulada pela temperatura
                            state.percentage = 100
                        update_comfort_led()
                    else:
                        print("[BOTÃO] Entrando em standby")
                        with state.lock:
                            state.triac_on = False
                            state.percentage = 0
                            state.menu_state = "OPERATIONAL"  # mantém OPERATIONAL
                    update_comfort_led()
                    break  # evita processamento de clique curto
                utime.sleep_ms(10)
            else:
                # Clique curto
                release_time = utime.ticks_ms()

                if state.menu_state == "OPERATIONAL" and state.triac_on:
                    print("[OPERATIONAL] Entrando em ajuste de conforto")
                    state.menu_state = "MENU_CONFORTO"
                    state.last_menu_time = release_time

                elif state.menu_state == "MENU_CONFORTO" and state.triac_on:
                    if state.comfort_mode == "TEMPERATE":
                        state.comfort_mode = "MEDIUM"
                    elif state.comfort_mode == "MEDIUM":
                        state.comfort_mode = "WARM"
                    else:
                        state.comfort_mode = "TEMPERATE"
                    print("[MENU_CONFORTO] Novo modo:", state.comfort_mode)
                    state.last_menu_time = release_time
                    update_comfort_led()

        # === Timeout do menu de conforto ===
        if state.menu_state == "MENU_CONFORTO":
            if utime.ticks_diff(now, state.last_menu_time) > MENU_TIMEOUT:
                print("[MENU_CONFORTO] Timeout – Voltando para OPERATIONAL")
                state.menu_state = "OPERATIONAL"

        utime.sleep_ms(20)