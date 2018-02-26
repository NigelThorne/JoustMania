import RPi.GPIO as GPIO
import time
import os

GPIO.setmode(GPIO.BCM)

GPIO.setup(26, GPIO.IN, pull_up_down=GPIO.PUD_UP)

while True:
	input_state = GPIO.input(26)
	if input_state == False:
		print('Button Pressed -- restarting JoustMania')
		os.system("sudo /home/pi/JoustMania/kill_processes.sh")
	time.sleep(0.5)
