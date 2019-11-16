import argparse
import asyncio
import signal
import logging
import json
import usb.core

from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

import odrive
from odrive.enums import *

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s,%(msecs)d %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)



#
# Global scope variables
#
nc = NATS()
odrives = []

nats_server = "nats://127.0.0.1:4222"



#
# Async Functions
#
async def robotInit(loop):
    logging.info("robotInit initializing robot-odrive stack")
    
    #
    # Enumerate ODrive devices connected via USB, UART, etc could be added here too.
    # adapted discovery logic from: https://github.com/BlakeLazarine/Portfolio/wiki/Week_24-_-2.18.19-_-2.22.19
    #
    usbDevices = list(usb.core.find(find_all=True, idVendor=0x1209, idProduct=0x0d32)) # id numbers are specific to ODrive boards
    logging.info("robotInit found %d ODrive devices via USB" % (len(usbDevices)))
    
    try:
        for usbDevice in usbDevices:            
            logging.info("robotInit connecting USB ODrive on usb:%s:%s" % (usbDevice.bus, usbDevice.address))
            
            od = odrive.find_any("usb:%s:%s" % (usbDevice.bus, usbDevice.address))
            odrives.append(od)
            
            logging.info("robotInit added USB ODrive with serial number: %s" % (od.serial_number))
    except:
        pass
        
    logging.info("robotInit connected to %d ODrive devices" % (len(odrives)))
    
    #
    # Establish connection to NATS
    #
    await nc.connect(nats_server, loop=loop)
    
    logging.info("robotInit complete")


#
# Graceful termination process
#
async def robotTerminate():
    logging.info("robotTerminate terminating robot-odrive stack")
    
    # Gracefully close the NATS connection.
    if nc.is_connected:
        await nc.drain()
    
    # No graceful handling for closing ODrive connections
    
    logging.info("robotTerminate complete")

#
# Main runloop
#
async def robotWork():
    async def discovery_request(msg):
        subject = msg.subject
        reply = msg.reply
        data = msg.data.decode()
        
        logging.info("discovery request subject:{subject} reply:{reply} data:{data}".format(subject=subject, reply=reply, data=data))
        
        if len(reply) > 0:
            for od in odrives:
                for axis in ["axis0", "axis1"]:
                    controlSubject = "robot.devices.od%s-%s.control" % (od.serial_number, axis)
                    stateSubject = "robot.devices.od%s-%s.state" % (od.serial_number, axis)
            
                    response = {
                        "type": "motion",
                        "motion_input": "velocity", 
                        "control": controlSubject,
                        "state": stateSubject
                    }
            
                    logging.debug("publishing %s: %s" % (reply, json.dumps(response)))
                    await nc.publish(reply, json.dumps(response).encode())
        else:
            logging.error("discovery request did not include a reply subject")
            
        
    async def control_request(msg):
        subject = msg.subject
        reply = msg.reply
        data = msg.data.decode()
        logging.info("control request subject:{subject} reply:{reply} data:{data}".format(subject=subject, reply=reply, data=data))
        
    
    #
    # Subscribe to control subjects for each device (by ODrive serial number)
    #
    for od in odrives:
        for axis in ["axis0", "axis1"]:
            subjectString = "robot.devices.od%s-%s.control" % (od.serial_number, axis)
            await nc.subscribe(subjectString, cb=control_request)
    
    #
    # Subscribe to the device discovery subject
    #
    await nc.subscribe("robot.devices.discovery", cb=discovery_request)
    
    while True:
        try:
            
            #
            # Publish ODrive status every second
            #
            await asyncio.sleep(1)
            
            for od in odrives:
                for axis in ["axis0", "axis1"]:
                    subjectString = "robot.devices.od%s-%s.state" % (od.serial_number, axis)
                    
                    axisObject = getattr(od, axis)
                    status = {
                        "bus_voltage": od.vbus_voltage,
                        "enabled": axisObject.motor.armed_state,
                        "status": "unknown",
                        "temperature": axisObject.motor.get_inverter_temp(),
                        "current_velocity": axisObject.controller.vel_setpoint,
                        "_velocity_integrator_current": axisObject.controller.vel_integrator_current
                    }
                    
                    if axisObject.current_state == AXIS_STATE_IDLE:
                        status["status"] = "idle"
                    elif axisObject.current_state == AXIS_STATE_CLOSED_LOOP_CONTROL:
                        status["status"] = "active"
                    
                    logging.debug("publishing %s: %s" % (subjectString, json.dumps(status)))
                    await nc.publish(subjectString, json.dumps(status).encode())
            
            
        except asyncio.CancelledError:
            logging.info("robotWork cancelled")
            break
    
    logging.info("robotWork finished")


#
# func() main
#
if __name__ == "__main__":
    # Argument parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", '--nats', dest="nats_server", type=str, default=nats_server, help="NATS server address (default: %s)" % (nats_server))
    args = parser.parse_args()
    
    if args.nats_server:
        nats_server = args.nats_server
        logging.info("using NATS server %s" % (nats_server))
    
    
    # Initialize event loop and initital robot setup
    loop = asyncio.get_event_loop()
    loop.run_until_complete(robotInit(loop))    
    
    # Main runloop
    robotWork = asyncio.ensure_future(robotWork())
    
    # Attach signal handling for graceful termination
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, robotWork.cancel)
    
    # Kick off the main runloop and catch signals
    try:
        loop.run_until_complete(robotWork)
    finally:
        loop.run_until_complete(robotTerminate())
        loop.close()