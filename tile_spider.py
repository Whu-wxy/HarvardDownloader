import aiohttp
import asyncio
import time
import threading
from bs4 import BeautifulSoup
import re
import multiprocessing as mp
import os
from urllib.parse import urljoin
from urllib.parse import urlunsplit
import random
import urllib3
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import requests
from queue import Queue
from tqdm import tqdm
import json
import cv2
import numpy as np
from colorlog import ColoredFormatter
from splice_thread import SpliceThread
from log_thread import LogThread

import config

urllib3.disable_warnings()
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36'
}

img_queue = Queue()
splice_queue = Queue()
log_queue = Queue()


def setup_logger(log_file_path: str = None):
    import logging
    from colorlog import ColoredFormatter
    logging.basicConfig(filename=log_file_path, format='%(asctime)s %(levelname)-8s %(filename)s: %(message)s',
                        # 定义输出log的格式
                        datefmt='%Y-%m-%d %H:%M:%S', )
    """Return a logger with a default ColoredFormatter."""
    formatter = ColoredFormatter("%(asctime)s %(log_color)s%(levelname)-8s %(reset)s %(filename)s: %(message)s",
                                 datefmt='%Y-%m-%d %H:%M:%S',
                                 reset=True,
                                 log_colors={
                                     'DEBUG': 'blue',
                                     'INFO': 'green',
                                     'WARNING': 'yellow',
                                     'ERROR': 'red',
                                     'CRITICAL': 'red',
                                 })

    logger = logging.getLogger('project')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.info('logger init finished')
    return logger

from datetime import datetime
now = datetime.now().strftime('%H-%M-%S')
logger = setup_logger('./train_log_' + str(now) + '.txt')

splicethread = SpliceThread(splice_queue, logger)
splicethread.start()

logthread = LogThread(log_queue, logger)
logthread.start()

def url_to_info(img_links):
    name_list = []
    info_list = []
    for link in img_links:
        link = link.split('/')
        name_list.append(link[-5])
        link = link[:-4]
        link = '/'.join(link) + '/info.json'
        info_list.append(link)
    return info_list, name_list


