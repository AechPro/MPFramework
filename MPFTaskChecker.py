"""
    File name: MPFTaskChecker.py
    Author: Matthew Allen

    Description:
        This file handles checking the input to an MPFProcess object. It handles reading from the input queue
        and appropriately processing new messages. It contains a method to wait for initialization so a process can
        hang when it is first started if initial data from the main process is necessary. To access the latest message,
        simply check the latest_data and header variables inside the MPFTaskChecker object.
"""

from multiprocessing import JoinableQueue
import logging
import time

class MPFTaskChecker(object):
    EXIT_KEYWORDS = ["terminate", "terminal", "exit", "stop", "join", "close", "finish"]

    def __init__(self, input_queue, pid, update_check_sleep_period=0.1, init_sleep_period=1.0):
        self.latest_data = None
        self.header = None
        self._input_queue = input_queue
        self._update_sleep_period = update_check_sleep_period
        self._init_sleep_period = init_sleep_period
        self._pid = pid
        self._joinable = type(input_queue) == type(JoinableQueue())
        self._log = logging.getLogger("MPFLogger")

    def wait_for_initialization(self, header=None):
        """
        Function to wait for initial data to be received.
        :param header: If we are looking for a specific header to be provided, we will compare the received
                       header to this argument.
        :return: None.
        """

        self._log.debug("MPFProcess {} is waiting for initialization...".format(self._pid))
        #In some cases we might have already received some data by the time this function is called. This checks for that.
        if header is not None and self.header is not None:
            if self.header == header:
                self._log.debug("MPFProcess {} has initialized!".format(self._pid))
                return


        self.latest_data = None

        #While we have no available data.
        while self.latest_data is None:

            #Check for new data.
            self.check_for_update()

            #If the header doesn't match our desired header, ignore any new data.
            if self.header != header and header is not None:
                self.latest_data = None

            #Wait to avoid CPU stress.
            time.sleep(self._init_sleep_period)

        self._log.debug("MPFProcess {} has initialized!".format(self._pid))

    def check_for_update(self):
        """
        Function to check for new data on the input queue. This is automatically called at the top of the
        MPFProcess run loop. This function checks for data and processes it into self.header and self.latest_data
        for access by an MPFProcess object.
        :return: True if new data was received, False otherwise.
        """

        newData = False
        if not self._input_queue.empty():

            #Get the next data packet, should be MPFDataPacket object.
            data_packet = self._input_queue.get_nowait()
            header, data = data_packet()
            self._log.debug("MPFProcess {} has received a new data packet!".format(self._pid))

            #Update our current data object and header.
            self._update_data(data)
            self.header = header
            newData = True

            #Check to see if the new data was a terminate signal.
            self._check_for_terminal_header(header)

            #Clean up and delete the received packet.
            data_packet.cleanup()
            del data_packet

            #If we are using a joinable queue, mark the task as done.
            if self._joinable:
                self._input_queue.task_done()

        return newData

    def _update_data(self, data):
        self.cleanup()
        self.latest_data = data
        del data

    def cleanup(self):
        try:
            self.latest_data.clear()
        except:
            pass
        finally:
            del self.latest_data

    def _check_for_terminal_header(self, header):
        h = header.lower().strip()

        for word in self.EXIT_KEYWORDS:
            if word in h:
                self.header = "STOP PROCESS"
                self._log.debug("MPFProcess {} has received a terminate command!".format(self._pid))
                return
