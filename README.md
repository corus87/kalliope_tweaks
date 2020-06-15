My tweaks for a faster start to speak after the hotword is triggered. 

After the hotword is triggered, the speech recorder immediately start to record, therefor I use some code taken from the [Mycroft project](https://github.com/MycroftAI/mycroft-core/tree/dev/mycroft/client/speech).
 
Place the ownsnowboy folder in resources/trigger/ in your starterkit. Don‘t forget to change the trigger in settings.yml to ownsnowboy.


[You can mostly follow the installtion guide for method 2](https://kalliope-project.github.io/kalliope/installation/raspbian/)

After you download kalliope, replace Utils.py in the kalliope folder under ```kalliope/stt/``` also place OwnSpeech.py in ```kalliope/stt/```.

Now just run the setup with ```sudo python3 setup.py install```

That's all. 
