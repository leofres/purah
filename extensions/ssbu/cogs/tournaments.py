import discord

import hero
from hero import checks, models

from ..controller import SsbuController
from ..models import SsbuSettings
from ..stages import Stage


class Tournaments(hero.Cog):
    ctl: SsbuController
    settings: SsbuSettings

    @hero.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        emoji: discord.PartialEmoji = payload.emoji
        message_id = payload.message_id
        user_id = payload.user_id
        channel_id = payload.channel_id
        guild_id = payload.guild_id

        # Ignore own reactions
        if user_id == self.core.user.id:
            return

        # If the reaction comes from a PrivateChannel, it is not relevant here
        if guild_id is None:
            return

        # TODO

    @hero.command(hidden=True)
    @checks.is_owner()
    async def set_challongecredentials(self, ctx: hero.Context, username: str, apikey: str):
        self.settings.challonge_username = username
        self.settings.challonge_api_key = apikey
        await self.settings.async_save()
        await self.ctl.initialize_challonge_user()
        await ctx.send("Challonge credentials set.")

    @hero.command()
    async def strike(self, ctx, stage: Stage):
        # TODO check if match channel, then
        # check if stage can be striked, then
        # add striked stage to Match's striked stages and
        # edit the striking message accordingly
        pass


"""
teamup
setteamname
forfeit
pick  # stage
accept  # gentleman agreement on a stage
reject  # opposite of accept
won
lost
confirm  # confirm that opponent won/lost
to_setwinner  # moderative command used to set the winner of a match
# more
"""
