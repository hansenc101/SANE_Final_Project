import sys
import random
from PyQt5 import QtWidgets,uic
from PyQt5.QtCore import QThread
import requests

ah_Count = 0 # Number of ahs

class FlaskClient(QThread):
    def run(self):
        r = requests.post('http://10.0.2.5:5000/set_text', json={"ahCount":str(ah_Count), "status":"CENG 4113/5113"}) # Set the initial values
        if r.ok:
            print(r.json()) # output to console the current values


# Function to quit thread 
def Quit(): 
    thread.terminate()
    thread.wait()
    App.quit()


# Function that executes when Increment Button is clicked
def Handle_Increment_Click():
    global ah_Count
    ah_Count = ah_Count + 1 # Increment the ah_Count by 1

    UI.lblOutput.setText("Ah Count: " + str(ah_Count)) # Display the current ah_Count
    r = requests.post('http://10.0.2.5:5000/set_text', json={"ahCount":str(ah_Count), "status":"CENG 4113/5113"}) # Send text data to web server


# Function that executes when Decrement Button is clicked
def Handle_Decrement_Click():
    global ah_Count
    ah_Count = ah_Count - 1 # Decrement the ah_Count by 1
    if ah_Count == -1: # Do not let ah_Count go below 0
        ah_Count = 0   # If ah_Count goes negative, just set to 0

    UI.lblOutput.setText("Ah Count: " + str(ah_Count)) # Display the current ah_Count
    r = requests.post('http://10.0.2.5:5000/set_text', json={"ahCount":str(ah_Count), "status":"CENG 4113/5113"}) # Send text data to web server


# Function that executes when any of the color sliders change value
def Handle_Color_Adjust():
    BG_Color = "rgb(" + str(UI.redSlider.value()) + "," + str(UI.greenSlider.value()) + "," + str(UI.blueSlider.value()) + ");" # Set Background rgb color to values from sliders
    FG_Color = "rgb(255,255,255);" # Set foreground to white
    UI.lblOutput.setStyleSheet("QLabel {background-color :" + BG_Color + "color : " + FG_Color + "}") # Set the colors of the QLabel widget using values from BG_Color and FG_Color
    UI.redMagLabel.setText("Red:   " + str(UI.redSlider.value())) # output the red value for background rgb color
    UI.greenMagLabel.setText("Green: " + str(UI.greenSlider.value())) # output the green value for background rgb color
    UI.blueMagLabel.setText("Blue:  " + str(UI.blueSlider.value())) # output the blue value for background rgb color

    # Send color data to web server
    r = requests.post('http://10.0.2.5:5000/set_color', json={"red":str(UI.redSlider.value()), "green":str(UI.greenSlider.value()) , "blue":str(UI.blueSlider.value())})


App = QtWidgets.QApplication([]) # Instantiate the application
UI=uic.loadUi("demo_flask_client.ui") # Load in client user interface: demo_flask_client.ui

UI.incrementBtn.clicked.connect(Handle_Increment_Click) # Connect Handle_Increment_Click to incrementBtn
UI.decrementBtn.clicked.connect(Handle_Decrement_Click) # Connect Handle_Decrement_Click to decrementBtn
UI.actionQuit.triggered.connect(Quit) # Quit the application
UI.redSlider.valueChanged.connect(Handle_Color_Adjust) # Connect Handle_Color_Adjust to redSlider
UI.greenSlider.valueChanged.connect(Handle_Color_Adjust) # Connect Handle_Color_Adjust to greenSlider
UI.blueSlider.valueChanged.connect(Handle_Color_Adjust) # Connect Handle_Color_Adjust to blueSlider

UI.show() # Display the ui
UI.lblOutput.setText("Ah Count: 0")

thread = FlaskClient() # Instantiate the thread
thread.start() # Begin the thread

sys.exit(App.exec_()) # Exit