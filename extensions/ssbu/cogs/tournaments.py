import discord

import hero
from hero import checks, models

from ..controller import SsbuController
from ..stages import Stage


class Tournaments(hero.Cog):
    ctl: SsbuController

    @hero.command()
    async def strike(self, ctx, stage: Stage):
        # TODO check if match channel, then
        # check if stage can be striked, then
        # add striked stage to Match's striked stages and
        # edit the striking message accordingly
        pass
