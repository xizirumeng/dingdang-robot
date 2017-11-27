# -*- coding: utf-8-*-
"""
A Speaker handles audio output from Dingdang to the user

Speaker methods:
    say - output 'phrase' as speech
    play - play the audio in 'filename'
    is_available - returns True if the platform supports this implementation
"""
import os
import platform
import re
import tempfile
import subprocess
import pipes
import logging
import urllib
import requests
import datetime
import base64
import hmac
import hashlib
from abc import ABCMeta, abstractmethod
from uuid import getnode as get_mac
import argparse
import yaml
import time
from dateutil import parser

import diagnose
import dingdangpath

try:
    import gtts
except ImportError:
    pass

import sys
reload(sys)
sys.setdefaultencoding('utf8')


class AbstractTTSEngine(object):
    """
    Generic parent class for all speakers
    """
    __metaclass__ = ABCMeta

    @classmethod
    def get_config(cls):
        return {}

    @classmethod
    def get_instance(cls):
        config = cls.get_config()
        instance = cls(**config)
        return instance

    @classmethod
    @abstractmethod
    def is_available(cls):
        return diagnose.check_executable('aplay')

    def __init__(self, **kwargs):
        self._logger = logging.getLogger(__name__)

    @abstractmethod
    def say(self, phrase, *args):
        pass

    def play(self, filename):
        cmd = ['aplay', str(filename)]
        self._logger.debug('Executing %s', ' '.join([pipes.quote(arg)
                                                     for arg in cmd]))
        with tempfile.TemporaryFile() as f:
            subprocess.call(cmd, stdout=f, stderr=f)
            f.seek(0)
            output = f.read()
            if output:
                self._logger.debug("Output was: '%s'", output)


class AbstractMp3TTSEngine(AbstractTTSEngine):
    """
    Generic class that implements the 'play' method for mp3 files
    """
    @classmethod
    def is_available(cls):
        return (super(AbstractMp3TTSEngine, cls).is_available() and
                diagnose.check_python_import('mad'))

    def play_mp3(self, filename, remove=False):
        cmd = ['play', str(filename)]
        self._logger.debug('Executing %s', ' '.join([pipes.quote(arg)
                                                     for arg in cmd]))
        with tempfile.TemporaryFile() as f:
            p = subprocess.Popen(cmd, stdout=f, stderr=f)
            p.wait()
            f.seek(0)
            output = f.read()
            if output:
                self._logger.debug("Output was: '%s'", output)


class SimpleMp3Player(AbstractMp3TTSEngine):
    """
    MP3 player for playing mp3 files
    """
    SLUG = "mp3-player"

    @classmethod
    def is_available(cls):
        return True

    def say(self, phrase):
        self._logger.info(phrase)


class DummyTTS(AbstractTTSEngine):
    """
    Dummy TTS engine that logs phrases with INFO level instead of synthesizing
    speech.
    """

    SLUG = "dummy-tts"

    @classmethod
    def is_available(cls):
        return True

    def say(self, phrase):
        self._logger.info(phrase)

    def play(self, filename):
        self._logger.debug("Playback of file '%s' requested")
        pass


