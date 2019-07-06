# MPFramework
A multiprocessing framework for Python 3.4+

While it is straightforward to use multiprocessing for simple tasks, when multiple processes need to exist for long periods of time and do many complex tasks, the Python multiprocessing library can be a huge hassle. This package allows easy spawning and communication between multiple persistent processes in Python.

With this package, a user only needs to extend the MPFProcess object to create a persistent and easy to manipulate process which is completely asynchronous from the main process.

# Installation
Clone the git. PIP integration is coming soon!

# Usage
Example usage of a custom MPFProcess object can be found in the Examples folder. Simply extend the MPFProcess object and implement the necessary functions, then start it through an MPFProcessHandler object and you are off to the races!
