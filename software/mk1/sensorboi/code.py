print("Hello World!")
print("Hello World!")
import time
import random
import board
import busio
import displayio
import terminalio
import wifi
import ssl
import adafruit_requests
import socketpool
import adafruit_ntp
import rtc
import os
import adafruit_displayio_ssd1306
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.ads1115 import Mode
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_display_text import label
from adafruit_display_shapes.sparkline import Sparkline
from adafruit_display_shapes.line import Line
from adafruit_display_shapes.rect import Rect
from digitalio import DigitalInOut, Direction, Pull
from adafruit_bus_device.spi_device import SPIDevice
from adafruit_bus_device.i2c_device import I2CDevice

## DISPLAY
WIDTH = 128 
HEIGHT = 64
BORDER = 5
CHART_WIDTH = 80
CHART_HEIGHT = 50
SCREEN_OFF_SECONDS = 2 

## Data recording
RECORDINGS_PER_SECOND = 10
BATCH_SIZE = 20
BAUD_RATE = 500_000

## NUMBER OF PINS TO READ
PINS_TO_READ = 5

## ALWAYS ZAP OR ONLY ZAP ON DEMAND
ZAP_ON_DEMAND = True # if true will only electrocute plant when reading values

## Time delay correction
READ_TIME_EVERY = 6 # this is hacky, to compensate for time spike every 6 sends


pins = []
pin1 = DigitalInOut(board.GP6)
pins.append(pin1) 
TIME_CORRECTION = 16_600 # in nanosec, calibrated to 10Hz recording, I2C, tolerance: 80ns
if PINS_TO_READ > 1:
    pin2 = DigitalInOut(board.GP7)
    pins.append(pin2)
if PINS_TO_READ > 2:
    pin3 = DigitalInOut(board.GP8)
    pins.append(pin3)
if PINS_TO_READ > 3:  
    pin4 = DigitalInOut(board.GP9)
    pins.append(pin4)
if PINS_TO_READ > 4:
    pin5 = DigitalInOut(board.GP21)
    pins.append(pin5)
    TIME_CORRECTION = 66_666 # in nanosec, calibrated to 10Hz recording, I2C, tolerance: 80ns
# pin6 = DigitalInOut(board.GP20)
# pin7 = DigitalInOut(board.GP19)
# pin8 = DigitalInOut(board.GP18)


for x in pins:
    x.direction = Direction.OUTPUT
    if not ZAP_ON_DEMAND:
        x.value = True


displayio.release_displays()

i2c = busio.I2C(board.GP5, board.GP4) 
i2c_influx = busio.I2C(board.GP11, board.GP10)




print ("setting up display connection")
display_bus = displayio.I2CDisplay(i2c, device_address=0x3c)
print ("setting up display")
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=WIDTH, height=HEIGHT)
print ("display ready")
 
## -------------- LED

led = DigitalInOut(board.LED)
led.direction = Direction.OUTPUT


## -------------- WIFI AND NTP

# wifi.radio.connect(os.getenv("JASP_SSID"), os.getenv("JASP_PSWD"))
# wifi.radio.connect(os.getenv("GH_SSID"), os.getenv("GH_PSWD"))
wifi.radio.connect(os.getenv("FLO_SSID"), os.getenv("FLO_PSWD"))
print("Connected to WiFi:", wifi.radio.ipv4_address)
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())
print("got http session, rdy to send")

#### GETTING NTP TIME
ntp = adafruit_ntp.NTP(pool, tz_offset=0)  # get time data from NTP server
rtc.RTC().datetime = ntp.datetime  # update internal timer

t = time.localtime()
# note that this is +6 or +5 hours ahead of Montreal time.
# I didn't wanna deal with daylight saving here, so UTC+0 is safe
print(f"current time (UTC+0): {t.tm_year}-{t.tm_mon}-{t.tm_mday} {t.tm_hour}:{t.tm_min}:{t.tm_sec}")


# ## -------------- UART

# uart = busio.UART(board.GP16, board.GP17, baudrate=BAUD_RATE, timeout=0)


# ## ------------ ADS

