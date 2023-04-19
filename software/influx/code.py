import time
import os
import time
import ssl
import wifi
import adafruit_requests
import socketpool
import busio
import board

# TODO put these into the settings.toml so we can upload the rest of this file to github
# then read these with `os.getenv("INFLUX_URL")` etc
INFLUX_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUX_BUCKET = "plantsig"
INFLUX_ORG = "a0c670c86137e49a"
INFLUX_TOKEN = "w4PH4W0DCotlW4pCbvi-UlxugYOfgFNrYNmn8Fq2eE0XVPRVuM6FXK-oofhPXO8NyWCFybfHfDe-_ZwGmnVYUg=="
INFLUX_TABLE = "april14_plant3_inverse"
INFLUX_TAGS = {"sensor": "influxmk1"}  # IDK, optional
INFLUX_MEASUREMENT = "adcraw"  # name of the value we're measuring


BATCH_SIZE = 10
BAUD_RATE = 38400

url = f"{INFLUX_URL}/api/v2/write?org={INFLUX_ORG}&bucket={INFLUX_BUCKET}&precision=ns"
headers = {"Authorization": f"Token {INFLUX_TOKEN}",
           "Content-Type": "text/plain"}

# wifi.radio.connect(os.getenv("JASP_SSID"), os.getenv("JASP_PSWD"))
wifi.radio.connect(os.getenv("GH_SSID"), os.getenv("GH_PSWD"))
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

 
uart = busio.UART(board.GP16, board.GP17, baudrate=BAUD_RATE)

message_started = False
data_buffer = []

def sendData():
    data_out = ""
    for message_parts in data_buffer:
        try:            
            ts, gain, p1, p2, p3, p4, p5 = message_parts
            probes = [p1,p2,p3,p4,p5]
            for idx, p in enumerate(probes):
                data_out += f"{INFLUX_TABLE},probe=p{idx+1},gain={gain}{tags} {INFLUX_MEASUREMENT}={p} {ts}\n"

        except Exception as e:
            print ("data corrupted or couldn't send... skipping")
            print (e)

    print("about to send")
    print(data_out)

    try:
        resp = requests.post(url=url, headers=headers, data=data_out, timeout=3)  # added the timeout just to be safe
        print(f"we have posted (should be 204): '{resp.status_code}'")
    except Exception as f:
        print("there was a timeout or some other error")
        print(f)
        print("...but life must go on, so we keep rolling")


def bufferData(message):
    message_parts = "".join(message).split(",")
    print("got a message", message_parts)
    data_buffer.append(message_parts)

    if len(data_buffer) == BATCH_SIZE:
        sendData()
        data_buffer.clear()


print ("ready to receive UART data")

while True:
    byte_read = uart.read(1)  # Read one byte over UART lines
    if not byte_read:
        # Nothing read.
        continue

    if byte_read == b"<":
        message = []
        message_started = True
        continue

    if message_started:
        if byte_read == b">":
            # print("got a message", message)
            message_started = False
            bufferData(message)

        else:
            # Accumulate message byte.
            message.append(chr(byte_read[0]))



    
