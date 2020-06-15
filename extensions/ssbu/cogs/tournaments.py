import datetime

import challonge

import discord
from discord.ext.commands import TextChannelConverter

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
        await ctx.send("Enter a key for your main tournament series (will be the prefix for tournament URLs) "
                       "(letters, numbers and underscores only):")
        tournament_series_key = await self.core.wait_for_response(ctx, timeout=600)

        participant_role = await guild.create_role(reason=f"Participant role is needed for "
                                                          f"{tournament_series_name} tournaments",
                                                   name=f"{tournament_series_name} Participants")
        participant_role = await self.db.wrap_role(participant_role)
        organizer_role = await guild.create_role(reason=f"Organizer role is needed for "
                                                        f"{tournament_series_name} tournaments",
                                                 name=f"{tournament_series_name} Organizers")
        organizer_role = await self.db.wrap_role(organizer_role)
        streamer_role = await guild.create_role(reason=f"Streamer role is useful for "
                                                       f"{tournament_series_name} tournaments,"
                                                       f"can be deleted if not needed",
                                                name=f"{tournament_series_name} Streamers")
        streamer_role = await self.db.wrap_role(streamer_role)

        main_series = await self.ctl.create_tournament_series(key=tournament_series_key, name=tournament_series_name,
                                                              participant_role=participant_role,
                                                              organizer_role=organizer_role,
                                                              streamer_role=streamer_role)

        await self.ctl.setup_guild(guild=guild, main_series=main_series)
        await ctx.send(f"Your server is now set up to use the tournament features! "
                       f"Check the Audit Log for details. Assign yourself the "
                       f"Tournament Organizer role I just created, and check out the "
                       f"commands you can use using `{ctx.prefix}help to`!")

    @hero.command()
    @checks.has_permissions(manage_roles=True)
    async def to_set_participantrole(self, ctx: hero.Context, role: models.Role):
        guild = await self.db.load(ctx.guild)
        try:
            await self.ctl.save_participant_role(guild, role)
        except ssbu_models.GuildSetup.DoesNotExist:
            await ctx.send(f"The server has not been set up yet; use `{ctx.prefix}to setup`.")
            return
        await ctx.send("Participant role set.")

    @hero.command()
    @checks.has_permissions(manage_roles=True)
    async def to_set_organizerrole(self, ctx: hero.Context, role: models.Role):
        guild = await self.db.load(ctx.guild)
        try:
            await self.ctl.save_organizer_role(guild, role)
        except ssbu_models.GuildSetup.DoesNotExist:
            await ctx.send(f"The server has not been set up yet; use `{ctx.prefix}to setup`.")
            return
        await ctx.send("Organizer role set.")

    @hero.command()
    @checks.has_permissions(manage_roles=True)
    async def to_set_streamerrole(self, ctx: hero.Context, role: models.Role):
        guild = await self.db.load(ctx.guild)
        try:
            await self.ctl.save_streamer_role(guild, role)
        except ssbu_models.GuildSetup.DoesNotExist:
            await ctx.send(f"The server has not been set up yet; use `{ctx.prefix}to setup`.")
            return
        await ctx.send("Streamer role set.")

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_set_ruleset(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_editruleset(self, ctx: hero.Context):
        # TODO
        pass

    @hero.command()
    @ssbu_checks.main_to_only()
    async def to_toggleelo(self, ctx: hero.Context):
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
            await ctx.send("I am currently not connected to Challonge, this is hopefully being fixed right now."
                           "Please try again later, and if it still doesn't work, feel free to join my "
                           "support server (`{prefix}support`) and get in touch with staff.")
            return

        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await self.ctl.get_setup(guild)

        await ctx.send("Should this tournament be part of a tournament series? (yes/no)")
        confirmation = await self.core.wait_for_confirmation(ctx, timeout=600)
        if confirmation:
            await ctx.send("Please enter the key of the tournament series:")
            response = await self.core.wait_for_response(ctx, timeout=600)
            tournament_series_name = response.content

            tournament_series = await ssbu_models.TournamentSeries.async_get(guild=guild, name=tournament_series_name)

            name = f"{tournament_series.name} {tournament_series.next_iteration}"
            key = f"{tournament_series.url_prefix}{tournament_series.next_iteration}"
            intro_message = tournament_series.introduction
            tournament_channel = tournament_series.announcements_channel
            talk_channel = tournament_series.talk_channel

            tournament_series.next_iteration += 1
        else:
            tournament_series = None

            await ctx.send("Please enter the full name of the tournament:")
            response = await self.core.wait_for_response(ctx, timeout=600)
            name = response.content

            await ctx.send("Please enter a key to use for the tournament URL (letters, numbers and underscores only):")
            response = await self.core.wait_for_response(ctx, timeout=600)
            key = response.content

            await ctx.send("Please enter the channel where tournament announcements should be posted:")
            response = await self.core.wait_for_response(ctx, timeout=600)
            tournament_channel = await TextChannelConverter().convert(ctx, response.content)
            tournament_channel = await self.db.load(tournament_channel)

            await ctx.send("Would you like to set a separate channel as the channel where "
                           "tournament participants can talk while the tournament is going on? "
                           "(I will automatically allow/disallow writing messages for Tournament Participants.) "
                           "(yes/no)")
            confirmation = await self.core.wait_for_confirmation(ctx, timeout=600)
            if confirmation:
                await ctx.send("Please enter the channel where people should be able to talk"
                               "during the tournament:")
                response = await self.core.wait_for_response(ctx, timeout=600)
                talk_channel = await TextChannelConverter().convert(ctx, response.content)
                talk_channel = await self.db.load(talk_channel)
            else:
                talk_channel = None

            await ctx.send("Please enter an introduction message for the tournament (will be displayed on Challonge "
                           "and the announcements channel):")
            response = await self.core.wait_for_response(ctx, timeout=600)
            intro_message = response.content

        if guild.invite_link is None:
            await ctx.send("Please enter an invite link to use for the tournament description:")
            response = await self.core.wait_for_response(ctx, timeout=600)
            invite_link = response.content
            guild.invite_link = invite_link
            await guild.async_save()
        else:
            invite_link = guild.invite_link

        await ctx.send("How many participants should the tournament have at max (up to 512)?")
        response = await self.core.wait_for_response(ctx, timeout=600)
        signup_cap = response.content
        if int(signup_cap) > 512:
            await ctx.send("Signup cap needs to be 512 or less.")
            return

        await ctx.send("When should the tournament start? (ISO format, example: `2019-04-27T18:00:00+00:00`)")
        response = await self.core.wait_for_response(ctx, timeout=600)
        start_at = response.content
        start_at_datetime = datetime.datetime.fromisoformat(start_at)
        start_time = start_at_datetime.strftime('on %A, %B %d, %Y at %I.%M %p %Z')

        description = strings.description.format(intro_message=intro_message, invite_link=invite_link,
                                                 channel=ctx.channel)

        try:
            _user = await self.db.load(ctx.author.user)
            admin = ssbu_models.Player(_user)
            if admin.challonge_user_id is None:
                admin = None
        except (models.User.DoesNotExist, hero.errors.UserDoesNotExist, hero.errors.InactiveUser):
            admin = None

        try:
            async with ctx.typing():
                tournament: challonge.Tournament = await self.ctl.create_tournament(

                )
                signup_message = await self.send_signup_message(tournament_channel,
                                                                intro_message=intro_message,
                                                                start_time=start_time,
                                                                full_challonge_url=tournament.full_challonge_url)
                signup_message = await self.db.load(signup_message)
                await self.ctl.save_tournament(signup_message, tournament)
            await ctx.send(f"{tournament.name} was created successfully: {tournament.full_challonge_url}\n"
                           f"Scheduling tasks...")

            # schedule tournament related commands
            when_to_checkreactions = start_at_datetime - datetime.timedelta(minutes=35)
            when_to_startcheckin = start_at_datetime - datetime.timedelta(minutes=30)
            scheduler = self.core.get_controller('scheduler')
            await scheduler.schedule(self.ctl.check_reactions, when_to_checkreactions, ctx=ctx, tournament=tournament.id)
            await scheduler.schedule(self.ctl.start_checkin, when_to_startcheckin, ctx=ctx, tournament=tournament.id)
            await scheduler.schedule(self.ctl.start_tournament, start_at_datetime, ctx=ctx, tournament=tournament.id)
        except challonge.APIException as ex:
            await ctx.send(f"An error occured:\n```{ex}```")
        else:
            if tournament_series is not None:
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
