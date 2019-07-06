"""
    File name: MPFSharedMemory.py
    Author: Matthew Allen

    Description:
        This file contains two classes used for allocating and handling a block of shared memory which can be accessed
        asynchronously by multiple MPFProcess objects. This is purposefully not thread safe because its intended usage
        is for large (1GB+) blocks of ROM, so returning thread-safe clones of the memory held by this object
        could result in huge memory usage spikes. Safe asynchronous usage is left to the user.
"""

from multiprocessing.managers import BaseManager
import multiprocessing as mp
import numpy as np
import logging
import ctypes

class MPFSharedMemory(object):

    #Supported memory types.
    MPF_FLOAT32 = ctypes.c_float
    MPF_FLOAT64 = ctypes.c_double
    MPF_INT32 = ctypes.c_int32
    MPF_INT64 = ctypes.c_int64

    def __init__(self, size, dtype=MPF_FLOAT32):
        self._dtype = dtype
        self._size = size
        self._manager = None
        self._memory = None
        self._allocate()
        self._log = logging.getLogger("MPFLogger")

    def set(self, index, data):
        """
        Function for writing to a segment of the shared memory.
        :param index: Index at which to begin writing.
        :param data: Data to write.
        :return: None.
        """
        self._memory.set(index, data)

    def get(self, index, size):
        """
        Function for reading out of the shared memory.
        :param index: Index at which to start reading.
        :param size: Index at which to stop reading.
        :return: The data in memory from index to index+size.
        """

        return self._memory.get(index, size)

    def _allocate(self):
        """
        Private function for allocating memory and creating the manager for handling access to the memory.
        The manager is necessary to ensure that no clones of the memory block are ever spawned. We don't interact with it
        outside of that.
        :return: None.
        """

        self._log.debug("Allocating MPFMemoryBlock!\nSize: {}\nData type: {}.".format(self._size, self._dtype))

        #Register our shared memory block and start the manager object.
        BaseManager.register('MPF_Memory_Block', MPFSharedMemoryBlock)
        self._manager = BaseManager()
        self._manager.start()

        #Build our memory object through the manager object.
        self._memory = self._manager.MPFSharedMemoryBlock(self._size, self._dtype)
        self._log.debug("MPFMemoryBlock allocated successfully!")


    def cleanup(self):
        try:
            self._log.debug("Cleaning up MPFMemoryBlock...")

            self._memory.cleanup()
            self._log.debug("Shutting down MPFMemory manager...")

            self._manager.shutdown()
            self._log.debug("MPFMemoryBlock has closed successfully!")

        except Exception as e:
            self._log.debug("MPFMemoryBlock was unable to close!"
                            "\nException type: {}\nException args:".format(type(e), e.args))
        finally:
            del self._memory
            del self._manager

class MPFSharedMemoryBlock(object):
    def __init__(self, mem_size, dtype):
        self._dtype = self._parse_dtype(dtype)
        self._mem_size = mem_size
        self._mem = None
        self._shared_block = None
        self._manager = None

        self._allocate()

    def set(self, start, data):
        """
        Function to write to our memory block.
        :param start: Index at which to start writing.
        :param data: Data to write.
        :return: None.
        """
        np.copyto(self._mem[start:], data)

    def get(self, index, size):
        """
        Function to read from our memory block.
        :param index: Index at which to start reading.
        :param size: Index at which to stop reading.
        :return: Memory from index to index+size
        """

        data = np.frombuffer(self._mem[index:index + size])
        return data

    def _parse_dtype(self, code):
        """
        Function to parse the data type code passed as a constructor argument into an appropriate MPF data type.
        :param code: Data-type code to be checked.
        :return: The appropriate MPF data type, defaults to float32.
        """

        code = code
        floatCodes = ('float', 'float32', np.float32, 'f', ctypes.c_float)
        doubleCodes = ('double', 'float64', np.float64, 'd', ctypes.c_double)
        intCodes = ('int', 'int32', np.int32, 'i', ctypes.c_int32)
        longCodes = ('long', 'int64', np.int64, 'l', ctypes.c_int64)

        if code in floatCodes:
            return MPFSharedMemory.MPF_FLOAT32

        if code in doubleCodes:
            return MPFSharedMemory.MPF_FLOAT64

        if code in intCodes:
            return MPFSharedMemory.MPF_INT32

        if code in longCodes:
            return MPFSharedMemory.MPF_INT64

        return MPFSharedMemory.MPF_FLOAT32

    def _allocate(self):
        """
        Private function to allocate the shared memory.
        :return: None.
        """
        #We use a RawArray because we don't want to deal with multiprocessing thread-safe nonsense.
        self._shared_block = mp.RawArray(self._dtype, self._mem_size)

        #Here we're loading the shared block into a numpy array so we can use it with little hassle.
        self._mem = np.frombuffer(self._shared_block, dtype=self._dtype)

    def cleanup(self):
        del self._mem
        self._mem = None

        del self._shared_block
        self._shared_block = None