from hero import fields, models


class GuildPlayer(models.Member):
    guild_elo = fields.IntegerField(db_index=True, default=1000)
