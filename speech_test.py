#!/usr/bin/env python3

# NOTE: this example requires PyAudio because it uses the Microphone class

import speech_recognition as sr
import string

# obtain audio from the microphone
r = sr.Recognizer()
phraseTimeLimit = 5
speechRate = 0

# This will be used to calculate words per minute
speechRateMultiplier = 60 / phraseTimeLimit # 60 seconds / phraseTimeLimit in seconds. 

# Test speech recognition using Google API
while True:
    with sr.Microphone() as source:
        print("Say something!")
        audio = r.listen(source, phrase_time_limit=phraseTimeLimit)
    # recognize speech using Google Speech Recognition
    try:
        # for testing purposes, we're just using the default API key
        # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
        # instead of `r.recognize_google(audio)`
        googleRecognizedAudio = r.recognize_google(audio)
        print("Google Speech Recognition thinks you said: " + googleRecognizedAudio)
        res = len(str(googleRecognizedAudio).split())
        speechRate = res * speechRateMultiplier
        print("You said " + str(res) + " words")
        print("Your speech rate is: " + str(speechRate) + " words/minute")
    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio")
    except sr.RequestError as e:
        print("Could not request results from Google Speech Recognition service; {0}".format(e))

# Test speech using Sphinx. Does not work very well, especially compared to Google
while False:
    with sr.Microphone() as source:
        print("Say something!")
        audio = r.listen(source, phrase_time_limit=5)
    try:
        print("Sphinx thinks you said " + r.recognize_sphinx(audio))
    except sr.UnknownValueError:
        print("Sphinx could not understand audio")
    except sr.RequestError as e:
        print("Sphinx error; {0}".format(e))