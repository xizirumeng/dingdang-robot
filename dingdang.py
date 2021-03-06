#!/usr/bin/env python2
# -*- coding: utf-8-*-

import logging
import os
import sys

import yaml

from client import dingdangpath
from client import stt
from client import tts
from client.conversation import Conversation

# Add dingdangpath.LIB_PATH to sys.path
sys.path.append(dingdangpath.LIB_PATH)
from client.mic import Mic

class Dingdang(object):
    def __init__(self):
        self._logger = logging.getLogger(__name__)

        # Create config dir if it does not exist yet
        if not os.path.exists(dingdangpath.CONFIG_PATH):
            try:
                os.makedirs(dingdangpath.CONFIG_PATH)
            except OSError:
                self._logger.error("Could not create config dir: '%s'",
                                   dingdangpath.CONFIG_PATH, exc_info=True)
                raise

        # Check if config dir is writable
        if not os.access(dingdangpath.CONFIG_PATH, os.W_OK):
            self._logger.critical("Config dir %s is not writable. Dingdang " +
                                  "won't work correctly.",
                                  dingdangpath.CONFIG_PATH)

        config_file = dingdangpath.config('profile.yml')
        # Read config
        self._logger.debug("Trying to read config file: '%s'", config_file)
        try:
            with open(config_file, "r") as f:
                self.config = yaml.safe_load(f)
        except OSError:
            self._logger.error("Can't open config file: '%s'", config_file)
            raise

        try:
            stt_engine_slug = self.config['stt_engine']
        except KeyError:
            stt_engine_slug = 'sphinx'
            logger.warning("stt_engine not specified in profile, defaulting " +
                           "to '%s'", stt_engine_slug)
        stt_engine_class = stt.get_engine_by_slug(stt_engine_slug)

        try:
            slug = self.config['stt_passive_engine']
            stt_passive_engine_class = stt.get_engine_by_slug(slug)
        except KeyError:
            stt_passive_engine_class = stt_engine_class

        try:
            tts_engine_slug = self.config['tts_engine']
        except KeyError:
            tts_engine_slug = tts.get_default_engine_slug()
            logger.warning("tts_engine not specified in profile, defaulting " +
                           "to '%s'", tts_engine_slug)
        tts_engine_class = tts.get_engine_by_slug(tts_engine_slug)

        # Initialize Mic
        self.mic = Mic(
            self.config,
            tts_engine_class.get_instance(),
            stt_passive_engine_class.get_passive_instance(),
            stt_engine_class.get_active_instance())
    def run(self):
        if 'first_name' in self.config:
            salutation = (u"%s 我能为您做什么?"
                          % self.config["first_name"])
        else:
            salutation = "主人，我能为您做什么?"

        persona = 'DINGDANG'
        if 'robot_name' in self.config:
            persona = self.config["robot_name"]
        conversation = Conversation(persona, self.mic, self.config)
        self.mic.say(salutation)
        conversation.handleForever()


if __name__ == "__main__":

    logging.basicConfig(
        filename=os.path.join(
            dingdangpath.TEMP_PATH, "dingdang.log"
        ),
        filemode="w",
        format='%(asctime)s %(filename)s[line:%(lineno)d] \
        %(levelname)s %(message)s',
        level=logging.INFO)
    logger = logging.getLogger()
    logger.getChild("client.stt").setLevel(logging.INFO)
    try:
        app = Dingdang()
    except Exception:
        logger.error("Error occured!", exc_info=True)
        sys.exit(1)
    app.run()
