import discord

import hero
from hero import checks, models, ObjectDoesNotExist
from hero.utils import MockMember

from ..controller import SsbuController
from ..models import Match, MatchOffer, MatchSearch, MatchmakingSetup, SsbuSettings
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
                player_1_user = await player_1.user
                player_2 = await match.player_2
                player_2_user = await player_2.user
                if user_id not in (player_1_user.id, player_2_user.id):
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
                        # leave match
                        await self.ctl.end_match(match, member)
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
                        await self.ctl.offer_match(channel, offered_to, offering, allow_decline=False)
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
                await self.ctl.create_match(offered_to, offering, channel)
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
    @checks.has_permissions(manage_guild=True)
    @checks.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def matchmaking_setup(self, ctx):
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

        ruleset = await self.ctl.create_ruleset(ctx)

        await ctx.send("If you have or plan to have multiple matchmaking setups, you should "
                       "give this matchmaking setup a name that would help you to "
                       "recognize which matchmaking role belongs to which "
                       "matchmaking setup. Do you want to give this matchmaking setup a name?")
        give_name = await self.core.wait_for_confirmation(ctx, timeout=90)
        if give_name:
            await ctx.send("Please enter a name for this matchmaking setup:")
            name = await self.core.wait_for_response(ctx, timeout=120)
        else:
            name = ""

        # configure matchmaking channel
        await channel.discord.set_permissions(ctx.guild.default_role, send_messages=False,
                                      add_reactions=False,
                                      reason="Only members looking for players should be able to "
                                             "send messages in the matchmaking channel")
        await channel.set_permissions(ctx.guild.me, send_messages=True,
                                      add_reactions=True, manage_messages=True,
                                      reason="The bot should also be able to "
                                             "send messages in the matchmaking channel")

        # send matchmaking message
        matchmaking_message = await channel.discord.send(
            f"Click a reaction to change your matchmaking status:\n"
            f"\n"
            f"{self.LOOKING_REACTION} **Looking for Player**\n"
            f"{self.AVAILABLE_REACTION} **Potentially Available**\n"
            f"{self.DND_REACTION} (Default) **Do Not Disturb**\n"
            f"\n"
            f"If a player is already looking for an opponent, you can "
            f"offer to play with them by clicking {self.OFFER_REACTION}. "
            f"They can then accept by clicking {self.ACCEPT_REACTION}.\n"
            f"\n"
            f"**Note:** You can also add a custom message to your "
            f"match request by sending a message in here.\n"
            f"If a match is not private, you can click the {self.SPECTATE_REACTION} "
            f"to get access to the match as a spectator."
        )

        # create roles
        looking_name = f"Looking for Player ({name})" if name else "Looking for Player"
        looking_role = await ctx.guild.create_role(name=looking_name,
                                                   colour=discord.Colour.from_rgb(60, 192, 48),
                                                   hoist=True,
                                                   reason="Creating role necessary for matchmaking")
        looking_role = await self.db.wrap_role(looking_role)

        await channel.set_permissions(looking_role.discord, send_messages=True,
                                      reason="Only members looking for players should be able to "
                                             "send messages in the matchmaking channel")

        available_name = f"Potentially Available ({name})" if name else "Potentially Available"
        available_role = await ctx.guild.create_role(name=available_name,
                                                     colour=discord.Colour.from_rgb(56, 140, 238),
                                                     reason="Creating role necessary for matchmaking")
        available_role = await self.db.wrap_role(available_role)

        await matchmaking_message.add_reaction("\U0001F50D")  # mag
        await matchmaking_message.add_reaction("\U0001F514")  # bell
        await matchmaking_message.add_reaction("\U0001F515")  # no_bell

        matchmaking_message = await self.db.wrap_message(matchmaking_message)

        # save setup
        await ruleset.async_save()
        _matchmaking_setup = MatchmakingSetup(channel=channel, name=name,
                                              matchmaking_message=matchmaking_message,
                                              ruleset=ruleset, looking_role=looking_role,
                                              available_role=available_role)
        await _matchmaking_setup.async_save()

        await ctx.send(f"Matchmaking has now been set up in {channel.discord}!\n"
                       f"All done! You can customize the roles and category as you wish."
                       f"\n**Note:** It is not recommended to use the roles that were created "
                       f"during installation for anything else. Also, make sure my "
                       f"highest role is always above those roles.")