def parse_info(width, height):
    tile_size = []
    x = 0
    y = 0
    for i in range((height//1024)+1):
        for j in range((width//1024)+1):
            if (x+1024) <= width and (y+1024) <= height:
                tile_size.append((x, y, 1024, 1024))
            elif (x+1024) > width and (y+1024) <= height:
                tile_size.append((x, y, width-x, 1024))
            elif (x+1024) <= width and (y+1024) > height:
                tile_size.append((x, y, 1024, height-y))
            elif (x+1024) > width and (y+1024) > height:
                tile_size.append((x, y, width-x, height-y))
            else:
                raise Exception("Exception in parse_info!")

            x += 1024
        x = 0
        y += 1024

    return tile_size


def tiles_splice(img_dir, width, height, cur_name):
    previous_dir = os.path.abspath(os.path.join(img_dir, ".."))
    base_img = np.zeros((height, width, 3), np.uint8)
    for filename in os.listdir(img_dir):
        img_temp = cv2.imread(os.path.join(img_dir, filename))
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

        base_img[y:h, x:w, :] = img_temp

    cv2.imwrite(os.path.join(previous_dir, cur_name+'.jpg'), base_img)


class DownloadThread(threading.Thread):
    def __init__(self, threadName, imageQueue, spliceQueue, log_queue, logger):
        super(DownloadThread, self).__init__()
        self.threadName = threadName
        self.imageQueue = imageQueue
        self.spliceQueue = spliceQueue
        self.log_queue = log_queue
        self.logger = logger
        self.THREAD_EXIT = False

    def run(self):
        logger.info(self.threadName + ' begin.')
        while not self.THREAD_EXIT or not self.imageQueue.empty():
            try:
                base_link, info, save_dir, max_w, max_h = self.imageQueue.get(block=False)
                self.writeImage(base_link, info, save_dir, max_w, max_h)
            except Exception as e:
                pass
            time.sleep(0.1)
        self.logger.info('{} finish.'.format(self.threadName))

    def writeImage(self, base_link, info, save_dir, max_w, max_h):
        x, y, w, h = info
        strinfo = (str(x), str(y), str(w), str(h))
        img_id = base_link.split('/')[-2]
        filename = ','.join(strinfo) + '.jpg'
        img_link = base_link + ','.join(strinfo) + '/' + str(w)+','+str(h) + '/0/default.jpg'

        i = 0
        success = False
        while i < config.retry_num:   #重连
            try:
                r = requests.get(img_link, stream=False, headers=headers, verify=False, timeout=6)
                success = True
                break
            except requests.exceptions.RequestException as e:
                success = False
                #logger.info(e)
                i += 1
                self.logger.info('tile requests error: {}, retry: {}/{}'.format(','.join(strinfo), i, config.retry_num))
                continue

        if not success:        #记录下载失败的块
            self.log_queue.put(os.path.join(save_dir, filename))
            self.logger.info('error img id: {} - tile: {}, {}, {}, {}'.format(img_id, x, y, w, h))
            self.logger.info('put back tile-({}, {}, {}, {}) to queue'.format(x, y, w, h))
            self.imageQueue.put((base_link, info, save_dir, max_w, max_h))    #重连三次下载失败的放回队列
            return

        try:
            if len(r.content) / 1024 < config.img_size_threld:
                return
            with open(os.path.join(save_dir, filename), 'wb') as f:
                f.write(r.content)
                self.spliceQueue.put((os.path.join(save_dir, filename), max_w, max_h))
        except Exception as e:
           # logger.info(repr(e))
            self.logger.info('tile save error:{}'.format(os.path.join(save_dir, filename)))
            return



def main():
    logger.info('begin')
    error_img_set = set()

    thread_list = []
    loadList = []
    for i in range(config.thread_num):
        loadList.append('线程'+str(i))
    for threadName in loadList:
        Ithraad = DownloadThread(threadName, img_queue, splice_queue, log_queue, logger)
        Ithraad.start()
        thread_list.append(Ithraad)

    html = ''
    with open(config.offline_html, 'r', encoding='utf-8') as f:
        html = f.read()

    if html == '':
        logger.info('请将html内容存入iframe_content.html文件！')
        for thread in thread_list:
            thread.THREAD_EXIT = True
            thread.join()
        return

    soup = BeautifulSoup(html, 'lxml')

    # 找出所有图片url
    url_feature = '^[\s\S]*(' + config.img_url_keyword + ')[\s\S]*$'   #url中可能有换行符
    imgs = soup.find_all("img", {"src": re.compile(url_feature)}, recursive=True)
    img_links = []
    for link in imgs:
        link = link['src']
        if len(link) < 2:
            continue
        link = link.replace("\n", "")
        link = link.replace("\r", "")
        img_links.append(link.strip())

    img_links = list(set(img_links))   #去重
    info_list, name_list = url_to_info(img_links)

    count = 0
    for link in tqdm(info_list, desc='download imgs'):
        while True:
            if img_queue.qsize() > config.thread_num * 10:
                time.sleep(1)
                continue
            else:
                break

        img_name = name_list[count]
        count += 1
        try:
            r = requests.get(link, stream=False, headers=headers,
                             verify=False)
        except requests.exceptions.RequestException as e:
            logger.info(e)
            error_img_set.update(img_name)
            logger.info('error img id: {}'.format(img_name))
            continue

        logger.info('已获取{}图片信息'.format(img_name))

        info_json = json.loads(r.content.decode('utf8', 'ignore'), encoding='utf-8')
        height = info_json['height']
        width = info_json['width']
        logger.info('maxHeight:{}---maxWidth:{}'.format(height, width))

        info_list = parse_info(width, height)

        base_link = link.split('/')
        base_link = base_link[:-1]
        base_link = '/'.join(base_link) + '/'

        if not os.path.exists(os.path.join(config.save_path + img_name)):
            os.makedirs(os.path.join(config.save_path + img_name))     #一个网页创建一个文件夹


        for info in info_list:
            save_dir = os.path.join(config.save_path + img_name)
            img_queue.put((base_link, info, save_dir, width, height))


    logger.info('等待图片下载...')

    for thread in thread_list:
        thread.THREAD_EXIT = True
        thread.join()

    global splicethread
    splicethread.THREAD_EXIT = True
    splicethread.join()
    global logthread
    logthread.THREAD_EXIT = True
    logthread.join()

    logger.info('结束！')
    for i in error_img_set:
        #print('Error img: ', i)
        logger.info('Error img: {}'.format(i))



if __name__ == "__main__":
    main()
    #tiles_splice('./img/', 2546, 4530, 'save')

    #tiles_splice('./imgs/26312180/', 10973, 16195, 'save')





# https://ids.lib.harvard.edu/ids/iiif/21159013/0,15360,1024,835/1024,835/0/default.jpg

#https://ids.lib.harvard.edu/ids/iiif/21159010/full/1200,/0/default.jpg
#https://ids.lib.harvard.edu/ids/iiif/21159010/full/300,/0/default.jpg
#https://ids.lib.harvard.edu/ids/iiif/21159013/full/,150/0/default.jpg

#https://iiif.lib.harvard.edu/manifests/drs:21158960

# 17 19
# node dezoomify-node.js "https://ids.lib.harvard.edu/ids/iiif/21159013/full/150,/0/default.jpg" "default.jpg"

# https://ids.lib.harvard.edu/ids/iiif/21159013/9216,11264,1024,1024/1024,1024/0/default.jpg

# https://ids.lib.harvard.edu/ids/iiif/21159013/9216,11264,1024,1024/1024,1024/0/default.jpg
#
# https://ids.lib.harvard.edu/ids/iiif/21159013/4096,13312,1024,1024/1024,1024/0/default.jpg
#
# {"profile": ["http://iiif.io/api/image/2/level2.json", {"supports": ["canonicalLinkHeader", "profileLinkHeader", "mirroring", "rotationArbitrary", "regionSquare", "sizeAboveFull"], "qualities": ["default", "bitonal", "gray", "color"], "formats": ["jpg", "tif", "png", "gif", "webp"]}], "tiles": [{"width": 1024, "scaleFactors": [1, 2, 4, 8, 16, 32, 64, 128]}], "protocol": "http://iiif.io/api/image", "maxWidth": 2400, "sizes": [{"width": 86, "height": 127}, {"width": 172, "height": 254}, {"width": 343, "height": 507}, {"width": 686, "height": 1013}, {"width": 1372, "height": 2025}], "maxHeight": 2400, "height": 16195, "width": 10973, "@context": "http://iiif.io/api/image/2/context.json", "@id": "https://ids.lib.harvard.edu/ids/iiif/21159013"}