class EspeakTTS(AbstractTTSEngine):
    """
    Uses the eSpeak speech synthesizer included in the Dingdang disk image
    Requires espeak to be available
    """

    SLUG = "espeak-tts"

    def __init__(self, voice='default+m3', pitch_adjustment=40,
                 words_per_minute=160):
        super(self.__class__, self).__init__()
        self.voice = voice
        self.pitch_adjustment = pitch_adjustment
        self.words_per_minute = words_per_minute

    @classmethod
    def get_config(cls):
        # FIXME: Replace this as soon as we have a config module
        config = {}
        # HMM dir
        # Try to get hmm_dir from config
        profile_path = dingdangpath.config('profile.yml')
        if os.path.exists(profile_path):
            with open(profile_path, 'r') as f:
                profile = yaml.safe_load(f)
                if 'espeak-tts' in profile:
                    if 'voice' in profile['espeak-tts']:
                        config['voice'] = profile['espeak-tts']['voice']
                    if 'pitch_adjustment' in profile['espeak-tts']:
                        config['pitch_adjustment'] = \
                            profile['espeak-tts']['pitch_adjustment']
                    if 'words_per_minute' in profile['espeak-tts']:
                        config['words_per_minute'] = \
                            profile['espeak-tts']['words_per_minute']
        return config

    @classmethod
    def is_available(cls):
        return (super(cls, cls).is_available() and
                diagnose.check_executable('espeak'))

    def say(self, phrase):
        self._logger.debug("Saying '%s' with '%s'", phrase, self.SLUG)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            fname = f.name
        cmd = ['espeak', '-v', self.voice,
                         '-p', self.pitch_adjustment,
                         '-s', self.words_per_minute,
                         '-w', fname,
                         phrase]
        cmd = [str(x) for x in cmd]
        self._logger.debug('Executing %s', ' '.join([pipes.quote(arg)
                                                     for arg in cmd]))
        with tempfile.TemporaryFile() as f:
            subprocess.call(cmd, stdout=f, stderr=f)
            f.seek(0)
            output = f.read()
            if output:
                self._logger.debug("Output was: '%s'", output)
        self.play(fname)
        os.remove(fname)


class FestivalTTS(AbstractTTSEngine):
    """
    Uses the festival speech synthesizer
    Requires festival (text2wave) to be available
    """

    SLUG = 'festival-tts'

    @classmethod
    def is_available(cls):
        if (super(cls, cls).is_available() and
           diagnose.check_executable('text2wave') and
           diagnose.check_executable('festival')):

            logger = logging.getLogger(__name__)
            cmd = ['festival', '--pipe']
            with tempfile.SpooledTemporaryFile() as out_f:
                with tempfile.SpooledTemporaryFile() as in_f:
                    logger.debug('Executing %s', ' '.join([pipes.quote(arg)
                                                           for arg in cmd]))
                    subprocess.call(cmd, stdin=in_f, stdout=out_f,
                                    stderr=out_f)
                    out_f.seek(0)
                    output = out_f.read().strip()
                    if output:
                        logger.debug("Output was: '%s'", output)
                    return ('No default voice found' not in output)
        return False

    def say(self, phrase):
        self._logger.debug("Saying '%s' with '%s'", phrase, self.SLUG)
        cmd = ['text2wave']
        with tempfile.NamedTemporaryFile(suffix='.wav') as out_f:
            with tempfile.SpooledTemporaryFile() as in_f:
                in_f.write(phrase)
                in_f.seek(0)
                with tempfile.SpooledTemporaryFile() as err_f:
                    self._logger.debug('Executing %s',
                                       ' '.join([pipes.quote(arg)
                                                 for arg in cmd]))
                    subprocess.call(cmd, stdin=in_f, stdout=out_f,
                                    stderr=err_f)
                    err_f.seek(0)
                    output = err_f.read()
                    if output:
                        self._logger.debug("Output was: '%s'", output)
            self.play(out_f.name)


class FliteTTS(AbstractTTSEngine):
    """
    Uses the flite speech synthesizer
    Requires flite to be available
    """

    SLUG = 'flite-tts'

    def __init__(self, voice=''):
        super(self.__class__, self).__init__()
        self.voice = voice if voice and voice in self.get_voices() else ''

    @classmethod
    def get_voices(cls):
        cmd = ['flite', '-lv']
        voices = []
        with tempfile.SpooledTemporaryFile() as out_f:
            subprocess.call(cmd, stdout=out_f)
            out_f.seek(0)
            for line in out_f:
                if line.startswith('Voices available: '):
                    voices.extend([x.strip() for x in line[18:].split()
                                   if x.strip()])
        return voices

    @classmethod
    def get_config(cls):
        # FIXME: Replace this as soon as we have a config module
        config = {}
        # HMM dir
        # Try to get hmm_dir from config
        profile_path = dingdangpath.config('profile.yml')
        if os.path.exists(profile_path):
            with open(profile_path, 'r') as f:
                profile = yaml.safe_load(f)
                if 'flite-tts' in profile:
                    if 'voice' in profile['flite-tts']:
                        config['voice'] = profile['flite-tts']['voice']
        return config

    @classmethod
    def is_available(cls):
        return (super(cls, cls).is_available() and
                diagnose.check_executable('flite') and
                len(cls.get_voices()) > 0)

    def say(self, phrase):
        self._logger.debug("Saying '%s' with '%s'", phrase, self.SLUG)
        cmd = ['flite']
        if self.voice:
            cmd.extend(['-voice', self.voice])
        cmd.extend(['-t', phrase])
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            fname = f.name
        cmd.append(fname)
        with tempfile.SpooledTemporaryFile() as out_f:
            self._logger.debug('Executing %s',
                               ' '.join([pipes.quote(arg)
                                         for arg in cmd]))
            subprocess.call(cmd, stdout=out_f, stderr=out_f)
            out_f.seek(0)
            output = out_f.read().strip()
        if output:
            self._logger.debug("Output was: '%s'", output)
        self.play(fname)
        os.remove(fname)


