import time
import os
import time
import ssl
import wifi
import adafruit_requests
import socketpool
import busio
import board
from digitalio import DigitalInOut, Direction
from adafruit_bus_device.spi_device import SPIDevice
from i2ctarget import I2CTarget

# TODO put these into the settings.toml so we can upload the rest of this file to github
# then read these with `os.getenv("INFLUX_URL")` etc
INFLUX_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUX_BUCKET = "plantsig"
INFLUX_ORG = "a0c670c86137e49a"
INFLUX_TOKEN = "w4PH4W0DCotlW4pCbvi-UlxugYOfgFNrYNmn8Fq2eE0XVPRVuM6FXK-oofhPXO8NyWCFybfHfDe-_ZwGmnVYUg=="
# INFLUX_TABLE = "onoff_secondround_april27"
INFLUX_TABLE = "flotest"
INFLUX_TAGS = {"sensor": "influxmk1.6"}  # IDK, optional
INFLUX_MEASUREMENT = "p"  # probe prefix (e.g. p1=123, p2=456)

BATCH_SIZE = 20 

## -------------- LED

led = DigitalInOut(board.LED)
led.direction = Direction.OUTPUT

## -------------- INFLUX

url = f"{INFLUX_URL}/api/v2/write?org={INFLUX_ORG}&bucket={INFLUX_BUCKET}&precision=ns"
headers = {"Authorization": f"Token {INFLUX_TOKEN}",
           "Content-Type": "text/plain"}

## -------------- WIFI

# wifi.radio.connect(os.getenv("JASP_SSID"), os.getenv("JASP_PSWD"))
# wifi.radio.connect(os.getenv("GH_SSID"), os.getenv("GH_PSWD"))
wifi.radio.connect(os.getenv("FLO_SSID"), os.getenv("FLO_PSWD"))
print("Connected to WiFi:", wifi.radio.ipv4_address)
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())
print("got http session, rdy to send")

print("testing internet connection")
resp = requests.get("https://httpbin.org/get")
print("internet test response (this should be 2xx):", resp.status_code)

# merge all tags into string
tags = ",".join([f"{k}={v}" for k, v in INFLUX_TAGS.items()])
if len(tags) > 0:
    tags = "," + tags 

 
# uart = busio.UART(board.GP16, board.GP17, baudrate=BAUD_RATE)

message_started = False
data_buffer = []

def sendData():
    data_out = ""
    for message_parts in data_buffer:
        try:            
            no_probes = len(message_parts) - 2 # first 2 are always ts and gain
            
            ts, gain = message_parts[0], message_parts[1]
            
            probe_str = []
            for idx in range(no_probes):
                probe_str.append(f"{INFLUX_MEASUREMENT}{idx+1}={message_parts[2+idx]}")
                
            data_out += f"{INFLUX_TABLE},gain={gain}{tags} {','.join(probe_str)} {ts}000\n"

        except Exception as e:
            print ("data corrupted or couldn't send... skipping")
            print (e)

    print("about to send")
    print(data_out) 

    try:
        led.value = True # turn LED on before send
        resp = requests.post(url=url, headers=headers, data=data_out, timeout=3)  # added the timeout just to be safe
        print(f"we have posted (should be 204): '{resp.status_code}'")
        led.value = False # turn LED off o successful send
    except Exception as f:
        print("there was a timeout or some other error")
        print("error:",f)
        print("...but life must go on, so we keep rolling")

def bufferData(message):
    message_parts = "".join(message).split(",")
    # print("got a message", message_parts)
    data_buffer.append(message_parts) 

    if len(data_buffer) == BATCH_SIZE:
        sendData()
        data_buffer.clear()


print ("ready to receive I2C data")

# The i2c address 0x18 here is completely arbitray. 
# It just needs to be the same on both Picos and one that's not used by the display or ads1115.
with I2CTarget(scl=board.GP11, sda=board.GP10, addresses=(0x18,)) as device:
    while True:
        r = device.request()
        if not r:
            continue
        with r:
            if r.is_read:
                continue
            b = r.read(1) # read one byte/character from i2c
            if b == b"<":
                message = []
                message_started = True
            elif message_started:
                if b == b">":
                    message_started = False
                    bufferData(message)
                else:
                    message.append(chr(b[0])) 
                    


