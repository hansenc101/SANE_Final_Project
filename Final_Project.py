import sys
import cv2
import numpy
from PyQt5 import QtWidgets,QtGui,uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
from fer import FER
from fer import Video
import flask
import time
import speech_recognition as sr
import string

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

        while True:
            startTime = time.time() # Get the start time for the fps calculation

            # I averaged about 20 fps, so 30 frames would allow for a time difference of a little more than a second
            frameCounter = 30       # Let the for loop count to this number before calculating new fps


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
                            UI.emotionMagLabel.setText("Score: " + str(score)) # Output the magnitude of emotion to GUI
                            UI.emotionTypeLabel.setText("Emotion: " + emotion) # Output the type of emotion to GUI

                        except IndexError as error: # no face is detected
                            UI.emotionMagLabel.setText("Score N/A ") # Magnitude of emotion is unavailabe since no face is detected
                            UI.emotionTypeLabel.setText("Emotion N/A") # Type of emotion is unavailabe since no face is detected

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
        print (flask.request.json) 
        UI.statusbar.showMessage(flask.request.json['status']) # Get the text for the field 'status'
        UI.ahCountLabel.setText("Ah Count: " + flask.request.json['ahCount']) # Get the text for the field 'ahCount'
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
        speechRate = 0

        # This will be used to calculate words per minute
        speechRateMultiplier = 60 / phraseTimeLimit # 60 seconds / phraseTimeLimit in seconds. 
        UI.speechOutputLabel.setText("Say something...")
        # Test speech recognition using Google API
        while True:
            with sr.Microphone() as source:
                # UI.speechOutputLabel.setText("Say something...")
                audio = sr.Recognizer().listen(source, phrase_time_limit=phraseTimeLimit)
            # recognize speech using Google Speech Recognition
            try:
                # for testing purposes, we're just using the default API key
                # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
                # instead of `r.recognize_google(audio)`
                googleRecognizedAudio = sr.Recognizer().recognize_google(audio)
                #print("Google Speech Recognition thinks you said: " + googleRecognizedAudio)
                res = len(str(googleRecognizedAudio).split())
                speechRate = res * speechRateMultiplier
                #print("You said " + str(res) + " words")
                #print("Your speech rate is: " + str(speechRate) + " words/minute")
                UI.speechOutputLabel.setText("You said: " + googleRecognizedAudio)
                UI.numWordsLabel.setText("# Words: " + str(res))
                UI.speechRateLabel.setText("Speech Rate: " + str(speechRate) + "wpm")
            except sr.UnknownValueError:
                UI.speechOutputLabel.setText("Google Speech Recognition could not understand audio")
            except sr.RequestError as e:
                UI.speechOutputLabel.setText("Could not request results from Google Speech Recognition service; {0}".format(e))

# This will quit the application when called
def Quit():
    FER_Thread.requestInterruption()
    FER_Thread.wait()
    webServerThread.terminate()
    webServerThread.wait()
    SR_Thread.requestInterruption()
    SR_Thread.terminate()
    App.quit()


App = QtWidgets.QApplication([]) # Initialize the application
UI=uic.loadUi("Final_Project.ui") # Load in specific UI from disk

UI.actionQuit.triggered.connect(Quit) # Connect Quit() method to actionQuit, and run when triggered

UI.show() # Display the GUI

FER_Thread = VideoThread() # instantiate a new VideoThread
FER_Thread.new_frame_signal.connect(Update_Image) # When a new frame arrives, run Update_Image() method
FER_Thread.start() # Begin thread

UI.ahCountLabel.setText("Ah Counter Disconnected") # Set the initial text in lblOutput to indicate no client is connected
webServerThread = FlaskServer() # instantiate a thread of FlaskServer
webServerThread.start() # Begin processing the thread

SR_Thread = SpeechRecognitionThread()
SR_Thread.start()

sys.exit(App.exec_()) # Exit 
    