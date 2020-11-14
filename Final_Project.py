import sys
import cv2
import numpy
from PyQt5 import QtWidgets,QtGui,uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
from fer import FER
from fer import Video
import pyaudio
import flask
import time
import speech_recognition as sr
import string
from playsound import playsound

isSpeaking = False # variable to keep track if the speaker is speaking or not
speechRateSamples = [] # array to hold the samples of speech rates of the speaker
emotionsList = [] # array that tracks the emotions that are used by the user
emotionNum = [] # Array that tracks "emotion use" each index in this array corresponds with the respective emotion in emotionsList[]
ahCounter = None # variable to keep track of how many filler words the speaker has used

#================================ FACIAL RECOGNITION ==============================================================
# This class describes the video thread
class VideoThread(QThread):
    new_frame_signal = pyqtSignal(numpy.ndarray)

    def run(self):
        # Capture from Webcam
        width = 400 # Width of the captured video frame, units in pixels
        height = 300 # Height of the captured video frame, units in pixels
        video_capture_device = cv2.VideoCapture(0)
        video_capture_device.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        video_capture_device.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        fps = 0 # initialize fps counter to 0
        detector = FER() # initialize Facial Expression Recognition

        global isSpeaking

        while True:
            startTime = time.time() # Get the start time for the fps calculation

            # I averaged about 20 fps, so 30 frames would allow for a time difference of a little more than a second
            frameCounter = 50       # Let the for loop count to this number before calculating new fps

            for i in range(0, frameCounter): # for loop to allow a time difference to calculate fps
                if self.isInterruptionRequested():
                    video_capture_device.release()
                    return
                else:
                    ret, frame = video_capture_device.read()
                    if ret:
                        self.new_frame_signal.emit(frame)

                        # When no face is detected, the emotion [] array is empty, so when detector.top_emotion() is called, 
                        # an IndexError is thrown. The try: will execute code when a face is detected, and therefore no IndexError.
                        # except IndexError as error: this code will execute when no face is detected, and the IndexError is thrown. 
                        try:
                            emotion, score = detector.top_emotion(frame) # get the top emotion and score from the video frame
                            if isSpeaking:
                                if emotion in emotionsList: # save the emotion to a list and keep track of number of times emotion is recognized
                                    index = emotionsList.index(emotion) # Get the index of current emotion
                                    emotionNum[index] += emotionNum[index] # add 1 to the array at the index of current emotion to keep track of "emotion use"
                                else:
                                    emotionsList.append(emotion) # if emotion does not exist yet, append it into the array
                                    emotionNum.append(1) # begin keeping track of this new emotion in the array that tracks "emotion use"

                            UI.emotionMagLabel.setText("Emotion Magnitude: " + str(score)) # Output the magnitude of emotion to GUI
                            UI.emotionTypeLabel.setText("  Current Emotion: " + emotion) # Output the type of emotion to GUI

                        except IndexError as error: # no face is detected
                            UI.emotionMagLabel.setText("Emotion Magnitude: " + "N/A") # Magnitude of emotion is unavailabe since no face is detected
                            UI.emotionTypeLabel.setText("  Current Emotion: " + "N/A") # Type of emotion is unavailabe since no face is detected

                        UI.outputFPS.setText("Frames Per Second: " + str(fps)) # Output the current fps                
            
            stopTime = time.time() # Get the stop time for the fps calculation
            fps = round(frameCounter / float(stopTime - startTime),3) # calculate the current fps, and round the answer to 3 decimal places

# This function runs whenever a new frame arrives, so it should happen about 20-30 times a second, for FPS in a range of 20-30 fps
def Update_Image(frame):
    # If the Mirror Video button is toggled, mirror the output of the video feed 
    if UI.mirrorToggle.isChecked() == True: # Check to see if the Mirror Button is Toggles
        frame = cv2.flip(frame,1) # Flip the current frame of the video feed


    height, width, channel = frame.shape # gather information from current frame
    h = UI.lblOutput.height() # Get the height from the lblOutput, this is used for setting the size of the image inside the label
    w = UI.lblOutput.width()  # Get the width from the lblOutput, this is used for setting the size of the image inside the label
    bytesPerLine = 3 * width
    qImg = QtGui.QImage(frame.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888) # generate qImg
    qImg = qImg.rgbSwapped()

    # Map the pixels of the frame from the video feed to the lblOutput object. 
    # .scaled() specifies how the mapped pixels are scaled to the size of lblOutput. Here, I specify that I want to preserve
    # the aspect ratio of the frame from the video feed
    UI.lblOutput.setPixmap(QtGui.QPixmap(qImg).scaled(w,h,Qt.KeepAspectRatio,Qt.FastTransformation))


