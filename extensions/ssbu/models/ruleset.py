from discord.ext.commands import BadArgument

from hero import fields, models

from ..dsr import DSR, DSRField
from ..stages import Stage


class Ruleset(models.Model):
    class Meta:
        unique_together = (('name', 'guild', 'version'),)
        get_latest_by = 'version'

    name = fields.CharField(max_length=128)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    version = fields.IntegerField(default=1)
    starter_stages = fields.SeparatedValuesField(default=Stage.get_default_starters, max_length=64,
                                                 converter=Stage.parse, serializer=Stage.serialize)
    counterpick_stages = fields.SeparatedValuesField(default=Stage.get_default_counterpicks, max_length=64,
                                                     converter=Stage.parse, serializer=Stage.serialize)
    counterpick_bans = fields.SmallIntegerField(default=2)
    dsr = DSRField(default=DSR('on'))

    @classmethod
    async def convert(cls, ctx, argument):
        try:
            argument = int(argument)
        except ValueError:
            raise BadArgument(f"{argument} is not a valid identifier for a ruleset")
        return await cls.async_get(pk=argument)

    def __str__(self):
        return self.name
