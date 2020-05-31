import datetime
import re

import aiohttp
import challonge

import discord
from discord.ext import commands

import hero
from hero import async_using_db, models
from hero.utils import async_to_sync

from .models import SsbuSettings
from .stages import Stage
from . import models as ssbu_models
from ..scheduler import schedulable


class SsbuController(hero.Controller):
    settings: SsbuSettings

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.challonge_user = None
        self.cached_tournaments = {}
        self.cached_participants = {}
        self.cached_matches = {}

    async def initialize_challonge_user(self):
        challonge_username = self.settings.challonge_username
        challonge_api_key = self.settings.challonge_api_key
        if challonge_username and challonge_api_key:
            self.challonge_user = await challonge.get_user(challonge_username, challonge_api_key)
        return self.challonge_user

    @async_using_db
    def save_participant_role(self, guild, role):
        guild_setup: ssbu_models.GuildSetup = ssbu_models.GuildSetup.get(guild=guild)
        guild_setup.participant_role = role
        guild_setup.save()

    @async_using_db
    def save_organizer_role(self, guild, role):
        guild_setup: ssbu_models.GuildSetup = ssbu_models.GuildSetup.get(guild=guild)
        guild_setup.organizer_role = role
        guild_setup.save()

    @async_using_db
    def save_streamer_role(self, guild, role):
        guild_setup: ssbu_models.GuildSetup = ssbu_models.GuildSetup.get(guild=guild)
        guild_setup.streamer_role = role
        guild_setup.save()

    async def save_challonge_username(self, user: models.User, challonge_username):
        player = ssbu_models.Player.async_get(user=user)
        player.challonge_username = challonge_username
        player.challonge_user_id = await self.get_challonge_user_id(challonge_username)
        await player.async_save()

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

    async def get_challonge_user_id(self, username: str):
        username = username.lower()

        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://challonge.com/users/{username}") as response:
                if response.status != 200:
                    raise commands.BadArgument("Invalid Challonge username.")
                text = await response.text()

        match = re.search(r'\?to=(\d+)', text)
        return int(match.group(1))

    @staticmethod
    async def get_final_ranking(tournament: challonge.Tournament):
        if tournament.state != challonge.TournamentState.complete.value:
            return None
        ranking = {}
        for p in tournament.participants:
            if p.final_rank is not None:  # and not p.removed:
                if p.final_rank in ranking:
                    ranking[p.final_rank].append(p)
                else:
                    ranking[p.final_rank] = [p]

        return dict(sorted(ranking.items(), key=lambda t: t[0]))

    @async_using_db
    def save_tournament(self, signup_message: models.Message, tournament: challonge.Tournament,
                        talk_channel: models.TextChannel = None, series: ssbu_models.TournamentSeries = None,
                        allow_matches_in_dms: bool = False):
        guild = async_to_sync(models.Guild.from_discord_obj(signup_message.guild))

        guild_setup = ssbu_models.GuildSetup(guild)
        guild_setup.load(prefetch_related=False)

        if series is not None:
            participant_role = series.participant_role
            organizer_role = series.organizer_role
            streamer_role = series.streamer_role
            ruleset = series.ruleset
        else:
            participant_role = guild_setup.participant_role
            organizer_role = guild_setup.organizer_role
            streamer_role = guild_setup.streamer_role
            ruleset = guild_setup.default_ruleset

        tournament = ssbu_models.Tournament(
            id=tournament.id,
            announcements_channel=signup_message.channel,
            talk_channel=talk_channel,
            guild=guild,
            signup_message=signup_message,
            series=series,
            name=tournament.name,
            key=tournament.url,
            participant_role=participant_role,
            organizer_role=organizer_role,
            streamer_role=streamer_role,
            doubles=tournament.teams,
            allow_matches_in_dms=allow_matches_in_dms,
            ruleset=ruleset,
            start_time=datetime.datetime.fromisoformat(tournament.start_at)
        )
        tournament.save()
        return tournament

    async def get_challonge_tournament(self, *args, **kwargs):
        # TODO
        pass

    async def get_challonge_participant(self, *args, **kwargs):
        # TODO
        pass

    async def get_challonge_match(self, *args, **kwargs):
        # TODO
        pass

    async def send_signup_message(self, *args, **kwargs):
        # TODO
        pass

    async def signup(self, *args, **kwargs):
        # TODO
        pass

    async def signup_team_member(self, *args, **kwargs):
        # TODO
        pass

    @schedulable
    async def check_reactions(self, ctx: hero.Context, tournament: ssbu_models.Tournament):
        # TODO
        pass

    @schedulable
    async def start_checkin(self, ctx: hero.Context, tournament: ssbu_models.Tournament):
        # TODO
        pass

    @schedulable
    async def start_tournament(self, ctx: hero.Context, tournament: ssbu_models.Tournament):
        # TODO
        pass

    async def send_checkin_message(self, *args, **kwargs):
        # TODO
        pass

    async def checkin(self, *args, **kwargs):
        # TODO
        pass

    async def checkin_team_member(self, *args, **kwargs):
        # TODO
        pass

    async def send_match_intro(self, *args, **kwargs):
        # TODO
        pass

    async def get_ranking(self, *args, **kwargs):
        # TODO
        pass

    async def start_match(self, *args, **kwargs):
        # TODO
        pass

    async def start_doubles_match(self, *args, **kwargs):
        # TODO
        pass

    async def end_match(self, *args, **kwargs):
        # TODO
        pass

    async def end_tournament(self, *args, **kwargs):
        # TODO
        pass

    @async_using_db
    def get_setup(self, ctx: hero.Context, guild):
        try:
            guild_setup = ssbu_models.GuildSetup.get(guild=guild)
        except ssbu_models.GuildSetup.DoesNotExist:
            raise ssbu_models.GuildSetup.DoesNotExist(f"**{guild.name}** has not been set up yet; "
                                                      f"use `{ctx.prefix}to setup`.")
        return guild_setup

    async def create_tournament(self, name, key, tournament_type, signup_cap, private, start_at, description, admin):
        tournament = await self.challonge_user.create_tournament(name=name, url=key,
                                                                 tournament_type=tournament_type,
                                                                 game_name="Super Smash Bros. Ultimate",
                                                                 open_signup=False, hide_forum=True, show_rounds=True,
                                                                 signup_cap=signup_cap,
                                                                 private=private,
                                                                 start_at=start_at,
                                                                 description=description,
                                                                 check_in_duration=35)
        # hacky but it works
        if admin is not None:
            await tournament.connection('PUT', f'tournaments/{tournament.id}',
                                        **{
                                            'shared_administration': 1,
                                            'tournament[admin_ids_csv]': admin.challonge_user_id
                                        })


# TODO
"""
cached_tournaments  # use self.cache for this
cached_participants
cached_matches
async def save_tournament
async def get_challonge_tournament
async def get_challonge_participant
async def get_challonge_match
async def send_signup_message
async def signup(self, tournament, member) -> Participant
async def signup_team_member(self, tournament, member)
async def send_checkin_message
async def checkin(self, tournament, member) -> Participant
async def checkin_team_member(self, tournament, member)
async def send_match_intro
async def get_ranking
async def start_match
async def start_doubles_match
async def end_match
async def end_tournament
# more
"""
