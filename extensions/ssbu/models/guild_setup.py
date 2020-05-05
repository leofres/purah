from hero import fields, models

from ..stages import DEFAULT_STARTER_STAGES, DEFAULT_COUNTERPICK_STAGES


def get_default_emoji():
    return models.Emoji(name='\u2705')  # white_check_mark


# by inheriting from models.Guild we extend the Guild with
# additional fields; this implicitly creates a OneToOne relationship
# and joins the database tables for us
class GuildSetup(models.Guild):
    guild = fields.GuildField(primary_key=True)
    participant_role = fields.RoleField(null=True, blank=True, on_delete=fields.SET_NULL)
    organizer_role = fields.RoleField(null=True, blank=True, on_delete=fields.SET_NULL)
    streamer_role = fields.RoleField(null=True, blank=True, on_delete=fields.SET_NULL)
    default_allow_matches_in_dms = fields.BooleanField(default=False)
    default_starter_stages = fields.SeparatedValuesField(default=DEFAULT_STARTER_STAGES)
    default_counterpick_stages = fields.SeparatedValuesField(default=DEFAULT_COUNTERPICK_STAGES)
    default_counterpick_bans = fields.SmallIntegerField(default=2)
    default_dsr = fields.BooleanField(default=True)
    signup_emoji = fields.EmojiField(default=get_default_emoji)
    checkin_emoji = fields.EmojiField(default=get_default_emoji)
