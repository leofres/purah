from discord.ext.commands import check, errors

from hero import Context
from hero.models import TextChannel

from .models import DoublesMatch, GuildSetup, Match


def match_participant_only():
    async def predicate(ctx: Context):
        if ctx.guild is None:
            return False
        match = Match.objects.filter(channel=await ctx.bot.db.wrap_text_channel(ctx.channel))
        match_exists = await match.async_exists()
        if not match_exists:
            return False
        match = await match.async_first()
        await match.async_load()
        player_1 = await match.player_1
        player_2 = await match.player_2
        return ctx.author.id in (player_1.id, player_2.id)

    return check(predicate)


def match_only():
    async def predicate(ctx: Context):
        match = Match.objects.filter(channel__id=ctx.channel.id)
        return await match.async_exists()

    return check(predicate)


def any_to_only():
    async def predicate(ctx: Context):
        if ctx.guild is None:
            raise errors.NoPrivateMessage()
        ssbu_controller = ctx.bot.get_controller('ssbu')
        db = ctx.bot.db
        guild = await db.wrap_guild(ctx.guild)
        author = await db.wrap_member(ctx.author)
        return await ssbu_controller.is_any_organizer(guild, author)

    return check(predicate)


def main_to_only():
    async def predicate(ctx: Context):
        if ctx.guild is None:
            raise errors.NoPrivateMessage()
        ssbu_controller = ctx.bot.get_controller('ssbu')
        db = ctx.bot.db
        guild = await db.wrap_guild(ctx.guild)
        author = await db.wrap_member(ctx.author)
        return await ssbu_controller.is_main_organizer(guild, author)

    return check(predicate)


def to_only():
    async def predicate(ctx: Context):
        if ctx.guild is None:
            raise errors.NoPrivateMessage()
        ssbu_controller = ctx.bot.get_controller('ssbu')
        db = ctx.bot.db
        channel = await db.wrap_text_channel(ctx.channel)
        author = await db.wrap_member(ctx.author)
        return await ssbu_controller.is_organizer(channel, author)

    return check(predicate)


def to_or_main_to_only():
    async def predicate(ctx: Context):
        if ctx.guild is None:
            raise errors.NoPrivateMessage()
        ssbu_controller = ctx.bot.get_controller('ssbu')
        db = ctx.bot.db
        guild = await db.wrap_guild(ctx.guild)
        author = await db.wrap_member(ctx.author)
        if await ssbu_controller.is_main_organizer(guild, author):
            return True
        else:
            channel = await db.wrap_text_channel(ctx.channel)
            return await ssbu_controller.is_organizer(channel, author)

    return check(predicate)
