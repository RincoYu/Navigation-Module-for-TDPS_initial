#
# OpenMV Software for TDPS self-driving vehicle project
# Main.py
# Sidi Liang, 2023
#

import sensor, image, time, pyb, json
from machine import Pin, I2C
from bno055 import BNO055, AXIS_P7
from HCSR04 import HCSR04
from LineTracking import LineTracking, dead_reckoning
from time import sleep_ms
from pyb import Timer
import uasyncio

RED_LED_PIN = 1
BLUE_LED_PIN = 3

sensor.reset()                      # Reset and initialize the sensor.
sensor.set_pixformat(sensor.RGB565) # Set pixel format to RGB565
sensor.set_framesize(sensor.QVGA)
sensor.skip_frames(time = 2000)     # Wait for settings take effect.
clock = time.clock()                # Create a clock object to track the FPS.

status_data = {'Info_Task': 1,
               'Info_Patio': 1,
               'Info_Stage': 1,
               'Control_Command': 0,
               'Control_Angle': 0,
               'Control_Velocity': 0}

# UART using uart 1 and baud rate of 115200
uart = pyb.UART(1, 115200)

async def uart_messaging_json(data):
    data_json = json.dumps([status_data])
    uart_send_buffer = b'\xaa\x55' +len(data_json).to_bytes(1, 'big') + bytes(data_json, 'utf-8') + b'\xbb'
    print("UART sent: ", uart_send_buffer)
    print("UART len: ", len(uart_send_buffer))
    last_message = uart_send_buffer
    return uart_send_buffer

async def readwrite():
    swriter = uasyncio.StreamWriter(uart, {})
    sreader = uasyncio.StreamReader(uart)
    last_message = 'nil'

    while True:
        print('Waiting for incoming message...')
        rcv = await sreader.read(1)
        if rcv:
            print('Received: ', rcv)
            buf = last_message
            if rcv == b'\xcc':
                buf = await uart_messaging_json(status_data)
                last_message = buf
            elif rcv == b'\xdd':
                buf = last_message

            await swriter.awrite(buf)
            print('Sent: ', buf)
            await uasyncio.sleep_ms(1)

# I2C
i2c = I2C(2, freq=400000)
imu = None
try:
    imu = BNO055(i2c)
except:
    pyb.LED(RED_LED_PIN).on()

dr = dead_reckoning.DeadReckoning()

line_tracking = LineTracking(sensor, draw=True)
#line_tracking.start()

async def start_patio_1():
    line_tracking.start()
    status_data['Info_Patio'] = 1
    print("In Patio 1")
    current_task = status_data['Info_Task']
    patio1_task1_stop_signal = 0
    patio1_task2_stop_signal = 0
    patio1_task3_stop_signal = 0
    if current_task == 1:
        # Line following
        status_data['Info_Task'] = 1
        print("Performing task 1")
        while True:
            velocity = 100
            control = line_tracking.calculate()
            line = line_tracking.get_line()
            theta_err = line_tracking.get_theta_err()
            status_data['Control_Command'] = control
            status_data['Control_Angle'] = theta_err
            status_data['Control_Velocity'] = velocity
            if imu:
                dr.dead_reckoning(imu)
                # print("Velocity m/s: ", dr.velocity_x, dr.velocity_y, dr.velocity_z)
                # print("Position m: ", dr.position_x, dr.position_y, dr.position_z)
            if patio1_task1_stop_signal:
                current_task = 2
                break
            await uasyncio.sleep_ms(1)

    elif current_task == 2:
        # Crossing the bridge
        status_data['Info_Task'] = 2

    elif current_task == 3:
        # Passing the Door
        status_data['Info_Task'] = 3

    return 0


async def start_patio_2():
    status_data['Info_Patio'] = 2
    print("In Patio 2, program not implemented yet, ending......")
    return 0


async def main():
    while True:
        clock.tick()
        ret = 1
        current_patio = status_data['Info_Patio']
        if current_patio == 1:
            ret = await start_patio_1()
            if ret == 0:
                current_patio = 2
        elif current_patio == 2:
            ret = await start_patio_2()
            if ret == 0: break


loop = uasyncio.get_event_loop()
loop.create_task(readwrite())
loop.create_task(main())
loop.run_forever()