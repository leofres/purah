from hero import fields, models


class GuildPlayer(models.Model):
    member = fields.OneToOneField(models.Member, primary_key=True, on_delete=fields.CASCADE)
    guild_elo = fields.IntegerField(db_index=True, default=1000)
