from queue import Queue
import threading
from urllib.parse import urljoin
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import requests
import time
import urllib3
import os
import re
import cv2
import numpy as np

import config

class LogThread(threading.Thread):
    def __init__(self, logQueue):
        super(LogThread, self).__init__()
        self.threadName = 'LogThread'
        self.logQueue = logQueue
        self.THREAD_EXIT = False

    def run(self):
        while not self.THREAD_EXIT or not self.logQueue.empty():
            try:
                img_path = self.logQueue.get(block=False)
                self.log(img_path)
            except Exception as e:
                pass
            time.sleep(0.1)
        print(self.threadName + ' finish.')

    def log(self, img_path):
        filename = os.path.basename(img_path)
        img_name = filename[:-4]    # x,y,w,h

        cur_dir = os.path.abspath(os.path.dirname(img_path))
        cur_dir = cur_dir.replace('\\', '/')
        img_id = cur_dir.split('/')[-1]
        #previous_dir = os.path.abspath(os.path.join(os.path.dirname(img_path), ".."))
        log_dir = os.path.join(cur_dir, img_id+'.txt')
        print(log_dir)

        try:
            with open(log_dir, w) as f:
                f.write(img_name+'\n')
        except Exception as e:
            print('log error')
            return



if __name__ == '__main__':
    img_path = 'C:\\Users\Administrator\PycharmProjects\Picture_tile_spider\imgs\\21159013\\1.jpg'
    print(os.path.abspath(os.path.dirname(img_path)))
    cur_dir = os.path.abspath(os.path.dirname(img_path))
    cur_dir = cur_dir.replace('\\', '/')
    img_id = cur_dir.split('/')[-1]
    print('img_id: ', img_id)