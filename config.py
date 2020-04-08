# 开始爬取的网址
base_url = "https://www.oschina.net/"
#http://www.zhejiangmuseum.com/zjbwg/collection/zpmcollection.html
#https://www.zjmuex.com/Collection/List/TSGC?etype=&areac=2ebfaf78-7f8c-47e9-8862-37b57baf05ea&city=80811da7-9a34-4705-8681-f88dec3a3c8b&fclass=&unit=2&title=
#https://www.deepin.org/
#https://morvanzhou.github.io/
#http://www.scmuseum.cn/list-1657.html


# 最大爬取页数：数字或None(一直爬取)
max_page_count = 10

# 先用审查元素找到关键词，用url中的关键词筛选url,用|隔开，为空则选取全部url
url_keyword = ''   #Collection|UploadFiles

img_url_keyword = ''

# 图片存储路径，如果不存在，将会创建文件夹
# 将会在这个文件夹下为每个网页创建一个子文件夹存图片
save_path = './imgs/'

#下载图片线程数
thread_num = 4


# 下载图片的最小KB值
img_size_threld = 0      # KB