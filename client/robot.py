# -*- coding: utf-8-*-
import requests
import json
import logging
from uuid import getnode as get_mac
from app_utils import sendToUser, create_reminder
from abc import ABCMeta, abstractmethod

import sys


reload(sys)
sys.setdefaultencoding('utf-8')


class AbstractRobot(object):

    __metaclass__ = ABCMeta

    @classmethod
    def get_instance(cls, mic, profile):
        instance = cls(mic, profile)
        cls.mic = mic
        return instance

    def __init__(self, **kwargs):
        self._logger = logging.getLogger(__name__)

    @abstractmethod
    def chat(self, texts):
        pass


class TulingRobot(AbstractRobot):

    SLUG = "tuling"

    def __init__(self, mic, profile):
        """
        图灵机器人
        """
        super(self.__class__, self).__init__()
        self.mic = mic
        self.profile = profile
        self.tuling_key = self.get_key("1")
        self.city = profile["tuling"]["city"]
        self.province = profile["tuling"]["province"]
        self.street = profile["tuling"]["street"]
        self.index = 1

    def get_key(self,index):
        if 'tuling' in self.profile:
            tuling_key = self.profile['tuling']['tuling_key_'+index]
        return tuling_key
    def chat(self, texts):
        """
        使用图灵机器人聊天

        Arguments:
        texts -- user input, typically speech, to be parsed by a module
        """
        msg = ''.join(texts)
        try:
            # url = "http://www.tuling123.com/openapi/api"
            url = "http://openapi.tuling123.com/openapi/api/v2"
            userid = str(get_mac())[:32]
            # body = {'key': self.tuling_key, 'info': msg, 'userid': userid}
            body = {
                "reqType":0,
                "perception":{
                    "inputText":{
                        "text":msg
                    },
                    "selfInfo":{
                        "city":self.city,
                        "province":self.province,
                        "street":self.street
                    }
                },
                "userInfo":{
                    "apiKey":self.tuling_key,
                    "userId":userid
                }
            }
            print str(body)
            r = requests.post(url, data=body)
            print r.text
            respond = json.loads(r.text)
            result = ''
            # 成功
            if respond["intent"]['code'] == 0:
                # 判断是否为文本信息
                if respond["results"][0]["groupType"] > 0:
                    for i in respond["results"]:
                        if i["resultType"] == "text":
                            result = i['values']["text"].replace('<br>', '  ')
                            result = result.replace(u'\xa0', u' ')
                            break
                    if result == "":
                        result = '格式暂不支持'
                elif respond["results"][0]["resultType"] == "text":
                    # 单组文本消息
                    result = respond[0]['values']["text"].replace('<br>', '  ')
                    result = result.replace(u'\xa0', u' ')
                elif respond["results"][0]["resultType"] == "url":
                    # 链接
                    result = respond[0]['values']["url"]
                elif respond["results"][0]["resultType"] == "voice":
                    # 音频
                    result = respond[0]['values']["voice"]
                elif respond["results"][0]["resultType"] == "video":
                    # 视频
                    result = respond[0]['values']["video"]
                elif respond["results"][0]["resultType"] == "image":
                    # 图片
                    result = respond[0]['values']["image"]
                elif respond["results"][0]["resultType"] == "news":
                    # 图文
                    result = respond[0]['values']["news"]
            elif respond["intent"]['code'] == 4003:
                self.tuling_key = self.get_key(str(self.index))
                result = "已切换key值，再来一次吧"
            else:
                result = "图灵出错 错误代码 "+str(respond["intent"]['code'])
            max_length = 200
            if 'max_length' in self.profile:
                max_length = self.profile['max_length']
            if len(result) > max_length and \
               self.profile['read_long_content'] is not None and \
               not self.profile['read_long_content']:
                target = '邮件'
                if sendToUser(self.profile, u'回答%s' % msg, result):
                    self.mic.say(u'%s发送成功！' % target)
                else:
                    self.mic.say(u'抱歉，%s发送失败了！' % target)
            else:
                self.mic.say(result)
            if result.endswith('?') or result.endswith(u'？') or \
               u'告诉我' in result or u'请回答' in result:
                self.mic.skip_passive = True
        except Exception:
            self._logger.critical("Tuling robot failed to responsed for %r",
                                  msg, exc_info=True)
            self.mic.say("抱歉, 我的大脑短路了 " +
                         "请稍后再试试.")


