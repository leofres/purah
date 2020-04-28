import discord

import hero
from hero import checks


class Essentials(hero.Cog):
    @hero.command(aliases=['set_prefix'])
    @checks.is_owner()
    async def set_prefixes(self, ctx, *prefixes: str):
        self.core.set_prefixes(prefixes)
        await ctx.send("Done.")

    @hero.command()
    @checks.is_owner()
    async def set_description(self, ctx, *, description: str):
        self.core.set_description(description)
        await ctx.send("Done.")
