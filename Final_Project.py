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

#///////////////GLOBAL VARIABLES/////////////////////////
isSpeaking = False # variable to keep track if the speaker is speaking or not
speechRateSamples = [] # array to hold the samples of speech rates of the speaker
emotionsList = [] # array that tracks the emotions that are used by the user
emotionNum = [] # Array that tracks "emotion use" each index in this array corresponds with the respective emotion in emotionsList[]
ahCounter = None # variable to keep track of how many filler words the speaker has used
t = 0 # variable to keep track of how long the speaker has talked in seconds

#================================ FACIAL EXPRESSION RECOGNITION ============================================================
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

        global isSpeaking # access global isSpeaking variable 

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
#----------------------------------END FACIAL RECOGNITION THREAD----------------------------------------------------------

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
        global ahCounter
        UI.statusbar.showMessage(flask.request.json['status']) # Get the text for the field 'status'
        if ahCounter == None:
            prevCount = 0
        else:
            prevCount = int(ahCounter)
        ahCounter = flask.request.json['ahCount'] # set ahCounter from client input
        UI.ahCountLabel.setText("Ah Count: " + ahCounter) # Get the text for the field 'ahCount'
        if isSpeaking and prevCount < int(ahCounter): # only play the audio to ding the speaker if incrementing Ah-Counter and if they are speaking
            playsound('ring.wav') # play audio to ding the speaker
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
#-------------------------------------END WEB SERVER THREAD--------------------------------------------------

#=======================================SPEECH RECOGNITION==================================================
class SpeechRecognitionThread(QThread):

    def run(self):
        # obtain audio from the microphone
        phraseTimeLimit = 5 # the amount of time, in seconds to record speaking audio from microphone
        speechRate = 0 # current speech rate of the speaker
        totalNumWords = 0 # total number of words speaker says
        global isSpeaking # use global isSpeaking variable

        # This will be used to calculate words per minute
        speechRateMultiplier = 60 / phraseTimeLimit # 60 seconds / phraseTimeLimit in seconds. 
        UI.speechOutputLabel.setText("Start speech once your voice is recognized. OR Simply say 'Start Speech'!") # output text to speechOutputLabel

        # obtain audio from the microphone
        r = sr.Recognizer()
        #r.energy_threshold = 100 # energy threshold of microphone to determine what volume is considered speaking or not

        # This will be used to calculate words per minute
        speechRateMultiplier = 60 / phraseTimeLimit # 60 seconds / phraseTimeLimit in seconds. 

        m = sr.Microphone() # instantiate a microphone variable
        pyAudio = pyaudio.PyAudio() # instantiate a pyaudio variable to see what microphones are available
        print(pyAudio.get_device_count()) # output to terminal the number of microphones available **debugging purposes only**
        print(m.list_microphone_names()) # output to terminal the names of the availabel microphones **debugging purposes only**

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
                if ("start speech" in googleRecognizedAudio) and (isSpeaking == False): # if user says "start speech", have the startBtn clicked to start speech
                    UI.startBtn.click() # click the start button
                if ("stop speech" in googleRecognizedAudio) and isSpeaking: # if the user says "stop speech", have the stopBtn clicked to stop speech
                    UI.stopBtn.click() # click the stop button
                    
                speechRate = res * speechRateMultiplier # calculate speech rate as words per minute (w/m) or (wpm)
                UI.speechOutputLabel.setText("You said: " + googleRecognizedAudio) # Output the recognized audio
                UI.numWordsLabel.setText("# Words: " + str(res)) # output number of words said
                UI.speechRateLabel.setText("Speech Rate: " + str(speechRate) + "wpm") # output current speech rate
                totalNumWords = totalNumWords + res # calculate total number of words said in speech so far
                speechRateSamples.append(speechRate) # keep track of the speechRate samples we have calculated
            except sr.UnknownValueError: # if audio is unrecognizable
                UI.speechOutputLabel.setText("Google Speech Recognition could not understand audio")
                UI.numWordsLabel.setText("# Words: N/A")
                UI.speechRateLabel.setText("Speech Rate: 0 wpm")
            except sr.RequestError as e: # if bad internet connection or if Google's API is unavailable
                UI.speechOutputLabel.setText("Could not request results from Google Speech Recognition service; {0}".format(e))
                UI.numWordsLabel.setText("# Words: N/A")
                UI.speechRateLabel.setText("Speech Rate: 0 wpm")
#--------------------------------END SPEECH RECOGNITION THREAD-----------------------------------------------

