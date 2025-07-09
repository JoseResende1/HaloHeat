import gc, sys, network, socket, uasyncio as asyncio, json, time, machine, os
from machine import Pin

SERVER_IP = '10.0.0.1'
SERVER_SUBNET = '255.255.255.0'
IS_UASYNCIO_V3 = hasattr(asyncio, "__version__") and asyncio.__version__ >= (3,)
HTML_FILE = "index.html"
CONFIG_FILE = "wifi_config.json"
RESET_PIN = 0  # GPIO0 (boot button)
FAIL_FLAG_FILE = "wifi_fail.flag"

reset_btn = Pin(RESET_PIN, Pin.IN, Pin.PULL_UP)

async def monitor_reset_button():
    pressed_time = 0
    while True:
        if reset_btn.value() == 0:
            pressed_time += 1
            if pressed_time > 5 * 10:
                print("[DEBUG] → Botão pressionado por >5s. Apagando config Wi-Fi...")
                if CONFIG_FILE in os.listdir():
                    os.remove(CONFIG_FILE)
                await asyncio.sleep(1)
                machine.reset()
        else:
            pressed_time = 0
        await asyncio.sleep_ms(100)

def wifi_start_ap():
    ap = network.WLAN(network.AP_IF)
    if not ap.active():
        print("[DEBUG] → Ativando Access Point...")
        ap.active(True)
        ap.ifconfig((SERVER_IP, SERVER_SUBNET, SERVER_IP, SERVER_IP))
        ap.config(essid="ConfigurarESP", authmode=network.AUTH_OPEN)
        print("[DEBUG] → AP ativo com config:", ap.ifconfig())
    else:
        print("[DEBUG] → AP já estava ativo. Ignorando reconfiguração.")

def scan_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    return [{"ssid": net[0].decode(), "rssi": net[3]} for net in sta.scan()]

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        f.write(json.dumps(data))

def clear_wifi_interfaces():
    ap = network.WLAN(network.AP_IF)
    sta = network.WLAN(network.STA_IF)
    ap.active(False)
    sta.disconnect()
    sta.active(False)
    time.sleep(1)

def test_wifi_connection(ssid, password, hostname):
    print(f"[DEBUG] → Iniciando teste de conexão Wi-Fi: SSID={ssid}, Hostname={hostname}")
    network.WLAN(network.AP_IF).active(False)
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    time.sleep(1)
    sta.disconnect()
    sta.config(dhcp_hostname=hostname)
    sta.connect(ssid, password)
    for i in range(30):
        print(f"[DEBUG] → Tentativa {i+1}/30 - Conectado: {sta.isconnected()}")
        if sta.isconnected():
            print("[DEBUG] → Conectado com IP:", sta.ifconfig()[0])
            return True
        time.sleep(0.5)
    print("[DEBUG] → Falha na conexão STA")
    sta.active(False)
    return False

class DNSQuery:
    def __init__(self, data):
        self.data = data
        self.domain = ''
        tipo = (data[2] >> 3) & 15
        if tipo == 0:
            ini = 12
            lon = data[ini]
            while lon != 0:
                self.domain += data[ini + 1:ini + lon + 1].decode() + '.'
                ini += lon + 1
                lon = data[ini]

    def response(self, ip):
        packet = self.data[:2] + b'\x81\x80'
        packet += self.data[4:6] + self.data[4:6] + b'\x00\x00\x00\x00'
        packet += self.data[12:]
        packet += b'\xC0\x0C'
        packet += b'\x00\x01\x00\x01\x00\x00\x00\x3C\x00\x04'
        packet += bytes(map(int, ip.split('.')))
        return packet

async def configure_wifi_from_http(data):
    ssid = data.get("ssid")
    pwd = data.get("password")
    hostname = data.get("hostname", "esp32")
    print(f"[DEBUG] → Configurar Wi-Fi recebido: SSID={ssid}, Hostname={hostname}")
    if test_wifi_connection(ssid, pwd, hostname):
        print("[DEBUG] → Conexão Wi-Fi bem-sucedida. Salvando configuração...")
        save_config(data)
        clear_wifi_interfaces()
        return True
    else:
        print("[DEBUG] → Falha ao conectar com os dados fornecidos.")
        return False

