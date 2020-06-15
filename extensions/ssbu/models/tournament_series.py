from challonge import TournamentType as Formats

from hero import fields, models

from ..formats import FormatField
from .player import Player
from .ruleset import Ruleset


def get_default_emoji():
    return models.Emoji(name='\u2705', is_custom=False)  # white_check_mark


class TournamentSeries(models.Model):
    class Meta:
        unique_together = (('name', 'guild'),)

    key_prefix = fields.CharField(primary_key=True, max_length=128)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    name = fields.CharField(max_length=128)
    next_iteration = fields.IntegerField(default=1)
    admins = fields.ManyToManyField(Player, null=True, blank=True, on_delete=fields.SET_NULL)
    participant_role = fields.RoleField(null=True, unique=True, on_delete=fields.SET_NULL)  # cancel tournament creation if not found on Discord
    organizer_role = fields.RoleField(null=True, on_delete=fields.SET_NULL)  # cancel tournament creation if not found on Discord
    streamer_role = fields.RoleField(null=True, blank=True, on_delete=fields.SET_NULL)  # delete if not found on Discord
    signup_emoji = fields.EmojiField(default=get_default_emoji, on_delete=fields.SET_DEFAULT)
    checkin_emoji = fields.EmojiField(default=get_default_emoji, on_delete=fields.SET_DEFAULT)
    announcements_channel = fields.TextChannelField(null=True, on_delete=fields.SET_NULL)  # if None, cancel tournament creation
    talk_channel = fields.TextChannelField(null=True, blank=True, on_delete=fields.SET_NULL)
    # introduction = fields.TextField(max_length=2048)
    default_participants_limit = fields.IntegerField(default=512)
    base_start_time = fields.DateTimeField(null=True, blank=True)
    every_x_weeks = fields.SmallIntegerField(null=True, blank=True)
    doubles = fields.BooleanField(db_index=True)
    format = FormatField(default=Formats.double_elimination)
    allow_matches_in_dms = fields.BooleanField()
    ruleset = fields.ForeignKey(Ruleset, null=True, blank=True, on_delete=fields.SET_NULL)
