from hero import fields, models

from .tournament_series import TournamentSeries


# by inheriting from models.Guild we extend the Guild with
# additional fields; this implicitly creates a OneToOne relationship
# and joins the database tables for us
class GuildSetup(models.Model):
    guild = fields.OneToOneField(models.Guild, primary_key=True, on_delete=fields.CASCADE)
    main_series = fields.OneToOneField(TournamentSeries, null=True, blank=True, on_delete=fields.SET_NULL)
    allow_matches_in_dms = fields.BooleanField(default=False)
    use_elo = fields.BooleanField(default=True)
    show_elo = fields.BooleanField(default=True)
    verified = fields.BooleanField(default=False)  # only verified guilds affect global ELO of players
    ingame_role = fields.RoleField(null=True, blank=True, on_delete=fields.SET_NULL)
    player_1_blindpick_channel = fields.TextChannelField(null=True, blank=True, on_delete=fields.SET_NULL)
    player_2_blindpick_channel = fields.TextChannelField(null=True, blank=True, on_delete=fields.SET_NULL)

    NOT_FOUND_MESSAGE = "This server has not been set up yet, use the `to setup` command."

    @property
    def default_ruleset(self):
        return self.main_series.ruleset

    @property
    def participant_role(self):
        return self.main_series.participant_role

    @property
    def organizer_role(self):
        return self.main_series.organizer_role

    @property
    def streamer_role(self):
        return self.main_series.streamer_role
