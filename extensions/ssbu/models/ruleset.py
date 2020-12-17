from discord.ext.commands import BadArgument

from hero import fields, models

from ..stages import Stage


class Ruleset(models.Model):
    class Meta:
        unique_together = (('name', 'guild'),)

    name = fields.CharField(max_length=128)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    starter_stages = fields.SeparatedValuesField(default=Stage.get_default_starters, max_length=64,
                                                 converter=Stage.parse, serializer=Stage.serialize)
    counterpick_stages = fields.SeparatedValuesField(default=Stage.get_default_counterpicks, max_length=64,
                                                     converter=Stage.parse, serializer=Stage.serialize)
    counterpick_bans = fields.SmallIntegerField(default=2)
    dsr = fields.BooleanField(default=True)

    @classmethod
    async def convert(cls, ctx, argument):
        try:
            argument = int(argument)
        except ValueError:
            raise BadArgument(f"{argument} is not a valid identifier for a ruleset")
        return await cls.async_get(pk=argument)
