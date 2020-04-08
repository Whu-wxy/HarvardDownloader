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

class SpliceThread(threading.Thread):
    def __init__(self, spliceQueue):
        super(SpliceThread, self).__init__()
        self.threadName = 'SpliceThread'
        self.spliceQueue = spliceQueue
        self.THREAD_EXIT = False

    def run(self):
        while not self.THREAD_EXIT or not self.spliceQueue.empty():
            try:
                img_path, max_w, max_h = self.spliceQueue.get(block=False)
                self.spliceImage(img_path, max_h, max_w)
            except Exception as e:
                pass
                #print('splice error')
            time.sleep(0.1)
        print(self.threadName + ' finish.')

    def spliceImage(self, img_path, height, width):
        filename = os.path.basename(img_path)
        img_name = filename[:-4]
        info_list = img_name.split(',')
        x = int(info_list[0])
        y = int(info_list[1])
        if x != 0:
            x = x - 1
        if y != 0:
            y = y - 1
        w = int(info_list[2]) + x
        h = int(info_list[3]) + y

        cur_dir = os.path.abspath(os.path.dirname(img_path))
        cur_dir = cur_dir.replace('\\', '/')
        img_id = cur_dir.split('/')[-1]
        previous_dir = os.path.abspath(os.path.join(os.path.dirname(img_path), ".."))
        base_img_dir = os.path.join(previous_dir, img_id+'.jpg')
        base_img = np.zeros((height, width, 3), np.uint8)
        if os.path.exists(base_img_dir):
            base_img = cv2.imread(base_img_dir)

        img_temp = cv2.imread(img_path)
        try:
            base_img[y:h, x:w, :] = img_temp
            cv2.imwrite(base_img_dir, base_img)
        except Exception as e:
            print('error in sliceImage')
            #print(e)


if __name__ == '__main__':
    img_path = 'C:\\Users\Administrator\PycharmProjects\Picture_tile_spider\imgs\\21159013'
    print(os.path.dirname(img_path))