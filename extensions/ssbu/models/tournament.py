from challonge import TournamentType as Formats

from hero import async_using_db, fields, models

from .tournament_series import TournamentSeries
from .ruleset import Ruleset
from ..formats import FormatField


class Tournament(models.Model):
    id = fields.BigIntegerField(primary_key=True)  # Challonge ID
    key = fields.CharField(max_length=128, unique=True)
    name = fields.CharField(max_length=128)
    series = fields.ForeignKey(TournamentSeries, null=True, blank=True, db_index=True, on_delete=fields.SET_NULL)
    signup_message = fields.MessageField(unique=True, db_index=True, null=True, on_delete=fields.SET_NULL)
    checkin_message = fields.MessageField(unique=True, db_index=True, null=True, blank=True, on_delete=fields.SET_NULL)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    announcements_channel = fields.TextChannelField(null=True, on_delete=fields.SET_NULL)
    talk_channel = fields.TextChannelField(null=True, blank=True, on_delete=fields.SET_NULL)
    participant_role = fields.RoleField(null=True, unique=True, on_delete=fields.SET_NULL)
    organizer_role = fields.RoleField(null=True, on_delete=fields.SET_NULL)
    streamer_role = fields.RoleField(null=True, blank=True, on_delete=fields.SET_NULL)
    doubles = fields.BooleanField(db_index=True)
    format = FormatField(default=Formats.double_elimination)
    allow_matches_in_dms = fields.BooleanField()
    ruleset = fields.ForeignKey(Ruleset, on_delete=fields.SET_DEFAULT)
    start_time = fields.DateTimeField(db_index=True)
    ended = fields.BooleanField(db_index=True, default=False)

    @async_using_db
    @classmethod
    def convert(cls, ctx, argument):
        try:
            argument = int(argument)
            # argument is Challonge ID
            tournament = cls(id=argument)
            tournament.load(prefetch_related=False)
        except ValueError:
            # argument is URL key
            qs = cls.objects.filter(key=str(argument))
            tournament = qs.first()
        return tournament
