#!/usr/bin/env python

import collections
import pyaudio
import time
import wave
import os
import logging
from ctypes import *
from contextlib import contextmanager
from threading import Thread
from kalliope import Utils
import sys

from kalliope.core.Cortex import Cortex
from kalliope.stt.Utils import SpeechRecorder
from kalliope.core.HookManager import HookManager

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from snowboydetect import SnowboyDetect
from datetime import datetime

logging.basicConfig()
logger = logging.getLogger("kalliope")

TOP_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCE_FILE = os.path.join(TOP_DIR, "resources/common.res")


def py_error_handler(filename, line, function, err, fmt):
    pass

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def no_alsa_error():
    try:
        asound = cdll.LoadLibrary('libasound.so')
        asound.snd_lib_error_set_handler(c_error_handler)
        yield
        asound.snd_lib_error_set_handler(None)
    except:
        yield
        pass

class RingBuffer(object):
    """Ring buffer to hold audio from PortAudio"""
    def __init__(self, size = 4096):
        self._buf = collections.deque(maxlen=size)

    def extend(self, data):
        """Adds data to the end of buffer"""
        self._buf.extend(data)

    def get(self):
        """Retrieves data from the beginning of buffer and clears it"""
        tmp = bytes(bytearray(self._buf))
        self._buf.clear()
        return tmp

class HotwordDetector(Thread):
    """
    Snowboy decoder to detect whether a keyword specified by `decoder_model`
    exists in a microphone input stream.

    :param decoder_model: decoder model file path, a string or a list of strings
    :param resource: resource file path.
    :param sensitivity: decoder sensitivity, a float of a list of floats.
                              The bigger the value, the more senstive the
                              decoder. If an empty list is provided, then the
                              default sensitivity in the model will be used.
    :param audio_gain: multiply input volume by this factor.
    :param apply_frontend: applies the frontend processing algorithm if True.
    """
    def __init__(self, decoder_model,
                 sleep_time=0.03,
                 resource=RESOURCE_FILE,
                 sensitivity=[],
                 audio_gain=1,
                 apply_frontend=False,
                 detected_callback=None,
                 interrupt_check=lambda: False
                 ):
                 
        super(HotwordDetector, self).__init__()
        self.sleep_time = sleep_time
        self.kill_received = False
        self.paused = False
        self.detected_callback = detected_callback
        self.interrupt_check = interrupt_check
    

        def audio_callback(in_data, frame_count, time_info, status):
            self.ring_buffer.extend(in_data)
            play_data = chr(0) * len(in_data)
            return play_data, pyaudio.paContinue

        tm = type(decoder_model)
        ts = type(sensitivity)
        if tm is not list:
            decoder_model = [decoder_model]
        if ts is not list:
            sensitivity = [sensitivity]
        model_str = ",".join(decoder_model)
        
        self.keyword_names = list()
        self.keyword_names.append('dummy')
        for n in decoder_model:
            name = os.path.basename(n).replace('.pmdl', '').replace('.umdl', '')
            if name == "jarvis" and "umdl" in n: # Its a special case for the jarvis.umdl which contains two hotwords
                self.keyword_names.append('jarvis_0')
            self.keyword_names.append(name)

        self.detector = SnowboyDetect(
            resource_filename=resource.encode(), model_str=model_str.encode())
        self.detector.SetAudioGain(audio_gain)
        self.detector.ApplyFrontend(apply_frontend)
        self.num_hotwords = self.detector.NumHotwords()


        if len(decoder_model) > 1 and len(sensitivity) == 1:
            sensitivity = sensitivity*self.num_hotwords
        if len(sensitivity) != 0:
            assert self.num_hotwords == len(sensitivity), \
                "number of hotwords in decoder_model (%d) and sensitivity " \
                "(%d) does not match" % (self.num_hotwords, len(sensitivity))
        sensitivity_str = ",".join([str(t) for t in sensitivity])
        if len(sensitivity) != 0:
            self.detector.SetSensitivity(sensitivity_str.encode())

        self.ring_buffer = RingBuffer(
            self.detector.NumChannels() * self.detector.SampleRate() * 5)
        with no_alsa_error():
            self.audio = pyaudio.PyAudio()
        self.stream_in = self.audio.open(
            input=True, output=False,
            format=self.audio.get_format_from_width(
                self.detector.BitsPerSample() / 8),
            channels=self.detector.NumChannels(),
            rate=self.detector.SampleRate(),
            frames_per_buffer=1024,
            stream_callback=audio_callback)


    def run(self):
        """
        Start the voice detector. For every `sleep_time` second it checks the
        audio buffer for triggering keywords. If detected, then call
        corresponding function in `detected_callback`, which can be a single
        function (single model) or a list of callback functions (multiple
        models). Every loop it also calls `interrupt_check` -- if it returns
        True, then breaks from the loop and return.

        :param detected_callback: a function or list of functions. The number of
                                  items must match the number of models in
                                  `decoder_model`.
        :param interrupt_check: a function that returns True if the main loop
                                needs to stop.
        :param float sleep_time: how much time in second every loop waits.
        :param audio_recorder_callback: if specified, this will be called after
                                        a keyword has been spoken and after the
                                        phrase immediately after the keyword has
                                        been recorded. The function will be
                                        passed the name of the file where the
                                        phrase was recorded.
        :param silent_count_threshold: indicates how long silence must be heard
                                       to mark the end of a phrase that is
                                       being recorded.
        :param recording_timeout: limits the maximum length of a recording.
        :return: None
        """
        if self.interrupt_check():
            logger.debug("detect voice return")
            return
        
        tc = type(self.detected_callback)
        if tc is not list:
            self.detected_callback = [self.detected_callback]
        if len(self.detected_callback) == 1 and self.num_hotwords > 1:
            self.detected_callback *= self.num_hotwords

        assert self.num_hotwords == len(self.detected_callback), \
            "Error: hotwords in your models (%d) do not match the number of " \
            "callbacks (%d)" % (self.num_hotwords, len(self.detected_callback))

        logger.debug("detecting...")

        SR = SpeechRecorder()
                
        while not self.kill_received:
            #if not self.paused:
            if self.interrupt_check():
                logger.debug("detect voice break")
                break
            data = self.ring_buffer.get()
            
            if len(data) == 0:
                time.sleep(self.sleep_time)
                continue
            self.saveMessage(data) # Save trigger data so it can be append to the record for STT
            status = self.detector.RunDetection(data)
            
            if status > 0: #key word found
                SR.start()              # Start the speech recorder
                Utils.print_info("Keyword " + self.keyword_names[status] + " detected")
                Cortex.save('kalliope_trigger_called', self.keyword_names[status])      # I save it to the Cortex, to use it by another neuron 
                                                                                        # for changing the tts acording to the trigger name
                HookManager.on_triggered()
                callback = self.detected_callback[status-1]
                if callback is not None:
                    callback()

            if status == -1:
                logger.warning("Error initializing streams or reading audio data")

        logger.debug("finished.")

    def saveMessage(self, data):
        """
        Save the message.
        """

        filename = '/tmp/kalliope/tmp_uploaded_audio/hotword_file.wav'

        #use wave to save data
        wf = wave.open(filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(self.audio.get_sample_size(
            self.audio.get_format_from_width(
                self.detector.BitsPerSample() / 8)))
        wf.setframerate(self.detector.SampleRate())
        wf.writeframes(data)
        wf.close()

    def terminate(self):
        """
        Terminate audio stream. Users cannot call start() again to detect.
        :return: None
        """
        self.stream_in.stop_stream()
        self.stream_in.close()
        self.audio.terminate()
