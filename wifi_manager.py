import time
import network
import socket
import machine
from machine import Pin
import config
import neopixel
import state

# Parâmetros
timeout_botao = 1.5  # tempo de botão pressionado para forçar standalone
timeout_wifi = 40

button_pin = Pin(26, Pin.IN, Pin.PULL_DOWN)
led_pin = 23
num_leds = 8
np = neopixel.NeoPixel(Pin(led_pin), num_leds)
for i in range(num_leds):
    np[i] = (0, 0, 0)
np.write()

state.triac_on = False

def fade_led(index, color, delay=0.01, steps=50):
    r, g, b = color
    min_brightness = 0.05
    max_brightness = 0.7

    for i in range(steps + 1):
        factor = min_brightness + (i / steps) * (max_brightness - min_brightness)
        np[index] = (int(r * factor), int(g * factor), int(b * factor))
        np.write()
        time.sleep(delay)

    for i in range(steps, -1, -1):
        factor = min_brightness + (i / steps) * (max_brightness - min_brightness)
        np[index] = (int(r * factor), int(g * factor), int(b * factor))
        np.write()
        time.sleep(delay)


def check_abort_button(timeout=timeout_botao):
    start = time.ticks_ms()
    blink_state = False
    blink_interval = 300
    last_blink = time.ticks_ms()

    while button_pin.value() == 1:
        elapsed = time.ticks_diff(time.ticks_ms(), start)

        if elapsed >= 15000:
            print("[Botão] Reset Wi-Fi após 15s.")
            config.reset_wifi_config()
            for _ in range(3):
                np[0] = (30, 0, 30)  # roxo
                np.write()
                time.sleep(0.3)
                np[0] = (0, 0, 0)
                np.write()
                time.sleep(0.3)
            machine.reset()
            return False

        elif elapsed >= timeout * 1000:
            if time.ticks_diff(time.ticks_ms(), last_blink) > blink_interval:
                blink_state = not blink_state
                np[0] = (20, 0, 0) if blink_state else (0, 0, 0)
                np.write()
                last_blink = time.ticks_ms()

        time.sleep(0.05)

    elapsed = time.ticks_diff(time.ticks_ms(), start)
    if elapsed >= timeout * 1000:
        print("[Botão] Abort solicitado via botão.")
        for _ in range(4):
            np[0] = (20, 0, 0)
            np.write()
            time.sleep(0.2)
            np[0] = (0, 0, 0)
            np.write()
            time.sleep(0.2)
        return True

    return False