#========================================= WEB SERVER ====================================================================
class FlaskServer(QThread):
    app = flask.Flask(__name__) # instantiate the flask application
    app.config["DEBUG"] = False # Set DEBUG to False so others can access the web server

    def run(self):
       self.app.run(host='0.0.0.0') # Allow anyone on the network to connect to the web server

    @app.route('/', methods=['GET'])
    def Home():
        return "<h1>Hello, World!</h1><p>This webserver is working!</p>" # Output that verifies the webserver is working

    @app.route('/time', methods=['GET']) # run Get_Time when the client requests to post to http://10.0.2.5:5000/time
    # This function will return the current time from the web server
    def Get_Time():
        t = time.localtime() # get time from system
        current_time = time.strftime("%H:%M:%S", t)
        return flask.jsonify(Current_Time=current_time)


    @app.route('/set_text', methods=['POST']) # run Set_Text when the client requests to post to http://10.0.2.5:5000/set_text
    # This function will update the text fields for the server gui
    def Set_Text(): 
        global isSpeaking
        UI.statusbar.showMessage(flask.request.json['status']) # Get the text for the field 'status'
        global ahCounter
        if ahCounter == None:
            prevCount = 0
        else:
            prevCount = int(ahCounter)
        ahCounter = flask.request.json['ahCount']
        UI.ahCountLabel.setText("Ah Count: " + ahCounter) # Get the text for the field 'ahCount'
        if isSpeaking and prevCount < int(ahCounter):
            playsound('ring.wav')
            print(prevCount + "\n")
            print(ahCounter)
            return flask.jsonify(flask.request.json) # return json object
        else:
            return flask.jsonify(flask.request.json) # return json object

    @app.route('/set_color', methods=['POST']) # run Set_Color when the client requests to post to http://10.0.2.5:5000/set_color
    # This function will update the lblOutput colors, based upon the values set by the client
    def Set_Color():
        redColorValue = flask.request.json['red'] # Get the current red rgb value from client
        greenColorValue = flask.request.json['green'] # Get the current green rgb value from client
        blueColorValue = flask.request.json['blue'] # Get the current blue rgb value from client
        BG_Color = "rgb(" + str(redColorValue) + "," + str(greenColorValue) + "," + str(blueColorValue) + ");" # set the background variable to the values read in from client
        FG_Color = "rgb(255,255,255);" # set the foreground variable to these values
        UI.ahCountLabel.setStyleSheet("QLabel {background-color :" + BG_Color + "color : " + FG_Color + "}") # Set the colors of the QLabel widget using values from BG_Color and FG_Color
        UI.redMagLabel.setText("Red:   " + str(redColorValue)) # Output the current value of red rgb background color from client
        UI.greenMagLabel.setText("Green: " + str(greenColorValue)) # Output the current value of green rgb background color from client
        UI.blueMagLabel.setText("Blue:  " + str(blueColorValue)) # Output the current value of blue rgb background color from client
        return flask.jsonify(flask.request.json) # return json object


