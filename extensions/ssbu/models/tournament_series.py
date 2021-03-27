import datetime

from challonge import TournamentType as Formats

from discord.ext.commands import BadArgument

from hero import fields, models, ObjectDoesNotExist

from ..fields import FormatField, IntervalField
from ..intervals import Intervals
from . import get_default_emoji
from .player import Player
from .ruleset import Ruleset


class TournamentSeries(models.Model):
    class Meta:
        unique_together = (('name', 'guild'),)

    key_prefix = fields.CharField(primary_key=True, max_length=128)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    name = fields.CharField(max_length=128)
    next_iteration = fields.IntegerField(default=1)
    ranked = fields.BooleanField()
    admins = fields.ManyToManyField(Player, null=True, blank=True)
    participant_role = fields.RoleField(null=True, unique=True, on_delete=fields.SET_NULL)  # cancel tournament creation if not found on Discord
    organizer_role = fields.RoleField(null=True, on_delete=fields.SET_NULL)  # cancel tournament creation if not found on Discord
    streamer_role = fields.RoleField(null=True, blank=True, on_delete=fields.SET_NULL)  # delete if not found on Discord
    # signup_emoji = fields.EmojiField(default=get_default_emoji, on_delete=fields.SET_DEFAULT)
    # checkin_emoji = fields.EmojiField(default=get_default_emoji, on_delete=fields.SET_DEFAULT)
    announcements_channel = fields.TextChannelField(null=True, on_delete=fields.SET_NULL)  # if None, cancel tournament creation
    talk_channel = fields.TextChannelField(null=True, blank=True, on_delete=fields.SET_NULL)
    introduction = fields.TextField(max_length=2048)
    default_participants_limit = fields.IntegerField(default=512)
    last_start_time = fields.DateTimeField(null=True, blank=True)
    delay_start = fields.SmallIntegerField(null=True, blank=True)  # minutes
    interval = IntervalField(null=True, blank=True)
    doubles = fields.BooleanField(db_index=True)
    format = FormatField(default=Formats.double_elimination)
    affects_elo = fields.BooleanField(default=True)
    allow_matches_in_dms = fields.BooleanField()
    ruleset = fields.ForeignKey(Ruleset, null=True, blank=True, on_delete=fields.SET_NULL)

    cancelled = fields.BooleanField(default=False)

    @property
    def next_start_time(self):
        self.last_start_time: datetime.datetime
        if self.last_start_time is None or self.interval is None:
            return None
        if self.interval == Intervals.MONTHLY:
            weekday = self.last_start_time.weekday()
            day_number = self.last_start_time.day

    @classmethod
    async def convert(cls, ctx, argument):
        try:
            tournament_series = await cls.async_get(pk=argument)
        except ObjectDoesNotExist:
            try:
                guild = await models.Guild.from_discord_obj(ctx.guild)
                tournament_series = await cls.async_get(guild=guild, name=argument)
            except ObjectDoesNotExist:
                raise BadArgument(f"{argument} does not seem to be a valid tournament series.")
        return tournament_series