def start_access_point():
    import _thread

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="ESP32_Setup", password="12345678")
    ap.ifconfig(('10.0.0.1', '255.255.255.0', '10.0.0.1', '10.0.0.1'))
    print("[Wi-Fi] Access Point iniciado. Aguardando ligação em http://10.0.0.1")

    def dns_server():
        import socket
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind(("0.0.0.0", 53))
        while True:
            try:
                data, addr = udp.recvfrom(512)
                # Resposta padrão para qualquer domínio
                dns_response = (
                    data[:2] + b'\x81\x80' + data[4:6]*2 +
                    b'\x00\x00\x00\x00' + data[12:] +
                    b'\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04' +
                    bytes(map(int, ap.ifconfig()[0].split('.')))
                )
                udp.sendto(dns_response, addr)
            except Exception as e:
                print("[DNS] Erro:", e)

    _thread.start_new_thread(dns_server, ())

    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(5)
    s.settimeout(1)

    start_time = time.time()
    while time.time() - start_time < timeout_wifi:
        fade_led(0, (0, 0, 40), delay=0.01, steps=50)
        if check_abort_button():
            print("[AP] Abort manual. Entrando em modo standalone.")
            s.close()
            ap.active(False)
            state.operating_mode = "STANDALONE"
            state.menu_state = "OPERATIONAL"
            np[0] = (50, 0, 0)
            np.write()
            return False

        try:
            conn, addr = s.accept()
            request = conn.recv(1024).decode('utf-8')
            print(f"[AP] Conexão recebida de {addr}")
            print("Request:", request)

            if "POST /configure" in request:
                body = request.split('\r\n\r\n')[1]
                params = dict(x.split('=') for x in body.split('&'))
                data = {
                    "ssid": params["ssid"],
                    "password": params["password"],
                    "hostname": params["hostname"]
                }
                config.save_wifi_config(data['ssid'], data['password'], data['hostname'])
                response = "HTTP/1.1 200 OK\nContent-Type: application/json\n\n{\"status\": \"success\", \"message\": \"Configuração salva. Reiniciando...\"}"
                conn.send(response)
                conn.close()
                time.sleep(2)
                machine.reset()

            elif (
                "generate_204" in request or
                "hotspot-detect.html" in request or
                "connecttest.txt" in request or
                "ncsi.txt" in request or
                "captive.apple.com" in request or
                "GET / HTTP" in request or
                "Host:" in request
            ):
                html = """
                <html>
                  <head>
                    <meta charset="UTF-8">
                    <title>Configurar Wi-Fi</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                      body {
                        background: linear-gradient(to right, #005AA7, #FFFDE4);
                        font-family: 'Segoe UI', sans-serif;
                        margin: 0;
                        padding: 0;
                      }
                      .container {
                        max-width: 400px;
                        margin: 60px auto;
                        background: white;
                        padding: 30px;
                        border-radius: 12px;
                        box-shadow: 0 8px 16px rgba(0,0,0,0.2);
                      }
                      h1 {
                        text-align: center;
                        color: #005AA7;
                        margin-bottom: 24px;
                      }
                      label {
                        font-weight: bold;
                        display: block;
                        margin: 12px 0 6px;
                        color: #333;
                      }
                      input {
                        width: 100%;
                        padding: 10px;
                        font-size: 16px;
                        border: 1px solid #ccc;
                        border-radius: 6px;
                        box-sizing: border-box;
                      }
                      button {
                        margin-top: 20px;
                        width: 100%;
                        padding: 12px;
                        background-color: #005AA7;
                        color: white;
                        font-size: 18px;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        transition: background-color 0.3s ease;
                      }
                      button:hover {
                        background-color: #003f7d;
                      }
                      .footer {
                        text-align: center;
                        font-size: 14px;
                        color: #666;
                        margin-top: 20px;
                      }
                    </style>
                  </head>
                  <body>
                    <div class="container">
                      <h1>Configurar Wi-Fi</h1>
                      <form method="post" action="/configure">
                        <label for="ssid">Nome da Rede (SSID):</label>
                        <input type="text" name="ssid" required>

                        <label for="password">Password:</label>
                        <input type="password" name="password" required>

                        <label for="hostname">Hostname:</label>
                        <input type="text" name="hostname" placeholder="esp32" required>

                        <button type="submit">Guardar e Ligar</button>
                      </form>
                      <div class="footer">Halo Heat &copy; 2025</div>
                    </div>
                  </body>
                </html>
                """

                response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
                conn.send(response)
                conn.close()

            else:
                response = "HTTP/1.1 302 Found\r\nLocation: /\r\n\r\n"
                conn.send(response)
                conn.close()

        except OSError:
            continue




    print("[AP] Tempo esgotado. Nenhuma ligação efetuada.")
    s.close()
    ap.active(False)
    state.operating_mode = "STANDALONE"
    state.menu_state = "BLOQUEADO"
    return False


def connect_to_wifi():
    config_data = config.load_wifi_config()

    if not config_data:
        print("[Wi-Fi] Nenhuma configuração encontrada. Iniciando modo configuração (AP)...")
        if not start_access_point():
            print("[Wi-Fi] Nenhuma ligação efetuada. Entrando em modo standalone.")
            state.operating_mode = "STANDALONE"
            state.menu_state = "BLOQUEADO"
            fade_led(0, (50, 0, 0), delay=0.01, steps=50)
            return False

    ssid = config_data["ssid"]
    password = config_data["password"]
    hostname = config_data["hostname"]
    print("[Wi-Fi] Dados da configuração encontrados:")
    print(ssid, password, hostname)

    station = network.WLAN(network.STA_IF)
    time.sleep(1)
    station.active(True)
    station.config(dhcp_hostname=hostname)
    station.connect(ssid, password)
    print(f"[Wi-Fi] Conectando-se à rede '{ssid}'...")

    start_time = time.time()
    while not station.isconnected():
        fade_led(0, (0, 50, 0), delay=0.01, steps=50)
        if check_abort_button():
            print("[Wi-Fi] Aborto manual. Entrando em modo standalone.")
            state.operating_mode = "STANDALONE"
            state.menu_state = "OPERATIONAL"
            np[0] = (50, 0, 0)
            np.write()
            return False

        if time.time() - start_time > timeout_wifi:
            print("[Wi-Fi] Falha ao conectar. Entrando em modo standalone.")
            for _ in range(4):
                np[0] = (20, 0, 0)
                np.write()
                time.sleep(0.2)
                np[0] = (0, 0, 0)
                np.write()
                time.sleep(0.2)
            station.active(False)
            state.operating_mode = "STANDALONE"
            state.menu_state = "BLOQUEADO"
            return False

    print(f"[Wi-Fi] Conectado com sucesso! Endereço IP: {station.ifconfig()[0]}")
    print("Hostname mDNS:", station.config("dhcp_hostname"))
    state.operating_mode = "ONLINE"
    state.menu_state = "BLOQUEADO"

    for _ in range(4):
        np[0] = (0, 20, 0)
        np.write()
        time.sleep(0.2)
        np[0] = (0, 0, 0)
        np.write()
        time.sleep(0.2)
    return True
