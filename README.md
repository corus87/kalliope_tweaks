My tweaks for a faster start to speak after the hotword is triggered. 

After the hotword is triggered, the speech recorder immediately start to record, therefor I use some code taken from the [Mycroft project](https://github.com/MycroftAI/mycroft-core/tree/dev/mycroft/client/speech).
 
Place the ownsnowboy folder in resources/trigger/ in your starterkit. Don‘t forget to change the trigger in settings.yml to ownsnowboy.

Place Utils.py and OwnSpeech.py in the kalliope folder under kalliope/stt/

You have to run the setup again to install the new files to Kalliope