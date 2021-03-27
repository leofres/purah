from hero import fields, models

from ...scheduler.models import ScheduledTask
from . import get_default_emoji
from .tournament_series import TournamentSeries
from .ruleset import Ruleset
from ..formats import Formats, FormatField


class Tournament(models.Model):
    id = fields.BigIntegerField(primary_key=True)  # Challonge ID
    key = fields.CharField(max_length=128, unique=True)
    name = fields.CharField(max_length=128)
    series = fields.ForeignKey(TournamentSeries, null=True, blank=True, db_index=True, on_delete=fields.SET_NULL)
    ranked = fields.BooleanField()
    signup_message = fields.MessageField(unique=True, db_index=True, null=True, on_delete=fields.SET_NULL)
    checkin_message = fields.MessageField(unique=True, db_index=True, null=True, blank=True, on_delete=fields.SET_NULL)
    # signup_emoji = fields.EmojiField(default=get_default_emoji, on_delete=fields.SET_DEFAULT)
    # checkin_emoji = fields.EmojiField(default=get_default_emoji, on_delete=fields.SET_DEFAULT)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    announcements_channel = fields.TextChannelField(null=True, on_delete=fields.SET_NULL)
    talk_channel = fields.TextChannelField(null=True, blank=True, on_delete=fields.SET_NULL)
    participant_role = fields.RoleField(null=True, unique=True, on_delete=fields.SET_NULL)
    organizer_role = fields.RoleField(null=True, on_delete=fields.SET_NULL)
    streamer_role = fields.RoleField(null=True, blank=True, on_delete=fields.SET_NULL)
    doubles = fields.BooleanField(db_index=True)
    format = FormatField(default=Formats.double_elimination)
    allow_matches_in_dms = fields.BooleanField()
    # don't hard delete rulesets that have already been used
    # instead, the ruleset should be swapped out with the updated version
    # and only for upcoming and ongoing tournaments
    ruleset = fields.ForeignKey(Ruleset, on_delete=fields.PROTECT)
    start_time = fields.DateTimeField(db_index=True)
    delay_start = fields.SmallIntegerField(null=True, blank=True)  # minutes
    start_task = fields.ForeignKey(ScheduledTask, null=True, on_delete=fields.SET_NULL)
    start_checkin_task = fields.ForeignKey(ScheduledTask, null=True, on_delete=fields.SET_NULL)
    check_reactions_task = fields.ForeignKey(ScheduledTask, null=True, on_delete=fields.SET_NULL)
    ended = fields.BooleanField(db_index=True, default=False)

    @property
    def full_challonge_url(self):
        return f"https://challonge.com/{self.key}"

    async def get_challonge_tournament(self):
        core = self._core
        extension_name = self._meta.app_label
        ssbu = core.get_controller(extension_name)
        return await ssbu.get_challonge_tournament(self.id)

    @classmethod
    async def convert(cls, ctx, argument):
        try:
            argument = int(argument)
            # argument is Challonge ID
            tournament = await cls.async_get(pk=argument)
        except ValueError:
            # argument is URL key
            tournament = await cls.async_get(key=argument)
        return tournament