#==========================================TIMER=============================================================
class TimerThread(QThread):
    def run(self):
        greenThreshold = (UI.greenThreshMinBox.value() * 60) + (UI.greenThreshSecBox.value()) # Green threshold flag in seconds
        yellowThreshold = (UI.yellowThreshMinBox.value() * 60) + (UI.yellowThreshSecBox.value()) # yellow threshold flag in seconds
        redThreshold = (UI.redThreshMinBox.value() * 60) + (UI.redThreshSecBox.value()) # red threshold flag in seconds
        speechTimeLimit = (UI.speechLimitMinBox.value() * 60) + (UI.speechLimitSecBox.value()) # Time limit in seconds
        global isSpeaking # access global isSpeaking variable
        isSpeaking = True # the speaker is now speaking
        global t # access global time variable 
        while t <= speechTimeLimit: # while under the speech time limit
            mins, secs = divmod(t, 60) # convert t to seconds and minutes
            if greenThreshold <= t and t < yellowThreshold: # time for green flag?
                UI.timeLeftLabel.setStyleSheet("background-color: green")
                UI.timerLabel.setStyleSheet("background-color: green")
            elif yellowThreshold <= t and t < redThreshold: # time for yellow flag?
                UI.timeLeftLabel.setStyleSheet("background-color: yellow") 
                UI.timerLabel.setStyleSheet("background-color: yellow")
            elif redThreshold <= t: # time for red flag?
                UI.timeLeftLabel.setStyleSheet("background-color: red")
                UI.timerLabel.setStyleSheet("background-color: red")
            timer = '{:02d}:{:02d}'.format(mins, secs) # convert timer values to a string
            UI.timeLeftLabel.setText(timer) # output the current timer values to GUI
            time.sleep(1) # wait 1 second
            t += 1 # add one to timer variable
        UI.timeLeftLabel.setText("Limit\nReached") #output to GUI that time limit has been reached
        isSpeaking = False # speaker is no longer speaking
#--------------------------------------END TIMER THREAD-----------------------------------------------

#==========================================FILE I/O===================================================
def saveReport(totalAvgSpeechRate, topEmotion, leastEmotion, mins, secs):
    global ahCounter # access global ahCount variable
    reportFile = open("ToastMaster Report.txt", "w+") # open file in writing mode (overwrite if file already exists)

    # The follow .write statements will write the contents of the report to the "ToastMaster Report.txt" file
    reportFile.write("===========TOASTMASTERS' TOOLBOX REPORT===========\n")
    reportFile.write("   Average Words per Minute: " + str(totalAvgSpeechRate) + "\n")
    reportFile.write("  Your Most Used Emotion is: " + str(topEmotion) + "\n")
    reportFile.write(" Your Least Used Emotion is: " + str(leastEmotion) + "\n")
    reportFile.write("Number of Filler Words Used: " + ahCounter + "\n")
    reportFile.write("              You Spoke for: " + str(mins) + " minutes, " + str(secs) + " seconds\n")
    reportFile.close() # close the file

def importReport():
    reportFile = open("Toastmaster Report.txt", "r") # open report file as read only
    reportData = reportFile.read() # read in contents of file
    UI.reportOutputLabel.setText(reportData) # output contents of file to GUI
    reportFile.close() # close the file
#------------------------------------END FILE I/0 METHODS-----------------------------------------

#=====================================REPORTING METHODS==========================================
def generateReport():
    global ahCounter # access global ahCounter variable
    global t # access global timer variable
    if ahCounter == None: # if ahCounter is empty
        ahCounter = "0" # set ahCounter to 0
    sumSpeechRates = 0 # instantiate a variable to hold the summation of all the speech rates we have collected
    for x in speechRateSamples: # loop through speechRateSamples vector
        sumSpeechRates = x + sumSpeechRates # sum all the speech rate samples we have collected
    if len(speechRateSamples) != 0: # if we have data in speech rate samples vector
        totalAvgSpeechRate = sumSpeechRates / len(speechRateSamples) # calculate overall average of the vector of speech rate samples
    elif len(speechRateSamples) == 0: # if no data in speech rate samples vector
        totalAvgSpeechRate = 0 # set total average speech rate to 0

    mins, secs = divmod(t, 60) # convert t to minutes and seconds
    
    topEmotion = emotionsList[emotionNum.index(max(emotionNum))] # Find index emotion that was used MOST from emotionNum list, and use that index to find most used emotion
    leastEmotion = emotionsList[emotionNum.index(min(emotionNum))] # Find index emotion that was used LEAST from emotionNum list, and use that index to find most used emotion

    # the follow code creates a long string of the report and its data that will then be passed to the GUI
    outputText = "===========TOASTMASTERS' TOOLBOX REPORT===========\n"
    outputText = outputText + "   Average Words per Minute: " + str(totalAvgSpeechRate) + "\n"
    outputText = outputText + "   Your Top Used Emotion is: " + str(topEmotion) + "\n"
    outputText = outputText + " Your Least Used Emotion is: " + str(leastEmotion) + "\n"
    outputText = outputText + "Number of Filler Words Used: " + ahCounter + "\n"
    outputText = outputText + "              You Spoke for: " + str(mins) + " minutes, " + str(secs) + " seconds\n"

    UI.reportOutputLabel.setText(outputText) # output Report to reportOutputLabel
    UI.saveReportBtn.clicked.connect(lambda: saveReport(totalAvgSpeechRate,topEmotion,leastEmotion, mins, secs)) # connect saveReportBtn to saveReport function, and pass appropriate arguments

