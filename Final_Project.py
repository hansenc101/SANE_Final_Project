import sys
import cv2
import numpy
from PyQt5 import QtWidgets,QtGui,uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
from fer import FER
from fer import Video
import time

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

# This will quit the application when called
def Quit():
    thread.requestInterruption()
    thread.wait()
    App.quit()


App = QtWidgets.QApplication([]) # Initialize the application
UI=uic.loadUi("Final_Project.ui") # Load in specific UI from disk

UI.actionQuit.triggered.connect(Quit) # Connect Quit() method to actionQuit, and run when triggered

UI.show() # Display the GUI

thread = VideoThread() # instantiate a new VideoThread
thread.new_frame_signal.connect(Update_Image) # When a new frame arrives, run Update_Image() method
thread.start() # Begin thread

sys.exit(App.exec_()) # Exit 
    