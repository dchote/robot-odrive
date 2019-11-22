# robot-odrive
ODrive controller interface for my robot control stack.  This project provides ODrive state and control interfaces over NATS (http://nats.io) that can be published to for control, and subscribed to for state.  This project is stateless, and presents all connected controllers as individually addressible interfaces that are discoverable over NATS.


## Raspberry Pi Setup

Please follow the Getting Started guide for your ODrive controller(s) here: https://docs.odriverobotics.com. 
The instructions found in the ODrive Getting Started guide for Linux will get your Python 3 environment setup and ready to install the rest of the requirements for this project.

### Create udev rule to allow non-Root users to use the ODrive controllers via USB
Create file `/lib/udev/rules.d/50-odrive.rules` with the following content and then reboot your Raspberry Pi.
```
ACTION=="add", SUBSYSTEMS=="usb", ATTRS{idVendor}=="1209", ATTRS{idProduct}=="0d32", MODE="660", GROUP="dialout"
```

### Create a user to run all of the robot processes
Create a new user, or just apply these groups to your existing user.
```
adduser --disabled-password --disabled-login --gecos "" robot
usermod -a -G dialout,gpio,i2c,spi robot 
```

### Install robot-odrive dependencies
```
pip3 install asyncio-nats-client
```

### Test run
```
sudo -u robot python3 robot-odrive.py 
```