class MacOSXTTS(AbstractTTSEngine):
    """
    Uses the OS X built-in 'say' command
    """

    SLUG = "osx-tts"

    @classmethod
    def is_available(cls):
        return (platform.system().lower() == 'darwin' and
                diagnose.check_executable('say') and
                diagnose.check_executable('afplay'))

    def say(self, phrase):
        self._logger.debug("Saying '%s' with '%s'", phrase, self.SLUG)
        cmd = ['say', str(phrase)]
        self._logger.debug('Executing %s', ' '.join([pipes.quote(arg)
                                                     for arg in cmd]))
        with tempfile.TemporaryFile() as f:
            subprocess.call(cmd, stdout=f, stderr=f)
            f.seek(0)
            output = f.read()
            if output:
                self._logger.debug("Output was: '%s'", output)

    def play(self, filename):
        cmd = ['aplay', str(filename)]
        self._logger.debug('Executing %s', ' '.join([pipes.quote(arg)
                                                     for arg in cmd]))
        with tempfile.TemporaryFile() as f:
            subprocess.call(cmd, stdout=f, stderr=f)
            f.seek(0)
            output = f.read()
            if output:
                self._logger.debug("Output was: '%s'", output)


class PicoTTS(AbstractTTSEngine):
    """
    Uses the svox-pico-tts speech synthesizer
    Requires pico2wave to be available
    """

    SLUG = "pico-tts"

    def __init__(self, language="en-US"):
        super(self.__class__, self).__init__()
        self.language = language

    @classmethod
    def is_available(cls):
        return (super(cls, cls).is_available() and
                diagnose.check_executable('pico2wave'))

    @classmethod
    def get_config(cls):
        # FIXME: Replace this as soon as we have a config module
        config = {}
        # HMM dir
        # Try to get hmm_dir from config
        profile_path = dingdangpath.config('profile.yml')
        if os.path.exists(profile_path):
            with open(profile_path, 'r') as f:
                profile = yaml.safe_load(f)
                if 'pico-tts' in profile and 'language' in profile['pico-tts']:
                    config['language'] = profile['pico-tts']['language']

        return config

    @property
    def languages(self):
        cmd = ['pico2wave', '-l', 'NULL',
                            '-w', os.devnull,
                            'NULL']
        with tempfile.SpooledTemporaryFile() as f:
            subprocess.call(cmd, stderr=f)
            f.seek(0)
            output = f.read()
        pattern = re.compile(r'Unknown language: NULL\nValid languages:\n' +
                             r'((?:[a-z]{2}-[A-Z]{2}\n)+)')
        matchobj = pattern.match(output)
        if not matchobj:
            raise RuntimeError("pico2wave: valid languages not detected")
        langs = matchobj.group(1).split()
        return langs

    def say(self, phrase):
        self._logger.debug("Saying '%s' with '%s'", phrase, self.SLUG)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            fname = f.name
        cmd = ['pico2wave', '--wave', fname]
        if self.language not in self.languages:
                raise ValueError("Language '%s' not supported by '%s'",
                                 self.language, self.SLUG)
        cmd.extend(['-l', self.language])
        cmd.append(phrase)
        self._logger.debug('Executing %s', ' '.join([pipes.quote(arg)
                                                     for arg in cmd]))
        with tempfile.TemporaryFile() as f:
            subprocess.call(cmd, stdout=f, stderr=f)
            f.seek(0)
            output = f.read()
            if output:
                self._logger.debug("Output was: '%s'", output)
        self.play(fname)
        os.remove(fname)


