import utime
import ds18x20, onewire
from machine import Pin, I2C
import state

def read_ir_temperature(i2c):
    try:
        data = i2c.readfrom_mem(0x5A, 0x07, 2)  # MLX90614 Tobj1
        raw = data[1] << 8 | data[0]
        return raw * 0.02 - 273.15
    except:
        return None

def temperature_thread():
    # DS18B20
    ds_pin = Pin(25)  # pino de dados
    ow = onewire.OneWire(ds_pin)
    ds_sensor = ds18x20.DS18X20(ow)
    roms = ds_sensor.scan()

    if not roms:
        print("DS18B20 não encontrado!")
    else:
        print("DS18B20 encontrado:", roms)

    # GY-906 IR sensor (MLX90614)
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)

    while True:
        # Lê DS18B20
        ds_sensor.convert_temp()
        utime.sleep_ms(750)
        temp_ds = None
        if roms:
            temp_ds = ds_sensor.read_temp(roms[0])

        # Lê MLX90614
        temp_ir = read_ir_temperature(i2c)

        # Calcula média se possível
        with state.lock:
            if temp_ds is not None:
                state.temperature_ds = temp_ds
            if temp_ir is not None:
                state.ir_temperature = temp_ir

            if temp_ds is not None and temp_ir is not None:
                state.temperature = (temp_ds + temp_ir) / 2
            elif temp_ds is not None:
                state.temperature = temp_ds
            elif temp_ir is not None:
                state.temperature = temp_ir
            else:
                state.temperature = None

        print(f"[TEMP] DS: {temp_ds}, IR: {temp_ir}, Média: {state.temperature}")
        utime.sleep(5)
