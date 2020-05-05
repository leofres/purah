from hero import fields, models


class TournamentSeries(models.Model):
    name = fields.CharField(max_length=128)
    next_iteration = fields.IntegerField(default=1)
    url_prefix = fields.CharField(max_length=128)
    announcements_channel = fields.TextChannelField(null=True, on_delete=fields.SET_NULL)
    talk_channel = fields.TextChannelField(null=True, on_delete=fields.SET_NULL)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    signup_message = fields.MessageField(unique=True, db_index=True, null=True, on_delete=fields.SET_NULL)
    checkin_message = fields.MessageField(unique=True, db_index=True, null=True, blank=True, on_delete=fields.SET_NULL)
    introduction = fields.TextField(max_length=2048)
    participants_limit = fields.IntegerField(null=True, blank=True)
    every_x_weeks = fields.SmallIntegerField(null=True, blank=True)
    doubles = fields.BooleanField(db_index=True)
    allow_matches_in_dms = fields.BooleanField()
    starter_stages = fields.SeparatedValuesField()
    counterpick_stages = fields.SeparatedValuesField()
    counterpick_bans = fields.SmallIntegerField()
    dsr = fields.BooleanField()
    first_start_time = fields.DateTimeField(null=True, blank=True)
