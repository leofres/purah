import asyncio
import datetime
import math
import random
import re

import aiohttp
import challonge

import discord
from discord.utils import find, get
from discord.ext import commands
from discord.ext.commands import BadArgument

import hero
from hero import async_using_db, models, ObjectDoesNotExist
from hero.utils import MockMember

from .dsr import DSR
from .fighters import Fighter
from .models import (Game, GuildPlayer, GuildSetup, Match, MatchCategory, MatchmakingSetup, MatchOffer, MatchSearch,
                     Player, Ruleset, SsbuSettings)
from .stages import Stage
from . import models as ssbu_models, strings
from ..scheduler import schedulable
from .formats import Formats
from .glicko import Glicko2


class SsbuController(hero.Controller):
    settings: SsbuSettings

    glicko = Glicko2()

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

    NUMBER_EMOJIS = (  # 0 - 10
        '\U00000030\U000020e3',
        '\U00000031\U000020e3',
        '\U00000032\U000020e3',
        '\U00000033\U000020e3',
        '\U00000034\U000020e3',
        '\U00000035\U000020e3',
        '\U00000036\U000020e3',
        '\U00000037\U000020e3',
        '\U00000038\U000020e3',
        '\U00000039\U000020e3',
        '\U0001f51f'
    )

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
    def calculate_rating(rating_1, rating_2, points_1, points_2):
        if points_1 + points_2 == 0:
            return rating_1, rating_2
        score = points_1 / (points_1 + points_2)
        rating_difference = rating_2 - rating_1
        odds = 1 / (1 + 10 ** (rating_difference / 400))
        odd_difference_1 = score - odds
        odd_difference_2 = 1 - score - (1 - odds)
        k_factor_1 = 32 if rating_1 <= 2100 else 24 if rating_1 <= 2400 else 16
        k_factor_2 = 32 if rating_2 <= 2100 else 24 if rating_2 <= 2400 else 16
        new_rating_1 = round(rating_1 + k_factor_1 * odd_difference_1)
        new_rating_2 = round(rating_2 + k_factor_2 * odd_difference_2)
        return new_rating_1, new_rating_2

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

    async def strike_stage(self, match: Match, stage: Stage, striked_by: models.User):
        # check if the stage can be striked by the person attempting to do so
        # return True if so (and striking succeeded), otherwise return False
        player_1 = await match.player_1
        player_2 = await match.player_2
        if striked_by.id not in (player_1.id, player_2.id):
            return False

        game = await Game.objects.async_get(match=match, number=match.current_game)
        first_to_strike = await game.first_to_strike
        channel = await match.channel
        await channel.fetch()
        ruleset = await match.ruleset

        if stage in game.striked_stages:
            raise BadArgument(f"{stage} has already been striked! Please choose a different stage.")
        if game.number == 1:
            if stage in ruleset.counterpick_stages:
                num_starters = len(ruleset.starter_stages)
                raise BadArgument(f"As this is the first game, you can only "
                                  f"strike the starter stages listed above, "
                                  f"so the stage number has to be "
                                  f"between 1 and {num_starters}.")
            if len(game.striked_stages) in (0, 3):
                # first to strike is striking
                if first_to_strike.id != striked_by.id:
                    return False
                elif len(game.striked_stages) == 3:
                    # figure out the stage that is left
                    for other_stage in [stage for stage
                                        in ruleset.starter_stages
                                        if stage not in game.striked_stages + [stage]]:
                        return await self.pick_stage(match, other_stage, striked_by)
            elif len(game.striked_stages) in (1, 2):
                # not first to strike is striking
                if first_to_strike.id == striked_by.id:
                    return False
            else:
                return False
        else:
            if len(game.striked_stages) >= ruleset.counterpick_bans:
                return False
            # first to strike is striking
            if first_to_strike.id != striked_by.id:
                return False
            # if stage disallowed due to DSR, stage cannot be striked
            dsr_stages = await ruleset.dsr.get_dsr_stages(match)
            if stage in dsr_stages:
                raise BadArgument(f"{stage} is already banned for this game due to DSR.")

        legal_stages = ruleset.starter_stages + ruleset.counterpick_stages
        if stage not in legal_stages:
            raise BadArgument(f"{stage} is not a legal stage.")

        next_to_strike = None
        if game.number == 1:
            if len(game.striked_stages) in (0, 1):
                if first_to_strike.id == player_1.id:
                    next_to_strike = player_2
                else:
                    next_to_strike = player_1
            elif len(game.striked_stages) == 2:
                next_to_strike = first_to_strike
        else:
            if len(game.striked_stages) < ruleset.counterpick_bans - 1:
                next_to_strike = first_to_strike
            else:
                if first_to_strike.id == player_1.id:
                    next_to_strike = player_2
                else:
                    next_to_strike = player_1

        await self._strike_stage(game, stage)

        if next_to_strike:
            guild = await match.guild
            await guild.fetch()
            next_to_strike = await guild.fetch_member(next_to_strike)
            await self._update_striking_message(match, next_to_strike)
        return True

    @async_using_db
    def _strike_stage(self, game, stage):
        striked_stages = game.striked_stages
        striked_stages.append(stage)
        game.striked_stages = striked_stages
        game.save()

    async def pick_stage(self, match, stage, picked_by):
        # check if the stage can be picked by the person attempting to do so
        # return True if so (and striking succeeded), otherwise
        # either offer the stage to the opponent, or if that's not possible either,
        # return False
        player_1 = await match.player_1
        player_2 = await match.player_2
        if picked_by.id not in (player_1.id, player_2.id):
            return False

        game = await Game.objects.async_get(match=match, number=match.current_game)

        if game.picked_stage is not None:
            return False

        first_to_strike = await game.first_to_strike
        ruleset = await match.ruleset

        if stage in game.striked_stages:
            raise BadArgument(f"{stage} has already been striked! Please choose a different stage.")
        if game.number == 1:
            if stage in ruleset.counterpick_stages:
                num_starters = len(ruleset.starter_stages)
                raise BadArgument(f"As this is the first game, you can only "
                                  f"pick the starter stages listed above, "
                                  f"so the stage number has to be "
                                  f"between 1 and {num_starters}.")
            if len(game.striked_stages) == 3:
                # first to strike is picking
                if first_to_strike.id != picked_by.id:
                    return await self.suggest_stage(match, stage, picked_by)
            else:
                return await self.suggest_stage(match, stage, picked_by)
        elif len(game.striked_stages) != ruleset.counterpick_bans:
            print("not enough bans")
            return await self.suggest_stage(match, stage, picked_by)
        elif first_to_strike.id == picked_by.id:
            print("you were the first to strike")
            return await self.suggest_stage(match, stage, picked_by)
        else:
            # if stage disallowed due to DSR, stage cannot be picked but can be gentlemen'd on
            dsr_stages = await ruleset.dsr.get_dsr_stages(match)
            if stage in dsr_stages:
                print(f"stage {stage} in dsr_stages: {dsr_stages}")
                return await self.suggest_stage(match, stage, picked_by, dsr_banned=True)

        game.picked_stage = stage.id
        await game.async_save()
        await self.game_ready(match, game)
        return True

    async def suggest_stage(self, match, stage, suggested_by, dsr_banned=False):
        # stage is guaranteed to be a valid choice
        game = await Game.objects.async_get(match=match, number=match.current_game)
        # if stage was already picked for this game, return False
        if game.picked_stage is not None:
            return False
        # if suggested_by is the one who last suggested a stage, return False
        last_suggester = await game.suggested_by
        if last_suggester is not None and last_suggester.id == suggested_by.id:
            return False

        game.suggested_stage = stage.id
        game.suggested_by = suggested_by
        await game.async_save()

        player_1 = await match.player_1
        player_2 = await match.player_2
        if player_1.id == suggested_by.id:
            other_player = player_2
        else:
            other_player = player_1
        await other_player.fetch()
        channel = await match.channel
        await channel.fetch()

        _dsr_banned = (f"{stage} is banned for this game due to DSR, however "
                       f"you can still agree to play on it.\n\n"
                       if dsr_banned else "")
        msg = await channel.send(f"{_dsr_banned}{suggested_by.mention} is suggesting {stage}.\n\n"
                                 f"{other_player.mention}, do you want to accept {suggested_by.mention}'s "
                                 f"suggestion, skip stage striking and play this game on {stage}?")
        accept_suggestion = await self.core.wait_for_confirmation(msg, other_player, force_response=False)
        await msg.delete()
        if accept_suggestion:
            await self.accept_stage_suggestion(match, game, stage, suggested_by)
        return True

    async def accept_stage_suggestion(self, match, game, stage, suggested_by):
        await game.async_load()
        if game.picked_stage is not None:  # prevent "race condition"
            return

        game.suggested_stage = stage.id
        game.suggested_by = suggested_by
        game.suggestion_accepted = True
        game.picked_stage = stage.id
        await game.async_save()
        await self.game_ready(match, game)

    async def game_ready(self, match, game):
        player_1 = await match.player_1
        await player_1.fetch()
        player_1_fighter = Fighter(game.player_1_fighter)
        player_2 = await match.player_2
        await player_2.fetch()
        player_2_fighter = Fighter(game.player_2_fighter)
        stage = Stage(game.picked_stage)
        channel = await match.channel
        await channel.fetch()

        await channel.send(
            f"**Game {game.number} ready!**\n\n"
            f"{player_1.mention} (**{player_1_fighter}**) "
            f"vs. {player_2.mention} (**{player_2_fighter}**)\n\n"
            f"Stage: **{stage}**\n\n"
            f"You may now start the game!\n"
            f"When the game is over, if you won the game, use `/won`; "
            f"if you lost it, use `/lost`. GLHF!"
        )

    async def get_stages(self, match):
        ruleset = await match.ruleset
        if match.current_game == 1:
            return ruleset.starter_stages
        else:
            return ruleset.starter_stages + ruleset.counterpick_stages

    async def get_formatted_stage_list(self, game):
        match = await game.match
        _stages = await self.get_stages(match)
        ruleset = await match.ruleset
        dsr_stages = await ruleset.dsr.get_dsr_stages(match)
        stages = []
        for number, stage in enumerate(_stages, 1):
            stages.append(f"**{self.NUMBER_EMOJIS[number]} {stage}**"
                          if not game.is_striked(stage) and stage not in dsr_stages
                          else f"~~{self.NUMBER_EMOJIS[number]} {stage}~~")
        return '\n'.join(stages)

    async def _update_striking_message(self, match, next_to_strike: discord.Member):
        """resend or edit the updated striking message"""
        game = await Game.objects.async_get(match=match, number=match.current_game)
        ruleset = await match.ruleset
        channel = await match.channel
        await channel.fetch()

        stages = await self.get_formatted_stage_list(game)
        if (
            (game.number == 1 and len(game.striked_stages) == 3)
            or (game.number > 1 and len(game.striked_stages) == ruleset.counterpick_bans)
        ):
            picking = next_to_strike
            new_content = f"**Pick a Stage**\n" \
                          f"\n" \
                          f"{stages}\n" \
                          f"\n" \
                          f"{picking.mention}, please pick a stage " \
                          f"using `/pick <stage>` (without <>)!"
        else:
            if len(game.striked_stages) == 0 or (game.number == 1 and len(game.striked_stages) == 1):
                bottom_text = "please strike a stage using `/strike <stage>` (without <>)!"
            else:
                bottom_text = "please strike another stage using `/strike <stage>` (without <>)!"

            new_content = f"**Stage Striking**\n" \
                          f"\n" \
                          f"{stages}\n" \
                          f"\n" \
                          f"{next_to_strike.mention}, {bottom_text}"

        striking_message = await game.striking_message
        if striking_message is not None:
            await striking_message.fetch()
            async for last_message in channel.history(limit=1):
                if striking_message.id == last_message.id:
                    await striking_message.edit(content=new_content)
                    return striking_message
                else:
                    await striking_message.discord.delete()
                    await striking_message.async_delete()

        new_msg = await channel.send(new_content)
        new_msg = await self.db.wrap_message(new_msg)
        game.striking_message = new_msg
        await game.async_save()
        return

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

    async def setup_matchmaking(self, channel, name, ruleset, ranked=False):
        guild = channel.discord.guild
        # configure matchmaking channel
        await channel.discord.set_permissions(guild.default_role, send_messages=False,
                                              add_reactions=False,
                                              reason="Only members looking for players should be able to "
                                                     "send messages in the matchmaking channel")
        await channel.set_permissions(guild.me, send_messages=True,
                                      add_reactions=True, manage_messages=True,
                                      reason="The bot should also be able to "
                                             "send messages in the matchmaking channel")

        # create roles
        looking_name = f"Looking for Player ({name})" if name else "Looking for Player"
        looking_role = await guild.create_role(name=looking_name,
                                               colour=discord.Colour.from_rgb(60, 192, 48),
                                               hoist=True,
                                               reason="Creating role necessary for matchmaking")
        looking_role = await self.db.wrap_role(looking_role)

        await channel.set_permissions(looking_role.discord, send_messages=True,
                                      reason="Only members looking for players should be able to "
                                             "send messages in the matchmaking channel")

        available_name = f"Potentially Available ({name})" if name else "Potentially Available"
        available_role = await guild.create_role(name=available_name,
                                                 colour=discord.Colour.from_rgb(56, 140, 238),
                                                 reason="Creating role necessary for matchmaking")
        available_role = await self.db.wrap_role(available_role)

        guild = await self.db.wrap_guild(guild)
        if ranked:
            await self.create_blindpick_channels(guild)

        # send matchmaking message
        matchmaking_message = await self._send_matchmaking_message(channel, ranked=ranked)

        matchmaking_message = await self.db.wrap_message(matchmaking_message)

        # save setup
        try:
            ruleset = await Ruleset.objects.async_get(name=ruleset.name, guild=guild)
        except Ruleset.DoesNotExist:
            await ruleset.async_save()
        matchmaking_setup = MatchmakingSetup(channel=channel, name=name, ranked=ranked,
                                             matchmaking_message=matchmaking_message,
                                             ruleset=ruleset, looking_role=looking_role,
                                             available_role=available_role)
        await matchmaking_setup.async_save()
        return matchmaking_setup

    async def create_blindpick_channels(self, guild):
        guild_setup = await GuildSetup.objects.async_get(guild=guild)

        ingame_role = await guild_setup.ingame_role
        try:
            await ingame_role.fetch()
        except (discord.Forbidden, AttributeError):
            # create ingame role
            ingame_role = await guild.discord.create_role(name="In-game",
                                                              colour=discord.Colour.from_rgb(207, 54, 48),
                                                              reason="Creating role necessary for matches")
            ingame_role = await self.db.wrap_role(ingame_role)
            guild_setup.ingame_role = ingame_role
            await guild_setup.async_save()

        blindpick_channel_1 = await guild_setup.player_1_blindpick_channel
        blindpick_channel_2 = await guild_setup.player_2_blindpick_channel

        if blindpick_channel_1 is None or blindpick_channel_2 is None:
            owner_id = self.core.owner_id
            try:
                owner = await guild.fetch_member(owner_id)
            except discord.NotFound:
                owner = None
            try:
                _matchmaking_category = await MatchCategory.objects.async_get(category__guild=guild, number=1)
                matchmaking_category = await _matchmaking_category.category
                await matchmaking_category.fetch()
            except MatchCategory.DoesNotExist:
                _matchmaking_category = await self.create_matches_category(guild, 1)
                matchmaking_category = await _matchmaking_category.category
                await matchmaking_category.fetch()
            except discord.NotFound:
                await _matchmaking_category.async_delete()
                _matchmaking_category = await self.create_matches_category(guild, 1)
                matchmaking_category = await _matchmaking_category.category
                await matchmaking_category.fetch()

        if blindpick_channel_1 is None:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, read_message_history=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True,
                                                      manage_channels=True),
            }
            bp_channel_1 = await guild.create_text_channel("blindpick-player-1", overwrites=overwrites,
                                                           category=matchmaking_category,
                                                           reason=f"Creating first channel for blindpicking")
            bp_channel_1 = await self.db.wrap_text_channel(bp_channel_1)
            guild_setup.player_1_blindpick_channel = bp_channel_1

        if blindpick_channel_2 is None:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, read_message_history=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True,
                                                      manage_channels=True),
            }
            bp_channel_2 = await guild.create_text_channel("blindpick-player-2", overwrites=overwrites,
                                                           category=matchmaking_category,
                                                           reason=f"Creating first channel for blindpicking")
            bp_channel_2 = await self.db.wrap_text_channel(bp_channel_2)
            guild_setup.player_2_blindpick_channel = bp_channel_2

        if blindpick_channel_1 is None or blindpick_channel_2 is None:
            await guild_setup.async_save()

    async def _send_matchmaking_message(self, channel: models.TextChannel, original_message: models.Message = None,
                                        ranked=False):
        new_msg = None
        _ranked = "**[RANKED]**\n\n" if ranked else ""
        content = (
            f"{_ranked}Click a reaction to change your matchmaking status:\n"
            f"\n"
            f"{self.LOOKING_REACTION} **Looking for Player**\n"
            f"{self.AVAILABLE_REACTION} **Potentially Available**\n"
            f"{self.DND_REACTION} **Do Not Disturb** (Default)\n"
            f"\n"
            f"**Note:** You can add a custom message to your "
            f"match search by sending a message in here "
            f"after you start looking for players."
        )
        if original_message is None:
            new_msg = await channel.discord.send(content)
        else:
            try:
                await original_message.fetch()
            except discord.NotFound:
                new_msg = await channel.discord.send(content)
            else:
                await original_message.discord.edit(content=content)
                return original_message
        await new_msg.add_reaction(self.LOOKING_REACTION)  # mag
        await new_msg.add_reaction(self.AVAILABLE_REACTION)  # bell
        await new_msg.add_reaction(self.DND_REACTION)  # no_bell
        return new_msg

    async def get_active_matchmaking_match(self, user):
        # get all unfinished matches that are at least 6 hours old
        six_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=6)
        matches_qs = (
            Match.objects.filter(tournament=None, player_1__id=user.id, started_at__lte=six_hours_ago, ended_at=None)
            | Match.objects.filter(tournament=None, player_2__id=user.id, started_at__lte=six_hours_ago, ended_at=None)
        ).order_by('started_at')
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
            voice_channel = await match.voice_channel

            if channel is not None:
                try:
                    await channel.fetch()
                except (discord.Forbidden, discord.NotFound):
                    pass
                else:
                    try:
                        await channel.discord.delete()
                    except discord.Forbidden:
                        pass

            if voice_channel is not None:
                try:
                    await voice_channel.fetch()
                except (discord.Forbidden, discord.NotFound):
                    pass
                else:
                    try:
                        await voice_channel.discord.delete()
                    except discord.Forbidden:
                        pass

            await match.async_delete()  # match that never ended and where another one started after is useless
            if channel is not None:
                await channel.async_delete()
            if voice_channel is not None:
                await voice_channel.async_delete()
        active_match_channel = await active_match.channel
        try:
            await active_match_channel.fetch()
        except AttributeError:
            await active_match.async_delete()
            return None
        except (discord.Forbidden, discord.NotFound):
            await active_match.async_delete()
            await active_match_channel.async_delete()
            return None
        return active_match

    async def look_for_opponents(self, matchmaking_setup: MatchmakingSetup, member: models.Member):
        channel = await matchmaking_setup.channel
        if await MatchSearch.objects.filter(setup=matchmaking_setup, looking=member).async_exists():
            return
        guild = await channel.guild
        # TODO fix this
        # guild_setup = await guild.guildsetup
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role
        try:
            await ingame_role.fetch()
        except (discord.Forbidden, AttributeError):
            # create ingame role
            ingame_role = await guild.discord.create_role(name="In-game",
                                                          colour=discord.Colour.from_rgb(207, 54, 48),
                                                          reason="Creating role necessary for matches")
            ingame_role = await self.db.wrap_role(ingame_role)
            guild_setup.ingame_role = ingame_role
            await guild_setup.aaync_save()
        looking_role = await matchmaking_setup.looking_role
        available_role = await matchmaking_setup.available_role

        _member: discord.Member = member.discord
        if looking_role in _member.roles:
            return
        if ingame_role in _member.roles:
            await channel.discord.send(f"{_member.mention}, you seem to be in-game right now so you "
                                       f"can't look for opponents until you finish your current match.",
                                       delete_after=30)

        user = await member.user
        active_match = await self.get_active_matchmaking_match(user)
        if active_match:
            active_match_channel = await active_match.channel
            if not member.is_fetched:
                await member.fetch()
            member_mention = member.mention
            if active_match_channel is None:
                do_close_active_match = True
            else:
                try:
                    await active_match_channel.fetch()
                except discord.NotFound:
                    do_close_active_match = True
                else:
                    channel_mention = active_match_channel.mention

                    if active_match.ranked:
                        msg_txt = (f"{member_mention}, you still have an active ranked match in "
                                   f"{channel_mention}."
                                   f"Would you like to forfeit that match now?")
                    else:
                        msg_txt = (f"{member_mention}, you still have an active match in "
                                   f"{channel_mention}."
                                   f"Would you like to leave that match now?")
                    msg = await channel.send(msg_txt)
                    do_close_active_match = await self.core.wait_for_confirmation(msg, member.discord)
                    await msg.delete()
            if do_close_active_match:
                try:
                    await self.close_match(active_match, member)
                except discord.NotFound:  # user probably left it themselves
                    pass
            else:
                return

        await member.add_roles(looking_role)
        await member.remove_roles(available_role)
        message = await self._send_match_search(channel, member, looking_role, available_role,
                                                ranked=matchmaking_setup.ranked)
        message = await self.db.wrap_message(message)
        # save match search
        match_search = MatchSearch(message=message, looking=member, setup=matchmaking_setup)
        await match_search.async_save()

    async def _send_match_search(self, channel, member, looking_role, available_role, ranked=False):
        if not channel.is_fetched:
            await channel.fetch()
        if not member.is_fetched:
            await member.fetch()
        if not looking_role.is_fetched:
            await looking_role.fetch()
        if not available_role.is_fetched:
            await available_role.fetch()

        if ranked:
            local_player, _ = await GuildPlayer.objects.async_get_or_create(member=member)
            rating_txt = f"(Rating: {local_player.rating}) "
        else:
            rating_txt = ""
        message = await channel.send(f"{member.mention} {rating_txt}is looking for a match! "
                                     f"{looking_role.mention} {available_role.mention}\n\n"
                                     f"React with {self.OFFER_REACTION} to challenge {member.mention}!")
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
        await match_search.async_delete()
        try:
            _message = await message.fetch()
            await _message.delete()
        except discord.Forbidden:
            try:
                await _message.channel.send("I cannot delete match searches, please grant me the "
                                            "**Manage Messages** permission.", delete_after=60)
            except (NameError, discord.Forbidden):
                pass
        except discord.NotFound:
            pass

    async def ensure_no_active_matches(self, channel, member: models.Member):
        user = await member.user
        active_match = await self.get_active_matchmaking_match(user)
        if active_match:
            active_match_channel = await active_match.channel
            if active_match_channel is None:
                do_close_active_match = True
            else:
                if not member.is_fetched:
                    await member.fetch()
                member_mention = member.mention
                try:
                    await active_match_channel.fetch()
                except discord.NotFound:
                    do_close_active_match = True
                else:
                    channel_mention = active_match_channel.mention

                    if active_match.ranked:
                        msg_txt = (f"{member_mention}, you still have an active ranked match in "
                                   f"{channel_mention}."
                                   f"Would you like to forfeit that match now?")
                    else:
                        msg_txt = (f"{member_mention}, you still have an active match in "
                                   f"{channel_mention}."
                                   f"Would you like to leave that match now?")
                    msg = await channel.send(msg_txt)
                    do_close_active_match = await self.core.wait_for_confirmation(msg, member.discord)
                    await msg.delete()
            if do_close_active_match:
                try:
                    await self.close_match(active_match, member)
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

        if not member.is_fetched:
            await member.fetch()

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
        except MatchSearch.MultipleObjectsReturned:
            match_searches = await MatchSearch.objects.filter(setup=matchmaking_setup, looking=member).async_to_list()
            for match_search in match_searches:
                await self.delete_match_search(match_search)
            await _member.remove_roles(looking_role)
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
        except MatchSearch.MultipleObjectsReturned:
            match_searches = await MatchSearch.objects.filter(setup=matchmaking_setup, looking=member).async_to_list()
            async def _delete_match_searches(*_match_searches):
                for _match_search in _match_searches:
                    await self.delete_match_search(_match_search)
            self.core.loop.create_task(_delete_match_searches(*match_searches))
            await _member.remove_roles(looking_role)
        else:
            await self.delete_match_search(match_search)
            await _member.remove_roles(looking_role)
        # remove potentially available role
        await _member.remove_roles(available_role)

    async def set_as_ingame(self, *members):
        guild = await members[0].guild
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role
        try:
            await ingame_role.fetch()
        except discord.NotFound:
            # create ingame role
            ingame_role = await guild.discord.create_role(name="In-game",
                                                          colour=discord.Colour.from_rgb(207, 54, 48),
                                                          reason="Creating role necessary for matches")
            ingame_role = await self.db.wrap_role(ingame_role)
            guild_setup.ingame_role = ingame_role
            await guild_setup.async_save()

        for member in members:
            await self._clear_searches(member)
            await self._clear_offers(member)
            # give ingame role
            await member.add_roles(ingame_role)

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

    async def offer_match(self, channel, offered_to, offering, allow_decline=True, ranked=False):
        if await MatchOffer.objects.filter(message__channel=channel, offering=offering, offered_to=offered_to).async_exists():
            return
        # if await MatchOffer.objects.filter(message__channel=channel, offering=offered_to, offered_to=offering).async_exists():
            # return
        # check if there's an active match
        guild = await channel.guild
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role

        if not offering.is_fetched:
            await offering.fetch()

        _member: discord.Member = offering.discord
        if ingame_role in _member.roles:
            await channel.discord.send(f"{_member.mention}, you seem to be in-game right now so you "
                                       f"can't offer matches until you finish your current match.",
                                       delete_after=30)
            return

        if not await self.ensure_no_active_matches(channel, offering):
            return

        rating_txt = ""
        try:
            matchmaking_setup = await MatchmakingSetup.objects.async_get(channel=channel)
        except MatchmakingSetup.DoesNotExist:
            pass
        else:
            if matchmaking_setup.ranked:
                ranked = True

        if ranked:
            # only one ranked match per pair per guild per day
            offered_to_user = await offered_to.user
            offering_user = await offering.user
            qs = Match.ranked_matches_today_qs(offered_to_user, offering_user, guild=guild)
            cant_offer = await qs.async_exists()
            if cant_offer:
                latest_match = await qs.async_latest()
                wait_for_td = datetime.timedelta(hours=18) - (datetime.datetime.now() - latest_match.started_at)
                hours, _remainder = divmod(wait_for_td.total_seconds(), 3600)
                minutes, seconds = divmod(_remainder, 60)
                hours, minutes, seconds = int(hours), int(minutes), math.ceil(seconds)
                wait_for = f"{hours} hours, {minutes} minutes and {seconds} seconds"
                if not offered_to.is_fetched:
                    await offered_to.fetch()
                _other_member = offered_to.discord

                await channel.discord.send(
                    f"{_member.mention}, you can't play ranked matches with {_other_member.mention} "
                    f"yet. You can do so again in {wait_for}. Please try to find a different opponent "
                    f"in the meantime!", delete_after=30
                )
                return
            local_player, _ = await GuildPlayer.objects.async_get_or_create(member=offering)
            rating_txt = f"(Rating: {local_player.rating}) "

        _ranked = "ranked " if ranked else ""
        message = await channel.send(f"{offered_to.mention}, {offering.mention} {rating_txt}is "
                                     f"offering a {_ranked}match!\n\n"
                                     f"Click the {self.ACCEPT_REACTION} if you want to "
                                     f"accept {offering.mention}'s challenge.")
        await message.add_reaction(self.ACCEPT_REACTION)  # white_check_mark
        if allow_decline:
            await message.add_reaction(self.DECLINE_REACTION)  # negative_squared_cross_mark
        message = await self.db.wrap_message(message)
        match_offer = MatchOffer(message=message, offering=offering, offered_to=offered_to, ranked=ranked)
        await match_offer.async_save()

    async def decline_offer(self, match_offer):
        message = await match_offer.message
        await match_offer.async_delete()
        try:
            _message = await message.fetch()
            await _message.delete()
        except discord.Forbidden:
            try:
                await _message.channel.send("I cannot delete match offers, please grant me the "
                                            "**Manage Messages** permission.", delete_after=60)
            except (NameError, discord.Forbidden):
                pass
        except discord.NotFound:
            pass

    async def create_match(self, offered_to, offering, origin_channel, ruleset=None, ranked=False, create_vc=True):
        if not offered_to.is_fetched:
            await offered_to.fetch()
        if not offering.is_fetched:
            await offering.fetch()

        channel, voice_channel, in_dms = await self._create_match_channel(offered_to, offering, origin_channel,
                                                                          ranked=ranked, create_vc=create_vc)
        await self.set_as_ingame(offered_to, offering)
        # TODO enable in_dms
        if not in_dms:
            management_message = await self._send_match_management_message(channel, offered_to, offering, ranked=ranked)
            channel = await self.db.wrap_text_channel(channel)
            voice_channel = await self.db.wrap_voice_channel(voice_channel) if not None else None
        guild = await channel.guild
        try:
            matchmaking_setup = await MatchmakingSetup.objects.async_get(channel=origin_channel)
            # available_role = await matchmaking_setup.available_role
            # await offered_to.remove_roles(available_role)
            # await offering.remove_roles(available_role)
        except MatchmakingSetup.DoesNotExist:
            matchmaking_setup = None
        management_message = await self.db.wrap_message(management_message)
        offered_to_user = await offered_to.user
        offering_user = await offering.user
        match = Match(
            channel=channel, guild=guild, voice_channel=voice_channel, setup=matchmaking_setup,
            management_message=management_message, ranked=ranked, in_dms=in_dms,
            player_1=offered_to_user, player_2=offering_user, ruleset=ruleset
        )
        if ranked:
            guild_setup = await GuildSetup.objects.async_get(guild=guild)
            if guild_setup.verified:
                global_player_1, _ = await Player.objects.async_get_or_create(user=offered_to_user)
                global_player_2, _ = await Player.objects.async_get_or_create(user=offering_user)
                match.player_1_global_rating = global_player_1.rating
                match.player_1_global_deviation = global_player_1.deviation
                match.player_1_global_volatility = global_player_1.volatility
                match.player_2_global_rating = global_player_2.rating
                match.player_2_global_deviation = global_player_2.deviation
                match.player_2_global_volatility = global_player_2.volatility
            player_1, _ = await GuildPlayer.objects.async_get_or_create(member=offered_to)
            player_2, _ = await GuildPlayer.objects.async_get_or_create(member=offering)
            match.player_1_rating = player_1.rating
            match.player_1_deviation = player_1.deviation
            match.player_1_volatility = player_1.volatility
            match.player_2_rating = player_2.rating
            match.player_2_deviation = player_2.deviation
            match.player_2_volatility = player_2.volatility
        await match.async_save()
        # TODO tournament match support
        if ranked:
            await self.match_intro(match)
        return match

    async def _create_match_channel(self, offered_to, offering, origin_channel, ranked: bool, create_vc=True):
        guild = await offered_to.guild
        match_categories = await MatchCategory.objects.filter(category__guild=guild).async_to_list()
        await guild.fetch()
        owner_id = self.core.owner_id
        try:
            owner = await guild.fetch_member(owner_id)
        except discord.NotFound:
            owner = None
        selected_category = None
        if len(match_categories) == 0:
            selected_category = await self.create_matches_category(guild, 1)
        else:
            for i, match_category in enumerate(match_categories, 1):
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
        if ranked:
            name_format_args.append('ranked')
        name_format_args.append(offered_to.name)
        name_format_args.append('vs')
        name_format_args.append(offering.name)
        matchmaking_name = origin_channel.name.replace("matchmaking", "").strip('_-')
        if matchmaking_name:  # if it's not an empty string now
            name_format_args.append(matchmaking_name)

        text_name = '_'.join(name_format_args)
        if len(text_name) > 100:
            text_name = text_name[0:100]
        text_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True,
                                                  manage_channels=True),
            offered_to: discord.PermissionOverwrite(read_messages=True, manage_messages=True),
            offering: discord.PermissionOverwrite(read_messages=True, manage_messages=True)
        }
        if owner:
            text_overwrites[owner] = discord.PermissionOverwrite(read_messages=True, manage_messages=True,
                                                                 manage_channels=True)
        text_channel = await guild.create_text_channel(text_name, overwrites=text_overwrites,
                                                       category=selected_category,
                                                       reason=f"Creating match channel for "
                                                              f"{offered_to.display_name} and "
                                                              f"{offering.display_name}")

        if not create_vc:
            voice_channel = None
        else:
            voice_name = ' '.join(name_format_args)
            if len(voice_name) > 100:
                voice_name = voice_name[0:100]
            voice_overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False),
                guild.me: discord.PermissionOverwrite(connect=True, manage_channels=True),
                offered_to: discord.PermissionOverwrite(connect=True),
                offering: discord.PermissionOverwrite(connect=True)
            }
            if owner:
                voice_overwrites[owner] = discord.PermissionOverwrite(connect=True, manage_channels=True)
            voice_channel = await guild.create_voice_channel(voice_name, overwrites=voice_overwrites,
                                                             category=selected_category,
                                                             reason=f"Creating voice channel for match with "
                                                                    f"{offered_to.display_name} and "
                                                                    f"{offering.display_name}")
        return text_channel, voice_channel, False

    async def _send_match_management_message(self, channel, player_1, player_2, ranked=False):
        leave_forfeit = "Forfeit" if ranked else "Leave"
        _ranked = "Ranked " if ranked else ""
        message = await channel.send(f"{_ranked}Match between {player_1.mention} and {player_2.mention}\n"
                                     f"\n"
                                     f"**Match Control Panel**\n"
                                     f"\n"
                                     f"{self.PRIVATE_REACTION} (Default) **Make the match private**\n"
                                     f"{self.PUBLIC_REACTION} [SOON] **Allow spectators to view the match**\n"
                                     f"{self.LEAVE_REACTION} **{leave_forfeit} the match**\n")

        await message.pin()
        await message.add_reaction(self.PRIVATE_REACTION)  # lock
        await message.add_reaction(self.PUBLIC_REACTION)  # no_lock
        await message.add_reaction(self.LEAVE_REACTION)  # negative_squared_cross_mark

        return message

    async def match_intro(self, match):
        player_1 = await match.player_1
        await player_1.fetch()
        player_2 = await match.player_2
        await player_2.fetch()
        channel = await match.channel
        await channel.fetch()
        guild = await match.guild

        first_to_strike = random.choice([player_1, player_2])
        await Game.objects.async_create(match=match, number=1, guild=guild, first_to_strike=first_to_strike)

        blindpicking_txt = await self.start_blindpicking(channel, player_1, player_2)

        _ranked = "Ranked " if match.ranked else ""
        best_of = match.wins_required * 2 - 1
        await channel.send(
            f"**{_ranked}Match** between {player_1.mention} and {player_2.mention}\n"
            f"**Best of {best_of}**\n"
            f"**Game 1**\n\n"
            f"{blindpicking_txt}"
        )

    async def start_blindpicking(self, channel, player_1, player_2) -> str:
        player_1_success = False
        player_2_success = False
        if not player_1.is_fetched:
            await player_1.fetch()
        if not player_2.is_fetched:
            await player_2.fetch()
        guild = await channel.guild
        guild_setup = await GuildSetup.objects.async_get(guild=guild)

        ask_for_blindpick_txt = (
            "Please pick the character you're going to use for game 1 using the "
            "`/charpick <character>` command (without <>) here."
        )

        try:
            await player_1.send(ask_for_blindpick_txt)
        except discord.Forbidden:
            pass
        else:
            player_1_success = True

        try:
            await player_2.send(ask_for_blindpick_txt)
        except discord.Forbidden:
            pass
        else:
            player_2_success = True

        if player_1_success:
            instructions_1 = "check your DMs"
        else:
            player_1_bp_channel = await guild_setup.player_1_blindpick_channel
            await player_1_bp_channel.fetch()
            overwrite_1 = {
                player_1.discord: discord.PermissionOverwrite(read_messages=True)
            }
            await player_1_bp_channel.discord.edit(overwrites=overwrite_1, reason=f"Allowing Player 1 "
                                                                                  f"({player_1.discord}) "
                                                                                  f"to blindpick a character for match "
                                                                                  f"{channel.name}")
            instructions_1 = f"use the `/charpick <character>` command (without <>) in " \
                             f"{player_1_bp_channel.discord.mention}"

        if player_2_success:
            instructions_2 = "check your DMs"
        else:
            player_2_bp_channel = await guild_setup.player_2_blindpick_channel
            await player_2_bp_channel.fetch()
            overwrite_2 = {
                player_2.discord: discord.PermissionOverwrite(read_messages=True)
            }
            await player_2_bp_channel.discord.edit(overwrites=overwrite_2, reason=f"Allowing Player 2 "
                                                                                  f"({player_2.discord}) "
                                                                                  f"to blindpick a character for match "
                                                                                  f"{channel.name}")
            instructions_2 = f"use the `/charpick <character>` command (without <>) in " \
                             f"{player_2_bp_channel.mention}"

        blindpick_txt = (
            f"Please blindpick your characters before striking.\n"
            f"For that, {player_1.mention}, please {instructions_1}.\n"
            f"{player_2.mention}, please {instructions_2}."
        )

        return blindpick_txt

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

    async def close_match(self, match, ended_by=None):
        # if ranked match, ended_by forfeited

        channel = await match.channel
        voice_channel = await match.voice_channel
        guild = await match.guild

        try:
            await guild.fetch()
        except (discord.NotFound, discord.Forbidden):
            await match.async_delete()
            if channel:
                await channel.async_delete()
            if voice_channel:
                await voice_channel.async_delete()
            return True

        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role
        player_1 = await match.player_1
        player_1_member = await guild.fetch_member(player_1.id)
        player_2 = await match.player_2
        player_2_member = await guild.fetch_member(player_2.id)

        await self._delete_spectating_message(match)

        if not match.ranked:
            me = await self.db.wrap_user(self.core.user)
            match.winner = me
            match.ended_at = datetime.datetime.now()
            await match.async_save()

        if channel is not None:
            try:
                await channel.fetch()
            except (discord.Forbidden, discord.NotFound):
                pass
            else:
                try:
                    await channel.discord.delete()
                except discord.Forbidden:
                    pass
            await channel.async_delete()
        if voice_channel is not None:
            try:
                await voice_channel.fetch()
            except (discord.Forbidden, discord.NotFound):
                pass
            else:
                try:
                    await voice_channel.discord.delete()
                except discord.Forbidden:
                    pass
            await voice_channel.async_delete()

        await player_1_member.remove_roles(ingame_role)
        await player_2_member.remove_roles(ingame_role)

    async def spectate_match(self, match, member):
        pass

    async def pick_character(self, channel, picking, fighter: Fighter):
        game, player_num, finished_blindpick, regular_pick, last_pick = await self._pick_character(channel,
                                                                                                   picking,
                                                                                                   fighter)

        if not any((finished_blindpick, regular_pick, last_pick)):
            await channel.send("Thanks! Please wait for your opponent to finish their blindpick.")
            return

        match = await game.match

        if finished_blindpick:
            await self._finish_blindpick(match, game)
            return

        if regular_pick:
            await self._report_pick(match, game, player_num)
            return

        if last_pick:
            await self._report_last_pick(match, game, player_num)

    @async_using_db  # to prevent race condition
    def _pick_character(self, channel, picking, fighter: Fighter):
        finished_blindpick = False
        first_pick = False
        second_pick = False
        player_num = None
        game = None

        if GuildSetup.objects.filter(player_1_blindpick_channel__id=channel.id).exists():
            player_num = 1
            try:
                # TODO allow for unranked tournament matches
                game = Game.objects.filter(match__player_1=picking, match__winner=None, number=1,
                                           player_1_fighter=None).latest('match__id')
            except Game.DoesNotExist:
                raise commands.CheckFailure("There doesn't seem to be a match that you "
                                            "need to blindpick a fighter for.")
        elif GuildSetup.objects.filter(player_2_blindpick_channel__id=channel.id).exists():
            player_num = 2
            try:
                game = Game.objects.filter(match__player_2=picking, match__winner=None, number=1,
                                           player_2_fighter=None).latest('match__id')
            except Game.DoesNotExist:
                raise commands.CheckFailure("There doesn't seem to be a match that you "
                                            "need to blindpick a fighter for.")
        elif isinstance(channel, discord.DMChannel):  # from DMs
            try:
                game = Game.objects.filter(match__player_1=picking, match__winner=None, number=1,
                                           player_1_fighter=None).latest('match__id')
            except Game.DoesNotExist:
                try:
                    game = Game.objects.filter(match__player_2=picking, match__winner=None, number=1,
                                               player_2_fighter=None).latest('match__id')
                except Game.DoesNotExist:
                    raise commands.CheckFailure("There doesn't seem to be a match that you "
                                                "need to blindpick a fighter for.")
                else:
                    player_num = 2
            else:
                player_num = 1

        if game is None:  # charpicked from inside the match channel
            try:
                match = Match.objects.get(channel=channel.id)
            except Match.DoesNotExist:
                raise commands.CheckFailure("There's a time and place for everything, but not now!")
            else:
                game = Game.objects.get(match=match, number=match.current_game)
                if match.player_1.id == picking.id:
                    player_num = 1
                elif match.player_2.id == picking.id:
                    player_num = 2
                else:
                    raise commands.CheckFailure("There's a time and place for everything, but not now!")

        if player_num == 1:
            if game.player_1_fighter is not None:
                raise commands.CheckFailure("You already picked a character for this game.")
            else:
                game.player_1_fighter = fighter.id
        else:
            if game.player_2_fighter is not None:
                raise commands.CheckFailure("You already picked a character for this game.")
            else:
                game.player_2_fighter = fighter.id

        game.save()

        if game.player_1_fighter is not None and game.player_2_fighter is not None:
            if game.number == 1:
                finished_blindpick = True
            else:
                second_pick = True
        else:
            if game.number != 1:
                first_pick = True

        return game, player_num, finished_blindpick, first_pick, second_pick

    async def _finish_blindpick(self, match, game):
        guild = await match.guild
        await guild.fetch()
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        p1_bp_channel: discord.TextChannel = await guild_setup.player_1_blindpick_channel
        await p1_bp_channel.fetch()
        p2_bp_channel = await guild_setup.player_2_blindpick_channel
        await p2_bp_channel.fetch()

        fighter_1 = Fighter(game.player_1_fighter)
        player_1 = await match.player_1
        player_1_member = guild.get_member(player_1.id)
        if player_1_member is None:
            player_1_member = await guild.fetch_member(player_1.id)
        await p1_bp_channel.set_permissions(player_1_member, overwrite=None)
        await player_1.fetch()

        fighter_2 = Fighter(game.player_2_fighter)
        player_2 = await match.player_2
        player_2_member = guild.get_member(player_2.id)
        if player_2_member is None:
            player_2_member = await guild.fetch_member(player_2.id)
        await p2_bp_channel.set_permissions(player_2_member, overwrite=None)
        await player_2.fetch()

        channel = await match.channel
        await channel.fetch()

        await channel.send(f"{player_1.mention} chose **{fighter_1}**!\n"
                           f"{player_2.mention} chose **{fighter_2}**!\n")

        await self.start_striking(match)

    async def _report_pick(self, match, game, player_num, last_pick=False):
        # TODO support next_to_pick
        channel = await match.channel
        await channel.fetch()

        if player_num == 1:
            fighter = Fighter(game.player_1_fighter)
            player = await match.player_1
            other_player = await match.player_2
        else:
            fighter = Fighter(game.player_2_fighter)
            player = await match.player_2
            other_player = await match.player_1

        await player.fetch()

        if last_pick:
            txt = f"{player.mention} chose **{fighter}**!"
        else:
            await other_player.fetch()
            txt = (
                f"{player.mention} chose **{fighter}**!\n\n"
                f"{other_player.mention}, please pick a fighter using "
                f"`/charpick <character>`!"
            )
        await channel.send(txt)

    async def _report_last_pick(self, match, game, player_num):
        await self._report_pick(match, game, player_num)

        await self.start_striking(match)

    async def start_striking(self, match):
        game = await Game.objects.async_get(match=match, number=match.current_game)
        guild = await match.guild
        first_to_strike_user = await game.first_to_strike
        first_to_strike_member = MockMember(first_to_strike_user.id, guild.id)
        first_to_strike = await self.db.wrap_member(first_to_strike_member)
        await first_to_strike.fetch()

        await self._update_striking_message(match, first_to_strike)

    async def start_charpicking(self, match):
        last_game = await Game.objects.async_get(match=match, number=match.current_game - 1)
        last_winner = await last_game.winner
        await last_winner.fetch()
        player_1 = await match.player_1
        player_2 = await match.player_2
        channel = await match.channel
        await channel.fetch()

        if last_winner.id == player_1.id:
            last_winner_fighter = Fighter(last_game.player_1_fighter)
            last_loser = player_2
            last_loser_fighter = Fighter(last_game.player_2_fighter)
        else:
            last_winner_fighter = Fighter(last_game.player_2_fighter)
            last_loser = player_1
            last_loser_fighter = Fighter(last_game.player_1_fighter)
        await last_loser.fetch()

        msg = await channel.send(f"{last_winner.mention}, do you want to switch from "
                                 f"{last_winner_fighter} after winning the last game?")
        switch_character = await self.core.wait_for_confirmation(msg, last_winner, force_response=False)
        if switch_character:
            await channel.send("Please use `/charpick <character>` to switch to a different character.")
        else:
            current_game = await Game.objects.async_get(match=match, number=match.current_game)
            if player_1.id == last_winner.id:
                current_game.player_1_fighter = last_winner_fighter.id
            else:
                current_game.player_2_fighter = last_winner_fighter.id
            await current_game.async_save()

            msg = await channel.send(f"{last_loser.mention}, do you want to switch from "
                                     f"{last_loser_fighter} for this game?")
            switch_character = await self.core.wait_for_confirmation(msg, last_loser, force_response=False)

            if switch_character:
                await channel.send("Please use `/charpick <character>` to switch to a different character.")
            else:
                if player_1.id == last_loser.id:
                    current_game.player_1_fighter = last_loser_fighter.id
                else:
                    current_game.player_2_fighter = last_loser_fighter.id
                await current_game.async_save()

                await self.start_striking(match)

    async def process_victory(self, match, player):
        game = await Game.objects.async_get(match=match, number=match.current_game)
        needs_confirmation_by = await game.needs_confirmation_by
        _winner = await game.winner
        if needs_confirmation_by is not None and player.id == needs_confirmation_by.id and player.id == _winner.id:
            winner = player
            game.needs_confirmation_by = None
            await game.async_save()
            await self.end_game(match, game, winner)
        else:
            player_1 = await match.player_1
            player_2 = await match.player_2
            channel = await match.channel
            await channel.fetch()
            if player_1.id == player.id:
                game.winner = player_1
                needs_confirmation_by = player_2
                game.needs_confirmation_by = needs_confirmation_by
            else:
                game.winner = player_2
                needs_confirmation_by = player_1
                game.needs_confirmation_by = needs_confirmation_by
            await game.async_save()
            await needs_confirmation_by.fetch()
            await channel.send(f"{needs_confirmation_by.mention}, please confirm this game's result with "
                               f"`/lost`.")

    async def process_loss(self, match, player):
        game = await Game.objects.async_get(match=match, number=match.current_game)
        player_1 = await match.player_1
        player_2 = await match.player_2
        needs_confirmation_by = await game.needs_confirmation_by
        _winner = await game.winner
        if needs_confirmation_by is not None and player.id == needs_confirmation_by.id and player.id != _winner.id:
            if player_1.id == player.id:
                await player_2.fetch()
                winner = player_2
            else:
                await player_1.fetch()
                winner = player_1
            game.needs_confirmation_by = None
            await game.async_save()
            await self.end_game(match, game, winner)
        else:
            channel = await match.channel
            await channel.fetch()
            if player_1.id == player.id:
                game.winner = player_2
                needs_confirmation_by = player_2
                game.needs_confirmation_by = needs_confirmation_by
            else:
                game.winner = player_1
                needs_confirmation_by = player_1
                game.needs_confirmation_by = needs_confirmation_by
            await game.async_save()
            await needs_confirmation_by.fetch()
            await channel.send(f"{needs_confirmation_by.mention}, please confirm this game's result with "
                               f"`/won`.")

    async def end_game(self, match, game, winner):
        channel = await match.channel
        await channel.fetch()
        player_1 = await match.player_1
        player_2 = await match.player_2
        if winner.id == player_1.id:
            win_count = match.player_1_score + 1
            match.player_1_score = win_count
        else:
            win_count = match.player_2_score + 1
            match.player_2_score = win_count
        await match.async_save()
        # check if winner has won enough games in this match
        if win_count == match.wins_required:
            # if so, announce match winner and gracefully end match
            await player_1.fetch()
            await player_2.fetch()
            await channel.send(
                f"{winner.mention} wins game {game.number} and with that, {winner.mention} wins the match!\n\n"
                f"Score: {player_1.mention} **{match.player_1_score} – {match.player_2_score}** {player_2.mention}"
            )
            await self.gracefully_end_match(match)
            return

        # if not, announce winner of game
        await channel.send(
            f"{winner.mention} wins game {game.number}!"
        )
        # wait 5 seconds
        await asyncio.sleep(5)
        # create next game
        match.current_game += 1
        guild = await match.guild
        next_game = await Game.objects.async_create(match=match, number=match.current_game,
                                                    guild=guild, first_to_strike=winner)
        await match.async_save()

        # then start next game
        await self.game_intro(match, next_game)

    async def game_intro(self, match, game):
        # intro message
        channel = await match.channel
        await channel.fetch()
        player_1 = await match.player_1
        await player_1.fetch()
        player_2 = await match.player_2
        await player_2.fetch()
        _ranked = "Ranked " if match.ranked else ""
        await channel.send(
            f"**Game {game.number}** of {_ranked}Match between "
            f"{player_1.mention} and {player_2.mention}!"
        )
        # start charpicking
        await self.start_charpicking(match)

    async def handle_forfeit(self, match, player):
        channel = await match.channel
        await channel.fetch()
        msg = await channel.send(f"{player.mention}, are you sure you want to forfeit this match?")
        confirm_forfeit = await self.core.wait_for_confirmation(msg, player, force_response=False)
        await msg.delete()
        if not confirm_forfeit:
            return

        await channel.send(f"{player.mention} forfeited!")

        player_1 = await match.player_1
        player_2 = await match.player_2
        try:
            last_game = await Game.objects.async_get(match=match, number=match.current_game)
        except Game.DoesNotExist:  # bug during creation
            await self.close_match(match, ended_by=player)
            return
        if player.id == player_1.id:
            # match.player_1_score = 0
            match.player_2_score = match.wins_required
            last_game.winner = player_2
        else:
            match.player_1_score = match.wins_required
            # match.player_2_score = 0
            last_game.winner = player_1
        await self.gracefully_end_match(match)

    async def process_match_result(self, player_1, player_2, score_1, score_2, guild=None):
        results_1 = await self.get_all_results(player_1, guild=guild)
        results_2 = await self.get_all_results(player_2, guild=guild)
        if guild is None:
            player_1: Player = await Player.objects.async_get(user=player_1)
            player_2: Player = await Player.objects.async_get(user=player_2)
        else:
            player_1, _ = await GuildPlayer.objects.async_get_or_create(
                member__user__id=player_1.id, member__guild__id=guild.id
            )
            player_2, _ = await GuildPlayer.objects.async_get_or_create(
                member__user__id=player_2.id, member__guild__id=guild.id
            )
        old_rating_1 = self.glicko.create_rating(
            player_1.rating, player_1.deviation, player_1.volatility
        )
        old_rating_2 = self.glicko.create_rating(
            player_2.rating, player_2.deviation, player_2.volatility
        )
        rating_1, rating_2 = self.glicko.rate_match(old_rating_1, old_rating_2, score_1, score_2,
                                                    results_1, results_2)
        rating_1['mu'] = round(rating_1['mu'])
        rating_1['phi'] = round(rating_1['phi'])
        rating_1['sigma'] = round(rating_1['sigma'], 3)
        rating_2['mu'] = round(rating_2['mu'])
        rating_2['phi'] = round(rating_2['phi'])
        rating_2['sigma'] = round(rating_2['sigma'], 3)
        player_1.rating = rating_1['mu']
        player_1.deviation = rating_1['phi']
        player_1.volatility = rating_1['sigma']
        await player_1.async_save()
        player_2.rating = rating_2['mu']
        player_2.deviation = rating_2['phi']
        player_2.volatility = rating_2['sigma']
        await player_2.async_save()
        return old_rating_1, rating_1, old_rating_2, rating_2

    async def get_all_results(self, player, guild=None):
        if guild is None:
            player_1_matches = await (
                Match.objects.filter(guild__guildsetup__verified=True, ranked=True, player_1=player)
            ).exclude(
                winner=None, player_1_global_rating=None
            ).async_to_list()
            player_2_matches = await (
                Match.objects.filter(guild__guildsetup__verified=True, ranked=True, player_2=player)
            ).exclude(
                winner=None, player_2_global_rating=None
            ).async_to_list()
            return [
                (
                    self.glicko.calculate_weight(match.player_1_score, match.player_2_score),
                    self.glicko.create_rating(
                        match.player_1_global_rating, match.player_1_global_deviation, match.player_1_global_volatility
                    )
                )
                for match in player_1_matches
            ] + [
                (
                    self.glicko.calculate_weight(match.player_2_score, match.player_1_score),
                    self.glicko.create_rating(
                        match.player_2_global_rating, match.player_2_global_deviation, match.player_2_global_volatility
                    )
                )
                for match in player_2_matches
            ]
        else:
            player_1_matches = await (
                Match.objects.filter(guild=guild, ranked=True, player_1=player)
            ).exclude(
                winner=None
            ).async_to_list()
            player_2_matches = await (
                Match.objects.filter(guild=guild, ranked=True, player_2=player)
            ).exclude(
                winner=None
            ).async_to_list()
            return [
                (
                    self.glicko.calculate_weight(match.player_1_score, match.player_2_score),
                    self.glicko.create_rating(
                        match.player_1_rating, match.player_1_deviation, match.player_1_volatility
                    )
                )
                for match in player_1_matches
            ] + [
                (
                    self.glicko.calculate_weight(match.player_2_score, match.player_1_score),
                    self.glicko.create_rating(
                        match.player_2_rating, match.player_2_deviation, match.player_2_volatility
                    )
                )
                for match in player_2_matches
            ]

    async def gracefully_end_match(self, match):
        channel = await match.channel
        await channel.fetch()
        # save winner and ended_at
        last_game = await Game.objects.async_get(match=match, number=match.current_game)
        winner = await last_game.winner
        match.winner = winner
        match.ended_at = datetime.datetime.now()
        await match.async_save()
        # remove in-game role
        guild = await match.guild
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        player_1 = await match.player_1
        await player_1.fetch()
        player_2 = await match.player_2
        await player_2.fetch()
        # if ranked, calculate rating changes and apply them
        if match.ranked:
            player_1_member = MockMember(player_1.id, guild.id)
            player_1_member = await self.db.wrap_member(player_1_member)
            player_2_member = MockMember(player_2.id, guild.id)
            player_2_member = await self.db.wrap_member(player_2_member)

            rating_diff_txt = ""
            if guild_setup.verified:
                rating_diff_txt += "Global Rating changes:\n\n"
                global_old_rating_1, global_new_rating_1, global_old_rating_2, global_new_rating_2 = self.process_match_result(
                    player_1, player_2, match.player_1_score, match.player_2_score
                )
                sign_1 = '+' if global_old_rating_1 < global_new_rating_1 else ''
                sign_2 = '+' if global_old_rating_2 < global_new_rating_2 else ''
                global_diff_1 = global_new_rating_1 - global_old_rating_1
                global_diff_2 = global_new_rating_2 - global_old_rating_2
                rating_diff_txt += (
                    f"{player_1.mention}: **{global_new_rating_1['mu']}**±**{global_new_rating_1['phi']}** "
                    f"(**{sign_1}{global_diff_1}**)\n"
                    f"{player_2.mention}: **{global_new_rating_2['mu']}**±**{global_new_rating_2['phi']}** "
                    f"(**{sign_2}{global_diff_2}**)\n\n"
                )
            rating_diff_txt += "Local Rating changes:\n\n"
            local_old_rating_1, local_new_rating_1, local_old_rating_2, local_new_rating_2 = await self.process_match_result(
                player_1, player_2, match.player_1_score, match.player_2_score, guild=guild
            )
            sign_1 = '+' if local_old_rating_1['mu'] < local_new_rating_1['mu'] else ''
            sign_2 = '+' if local_old_rating_2['mu'] < local_new_rating_2['mu'] else ''
            local_diff_1 = local_new_rating_1['mu'] - local_old_rating_1['mu']
            local_diff_2 = local_new_rating_2['mu'] - local_old_rating_2['mu']
            rating_diff_txt += (
                f"{player_1.mention}: **{local_new_rating_1['mu']}**±**{local_new_rating_1['phi']}** "
                f"(**{sign_1}{local_diff_1}**)\n"
                f"{player_2.mention}: **{local_new_rating_2['mu']}**±**{local_new_rating_2['phi']}** "
                f"(**{sign_2}{local_diff_2}**)"
            )
            await channel.send(rating_diff_txt)

        # TODO if match.setup, offer members to set their matchmaking status

        await channel.send("This channel will be closed in 1 minute. Make sure to continue conversations in DMs!")
        await asyncio.sleep(60)
        await self.close_match(match)

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

    async def setup_guild(self, guild: models.Guild, use_rating=True, main_series: ssbu_models.TournamentSeries = None):
        guild_setup, created = await ssbu_models.GuildSetup.async_get_or_create(guild=guild)
        if created:
            guild_setup.use_rating = use_rating
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

    async def create_ruleset(self, ctx, given_name=None):
        if not given_name:
            msg = await ctx.send(
                "The default ruleset is as follows:\n\n"
                "__Starter Stages__\n"
                "{}\n\n"
                "__Counterpick Stages__\n"
                "{}\n\n"
                "Counterpick Bans: 2\n"
                "DSR: ON\n\n"
                "Do you want to use this ruleset? If no is selected, "
                "you will be able to create a custom ruleset "
                "or choose from the ones you already created for your server."
                "".format('\n'.join([str(stage) for stage in Stage.get_default_starters()]),
                          '\n'.join([str(stage) for stage in Stage.get_default_counterpicks()]))
            )
            use_custom_ruleset = not await self.core.wait_for_confirmation(msg, ctx.author)
        else:
            use_custom_ruleset = True
        if use_custom_ruleset:
            # allow people to choose from existing rulesets
            if not given_name:
                msg = await ctx.send("Do you want to use an existing ruleset?")
                use_existing_ruleset = await self.core.wait_for_confirmation(msg, ctx.author)
                if use_existing_ruleset:
                    guild = await self.db.wrap_guild(ctx.guild)
                    rulesets_qs = Ruleset.objects.filter(guild=guild).distinct('name')
                    rulesets = await rulesets_qs.async_to_list()
                    ruleset_names = [ruleset.name for ruleset in rulesets]
                    ruleset_name = await self.core.wait_for_choice(ctx, ctx.author,ruleset_names, timeout=90)
                    ruleset = await Ruleset.objects.filter(guild=guild, name=ruleset_name).async_latest()
                    return ruleset
            while True:
                await ctx.send("Please list your 5 starter stages separated by a comma (,) "
                               "(only English names; common stage aliases like **bf** are allowed, "
                               "example: **bf, fd, ps2, sv, tac**):")
                starter_stages = await self.core.wait_for_response(ctx, timeout=300)
                starter_stages = starter_stages.replace(', ', ',')
                starter_stages = [await Stage.convert(ctx, stage) for stage in starter_stages.split(',')]
                if len(starter_stages) != 5:
                    await ctx.send("You need exactly 5 starter stages!")
                else:
                    break
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
                except ValueError:
                    return False
                if number < 0:
                    return False
                if number != 0 and number >= len(starter_stages) + len(counterpick_stages) - 1:
                    return False
                return True

            counterpick_bans = None
            await ctx.send("How many counterpick bans?")
            while counterpick_bans is None:
                number = await self.core.wait_for_response(ctx)
                if cp_ban_number_check(number):
                    counterpick_bans = int(number)
                else:
                    await ctx.send("Counterpick bans needs to be a number and less than or"
                                   "equal to the total number of stages - 2, please try again:")

            dsr = DSR('off')

            msg = await ctx.send("I support multiple different variations of DSR. "
                                 "I will ask you for each one that I support if you want to use it.\n\n"
                                 "Do you want to use regular DSR (a player cannot pick any stage "
                                 "they have won on during the set)? (y/n)")
            use_regular_dsr = await self.core.wait_for_confirmation(msg, ctx.author)
            if use_regular_dsr:
                dsr = DSR('on')

            msg = await ctx.send("Do you want to use modified DSR (a player cannot pick the stage "
                                 "they have most recently won on during the set)? (y/n)")
            use_modified_dsr = await self.core.wait_for_confirmation(msg, ctx.author)
            if use_modified_dsr:
                dsr = DSR('modified')
            if not given_name:
                await ctx.send("Please give your ruleset a name so you'll recognize it later:")
                name = await self.core.wait_for_response(ctx, message_check=lambda m: len(m.content) <= 128, timeout=120)
                version = 1
            else:
                name = given_name
                guild = await self.db.wrap_guild(ctx.guild)
                last_version = await Ruleset.objects.filter(name=name, guild=guild).async_latest()
                version = last_version.version + 1
                ruleset = Ruleset.objects.async_create(
                    name=name, guild=guild, version=version,
                    starter_stages=starter_stages,
                    counterpick_stages=counterpick_stages,
                    counterpick_bans=counterpick_bans, dsr=dsr
                )
                return ruleset
        else:
            starter_stages = Stage.get_default_starters()
            counterpick_stages = Stage.get_default_counterpicks()
            counterpick_bans = 2
            dsr = DSR('on')
            name = "Default Rules"

        guild = await self.db.wrap_guild(ctx.guild)
        ruleset = Ruleset(name=name, guild=guild, starter_stages=starter_stages,
                          counterpick_stages=counterpick_stages,
                          counterpick_bans=counterpick_bans, dsr=dsr)
        return ruleset

    @async_using_db
    def create_default_ruleset(self, guild: models.Guild):
        guild_setup = self.get_setup.sync(guild)
        main_series = guild_setup.main_series
        default_ruleset = ssbu_models.Ruleset.create(name=f"{main_series.name} Ruleset", guild=guild)
        main_series.ruleset = default_ruleset
        main_series.save()
        return default_ruleset

    async def edit_ruleset(self, ctx, name):
        guild = await self.db.wrap_guild(ctx.guild)
        next_version = await self.create_ruleset(ctx, given_name=name)
        matchmaking_setups = await MatchmakingSetup.objects.filter(guild=guild, ruleset__name=name).async_to_list()
        for matchmaking_setup in matchmaking_setups:
            matchmaking_setup.ruleset = next_version
            await matchmaking_setup.async_save()

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
