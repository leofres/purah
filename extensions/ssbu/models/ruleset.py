from hero import fields, models

from ..stages import DEFAULT_STARTER_STAGES, DEFAULT_COUNTERPICK_STAGES


class Ruleset(models.Model):
    name = fields.CharField(max_length=128)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    starter_stages = fields.SeparatedValuesField(default=DEFAULT_STARTER_STAGES, max_length=64)
    counterpick_stages = fields.SeparatedValuesField(default=DEFAULT_COUNTERPICK_STAGES, max_length=64)
    counterpick_bans = fields.SmallIntegerField(default=2)
    dsr = fields.BooleanField(default=True)
