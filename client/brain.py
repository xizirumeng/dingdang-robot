# -*- coding: utf-8-*-
import logging
import pkgutil
import dingdangpath


class Brain(object):

    def __init__(self, mic, profile):
        """
        Instantiates a new Brain object, which cross-references user
        input with a list of plugins. Note that the order of brain.plugins
        matters, as the Brain will cease execution on the first plugin
        that accepts a given input.

        Arguments:
        mic -- used to interact with the user (for both input and output)
        profile -- contains information related to the user (e.g., phone
                   number)
        """

        self.mic = mic
        self.profile = profile
        (self.plugins) = self.get_plugins()
        self._logger = logging.getLogger(__name__)
        self.handling = False

    @classmethod
    def get_plugins(cls):
        """
        Dynamically loads all the plugins in the plugins folder and sorts
        them by the PRIORITY key. If no PRIORITY is defined for a given
        plugin, a priority of 0 is assumed.
        """

        logger = logging.getLogger(__name__)
        locations = [
            dingdangpath.PLUGIN_PATH,
            dingdangpath.CONTRIB_PATH,
            dingdangpath.CUSTOM_PATH
        ]
        logger.debug("Looking for plugins in: %s",
                     ', '.join(["'%s'" % location for location in locations]))
        plugins = []
        for finder, name, ispkg in pkgutil.walk_packages(locations):
            try:
                loader = finder.find_module(name)
                mod = loader.load_module(name)
            except Exception:
                logger.warning("Skipped plugin '%s' due to an error.", name,
                               exc_info=True)
            else:
                if hasattr(mod, 'WORDS'):
                    logger.debug("Found plugin '%s' with words: %r", name,
                                 mod.WORDS)
                    plugins.append(mod)
                else:
                    logger.warning("Skipped plugin '%s' because it misses " +
                                   "the WORDS constant.", name)
        plugins.sort(key=lambda mod: mod.PRIORITY if hasattr(mod, 'PRIORITY')
                     else 0, reverse=True)
        return (plugins)

    def isEnabled(self, plugin):
        """
        whether a plugin is enabled.
        Default disable
        """
        if plugin is None:
            return False
        if not hasattr(plugin, 'SLUG'):
            return True
        slug = plugin.SLUG
        if slug in self.profile and 'enable' in self.profile[slug]:
            return self.profile[slug]['enable']
        else:
            return False

    def query(self, texts):
        """
        Passes user input to the appropriate plugin, testing it against
        each candidate plugin's isValid function.

        Arguments:
        text -- user input, typically speech, to be parsed by a plugin
        """
        for plugin in self.plugins:
            for text in texts:
                if plugin.isValid(text) and self.isEnabled(plugin):
                    self._logger.debug("'%s' is a valid phrase for plugin " +
                                       "'%s'", text, plugin.__name__)
                    try:
                        self.handling = True
                        plugin.handle(text, self.mic, self.profile)
                        self.handling = False
                    except Exception:
                        self._logger.error('Failed to execute plugin',
                                           exc_info=True)
                        reply = u"抱歉，我的大脑出故障了，晚点再试试吧"
                        self.mic.say(reply)
                    else:
                        self._logger.debug("Handling of phrase '%s' by " +
                                           "plugin '%s' completed", text,
                                           plugin.__name__)
                    finally:
                        return
        self._logger.debug("No plugin was able to handle any of these " +
                           "phrases: %r", texts)
