"""
    File name: MPFResultsPublisher.py
    Author: Matthew Allen

    Description:
        This is a container for the output queue used by an MPFProcess object. It handles putting data on the queue.
"""
from MPFramework import MPFDataPacket
import logging
import time

class MPFResultPublisher(object):
    def __init__(self, output_queue, pid):
        self._output_queue = output_queue
        self._pid = pid
        self._log = logging.getLogger("MPFLogger")

    def publish(self, data, header="MPFProcess_default_header", block=True, timeout = 1.0):
        """
        Function to publish data to our output queue.
        :param data: data to put on the queue.
        :param header: header to identify the data.
        :param block: mp.Queue block argument.
        :param timeout: mp.Queue timeout argument.
        :return: None.
        """

        if not self._output_queue.full():
            data_packet = MPFDataPacket(header, data)
            self._output_queue.put(data_packet, block=block, timeout=timeout)
            del data_packet
        else:
            self._log.debug("Unable to publish results, MPFProcess {} output queue is full!".format(self._pid))
            time.sleep(timeout)

        del data