"""
    File name: MPFProcessHandler.py
    Author: Matthew Allen

    Description:
        This is the container for an MPFProcess object. It handles spawning the process and interfacing with it
        from the main process.
"""
from MPFramework import MPFDataPacket, MPFTaskChecker
import multiprocessing as mp
import logging
import time

try:
    #We want true asynchronicity with as little task switching as possible.
    #To accomplish this we will attempt to tell the global multiprocessing instance
    #to spawn processes in a new interpreter with no shared resources.
    #This throws an error if it has been done elsewhere already, so we will just catch that and ignore it if it happens.
    mp.set_start_method('spawn')

except: #Yeah yeah yeah, I shouldn't use catch-alls for exception handling. Bite me.
    pass


class MPFProcessHandler(object):
    def __init__(self, inputQueue=None, input_queue_max_size=1000, output_queue_max_size=1000):
        self._output_queue = mp.Queue(maxsize = output_queue_max_size)
        self._process = None
        self._log = logging.getLogger("MPFLogger")

        if inputQueue is None:
            self._input_queue = mp.Queue(maxsize = input_queue_max_size)

    def setup_process(self, process, cpu_num = None):
        """
        This function spawns a process on a desired CPU core if one is provided. It expects an instance of
        MPFProcess to be passed as the process argument.

        :param process: An instance of an MPFProcess object.
        :param cpu_num: The CPU core to spawn the process on. Only available on Linux.
        :return: None.
        """

        import sys
        import os
        self._log.debug("Setting up a new MPFProcess...")
        self._process = process

        #Setup process i/o and start it.
        process._inp = self._input_queue
        process._out = self._output_queue
        process.start()

        #If a specific cpu core is requested and the os is linux, move the process to that core.
        if "linux" in sys.platform and cpu_num is not None:
            self._log.debug("Moving MPFProcess {} to CPU core {}.".format(process.pid, cpu_num))
            os.system("taskset -p -c {} {}".format(cpu_num, process.pid))

        self._log.debug("MPFProcess {} has started!".format(process.pid))

    def put(self, header, data, delay=None, block=False, timeout=None):
        """
        Function to send data to the process contained by this object.
        :param header: Header for data packet.
        :param data: Data to send.
        :param delay: Optionally delay for some period after putting data on the queue.
        :param block: mp.Queue block argument.
        :param timeout: mp.Queue timeout argument.
        :return: None.
        """

        if not self._input_queue.full():
            #Construct a data packet and put it on the process input queue.
            task = MPFDataPacket(header, data)
            self._input_queue.put(task, block=block, timeout=timeout)
            del task
        else:
            self._log.debug("MPFProcess {} input queue is full!".format(self._process.pid))

        if delay is not None:
            time.sleep(delay)

        del header
        del data

    def get(self):
        """
        Function to get one item from our process' output queue.
        :return: Item from our process if there was one, None otherwise.
        """

        if not self._output_queue.empty():
            data_packet = self._output_queue.get()
            return data_packet()

        return None

    def get_all(self, block=False, timeout=None):
        """
        Function to get every item currently available on the output queue from our process. The implementation of
        this function looks a bit odd, but it has been my experience that simply checking if a queue is empty almost never
        results in an accurate measurement of how many items are actually available on the queue. This function
        tries its best to guarantee that all items will be taken off the queue when it is called.

        :param block: mp.Queue block argument.
        :param timeout: mp.Queue timeout argument.
        :return: List of items obtained from our process.
        """

        #First, check if the queue is empty and return if it is.
        if self._output_queue.empty():
            return None

        results = []
        try:
            #Here we take items off the queue for as long as the qsize function says we can.
            while self._output_queue.qsize() > 0:
                result = self._output_queue.get(block=block, timeout=timeout)

                header, data = result()
                results.append((header, data))
                result.cleanup()

                del result
        except:
            #There are cases when qsize() will claim to be greater than zero, but will be wrong.
            #We want to catch those cases and ignore them.
            pass

        finally:
            return results

    def is_alive(self):
        """
        Function to check the status of our process.
        :return: True if process exists and is alive, False otherwise.
        """
        if self._process is None:
            return False

        return self._process.is_alive()

    def close(self):
        """
        Function to close and join our process. This should always be called when a process is no longer in use.
        :return: None.
        """

        #Put an exit command on the input queue to our process.
        self._log.debug("Sending terminate command to process {}.".format(self._process.pid))
        task = MPFDataPacket(MPFTaskChecker.EXIT_KEYWORDS[0], None)
        self._input_queue.put(task)

        #Terminate and join the process.
        self._process.terminate()
        self._process.join()
        self._log.debug("Successfully terminated MPFProcess {}!".format(self._process.pid))

        #Get any residual items from the output queue and delete them.
        residual_output = self.get_all()
        if residual_output is not None:
            self._log.debug("Removed {} residual outputs from queue.".format(len(residual_output)))
            del residual_output

        del self._input_queue
        del self._output_queue
        del self._process


    def join(self):
        self.close()

    def stop(self):
        self.close()