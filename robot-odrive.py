import asyncio
import signal
import logging

from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,%(msecs)d %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

nc = NATS()

async def robotInit(loop):
    logging.info("robotInit initializing robot-odrive stack")
    await nc.connect("nats://tank.local:4222", loop=loop)
    
    logging.info("robotInit complete")

async def robotTerminate():
    logging.info("robotTerminate terminating robot-odrive stack")
    
    # Gracefully close the NATS connection.
    if nc.is_connected:
        await nc.drain()
    
    logging.info("robotTerminate complete")


async def robotWork():
    async def motion_handler(msg):
        subject = msg.subject
        reply = msg.reply
        data = msg.data.decode()
        print("Received a message on '{subject} {reply}': {data}".format(
            subject=subject, reply=reply, data=data))
    
    
    await nc.subscribe("robot.motion.*", cb=motion_handler)
    
    while True:
        try:
            await asyncio.sleep(1)
            await nc.publish("robot.motion.discover", b'')
            
        except asyncio.CancelledError:
            logging.info("robotWork cancelled")
            break
    
    logging.info("robotWork finished")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    
    loop.run_until_complete(robotInit(loop))    
    
    robotWork = asyncio.ensure_future(robotWork())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, robotWork.cancel)
    
    try:
        loop.run_until_complete(robotWork)
    finally:
        loop.run_until_complete(robotTerminate())
        loop.close()