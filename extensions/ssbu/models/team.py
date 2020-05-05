from hero import fields, models

from .participant_team import ParticipantTeam
from .player import Player
from .tournament import Tournament


class Team(models.Model):
    class Meta:
        unique_together = (('member_1', 'member_2'),)

    # member_1 is always the user with the lower user ID
    # to avoid duplicate teams
    member_1 = fields.ForeignKey(Player, db_index=True, on_delete=fields.CASCADE)
    member_2 = fields.ForeignKey(Player, db_index=True, on_delete=fields.CASCADE)
    custom_name = fields.CharField(null=True, max_length=64)
    current_tournament = fields.ForeignKey(Tournament, null=True, blank=True, on_delete=fields.SET_NULL)
    current_participant_team = fields.ForeignKey(ParticipantTeam, null=True, blank=True, on_delete=fields.SET_NULL)
    elo = fields.IntegerField(db_index=True, default=1000)