#=======================================SPEECH RECOGNITION==================================================
class SpeechRecognitionThread(QThread):

    def run(self):
        # obtain audio from the microphone
        phraseTimeLimit = 5
        speechRate = 0 # current speech rate of the speaker
        totalNumWords = 0

        # This will be used to calculate words per minute
        speechRateMultiplier = 60 / phraseTimeLimit # 60 seconds / phraseTimeLimit in seconds. 
        UI.speechOutputLabel.setText("Say something! Start speech once your voice is recognized. Output goes here!")
        # obtain audio from the microphone
        r = sr.Recognizer()
        #r.energy_threshold = 100
        # This will be used to calculate words per minute
        speechRateMultiplier = 60 / phraseTimeLimit # 60 seconds / phraseTimeLimit in seconds. 
        m = sr.Microphone()
        pyAudio = pyaudio.PyAudio()
        print(pyAudio.get_device_count())
        #print(m.list_working_microphones())
        print(m.list_microphone_names())

        # Test speech recognition using Google API
        while True:
            with sr.Microphone() as source:
                audio = r.listen(source, phrase_time_limit=phraseTimeLimit)
            # recognize speech using Google Speech Recognition
            try:
                # for testing purposes, we're just using the default API key
                # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
                # instead of `r.recognize_google(audio)`
                googleRecognizedAudio = r.recognize_google(audio)
                #print("Google Speech Recognition thinks you said: " + googleRecognizedAudio)
                res = len(str(googleRecognizedAudio).split())
                speechRate = res * speechRateMultiplier
                UI.speechOutputLabel.setText("You said: " + googleRecognizedAudio)
                UI.numWordsLabel.setText("# Words: " + str(res))
                UI.speechRateLabel.setText("Speech Rate: " + str(speechRate) + "wpm")
                totalNumWords = totalNumWords + res
                speechRateSamples.append(speechRate)
            except sr.UnknownValueError:
                UI.speechOutputLabel.setText("Google Speech Recognition could not understand audio")
                UI.numWordsLabel.setText("# Words: N/A")
                UI.speechRateLabel.setText("Speech Rate: 0 wpm")
            except sr.RequestError as e:
                UI.speechOutputLabel.setText("Could not request results from Google Speech Recognition service; {0}".format(e))
                UI.numWordsLabel.setText("# Words: N/A")
                UI.speechRateLabel.setText("Speech Rate: 0 wpm")


#==============================FILE I/O===========================================
def saveReport(totalAvgSpeechRate, topEmotion, leastEmotion):
    global ahCounter
    reportFile = open("ToastMaster Report.txt", "w+")
    reportFile.write("==========TOASTMASTERS' TOOLBOX REPORT==========\n")
    reportFile.write("   Average Words per Minute: " + str(totalAvgSpeechRate) + "\n")
    reportFile.write("  Your Most Used Emotion is: " + str(topEmotion) + "\n")
    reportFile.write(" Your Least Used Emotion is: " + str(leastEmotion) + "\n")
    #reportFile.write(" Your Third Most Used Emotion is: " + "\n")
    reportFile.write("Number of Filler Words Used: " + ahCounter + "\n")
    reportFile.close()

def generateReport():
    global ahCounter
    if ahCounter == None:
        ahCounter = "0"
    sumSpeechRates = 0
    for x in speechRateSamples:
        sumSpeechRates = x + sumSpeechRates
    if len(speechRateSamples) != 0:
        totalAvgSpeechRate = sumSpeechRates / len(speechRateSamples)
    elif len(speechRateSamples) == 0:
        totalAvgSpeechRate = 0
    
    topEmotion = emotionsList[emotionNum.index(max(emotionNum))] # Find index emotion that was used MOST from emotionNum list, and use that index to find most used emotion
    leastEmotion = emotionsList[emotionNum.index(min(emotionNum))] # Find index emotion that was used LEAST from emotionNum list, and use that index to find most used emotion

    outputText = "==========TOASTMASTERS' TOOLBOX REPORT==========\n"
    outputText = outputText + "   Average Words per Minute: " + str(totalAvgSpeechRate) + "\n"
    outputText = outputText + "   Your Top Used Emotion is: " + str(topEmotion) + "\n"
    outputText = outputText + " Your Least Used Emotion is: " + str(leastEmotion) + "\n"
    #outputText = outputText + " Your Third Most Used Emotion is: " + "\n"
    outputText = outputText + "Number of Filler Words Used: " + ahCounter + "\n"
    UI.reportOutputLabel.setText(outputText)
    UI.saveReportBtn.clicked.connect(lambda: saveReport(totalAvgSpeechRate,topEmotion,leastEmotion))

def importReport():
    reportFile = open("Toastmaster Report.txt", "r")
    reportData = reportFile.read()
    UI.reportOutputLabel.setText(reportData)
    reportFile.close()


#==============================REPORTING==========================================
def goReportPage():
    UI.stackedWidget.setCurrentIndex(UI.stackedWidget.currentIndex() + 1)
    terminateThreads()
    generateReport()

def cancelReport():
    global speechRateSamples
    speechRateSamples = []
    UI.stackedWidget.setCurrentIndex(UI.stackedWidget.currentIndex() - 1)
    webServerThread.start() # Begin web server thread
    FER_Thread.start() # Begin facial expression recognition thread
    SR_Thread.start()  # Begin speech recognition thread


