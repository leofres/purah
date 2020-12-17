import datetime

import challonge

import discord
from discord.ext.commands import BadArgument, CheckFailure, TextChannelConverter

import hero
from hero import checks, models

from .. import checks as ssbu_checks, models as ssbu_models, strings
from ..controller import SsbuController
from ..models import SsbuSettings
from ..stages import Stage


class Tournaments(hero.Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core.loop.create_task(self.ctl.initialize_challonge_user())

    core: hero.Core
    ctl: SsbuController
    settings: SsbuSettings

    MAX_PARTICIPANTS = 512

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
    @ssbu_checks.match_participant_only()
    async def strike(self, ctx, stage: Stage):
        # TODO check if match channel, then
        # check if stage can be striked, then
        # add striked stage to Match's striked stages and
        # edit the striking message accordingly
        pass

    @hero.command()
    @checks.is_owner()
    async def gettournaments(self, ctx):
        tournaments = await self.ctl.challonge_user.get_tournaments(force_update=True)
        text = ""
        for tournament in tournaments:
            text += (f"{tournament.name} ({tournament.id}): \n"
                     f"    Open signup: {tournament.open_signup}\n"
                     f"    Participants: {tournament.participants_count}\n"
                     f"    Private: {tournament.private}\n"
                     f"    Start at: {tournament.start_at}\n"
                     f"    State: {tournament.state}\n"
                     f"    URL: {tournament.full_challonge_url}\n"
                     f"\n")
        await ctx.send(text)

    @hero.command()
    @checks.is_owner()
    async def getmatches(self, ctx, channel: discord.TextChannel):
        tournament = await self.ctl.get_challonge_tournament(channel)
        await tournament.get_participants(force_update=True)
        matches = await tournament.get_matches(force_update=True)
        text = ""
        for match in matches:
            player_1 = await tournament.get_participant(match.player1_id)
            player_2 = await tournament.get_participant(match.player2_id)
            text += f"Round {match.round}, {match.id} ({match.identifier}): "
            text += f"{player_1.name} vs {player_2.name}, {match.state}\n"
        await ctx.send(text)

    @hero.command()
    @checks.is_owner()
    async def getparticipants(self, ctx, channel: discord.TextChannel):
        tournament = await self.ctl.get_challonge_tournament(channel)
        participants = await tournament.get_participants(force_update=True)
        await ctx.send('\n'.join([f"{p.id} ({p.name}): {p.final_rank}" for p in participants]))

    @hero.command()
    @checks.has_permissions(manage_guild=True)
    @checks.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def to_setup(self, ctx: hero.Context):
        """Set up your server so tournaments can be hosted on it"""
        # TODO interactive server setup
        # it automatically uses defaults for the most part for now
        guild = await self.db.wrap_guild(ctx.guild)
        await ctx.send("Enter a name for your main tournament series (will be the prefix for tournament names):")
        tournament_series_name = await self.core.wait_for_response(ctx, timeout=600)

        taken_key = True  # until proven otherwise
        while taken_key:
            await ctx.send("Enter a key for your main tournament series (will be the prefix for tournament URLs) "
                           "(letters, numbers and underscores only):")
            tournament_series_key = await self.core.wait_for_response(ctx, timeout=600)
            async with ctx.typing():
                if not await self.ctl.is_key_available(tournament_series_key):
                    taken_key = tournament_series_key
                else:
                    if '_' in tournament_series_key:
                        first_key = f"{tournament_series_key}_1"
                    else:
                        first_key = f"{tournament_series_key}1"
                    if not await self.ctl.is_key_available(first_key):
                        taken_key = first_key
                    else:
                        # key is available
                        taken_key = False
            if taken_key:
                await ctx.send(f"It appears as if this tournament series already exists:\n\n"
                               f"https://challonge.com/{taken_key}\n\n"
                               f"Please enter a different key.")
            else:
                await ctx.send(f"{self.core.YES_EMOJI} This key is available.")

        participant_role = discord.utils.get(ctx.guild.roles, name="Tournament Participants")
        if participant_role is None:
            participant_role = await guild.create_role(reason=f"Participant role is needed for "
                                                              f"{tournament_series_name} tournaments",
                                                       name=f"{tournament_series_name} Participants")
        else:
            await participant_role.edit(reason=f"Participant role is needed for "
                                               f"{tournament_series_name} tournaments",
                                        name=f"{tournament_series_name} Participants")
        participant_role = await self.db.wrap_role(participant_role)
        organizer_role = discord.utils.get(ctx.guild.roles, name="Tournament Organizers")
        if organizer_role is None:
            organizer_role = await guild.create_role(reason="Organizer role is needed for tournaments",
                                                     name="Tournament Organizers")
        organizer_role = await self.db.wrap_role(organizer_role)
        streamer_role = discord.utils.get(ctx.guild.roles, name="Tournament Streamers")
        if streamer_role is None:
            streamer_role = await guild.create_role(reason="Streamer role is useful for tournaments,"
                                                           "can be deleted if not needed",
                                                    name=f"Tournament Streamers")
        streamer_role = await self.db.wrap_role(streamer_role)

        main_series = await self.ctl.create_tournament_series(
            key=tournament_series_key, guild=guild, doubles=False,
            name=tournament_series_name,
            participant_role=participant_role, organizer_role=organizer_role,
            streamer_role=streamer_role
        )

        await self.ctl.setup_guild(guild=guild, main_series=main_series)
        await ctx.send(f"Your server is now set up to use the tournament features! "
                       f"Check the Audit Log for details. Assign yourself the "
                       f"**Tournament Organizers** role I just created, then check out the "
                       f"commands you can use using `{ctx.prefix}help to`!\n\n"
                       f"Users with the **Tournament Organizers** role will be able to "
                       f"help organize tournaments for the main tournament series and "
                       f"tournaments that do not belong to a series.\n"
                       f"Users with the **Tournament Streamers** role will be able to "
                       f"stream tournament matches of the main tournament series and "
                       f"tournaments that do not belong to a series.")

    @hero.command()
    @checks.has_permissions(manage_roles=True)
    async def to_set_participantrole(self, ctx: hero.Context, role: models.Role, *,
                                     series: ssbu_models.TournamentSeries = None):
        if series is None:
            guild = await self.db.wrap_guild(ctx.guild)
            guild_setup = await self.ctl.get_setup(guild)
            series = await guild_setup.main_series

        if not await self.ctl.is_organizer_of_series(series, ctx.author):
            organizer_role = await series.organizer_role
            organizer_role = await organizer_role.fetch()
            raise CheckFailure(f"You are not allowed to manage this tournament series.\n"
                               f"Required: Role **{organizer_role.name}**")

        series.participant_role = role
        await series.async_save()
        await ctx.send(f"Participant role set for series {series.name}.")

    @hero.command()
    @checks.has_permissions(manage_roles=True)
    async def to_set_organizerrole(self, ctx: hero.Context, role: models.Role, *,
                                   series: ssbu_models.TournamentSeries = None):
        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await self.ctl.get_setup(guild)
        if series is None:
            series = await guild_setup.main_series
            is_main_series = True
        else:
            main_series = await guild_setup.main_series
            is_main_series = main_series.key_prefix == series.key_prefix
        series.organizer_role = role
        await series.async_save()
        if is_main_series:
            await ctx.send(f"Main organizer role set.")
        else:
            await ctx.send(f"Organizer role set for series {series.name}.")

    @hero.command()
    @checks.has_permissions(manage_roles=True)
    async def to_set_streamerrole(self, ctx: hero.Context, role: models.Role, *,
                                  series: ssbu_models.TournamentSeries = None):
        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await self.ctl.get_setup(guild)
        if series is None:
            series = await guild_setup.main_series
            is_main_series = True
        else:
            main_series = await guild_setup.main_series
            is_main_series = main_series.key_prefix == series.key_prefix
        series.streamer_role = role
        await series.async_save()
        if is_main_series:
            await ctx.send("Main streamer role set.")
        else:
            await ctx.send(f"Streamer role set for series {series.name}.")

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_edit_ruleset(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_toggle_elo(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_set_signupemoji(self, ctx: hero.Context, emoji: models.Emoji):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_set_checkinemoji(self, ctx: hero.Context, emoji: models.Emoji):
        # TODO
        pass

    @hero.command()
    async def to_set_username(self, ctx: hero.Context, *, username):
        user = await self.db.load(ctx.author)
        await self.ctl.save_challonge_username(user, username)
        await ctx.send("Username set.")

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_create(self, ctx: hero.Context):
        if self.ctl.challonge_user is None:
            await ctx.send(f"I am currently not connected to Challonge, this is hopefully being fixed right now."
                           f"Please try again later, and if it still doesn't work, feel free to join my "
                           f"support server (`{ctx.prefix}support`) and get in touch with staff.")
            return

        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await self.ctl.get_setup(guild)

        await ctx.send("Should this tournament be part of a tournament series? (yes/no)")
        is_from_series = await self.core.wait_for_confirmation(ctx, timeout=600)
        if is_from_series:
            await ctx.send("Please enter the key of the tournament series:")
            tournament_series_key = await self.core.wait_for_response(ctx, timeout=600)
            await ctx.trigger_typing()
            tournament_series: ssbu_models.TournamentSeries = await ssbu_models.TournamentSeries.async_get(guild=guild, name=tournament_series_key)
            await tournament_series.async_load()
            tournament_series.next_iteration += 1
        else:
            tournament_series = None

        if tournament_series:
            name = f"{tournament_series.name} {tournament_series.next_iteration}"
        else:
            await ctx.send("Please enter the full name of the tournament:")
            name = await self.core.wait_for_response(ctx, timeout=600)

        if tournament_series:
            key = f"{tournament_series.url_prefix}{tournament_series.next_iteration}"
            taken_key = True  # until proven otherwise
            while taken_key:
                async with ctx.typing():
                    if not await self.ctl.is_key_available(tournament_series_key):
                        taken_key = tournament_series_key
                    else:
                        if '_' in tournament_series_key:
                            first_key = f"{tournament_series_key}_1"
                        else:
                            first_key = f"{tournament_series_key}1"
                        if not await self.ctl.is_key_available(first_key):
                            taken_key = first_key
                        else:
                            # key is available
                            taken_key = False
                if taken_key:
                    admin_mentions = ' '.join([admin.mention for admin in tournament_series.admins])
                    await ctx.send(f"{admin_mentions} "
                                   f"{self.core.NO_EMOJI} It appears as if someone took this tournament's key:\n\n"
                                   f"https://challonge.com/{key}"
                                   f"\n\nEnter a key to use for this tournament's URL "
                                   f"(letters, numbers and underscores only):")
                    key = await self.core.wait_for_response(ctx, timeout=600)
                else:
                    await ctx.send(f"{self.core.YES_EMOJI} This key is available.")
        else:
            taken_key = True  # until proven otherwise
            while taken_key:
                await ctx.send("Enter a key to use for this tournament's URL "
                               "(letters, numbers and underscores only):")
                key = await self.core.wait_for_response(ctx, timeout=600)
                async with ctx.typing():
                    if not await self.ctl.is_key_available(key):
                        taken_key = key
                    else:
                        # key is available
                        taken_key = False
                if taken_key:
                    await ctx.send(f"{self.core.NO_EMOJI} This tournament key is already taken:\n\n"
                                   f"https://challonge.com/{taken_key}"
                                   f"\n\nPlease enter a different key.")
                else:
                    await ctx.send(f"{self.core.YES_EMOJI} This key is available.")

        if tournament_series:
            tournament_channel = tournament_series.announcements_channel
        else:
            await ctx.send("Please enter the channel where tournament announcements should be posted:")
            tournament_channel = await self.core.wait_for_response(ctx, timeout=600)
            tournament_channel = await TextChannelConverter().convert(ctx, tournament_channel)
            tournament_channel = await self.db.wrap_text_channel(tournament_channel)

        if tournament_series:
            talk_channel = tournament_series.talk_channel
        else:
            await ctx.send("Would you like to set a separate channel as the channel where "
                           "tournament participants can talk while the tournament is going on? "
                           "(I will automatically allow/disallow writing messages for Tournament Participants.) "
                           "(yes/no)")
            confirmation = await self.core.wait_for_confirmation(ctx, timeout=600)
            if confirmation:
                await ctx.send("Please enter the channel where people should be able to talk"
                               "during the tournament:")
                talk_channel = await self.core.wait_for_response(ctx, timeout=600)
                talk_channel = await TextChannelConverter().convert(ctx, talk_channel)
                talk_channel = await self.db.wrap_text_channel(talk_channel)
            else:
                talk_channel = None

        if tournament_series:
            intro_message = tournament_series.introduction
        else:
            await ctx.send("Please enter an introduction message for the tournament (will be displayed on Challonge "
                           "and the announcements channel):")
            intro_message = await self.core.wait_for_response(ctx, timeout=600)

        async def signup_cap_check(msg):
            try:
                _signup_cap = int(msg.content)
                return 2 <= _signup_cap <= self.MAX_PARTICIPANTS
            except ValueError:
                return False

        if tournament_series:
            signup_cap = tournament_series.default_participants_limit
            await ctx.send(f"Do you want to change the maximum participants number from {signup_cap}?")
            confirmation = await self.core.wait_for_confirmation(ctx, force_response=False, timeout=150)
            if confirmation:
                _signup_cap = await self.core.wait_for_response(ctx, message_check=signup_cap_check, timeout=600)
                signup_cap = _signup_cap
                tournament_series.default_participants_limit = signup_cap
        else:
            await ctx.send(f"How many participants should the tournament have at max "
                           f"(up to {self.MAX_PARTICIPANTS})?")
            signup_cap = await self.core.wait_for_response(ctx, message_check=signup_cap_check, timeout=600)
            signup_cap = int(signup_cap)

        if tournament_series:
            start_at_datetime = tournament_series.next_start_time
        else:
            await ctx.send("When should the tournament start? (ISO format, example: `2019-04-27T18:00:00+00:00`)")
            start_at = await self.core.wait_for_response(ctx, timeout=600)
            start_at_datetime = datetime.datetime.fromisoformat(start_at)

        if tournament_series:
            delay_start = tournament_series.delay_start
        else:
            await ctx.send("Do you want to delay the start of the tournament so you can, for instance, make "
                           "changes to the automated seeding? (Recommended for servers that haven't hosted "
                           "tournaments with me before.)")
            do_delay_start = await self.core.wait_for_confirmation(ctx, timeout=600)
            if do_delay_start:
                await ctx.send("How much would you like to delay the start of the tournament (in minutes, "
                               "min. 1, max. 60)?")

                async def delay_check(msg):
                    try:
                        delay = int(msg.content)
                        return 1 <= delay <= 60
                    except ValueError:
                        return False

                delay_start = await self.core.wait_for_response(ctx, message_check=delay_check, timeout=600)
                delay_start = int(delay_start)
            else:
                delay_start = None

        admins = None
        if tournament_series:
            admins = tournament_series.admins
        if not admins:
            try:
                _user = await self.db.wrap_user(ctx.author._user)
                admin = ssbu_models.Player.async_get(pk=_user)
                if admin.challonge_user_id is None:
                    await ctx.send("Would you like to register your Challonge username "
                                   "so you can be added as admin automatically to "
                                   "tournaments you organize? (yes/no)")
                    set_admin = await self.core.wait_for_confirmation(ctx, timeout=600)
                    if set_admin:
                        while True:
                            await ctx.send("Please enter your Challonge username:")
                            challonge_username = await self.core.wait_for_response(ctx, timeout=900)
                            await self.ctl.save_challonge_username(_user, challonge_username)
                    admins = None
                else:
                    if tournament_series:
                        await tournament_series.admins.async_add(admin)
                    admins = [admin]
            except (models.User.DoesNotExist, hero.errors.UserDoesNotExist, hero.errors.InactiveUser):
                pass

        if admins:
            admins_csv = ','.join([admin.challonge_user_id for admin in admins])

        invite_link = guild.invite_link
        if invite_link is None:
            # create permanent invite for tournament descriptions
            try:
                invite = await tournament_channel.create_invite(
                    reason=f"Creating invite link for tournaments and other purposes",
                )
                invite_link = invite.url
                guild.invite_link = invite_link
            except discord.Forbidden:
                while not guild.invite_link:
                    await ctx.send("Please provide an invite link to use for tournaments")
                    invite_link = await self.core.wait_for_response(ctx, timeout=600)
                    try:
                        guild.invite_link = invite_link
                    except ValueError as ex:
                        await ctx.send(str(ex))
            await guild.async_save()

        await self.ctl.create_tournament()

        try:
            async with ctx.typing():
                tournament = await self.ctl.create_tournament()
        except challonge.APIException as ex:
            await ctx.send(f"An error occured:\n```{ex}```")
        else:
            await ctx.send(f"{tournament.name} was created successfully: {tournament.full_challonge_url}")
            # schedule tournament related commands
            when_to_checkreactions = start_at_datetime - datetime.timedelta(minutes=35)
            when_to_startcheckin = start_at_datetime - datetime.timedelta(minutes=30)
            scheduler = self.core.get_controller('scheduler')
            await scheduler.schedule(self.ctl.check_reactions, when_to_checkreactions, ctx=ctx, tournament=tournament.id)
            await scheduler.schedule(self.ctl.start_checkin, when_to_startcheckin, ctx=ctx, tournament=tournament.id)
            await scheduler.schedule(self.ctl.start_tournament, start_at_datetime, ctx=ctx, tournament=tournament.id)
            if tournament_series:
                await tournament_series.async_save()

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_checkreactions(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_signup(self, ctx: hero.Context, channel: models.TextChannel, member: models.Member):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_startcheckin(self, ctx: hero.Context, channel: models.TextChannel):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_start(self, ctx: hero.Context, channel: models.TextChannel):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_startmatch(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_end(self, ctx: hero.Context, channel: models.TextChannel):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_setwinner(self, ctx: hero.Context, participant: ssbu_models.Participant):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_setbo3(self, ctx: hero.Context, channel: models.TextChannel):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_setbo5(self, ctx: hero.Context, channel: models.TextChannel):
        # TODO
        pass

    @hero.command()
    @checks.is_owner()
    async def to_deleteall(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @checks.guild_only()
    async def teamup(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @checks.guild_only()
    async def setteamname(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.match_participant_only()
    async def forfeit(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.match_participant_only()
    async def pick(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.match_participant_only()
    async def accept(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.match_participant_only()
    async def reject(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.match_participant_only()
    async def won(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.match_participant_only()
    async def lost(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.match_participant_only()
    async def confirm(self, ctx: hero.Context):
        # TODO
        pass


"""
to_setup  # set roles, ruleset and user's Challonge username, and optionally create a tournament series
to_setparticipantrole
to_setorganizerrole
to_setstreamerrole
to_setruleset [tournament_channel]
to_editruleset [tournament_channel]
to_setusername  # set Challonge username for user
to_create
to_checkreactions
to_signup
to_startcheckin
to_start
to_startmatch
to_end
to_setwinner  # moderative command used to set the winner of a match
to_setbo3
to_setbo5
to_deleteall
teamup
setteamname
forfeit
pick  # stage
accept  # gentleman agreement on a stage
reject  # opposite of accept
won
lost
confirm  # confirm that opponent won/lost
"""