async def handle_http(reader, writer):
    try:
        req_line = await reader.readline()
        print("[DEBUG] → Linha de requisição:", req_line)
        if not req_line:
            return
        method, path, _ = req_line.decode().split()
        headers = {}
        while True:
            line = await reader.readline()
            if line == b'\r\n': break
            parts = line.decode().split(":", 1)
            if len(parts) == 2:
                headers[parts[0].strip().lower()] = parts[1].strip()

        print(f"[DEBUG] → Método: {method}, Caminho: {path}")

        if path == "/scan":
            res = json.dumps(scan_wifi())
            await writer.awrite("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n" + res)

        elif path == "/configure" and method == "POST":
            content_length = int(headers.get("content-length", 0))
            print(f"[DEBUG] → Content-Length: {content_length}")
            body = await reader.read(content_length)
            print(f"[DEBUG] → Corpo recebido: {body}")
            data = json.loads(body)
            try:
                await writer.awrite("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n")
                if await configure_wifi_from_http(data):
                    try:
                        await writer.awrite(json.dumps({"status": "ok"}))
                    except Exception as e:
                        print("[DEBUG] → Ignorando erro de escrita após sucesso:", type(e), e)
                    try:
                        await writer.aclose()
                    except Exception as e:
                        print("[DEBUG] → Ignorando erro ao fechar conexão:", type(e), e)
                    await asyncio.sleep(1)
                    machine.reset()
                    return
                else:
                    with open(FAIL_FLAG_FILE, "w") as f:
                        f.write("wifi_failed")
                    await writer.awrite(json.dumps({"status": "fail", "reason": "wifi_connection_failed"}))
            except Exception as e:
                print("[DEBUG] → Exceção em /configure:")
                sys.print_exception(e)
                await writer.awrite(json.dumps({"status": "error", "reason": str(e)}))
            finally:
                try:
                    await writer.aclose()
                except Exception as e:
                    print("[DEBUG] → Erro ao fechar socket:")
                    sys.print_exception(e)

        elif path == "/reset":
            if CONFIG_FILE in os.listdir():
                os.remove(CONFIG_FILE)
            await writer.awrite("HTTP/1.0 200 OK\r\n\r\nConfiguração apagada. A reiniciar...")
            await asyncio.sleep(1)
            machine.reset()

        elif path == "/clear_flag":
            if FAIL_FLAG_FILE in os.listdir():
                os.remove(FAIL_FLAG_FILE)
            await writer.awrite("HTTP/1.0 200 OK\r\n\r\nFlag apagada")

        else:
            try:
                with open(HTML_FILE) as f:
                    html = f.read()
                if FAIL_FLAG_FILE in os.listdir():
                    html = html.replace("<!--FAIL_MSG-->", "<p style='color:red'>Falha na ligação Wi-Fi. Verifique a password e tente novamente.</p>")
                await writer.awrite("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html)
            except Exception as e:
                print("[DEBUG] → Erro ao servir index.html:")
                sys.print_exception(e)
                await writer.awrite("HTTP/1.0 404 Not Found\r\n\r\nFicheiro não encontrado.")
        await writer.aclose()
    except Exception as e:
        print("[DEBUG] → Exceção em handle_http:")
        sys.print_exception(e)

async def dns_server():
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setblocking(False)
    udp.bind(("0.0.0.0", 53))
    while True:
        try:
            if IS_UASYNCIO_V3:
                yield asyncio.core._io_queue.queue_read(udp)
            else:
                yield asyncio.IORead(udp)
            data, addr = udp.recvfrom(512)
            dns = DNSQuery(data)
            udp.sendto(dns.response(SERVER_IP), addr)
        except Exception as e:
            print("[DEBUG] → Exceção no servidor DNS:")
            sys.print_exception(e)
            await asyncio.sleep_ms(500)

async def run_portal():
    wifi_start_ap()
    await asyncio.start_server(handle_http, "0.0.0.0", 80)
    asyncio.create_task(dns_server())
    asyncio.create_task(monitor_reset_button())
    asyncio.create_task(dummy_app_loop())
    while True:
        await asyncio.sleep(1)

async def dummy_app_loop():
    while True:
        print("[DEBUG] → Loop principal em execução...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    if IS_UASYNCIO_V3:
        asyncio.run(run_portal())
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_portal())