#==============================TIMER=============================================
class TimerThread(QThread):
    def run(self):
        greenThreshold = (UI.greenThreshMinBox.value() * 60) + (UI.greenThreshSecBox.value()) # Green threshold flag in seconds
        yellowThreshold = (UI.yellowThreshMinBox.value() * 60) + (UI.yellowThreshSecBox.value()) # yellow threshold flag in seconds
        redThreshold = (UI.redThreshMinBox.value() * 60) + (UI.redThreshSecBox.value()) # red threshold flag in seconds
        speechTimeLimit = (UI.speechLimitMinBox.value() * 60) + (UI.speechLimitSecBox.value()) # Time limit in seconds
        isSpeaking = True
        t = 0
        while t <= speechTimeLimit: 
            mins, secs = divmod(t, 60) 
            if greenThreshold <= t and t < yellowThreshold:
                UI.timeLeftLabel.setStyleSheet("background-color: green")
            elif yellowThreshold <= t and t < redThreshold:
                UI.timeLeftLabel.setStyleSheet("background-color: yellow")
            elif redThreshold <= t:
                UI.timeLeftLabel.setStyleSheet("background-color: red")
            timer = '{:02d}:{:02d}'.format(mins, secs) 
            #print(timer, end="\r") 
            UI.timeLeftLabel.setText(timer)
            time.sleep(1) 
            t += 1
        UI.timeLeftLabel.setText("Limit\nReached")
        isSpeaking = False

def startSpeech():
    Timer_Thread.start() # Begin timing, now that the speech has started
    global isSpeaking
    isSpeaking = True
    UI.stackedWidget_2.setCurrentIndex(UI.stackedWidget_2.currentIndex() + 1)

def stopSpeech():
    global isSpeaking
    isSpeaking = False
    terminateThreads()
    UI.stackedWidget_2.setCurrentIndex(UI.stackedWidget_2.currentIndex() - 1)

def setSpeechSettings():
    # The time threshold and limit settings will be set once the Timer_Thread Begins running
    UI.stackedWidget.setCurrentIndex(UI.stackedWidget.currentIndex() + 1)


# This will quit the application when called
def Quit():
    terminateThreads()
    App.quit()

def terminateThreads():
    if (FER_Thread.isRunning()): # check if Facial Expression Recognition thread is running
        print("FER was running")
        FER_Thread.requestInterruption() # if running, kill it
        FER_Thread.wait()

    if (webServerThread.isRunning()): # check if Flask Server thread is running
        print("Web Server Thread was running")
        webServerThread.terminate() # if running, kill it
        webServerThread.wait()

    if(SR_Thread.isRunning()): # check if Speech Recognition thread is running
        print("Speech Recogntion Thread was running")
        SR_Thread.requestInterruption()
        SR_Thread.terminate() # if running, kill it
        SR_Thread.wait()
    
    if(Timer_Thread.isRunning()): # check is Timer Thread is running
        print("Timer Thread was running")
        Timer_Thread.requestInterruption()
        Timer_Thread.terminate() # if running, kill it
        Timer_Thread.wait()


App = QtWidgets.QApplication([]) # Initialize the application
UI=uic.loadUi("Final_Project.ui") # Load in specific UI from disk
UI.actionQuit.triggered.connect(Quit) # Connect Quit() method to actionQuit, and run when triggered

UI.generateReportBtn.clicked.connect(goReportPage)
UI.cancelBtn.clicked.connect(cancelReport)
#UI.saveReportBtn.clicked.connect(saveReport)
UI.importReportBtn.clicked.connect(importReport)
UI.startBtn.clicked.connect(startSpeech)
UI.stopBtn.clicked.connect(stopSpeech)
UI.enterBtn.clicked.connect(setSpeechSettings)

UI.show() # Display the GUI

FER_Thread = VideoThread() # instantiate a new VideoThread
FER_Thread.new_frame_signal.connect(Update_Image) # When a new frame arrives, run Update_Image() method
UI.ahCountLabel.setText("Ah Counter Disconnected") # Set the initial text in lblOutput to indicate no client is connected
webServerThread = FlaskServer() # instantiate a thread of FlaskServer
SR_Thread = SpeechRecognitionThread()
Timer_Thread = TimerThread()

webServerThread.start() # Begin web server thread
time.sleep(2)
FER_Thread.start() # Begin facial expression recognition thread
time.sleep(3)
SR_Thread.start()

sys.exit(App.exec_()) # Exit 