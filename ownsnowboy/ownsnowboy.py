import logging
import os
import sys
from threading import Thread

from kalliope import Utils 

from cffi import FFI as _FFI

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from snowboydecoder import HotwordDetector


class SnowboyModelNotFound(Exception):
    pass


class MissingParameterException(Exception):
    pass

logging.basicConfig()
logger = logging.getLogger("kalliope")


class Ownsnowboy(Thread):

    def __init__(self, **kwargs):
        super(Ownsnowboy, self).__init__()
        self._ignore_stderr()
        # pause listening boolean
        self.interrupted = False
        self.apply_frontend = kwargs.get('apply_frontend', False)
        
        # callback function to call when hotword caught
        self.callback = kwargs.get('callback', None)
        if self.callback is None:
            raise MissingParameterException("callback function is required with snowboy")

        self.keywords = kwargs.get('keywords', None)      
        keyword_file_paths = list()
        sensitivities = list()
        for keyword in self.keywords:
            path = Utils.get_real_file_path(keyword['keyword']['pmdl_path'])  
            try:
                os.path.isfile(path)
            except TypeError: 
                raise SnowboyModelNotFound("The Snowboy keyword at %s does not exist" % keyword['keyword']['pmdl_path'])
            keyword_file_paths.append(path)
            try:
                for sens in keyword['keyword']['sensitivity']:
                    sensitivities.append(sens)
            except KeyError:
                sensitivities.append("0.5")

        self.detector = HotwordDetector(keyword_file_paths,
                                       sensitivity=sensitivities,
                                       detected_callback=self.callback,
                                       interrupt_check=self.interrupt_callback,
                                       apply_frontend=self.apply_frontend,
                                       sleep_time=0.01)


    def interrupt_callback(self):
        """
        This function will be passed to snowboy to stop the main thread
        :return:
        """
        return self.interrupted


    def run(self):
        """
        Start the snowboy thread and wait for a Kalliope trigger word
        :return:
        """
        # start snowboy loop forever
        self.detector.daemon = True
        self.detector.start()
        self.detector.join()

    def stop(self):
        """
        Kill the snowboy process
        :return: 
        """
        logger.debug("Killing snowboy process")
        self.interrupted = True
        self.detector.terminate()
    
    def pause(self):
        """
        pause the Snowboy main thread
        """
        logger.debug("Pausing snowboy process")
        self.detector.paused = True

    def unpause(self):
        """
        unpause the Snowboy main thread
        """
        logger.debug("Unpausing snowboy process")
        self.detector.paused = False

    @staticmethod
    def _ignore_stderr():
        """
        Try to forward PortAudio messages from stderr to /dev/null.
        """
        ffi = _FFI()
        ffi.cdef("""
            /* from stdio.h */
            FILE* fopen(const char* path, const char* mode);
            int fclose(FILE* fp);
            FILE* stderr;  /* GNU C library */
            FILE* __stderrp;  /* Mac OS X */
            """)
        stdio = ffi.dlopen(None)
        devnull = stdio.fopen(os.devnull.encode(), b'w')
        try:
            stdio.stderr = devnull
        except KeyError:
            try:
                stdio.__stderrp = devnull
            except KeyError:
                stdio.fclose(devnull)
