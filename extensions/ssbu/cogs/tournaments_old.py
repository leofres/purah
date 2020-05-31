import asyncio
from collections import defaultdict, OrderedDict
import datetime
import math
import random
import re
from typing import List

import aiohttp

import challonge

import discord

from redbot.core import commands, checks, bank, errors
from redbot.core.config import Config, Group

from . import checks as custom_checks, strings


class Tournaments(commands.Cog):
    """Host tournaments via Challonge"""
    __author__ = "Palucina#1801"

    challonge_user = None

    class FakeMember:
        def __init__(self, user_id, guild_id):
            self.id = user_id
            self.guild = discord.Object(guild_id)
            self.mention = f"<@{user_id}>"
            self.name = "invalid user"
            self.display_name = "invalid user"
            self.nickname = None

        def __str__(self):
            return str(self.id)

    STARTER_STAGES = (
        "Battlefield",
        "Final Destination",
        "Lylat Cruise",
        "Pokémon Stadium 2",
        "Smashville"
    )
    COUNTERPICK_STAGES = (
        "Yoshi's Story",
        "Kalos Pokémon League",
        "Town and City"
    )
    ALL_STAGES = STARTER_STAGES + COUNTERPICK_STAGES
    BANNED_ALTS = (
        "Dream Land GB (2D)",
        "Duck Hunt (2D)",
        "Flatzone X (2D)",
        "Gamer (Camera Issues)",
        "Hanenbow (2D)",
        "Super Mario Maker (2D)",
        "Mute City (SNES) (2D)",
        "PAC-LAND (2D)",
        "Pilot Wings (Camera Issues)",
        "Windy Hill Zone (Grass covers objects)"
    )
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

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cached_tournaments = {}
        self.cached_participants = {}
        self.cached_matches = {}
        self.config = Config.get_conf(
            self,
            identifier=1004548351,
            force_registration=True,
        )
        default_global = {
            'challonge_username': None,
            'challonge_api_key': None
        }
        default_guild = {
            'participant_role_id': None,
            'organizer_role_id': None,
            'streamer_role_id': None,
            'matches_category_id': None,
            'starter_stages': [
                "Battlefield",
                "Final Destination",
                "Lylat Cruise",
                "Pokémon Stadium 2",
                "Smashville"
            ],
            'counterpick_stages': [
                "Yoshi's Story",
                "Kalos Pokémon League",
                "Town and City"
            ],
            'counterpick_bans': 2,
            'dsr': False
        }
        default_member = {
            'challonge_id': None,
            'current_match_channel_id': None,
            'current_doubles_tournament_id': None,
            'current_team_member_id': None
        }
        default_user = {
            'elo': 1000,
            'challonge_username': None,
            'challonge_user_id': None
        }
        default_tournament = {
            'channel_id': None,
            'tournament_id': None,
            'guild_id': None,
            'signup_message_id': None,
            'checkin_message_id': None,
            'doubles': False
        }
        default_participant = {
            'challonge_id': None,
            'tournament_id': None,
            'user_id': None,
            'guild_id': None,
            'starting_elo': None,
            'match_count': 0,
            'forfeit_count': 0
        }
        default_team = {  # keys: lower user ID, higher user ID
            'player_1_user_id': None,
            'player_2_user_id': None,
            'name': None,
            'current_tournament_id': None,
            'current_participant_id': None,
            'elo': 1000
        }
        default_participant_team = {  # key: challonge participant ID
            'challonge_id': None,
            'tournament_id': None,
            'guild_id': None,
            'player_1_user_id': None,
            'player_1_checked_in': False,
            'player_2_user_id': None,
            'player_2_checked_in': False,
            'starting_elo': None,
            'match_count': 0,
            'forfeit_count': 0
        }
        default_match = {
            'match_id': None,
            'channel_id': None,
            'guild_id': None,
            'tournament_id': None,
            'player_1_user_id': None,
            'player_1_challonge_id': None,
            'player_2_user_id': None,
            'player_2_challonge_id': None,
            'player_1_score': 0,
            'player_2_score': 0,
            'current_game_nr': 1,
            'last_game_won_by': None,
            'wins_required': 2,
            'winner_user_id': None,
            'winner_challonge_id': None
        }
        default_doubles_match = {
            'match_id': None,
            'channel_id': None,
            'guild_id': None,
            'tournament_id': None,
            'team_1_player_1_user_id': None,
            'team_1_player_2_user_id': None,
            'team_1_challonge_id': None,
            'team_2_player_1_user_id': None,
            'team_2_player_2_user_id': None,
            'team_2_challonge_id': None,
            'team_1_score': 0,
            'team_2_score': 0,
            'current_game_nr': 1,
            'last_game_won_by': None,
            'wins_required': 2,
            'winner_user_ids': None,
            'winner_challonge_id': None
        }
        default_game = {
            'match_id': None,
            'game_number': None,
            'first_to_strike_user_id': None,
            'striking_message_id': None,
            'striked_stages': [],
            'suggested_stage': None,
            'suggested_by_user_id': None,
            'suggestion_accepted': None,
            'picked_stage': None,
            'winner_user_id': None,
            'needs_confirmation_by_user_id': None,
            'winner_confirmed': False
        }
        default_game = {
            'match_id': None,
            'game_number': None,
            'first_to_strike_user_id': None,
            'striking_message_id': None,
            'striked_stages': [],
            'suggested_stage': None,
            'suggested_by_user_id': None,
            'suggestion_accepted': None,
            'picked_stage': None,
            'winner_user_id': None,
            'needs_confirmation_by_user_id': None,
            'winner_confirmed': False
        }
        self.config.init_custom("tournament", 1)
        self.config.init_custom("participant", 1)
        self.config.init_custom("match", 1)
        self.config.init_custom("game", 2)
        self.config.init_custom("team", 2)
        self.config.init_custom("participant_team", 1)
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)
        self.config.register_user(**default_user)
        self.config.register_custom("tournament", **default_tournament)
        self.config.register_custom("participant", **default_participant)
        self.config.register_custom("match", **default_match)
        self.config.register_custom("game", **default_game)
        self.config.register_custom("team", **default_team)
        self.config.register_custom("participant_team", **default_participant_team)

        self.bot.loop.create_task(self.initialize_challonge_user())

        super().__init__()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        emoji = payload.emoji  # type: discord.PartialEmoji
        message_id = payload.message_id
        user_id = payload.user_id
        channel_id = payload.channel_id
        guild_id = payload.guild_id

        # Ignore own reactions
        if user_id == self.bot.user.id:
            return

        # If the reaction comes from a PrivateChannel, it is not relevant here
        if guild_id is None:
            return

        # None of the relevant reactions currently use custom emojis
        if emoji.is_custom_emoji():
            return

        # Does the reaction come from a signup message?
        if message_id == await self.config.custom('tournament', channel_id).signup_message_id():
            tournament_id = await self.config.custom('tournament', channel_id).tournament_id()
            user = self.bot.get_user(user_id)
            guild = self.bot.get_guild(guild_id)  # type: discord.Guild
            member = guild.get_member(user_id)  # type: discord.Member
            participant_id = await self.config.member(member).challonge_id()
            if participant_id is not None:
                if await self.config.custom('participant', participant_id).tournament_id() == tournament_id:
                    return
            factions_cog = self.bot.get_cog('Factions')
            is_doubles = await self.config.custom('tournament', tournament_id).doubles()
            if guild_id == factions_cog.GUILD_ID and not is_doubles:
                if await factions_cog.config.user(user).faction() is None:
                    await user.send("You have to join a faction first, see <#510140373171961886>.")
                    channel = guild.get_channel(channel_id)  # type: discord.TextChannel
                    message = await channel.fetch_message(message_id)  # type: discord.Message
                    await message.remove_reaction(emoji, member)
                    return
            tournament = await self.get_challonge_tournament(tournament_id)
            if tournament.state != challonge.TournamentState.pending.value:
                await member.send(f"Signups are not currently open for **{tournament.name}**.")
                channel = guild.get_channel(channel_id)  # type: discord.TextChannel
                message = await channel.fetch_message(message_id)  # type: discord.Message
                await message.remove_reaction(emoji, member)
                return
            if is_doubles:
                current_team_member_id = await self.config.member(member).current_team_member_id()
                if current_team_member_id is None:
                    await member.send(f"You need to find another team member and create a team in order to "
                                      f"sign up for **{tournament.name}**. Check out the `.teamup @user` "
                                      f"command for that.")
                    return
                await self.signup_team_member(tournament, member)
                role_id = await self.config.guild(guild).participant_role_id()
                role = guild.get_role(role_id)
                await member.add_roles(role, reason=f"Signed up {member} for: {tournament.name}")
                other_team_member = guild.get_member(current_team_member_id)
                await other_team_member.add_roles(role, reason=f"Signed up {other_team_member} "
                                                               f"for: {tournament.name}")
            else:
                await self.signup(tournament, member)
            role_id = await self.config.guild(guild).participant_role_id()
            role = guild.get_role(role_id)
            await member.add_roles(role, reason=f"Signed up {member} for: {tournament.name}")
            await member.send(f"You were successfully signed up for: **{tournament.name}**")
            return

        # Does the reaction come from a check-in message?
        if message_id == await self.config.custom('tournament', channel_id).checkin_message_id():
            tournament_id = await self.config.custom('tournament', channel_id).tournament_id()
            guild = self.bot.get_guild(guild_id)  # type: discord.Guild
            member = guild.get_member(user_id)  # type: discord.Member
            is_doubles = await self.config.custom('tournament', tournament_id).doubles()
            if not is_doubles:
                participant_id = await self.config.member(member).challonge_id()
                if (participant_id is None
                    or await self.config.custom('participant', participant_id).tournament_id() != tournament_id):
                    return
            else:
                current_team_member_id = await self.config.member(member).current_team_member_id()
                (player_1_id, player_2_id) = ((user_id, current_team_member_id)
                                              if user_id < current_team_member_id
                                              else (current_team_member_id, user_id))
                participant_id = await self.config.custom("participant_team", player_1_id, player_2_id).challonge_id()
                if (participant_id is None
                    or await self.config.custom("participant_team", player_1_id, player_2_id).tournament_id() != tournament_id):
                    return
            tournament = await self.get_challonge_tournament(tournament_id)
            if not is_doubles:
                await self.checkin(tournament, member)
            else:
                await self.checkin_team_member(tournament, member)
            await member.send(f"You were successfully checked in for: **{tournament.name}**\n"
                              f"Please wait until your first match starts.")

    @commands.group(invoke_without_command=True, aliases=['to', 'tournament'])
    @commands.guild_only()
    async def tournaments(self, ctx: commands.Context):
        """Tournament management commands"""
        await ctx.send_help()

    @commands.command(hidden=True)
    @checks.is_owner()
    async def setchallongecredentials(self, ctx: commands.Context, username: str, apikey: str):
        await self.config.challonge_username.set(username)
        await self.config.challonge_api_key.set(apikey)
        await self.initialize_challonge_user()
        await ctx.send("Challonge credentials set.")

    @tournaments.command(hidden=True)
    @checks.is_owner()
    async def deleteall(self, ctx: commands.Context):
        await self.config.clear_all()
        await ctx.send("Done.")

    @tournaments.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_roles=True)
    async def setparticipantrole(self, ctx: commands.Context, *, role: discord.Role):
        await self.config.guild(ctx.guild).participant_role_id.set(role.id)
        await ctx.send("Tournament participant role set.")

    @tournaments.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_roles=True)
    async def setorganizerrole(self, ctx: commands.Context, *, role: discord.Role):
        await self.config.guild(ctx.guild).organizer_role_id.set(role.id)
        await ctx.send("Tournament organizer role set.")

    @tournaments.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_roles=True)
    async def setstreamerrole(self, ctx: commands.Context, *, role: discord.Role):
        await self.config.guild(ctx.guild).streamer_role_id.set(role.id)
        await ctx.send("Tournament streamer role set.")

    @tournaments.command()
    @custom_checks.to_only()
    async def setusername(self, ctx: commands.Context, *, username: str):
        """Set your Challonge username so you will be added as tournament admin for tournaments you create

        *Warning: This feature is largely untested; be careful about making changes to the tournament!*
        *Do not ever manually set the winner of a set, use the `.setwinner` command instead.*
        """
        await ctx.message.delete()
        async with ctx.typing():
            user_id = await self.get_challonge_user_id(username)
            await self.config.user(ctx.author).challonge_username.set(username)
            await self.config.user(ctx.author).challonge_user_id.set(user_id)
        await ctx.send(f"{ctx.author.mention}, your Challonge username has been saved.")

    @tournaments.command()
    @custom_checks.to_only()
    async def create(self, ctx: commands.Context, channel: discord.TextChannel):
        """Create a tournament via Challonge"""
        participant_role_id = await self.config.guild(ctx.guild).participant_role_id()
        if participant_role_id is None:
            await ctx.send(f"You have to set the tournament participant role "
                           f"using `{ctx.prefix}tournaments setparticipantrole <role name>`.")
            return
        organizer_role_id = await self.config.guild(ctx.guild).organizer_role_id()
        if organizer_role_id is None:
            await ctx.send(f"You have to set the tournament organizer role "
                           f"using `{ctx.prefix}tournaments setorganizerrole <role name>`.")
            return
        await ctx.send("Please enter the full name of the tournament:")
        response = await self.bot.wait_for('message', check=lambda msg: msg.channel == ctx.channel and msg.author == ctx.author)
        name = response.content
        await ctx.send("Please enter a key to use for the tournament URL (letters, numbers and underscores only):")
        response = await self.bot.wait_for('message', check=lambda msg: msg.channel == ctx.channel and msg.author == ctx.author)
        key = response.content
        await ctx.send("Please enter an introduction message for the tournament (will be displayed on Challonge "
                       "and the tournament channel):")
        response = await self.bot.wait_for('message', check=lambda msg: msg.channel == ctx.channel and msg.author == ctx.author)
        intro_message = response.content
        await ctx.send("Please enter an invite link to use for the tournament description:")
        response = await self.bot.wait_for('message', check=lambda msg: msg.channel == ctx.channel and msg.author == ctx.author)
        invite_link = response.content
        await ctx.send("How many participants should the tournament have at max (up to 100)?")
        response = await self.bot.wait_for('message', check=lambda msg: msg.channel == ctx.channel and msg.author == ctx.author)
        signup_cap = response.content
        if int(signup_cap) > 100:
            await ctx.send("Signup cap needs to be 100 or less.")
            return
        await ctx.send("When should the tournament start? (ISO format, example: `2019-04-27T18:00:00+00:00`)")
        response = await self.bot.wait_for('message', check=lambda msg: msg.channel == ctx.channel and msg.author == ctx.author)
        start_at = response.content
        start_at_datetime = datetime.datetime.fromisoformat(start_at)
        start_time = start_at_datetime.strftime('on %A, %B %d, %Y at %I.%M %p %Z')

        description = strings.description.format(intro_message=intro_message, invite_link=invite_link, channel=channel)

        admin_id = await self.config.user(ctx.author).challonge_user_id()

        try:
            async with ctx.typing():
                tournament = await self.challonge_user.create_tournament(name=name, url=key,
                                                                         tournament_type=challonge.TournamentType.double_elimination,
                                                                         game_name="Super Smash Bros. Ultimate",
                                                                         open_signup=False, hide_forum=True, show_rounds=True,
                                                                         signup_cap=signup_cap,
                                                                         private=True if ctx.guild.id in (
                                                                             522512647862616079,  # Hateno Lab
                                                                             578663817651945482,  # Tournament Testing
                                                                             553311497279897601  # /r/smashbros DMods
                                                                         ) else False,
                                                                         start_at=start_at,
                                                                         description=description,
                                                                         check_in_duration=35)
                # hacky but it works
                if admin_id is not None:
                    await tournament.connection('PUT', f'tournaments/{tournament.id}',
                                                **{
                                                    'shared_administration': 1,
                                                    'tournament[admin_ids_csv]': admin_id
                                                })
                signup_message = await self.send_signup_message(channel,
                                                                intro_message=intro_message,
                                                                start_time=start_time,
                                                                full_challonge_url=tournament.full_challonge_url)
                await self.save_tournament(signup_message, tournament)
            await ctx.send(f"{tournament.name} was created successfully: {tournament.full_challonge_url}\n"
                           f"Scheduling tasks...")

            # schedule tournament related commands
            when_to_checkreactions = start_at_datetime - datetime.timedelta(minutes=35)
            when_to_startcheckin = start_at_datetime - datetime.timedelta(minutes=30)
            schedule_cmd = self.bot.get_command('schedule')
            await ctx.invoke(schedule_cmd, f"{key}_checkreactions",
                             schedule=(f'tournaments checkreactions {channel.id}',
                                       when_to_checkreactions, None))
            await ctx.invoke(schedule_cmd, f"{key}_startcheckin",
                             schedule=(f'tournaments startcheckin {channel.id}',
                                       when_to_startcheckin, None))
            await ctx.invoke(schedule_cmd, f"{key}_start",
                             schedule=(f'tournaments start {channel.id}',
                                       start_at_datetime, None))
        except challonge.APIException as ex:
            await ctx.send(f"An error occured:\n```{ex}```")

    @tournaments.command()
    @custom_checks.to_only()
    async def checkreactions(self, ctx: commands.Context, channel: discord.TextChannel):
        # a) who has reacted?
        message_id = await self.config.custom('tournament', channel.id).signup_message_id()
        message = await channel.fetch_message(message_id)  # type: discord.Message
        reaction = discord.utils.find(lambda r: r.emoji == '\U00002705', message.reactions)
        users = await reaction.users().flatten()
        # b) who are the participants?
        tournament_id = await self.config.custom('tournament', channel.id).tournament_id()
        tournament = await self.challonge_user.get_tournament(tournament_id)
        participants = await tournament.get_participants(force_update=True)
        # c) whoever is in b but not in a will have their participant role removed,
        # will be deleted from the config and from challonge
        role_id = await self.config.guild(ctx.guild).participant_role_id()
        participant_role = ctx.guild.get_role(role_id)
        for participant in participants:
            user_id = await self.config.custom('participant', participant.id).user_id()
            user = discord.utils.find(lambda u: u.id == user_id, users)
            if user is None:
                member = ctx.guild.get_member(user_id)
                if member is None:
                    continue
                await member.remove_roles(participant_role, reason=f"{member} signed out of the tournament.")
                await self.config.custom('participant', participant.id).clear()
                await self.config.member(member).clear()
                await tournament.remove_participant(participant)
            else:
                factions_cog = self.bot.get_cog('Factions')
                if channel.guild.id == factions_cog.GUILD_ID:
                    if await factions_cog.config.user(user).faction() is None:
                        member = ctx.guild.get_member(user_id)
                        await message.remove_reaction('\U00002705', member)
                        await member.remove_roles(participant_role, reason=f"{member} signed out of the tournament.")
                        await self.config.custom('participant', participant.id).clear()
                        await self.config.member(member).clear()
                        await tournament.remove_participant(participant)
                        await user.send("You tried to sign up for {tournament.name}, but you have to "
                                        "join a faction first; see <#510140373171961886>. "
                                        "If you want to join this tournament, quickly join a "
                                        "faction and then sign up again in {channel.mention}.")
                        continue
                member = ctx.guild.get_member(user.id)
                if member is not None:
                    await member.add_roles(participant_role, reason=f"{member} signed up for the tournament.")
        await ctx.send(f"Checked reactions for {tournament.name}.")

    @tournaments.command(name='signup')
    @custom_checks.to_only()
    async def _signup(self, ctx, member: discord.Member, channel: discord.TextChannel):
        tournament_id = await self.config.custom('tournament', channel.id).tournament_id()
        user = member
        guild = ctx.guild  # type: discord.Guild
        participant_id = await self.config.member(member).challonge_id()
        if participant_id is not None:
            if await self.config.custom('participant', participant_id).tournament_id() == tournament_id:
                return
        factions_cog = self.bot.get_cog('Factions')
        if ctx.guild.id == factions_cog.GUILD_ID:
            if await factions_cog.config.user(user).faction() is None:
                await user.send("You have to join a faction first, see <#510140373171961886>.")
                return
        tournament = await self.get_challonge_tournament(tournament_id)
        if tournament.state != challonge.TournamentState.pending.value:
            await member.send(f"Signups are not currently open for **{tournament.name}**.")
            return
        await self.signup(tournament, member)
        role_id = await self.config.guild(guild).participant_role_id()
        role = guild.get_role(role_id)
        await member.add_roles(role, reason=f"Signed up {member} for: {tournament.name}")
        try:
            await member.send(f"You were successfully signed up for: **{tournament.name}**")
        except discord.Forbidden:
            pass
        ctx.send("Done.")

    @tournaments.command()
    @custom_checks.to_only()
    async def startcheckin(self, ctx: commands.Context, channel: discord.TextChannel):
        # send check-in message
        role_id = await self.config.guild(ctx.guild).participant_role_id()
        participant_role = ctx.guild.get_role(role_id)  # type: discord.Role
        await participant_role.edit(mentionable=True, reason="I need to ping tournament participants for the check-in.")
        await asyncio.sleep(5)
        message = await self.send_checkin_message(channel, participant_role)
        # store check-in message ID
        await self.config.custom('tournament', channel.id).checkin_message_id.set(message.id)
        tournament_id = await self.config.custom('tournament', channel.id).tournament_id()
        await self.config.custom('tournament', tournament_id).checkin_message_id.set(message.id)
        await asyncio.sleep(15)
        await participant_role.edit(mentionable=False)

    @tournaments.command()
    @custom_checks.to_only()
    async def start(self, ctx: commands.Context, channel: discord.TextChannel):
        tournament_id = await self.config.custom('tournament', channel.id).tournament_id()
        tournament = await self.challonge_user.get_tournament(tournament_id)
        is_doubles = await self.config.custom('tournament', channel.id).doubles()
        # remove participants that are not checked in
        all_participants = await tournament.get_participants(force_update=True)
        await tournament.process_check_ins()
        checked_in_participants = await tournament.get_participants(force_update=True)
        role_id = await self.config.guild(ctx.guild).participant_role_id()
        participant_role = ctx.guild.get_role(role_id)
        if is_doubles:
            for participant in all_participants:
                player_1_id = await self.config.custom('participant_team', participant.id).player_1_user_id()
                player_2_id = await self.config.custom('participant_team', participant.id).player_2_user_id()
                if discord.utils.find(lambda p: p.id == participant.id, checked_in_participants) is None:
                    # participant did not check in
                    player_1 = ctx.guild.get_member(player_1_id)
                    player_2 = ctx.guild.get_member(player_2_id)
                    # delete participant from config
                    await self.config.custom('participant_team', participant.id).clear()
                    # delete member from config
                    await self.config.member(player_1).current_doubles_tournament_id.clear()
                    await self.config.member(player_2).current_doubles_tournament_id.clear()
                    # remove participant role
                    await player_1.remove_roles(participant_role, reason=f"{member} did not check in.")
                    await player_2.remove_roles(participant_role, reason=f"{member} did not check in.")
                else:
                    starting_elo = await self.config.custom("team", player_1_id, player_2_id).elo()
                    await self.config.custom('participant_team', participant.id).starting_elo.set(starting_elo)
        else:
            for participant in all_participants:
                if discord.utils.find(lambda p: p.id == participant.id, checked_in_participants) is None:
                    # participant did not check in
                    user_id = await self.config.custom('participant', participant.id).user_id()
                    member = ctx.guild.get_member(user_id)
                    # delete participant from config
                    await self.config.custom('participant', participant.id).clear()
                    # delete member from config
                    await self.config.member(member).challonge_id.clear()
                    # remove participant role
                    await member.remove_roles(participant_role, reason=f"{member} did not check in.")
                else:
                    user_id = await self.config.custom('participant', participant.id).user_id()
                    try:
                        starting_elo = await self.config.user(self.bot.get_user(user_id)).elo()
                    except AttributeError:
                        starting_elo = 1000
                    await self.config.custom('participant', participant.id).starting_elo.set(starting_elo)

        # start the tournament
        await tournament.start()
        signup_message_id = await self.config.custom('tournament', channel.id).signup_message_id()
        signup_message = await channel.fetch_message(signup_message_id)  # type: discord.Message
        await signup_message.clear_reactions()
        checkin_message_id = await self.config.custom('tournament', channel.id).checkin_message_id()
        checkin_message = await channel.fetch_message(checkin_message_id)
        await checkin_message.clear_reactions()
        await channel.send(strings.tournament_start)
        overwrite = discord.PermissionOverwrite(send_messages=True)
        await channel.set_permissions(participant_role, overwrite=overwrite, reason="Tournament started.")
        # start the matches
        for match in await tournament.get_matches(force_update=True):  # type: challonge.Match
            if challonge.MatchState(match.state) == challonge.MatchState.open_:
                if is_doubles:
                    self.bot.loop.create_task(self.start_doubles_match(ctx.guild, tournament, match))
                else:
                    self.bot.loop.create_task(self.start_match(ctx.guild, tournament, match))

    @tournaments.command()
    @custom_checks.to_only()
    async def startmatch(self, ctx, channel: discord.TextChannel, player_1: discord.Member, player_2: discord.Member):
        tournament_id = await self.config.custom('tournament', channel.id).tournament_id()
        tournament = await self.challonge_user.get_tournament(tournament_id)
        player_1_id = await self.config.member(player_1).challonge_id()
        player_2_id = await self.config.member(player_2).challonge_id()
        for match in await tournament.get_matches(force_update=True):
            if match.player1_id == player_1_id and match.player2_id == player_2_id and match.state == challonge.MatchState.open_.value or match.state == challonge.MatchState.pending:
                await self.start_match(ctx.guild, tournament, match)
                await ctx.send("Done.")
                return
        await ctx.send("No match found.")

    @tournaments.command(aliases=['dq'])
    @custom_checks.to_only()
    async def disqualify(self, ctx, member: discord.Member, tournamentchannel: discord.TextChannel=None):
        if tournamentchannel is None:
            tournamentchannel = ctx.channel
        if member is None:
            await ctx.send("Participant left the server, use "
                           "`.tournaments hackdisqualify <userid> <tournamentchannel>`.")
            return

        tournament_id = await self.config.custom('tournament', tournamentchannel.id).tournament_id()
        tournament = await self.get_challonge_tournament(tournament_id)
        current_match_channel_id = await self.config.member(member).current_match_channel_id()
        current_match_channel = ctx.guild.get_channel(current_match_channel_id)  # type: discord.TextChannel
        match = self.config.custom('match', current_match_channel_id)
        participant_id = await self.config.member(member).challonge_id()
        participant = await tournament.get_participant(participant_id)  # type: challonge.Participant
        await tournament.remove_participant(participant)
        if current_match_channel is not None:
            await current_match_channel.set_permissions(member, send_messages=False, add_reactions=False)
        await ctx.send(f"**{member}** has been disqualified.")
        # make the other player win the current match
        player_1_user_id = await match.player_1_user_id()
        player_2_user_id = await match.player_2_user_id()
        player_1 = ctx.guild.get_member(player_1_user_id)
        player_2 = ctx.guild.get_member(player_2_user_id)
        if member.id == player_1_user_id:
            winner = ctx.guild.get_member(player_2_user_id)
        else:
            winner = ctx.guild.get_member(player_1_user_id)
        if current_match_channel is not None:
            await self.end_match(current_match_channel, winner, disqualified=True)

    @tournaments.command(aliases=['hackdq'])
    @custom_checks.to_only()
    async def hackdisqualify(self, ctx, userid: int, tournamentchannel: discord.TextChannel=None):
        if tournamentchannel is None:
            tournamentchannel = ctx.channel
        member = self.FakeMember(userid, ctx.guild.id)

        tournament_id = await self.config.custom('tournament', tournamentchannel.id).tournament_id()
        tournament = await self.get_challonge_tournament(tournament_id)
        current_match_channel_id = await self.config.member(member).current_match_channel_id()
        current_match_channel = ctx.guild.get_channel(current_match_channel_id)  # type: discord.TextChannel
        match = self.config.custom('match', current_match_channel_id)
        participant_id = await self.config.member(member).challonge_id()
        participant = await tournament.get_participant(participant_id)  # type: challonge.Participant
        await tournament.remove_participant(participant)
        await ctx.send(f"User **{member.id}** has been disqualified.")
        # make the other player win the current match
        player_1_user_id = await match.player_1_user_id()
        player_2_user_id = await match.player_2_user_id()
        if member.id == player_1_user_id:
            winner = ctx.guild.get_member(player_2_user_id)
        else:
            winner = ctx.guild.get_member(player_1_user_id)
        if current_match_channel is not None:
            await self.end_match(current_match_channel, winner, disqualified=True)

    @tournaments.command(hidden=True)
    @checks.is_owner()
    async def __getranking(self, ctx, channel: discord.TextChannel):
        tournament_id = await self.config.custom('tournament', channel.id).tournament_id()
        tournament = await self.get_challonge_tournament(tournament_id)
        tournament.participants = await tournament.get_participants(force_update=True)
        participants_number = len(tournament.participants)
        await ctx.send(f"Number of participants: {participants_number}")
        ranking = await self.get_final_ranking(tournament)
        calculated_ranking = await self.calculate_ranking(ranking)
        for n in ranking:
            await ctx.send(f"Rank {n}:\n\n" + '\n'.join(calculated_ranking[n]))

    @tournaments.command()
    @commands.is_owner()
    async def gettournaments(self, ctx):
        tournaments = await self.challonge_user.get_tournaments(force_update=True)
        text = ""
        for tournament in tournaments:  # type: challonge.Tournament
            text += (f"{tournament.name} ({tournament.id}): \n"
                     f"    Open signup: {tournament.open_signup}\n"
                     f"    Participants: {tournament.participants_count}\n"
                     f"    Private: {tournament.private}\n"
                     f"    Start at: {tournament.start_at}\n"
                     f"    State: {tournament.state}\n"
                     f"    URL: {tournament.full_challonge_url}\n"
                     f"\n")
        await ctx.send(text)

    @tournaments.command()
    @commands.is_owner()
    async def getmatches(self, ctx, channel: discord.TextChannel):
        tournament_id = await self.config.custom('tournament', channel.id).tournament_id()
        tournament = await self.get_challonge_tournament(tournament_id)
        await tournament.get_participants(force_update=True)
        matches = await tournament.get_matches(force_update=True)
        text = ""
        for match in matches:
            player_1 = await tournament.get_participant(match.player1_id)
            player_2 = await tournament.get_participant(match.player2_id)
            text += f"Round {match.round}, {match.id} ({match.identifier}): "
            text += f"{player_1.name} vs {player_2.name}, {match.state}\n"
        await ctx.send(text)

    @tournaments.command()
    @checks.is_owner()
    async def getparticipants(self, ctx, channel: discord.TextChannel):
        tournament_id = await self.config.custom('tournament', channel.id).tournament_id()
        tournament = await self.get_challonge_tournament(tournament_id)
        participants = await tournament.get_participants(force_update=True)
        await ctx.send('\n'.join([f"{p.id} ({p.name}): {p.final_rank}" for p in participants]))

    @tournaments.command()
    @custom_checks.to_only()
    async def end(self, ctx, channel: discord.TextChannel):
        await self.end_tournament(channel)
        await ctx.send("Done.")

    @tournaments.command()
    @custom_checks.to_only()
    async def setbo5(self, ctx, matchchannel: discord.TextChannel):
        match = self.config.custom('match', matchchannel.id)
        if await match.player_1_user_id() is None:
            await ctx.send("Not a match channel.")
            return
        wins_required = await match.wins_required()
        if wins_required == 3:
            await ctx.send("Match is already Bo5.")
            return
        else:
            await match.wins_required.set(3)
            await matchchannel.send("This match is now a Best of 5.")
            await ctx.send("Done.")

    @tournaments.command(hidden=True)
    @checks.is_owner()
    async def setbo3(self, ctx, matchchannel: discord.TextChannel):
        match = self.config.custom('match', matchchannel.id)
        if await match.player_1_user_id() is None:
            await ctx.send("Not a match channel.")
            return
        wins_required = await match.wins_required()
        if wins_required == 2:
            await ctx.send("Match is already Bo3.")
            return
        else:
            await match.wins_required.set(2)
            await matchchannel.send("This match is now a Best of 3.")
            await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    async def teamup(self, ctx, partner: discord.Member):
        current_team_member_id = await self.config.member(ctx.author).current_team_member_id()
        other_current_team_member_id = await self.config.member(partner).current_team_member_id()
        if not current_team_member_id is None is other_current_team_member_id:
            await ctx.send("Both team partners have to leave their current teams before teaming up. "
                           "(Don't worry, your ELO will be saved for when you want to team up with "
                           "your previous partner again.)")
            return
        author = ctx.author
        await ctx.message.delete()
        msg = await ctx.send(strings.teamup_request.format(partner=partner, author=author))
        await msg.add_reaction("\U00002705")  # white_check_mark
        await msg.add_reaction("\U0000274E")  # negative_squared_cross_mark

        def check(r: discord.Reaction, u: discord.User):
            return r.message.id == msg.id and u.id == author.id and str(r.emoji) in ('\U00002705', '\U0000274E')

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=check, timeout=60)  # type: discord.Reaction
            if str(reaction.emoji) == '\U00002705':  # white_check_mark
                await self.config.member(author).current_team_member_id.set(partner.id)
                await self.config.member(author).current_team_member_id.set(partner.id)
                (player_1_id, player_2_id) = ((ctx.author.id, current_team_member_id)
                                              if ctx.author.id < current_team_member_id
                                              else (current_team_member_id, ctx.author.id))
                player_1 = await ctx.guild.get_member(player_1_id)
                player_2 = await ctx.guild.get_member(player_2_id)
                current_team_name = await self.config.custom("team", player_1_id, player_2_id).name()
                if current_team_name is None:
                    name = f"{player_1.name} & {player_2.name}"
                    await self.config.custom("team", player_1_id, player_2_id).name.set(name)
                await msg.delete()
                await ctx.send(f"{player_1.mention} and {player_2.mention}, you are now teamed up and "
                               f"ready for doubles tournaments! You can set your team name using "
                               f"`{ctx.prefix}setteamname <name>`.", delete_after=30)
            elif str(reaction.emoji) == '\U0000274E':  # negative_squared_cross_mark
                await msg.delete()
        except asyncio.TimeoutError:
            await msg.delete()

    @commands.command()
    @commands.guild_only()
    async def setteamname(self, ctx, *, name: str):
        current_team_member_id = await self.config.member(ctx.author).current_team_member_id()
        (player_1_id, player_2_id) = ((ctx.author.id, current_team_member_id)
                                      if ctx.author.id < current_team_member_id
                                      else (current_team_member_id, ctx.author.id))
        await self.config.custom("team", player_1_id, player_2_id).name.set(name)
        tournament_id = await self.config.custom("team", player_1_id, player_2_id).current_tournament_id()
        tournament = await self.get_challonge_tournament(tournament_id)
        if tournament.state == challonge.TournamentState.pending.value:
            participant_id = await self.config.custom("team", player_1_id, player_2_id).current_participant_id()
            participant = await tournament.get_participant(participant_id, force_update=True)
            await participant.change_display_name(name)

    # match commands

    @commands.command()
    @commands.guild_only()
    @custom_checks.match_participant_only()
    async def forfeit(self, ctx):
        match = self.config.custom('match', ctx.channel.id)
        player_1_user_id = await match.player_1_user_id()
        player_2_user_id = await match.player_2_user_id()
        if player_1_user_id == ctx.author.id:
            winner = ctx.guild.get_member(player_2_user_id)
        else:
            winner = ctx.guild.get_member(player_1_user_id)
        await self.end_match(ctx.channel, winner, forfeited=True)

    @commands.command()
    @commands.guild_only()
    @custom_checks.match_participant_only()
    async def strike(self, ctx: commands.Context, stage_number: int):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        match = self.config.custom('match', ctx.channel.id)
        current_game_nr = await match.current_game_nr()

        if stage_number < 1 or stage_number > 8:
            await ctx.send(f"{ctx.author.mention}, that's not a valid stage.")
            return
        if current_game_nr == 1:
            if 6 <= stage_number <= 8:
                await ctx.send(f"{ctx.author.mention}, you can't pick that stage for this match.")
                return

        current_game = self.config.custom('game', ctx.channel.id, current_game_nr)
        async with current_game.striked_stages() as striked_stages:
            striking_member_id = await self.get_striking_member_id(ctx.channel, striked_stages)
            if ctx.author.id != striking_member_id:
                await ctx.send(f"{ctx.author.mention}, it is not your turn to strike a stage.",
                               delete_after=30)
                return
            if stage_number > 8 or stage_number < 1:
                raise commands.BadArgument("Stage number has to be between 1 and 10, "
                                           "or between 1 and 5 if it's game 1.")
            if current_game_nr == 1 and stage_number > 5:
                raise commands.BadArgument("As this is the first game, you can only "
                                           "strike the starter stages listed above, "
                                           "so the stage number has to be "
                                           "between 1 and 5.")
            if stage_number - 1 in striked_stages:
                await ctx.send(f"{self.ALL_STAGES[stage_number - 1]} has already been striked.",
                               delete_after=30)
                return

            striked_stages.append(stage_number - 1)
        striked_stages = await current_game.striked_stages()
        if current_game_nr == 1:
            if len(striked_stages) == 4:
                player_1_user_id = await match.player_1_user_id()
                player_1 = ctx.guild.get_member(player_1_user_id)
                player_2_user_id = await match.player_2_user_id()
                player_2 = ctx.guild.get_member(player_2_user_id)
                for number in range(5):
                    if number not in striked_stages:
                        if number == 0:  # Battlefield
                            await ctx.send(strings.picking_battlefield_version.format(
                                member=ctx.author,
                                forbidden_versions='\n'.join(self.BANNED_ALTS)
                            ))
                        elif number == 1:  # Final Destination
                            await ctx.send(strings.picking_omega_version.format(
                                member=ctx.author,
                                forbidden_versions='\n'.join(self.BANNED_ALTS)
                            ))
                        await self.send_start_game_message(ctx.channel, player_1, player_2,
                                                           current_game_nr, number)
                        return
            else:
                striking_member_id = await self.get_striking_member_id(ctx.channel, striked_stages)
                striking_member = ctx.guild.get_member(striking_member_id)
                await self.send_striking_message(ctx.channel, striking_member, current_game_nr, striked_stages)
        elif len(striked_stages) == 1:
            striking_member_id = await self.get_striking_member_id(ctx.channel, striked_stages)
            striking_member = ctx.guild.get_member(striking_member_id)
            await self.send_striking_message(ctx.channel, striking_member, current_game_nr, striked_stages)
        else:
            picking_member_id = await self.get_picking_member_id(ctx.channel)
            picking_member = ctx.guild.get_member(picking_member_id)
            await self.send_picking_stage_message(ctx.channel, picking_member,
                                                  current_game_nr, striked_stages)

    @commands.command()
    @commands.guild_only()
    @custom_checks.match_participant_only()
    async def pick(self, ctx: commands.Context, stage_number: int):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        match = self.config.custom('match', ctx.channel.id)
        current_game_nr = await match.current_game_nr()

        if stage_number < 0 or stage_number > 8:
            await ctx.send(f"{ctx.author.mention}, that's not a valid stage.")
            return
        if current_game_nr == 1:
            if 6 <= stage_number <= 8:
                await ctx.send(f"{ctx.author.mention}, you can't pick that stage for this match.")
                return

        current_game = self.config.custom('game', ctx.channel.id, current_game_nr)
        picking_member_id = await self.get_picking_member_id(ctx.channel)
        striked_stages = await current_game.striked_stages()

        if stage_number - 1 in striked_stages:
            await ctx.send("This stage can't be picked as it was striked already. Please "
                           "choose a different one.")
            return

        # striking is not complete yet or author is not the player picking the stage
        if ctx.author.id != picking_member_id:
            suggested_stage = await current_game.suggested_stage()
            if suggested_stage is not None:  # a stage was already suggested
                message_content = f"{ctx.author.mention}, a stage has already been suggested for this game."
                suggestion_accepted = await current_game.suggestion_accepted()
                if suggestion_accepted is not None:
                    message_content += " Please proceed to strike stages until a stage has been determined."
                await ctx.send(message_content, delete_after=30)
                return
            else:  # stage is being suggested
                await current_game.suggested_stage.set(stage_number - 1)
                await current_game.suggested_by_user_id.set(ctx.author.id)
                player_1_user_id = await match.player_1_user_id()
                player_2_user_id = await match.player_2_user_id()
                if player_1_user_id == ctx.author.id:
                    opponent_id = player_2_user_id
                else:
                    opponent_id = player_1_user_id
                opponent = ctx.guild.get_member(opponent_id)
                await ctx.send(strings.stage_suggestion.format(suggested_to=opponent, suggested_by=ctx.author,
                                                               stage=self.ALL_STAGES[stage_number - 1]))
        else:  # stage being picked after striking was completed
            await current_game.picked_stage.set(stage_number - 1)
            if current_game_nr > 1:
                # announce fighter
                announcing_user_id = await current_game.first_to_strike_user_id()
                announcing_member = ctx.guild.get_member(announcing_user_id)
                await ctx.send(f"**{self.ALL_STAGES[stage_number - 1]}** was picked. "
                               f"{announcing_member.mention}, since you won the last game, "
                               f"please announce which fighter you are going to pick "
                               f"if you are going to switch to a different one for this game.")
            player_1_user_id = await match.player_1_user_id()
            player_1 = ctx.guild.get_member(player_1_user_id)
            player_2_user_id = await match.player_2_user_id()
            player_2 = ctx.guild.get_member(player_2_user_id)
            if stage_number == 1:  # Battlefield
                await ctx.send(strings.picking_battlefield_version.format(
                    member=ctx.author,
                    forbidden_versions='\n'.join(self.BANNED_ALTS)
                ))
            elif stage_number == 2:  # Final Destination
                await ctx.send(strings.picking_omega_version.format(
                    member=ctx.author,
                    forbidden_versions='\n'.join(self.BANNED_ALTS)
                ))
            await self.send_start_game_message(ctx.channel, player_1, player_2,
                                               current_game_nr, stage_number - 1)

    @commands.command()
    @commands.guild_only()
    @custom_checks.match_participant_only()
    async def accept(self, ctx: commands.Context):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        match = self.config.custom('match', ctx.channel.id)
        current_game_nr = await match.current_game_nr()
        current_game = self.config.custom('game', ctx.channel.id, current_game_nr)
        suggested_by_user_id = await current_game.suggested_by_user_id()
        if ctx.author.id == suggested_by_user_id:
            await ctx.send(f"{ctx.author.mention}, you can't accept your own stage suggestion.")
            return
        await current_game.suggestion_accepted.set(True)
        suggested_stage = await current_game.suggested_stage()
        await current_game.picked_stage.set(suggested_stage)
        if current_game_nr > 1:
            # announce fighter
            announcing_user_id = await current_game.first_to_strike_user_id()
            announcing_member = ctx.guild.get_member(announcing_user_id)
            await ctx.send(f"{announcing_member.mention}, please announce which fighter you are going to pick.")
            try:
                await self.bot.wait_for('message',
                                        check=lambda msg: msg.author == announcing_member and msg.channel == ctx.channel,
                                        timeout=120)
            except asyncio.TimeoutError:
                pass
        player_1_user_id = await match.player_1_user_id()
        player_1 = ctx.guild.get_member(player_1_user_id)
        player_2_user_id = await match.player_2_user_id()
        player_2 = ctx.guild.get_member(player_2_user_id)
        if suggested_stage == 0:  # Battlefield
            await ctx.send(strings.picking_battlefield_version.format(
                member=ctx.author,
                forbidden_versions='\n'.join(self.BANNED_ALTS)
            ))
        elif suggested_stage == 1:  # Final Destination
            await ctx.send(strings.picking_omega_version.format(
                member=ctx.author,
                stage_type='\U000003a9',
                forbidden_versions='\n'.join(self.BANNED_ALTS)
            ))
        await self.send_start_game_message(ctx.channel, player_1, player_2,
                                           current_game_nr, suggested_stage)

    @commands.command()
    @commands.guild_only()
    @custom_checks.match_participant_only()
    async def reject(self, ctx: commands.Context):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        match = self.config.custom('match', ctx.channel.id)
        current_game_nr = await match.current_game_nr()
        current_game = self.config.custom('game', ctx.channel.id, current_game_nr)
        suggested_by_user_id = await current_game.suggested_by_user_id()
        if ctx.author.id == suggested_by_user_id:
            await ctx.send(f"{ctx.author.mention}, you can't reject your own stage suggestion.")
            return
        await current_game.suggestion_accepted.set(False)
        suggested_by = ctx.guild.get_member(suggested_by_user_id)
        await ctx.send(strings.suggestion_rejected.format(suggested_by=suggested_by))

    @commands.command(alias='win')
    @commands.guild_only()
    @custom_checks.match_participant_only()
    async def won(self, ctx: commands.Context):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        match = self.config.custom('match', ctx.channel.id)
        current_game_nr = await match.current_game_nr()
        current_game = self.config.custom('game', ctx.channel.id, current_game_nr)
        if await current_game.winner_user_id() == ctx.author.id:
            await ctx.invoke(self.bot.get_command('confirm'))
            return
        await current_game.winner_user_id.set(ctx.author.id)
        player_1_user_id = await match.player_1_user_id()
        player_2_user_id = await match.player_2_user_id()
        if player_1_user_id == ctx.author.id:
            opponent_id = player_2_user_id
        else:
            opponent_id = player_1_user_id
        await current_game.needs_confirmation_by_user_id.set(opponent_id)
        opponent = ctx.guild.get_member(opponent_id)
        await ctx.send(strings.confirm_lost.format(loser=opponent, winner=ctx.author))

    @commands.command(alias='lose')
    @commands.guild_only()
    @custom_checks.match_participant_only()
    async def lost(self, ctx: commands.Context):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        match = self.config.custom('match', ctx.channel.id)
        current_game_nr = await match.current_game_nr()
        current_game = self.config.custom('game', ctx.channel.id, current_game_nr)
        player_1_user_id = await match.player_1_user_id()
        player_2_user_id = await match.player_2_user_id()
        if player_1_user_id == ctx.author.id:
            opponent_id = player_2_user_id
        else:
            opponent_id = player_1_user_id
        if await current_game.winner_user_id() == opponent_id:
            await ctx.invoke(self.bot.get_command('confirm'))
            return
        await current_game.winner_user_id.set(opponent_id)
        await current_game.needs_confirmation_by_user_id.set(opponent_id)
        opponent = ctx.guild.get_member(opponent_id)
        await ctx.send(strings.confirm_won.format(winner=opponent))

    @commands.command()
    @commands.guild_only()
    @custom_checks.match_participant_only()
    async def confirm(self, ctx: commands.Context):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        match = self.config.custom('match', ctx.channel.id)
        current_game_nr = await match.current_game_nr()
        current_game = self.config.custom('game', ctx.channel.id, current_game_nr)
        needs_confirmation_by_user_id = await current_game.needs_confirmation_by_user_id()
        if needs_confirmation_by_user_id is None or await current_game.winner_confirmed():
            await ctx.send(f"{ctx.author.mention}, there's nothing to confirm.",
                           delete_after=30)
            return
        if ctx.author.id != needs_confirmation_by_user_id:
            await ctx.send(f"{ctx.author.mention}, you can't confirm your own score report.",
                           delete_after=30)
            return
        await current_game.winner_confirmed.set(True)
        # report score
        player_1_user_id = await match.player_1_user_id()
        player_2_user_id = await match.player_2_user_id()
        player_1 = ctx.guild.get_member(player_1_user_id)
        player_2 = ctx.guild.get_member(player_2_user_id)
        player_1_score = await match.player_1_score()
        player_2_score = await match.player_2_score()
        winner_user_id = await current_game.winner_user_id()
        winner = ctx.guild.get_member(winner_user_id)
        wins_required = await match.wins_required()
        if player_1_user_id == winner_user_id:
            loser = ctx.guild.get_member(player_2_user_id)
            player_1_score += 1
            await match.player_1_score.set(player_1_score)
        else:
            loser = ctx.guild.get_member(player_1_user_id)
            player_2_score += 1
            await match.player_2_score.set(player_2_score)

        challonge_match = await self.get_challonge_match(await match.tournament_id(), await match.match_id())  # type: challonge.Match
        if player_1_score >= wins_required or player_2_score >= wins_required:
            await self.end_match(ctx.channel, winner)
        else:
            # finalize current game
            await ctx.send(strings.who_won_current_game.format(winner=winner,
                                                               game_nr=current_game_nr))
            await challonge_match.report_live_scores(f"{player_1_score}-{player_2_score}")
            # start and store the next game
            current_game_nr += 1
            await match.current_game_nr.set(current_game_nr)
            current_game = self.config.custom('game', ctx.channel.id, current_game_nr)
            await current_game.first_to_strike_user_id.set(winner.id)
            await self.send_striking_message(ctx.channel, winner, current_game_nr, [])

    @commands.command()
    @custom_checks.to_only()
    async def setwinner(self, ctx, winner: discord.Member, *, channel: discord.TextChannel=None):
        if channel is None:
            match_channel = ctx.channel
        else:
            match_channel = channel
        match_id = await self.config.custom('match', match_channel.id).match_id()
        if match_id is None:
            raise commands.errors.BadArgument("`channel` needs to be a match channel.")
        await self.end_match(match_channel, winner, winner_set=True)
        await ctx.send("Done.")

    async def get_challonge_user_id(self, username: str):
        username = username.lower()

        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://challonge.com/users/{username}") as response:
                if response.status != 200:
                    raise commands.BadArgument("Invalid Challonge username.")
                text = await response.text()

        match = re.search(r'\?to=(\d+)', text)
        return int(match.group(1))

    async def start_doubles_match(self, guild: discord.Guild, tournament: challonge.Tournament, match: challonge.Match):
        team_1 = self.config.custom('participant_team', match.player1_id)
        team_2 = self.config.custom('participant_team', match.player2_id)
        team_1_id = await team_1.participant_id()
        team_1_player_1_user_id = await team_1.player_1_user_id()
        team_1_player_1 = guild.get_member(team_1_player_1_user_id)
        team_1_player_2_user_id = await team_1.player_2_user_id()
        team_1_player_2 = guild.get_member(team_1_player_2_user_id)
        team_2_id = await team_2.participant_id()
        team_2_player_1_user_id = await team_2.player_1_user_id()
        team_2_player_1 = guild.get_member(team_2_player_1_user_id)
        team_2_player_2_user_id = await team_2.player_2_user_id()
        team_2_player_2 = guild.get_member(team_2_player_2_user_id)
        match_channel = await self.create_doubles_match_channel(team_1_id, team_2_id,
                                                                [team_1_player_1, team_1_player_2],
                                                                [team_2_player_1, team_2_player_2])
        await self.config.member(team_1_player_1).current_match_channel_id.set(match_channel.id)
        await self.config.member(team_1_player_2).current_match_channel_id.set(match_channel.id)
        await self.config.member(team_2_player_1).current_match_channel_id.set(match_channel.id)
        await self.config.member(team_2_player_2).current_match_channel_id.set(match_channel.id)
        _match = self.config.custom('match', match_channel.id)
        # await self.store_match(tournament, match, match_channel,
        #                        player_1_member, player_2_member,
        #                        match.player1_id, match.player2_id)
        match_title = await self.get_match_title(tournament, match)
        # await self.send_match_intro(match_channel, player_1_member, player_2_member,
        #                             await _match.wins_required() * 2 - 1,
        #                             match_title)

        striking_member, striked_stages, current_game_nr = await self.get_striking_info(match_channel)
        striking_message = await self.send_striking_message(match_channel, striking_member,
                                                            current_game_nr, striked_stages)

    async def start_match(self, guild: discord.Guild, tournament: challonge.Tournament, match: challonge.Match):
        player_1_user_id = await self.config.custom('participant', match.player1_id).user_id()
        player_1_member = guild.get_member(player_1_user_id)
        player_2_user_id = await self.config.custom('participant', match.player2_id).user_id()
        player_2_member = guild.get_member(player_2_user_id)  # is None
        match_channel = await self.create_match_channel(player_1_member, player_2_member)
        await self.config.member(player_1_member).current_match_channel_id.set(match_channel.id)
        await self.config.member(player_2_member).current_match_channel_id.set(match_channel.id)
        _match = self.config.custom('match', match_channel.id)
        await self.store_match(tournament, match, match_channel,
                               player_1_member, player_2_member,
                               match.player1_id, match.player2_id)
        match_title = await self.get_match_title(tournament, match)
        await self.send_match_intro(match_channel, player_1_member, player_2_member,
                                    await _match.wins_required() * 2 - 1,
                                    match_title)

        striking_member, striked_stages, current_game_nr = await self.get_striking_info(match_channel)
        striking_message = await self.send_striking_message(match_channel, striking_member,
                                                            current_game_nr, striked_stages)

    async def end_match(self, match_channel: discord.TextChannel, winner: discord.Member, *,
                        forfeited: bool=False, winner_set: bool=False, disqualified: bool=False):
        if forfeited and winner_set or winner_set and disqualified or disqualified and forfeited:
            raise TypeError("Only one of forfeited, winner_set and disqualified can be True.")
        match = self.config.custom('match', match_channel.id)
        if await match.winner_user_id() is not None and not (disqualified or winner_set):
            await match_channel.send("A winner for this match has already been determined.")
            return
        await match.winner_user_id.set(winner.id)
        player_1_user_id = await match.player_1_user_id()
        player_2_user_id = await match.player_2_user_id()
        player_1 = match_channel.guild.get_member(player_1_user_id)
        player_2 = match_channel.guild.get_member(player_2_user_id)
        player_1_score = await match.player_1_score()
        player_2_score = await match.player_2_score()
        player_1_elo = await self.config.user(player_1).elo()
        player_2_elo = await self.config.user(player_2).elo()
        current_game_nr = await match.current_game_nr()
        if player_1_user_id == winner.id:
            loser = match_channel.guild.get_member(player_2_user_id)
        else:
            loser = match_channel.guild.get_member(player_1_user_id)
        challonge_match = await self.get_challonge_match(await match.tournament_id(), await match.match_id())  # type: challonge.Match
        tournament = await self.get_challonge_tournament(await match.tournament_id())
        winner_participant_id = await self.config.member(winner).challonge_id()
        winner_participant = await tournament.get_participant(winner_participant_id)
        loser_participant_id = await self.config.member(loser).challonge_id()
        loser_participant = await tournament.get_participant(loser_participant_id)
        await challonge_match.report_winner(winner_participant,
                                            f"{player_1_score}-{player_2_score}")
        winner_match_count = await self.config.custom('participant', winner_participant_id).match_count() + 1
        await self.config.custom('participant', winner_participant_id).match_count.set(winner_match_count)
        loser_match_count = await self.config.custom('participant', loser_participant_id).match_count() + 1
        await self.config.custom('participant', loser_participant_id).match_count.set(loser_match_count)

        if forfeited:
            await match_channel.send(strings.forfeited_match.format(winner=winner,
                                                                    loser=loser))
            forfeit_count = await self.config.custom('participant', loser_participant_id).forfeit_count() + 1
            await self.config.custom('participant', loser_participant_id).forfeit_count.set(forfeit_count)
            if forfeit_count == loser_match_count == 2 and player_1_score + player_2_score == 0:
                await tournament.remove_participant(loser_participant)
            if player_1 == loser:
                player_1_score, player_2_score = 0, 2
            else:
                player_1_score, player_2_score = 2, 0
        elif winner_set:
            await match_channel.send(strings.who_won_match.format(winner=winner))
            forfeit_count = await self.config.custom('participant', loser_participant_id).forfeit_count() + 1
            await self.config.custom('participant', loser_participant_id).forfeit_count.set(forfeit_count)
            if forfeit_count == loser_match_count == 2 and player_1_score + player_2_score == 0:
                await tournament.remove_participant(loser_participant)
            if player_1 == loser:
                player_1_score, player_2_score = 0, 2
            else:
                player_1_score, player_2_score = 2, 0
        elif disqualified:
            await match_channel.send(strings.disqualified_win.format(winner=winner,
                                                                     disqualified=loser))
            if player_1 == loser:
                player_1_score, player_2_score = 0, 2
            else:
                player_1_score, player_2_score = 2, 0
        else:
            await match_channel.send(strings.who_won_final_game.format(winner=winner,
                                                                       game_nr=current_game_nr,
                                                                       player_1_score=player_1_score,
                                                                       player_2_score=player_2_score))

        if not tournament.private:
            player_1_elo, player_2_elo = self.calculate_elo(player_1_elo, player_2_elo, player_1_score, player_2_score)
            await self.config.user(player_1).elo.set(player_1_elo)
            await self.config.user(player_2).elo.set(player_2_elo)
        # wait a minute, then close the match channel and start the next match if available
        winners_next_match = await winner_participant.get_next_match()  # type: challonge.Match
        start_winners_next_match = (winners_next_match is not None
                                    and challonge.MatchState(winners_next_match.state) == challonge.MatchState.open_)
        losers_next_match = await loser_participant.get_next_match() if loser_participant is not None else None  # type: challonge.Match
        start_losers_next_match = (not disqualified
                                   and losers_next_match is not None
                                   and challonge.MatchState(losers_next_match.state) == challonge.MatchState.open_
                                   and winners_next_match.id != losers_next_match.id)

        await asyncio.sleep(60)
        await match_channel.delete(reason=f"Match between {player_1} and {player_2} is over.")
        await self.config.member(player_1).current_match_channel_id.clear()
        await self.config.member(player_2).current_match_channel_id.clear()
        if start_winners_next_match:
            await self.start_match(match_channel.guild, tournament, winners_next_match)
        if start_losers_next_match:
            await self.start_match(match_channel.guild, tournament, losers_next_match)
        # end tournament if no more matches are to be played
        if (
            not (start_winners_next_match or start_losers_next_match)
            or (tournament.tournament_type == challonge.TournamentType.double_elimination.value
                and winners_next_match.round == challonge_match.round
                and winner_participant_id == challonge_match.player1_id)  # Challonge is buggy as heck
        ):
            matches = await tournament.get_matches(force_update=True)
            matches = sorted(matches, key=lambda m: m.id, reverse=True)
            last_match = matches[0]
            second_to_last_match = matches[1]
            if (
                (
                    challonge_match.id == second_to_last_match.id
                    and winner_participant_id == second_to_last_match.player1_id
                )
                or challonge_match.id == last_match.id
            ):
                tournament_channel_id = await self.config.custom('tournament', tournament.id).channel_id()
                tournament_channel = match_channel.guild.get_channel(tournament_channel_id)
                await self.end_tournament(tournament_channel)

    async def end_tournament(self, tournament_channel: discord.TextChannel):
        tournament_id = await self.config.custom('tournament', tournament_channel.id).tournament_id()
        tournament = await self.get_challonge_tournament(tournament_id)
        try:
            await tournament.finalize()
        except challonge.APIException:  # either Challonge or the library is broken
            pass
        participants = await tournament.get_participants(force_update=True)
        tournament.participants = participants  # library br0ken
        # TODO try without the above line
        ranking = await self.get_final_ranking(tournament)  # type: dict
        # TODO file_path = await self.create_ranking_image()
        async with tournament_channel.typing():
            factions_results = await self.process_ranking(ranking)
            top_3 = {}
            four_to_eight = {}
            for rank, participant in ranking.items():  # participant is a list because teams exist
                if rank <= 3:
                    top_3[rank] = ', '.join([p.name for p in participant])
                elif rank <= 8:
                    four_to_eight[rank] = ', '.join([p.name for p in participant])
                else:
                    break
            top_3_formatted = '\n'.join([f"**{rank}: {p}**" for rank, p in top_3.items()])
            four_to_eight_formatted = '\n'.join([f"{rank}: {p}" for rank, p in four_to_eight.items()])
            top_8_formatted = '\n'.join((top_3_formatted, four_to_eight_formatted))

        if factions_results:
            await tournament_channel.send(strings.factions_tournament_end.format(
                name=tournament.name,
                top_8=top_8_formatted,
                challonge_url=tournament.full_challonge_url,
                **factions_results
            ))
        else:
            await tournament_channel.send(strings.tournament_end.format(
                name=tournament.name,
                top_8=top_8_formatted,
                challonge_url=tournament.full_challonge_url
            ))
        await asyncio.sleep(600)
        # TODO remove participant roles and permission override
        participant_role_id = await self.config.guild(tournament_channel.guild).participant_role_id()
        participant_role = tournament_channel.guild.get_role(participant_role_id)
        await tournament_channel.set_permissions(participant_role, overwrite=None)
        await tournament_channel.send("This channel is now read-only.")
        for participant in tournament.participants:
            user_id = await self.config.custom('participant', participant.id).user_id()
            member = tournament_channel.guild.get_member(user_id)
            try:
                await member.remove_roles(participant_role)
            except discord.Forbidden:
                continue

    @staticmethod
    async def get_final_ranking(tournament: challonge.Tournament):
        if tournament.state != challonge.TournamentState.complete.value:
            return None
        ranking = {}
        for p in tournament.participants:
            if p.final_rank is not None:  # and not p.removed:  # readd when DQing works
                if p.final_rank in ranking:
                    ranking[p.final_rank].append(p)
                else:
                    ranking[p.final_rank] = [p]

        return OrderedDict(sorted(ranking.items(), key=lambda t: t[0]))

    async def __calculate_ranking(self, ranking: dict):
        calculated_ranking = defaultdict(lambda: [])
        participants_lists = list(ranking.values())
        participants = [item for sublist in participants_lists for item in sublist]
        ranks = list(ranking.keys())
        guild_id = await self.config.custom('participant', ranking[1][0].id).guild_id()
        guild = self.bot.get_guild(guild_id)
        factions_cog = self.bot.get_cog('Factions')
        faction_numbers = {
            'light': 0,
            'darkness': 0,
            'subspace': 0
        }
        if guild_id == factions_cog.GUILD_ID:
            for participant in participants:
                user_id = await self.config.custom('participant', participant.id).user_id()
                member = guild.get_member(user_id)
                if member is None:
                    continue
                _faction = await factions_cog.config.user(member).faction()
                if _faction is None:
                    print(str(member))
                    continue
                faction_numbers[await factions_cog.config.user(member).faction()] += 1
        max_faction_number = max(faction_numbers.values())

        def calculate_credits(_rank, _elo_diff):
            if _elo_diff > 0:
                return (len(participants) - (_rank - 1)) * 20 + _elo_diff * 5 + 100 + random.randrange(0, 20)
            return (len(participants) - (_rank - 1)) * 20 + 100 + random.randrange(0, 20)

        def calculate_faction_points(_rank, _faction):
            faction_number = faction_numbers[_faction]
            return (
                round(
                    math.sqrt(
                        (len(ranks) - ranks.index(_rank)) * len(ranks)
                    ) * ((max_faction_number / faction_number - 1) * 0.6 + 1) * 2
                ) + round(
                len(participants) / 20
            )
            )

        light_points = 0
        darkness_points = 0
        subspace_points = 0
        for rank, _participants in ranking.items():
            for participant in _participants:  # type: challonge.Participant
                user_id = await self.config.custom('participant', participant.id).user_id()
                member = guild.get_member(user_id)
                if member is None:
                    continue
                starting_elo = await self.config.custom('participant', participant.id).starting_elo()
                new_elo = await self.config.user(member).elo()
                elo_diff = new_elo - starting_elo
                elo_change = f"+{elo_diff}" if elo_diff >= 0 else str(elo_diff)
                faction = await factions_cog.config.user(member).faction()
                if guild_id == factions_cog.GUILD_ID and faction is not None:
                    faction_points = calculate_faction_points(rank, faction)
                    creds = calculate_credits(rank, elo_diff)
                    faction_points_change = f"+{faction_points}"
                    new_faction_points = 0
                    credits_change = f"+{creds}"
                    balance = await bank.get_balance(member) + creds
                    if faction == 'light':
                        light_points += faction_points
                        current_faction_points = 0
                        new_faction_points = current_faction_points + faction_points
                        await factions_cog.config.user(member).light_points.set(new_faction_points)
                        await factions_cog.config.user(member).darkness_points.set(0)
                        await factions_cog.config.user(member).subspace_points.set(0)
                    elif faction == 'darkness':
                        darkness_points += faction_points
                        current_faction_points = 0
                        new_faction_points = current_faction_points + faction_points
                        await factions_cog.config.user(member).light_points.set(0)
                        await factions_cog.config.user(member).darkness_points.set(new_faction_points)
                        await factions_cog.config.user(member).subspace_points.set(0)
                    elif faction == 'subspace':
                        subspace_points += faction_points
                        current_faction_points = 0
                        new_faction_points = current_faction_points + faction_points
                        await factions_cog.config.user(member).light_points.set(0)
                        await factions_cog.config.user(member).darkness_points.set(0)
                        await factions_cog.config.user(member).subspace_points.set(new_faction_points)
                    # try:
                    await bank.set_balance(member, creds)
                    # except errors.BalanceTooHigh as e:
                    # await member.send(str(e))
                    calculated_ranking[rank].append(
                        f"**{member.name}** ({faction.capitalize()}): {credits_change} credits, {faction_points_change}"
                        f" {faction} points, {elo_change} ELO"
                    )
                else:
                    pass
        return calculated_ranking

    async def process_ranking(self, ranking: dict):
        participants = [item for sublist in list(ranking.values()) for item in sublist]
        ranks = list(ranking.keys())
        guild_id = await self.config.custom('participant', ranking[1][0].id).guild_id()
        guild = self.bot.get_guild(guild_id)
        factions_cog = self.bot.get_cog('Factions')
        faction_numbers = {
            'light': 0,
            'darkness': 0,
            'subspace': 0
        }
        if guild_id == factions_cog.GUILD_ID:
            for participant in participants:
                user_id = await self.config.custom('participant', participant.id).user_id()
                member = guild.get_member(user_id)
                if member is None:
                    continue
                _faction = await factions_cog.config.user(member).faction()
                if _faction is None:
                    print(str(member))
                    continue
                faction_numbers[await factions_cog.config.user(member).faction()] += 1
        max_faction_number = max(faction_numbers.values())

        def calculate_credits(_rank, _elo_diff):
            if _elo_diff > 0:
                return (len(participants) - (_rank - 1)) * 20 + _elo_diff * 5 + 100 + random.randrange(0, 20)
            return (len(participants) - (_rank - 1)) * 20 + 100 + random.randrange(0, 20)

        def calculate_faction_points(_rank, _faction):
            faction_number = faction_numbers[_faction]
            return (
                round(
                    math.sqrt(
                        (len(ranks) - ranks.index(_rank)) * len(ranks)
                    ) * ((max_faction_number / faction_number - 1) + 1) * 2
                ) + round(
                len(participants) / 20
            )
            )

        tournament_id = ranking[1][0].tournament_id
        tournament = await self.get_challonge_tournament(tournament_id)
        currency = await bank.get_currency_name(guild)
        light_points = 0
        darkness_points = 0
        subspace_points = 0
        for rank, _participants in ranking.items():
            for participant in _participants:  # type: challonge.Participant
                user_id = await self.config.custom('participant', participant.id).user_id()
                member = guild.get_member(user_id)
                if member is None:
                    continue
                starting_elo = await self.config.custom('participant', participant.id).starting_elo()
                new_elo = await self.config.user(member).elo()
                elo_diff = new_elo - starting_elo
                elo_change = f"+{elo_diff}" if elo_diff >= 0 else str(elo_diff)
                faction = await factions_cog.config.user(member).faction()
                if guild_id == factions_cog.GUILD_ID and faction is not None:
                    faction_points = abs(calculate_faction_points(rank, faction))
                    creds = abs(calculate_credits(rank, elo_diff))
                    faction_points_change = f"+{faction_points}"
                    new_faction_points = 0
                    credits_change = f"+{creds}"
                    balance = await bank.get_balance(member) + creds
                    if faction == 'light':
                        light_points += faction_points
                        current_faction_points = 0
                        new_faction_points = current_faction_points + faction_points
                        await factions_cog.config.user(member).light_points.set(new_faction_points)
                    elif faction == 'darkness':
                        darkness_points += faction_points
                        current_faction_points = 0
                        new_faction_points = current_faction_points + faction_points
                        await factions_cog.config.user(member).darkness_points.set(new_faction_points)
                    elif faction == 'subspace':
                        subspace_points += faction_points
                        current_faction_points = 0
                        new_faction_points = current_faction_points + faction_points
                        await factions_cog.config.user(member).light_points.set(new_faction_points)
                    # try:
                    await bank.deposit_credits(member, creds)
                    # except errors.BalanceTooHigh as e:
                    # await member.send(str(e))
                    self.bot.loop.create_task(member.send(strings.participant_faction_results.format(
                        tournament=tournament,
                        rank=rank,
                        faction=faction.capitalize(),
                        faction_points_change=faction_points_change,
                        total_faction_points=new_faction_points,
                        currency=currency,
                        credits_change=credits_change,
                        total_balance=balance,
                        elo_change=elo_change,
                        new_elo=new_elo
                    )))
                else:
                    self.bot.loop.create_task(member.send(strings.participant_results.format(
                        tournament=tournament,
                        rank=rank,
                        elo_change=elo_change,
                        new_elo=new_elo
                    )))
        if guild_id == factions_cog.GUILD_ID:
            return {
                'light': light_points,
                'darkness': darkness_points,
                'subspace': subspace_points
            }
        return {}

    @staticmethod
    def calculate_elo(elo_1, elo_2, points_1, points_2):
        if points_1 + points_2 == 0:
            return elo_1, elo_2
        score = points_1 / (points_1 + points_2)
        elo_difference = elo_2 - elo_1
        odds = 1 / (1 + 10 ** (elo_difference / 400))
        odd_difference_1 = score - odds
        odd_difference_2 = 1 - score - (1 - odds)
        k_factor_1 = 32 if elo_1 <= 2100 else 24 if elo_1 <= 2400 else 16
        k_factor_2 = 32 if elo_2 <= 2100 else 24 if elo_2 <= 2400 else 16
        new_elo_1 = round(elo_1 + k_factor_1 * odd_difference_1)
        new_elo_2 = round(elo_2 + k_factor_2 * odd_difference_2)
        return new_elo_1, new_elo_2

    async def create_match_channel(self, player_1, player_2):
        guild = player_1.guild
        matches_category_id = await self.config.guild(guild).matches_category_id()
        if matches_category_id is None:
            matchmaking_cog = self.bot.get_cog('MatchMaking')
            if matchmaking_cog is not None:
                matches_category_id = await matchmaking_cog.config.guild(guild).category_id()
            elif matchmaking_cog is None or matches_category_id is None:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, connect=True,
                                                          manage_messages=True, manage_channels=True)
                }
                category = await guild.create_category_channel(name="Matches",
                                                               overwrites=overwrites,
                                                               reason="Creating category necessary "
                                                                      "for tournament matches")
                await self.config.guild(guild).matches_category_id.set(category.id)
                matches_category_id = category.id
                if matchmaking_cog is not None:
                    await matchmaking_cog.config.guild(guild).category_id.set(matches_category_id)

        category = guild.get_channel(matches_category_id)
        organizer_role_id = await self.config.guild(guild).organizer_role_id()
        organizer_role = guild.get_role(organizer_role_id)
        streamer_role_id = await self.config.guild(guild).streamer_role_id()
        streamer_role = guild.get_role(streamer_role_id)
        name = '\U00002009\U00002009vs\U00002009\U00002009'.join((player_1.name, player_2.name))
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True,
                                                  manage_channels=True),
            player_1: discord.PermissionOverwrite(read_messages=True),
            player_2: discord.PermissionOverwrite(read_messages=True)
        }
        if organizer_role is not None:
            overwrites[organizer_role] = discord.PermissionOverwrite(read_messages=True, manage_messages=True)
        if streamer_role is not None:
            overwrites[streamer_role] = discord.PermissionOverwrite(read_messages=True)
        channel = await guild.create_text_channel(name, overwrites=overwrites, category=category,
                                                  reason=f"Creating match channel for "
                                                         f"{player_1} and "
                                                         f"{player_2}")
        return channel

    async def create_doubles_match_channel(self, name_1: str, name_2: str, team_1: List[discord.Member],
                                           team_2: List[discord.Member]):
        guild = team_1[0].guild

        matches_category_id = await self.config.guild(guild).matches_category_id()
        if matches_category_id is None:
            matchmaking_cog = self.bot.get_cog('MatchMaking')
            if matchmaking_cog is not None:
                matches_category_id = await matchmaking_cog.config.guild(guild).category_id()
            elif matchmaking_cog is None or matches_category_id is None:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, connect=True,
                                                          manage_messages=True, manage_channels=True)
                }
                category = await guild.create_category_channel(name="Matches",
                                                               overwrites=overwrites,
                                                               reason="Creating category necessary "
                                                                      "for tournament matches")
                await self.config.guild(guild).matches_category_id.set(category.id)
                matches_category_id = category.id
                if matchmaking_cog is not None:
                    await matchmaking_cog.config.guild(guild).category_id.set(matches_category_id)

        category = guild.get_channel(matches_category_id)
        organizer_role_id = await self.config.guild(guild).organizer_role_id()
        organizer_role = guild.get_role(organizer_role_id)
        streamer_role_id = await self.config.guild(guild).streamer_role_id()
        streamer_role = guild.get_role(streamer_role_id)
        name = '\U00002009\U00002009vs\U00002009\U00002009'.join((name_1, name_2))
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True,
                                                  manage_channels=True),
            team_1[0]: discord.PermissionOverwrite(read_messages=True),
            team_1[1]: discord.PermissionOverwrite(read_messages=True),
            team_2[0]: discord.PermissionOverwrite(read_messages=True),
            team_2[1]: discord.PermissionOverwrite(read_messages=True)
        }
        if organizer_role is not None:
            overwrites[organizer_role] = discord.PermissionOverwrite(read_messages=True, manage_messages=True)
        if streamer_role is not None:
            overwrites[streamer_role] = discord.PermissionOverwrite(read_messages=True)
        channel = await guild.create_text_channel(name, overwrites=overwrites, category=category,
                                                  reason=f"Creating match channel for "
                                                         f"team {name_1} and "
                                                         f"team {name_2}")
        return channel

    async def get_match_title(self, tournament: challonge.Tournament, match: challonge.Match):
        if tournament.tournament_type not in (
            challonge.TournamentType.double_elimination.value,
            challonge.TournamentType.single_elimination.value
        ):
            return "Match"
        if tournament.tournament_type == challonge.TournamentType.double_elimination.value:
            matches = await tournament.get_matches()
            max_round = max(matches, key=lambda m: m.round).round
            min_round = min(matches, key=lambda m: m.round).round
            winners_quarterfinals_round = max_round - 3
            winners_semifinals_round = max_round - 2
            winners_finals_round = max_round - 1
            losers_quarterfinals_round = min_round + 2
            losers_semifinals_round = min_round + 1
            losers_finals_round = min_round
            grand_finals_round = max_round

            if 0 < winners_quarterfinals_round == match.round:
                return "Winners Quarterfinals"
            if 0 < winners_semifinals_round == match.round:
                return "Winners Semifinals"
            if 0 < winners_finals_round == match.round:
                return "Winners Finals"
            if 0 > losers_quarterfinals_round == match.round:
                return "Losers Quarterfinals"
            if 0 > losers_semifinals_round == match.round:
                return "Losers Semifinals"
            if 0 > losers_finals_round == match.round:
                return "Losers Finals"
            if 0 < grand_finals_round == match.round:
                return "Grand Finals"
            if match.round > 0:
                return f"Round {match.round}"
            if match.round < 0:
                return f"Losers Round {abs(match.round)}"
        return "Match"

    async def store_match(self, tournament: challonge.Tournament, challonge_match: challonge.Match,
                          channel: discord.TextChannel,
                          player_1: discord.Member, player_2: discord.Member,
                          participant_1_id, participant_2_id):
        match = self.config.custom('match', channel.id)
        await match.match_id.set(challonge_match.id)
        await match.channel_id.set(channel.id)
        await match.guild_id.set(channel.guild.id)
        await match.tournament_id.set(tournament.id)
        await match.player_1_user_id.set(player_1.id)
        await match.player_2_user_id.set(player_2.id)
        await match.player_1_challonge_id.set(participant_1_id)
        await match.player_2_challonge_id.set(participant_2_id)

        wins_required = 2
        matches = await tournament.get_matches()
        max_round = max(matches, key=lambda m: m.round).round
        min_round = min(matches, key=lambda m: m.round).round
        if challonge_match.round in (max_round, max_round - 1, min_round):
            wins_required = 3
        await match.wins_required.set(wins_required)
        # also store the first game
        game_1 = self.config.custom('game', channel.id, 1)
        await game_1.match_id.set(challonge_match.id)
        await game_1.game_number.set(1)
        await game_1.first_to_strike_user_id.set(
            random.choice((player_1.id, player_2.id))
        )

    async def store_doubles_match(self, tournament: challonge.Tournament, challonge_match: challonge.Match,
                                  channel: discord.TextChannel,
                                  player_1: discord.Member, player_2: discord.Member,
                                  participant_1_id, participant_2_id):
        match = self.config.custom('match', channel.id)
        await match.match_id.set(challonge_match.id)
        await match.channel_id.set(channel.id)
        await match.guild_id.set(channel.guild.id)
        await match.tournament_id.set(tournament.id)
        await match.player_1_user_id.set(player_1.id)
        await match.player_2_user_id.set(player_2.id)
        await match.player_1_challonge_id.set(participant_1_id)
        await match.player_2_challonge_id.set(participant_2_id)

        wins_required = 2
        matches = await tournament.get_matches()
        max_round = max(matches, key=lambda m: m.round).round
        min_round = min(matches, key=lambda m: m.round).round
        if challonge_match.round in (max_round, max_round - 1, min_round):
            wins_required = 3
        await match.wins_required.set(wins_required)
        # also store the first game
        game_1 = self.config.custom('game', channel.id, 1)
        await game_1.match_id.set(challonge_match.id)
        await game_1.game_number.set(1)
        await game_1.first_to_strike_user_id.set(
            random.choice((player_1.id, player_2.id))
        )

    async def initialize_challonge_user(self):
        challonge_username = await self.config.challonge_username()
        challonge_api_key = await self.config.challonge_api_key()
        if challonge_username is None or challonge_api_key is None:
            return
        self.challonge_user = await challonge.get_user(challonge_username, challonge_api_key)

    async def set_challonge_credentials(self, username: str, api_key: str):
        await self.config.challonge_username.set(username)
        await self.config.challonge_api_key.set(api_key)

    async def save_tournament(self, signup_message: discord.Message, tournament: challonge.Tournament):
        channel = signup_message.channel
        await self.config.custom('tournament', channel.id).set({
            'channel_id': channel.id,
            'tournament_id': tournament.id,
            'guild_id': channel.guild.id,
            'signup_message_id': signup_message.id,
            'checkin_message_id': None
        })
        await self.config.custom('tournament', tournament.id).set({
            'channel_id': channel.id,
            'tournament_id': tournament.id,
            'guild_id': channel.guild.id,
            'signup_message_id': signup_message.id,
            'checkin_message_id': None
        })
        self.cached_tournaments[tournament.id] = tournament

    async def get_challonge_tournament(self, challonge_id) -> challonge.Tournament:
        tournament = self.cached_tournaments.get(challonge_id)
        if tournament is None:
            tournament = await self.challonge_user.get_tournament(challonge_id)
            self.cached_tournaments[challonge_id] = tournament
        return tournament

    async def get_challonge_participant(self, tournament_id, challonge_id) -> challonge.Participant:
        participant = self.cached_participants.get(challonge_id)
        if participant is None:
            tournament = await self.get_challonge_tournament(tournament_id)
            participant = await tournament.get_participant(challonge_id)
            self.cached_tournaments[challonge_id] = participant
        return participant

    async def get_challonge_match(self, tournament_id, challonge_id):
        match = self.cached_matches.get(challonge_id)
        if match is None:
            tournament = await self.get_challonge_tournament(tournament_id)
            match = await tournament.get_match(challonge_id)
            self.cached_tournaments[challonge_id] = match
        return match

    async def send_signup_message(self, channel: discord.TextChannel, **format_kwargs):
        is_doubles = await self.config.custom("tournament", channel.id).doubles()
        if is_doubles:
            message = await channel.send(strings.doubles_signup_message.format(**format_kwargs))
        else:
            message = await channel.send(strings.signup_message.format(**format_kwargs))
        await message.add_reaction('\U00002705')  # white_check_mark
        return message

    async def signup(self, tournament: challonge.Tournament, member: discord.Member):
        factions_cog = self.bot.get_cog('Factions')
        if member.guild.id == factions_cog.GUILD_ID:
            faction = await factions_cog.config.user(member).faction()
            if faction is None:
                display_name = member.name
            else:
                display_name = f"[{faction.upper()}] {member.name}"
        else:
            display_name = member.name
        participant = await tournament.add_participant(display_name=display_name)
        await self.config.member(member).challonge_id.set(participant.id)
        await self.config.custom('participant', participant.id).challonge_id.set(participant.id)
        await self.config.custom('participant', participant.id).tournament_id.set(tournament.id)
        await self.config.custom('participant', participant.id).user_id.set(member.id)
        await self.config.custom('participant', participant.id).guild_id.set(member.guild.id)
        self.cached_participants[participant.id] = participant

    async def signup_team_member(self, tournament: challonge.Tournament, member: discord.Member):
        current_team_member_id = await self.config.member(member).current_team_member_id()
        (player_1, player_2) = ((member, current_team_member_id)
                                if member.id < current_team_member_id
                                else (current_team_member_id, member))
        team_name = await self.config.custom("team", player_1.id, player_2.id).name()
        participant = await tournament.add_participant(display_name=team_name)
        participant_team = self.config.custom("participant_team", participant.id)
        await self.config.custom("team", player_1.id, player_2.id).current_participant_id.set(participant.id)
        await self.config.custom("team", player_1.id, player_2.id).current_tournament_id.set(tournament.id)
        await participant_team.challonge_id.set(participant.id)
        await participant_team.tournament_id.set(tournament.id)
        await self.config.member(player_1).current_doubles_tournament.set(tournament.id)
        await participant_team.guild_id.set(member.guild.id)
        await participant_team.player_1_user_id.set(player_1.id)
        await participant_team.player_2_user_id.set(player_2.id)

    async def send_checkin_message(self, channel: discord.TextChannel, participant_role: discord.Role):
        is_doubles = await self.config.custom("tournament", channel.id).doubles()
        if is_doubles:
            message = await channel.send(strings.doubles_checkin_message.format(role=participant_role))
        else:
            message = await channel.send(strings.checkin_message.format(role=participant_role))
        await message.add_reaction('\U00002705')  # white_check_mark
        return message

    async def checkin(self, tournament: challonge.Tournament, member: discord.Member):
        participant_id = await self.config.member(member).challonge_id()
        participant = await tournament.get_participant(participant_id, force_update=True)
        if participant is None:
            await member.send("You have to sign up before you can check in.")
            return
        if participant.checked_in:
            return
        await participant.check_in()

    async def checkin_team_member(self, tournament: challonge.Tournament, member: discord.Member):
        current_team_member_id = await self.config.member(member).current_team_member_id()
        (player_1, player_2) = ((member, current_team_member_id)
                                if member.id < current_team_member_id
                                else (current_team_member_id, member))
        participant_id = await self.config.custom("team", player_1.id, player_2.id).participant_id()
        participant = await tournament.get_participant(participant_id)
        participant_team = self.config.custom("participant_team", participant.id)
        if member == player_1:
            await participant_team.player_1_checked_in.set(True)
            checked_in = await participant_team.player_2_checked_in()
        else:
            await participant_team.player_2_checked_in.set(True)
            checked_in = await participant_team.player_1_checked_in()
        if checked_in:
            await participant.check_in()

    async def send_match_intro(self, channel: discord.TextChannel, player_1: discord.User, player_2: discord.User,
                               best_of_number: int=3, match_title="Match"):
        factions_cog = self.bot.get_cog('Factions')
        if channel.guild.id == factions_cog.GUILD_ID:
            player_1_faction = await factions_cog.config.user(player_1).faction()
            player_1_faction = player_1_faction.capitalize()
            player_2_faction = await factions_cog.config.user(player_2).faction()
            player_2_faction = player_2_faction.capitalize()
            await channel.send(strings.match_intro_factions.format(match_title=match_title,
                                                                   player_1=player_1, player_2=player_2,
                                                                   player_1_faction=player_1_faction,
                                                                   player_2_faction=player_2_faction,
                                                                   best_of_number=best_of_number))
        else:
            await channel.send(strings.match_intro.format(match_title=match_title,
                                                          player_1=player_1, player_2=player_2,
                                                          best_of_number=best_of_number))

    async def get_striking_member_id(self, match_channel, striked_stages=None):
        match = self.config.custom('match', match_channel.id)
        current_game_nr = await match.current_game_nr()
        current_game = self.config.custom('game', match_channel.id, current_game_nr)
        if striked_stages is None:
            striked_stages = await current_game.striked_stages()
        first_to_strike_user_id = await current_game.first_to_strike_user_id()

        if len(striked_stages) == 0:  # if this is the first striking
            return first_to_strike_user_id
        elif current_game_nr == 1 and len(striked_stages) in (1, 2, 3):
            player_1_user_id = await match.player_1_user_id()
            player_2_user_id = await match.player_2_user_id()
            if len(striked_stages) in (1, 2):  # second or third striking
                if player_1_user_id == first_to_strike_user_id:
                    return player_2_user_id
                else:
                    return player_1_user_id
            else:  # fourth striking
                if player_1_user_id == first_to_strike_user_id:
                    return player_1_user_id
                else:
                    return player_2_user_id
        elif len(striked_stages) == 1:
            return first_to_strike_user_id
        else:
            return None

    async def get_picking_member_id(self, match_channel):
        match = self.config.custom('match', match_channel.id)
        current_game_nr = await match.current_game_nr()
        current_game = self.config.custom('game', match_channel.id, current_game_nr)
        striked_stages = await current_game.striked_stages()
        if (
            (current_game_nr == 1 and len(striked_stages) != 3)
            or (current_game_nr != 1 and len(striked_stages) != 2)
        ):
            return None
        first_to_strike_user_id = await current_game.first_to_strike_user_id()
        player_1_user_id = await match.player_1_user_id()
        player_2_user_id = await match.player_2_user_id()
        if player_1_user_id == first_to_strike_user_id:
            return player_2_user_id
        else:
            return player_1_user_id

    async def get_striking_info(self, match_channel: discord.TextChannel):
        # who needs to strike?
        match = self.config.custom('match', match_channel.id)
        current_game_nr = await match.current_game_nr()
        current_game = self.config.custom('game', match_channel.id, current_game_nr)
        striked_stages = await current_game.striked_stages()
        striking_member_id = await self.get_striking_member_id(match_channel, striked_stages)
        striking_member = match_channel.guild.get_member(striking_member_id)
        return striking_member, striked_stages, current_game_nr

    async def get_formatted_stage_list(self, current_game_nr, striked_stages):
        if current_game_nr == 1:
            all_stages = self.STARTER_STAGES
        else:
            all_stages = self.ALL_STAGES
        stages = [f"{self.NUMBER_EMOJIS[number + 1]} **{stage}**"
                  if number not in striked_stages
                  else f"{self.NUMBER_EMOJIS[number + 1]} ~~{stage}~~"
                  for number, stage
                  in enumerate(all_stages)]
        return "\n".join(stages)

    async def send_striking_message(self, match_channel: discord.TextChannel, striking_member: discord.Member,
                                    current_game_nr: int, striked_stages: list):
        current_game = self.config.custom('game', match_channel.id, current_game_nr)
        stages = await self.get_formatted_stage_list(current_game_nr, striked_stages)
        if len(striked_stages) == 0:
            message = await match_channel.send(strings.first_striking.format(
                member=striking_member, stages=stages
            ))
            await current_game.striking_message_id.set(message.id)
            return message
        else:
            if len(striked_stages) == 1:
                if current_game_nr == 1:
                    message_content = strings.second_striking.format(
                        member=striking_member, stages=stages
                    )
                else:
                    message_content = strings.second_striking_second_game.format(
                        member=striking_member, stages=stages
                    )
            elif len(striked_stages) == 2:
                message_content = strings.third_striking.format(
                    member=striking_member, stages=stages
                )
            elif len(striked_stages) == 3:
                message_content = strings.fourth_striking.format(
                    member=striking_member, stages=stages
                )
            else:
                await match_channel.send("Something went wrong, pinging <@506153885279191050>.")
                raise commands.CommandError

            striking_message_id = await current_game.striking_message_id()
            async for last_message in match_channel.history(limit=1):
                if striking_message_id is not None and last_message.id == striking_message_id:
                    await last_message.edit(content=message_content)
                    striking_message = last_message
                else:
                    if striking_message_id is not None:
                        old_striking_message = await match_channel.fetch_message(striking_message_id)
                        try:
                            await old_striking_message.delete()
                        except discord.NotFound:
                            pass
                    striking_message = await match_channel.send(message_content)
                    await current_game.striking_message_id.set(striking_message.id)
                return striking_message

    async def send_picking_stage_message(self, match_channel: discord.TextChannel, picking_member: discord.Member,
                                         current_game_nr: int, striked_stages: tuple):
        stages = await self.get_formatted_stage_list(current_game_nr, striked_stages)
        await match_channel.send(strings.picking_stage.format(
            member=picking_member, stages=stages
        ))

    async def send_start_game_message(self, match_channel: discord.TextChannel,
                                      player_1: discord.Member, player_2: discord.Member,
                                      current_game_nr: int, stage_id: int):
        stage = self.ALL_STAGES[stage_id]
        if current_game_nr == 1:
            message_content = strings.start_first_game.format(player_1=player_1, player_2=player_2,
                                                              stage=stage)
        else:
            message_content = strings.start_game.format(current_game_nr=current_game_nr,
                                                        player_1=player_1, player_2=player_2,
                                                        stage=stage)
        await match_channel.send(message_content)
