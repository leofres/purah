import hero
from hero import async_using_db

import challonge

from .models import SsbuSettings


class SsbuController(hero.Controller):
    settings: SsbuSettings

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.challonge_user = None

    async def initialize_challonge_user(self):
        challonge_username = self.settings.challonge_username
        challonge_api_key = await self.settings.challonge_api_key
        if challonge_username is None or challonge_api_key is None:
            return
        self.challonge_user = await challonge.get_user(challonge_username, challonge_api_key)
        return self.challonge_user

    @async_using_db
    def get_stage(self, ctx, number):
        """Gets the stage with that number given the context

        Especially if stage striking is going on, this method
        is helpful to figure out which stage is currently being
        referred to.
        """
        # TODO check if match channel, then get stagelist
        # and get the stage from that (list index + 1),
        # else just instantiate a stage with the given number
        # and return that
        pass

    @async_using_db
    def get_starter_stages(self, ctx, channel=None):
        channel = channel or ctx.channel
        # TODO figure out if channel is tournament channel,
        # match channel or neither, then get stagelist
        # from tournament or guild

    async def strike_stage(self, channel, stage):
        match = self.get_match(channel)
        await self._strike_stage(match, stage)
        await self._update_striking_message(channel, match)

    @async_using_db
    def get_match(self, channel):
        # TODO get Match/DoublesMatch from channel
        pass

    @async_using_db
    def _strike_stage(self, match, stage):
        # TODO strike stage from game in database
        pass

    async def _update_striking_message(self, channel, match=None):
        match = match or self.get_match(channel)
        message = await channel.fetch_message(match.striking_message.id)
        # TODO generate new striking message with updated striked stages,
        # then find out if stage is the newest message with `message.channel.history`;
        # if so, edit the message; if not, delete it, send a new message and
        # set the striking_message to the new message (after `db.load`ing it and
        # async_saving it), then async_saving the match


# TODO
"""
async def save_tournament
async def get_challonge_tournament
cached_tournaments  # use self.cache for this
async def get_challonge_participant
async def get_challonge_match
async def send_signup_message
async def signup(self, tournament, member) -> Participant
async def signup_team_member(self, tournament, member)
async def send_checkin_message
async def checkin(self, tournament, member) -> Participant
async def checkin_team_member(self, tournament, member)
async def send_match_intro
# more
"""
