import datetime

import discord
from discord.ext.commands import CheckFailure, has_any_role, has_guild_permissions, Paginator

import hero
from hero import checks, models, ObjectDoesNotExist
from hero.utils import MockMember

from ..checks import match_only, match_participant_only
from ..controller import SsbuController
from ..fighters import Fighter
from ..models import (Game, GuildPlayer, GuildSetup, Match, MatchCategory, MatchOffer, MatchSearch, MatchmakingSetup,
                      Player, Ruleset, SsbuSettings)
from ..stages import Stage


class Matchmaking(hero.Cog):
    core: hero.Core
    ctl: SsbuController
    settings: SsbuSettings

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

    EASTER_EGG_LINES = [
        "Oh? You're approaching me, {member.mention}?",
        "My power level is over 9000!!!",
        "I'm sorry, but your princess is in another castle.",
        "I'd destroy you, but my controller is broken right now, sorry."
    ]
    next_easter_egg_line = 0

    @hero.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        emoji = payload.emoji  # type: discord.PartialEmoji
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

        # None of the relevant reactions currently use custom emojis
        if emoji.is_custom_emoji():
            return

        guild = self.core.get_guild(guild_id)
        channel = guild.get_channel(channel_id)
        if channel is None:
            return

        member = guild.get_member(user_id)
        if member is None:
            member = await guild.fetch_member(user_id)
        try:
            message = await models.Message.objects.async_get(id=message_id)
        except models.Message.DoesNotExist:
            return
        else:
            await message.fetch()

        channel = await message.channel
        matchmaking_setup = None

        try:
            matchmaking_setup = await MatchmakingSetup.async_get(channel=channel)
        except MatchmakingSetup.DoesNotExist:
            # Is the reaction from an ongoing match, from one of the match players
            # and to the match management message?
            try:
                match = await Match.async_get(channel=channel)
            except Match.DoesNotExist:
                pass
            else:
                player_1 = await match.player_1
                player_2 = await match.player_2
                if user_id not in (player_1.id, player_2.id):
                    return

                management_message = await match.management_message
                if management_message.id == message_id:
                    await message.remove_reaction(emoji, member)

                    if str(emoji) == self.PRIVATE_REACTION:
                        # make the match private
                        await self.ctl.make_match_private(match)
                    elif str(emoji) == self.PUBLIC_REACTION:
                        # make the match spectatable
                        await self.ctl.make_match_spectatable(match)
                    elif str(emoji) == self.LEAVE_REACTION:
                        # leave/forfeit match
                        if match.ranked:
                            user = await self.db.wrap_user(member)
                            await self.ctl.handle_forfeit(match, user)
                        else:
                            await self.ctl.close_match(match, member)
                return
        else:
            # Is the reaction relevant for the main matchmaking?
            if message_id == (matchmaking_message := await matchmaking_setup.matchmaking_message).id:
                await message.remove_reaction(emoji, member)

                if str(emoji) == self.LOOKING_REACTION:
                    # looking for opponent
                    member = await self.db.wrap_member(member)
                    await self.ctl.look_for_opponents(matchmaking_setup, member)
                elif str(emoji) == self.AVAILABLE_REACTION:
                    # potentially available
                    member = await self.db.wrap_member(member)
                    await self.ctl.set_as_available(matchmaking_setup, member)
                elif str(emoji) == self.DND_REACTION:
                    # do not disturb
                    member = await self.db.wrap_member(member)
                    await self.ctl.set_as_dnd(matchmaking_setup, member)
                return

            # Is the reaction relevant for a specific match search?
            try:
                match_search = await MatchSearch.async_get(message=message)
            except MatchSearch.DoesNotExist:
                pass
            else:
                looking_member = await match_search.looking
                if (looking_user := await looking_member.user).id == user_id:
                    return
                if str(emoji) == self.OFFER_REACTION:
                    # offering match
                    offering = await self.db.wrap_member(member)
                    offered_to = looking_member
                    await offered_to.fetch()
                    try:
                        await MatchOffer.async_get(message__channel__id=channel_id,
                                                   offering=offering, offered_to=offered_to)
                    except MatchOffer.DoesNotExist:
                        await message.remove_reaction(emoji, offering)
                        ranked = matchmaking_setup.ranked
                        await self.ctl.offer_match(channel, offered_to, offering, allow_decline=False, ranked=ranked)
                elif str(emoji) == self.DECLINE_REACTION:
                    await self.ctl.set_as_available(matchmaking_setup, looking_member)
                return

        # Is the reaction relevant for a specific match offer?
        try:
            match_offer = await MatchOffer.async_get(message=message)
        except MatchOffer.DoesNotExist:
            pass
        else:
            offered_to = await match_offer.offered_to
            if not (offered_to_user := await offered_to.user).id == user_id:
                return
            if str(emoji) == self.ACCEPT_REACTION:
                # accept offer
                offering = await match_offer.offering
                if matchmaking_setup is not None:
                    ruleset = await matchmaking_setup.ruleset
                else:
                    guild = await self.db.wrap_guild(guild)
                    guild_setup = await GuildSetup.objects.async_get(guild=guild)
                    ruleset = await guild_setup.default_ruleset
                ranked = match_offer.ranked
                await self.ctl.create_match(offered_to, offering, channel, ruleset=ruleset, ranked=ranked)
            elif str(emoji) == self.DECLINE_REACTION:
                # decline offer
                await self.ctl.decline_offer(match_offer)  # delete offer message
            return

        # Is the reaction for spectating an ongoing match?
        try:
            match = await Match.async_get(spectating_message=message)
        except ObjectDoesNotExist:
            pass
        else:
            if str(emoji) == self.SPECTATE_REACTION:
                # spectate match
                player_1 = await match.player_1
                player_1_user = await player_1.user
                player_2 = await match.player_2
                player_2_user = await player_2.user
                if member.id not in (player_1_user.id, player_2_user.id):
                    await message.remove_reaction(emoji, member)
                    member = await self.db.wrap_member(member)
                    await self.ctl.spectate_match(match, member)

    @hero.listener()
    async def on_message(self, message):
        # Ignore own messages
        if message.author == self.core.user:
            return

        # If the message is from a PrivateChannel, it is not relevant here
        if message.guild is None:
            return

        # Is the message for adding to a match request?
        try:
            matchmaking_setup = await MatchmakingSetup.objects.async_get(channel__id=message.channel.id)
            match_search = await MatchSearch.objects.async_get(setup=matchmaking_setup,
                                                               looking__user__id=message.author.id)
        except ObjectDoesNotExist:
            pass
        else:
            await self.ctl.add_message_to_search(match_search, message)

    @hero.command()
    @checks.has_guild_permissions(manage_guild=True)
    @checks.bot_has_guild_permissions(manage_roles=True, manage_channels=True)
    @checks.guild_only()
    async def setup_matchmaking(self, ctx):
        guild = await self.db.wrap_guild(ctx.guild)
        setup = await self.ctl.get_setup(guild)
        if setup is None:
            setup, _ = await self.ctl.setup_guild(guild)

        await ctx.send("Which channel do you want to set up as a dedicated matchmaking channel?")
        channel = await self.core.wait_for_response(ctx)
        channel = await models.TextChannel.convert(ctx, channel)
        if channel.discord.guild != ctx.guild:
            await ctx.send("Invalid text channel, the given text channel has "
                           "to be located on this server.")
            return

        msg = await ctx.send("Do you want this matchmaking setup to host ranked matches?")
        ranked = await self.core.wait_for_confirmation(msg, ctx.author)

        ruleset = await self.ctl.create_ruleset(ctx)

        msg = await ctx.send("If you have or plan to have multiple matchmaking setups, you should "
                             "give this matchmaking setup a name that would help you "
                             "recognize which matchmaking role belongs to which "
                             "matchmaking setup. Do you want to give this matchmaking setup a name? (y/n)")
        give_name = await self.core.wait_for_confirmation(msg, ctx.author, timeout=90)
        if give_name:
            await ctx.send("Please enter a name for this matchmaking setup:")
            name = await self.core.wait_for_response(ctx, timeout=120)
        else:
            name = ""

        await self.ctl.setup_matchmaking(channel, name, ruleset, ranked=ranked)

        _ranked = "Ranked " if ranked else ""
        await ctx.send(f"{_ranked}Matchmaking has now been set up in {channel.discord.mention}!\n"
                       f"You can customize the roles and category as you wish."
                       f"\n**Note:** It is not recommended to use the roles that were created "
                       f"during installation for anything else. Also, make sure my "
                       f"highest role is always above those roles.")

    @hero.command()
    @checks.guild_only()
    @checks.has_permissions(manage_guild=True)
    async def edit_ruleset(self, ctx):
        guild = await self.db.wrap_guild(ctx.guild)
        rulesets_qs = Ruleset.objects.filter(guild=guild).distinct('name')
        rulesets = await rulesets_qs.async_to_list()
        ruleset_names = [ruleset.name for ruleset in rulesets]
        await ctx.send("Which ruleset do you want to edit? Please enter its number:")
        ruleset_name = await self.core.wait_for_choice(ctx, ctx.author, ruleset_names)
        new_ruleset = await self.ctl.edit_ruleset(ctx, ruleset_name)
        starters = '**' + '**\n**'.join([str(stage) for stage in new_ruleset.starter_stages]) + '**'
        counterpicks = '**' + '**\n**'.join([str(stage) for stage in new_ruleset.counterpick_stages]) + '**'
        await ctx.send(
            f"Done! This is what your new ruleset looks like:\n\n"
            f"**{ruleset_name} (Version {new_ruleset.version})**\n\n"
            f"__Starter Stages__\n"
            f"{starters}\n\n"
            f"__Counterpick Stages__\n"
            f"{counterpicks}\n\n"
            f"Counterpick Bans: **{new_ruleset.counterpick_bans}**\n"
            f"DSR: {new_ruleset.dsr.value.capitalize()}"
        )

    @hero.command()
    @checks.guild_only()
    @checks.has_permissions(manage_guild=True)
    async def set_defaultruleset(self, ctx):
        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        rulesets_qs = Ruleset.objects.filter(guild=guild).distinct('name')
        rulesets = await rulesets_qs.async_to_list()
        ruleset_names = [ruleset.name for ruleset in rulesets]
        await ctx.send("Which ruleset do you want to choose as this server's default ruleset? "
                       "Please enter its number:")
        ruleset_name = await self.core.wait_for_choice(ctx, ctx.author, ruleset_names)
        ruleset = await Ruleset.objects.filter(name=ruleset_name, guild=guild).async_latest()
        guild_setup.default_ruleset = ruleset
        await guild_setup.async_save()
        starters = '**' + '**\n**'.join([str(stage) for stage in ruleset.starter_stages]) + '**'
        counterpicks = '**' + '**\n**'.join([str(stage) for stage in ruleset.counterpick_stages]) + '**'
        await ctx.send(
            f"Done! This is your server's default ruleset now:\n\n"
            f"**{ruleset.name} (Version {ruleset.version})**\n\n"
            f"__Starter Stages__\n"
            f"{starters}\n\n"
            f"__Counterpick Stages__\n"
            f"{counterpicks}\n\n"
            f"Counterpick Bans: **{ruleset.counterpick_bans}**\n"
            f"DSR: {ruleset.dsr.value.capitalize()}"
        )

    @hero.command()
    @checks.guild_only()
    async def challenge(self, ctx, member: models.Member):
        """Offer a match to another server member"""
        await ctx.message.delete()
        _user = await member.user
        if ctx.author.id == _user.id:
            await ctx.send("You can't challenge yourself.")
            return
        if _user.id == self.core.user.id:
            line = self.EASTER_EGG_LINES[self.next_easter_egg_line]
            try:
                line = line.format(member=ctx.author)
            except TypeError:
                pass
            num_lines = len(self.EASTER_EGG_LINES)
            if self.next_easter_egg_line == num_lines:
                self.next_easter_egg_line = 0
            else:
                self.next_easter_egg_line += 1
            await ctx.send(line)
            return

        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        default_ruleset = await guild_setup.default_ruleset
        if default_ruleset is not None:
            msg = await ctx.send(f"Do you want to challenge **{member.display_name}** to a ranked match?")
            ranked = await self.core.wait_for_confirmation(msg, ctx.author)
            await msg.delete()
        else:
            ranked = False

        channel = await self.db.wrap_text_channel(ctx.channel)
        offering = await self.db.wrap_member(ctx.message.author)
        await self.ctl.offer_match(channel, member, offering, ranked=ranked)

    @hero.command()
    async def charpick(self, ctx, *, fighter: Fighter):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        picking = await self.db.wrap_user(ctx.author)
        try:
            await self.ctl.pick_character(ctx.channel, picking, fighter)
        except CheckFailure as cf:
            await ctx.send(str(cf))

    @hero.command()
    @match_participant_only()
    async def strike(self, ctx, *, stages: str):
        await ctx.message.delete()
        stages = [await Stage.convert(ctx, stage) for stage in stages.replace(', ', ',').split(',')]
        channel = await self.db.wrap_text_channel(ctx.channel)
        match = await Match.objects.async_get(channel=channel)
        striked_by = await self.db.wrap_user(ctx.author)
        for stage in stages:
            is_your_turn = await self.ctl.strike_stage(match, stage, striked_by)
            if not is_your_turn:
                await ctx.send("It is not your turn to strike a stage.", delete_after=30)
                return

    @hero.command()
    @match_participant_only()
    async def pick(self, ctx, *, stage: Stage):
        await ctx.message.delete()
        channel = await self.db.wrap_text_channel(ctx.channel)
        match = await Match.objects.async_get(channel=channel)
        striked_by = await self.db.wrap_user(ctx.author)
        is_your_turn = await self.ctl.pick_stage(match, stage, striked_by)
        if not is_your_turn:
            await ctx.send("It is not your turn to pick a stage.", delete_after=30)

    @hero.command(aliases=['win', 'victory'])
    @match_participant_only()
    async def won(self, ctx):
        await ctx.message.delete()
        channel = await self.db.wrap_text_channel(ctx.channel)
        match = await Match.objects.async_get(channel=channel)
        player = await self.db.wrap_user(ctx.author)
        await self.ctl.process_victory(match, player)

    @hero.command(aliases=['lose', 'loss'])
    @match_participant_only()
    async def lost(self, ctx):
        await ctx.message.delete()
        channel = await self.db.wrap_text_channel(ctx.channel)
        match = await Match.objects.async_get(channel=channel)
        player = await self.db.wrap_user(ctx.author)
        await self.ctl.process_loss(match, player)

    @hero.command()
    @match_participant_only()
    async def leave(self, ctx):
        await ctx.message.delete()
        channel = await self.db.wrap_text_channel(ctx.channel)
        match = await Match.objects.async_get(channel=channel)
        player = await self.db.wrap_user(ctx.author)
        # TODO if match.tournament
        if match.ranked:
            if match.ended_at is None:
                await ctx.send("This is a ranked match, so leaving it would make you forfeit.",
                               delete_after=60)
                await self.ctl.handle_forfeit(match, player)
            else:
                await ctx.channel.edit(overwrites={ctx.author: None})
        else:
            await self.ctl.close_match(match)

    @hero.command()
    @match_participant_only()
    async def forfeit(self, ctx):
        await ctx.message.delete()
        channel = await self.db.wrap_text_channel(ctx.channel)
        match = await Match.objects.async_get(channel=channel)
        if not match.ranked:
            await channel.send("This is not a ranked match, just use the `/leave` command to leave the match.")
            return
        player = await self.db.wrap_user(ctx.author)
        await self.ctl.handle_forfeit(match, player)

    @hero.command()
    @has_guild_permissions(manage_channels=True)
    async def close(self, ctx):
        try:
            match = await Match.objects.async_get(channel__id=ctx.channel.id)
        except Match.DoesNotExist:
            channel_name: str = ctx.channel.name
            if '_vs_' in channel_name:
                await ctx.send("It looks like this match channel has not been deleted. You can delete it manually!")
            return
        if match.ranked and await match.winner is None:
            match.ranked = False
            await match.async_save()
        await self.ctl.close_match(match)

    @hero.command()
    @checks.guild_only()
    async def rating(self, ctx, member: models.Member = None):
        if member is None:
            member = await self.db.wrap_member(ctx.author)
            guild_player, _ = await GuildPlayer.objects.async_get_or_create(member=member)
            await ctx.send(f"Your Rating is: **{guild_player.rating}**±**{guild_player.deviation}**")
        else:
            guild_player, _ = await GuildPlayer.objects.async_get_or_create(member=member)
            await ctx.send(f"{member.mention}'s Rating is: **{guild_player.rating}**±**{guild_player.deviation}**")

    @hero.command()
    @has_guild_permissions(manage_guild=True)
    @checks.guild_only()
    async def reset_rating(self, ctx, member: models.Member, rating: int = None,
                           deviation: int = None, volatility: float = None):
        if rating is None:
            rating = self.ctl.glicko.mu
        if deviation is None:
            deviation = self.ctl.glicko.phi

        guild = await self.db.wrap_guild(ctx.guild)
        player = await member.user

        matches_qs_1: models.QuerySet = Match.objects.filter(guild=guild, ranked=True, player_1=player)
        matches_1 = await matches_qs_1.async_to_list()
        for match_1 in matches_1:
            await match_1.async_delete()

        matches_qs_2 = Match.objects.filter(guild=guild, ranked=True, player_2=player)
        matches_2 = await matches_qs_2.async_to_list()
        for match_2 in matches_2:
            await match_2.async_delete()

        mention = member.discord.mention
        guild_player, _ = await GuildPlayer.objects.async_get_or_create(member=member)
        guild_player.rating = rating
        guild_player.deviation = deviation
        if volatility is not None:
            guild_player.volatility = volatility
        await guild_player.async_save()
        await ctx.send(f"{mention}'s rating is now: **{guild_player.rating}**±**{guild_player.deviation}**")

    @hero.command()
    @has_guild_permissions(manage_guild=True)
    @checks.guild_only()
    async def set_rating(self, ctx, member: models.Member, rating: int, deviation: int, volatility: float = None):
        mention = member.discord.mention
        guild_player, _ = await GuildPlayer.objects.async_get_or_create(member=member)
        guild_player.rating = rating
        guild_player.deviation = deviation
        if volatility is not None:
            guild_player.volatility = volatility
        await guild_player.async_save()
        await ctx.send(f"{mention}'s rating is now: **{guild_player.rating}**±**{guild_player.deviation}**")

    @hero.command()
    @checks.guild_only()
    @checks.is_owner()
    async def verify(self, ctx):
        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        guild.setup.verified = True
        await guild_setup.async_save()
        await ctx.send(f"**{guild}** is now a verified server! Ranked matches held here will now "
                       f"affect players' global Rating as well.")

    @hero.command()
    @checks.guild_only()
    @checks.is_owner()
    async def updatemmmsg(self, ctx, channel: models.TextChannel):
        matchmaking_setup = await MatchmakingSetup.async_get(channel=channel)
        original_message = await matchmaking_setup.matchmaking_message
        msg = await self.ctl._send_matchmaking_message(channel, original_message=original_message,
                                                       ranked=matchmaking_setup.ranked)
        if msg.id != original_message.id:
            msg = await self.db.wrap_message(msg)
            matchmaking_setup.matchmaking_message = msg
            await matchmaking_setup.async_save()
            await original_message.async_delete()

    @hero.command()
    async def test_fighter(self, ctx, *, fighter: Fighter):
        await ctx.send(f"That's {fighter}!")

    @hero.command()
    async def test_stage(self, ctx, *, stage: Stage):
        await ctx.send(f"That's {stage}!")

    @hero.command()
    @checks.is_owner()
    async def reset_allratings(self, ctx):
        from hero import async_using_db

        @async_using_db
        def _clear_ratings():
            # delete all Matches
            for match in list(Match.objects.all()):
                match.delete()
            # delete all GuildPlayers
            for guild_player in list(GuildPlayer.objects.all()):
                guild_player.delete()
            # delete all Players
            for player in list(Player.objects.all()):
                player.delete()
        await _clear_ratings()

        await ctx.send("Done!")

    @hero.command()
    @has_any_role(784115581837770763, 415354084846206976)
    @checks.guild_only()
    async def reset_euasrating(self, ctx, user: discord.User):
        guild: discord.Guild = self.core.get_guild(415351962372931585)
        member = await guild.fetch_member(user.id)
        divx_role = guild.get_role(785085848751964190)
        div1_role = guild.get_role(783857557529165854)
        div1_trial_role = guild.get_role(784497087915622470)
        div2_role = guild.get_role(783858759226359900)
        div3_role = guild.get_role(783858963967901698)
        guild = await self.db.wrap_guild(guild)
        mention = member.mention

        if divx_role in member.roles:
            rating = 2800
            deviation = 100
        elif div1_role in member.roles or div1_trial_role in member.roles:
            rating = 2500
            deviation = 150
        elif div2_role in member.roles:
            rating = 2000
            deviation = 250
        else:
            rating = 1500
            deviation = 350

        user, _ = await models.User.objects.async_get_or_create(id=member._user.id)
        member, _ = await models.Member.objects.async_get_or_create(user=user, guild=guild)
        guild_player = GuildPlayer(member=member, rating=rating, deviation=deviation, volatility=0.06)
        await guild_player.async_save()
        await ctx.send(f"{mention}'s rating is now: **{guild_player.rating}**±**{guild_player.deviation}**")

    @hero.command()
    @checks.is_owner()
    async def reset_euasratings(self, ctx):
        guild: discord.Guild = self.core.get_guild(415351962372931585)
        divx_role = guild.get_role(785085848751964190)
        div1_role = guild.get_role(783857557529165854)
        div1_trial_role = guild.get_role(784497087915622470)
        div2_role = guild.get_role(783858759226359900)
        div3_role = guild.get_role(783858963967901698)
        members = guild.members
        guild = await self.db.wrap_guild(guild)
        for member in members:
            if member._user.bot:
                continue
            if divx_role in member.roles:
                rating = 2800
                deviation = 100
            elif div1_role in member.roles or div1_trial_role in member.roles:
                rating = 2500
                deviation = 150
            elif div2_role in member.roles:
                rating = 2000
                deviation = 250
            else:
                rating = 1500
                deviation = 350
            user, _ = await models.User.objects.async_get_or_create(id=member._user.id)
            member, _ = await models.Member.objects.async_get_or_create(user=user, guild=guild)
            guild_player = GuildPlayer(member=member, rating=rating, deviation=deviation, volatility=0.06)
            await guild_player.async_save()
        await ctx.send("Done!")

    @hero.command()
    @hero.cooldown(1, 600.0, hero.BucketType.guild)
    @checks.guild_only()
    async def stats(self, ctx, month: int = None, year: int = None):
        Count, Q = models.Count, models.Q
        async with ctx.typing():
            guild = await self.db.wrap_guild(ctx.guild)
            now = datetime.datetime.utcnow()
            if month is None:
                month = now.month
            if year is None:
                year = now.year
            month_start = datetime.datetime(year=year, month=month, day=1, tzinfo=now.tzinfo)
            next_month_start = datetime.datetime(year=year, month=month + 1, day=1, tzinfo=now.tzinfo)
            # most active users this month
            members_qs = models.Member.objects.filter(guild=guild, user__is_active=True)
            members_qs = members_qs.annotate(
                num_total_matches=Count(
                    'user__match', filter=Q(
                        user__match__guild=guild, user__match__started_at__gte=month_start,
                        user__match__started_at__lt=next_month_start
                    )
                )
            ).filter()
            members_qs = members_qs.annotate(
                num_ranked_matches=Count(
                    'user__match', filter=Q(
                        user__match__guild=guild, user__match__ranked=True,
                        user__match__started_at__gte=month_start, user__match__started_at__lt=next_month_start
                    )
                )
            )

            @hero.async_using_db
            def get_users_with_most_matches(_members_qs, limit=10):
                return list(_members_qs.order_by('-num_total_matches')[:limit])

            @hero.async_using_db
            def get_users_with_least_matches(_members_qs):
                return list(_members_qs.filter(num_total_matches=0))

            @hero.async_using_db
            def get_highest_rated_users(_guild, limit=10):
                return list(GuildPlayer.objects.filter(member__guild=_guild).order_by('-rating')[:limit])

            most_active_users = await get_users_with_most_matches(members_qs)
            least_active_users = await get_users_with_least_matches(members_qs)
            highest_rated_users = await get_highest_rated_users(guild)

            paginator = Paginator(prefix='', suffix='')

            paginator.add_line("**__Most active users:__**", empty=True)
            for i, member in enumerate(most_active_users, 1):
                _user = await member.user
                user = await _user.fetch()
                paginator.add_line(
                    f"**{i}.** {user.mention}: **{member.num_total_matches}**"
                )

            paginator.add_line('')
            paginator.add_line("**__Least active users:__**", empty=True)
            for i, member in enumerate(least_active_users, 1):
                _user = await member.user
                try:
                    user = await _user.fetch()
                except discord.HTTPException:
                    continue
                paginator.add_line(
                    f"**{i}.** {user.mention}: **{member.num_total_matches}**"
                )

            paginator.add_line('')
            paginator.add_line("**__Highest rated users:__**", empty=True)
            for i, guild_player in enumerate(highest_rated_users, 1):
                _member = await guild_player.member
                _user = await _member.user
                user = await _user.fetch()
                paginator.add_line(
                    f"**{i}.** {user.mention}: **{guild_player.rating}**±**{guild_player.deviation}**"
                )

            for page in paginator.pages:
                await ctx.send(page)

    @hero.command()
    @checks.has_guild_permissions(manage_roles=True)
    async def fix_ingamerole(self, ctx):
        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        ingame_role = await guild_setup.ingame_role
        needs_fixing = False
        if ingame_role is None:
            needs_fixing = True
        try:
            await ingame_role.fetch()
        except discord.NotFound:
            needs_fixing = True
        if ingame_role.discord is None:
            needs_fixing = True
        if not needs_fixing:
            ingame_role = ingame_role.discord
            mention = ingame_role.mention
            await ctx.send(f"No fixing needed: {mention}")
            return

        # create ingame role
        ingame_role = await guild.discord.create_role(name="In-game",
                                                      colour=discord.Colour.from_rgb(207, 54, 48),
                                                      reason="Creating role necessary for matches")
        ingame_role = await self.db.wrap_role(ingame_role)
        guild_setup.ingame_role = ingame_role
        await guild_setup.async_save()
        await ctx.send("Done!")

    @hero.command()
    @checks.has_guild_permissions(manage_channels=True)
    async def fix_bpchannels(self, ctx):
        guild = await self.db.wrap_guild(ctx.guild)
        guild_setup = await GuildSetup.objects.async_get(guild=guild)
        p1_bp_channel = await guild_setup.player_1_blindpick_channel
        p2_bp_channel = await guild_setup.player_2_blindpick_channel
        ch1_needs_fixing = False
        ch2_needs_fixing = False

        if p1_bp_channel is None:
            ch1_needs_fixing = True
        try:
            await p1_bp_channel.fetch()
        except discord.NotFound:
            ch1_needs_fixing = True
        if p1_bp_channel.discord is None:
            ch1_needs_fixing = True

        if p2_bp_channel is None:
            ch2_needs_fixing = True
        try:
            await p2_bp_channel.fetch()
        except discord.NotFound:
            ch2_needs_fixing = True
        if p2_bp_channel.discord is None:
            ch2_needs_fixing = True

        if not (ch1_needs_fixing or ch2_needs_fixing):
            p1_bp_channel = p1_bp_channel.discord
            mention_1 = p1_bp_channel.mention
            await ctx.send(f"No fixing needed: {mention_1}")
            return

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
            _matchmaking_category = await self.ctl.create_matches_category(guild, 1)
            matchmaking_category = await _matchmaking_category.category
            await matchmaking_category.fetch()
        except discord.NotFound:
            await _matchmaking_category.async_delete()
            _matchmaking_category = await self.ctl.create_matches_category(guild, 1)
            matchmaking_category = await _matchmaking_category.category
            await matchmaking_category.fetch()

        if ch1_needs_fixing:
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

        if ch2_needs_fixing:
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

        await guild_setup.async_save()
        await ctx.send("Done!")