current_gain = 0
gains = [1,2,4,8,16]
ads1 = ADS.ADS1115(i2c)
ads1.mode = Mode.SINGLE 
ads1.gain = gains[current_gain] # 1,2,3,4,8,16
ads2 = ADS.ADS1115(i2c, address=0x49) # second ADC is on a different address
ads2.mode = Mode.SINGLE 
ads2.gain = gains[current_gain] # 1,2,3,4,8,16
chan1 = AnalogIn(ads1, ADS.P0)
chan2 = AnalogIn(ads1, ADS.P1)
chan3 = AnalogIn(ads1, ADS.P2)
chan4 = AnalogIn(ads1, ADS.P3)
chan5 = AnalogIn(ads2, ADS.P0)
chan6 = AnalogIn(ads2, ADS.P1)
chan7 = AnalogIn(ads2, ADS.P2)
chan8 = AnalogIn(ads2, ADS.P3)
channels = [chan1, chan2, chan3, chan4, chan5, chan6, chan7, chan8]
# print(chan1.value, chan1.voltage)

# ## ------------ DISPLAY

font = terminalio.FONT

# Setup the first bitmap and sparkline
# This sparkline has no background bitmap
# sparkline1 uses a vertical y range between -1 to +1.25 and will contain a maximum of 40 items
sparkline1 = Sparkline(
    width=CHART_WIDTH,
    height=CHART_HEIGHT,
    max_items=20,
    y_min=0,
    y_max=32768,
    x=10,
    y=10,
)

# Label the y-axis range
# text_label1a = label.Label(font=font, text=str(sparkline1.y_top), color=0xFFFFFF)
text_label1a = label.Label(font=font, text="32k", color=0xFFFFFF)
text_label1a.anchor_point = (0, 0.5)  # set the anchorpoint
text_label1a.anchored_position = (
    10 + CHART_WIDTH,
    10,
)  # set the text anchored position to the upper right of the graph

text_label1b = label.Label(
    font=font, text=str(sparkline1.y_bottom), color=0xFFFFFF
)  # y_bottom label
text_label1b.anchor_point = (0, 0.5)  # set the anchorpoint
text_label1b.anchored_position = (
    10 + CHART_WIDTH,
    10 + CHART_HEIGHT,
)  # set the text anchored position to the upper right of the graph

text_label1c = label.Label(
    font=font, text="pin 1", color=0xFFFFFF
)  # y_bottom label
text_label1c.anchor_point = (0, 0.5)  # set the anchorpoint
text_label1c.anchored_position = (
    10 + CHART_WIDTH,
    10 + int(CHART_HEIGHT/2),
)  # set the text anchored position to the upper right of the graph

text_label1d = label.Label(
    font=font, text="gain 1", color=0xFFFFFF
)  # y_bottom label
text_label1d.anchor_point = (0, 0.5)  # set the anchorpoint
text_label1d.anchored_position = (
    10 + CHART_WIDTH,
    20 + int(CHART_HEIGHT/2),
)  # set the text anchored position to the upper right of the graph


# Create a group to hold the three bitmap TileGrids and the three sparklines and
# append them into the group (my_group)
#
# Note: In cases where display elements will overlap, then the order the elements
# are added to the group will set which is on top.  Latter elements are displayed
# on top of former elements.
my_group = displayio.Group()

my_group.append(sparkline1)
my_group.append(text_label1a)
my_group.append(text_label1b)
my_group.append(text_label1c)
my_group.append(text_label1d)



# Set the display to show my_group that contains all the bitmap TileGrids and
# sparklines
display.show(my_group)

btn1 = DigitalInOut(board.GP2)
btn1.direction = Direction.INPUT
btn1.pull = Pull.DOWN
btn1_was_pressed = False 

btn2 = DigitalInOut(board.GP22)
btn2.direction = Direction.INPUT
btn2.pull = Pull.DOWN
btn2_was_pressed = False

current_adc_chan = 0

configure_mode = True
btn_held_timer = None

# ## ------------ INFLUXBOARD STUFF BE

def wait_for_influxboard():
    while True:
        try:
            device = I2CDevice(i2c_influx, 0x18)
            break
        except ValueError as e:
            print (e) 
            time.sleep(1)
    return device

