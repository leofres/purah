from hero import fields, models

from .doubles_match import DoublesMatch
from .tournament import Tournament


class ParticipantTeam(models.Model):
    challonge_id = fields.IntegerField(db_index=True)
    member_1 = fields.MemberField(on_delete=fields.CASCADE)
    member_2 = fields.MemberField(on_delete=fields.CASCADE)
    tournament = fields.ForeignKey(Tournament, on_delete=fields.CASCADE)
    current_match = fields.ForeignKey(DoublesMatch, null=True, on_delete=fields.SET_NULL)
    starting_elo = fields.IntegerField()
    starting_guild_elo = fields.IntegerField()
    match_count = fields.SmallIntegerField(default=0)
    forfeit_count = fields.SmallIntegerField(default=0)