class BaiduTTS(AbstractMp3TTSEngine):
    """
    使用百度语音合成技术
    要使用本模块, 首先到 yuyin.baidu.com 注册一个开发者账号,
    之后创建一个新应用, 然后在应用管理的"查看key"中获得 API Key 和 Secret Key
    填入 profile.xml 中.
    ...
        baidu_yuyin: 'AIzaSyDoHmTEToZUQrltmORWS4Ott0OHVA62tw8'
            api_key: 'LMFYhLdXSSthxCNLR7uxFszQ'
            secret_key: '14dbd10057xu7b256e537455698c0e4e'
        ...
    """

    SLUG = "baidu-tts"

    def __init__(self, api_key, secret_key, per=0):
        self._logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.secret_key = secret_key
        self.per = per
        self.token = ''
        self.token_time = ''

    @classmethod
    def get_config(cls):
        # FIXME: Replace this as soon as we have a config module
        config = {}
        # Try to get baidu_yuyin config from config
        profile_path = dingdangpath.config('profile.yml')
        if os.path.exists(profile_path):
            with open(profile_path, 'r') as f:
                profile = yaml.safe_load(f)
                if 'baidu_yuyin' in profile:
                    if 'api_key' in profile['baidu_yuyin']:
                        config['api_key'] = \
                            profile['baidu_yuyin']['api_key']
                    if 'secret_key' in profile['baidu_yuyin']:
                        config['secret_key'] = \
                            profile['baidu_yuyin']['secret_key']
                    if 'per' in profile['baidu_yuyin']:
                        config['per'] = \
                            profile['baidu_yuyin']['per']
        return config

    @classmethod
    def is_available(cls):
        return diagnose.check_network_connection()

    def get_token(self):
        URL = 'http://openapi.baidu.com/oauth/2.0/token'
        params = urllib.urlencode({'grant_type': 'client_credentials',
                                   'client_id': self.api_key,
                                   'client_secret': self.secret_key})
        r = requests.get(URL, params=params)
        try:
            r.raise_for_status()
            self.token_time = str(datetime.datetime.now())
            token = r.json()['access_token']
            return token
        except requests.exceptions.HTTPError:
            self._logger.critical('Token request failed with response: %r',
                                  r.text,
                                  exc_info=True)
            return ''

    def split_sentences(self, text):
        punctuations = ['.', '。', ';', '；', '\n']
        for i in punctuations:
            text = text.replace(i, '@@@')
        return text.split('@@@')

    def get_speech(self, phrase):
        if self.token == '' or (datetime.datetime.now() - parser.parse(self.token_time)).days >= 29:
            self.token = self.get_token()
        query = {'tex': phrase,
                 'lan': 'zh',
                 'tok': self.token,
                 'ctp': 1,
                 'cuid': str(get_mac())[:32],
                 'per': self.per
                 }
        r = requests.post('http://tsn.baidu.com/text2audio',
                          data=query,
                          headers={'content-type': 'application/json'})
        try:
            r.raise_for_status()
            if r.json()['err_msg'] is not None:
                self._logger.critical('Baidu TTS failed with response: %r',
                                      r.json()['err_msg'],
                                      exc_info=True)
                return None
        except Exception:
            pass
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(r.content)
            tmpfile = f.name
            return tmpfile

    def say(self, phrase):
        self._logger.debug(u"Saying '%s' with '%s'", phrase, self.SLUG)
        tmpfile = self.get_speech(phrase)
        if tmpfile is not None:
            self.play_mp3(tmpfile)
            os.remove(tmpfile)

