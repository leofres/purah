from hero import fields, models

from .tournament_series import TournamentSeries


class Tournament(models.Model):
    challonge_id = fields.BigIntegerField(primary_key=True)
    announcements_channel = fields.TextChannelField(null=True, on_delete=fields.SET_NULL)
    talk_channel = fields.TextChannelField(null=True, on_delete=fields.SET_NULL)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    signup_message = fields.MessageField(unique=True, db_index=True, null=True, on_delete=fields.SET_NULL)
    checkin_message = fields.MessageField(unique=True, db_index=True, null=True, blank=True, on_delete=fields.SET_NULL)
    series = fields.ForeignKey(TournamentSeries, null=True, blank=True, db_index=True, on_delete=fields.SET_NULL)
    name = fields.CharField(max_length=128)
    url_key = fields.CharField(max_length=128)
    doubles = fields.BooleanField(db_index=True)
    allow_matches_in_dms = fields.BooleanField()
    starter_stages = fields.SeparatedValuesField()
    counterpick_stages = fields.SeparatedValuesField()
    counterpick_bans = fields.SmallIntegerField()
    dsr = fields.BooleanField()
    start_time = fields.DateTimeField(db_index=True)