# ## ------------ Main Loop

counter = READ_TIME_EVERY - 1

ts_size = int(1_000_000 / RECORDINGS_PER_SECOND) + TIME_CORRECTION
ts = time.time() * 1_000_000
# Start the main loop
print ("ready to roll")

while True:

    if configure_mode:

        # Turn off auto_refresh to prevent partial updates of the screen during updates
        # of the sparklines
        display.auto_refresh = False
        
        ## BTN 1
        btn1_is_pressed = btn1.value
        if btn1_is_pressed and not btn1_was_pressed:
            print("BTN1 is down")
            btn1_was_pressed = True
            current_adc_chan += 1
            sparkline1.clear_values()
            if current_adc_chan == PINS_TO_READ:
                current_adc_chan = 0
            text_label1c.text = f"pin {current_adc_chan+1}"
            btn_held_timer = time.time()
        elif btn1_is_pressed and btn1_was_pressed:
            # btn is being held
            diff_time = time.time() - btn_held_timer
            if diff_time >= SCREEN_OFF_SECONDS:
                
                configure_mode = False
                print ("switching from configure mode to influx send mode")
                print ("waiting for influxdb daughter board...")
                dev_influx = wait_for_influxboard()
                print ("done, switching off display")
                display.sleep()
                
        elif not btn1_is_pressed:
            btn1_was_pressed = False
            pass 

        ## BTN 2
        btn2_is_pressed = btn2.value
        if btn2_is_pressed and not btn2_was_pressed:
            print("BTN2 is down")
            btn2_was_pressed = True
            current_gain += 1
            sparkline1.clear_values()
            if current_gain == len(gains):
                current_gain = 0
            text_label1d.text = f"gain {gains[current_gain]}"
            ads1.gain = gains[current_gain]
            ads2.gain = gains[current_gain]
        elif not btn2_is_pressed:
            btn2_was_pressed = False
            pass

        # Note: For sparkline2, the y-axis range is set from 0 to 1.
        # With the random values set between -1 and +2, the values will sometimes
        # be out of the y-range.  This example shows how the fixed y-range (0 to 1)
        # will "clip" values (it will not display them) that are above or below the
        # y-range.

        sparkline1.add_value(channels[current_adc_chan].value)
        # to read any given channel, use print(channels[0].value)


        # Turn on auto_refresh for the display
        display.auto_refresh = True
        time.sleep(0.1)
        # with spi_dev as spi:
        #     spi.write(bytes("(abcd)", "ascii"))

    else:
        buffer = []
        # print ('gathering data...')
        
        ts_new = time.time() * 1_000_000 # we read the time regardless but we use it only conditionally
        counter += 1
        if counter == READ_TIME_EVERY:
            print ("difference in expected vs actual ts:",ts_new-ts)
            ts = ts_new
            counter = 0
            led.value = True
        for _ in range(BATCH_SIZE):
            # ------------------section added to see on off of pins and not continuous -------#
            if ZAP_ON_DEMAND:
                for x in pins:  # only calling onto pins that we need
                    x.value = True
            # -----------------------------------------------------------------------------#
            
            outputs = [str(channels[i].value) for i in range(PINS_TO_READ)]
            
            # ------------------section added to see on off of pins and not continuous -------#
            if ZAP_ON_DEMAND:
                for x in pins:  # only calling onto pins that we need
                    x.value = False
            # -----------------------------------------------------------------------------#
            data_line = f"<{ts},{gains[current_gain]},{','.join(outputs)}>"
            buffer.append(data_line)
            time.sleep(1/RECORDINGS_PER_SECOND)
            ts += ts_size

        # print (f"buffer is full, sending {len(buffer)} items of data")
        ## buffer is full, lets  send it out
        
        try:
            with dev_influx:
                for buffer_line in buffer:
                    # print ("line: ", buffer_line)
                    dev_influx.write(bytes(buffer_line, "ascii"))
                print ("sent")
        except OSError as e:
            print (e)
            # supervisor.reload() # we could either reboot or 
            dev_influx = wait_for_influxboard() # attempt to reestablish the device
            
        led.value = False 
        # time.sleep(1)