class GoogleTTS(AbstractMp3TTSEngine):
    """
    Uses the Google TTS online translator
    Requires pymad and gTTS to be available
    """

    SLUG = "google-tts"

    def __init__(self, language='en'):
        super(self.__class__, self).__init__()
        self.language = language

    @classmethod
    def is_available(cls):
        return (super(cls, cls).is_available() and
                diagnose.check_python_import('gtts') and
                diagnose.check_network_connection())

    @classmethod
    def get_config(cls):
        # FIXME: Replace this as soon as we have a config module
        config = {}
        # HMM dir
        # Try to get hmm_dir from config
        profile_path = dingdangpath.config('profile.yml')
        if os.path.exists(profile_path):
            with open(profile_path, 'r') as f:
                profile = yaml.safe_load(f)
                if ('google_yuyin' in profile and
                   'language' in profile['google_yuyin']):
                    config['language'] = profile['google_yuyin']['language']

        return config

    @property
    def languages(self):
        langs = ['af', 'sq', 'ar', 'hy', 'ca', 'zh-CN', 'zh-TW', 'hr', 'cs',
                 'da', 'nl', 'en', 'eo', 'fi', 'fr', 'de', 'el', 'ht', 'hi',
                 'hu', 'is', 'id', 'it', 'ja', 'ko', 'la', 'lv', 'mk', 'no',
                 'pl', 'pt', 'ro', 'ru', 'sr', 'sk', 'es', 'sw', 'sv', 'ta',
                 'th', 'tr', 'vi', 'cy', 'zh-yue']
        return langs

    def say(self, phrase):
        self._logger.debug("Saying '%s' with '%s'", phrase, self.SLUG)
        if self.language not in self.languages:
            raise ValueError("Language '%s' not supported by '%s'",
                             self.language, self.SLUG)
        tts = gtts.gTTS(text=phrase, lang=self.language)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tmpfile = f.name
        tts.save(tmpfile)
        self.play_mp3(tmpfile)
        os.remove(tmpfile)


def get_default_engine_slug():
    return 'osx-tts' if platform.system().lower() == 'darwin' else 'espeak-tts'


def get_engine_by_slug(slug=None):
    """
    Returns:
        A speaker implementation available on the current platform

    Raises:
        ValueError if no speaker implementation is supported on this platform
    """

    if not slug or type(slug) is not str:
        raise TypeError("Invalid slug '%s'", slug)

    selected_engines = filter(lambda engine: hasattr(engine, "SLUG") and
                              engine.SLUG == slug, get_engines())
    if len(selected_engines) == 0:
        raise ValueError("No TTS engine found for slug '%s'" % slug)
    else:
        if len(selected_engines) > 1:
            print("WARNING: Multiple TTS engines found for slug '%s'. " +
                  "This is most certainly a bug." % slug)
        engine = selected_engines[0]
        if not engine.is_available():
            raise ValueError(("TTS engine '%s' is not available (due to " +
                              "missing dependencies, etc.)") % slug)
        return engine


def get_engines():
    def get_subclasses(cls):
        subclasses = set()
        for subclass in cls.__subclasses__():
            subclasses.add(subclass)
            subclasses.update(get_subclasses(subclass))
        return subclasses
    return [tts_engine for tts_engine in
            list(get_subclasses(AbstractTTSEngine))
            if hasattr(tts_engine, 'SLUG') and tts_engine.SLUG]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dingdang TTS module')
    parser.add_argument('--debug', action='store_true',
                        help='Show debug messages')
    args = parser.parse_args()

    logging.basicConfig()
    if args.debug:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

    engines = get_engines()
    available_engines = []
    for engine in get_engines():
        if engine.is_available():
            available_engines.append(engine)
    disabled_engines = list(set(engines).difference(set(available_engines)))
    print("Available TTS engines:")
    for i, engine in enumerate(available_engines, start=1):
        print("%d. %s" % (i, engine.SLUG))

    print("")
    print("Disabled TTS engines:")

    for i, engine in enumerate(disabled_engines, start=1):
        print("%d. %s" % (i, engine.SLUG))

    print("")
    for i, engine in enumerate(available_engines, start=1):
        print("%d. Testing engine '%s'..." % (i, engine.SLUG))
        engine.get_instance().say("This is a test.")
    print("Done.")
