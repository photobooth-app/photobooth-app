import cv2 #sudo apt-get install python-opencv
import numpy as py
import os
import time
from ctypes import *
cameraNum = 2
#load arducam shared object file
arducam_vcm= CDLL('./lib/libarducam_vcm.so')
try:
	import picamera
	from picamera.array import PiRGBArray
except:
	sys.exit(0)
	
def focusing(val):
        arducam_vcm.vcm_write(val)
        #print("focus value: {}".format(val))
	
def sobel(img):
	img_gray = cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
	img_sobel = cv2.Sobel(img_gray,cv2.CV_16U,1,1)
	return cv2.mean(img_sobel)[0]

def laplacian(img):
	img_gray = cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
	img_sobel = cv2.Laplacian(img_gray,cv2.CV_16U)
	return cv2.mean(img_sobel)[0]
	

def calculation(camera):
	rawCapture = PiRGBArray(camera) 
	camera.capture(rawCapture,format="bgr", use_video_port=True)
	image = rawCapture.array
	rawCapture.truncate(0)
	return laplacian(image)
	

if __name__ == "__main__":
    #vcm init
  arducam_vcm.vcm_init()
    #open camera
  camera = picamera.PiCamera()
	
  #open camera preview
  camera.start_preview()
	#set camera resolution to 640x480(Small resolution for faster speeds.)
  camera.resolution = (640, 480)
  time.sleep(0.1)
  print("Start focusing 1")
  max_index = 10
  max_value = 0.0
  last_value = 0.0
  dec_count = 0
  focal_distance = 10
	#choose cmaera A
  arducam_vcm.choose_channel(0)
  while True:
	    #Adjust focus
		focusing(focal_distance)
		#Take image and calculate image clarity
		val = calculation(camera)
		#Find the maximum image clarity
		if val > max_value:
			max_index = focal_distance
			max_value = val	
		#If the image clarity starts to decrease
		if val < last_value:
			dec_count += 1
		else:
			dec_count = 0
		#Image clarity is reduced by six consecutive frames
		if dec_count > 6:
			break
		last_value = val
		#Increase the focal distance
		focal_distance += 15
		if focal_distance > 1000:
			break
    #Adjust focus to the best
  focusing(max_index)
  time.sleep(1)
	#set camera resolution to 2592x1944
  camera.resolution = (1920,1080)
	#save image to file.
  camera.capture("test_A.jpg")
  print("max index = %d,max value = %lf" % (max_index,max_value))
  print("Start focusing 2")
  max_index = 10
  max_value = 0.0
  last_value = 0.0
  dec_count = 0
  focal_distance = 10
  camera.resolution = (640, 480)
	#choose cmaera A
  arducam_vcm.choose_channel(1)
  while True:
	    #Adjust focus
		focusing(focal_distance)
		#Take image and calculate image clarity
		val = calculation(camera)
		#Find the maximum image clarity
		if val > max_value:
			max_index = focal_distance
			max_value = val	
		#If the image clarity starts to decrease
		if val < last_value:
			dec_count += 1
		else:
			dec_count = 0
		#Image clarity is reduced by six consecutive frames
		if dec_count > 6:
			break
		last_value = val
		#Increase the focal distance
		focal_distance += 15
		if focal_distance > 1000:
			break
    #Adjust focus to the best
  focusing(max_index)
  time.sleep(1)
	#set camera resolution to 2592x1944
  camera.resolution = (1920,1080)
	#save image to file.
  camera.capture("test_B.jpg")
  print("max index = %d,max value = %lf" % (max_index,max_value))
  
 
	#while True:
	#	time.sleep(1)
  camera.stop_preview()
  camera.close()
		
	
