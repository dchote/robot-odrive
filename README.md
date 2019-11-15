# robot-odrive
ODrive controller interface for my robot control stack.  This project provides ODrive state and control interfaces over NATS (http://nats.io) that can be published to for control, and subscribed to for state.  This project is stateless, and presents all connected controllers as individually addressible interfaces that are discoverable over NATS.

**This is a work in progress!**
