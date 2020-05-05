from hero import fields, models


class Tournament(models.Model):
    challonge_id = fields.BigIntegerField(primary_key=True)
    channel = fields.TextChannelField()
    guild = fields.GuildField()
    signup_message = fields.MessageField()

