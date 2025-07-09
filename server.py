import uasyncio as asyncio
import json
import utime
import state
import machine
from machine import Pin
import neopixel
from regulation import calc_effective_percentage

np = neopixel.NeoPixel(Pin(23), 8)

async def handle_client(reader, writer):
    try:
        request = await reader.read(1024)
        request_str = request.decode()
        headers, _, body = request_str.partition("\r\n\r\n")
        lines = headers.splitlines()
        first_line = lines[0] if lines else ""
        parts = first_line.split(" ")
        method = parts[0] if len(parts) > 0 else ""
        path = parts[1] if len(parts) > 1 else "/"

        if method == "GET" and path == "/":
            with state.lock:
                base_percentage = state.percentage
                current_temperature = state.temperature if state.temperature is not None else "N/A"
                comfort_mode = state.comfort_mode
                triac_status = state.triac_on
                effective_percentage = calc_effective_percentage(base_percentage, state.temperature, comfort_mode)

                temperate_low, temperate_high = state.online_temperature_thresholds.get("TEMPERATE", state.DEFAULT_TEMPERATURE_THRESHOLDS["TEMPERATE"])
                medium_low, medium_high = state.online_temperature_thresholds.get("MEDIUM", state.DEFAULT_TEMPERATURE_THRESHOLDS["MEDIUM"])
                warm_low, warm_high = state.online_temperature_thresholds.get("WARM", state.DEFAULT_TEMPERATURE_THRESHOLDS["WARM"])

                power_color = "#28a745" if triac_status else "#dc3545"
                power_status = "Ligado" if triac_status else "Desligado"

            html = f"""
<html>
  <head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="30; url=/" >
    <title>Halo Heat</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body {{
        background: linear-gradient(to right, #005AA7, #FFFDE4);
        font-family: 'Segoe UI', sans-serif;
        margin: 0;
        padding: 0;
      }}
      .container {{
        max-width: 500px;
        margin: 40px auto;
        padding: 30px;
        background: white;
        border-radius: 12px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.15);
      }}
      h1 {{
        text-align: center;
        color: #005AA7;
        margin-bottom: 24px;
      }}
      .status {{
        text-align: center;
        margin-bottom: 20px;
        font-size: 16px;
        color: #333;
      }}
      .power-status {{
        text-align: center;
        font-weight: bold;
        font-size: 18px;
        color: {power_color};
        margin-bottom: 20px;
      }}
      .field-group {{
        margin-bottom: 20px;
      }}
      label {{
        display: block;
        margin-bottom: 6px;
        font-weight: bold;
        color: #444;
      }}
      input[type="number"], input[type="range"], select {{
        width: 100%;
        padding: 10px;
        font-size: 16px;
        border: 1px solid #ccc;
        border-radius: 6px;
        box-sizing: border-box;
      }}
      button {{
        width: 100%;
        padding: 12px;
        font-size: 18px;
        background-color: {power_color};
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        transition: background-color 0.3s ease;
      }}
      button:hover {{
        background-color: #003f7d;
      }}
      .button-circle {{
        font-size: 24px;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        padding: 10px;
        margin: 10px auto 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: {power_color};
        color: white;
        border: none;
        cursor: pointer;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Halo Heat</h1>
      <div class="status">
        <p>Temperatura Atual: {current_temperature} ºC</p>
        <p>Potência configurada: {base_percentage}%</p>
        <p>Potência efetiva: {effective_percentage:.1f}%</p>
        <p>Modo de Conforto: {comfort_mode}</p>
      </div>
      <div class="power-status">{power_status}</div>
      <div style="text-align:center;">
        <form method="post" action="/toggle_power">
          <button class="button-circle">⏻</button>
        </form>
      </div>
      <form method="post" action="/update_settings">
        <div class="field-group">
          <label for="percentage">Potência Máxima (0–100):</label>
          <input type="range" id="percentage" name="percentage" min="0" max="100" value="{base_percentage}" oninput="document.getElementById('percValue').innerText = this.value + '%'">
          <span id="percValue">{base_percentage}%</span>
        </div>
        <div class="field-group">
          <label for="comfort_mode">Modo de Conforto:</label>
          <select id="comfort_mode" name="comfort_mode">
            <option value="TEMPERATE" {"selected" if comfort_mode == "TEMPERATE" else ""}>TEMPERATE</option>
            <option value="MEDIUM" {"selected" if comfort_mode == "MEDIUM" else ""}>MEDIUM</option>
            <option value="WARM" {"selected" if comfort_mode == "WARM" else ""}>WARM</option>
          </select>
        </div>
        <div class="field-group">
          <h3>Limites para TEMPERATE</h3>
          <label>Mínima (ºC):</label><input type="number" name="temperate_min" value="{temperate_low}" step="0.1" min="10" max="35">
          <label>Máxima (ºC):</label><input type="number" name="temperate_max" value="{temperate_high}" step="0.1" min="10" max="35">
        </div>
        <div class="field-group">
          <h3>Limites para MEDIUM</h3>
          <label>Mínima (ºC):</label><input type="number" name="medium_min" value="{medium_low}" step="0.1" min="10" max="35">
          <label>Máxima (ºC):</label><input type="number" name="medium_max" value="{medium_high}" step="0.1" min="10" max="35">
        </div>
        <div class="field-group">
          <h3>Limites para WARM</h3>
          <label>Mínima (ºC):</label><input type="number" name="warm_min" value="{warm_low}" step="0.1" min="10" max="35">
          <label>Máxima (ºC):</label><input type="number" name="warm_max" value="{warm_high}" step="0.1" min="10" max="35">
        </div>
        <button type="submit">Atualizar Configurações</button>
      </form>
    </div>
  </body>
</html>
"""

            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n" + html

        elif method == "POST" and path == "/toggle_power":
            with state.lock:
                if state.menu_state == "BLOQUEADO":
                    try:
                        from button_control import unlock_effect
                        unlock_effect()
                    except:
                        pass
                    state.menu_state = "OPERATIONAL"
                state.triac_on = not state.triac_on
                if not state.triac_on:
                    np[0] = (2, 0, 0)
                else:
                    if state.comfort_mode == "TEMPERATE":
                        np[0] = (8, 7, 0)
                    elif state.comfort_mode == "MEDIUM":
                        np[0] = (15, 4, 0)
                    elif state.comfort_mode == "WARM":
                        np[0] = (15, 1, 0)
                np.write()
            response = "HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n"

        elif method == "POST" and path == "/update_settings":
            try:
                params = {}
                for pair in body.split("&"):
                    if "=" in pair:
                        k, v = pair.split("=")
                        params[k] = v

                with state.lock:
                    state.percentage = int(params.get("percentage", state.percentage))
                    state.comfort_mode = params.get("comfort_mode", state.comfort_mode)
                    state.online_temperature_thresholds["TEMPERATE"] = (float(params["temperate_min"]), float(params["temperate_max"]))
                    state.online_temperature_thresholds["MEDIUM"] = (float(params["medium_min"]), float(params["medium_max"]))
                    state.online_temperature_thresholds["WARM"] = (float(params["warm_min"]), float(params["warm_max"]))
                import settings
                settings.save_settings(state)
            except Exception as e:
                print("Erro ao atualizar configs:", e)

            response = "HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n"

        elif method == "GET" and path == "/status":
            with state.lock:
                resp_data = {
                    "triac_on": state.triac_on,
                    "percentage": state.percentage,
                    "comfort_mode": state.comfort_mode,
                    "temperature": state.temperature,
                    "online_thresholds": state.online_temperature_thresholds
                }
            response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps(resp_data)

        else:
            response = "HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n\r\nNot Found"

        writer.write(response.encode())
        await writer.drain()
    except Exception as e:
        print("Erro ao processar request:", e)
    finally:
        await writer.wait_closed()

async def main_http_server():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("[HTTP] Servidor iniciado na porta 80")
    while True:
        await asyncio.sleep(3600)


