import datetime
import re

import aiohttp
import challonge

import discord
from discord.utils import find, get
from discord.ext import commands

import hero
from hero import async_using_db, models, ObjectDoesNotExist
from hero.utils import async_to_sync

from .models import GuildSetup, Match, MatchCategory, MatchmakingSetup, MatchOffer, MatchSearch, Player, SsbuSettings
from .stages import Stage
from . import models as ssbu_models, strings
from ..scheduler import schedulable
from .formats import Formats


class SsbuController(hero.Controller):
    settings: SsbuSettings

    RANKED_REMATCHES_PER_DAY = 1
    LOOKING_REACTION = '\U0001f50d'
    AVAILABLE_REACTION = '\U0001f514'
    DND_REACTION = '\U0001f515'
    OFFER_REACTION = '\U0001f3ae'
    ACCEPT_REACTION = '\U00002705'
    DECLINE_REACTION = '\U0000274e'
    PRIVATE_REACTION = '\U0001F512'
    PUBLIC_REACTION = '\U0001F513'
    LEAVE_REACTION = DECLINE_REACTION
    SPECTATE_REACTION = '\U0001F441'

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

    async def save_challonge_username(self, user: models.User, challonge_username):
        player = ssbu_models.Player.async_get(user=user)
        player.challonge_user_id = await self.get_challonge_user_id(challonge_username)
        player.challonge_username = challonge_username
        await player.async_save()

    @staticmethod
    async def get_challonge_user_id(username: str):
        username = username.lower()

        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://challonge.com/users/{username}") as response:
                if response.status != 200:
                    raise commands.BadArgument("Invalid Challonge username.")
                text = await response.text()

        # scrape page to find user ID
        match = re.search(r'\?to=(\d+)', text)
        return int(match.group(1))

    @staticmethod
    async def is_key_available(key: str):
        key = key.lower()

        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://challonge.com/{key}") as response:
                return response.status == 404

    @async_using_db
    def create_tournament_series(self, key: str, guild: models.Guild, doubles: bool, name: str,
                                 participant_role: models.Role, organizer_role: models.Role,
                                 announcements_channel: models.TextChannel, admin: ssbu_models.Player = None,
                                 streamer_role: models.Role = None, talk_channel: models.TextChannel = None,
                                 signup_emoji: models.Emoji = None, checkin_emoji: models.Emoji = None,
                                 participants_limit: int = None, _format: Formats = Formats.double_elimination,
                                 allow_matches_in_dms: bool = False, ruleset: ssbu_models.Ruleset = None):
        tournament_series = ssbu_models.TournamentSeries(
            key=key, guild=guild, doubles=doubles, name=name, participant_role=participant_role,
            organizer_role=organizer_role, announcements_channel=announcements_channel,
            streamer_role=streamer_role, talk_channel=talk_channel, format=_format,
            allow_matches_in_dms=allow_matches_in_dms, ruleset=ruleset
        )
        if signup_emoji is not None:
            tournament_series.signup_emoji = signup_emoji
        if checkin_emoji is not None:
            tournament_series.checkin_emoji = checkin_emoji
        if participants_limit is not None:
            tournament_series.default_participants_limit = participants_limit
        tournament_series.save()
        if admin is not None:
            tournament_series.admins.add(admin)
        return tournament_series

    @async_using_db
    def is_any_organizer(self, guild: models.Guild, member: models.Member):
        try:
            guild_setup = ssbu_models.GuildSetup.get(pk=guild)
        except ObjectDoesNotExist:
            return False

        main_organizer_role = guild_setup.main_series.organizer_role
        if get(member.roles, id=main_organizer_role.id):
            return True
        qs = ssbu_models.TournamentSeries.objects.filter(guild=guild)
        if find(lambda role: role.id in [series.organizer_role.id for series in qs], member.roles):
            return True
        qs = ssbu_models.Tournament.objects.filter(guild=guild, ended=False)
        if find(lambda role: role.id in [tournament.organizer_role.id for tournament in qs], member.roles):
            return True
        return False

    @async_using_db
    def is_main_organizer(self, guild: models.Guild, member: models.Member):
        try:
            guild_setup = ssbu_models.GuildSetup.get(pk=guild)
        except ObjectDoesNotExist:
            return False

        main_organizer_role = guild_setup.main_series.organizer_role
        if get(member.roles, id=main_organizer_role.id):
            return True
        return False

    @async_using_db
    def is_organizer(self, channel: models.TextChannel, member: models.Member):
        try:
            guild_setup = ssbu_models.GuildSetup.get(pk=channel.guild)
        except ObjectDoesNotExist:
            return False

        try:
            tournament = ssbu_models.Tournament.objects.get(announcements_channel=channel, ended=False)
        except ssbu_models.Tournament.MultipleObjectsReturned:
            pass
        else:
            if get(member.roles, id=tournament.organizer_role.id):
                return True

        try:
            tournament = ssbu_models.Tournament.objects.get(talk_channel=channel, ended=False)
        except ssbu_models.Tournament.MultipleObjectsReturned:
            pass
        else:
            if get(member.roles, id=tournament.organizer_role.id):
                return True

        return False

    @async_using_db
    def is_organizer_of_series(self, series: ssbu_models.TournamentSeries, member):
        if isinstance(series, str):
            tournament = ssbu_models.TournamentSeries.get(key_prefix=series)
        if isinstance(member, models.Member):
            member = member.discord
        if get(member.roles, id=series.organizer_role.id):
            return True
        return False

    @async_using_db
    def is_organizer_of_tournament(self, tournament: ssbu_models.Tournament, member):
        if isinstance(tournament, str):
            tournament = ssbu_models.Tournament.get(key=tournament)
        if isinstance(member, models.Member):
            member = member.discord
        if get(member.roles, id=tournament.organizer_role.id):
            return True
        return False

    @schedulable
    async def create_tournament(self, name: str, key: str, tournament_channel: models.TextChannel,
                                tournament_type: str, start_at: datetime.datetime, intro_message: str,
                                ruleset: ssbu_models.Ruleset,
                                series: ssbu_models.TournamentSeries = None,
                                talk_channel: models.TextChannel = None,
                                signup_emoji: models.Emoji = None,
                                signup_cap: int = 512, private: bool = False, admins_csv: str = '',
                                invite_link: str = None):
        # can raise challonge.APIException
        starter_stages = ruleset.starter_stages
        counterpick_stages = ruleset.counterpick_stages
        counterpick_bans = ruleset.counterpick_bans
        dsr = ruleset.dsr

        description = self.create_challonge_description(intro_message, invite_link, tournament_channel,
                                                        starter_stages, counterpick_stages, counterpick_bans, dsr)

        challonge_tournament = await self.create_challonge_tournament(name, key, tournament_type, signup_cap,
                                                                      private, start_at, description, admins_csv)
        self.cache_tournament(challonge_tournament)

        if signup_emoji is None:
            signup_emoji = models.Emoji(name='\u2705', is_custom=False)  # white_check_mark
            await signup_emoji.async_save()
        signup_message = await self.send_signup_message(tournament_channel, key, starter_stages, counterpick_stages,
                                                        counterpick_bans, dsr, signup_emoji, intro_message, start_at)

        tournament = await self.save_tournament(signup_message=signup_message, tournament=challonge_tournament,
                                                talk_channel=talk_channel, series=series, allow_matches_in_dms=False)
        return tournament

    @staticmethod
    def create_challonge_description(intro_message, invite_link, channel, starter_stages,
                                     counterpick_stages, counterpick_bans, dsr):
        _starter_stages = '\n'.join([str(stage) for stage in starter_stages])
        _counterpick_stages = '\n'.join([str(stage) for stage in counterpick_stages])
        description = strings.description.format(intro_message=intro_message, invite_link=invite_link,
                                                 channel=channel, starter_stages=_starter_stages,
                                                 counterpick_stages=_counterpick_stages,
                                                 counterpick_bans=counterpick_bans, dsr=dsr)
        return description

    async def create_challonge_tournament(self, name, key, tournament_type, signup_cap, private, start_at, description,
                                          admins_csv):
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
        if admins_csv:
            await tournament.connection(
                'PUT', f'tournaments/{tournament.id}',
                **{
                    'shared_administration': 1,
                    'tournament[admin_ids_csv]': admins_csv
                })
        self.cache_tournament(tournament)
        return tournament

    async def send_signup_message(self, channel, key, starter_stages, counterpick_stages,
                                  counterpick_bans, dsr, signup_emoji, intro_message, start_at):
        start_time = start_at.strftime('on %A, %B %d, %Y at %I.%M %p %Z')
        _starter_stages = '\n'.join([str(stage) for stage in starter_stages])
        _counterpick_stages = '\n'.join([str(stage) for stage in counterpick_stages])
        text = strings.signup_message.format(
            intro_message=intro_message,
            start_time=start_time,
            full_challonge_url=f"https://challonge.com/{key}",
            signup_emoji=signup_emoji,
            starter_stages_list=_starter_stages,
            counterpick_stages_list=_counterpick_stages,
            counterpick_bans=counterpick_bans,
            dsr_on_off='ON' if dsr else 'OFF'
        )
        timestamp_embed = discord.Embed(timestamp=start_at, color=discord.Colour.blurple())
        timestamp_embed.set_footer(text="Start time in your local time")
        message = await channel.send(text, embed=timestamp_embed)
        await message.add_reaction(signup_emoji)
        return message

    @async_using_db
    def save_tournament(self, signup_message: models.Message, tournament: challonge.Tournament,
                        talk_channel: models.TextChannel = None, series: ssbu_models.TournamentSeries = None,
                        allow_matches_in_dms: bool = False):
        guild = signup_message.guild

        guild_setup = ssbu_models.GuildSetup.get(pk=guild)

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

    def cache_tournament(self, challonge_tournament):
        self.cached_tournaments[challonge_tournament.id] = challonge_tournament

    def cache_participant(self, challonge_participant):
        self.cached_participants[challonge_participant.id] = challonge_participant

    def cache_match(self, challonge_match):
        self.cached_matches[challonge_match.id] = challonge_match

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

    @async_using_db
    def get_match(self, channel):
        # TODO get Match/DoublesMatch from channel
        pass

    @async_using_db
    def get_starter_stages(self, ctx, channel=None):
        channel = channel or ctx.channel
        # TODO figure out if channel is tournament channel,
        # match channel or neither, then get stagelist
        # from tournament or guild

    @async_using_db
    def get_counterpick_stages(self, ctx, channel=None):
        channel = channel or ctx.channel
        # TODO

    @async_using_db
    def get_stagelist(self, ctx, channel=None):
        channel = channel or ctx.channel
        # TODO

    async def strike_stage(self, channel, stage):
        match = self.get_match(channel)
        await self._strike_stage(match, stage)
        await self._update_striking_message(channel, match)

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
        # set the striking_message to the new message (after `db.wrap`ing it and
        # async_saving it), then async_saving the match

    async def send_tournament_match_intro(self, *args, **kwargs):
        # TODO
        pass

    async def start_tournament_match(self, *args, **kwargs):
        # TODO
        pass

    async def start_tournament_doubles_match(self, *args, **kwargs):
        # TODO
        pass

    async def end_tournament_match(self, *args, **kwargs):
        # TODO
        pass

    async def end_tournament(self, *args, **kwargs):
        # TODO
        pass

    async def get_ranking(self, *args, **kwargs):
        # TODO
        pass

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

    async def get_active_matchmaking_match(self, user):
        # get all unfinished matches that are at least 6 hours old
        six_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=6)
        matches_qs = (
            Match.objects.filter(tournament=None, player_1__user__id=user.id, winner=None, when__lte=six_hours_ago)
            | Match.objects.filter(tournament=None, player_2__user__id=user.id, winner=None, when__lte=six_hours_ago)
        ).order_by('when')
        matches: list = await matches_qs.async_to_list()
        # print(matches)
        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches[0]
        active_match = matches.pop(-1)
        for match in matches:
            # sanitize match records
            channel = await match.channel
            await match.async_delete()  # match that never ended and where another one started after is useless
            try:
                await channel.fetch()
            except (discord.Forbidden, discord.NotFound):
                await match.async_delete()
                await channel.async_delete()
            else:
                try:
                    await channel.discord.delete()
                except discord.Forbidden:
                    pass
            await match.async_delete()
            await channel.async_delete()
        active_match_channel = await active_match.channel
        try:
            await active_match_channel.fetch()
        except (discord.Forbidden, discord.NotFound):
            await active_match.async_delete()
            await active_match_channel.async_delete()
            return None
        return active_match

    async def look_for_opponents(self, matchmaking_setup: MatchmakingSetup, member: models.Member):
        channel = await matchmaking_setup.channel
        guild = await channel.guild
        # TODO fix this
        # guild_setup = await guild.guildsetup
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role
        looking_role = await matchmaking_setup.looking_role
        available_role = await matchmaking_setup.available_role

        _member: discord.Member = member.discord
        if ingame_role in _member.roles:
            await channel.discord.send(f"{_member.mention}, you seem to be in-game right now so you "
                                       f"can't look for opponents until you finish your current match.",
                                       delete_after=30)

        user = await member.user
        active_match = await self.get_active_matchmaking_match(user)
        if active_match:
            active_match_channel = await active_match.channel

            if active_match.ranked:
                msg_txt = (f"{member.mention}, you still have an active ranked match in "
                           f"{active_match_channel.mention}."
                           f"Would you like to forfeit that match now?")
            else:
                msg_txt = (f"{member.mention}, you still have an active match in "
                           f"{active_match_channel.mention}."
                           f"Would you like to leave that match now?")
            msg = await channel.send(msg_txt)
            do_close_active_match = await self.core.wait_for_confirmation(msg)
            await msg.delete()
            if do_close_active_match:
                try:
                    await self.end_match(active_match, member)
                except discord.NotFound:  # user probably left it themselves
                    pass
            else:
                return

        await member.add_roles(looking_role)
        await member.remove_roles(available_role)
        message = await self._send_match_search(channel, member, looking_role, available_role)
        message = await self.db.wrap_message(message)
        # save match search
        match_search = MatchSearch(message=message, looking=member, setup=matchmaking_setup)
        await match_search.async_save()

    async def _send_match_search(self, channel, member, looking_role, available_role):
        if not channel.is_fetched:
            await channel.fetch()
        if not member.is_fetched:
            await member.fetch()
        if not looking_role.is_fetched:
            await looking_role.fetch()
        if not available_role.is_fetched:
            await available_role.fetch()

        message = await channel.send(f"{looking_role.mention}, {available_role.mention}: "
                                     f"{member.mention} is looking for a match!",
                                     allowed_mentions=discord.AllowedMentions(users=False))
        await message.add_reaction(self.OFFER_REACTION)
        return message

    async def add_message_to_search(self, match_search: MatchSearch, message: discord.Message):
        search_message = await match_search.message
        _search_message = await search_message.fetch()
        text = _search_message.content + "\n" + message.content
        await _search_message.edit(content=text)
        await message.delete()

    async def delete_match_search(self, match_search):
        message = await match_search.message
        _message = await message.fetch()
        await match_search.async_delete()
        try:
            await _message.delete()
        except discord.Forbidden:
            await _message.channel.send("I cannot delete match searches, please grant me the "
                                        "**Manage Messages** permission.", delete_after=60)
        except discord.NotFound:
            pass

    async def ensure_no_active_matches(self, channel, member):
        user = await member.user
        active_match = await self.get_active_matchmaking_match(user)
        if active_match:
            active_match_channel = await active_match.channel

            if active_match.ranked:
                msg_txt = (f"{member.mention}, you still have an active ranked match in "
                           f"{active_match_channel.mention}."
                           f"Would you like to forfeit that match now?")
            else:
                msg_txt = (f"{member.mention}, you still have an active match in "
                           f"{active_match_channel.mention}."
                           f"Would you like to leave that match now?")
            msg = await channel.send(msg_txt)
            do_close_active_match = await self.core.wait_for_confirmation(msg)
            await msg.delete()
            if do_close_active_match:
                try:
                    await self.end_match(active_match, member)
                except discord.NotFound:  # user probably left it themselves
                    pass
                return True
            else:
                return False
        return True

    async def set_as_available(self, matchmaking_setup, member):
        # check if there's an active match
        channel = await matchmaking_setup.channel
        guild = await channel.guild
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role
        looking_role = await matchmaking_setup.looking_role
        available_role = await matchmaking_setup.available_role

        _member: discord.Member = member.discord
        if ingame_role in _member.roles:
            await channel.discord.send(f"{_member.mention}, you seem to be in-game right now so you "
                                       f"can't change your status until you finish your current match.",
                                       delete_after=30)

        if not await self.ensure_no_active_matches(channel, member):
            return

        # delete match search in channel if there is one
        try:
            match_search = await MatchSearch.objects.async_get(setup=matchmaking_setup, looking=member)
        except MatchSearch.DoesNotExist:
            pass
        else:
            await self.delete_match_search(match_search)
            await _member.remove_roles(looking_role)
        # give potentially available role
        await _member.add_roles(available_role)

    async def set_as_dnd(self, matchmaking_setup, member):
        # check if there's an active match
        channel = await matchmaking_setup.channel
        guild = await channel.guild
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role
        looking_role = await matchmaking_setup.looking_role
        available_role = await matchmaking_setup.available_role

        _member: discord.Member = member.discord
        if ingame_role in _member.roles:
            await channel.discord.send(f"{_member.mention}, you seem to be in-game right now so you "
                                       f"can't change your status until you finish your current match.",
                                       delete_after=30)

        if not await self.ensure_no_active_matches(channel, member):
            return

        # delete match search in channel if there is one
        try:
            match_search = await MatchSearch.objects.async_get(setup=matchmaking_setup, looking=member)
        except MatchSearch.DoesNotExist:
            pass
        else:
            await self.delete_match_search(match_search)
            await _member.remove_roles(looking_role)
        # remove potentially available role
        await _member.remove_roles(available_role)

    async def set_as_ingame(self, *members):
        for member in members:
            await self._clear_searches(member)
            await self._clear_offers(member)
            # give ingame role


    async def _clear_searches(self, member):
        # clear searches
        searches = await MatchSearch.objects.filter(looking=member).async_to_list()
        for search in searches:
            setup = await search.setup
            looking_role = await setup.looking_role
            await member.remove_roles(looking_role)
            await self.delete_match_search(search)
        # clear offered to
        offered_to = await MatchOffer.objects.filter(offered_to=member).async_to_list()
        for offer in offered_to:
            await self.decline_offer(offer)

    async def _clear_offers(self, member):
        offers = await MatchOffer.objects.filter(offering=member).async_to_list()
        for offer in offers:
            await self.decline_offer(offer)

    async def offer_match(self, channel, offered_to, offering, allow_decline=True):
        # check if there's an active match
        guild = await channel.guild
        # guild_setup = await guild.guild_setup
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role

        _member: discord.Member = offering.discord
        if ingame_role in _member.roles:
            await channel.discord.send(f"{_member.mention}, you seem to be in-game right now so you "
                                       f"can't offer matches until you finish your current match.",
                                       delete_after=30)

        if not await self.ensure_no_active_matches(channel, offering):
            return

        message = await channel.send(f"{offered_to.mention}, {offering.mention} is offering a match!")
        await message.add_reaction(self.ACCEPT_REACTION)  # white_check_mark
        if allow_decline:
            await message.add_reaction(self.DECLINE_REACTION)  # negative_squared_cross_mark
        message = await self.db.wrap_message(message)
        match_offer = MatchOffer(message=message, offering=offering, offered_to=offered_to)
        await match_offer.async_save()

    async def decline_offer(self, match_offer):
        message = await match_offer.message
        _message = await message.fetch()
        await match_offer.async_delete()
        try:
            await _message.delete()
        except discord.Forbidden:
            await _message.channel.send("I cannot delete match offers, please grant me the "
                                        "**Manage Messages** permission.", delete_after=60)
        except discord.NotFound:
            pass

    async def create_match(self, offered_to, offering, origin_channel, ranked=False, create_vc=True):
        if not offered_to.is_fetched:
            await offered_to.fetch()
        if not offering.is_fetched:
            await offering.fetch()

        channel, voice_channel = await self._create_match_channel(offered_to, offering, origin_channel,
                                                                  ranked=ranked, create_vc=create_vc)
        await self.set_as_ingame(offered_to, offering)
        management_message = await self._send_match_management_message(channel, offered_to, offering)
        channel = await self.db.wrap_text_channel(channel)
        voice_channel = await self.db.wrap_voice_channel(voice_channel) if not None else None
        guild = await channel.guild
        try:
            matchmaking_setup = await MatchmakingSetup.objects.async_get(channel=channel)
            available_role = await matchmaking_setup.available_role
            await offered_to.remove_roles(available_role)
            await offering.remove_roles(available_role)
        except MatchmakingSetup.DoesNotExist:
            matchmaking_setup = None
        management_message = await self.db.wrap_message(management_message)
        offered_to_user = await offered_to.user
        await offered_to_user.async_load()
        offered_to_player, _ = await Player.objects.async_get_or_create(user=offered_to_user)
        offering_user = await offering.user
        await offering_user.async_load()
        offering_player, _ = await Player.objects.async_get_or_create(user=offering_user)
        match = Match(
            channel=channel, guild=guild, voice_channel=voice_channel, setup=matchmaking_setup,
            management_message=management_message, ranked=ranked, in_dms=False,
            player_1=offered_to_player, player_2=offering_player
        )
        await match.async_save()
        return match

    async def _create_match_channel(self, offered_to, offering, origin_channel, ranked: bool, create_vc=True):
        guild = await offered_to.guild
        match_categories = await MatchCategory.objects.filter(category__guild=guild).async_to_list()
        selected_category = None
        if len(match_categories) == 0:
            selected_category = await self.create_matches_category(guild, 1)
        else:
            for i, match_category in enumerate(match_categories):
                category = await match_category.category
                try:
                    discord_category: discord.CategoryChannel = await category.fetch()
                except discord.NotFound:
                    number = match_category.number
                    await category.async_delete()
                    selected_category = await self.create_matches_category(guild, number)
                    break
                if len(discord_category.channels) >= 49:  # next category
                    if len(match_categories) < i + 1:  # need one more category
                        selected_category = await self.create_matches_category(guild, i + 1)
                        break
                    continue
                selected_category = category
                break

        name_format_args = []
        matchmaking_name = origin_channel.name.replace("matchmaking", "").strip('_-')
        if matchmaking_name:  # if it's not an empty string now
            name_format_args.append(matchmaking_name)
        name_format_args.append(offered_to.name)
        name_format_args.append('vs')
        name_format_args.append(offering.name)

        text_name = '_'.join(name_format_args)
        text_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True,
                                                  manage_channels=True),
            offered_to: discord.PermissionOverwrite(read_messages=True, manage_messages=True),
            offering: discord.PermissionOverwrite(read_messages=True, manage_messages=True)
        }
        text_channel = await guild.create_text_channel(text_name, overwrites=text_overwrites,
                                                       category=selected_category,
                                                       reason=f"Creating match channel for "
                                                              f"{offered_to.display_name} and "
                                                              f"{offering.display_name}")

        if not create_vc:
            voice_channel = None
        else:
            voice_name = ' '.join(name_format_args)
            voice_overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False),
                guild.me: discord.PermissionOverwrite(connect=True),
                offered_to: discord.PermissionOverwrite(connect=True),
                offering: discord.PermissionOverwrite(connect=True)
            }
            voice_channel = await guild.create_voice_channel(voice_name, overwrites=voice_overwrites,
                                                             category=selected_category,
                                                             reason=f"Creating voice channel for match with "
                                                                    f"{offered_to.display_name} and "
                                                                    f"{offering.display_name}")
        return text_channel, voice_channel

    async def _send_match_management_message(self, channel, player_1, player_2):
        message = await channel.send(f"Match of {player_1.mention} and {player_2.mention}\n"
                                     f"\n"
                                     f"**Match Control Panel**\n"
                                     f"\n"
                                     f"{self.PRIVATE_REACTION} (Default) Make the match private\n"
                                     f"{self.PUBLIC_REACTION} [SOON] Allow spectators to join the match\n"
                                     f"{self.LEAVE_REACTION} Leave the match\n")

        await message.pin()
        await message.add_reaction(self.PRIVATE_REACTION)  # lock
        await message.add_reaction(self.PUBLIC_REACTION)  # no_lock
        await message.add_reaction(self.LEAVE_REACTION)  # negative_squared_cross_mark

        return message

    async def make_match_private(self, match):
        pass

    async def make_match_spectatable(self, match):
        pass

    async def _delete_spectating_message(self, match):
        spectating_message = await match.spectating_message
        if spectating_message is not None:
            try:
                msg = await spectating_message.fetch()
            except (discord.Forbidden, discord.NotFound):
                pass
            else:
                await msg.delete()

    async def end_match(self, match, ended_by=None):
        # if ranked match, ended_by forfeited

        channel = await match.channel
        await channel.fetch()
        voice_channel = await match.voice_channel
        await voice_channel.fetch()
        guild = await match.guild
        await guild.fetch()
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role
        player_1 = await match.player_1
        player_1_user = await player_1.user
        player_1_member = await guild.fetch_member(player_1_user.id)
        player_2 = await match.player_2
        player_2_user = await player_2.user
        player_2_member = await guild.fetch_member(player_2_user.id)

        await self._delete_spectating_message(match)

        try:
            await channel.discord.delete()
        except (discord.Forbidden, discord.NotFound):
            pass
        await channel.async_delete()
        if voice_channel is not None:
            try:
                await voice_channel.discord.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
        await voice_channel.async_delete()

        await player_1_member.remove_roles(ingame_role)
        await player_2_member.remove_roles(ingame_role)

        if not match.ranked:
            me = await self.db.wrap_user(self.core.user)
            player_me, _ = await Player.objects.async_get_or_create(user=me)
            match.winner = player_me
            await match.async_save()

    async def spectate_match(self, match, member):
        pass

    async def create_next_matches_category(self, guild):
        qs = ssbu_models.MatchCategory.objects.filter(category__guild=guild)
        number = await qs.async_count() + 1
        return await self.create_matches_category(guild, number)

    async def create_matches_category(self, guild, number):
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, connect=True,
                                                  manage_messages=True, manage_channels=True)
        }
        category_name = f"Matches {number}" if number != 1 else "Matches"
        category = await guild.create_category_channel(name=category_name, overwrites=overwrites,
                                                       reason="Creating category necessary for matches")
        category = await self.db.wrap_category_channel(category)
        new_match_category = ssbu_models.MatchCategory(category=category, number=number)
        await new_match_category.async_save()
        return new_match_category

    async def setup_guild(self, guild: models.Guild, use_elo=True, main_series: ssbu_models.TournamentSeries = None):
        guild_setup, created = await ssbu_models.GuildSetup.async_get_or_create(guild=guild)
        if created:
            guild_setup.use_elo = use_elo
            guild_setup.main_series = main_series
            # create ingame role
            ingame_role = await guild.discord.create_role(name="In-game",
                                                          colour=discord.Colour.from_rgb(207, 54, 48),
                                                          reason="Creating role necessary for matches")
            ingame_role = await self.db.wrap_role(ingame_role)
            guild_setup.ingame_role = ingame_role
            # create first category if there isn't one already
            matches_category = await self.create_next_matches_category(guild)
            await guild_setup.async_save()
        if main_series is not None and main_series.ruleset is None:
            self.create_default_ruleset.sync(guild)
        return guild_setup, not created

    async def create_ruleset(self, ctx):
        await ctx.send(
            "The default ruleset is as follows:\n\n"
            "__Starter Stages__\n"
            "{}\n\n"
            "__Counterpick Stages__\n"
            "{}\n\n"
            "Counterpick Bans: 2\n"
            "DSR: ON\n\n"
            "Do you want to use this ruleset? If no is selected, "
            "you will be able to create a custom ruleset. (y/n)"
            "".format('\n'.join([str(stage) for stage in Stage.get_default_starters()]),
                      '\n'.join([str(stage) for stage in Stage.get_default_counterpicks()]))
        )
        use_custom_ruleset = not await self.core.wait_for_confirmation(ctx)
        if use_custom_ruleset:
            await ctx.send("Please list your starter stages separated by a comma (,) "
                           "(only English names; common stage aliases like **bf** are allowed, "
                           "example: **bf, fd, ps2, sv, tac**):")
            starter_stages = await self.core.wait_for_response(ctx, timeout=300)
            starter_stages = starter_stages.replace(', ', ',')
            starter_stages = [await Stage.convert(ctx, stage) for stage in starter_stages.split(',')]
            starter_stages.sort(key=lambda s: s.id)

            await ctx.send("Please list your counterpick stages separated by a comma (,) "
                           "(only English names; common stage aliases like **bf** are allowed, "
                           "example: **sbf, ys, kalos**):")
            counterpick_stages = await self.core.wait_for_response(ctx, timeout=300)
            counterpick_stages = counterpick_stages.replace(', ', ',')
            counterpick_stages = [await Stage.convert(ctx, stage) for stage in counterpick_stages.split(',')]
            counterpick_stages.sort(key=lambda s: s.id)

            def cp_ban_number_check(number):
                try:
                    number = int(number)
                except TypeError:
                    return False
                if number >= len(counterpick_stages):
                    return False
                return True

            counterpick_bans = None
            await ctx.send("How many counterpick bans?")
            while counterpick_bans is None:
                number = await self.core.wait_for_response(ctx)
                if cp_ban_number_check(number):
                    counterpick_bans = int(number)
                else:
                    await ctx.send("Counterpick bans needs to be a number and lower than "
                                   "the number of counterpick stages, please try again:")

            await ctx.send("Do you want to use DSR (a player cannot pick any stage "
                           "they have won on during the set)? (y/n)")
            use_dsr = await self.core.wait_for_confirmation(ctx)

            await ctx.send("Please give your ruleset a name so you'll recognize it later:")
            name = await self.core.wait_for_response(ctx, message_check=lambda m: len(m.content) <= 128, timeout=120)
        else:
            starter_stages = Stage.get_default_starters()
            counterpick_stages = Stage.get_default_counterpicks()
            counterpick_bans = 2
            use_dsr = True
            name = "Default Rules"

        guild = await self.db.wrap_guild(ctx.guild)
        ruleset = ssbu_models.Ruleset(guild=guild, starter_stages=starter_stages,
                                      counterpick_stages=counterpick_stages,
                                      counterpick_bans=counterpick_bans, dsr=use_dsr)
        return ruleset

    @async_using_db
    def create_default_ruleset(self, guild: models.Guild):
        guild_setup = self.get_setup.sync(guild)
        main_series = guild_setup.main_series
        default_ruleset = ssbu_models.Ruleset.create(name=f"{main_series.name} Rules", guild=guild)
        main_series.ruleset = default_ruleset
        main_series.save()
        return default_ruleset

    @async_using_db
    def get_setup(self, guild: models.Guild):
        try:
            guild_setup = ssbu_models.GuildSetup.get(guild=guild)
        except ssbu_models.GuildSetup.DoesNotExist:
            return None
        return guild_setup

    @async_using_db
    def get_ruleset(self, tournament_series: ssbu_models.TournamentSeries):
        ruleset = tournament_series.ruleset
        if ruleset is None:
            guild_setup = self.get_setup.sync(tournament_series.guild)
            ruleset = guild_setup.default_ruleset
            if ruleset is None:
                ruleset = self.create_default_ruleset.sync(tournament_series.guild)
        return ruleset


# TODO
"""
cached_tournaments
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
