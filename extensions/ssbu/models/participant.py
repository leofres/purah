from hero import fields, models

from .tournament import Tournament


class Participant(models.Member):
    challonge_id = fields.IntegerField(db_index=True)
    tournament = fields.ForeignKey(Tournament, db_index=True, on_delete=fields.CASCADE)
    current_match = fields.ForeignKey('Match', null=True, blank=True, on_delete=fields.SET_NULL)
    starting_elo = fields.IntegerField()
    starting_guild_elo = fields.IntegerField()
    match_count = fields.SmallIntegerField(default=0)
    forfeit_count = fields.SmallIntegerField(default=0)
