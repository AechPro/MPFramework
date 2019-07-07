# MPFramework
A multiprocessing framework for Python 3.4+

This package enables easy spawning and communication between persistent asychnronous processes in Python.

# Installation
Clone the git. PIP integration is coming soon!

# Usage
Detailed examples can be found in the Examples folder. The following is a simple example of using a MPFProcess.
```
#Extend the MPFProcess base object and implement the necessary functions.
class ExampleProcess(MPFProcess):
    def __init__(self):
        super().__init__(loop_wait_period=1.0) #Wait one second between process loop cycles. 

    def init(self): #Init anything we need in this process.
        pass

    def update(self, header, data): #Handle messages from another process.
        pass

    def step(self): #Do whatever our process needs to do.
        print("Hello from a process!")

    def publish(self): #Send results to our output queue.
        pass

    def cleanup(self): #Free all resources held by this process.
        pass

def main():
    #Use a process handler to start our process by passing an instance of our process object to the handler.
    process_handler = MPFProcessHandler()
    process_handler.setup_process(ExampleProcess())

    #Start an infinite loop in the main process.
    seconds = 0
    while seconds < 10:
        seconds += 1
        time.sleep(1.0)

    #Let the handler deal with cleaning up and closing our process.
    process_handler.close()
```
