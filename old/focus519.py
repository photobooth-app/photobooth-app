import os
import time
import sys
import threading
import pygame,sys
from pygame.locals import *
from time import ctime, sleep
pygame.init()
screen=pygame.display.set_mode((320,240),0,32)
pygame.key.set_repeat(100)


def runFocus(func):
	temp_val = 512
	while True:
		for event in pygame.event.get():
			if event.type ==KEYDOWN:
				print(temp_val)
				if event.key == K_UP:
					print('UP')
					if temp_val < 4000:
						temp_val += 10
					else:
						temp_val = temp_val

					os.system("v4l2-ctl -c focus_absolute=%d -d /dev/v4l-subdev1" % (temp_val))
					
				elif event.key==K_DOWN:
					print('DOWN')
					if temp_val <12 :
						temp_val = temp_val
					else:
						temp_val -= 10
					os.system("v4l2-ctl -c focus_absolute=%d -d /dev/v4l-subdev1" % (temp_val))

def runCamera():
	cmd = "sudo libcamera-still -t 0"
	os.system(cmd)
if __name__ == "__main__":
	t1 = threading.Thread(target=runFocus,args=("t1",))
	t1.setDaemon(True)
	t1.start()
	runCamera()
