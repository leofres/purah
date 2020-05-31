from hero import fields, models

from .tournament_series import TournamentSeries


# by inheriting from models.Guild we extend the Guild with
# additional fields; this implicitly creates a OneToOne relationship
# and joins the database tables for us
class GuildSetup(models.Guild):
    main_series = fields.ForeignKey(TournamentSeries, null=True, on_delete=fields.SET_NULL)
    allow_matches_in_dms = fields.BooleanField(default=False)
    use_elo = fields.BooleanField(default=True)

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
