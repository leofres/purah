"""discord-hero: Discord Application Framework for humans

:copyright: (c) 2019-2020 monospacedmagic et al.
:license: Apache-2.0 OR MIT
"""

from aiologger.levels import LogLevel
from discord.ext.commands import cog as _discord_cog

import hero
from hero import logging, utils


class Cog(_discord_cog.Cog):
    def __init__(self, core, extension: hero.Extension):
        self.core = core
        self.extension = extension
        self.cache = hero.get_cache(self.extension.name)
        self.db = hero.Database(self.core)

        self.log = logging.Logger.with_default_handlers(name=self.qualified_name,
                                                        level=LogLevel.DEBUG if hero.TEST else LogLevel.INFO,
                                                        loop=self.core.loop)

    @property
    def bot(self):
        return self.core

    @property
    def name(self):
        return utils.snakecaseify(self.__class__.__name__)

    @property
    def qualified_name(self):
        return f'{self.extension.name}.{self.name}'

    @property
    def config(self):
        return self.extension.config


