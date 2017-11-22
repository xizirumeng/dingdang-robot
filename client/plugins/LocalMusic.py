# -*- coding: utf-8-*-
# 本地音乐播放器
import logging
import sys
import time
import os
import subprocess
import random
import threading

reload(sys)
sys.setdefaultencoding('utf8')

# Standard module stuff
WORDS = ["YINYUE","MUSIC"]
SLUG = "music"
class MusicThread(threading.Thread):
    def __init__(self, files, mic, unlimited):
        threading.Thread.__init__(self)
        self.files = files
        self.mic = mic
        self.unlimited = unlimited
        # 单曲循环
        self.single = False
        # 播放状态
        self.status = True
        # 随机播放
        self.random = False
        self.current = -1
        self.size = len(files)
        self.index = random.randint(0, self.size - 1)

    def run(self):
        self.current = self.index
        self.play()
        while self.status:
            time.sleep(1)
            if self.current != self.index:
                self.current = self.index
                self.play()

    # 播放
    def play(self):
        try:
            self.clean()
            if not self.single:
                temp = os.path.splitext(self.files[self.index])[0].split('/')
                self.mic.say('即将播放' + temp[len(temp) - 1])
            time.sleep(1)
            subprocess.call('play -G -q ' + self.files[self.index], shell=True)
        except Exception, e:
            print e
        self.next(True)

    # 下一首
    def next(self, bol):
        if bol:
            # 单曲播放
            if self.single:
                self.current = -1
                return
        self.clean()
        if self.random:
            self.index = random.randint(0, self.size - 1)
        elif self.index < self.size - 1:
            self.index += 1
        elif self.unlimited:
            self.index = 0
        else:
            self.stop()

    # 上一首
    def previous(self):
        self.clean()
        if self.index <= 0:
            self.index = self.size - 1
        else:
            self.index -= 1

    # 停止播放
    def stop(self):
        self.status = False
        self.clean()

    # 暂停播放
    def pause(self):
        subprocess.call('pkill -STOP play', shell=True)

    # 继续播放
    def proceed(self):
        subprocess.call('pkill -CONT play', shell=True)

    # 结束当前播放
    def clean(self):
        process = subprocess.Popen('pkill -9 play', shell=True)
        process.wait()

    # 用于控制循环模式
    def setunlimited(self):
        self.unlimited = True
        self.single = False
        self.random = False
        self.proceed()

    # 用于控制单曲循环
    def setsingle(self):
        self.single = True
        self.random = False
        self.unlimited = False
        self.proceed()

    def setrandom(self):
        self.single = False
        self.unlimited = False
        self.random = True
        self.proceed()


# 遍历文件's\
def getfile(url,files,subdirectory,suffix):
    temp = os.listdir(url)
    for f in temp:
        # 排除隐藏文件
        if f[0] == '.':
            pass
        elif os.path.isfile(url + '/' + f):
            # 常见音频文件
            hz = os.path.splitext(url + '/' + f)[1].lower();
            if hz in suffix:
                files.append(url + '/' + \
                             f.replace(' ', '\ ')\
                             .replace('(', '\(')\
                             .replace(')', '\)')\
                             .replace('#', '\#')\
                             .replace('-', '\-')\
                             .replace('$', '\$')\
                             .replace('&', '\&')\
                             .replace('?', '\?')\
                             .replace('\'', '\\\'')\
                             .replace(',', '\,'))
        elif os.path.isdir(url + '/' + f) and subdirectory:  # 递归查找
            getfile(url + '/' + f,files,subdirectory,suffix)


def handle(text, mic, profile):
    logger = logging.getLogger(__name__)
    try:
        if 'robot_name' in profile:
            persona = profile['robot_name']
        if SLUG not in profile or \
                not profile[SLUG].has_key('url') or \
                not profile[SLUG].has_key('unlimited') or \
                not profile[SLUG].has_key('subdirectory'):
            mic.say('音乐插件配置有误,启动失败')
            time.sleep(1)
            return
        url = profile[SLUG]['url']
        unlimited = profile[SLUG]['unlimited']
        subdirectory = profile[SLUG]['subdirectory']
        # 判断是否存在自定义后缀
        suffix = ['.wav', '.mp3', '.wma', '.ogg', '.midi', '.aac', '.flac', '.ape'] \
            if not profile[SLUG].has_key('suffix') else profile[SLUG]['suffix']
        files= []
        getfile(url,files,subdirectory,suffix)
        length = len(files)
        if length <= 0:
            mic.say('未扫描到音乐文件')
            return
        mic.say('扫描到' + str(length) + '个音乐文件')
        music = MusicThread(files, mic, unlimited)
        music.start()
        while True:
            threshold, transcribed = mic.passiveListen(persona)
            if not transcribed or not threshold:
                continue
            music.pause()
            inputs = mic.activeListen()
            if inputs and any(ext in inputs for ext in [u'结束', u'退出', u'停止', u'关闭']):
                music.stop()
                mic.say('结束播放')
                return
            elif inputs and any(ext in inputs for ext in [u'上一首', u'上一']):
                mic.say('上一首')
                music.previous()
            elif inputs and any(ext in inputs for ext in [u'下一首', u'下一']):
                mic.say('下一首')
                music.next(False)
            elif inputs and any(ext in inputs for ext in [u'暂停']):
                mic.say('暂停播放')
                music.pause()
            elif inputs and any(ext in inputs for ext in [u'继续']):
                mic.say('继续播放')
                music.proceed()
            elif inputs and any(ext in inputs for ext in [u'列表循环', u'列表']):
                mic.say('列表循环模式')
                music.setunlimited()
            elif inputs and any(ext in inputs for ext in [u'单曲循环', u'单曲']):
                mic.say('无脑单曲模式')
                music.setsingle()
            elif inputs and any(ext in inputs for ext in [u'随机播放', u'随机模式', u'随机']):
                mic.say('随机播放')
                music.setrandom()
            else:
                mic.say('说什么?')
                music.proceed()
    except Exception, e:
        logger.error(e)
        threshold, transcribed = (None, None)
        mic.say('出了点小故障...')
def isValid(text):
    return any(word in text for word in [u"音乐", u'播放音乐', u'嗨起来'])