# go to the report page on GUI and generate the report
def goReportPage():
    UI.stackedWidget.setCurrentIndex(UI.stackedWidget.currentIndex() + 1) # change GUI to report page
    terminateThreads() # terminate current threads
    generateReport() # call the generateReport function to generate the report

# cancel the current report and go back to speaking page on GUI
def cancelReport():
    global speechRateSamples # access global speechRateSamples vector
    speechRateSamples = [] # empty the vector
    UI.stackedWidget.setCurrentIndex(UI.stackedWidget.currentIndex() - 1) # go back to speaking page on GUI
    webServerThread.start() # Begin web server thread
    FER_Thread.start() # Begin facial expression recognition thread
    SR_Thread.start()  # Begin speech recognition thread
#--------------------------------END REPORTING METHODS-----------------------------------------------

#==============================GENERIC APPLICATION METHODS======================================
def startSpeech():
    Timer_Thread.start() # Begin timing, now that the speech has started
    global isSpeaking # access global isSpeaking variable
    isSpeaking = True # the speaker is now speaking
    UI.stackedWidget_2.setCurrentIndex(UI.stackedWidget_2.currentIndex() + 1) # change start button to stop button on GUI

def stopSpeech():
    global isSpeaking #access global isSpeaking variable
    isSpeaking = False # the speaker is no longer speaking
    UI.stackedWidget_2.setCurrentIndex(UI.stackedWidget_2.currentIndex() - 1) # change stop button to start button on GUI
    terminateThreads() # terminate all the running threads

def setSpeechSettings():
    # The time threshold and limit settings will be set once the Timer_Thread Begins running
    UI.stackedWidget.setCurrentIndex(UI.stackedWidget.currentIndex() + 1)

# This will quit the application when called
def Quit():
    terminateThreads() # terminate all the running threads
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
#--------------------------------END APPLICATION METHODS-----------------------------------------------


App = QtWidgets.QApplication([]) # Initialize the application
UI=uic.loadUi("Final_Project.ui") # Load in specific UI from disk
UI.actionQuit.triggered.connect(Quit) # Connect Quit() method to actionQuit, and run when triggered

UI.generateReportBtn.clicked.connect(goReportPage) # connect Generate Report button click to goReportPage() function
UI.cancelBtn.clicked.connect(cancelReport) # connect Cancel button to cancelReport() function
UI.importReportBtn.clicked.connect(importReport) # connect Import Report button to importReport() function
UI.startBtn.clicked.connect(startSpeech) # connect Start button to startSpeech() function
UI.stopBtn.clicked.connect(stopSpeech) # coneect Stop button to stopSpeech() function
UI.enterBtn.clicked.connect(setSpeechSettings) # connect Enter button to setSpeechSettings()

UI.show() # Display the GUI

FER_Thread = VideoThread() # instantiate a new VideoThread
FER_Thread.new_frame_signal.connect(Update_Image) # When a new frame arrives, run Update_Image() method
UI.ahCountLabel.setText("Ah Counter Disconnected") # Set the initial text in lblOutput to indicate no client is connected
webServerThread = FlaskServer() # instantiate a thread of FlaskServer
SR_Thread = SpeechRecognitionThread() # instantiate a thread of SpeechRecognitionThread
Timer_Thread = TimerThread() # instantiate a thread of TimerThread

webServerThread.start() # Begin web server thread
time.sleep(2) # wait 2 seconds
FER_Thread.start() # Begin facial expression recognition thread
time.sleep(3) # wait 3 seconds
SR_Thread.start() # Begin speech recognition thread

sys.exit(App.exec_()) # Exit 