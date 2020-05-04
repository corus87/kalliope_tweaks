import threading
from threading import Thread

import logging
import speech_recognition as sr

from kalliope import Utils, SettingLoader

from kalliope.stt import OwnSpeech
import os
import time

from pydub import AudioSegment
#import wave

logging.basicConfig()
logger = logging.getLogger("kalliope")

OWN_AUDIO_FILE = '/tmp/kalliope/tmp_uploaded_audio/own_audio_file.wav'
HOTWORD_FILE = '/tmp/kalliope/tmp_uploaded_audio/hotword_file.wav'

class SpeechRecognition(Thread):

    def __init__(self, audio_file=None):
        """
        Thread used to caught n audio from the microphone and pass it to a callback method
        """
        super(SpeechRecognition, self).__init__()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.callback = None
        self.audio_stream = None
        # get global configuration
        sl = SettingLoader()
        self.settings = sl.settings


        if self.audio_file_exist(OWN_AUDIO_FILE):  # Maybe provided by the APP
            self.audio_file = OWN_AUDIO_FILE
        else:
            if self.load_status() == 'is_recording': # Record thread is still active
                while not self.record_is_finished():
                    time.sleep(0.1)
            else:
                SR = SpeechRecorder()
                SR.start()
                while not self.record_is_finished():
                    time.sleep(0.1)

        if self.audio_file_exist(HOTWORD_FILE):     # If there is a hotword_file, then merge both togther 
            self.merge_audio()

        if self.audio_file:
            with sr.AudioFile(self.audio_file) as source:
                self.audio_stream = self.recognizer.record(source) 
            os.remove(self.audio_file)              # we need to remove it, otherwise it would end in a loop
            if self.audio_file_exist(HOTWORD_FILE):
                os.remove(HOTWORD_FILE)
                
    def run(self):
        self.callback(self.recognizer, self.audio_stream)
    
    def audio_file_exist(self, file):
        if os.path.exists(file):
            return True
        return False

    def record_is_finished(self):
        if self.load_status() == 'is_recording':
            while True:
                if self.load_status() == "record_finished":
                    self.audio_file = OWN_AUDIO_FILE
                    return True
        return False

    def load_status(self):
        with open('/tmp/kalliope/record_status', 'r') as status:
            return status.read()


    def merge_audio(self):
        sound1 = AudioSegment.from_wav(OWN_AUDIO_FILE)
        sound2 = AudioSegment.from_wav(HOTWORD_FILE)
        combined_sounds = sound2 + sound1
        combined_sounds.export(OWN_AUDIO_FILE, format="wav")
        
    def start_processing(self):
        """
        A method to start the thread
        """
        self.start()

    def set_callback(self, callback):
        """
        set the callback method that will receive the audio stream caught by the microphone
        :param callback: callback method
        :return:
        """
        self.callback = callback



class SpeechRecorder(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        sl = SettingLoader()
        self.settings = sl.settings # To set the multiplier and energy_ratio in settings.yml, it need to be set in models/settings etc.

    def run(self):
        #responsive = OwnSpeech.ResponsiveRecognizer(multiplier=self.settings.options.ownspeech_energy_ratio,    
        #                                            energy_ratio=self.settings.options.ownspeech_multiplier)
        responsive = OwnSpeech.ResponsiveRecognizer(multiplier=1.0, 
                                                    energy_ratio=1.5)   
        mic = OwnSpeech.MutableMicrophone()
        Utils.print_success("[SpeechRecorder] Listening...")
        self.write_status("is_recording")

        with mic as source:
            audio_data = responsive.listen(source)
        
        with open(OWN_AUDIO_FILE, 'wb') as file:
            file.write(audio_data.get_wav_data())

        self.write_status("record_finished")

    def write_status(self, status):
        with open('/tmp/kalliope/record_status', 'w') as record_status:
            record_status.write(status)


