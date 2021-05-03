"""
    File name: MPFProcessHandler.py
    Author: Matthew Allen

    Description:
        This is the container for an MPFProcess object. It handles spawning the process and interfacing with it
        from the main process.
"""
import logging
import multiprocessing as mp
import time
import traceback
from queue import Empty
import psutil

from MPFramework import MPFDataPacket, MPFTaskChecker

try:
    #We want true asynchronicity with as little task switching as possible.
    #To accomplish this we will attempt to tell the global multiprocessing instance
    #to spawn processes in a new interpreter with no shared resources.
    #This throws an error if it has been done elsewhere already, so we will just catch that and ignore it if it happens.
    mp.set_start_method('spawn')

except: #Yeah yeah yeah, I shouldn't use catch-alls for exception handling. Bite me.
    pass


class MPFProcessHandler(object):
    def __init__(self, input_queue=None, input_queue_max_size=1000, output_queue_max_size=1000):
        self._output_queue = mp.Queue(maxsize = output_queue_max_size)
        self._process = None
        self._MPFLog = logging.getLogger("MPFLogger")
        self._terminating = False

        if input_queue is None:
            self._input_queue = mp.Queue(maxsize = input_queue_max_size)
        else:
            self._input_queue = input_queue

    def setup_process(self, process, shared_memory = None, cpu_num = None):
        """
        This function spawns a process on a desired CPU core if one is provided. It expects an instance of
        MPFProcess to be passed as the process argument.

        :param process: An instance of an MPFProcess object.
        :param cpu_num: The CPU core to spawn the process on. Only available on Linux.
        :return: None.
        """
        self._MPFLog.debug("Setting up a new MPFProcess...")
        self._process = process

        #Setup process i/o and start it.
        process._inp = self._input_queue
        process._out = self._output_queue
        process.set_shared_memory(shared_memory)
        process.start()

        #If a specific cpu core is requested, move the process to that core.
        if cpu_num is not None:
            self._MPFLog.debug("Moving MPFProcess {} to CPU core {}.".format(process.name, cpu_num))
            if type(cpu_num) not in (list, tuple):
                cpu_num = [cpu_num]
            psutil.Process(process.pid).cpu_affinity(cpu_num)

        self._MPFLog.debug("MPFProcess {} has started!".format(process.name))

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

        if self._check_status():
            return

        if not self._input_queue.full():
            #Construct a data packet and put it on the process input queue.
            task = MPFDataPacket(header, data)
            self._input_queue.put(task, block=block, timeout=timeout)
            del task
        else:
            self._MPFLog.debug("MPFProcess {} input queue is full!".format(self._process.name))

        if delay is not None:
            time.sleep(delay)

        del header
        del data

    def get(self, block=False, timeout=None):
        """
        Function to get one item from our process' output queue.
        :return: Item from our process if there was one, None otherwise.
        """

        if self._check_status() and not cleaning_up:
            return None

        #First, check if the queue is empty and return if it is.
        if self._output_queue.empty():
            return None

        if not self._output_queue.empty():
            result = self._output_queue.get(block=block, timeout=timeout)
            return result()

        return None

    def get_all(self, block=False, timeout=None, failure_sleep_period_ms=0.1, cleaning_up=False):
        """
        Function to get every item currently available on the output queue from our process. The implementation of
        this function looks a bit odd, but it has been my experience that simply checking if a queue is empty almost never
        results in an accurate measurement of how many items are actually available on the queue. This function
        tries its best to guarantee that all items will be taken off the queue when it is called.

        :param block: mp.Queue block argument.
        :param timeout: mp.Queue timeout argument.
        :param cleaning_up: boolean to indicate that cleanup is happening. Do not modify.
        :return: List of items obtained from our process.
        """

        if self._check_status() and not cleaning_up:
            return None

        #First, check if the queue is empty and return if it is.
        if self._output_queue.empty():
            return None

        failCount = 0

        results = []
        try:
            # Here we take items off the queue for as long as the qsize function says we can.
            while self._output_queue.qsize() > 0:
                try:
                    result = self._output_queue.get(block=block, timeout=timeout)

                    header, data = result()
                    results.append((header, data))
                    result.cleanup()

                    del result
                    failCount = 0
                except Empty:
                    failCount += 1
                    if failure_sleep_period_ms is not None and failure_sleep_period_ms > 0:
                        time.sleep(failure_sleep_period_ms)

                    # It appears to be the case that the empty flag in the queue object
                    # is not related to the qsize() function, so an empty queue exception can
                    # be thrown even when the queue is not actually empty.

                    # This code can infinitely loop for some reason. qsize() can return a valid integer,
                    # while empty() can return true for an unlimited period of time, causing get to fail indefinitely.
                    # Whatever data remains in the queue simply cannot be
                    # retrieved at this point, and it is left in memory until the Python interpreter is closed.
                    if failCount >= 10:
                        if self._input_queue.qsize() == 0 and self._input_queue.empty():
                            break

                        self._MPFLog.critical("GET_ALL FAILURE LIMIT REACHED ERROR!\n"
                                              "FAILURE COUNT: {}\n"
                                              "REMAINING QSIZE: {}\n"
                                              "QUEUE EMPTY STATUS: {}".format(failCount,
                                                                              self._input_queue.qsize(),
                                                                              self._input_queue.empty()))
                        break
                    else:
                        continue
        except Exception:
            error = traceback.format_exc()
            self._MPFLog.critical("GET_ALL ERROR!\n{}".format(error))
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
        self._terminating = True

        #Put an exit command on the input queue to our process.
        self._MPFLog.debug("Beginning process termination...")

        self._terminate_process()

        self._MPFLog.debug("Successfully terminated MPFProcess {}!".format(self._process.name))

        #Get any residual items from the output queue and delete them.
        self._MPFLog.debug("Beginning residual output collection...")
        residual_output = self.get_all(cleaning_up=True)
        if residual_output is not None:
            self._MPFLog.debug("Removed {} residual outputs from queue.".format(len(residual_output)))
            del residual_output

        #Note here that we do not join either the input or output queues.
        #A process handler should only have a single process, so if the user has passed
        #a joinable queue to this handler's process, they are responsible for closing it.

        del self._input_queue
        del self._output_queue
        del self._process
        self._MPFLog.debug("All MPFProcess objects have been terminated!")

    def join(self):
        self.close()

    def stop(self):
        self.close()

    def _check_status(self):
        """
        Private function to check if our process is still running. If it is not, cleanup the resources.
        :return:
        """
        if self._terminating:
            return True

        if not self.is_alive():
            self._MPFLog.critical("Detected failure in MPFProcess {}! Terminating...".format(self._process.name))
            self.close()
            return True
        return False

    def _terminate_process(self):
        self._MPFLog.debug("Sending terminate command to process {}.".format(self._process.name))
        task = MPFDataPacket(MPFTaskChecker.EXIT_KEYWORDS[0], self._process.name)
        self._input_queue.put(task)
        self._process.join(timeout=5)
        while self.is_alive():
            self._process.terminate()
            self._process.join(timeout=5)