class Emotibot(AbstractRobot):

    SLUG = "emotibot"

    def __init__(self, mic, profile):
        """
        Emotibot机器人
        """
        super(self.__class__, self).__init__()
        self.mic = mic
        self.profile = profile
        (self.appid, self.location, self.more) = self.get_config()

    def get_config(self):
        if 'emotibot' in self.profile:
            if 'appid' in self.profile['emotibot']:
                appid = \
                        self.profile['emotibot']['appid']
            if 'location' in self.profile:
                location = \
                        self.profile['location']
            else:
                location = None
            if 'active_mode' in self.profile['emotibot']:
                more = \
                        self.profile['emotibot']['active_mode']
            else:
                more = False
        return (appid, more, location)

    def chat(self, texts):
        """
        使用Emotibot机器人聊天

        Arguments:
        texts -- user input, typically speech, to be parsed by a module
        """
        msg = ''.join(texts)
        try:
            url = "http://idc.emotibot.com/api/ApiKey/openapi.php"
            userid = str(get_mac())[:32]
            register_data = {
                "cmd": "chat",
                "appid": self.appid,
                "userid": userid,
                "text": msg,
                "location": self.location
            }
            r = requests.post(url, params=register_data)
            jsondata = json.loads(r.text)
            result = ''
            responds = []
            if jsondata['return'] == 0:
                if self.more:
                    datas = jsondata.get('data')
                    for data in datas:
                        responds.append(data.get('value'))
                else:
                    responds.append(jsondata.get('data')[0].get('value'))
                result = '\n'.join(responds)

                if jsondata.get('data')[0]['cmd'] == 'reminder':
                    data = jsondata.get('data')[0]
                    remind_info = data.get('data').get('remind_info')
                    remind_event = remind_info[0].get('remind_event')
                    remind_time = remind_info[0].get('remind_time')

                    if not create_reminder(remind_event, remind_time):
                        result = u'创建提醒失败了'
            else:
                result = u"抱歉, 我的大脑短路了，请稍后再试试."
            max_length = 200
            if 'max_length' in self.profile:
                max_length = self.profile['max_length']
            if len(result) > max_length and \
               self.profile['read_long_content'] is not None and \
               not self.profile['read_long_content']:
                target = '邮件'
                self.mic.say(u'一言难尽啊，我给您发%s吧' % target)
                if sendToUser(self.profile, u'回答%s' % msg, result):
                    self.mic.say(u'%s发送成功！' % target)
                else:
                    self.mic.say(u'抱歉，%s发送失败了！' % target)
            else:
                self.mic.say(result)
            if result.endswith('?') or result.endswith(u'？') or \
               u'告诉我' in result or u'请回答' in result:
                self.mic.skip_passive = True

        except Exception:
            self._logger.critical("Emotibot failed to responsed for %r",
                                  msg, exc_info=True)
            self.mic.say("抱歉, 我的大脑短路了 " +
                         "请稍后再试试.")


def get_robot_by_slug(slug):
    """
    Returns:
        A robot implementation available on the current platform
    """
    if not slug or type(slug) is not str:
        raise TypeError("Invalid slug '%s'", slug)

    selected_robots = filter(lambda robot: hasattr(robot, "SLUG") and
                             robot.SLUG == slug, get_robots())
    if len(selected_robots) == 0:
        raise ValueError("No robot found for slug '%s'" % slug)
    else:
        if len(selected_robots) > 1:
            print("WARNING: Multiple robots found for slug '%s'. " +
                  "This is most certainly a bug." % slug)
        robot = selected_robots[0]
        return robot


def get_robots():
    def get_subclasses(cls):
        subclasses = set()
        for subclass in cls.__subclasses__():
            subclasses.add(subclass)
            subclasses.update(get_subclasses(subclass))
        return subclasses
    return [robot for robot in
            list(get_subclasses(AbstractRobot))
            if hasattr(robot, 'SLUG') and robot.SLUG]
