from hero import fields, models

from .participant import Participant
from .tournament import Tournament


class Match(models.Model):
    id = fields.BigIntegerField(primary_key=True)
    channel = fields.TextChannelField(null=True, db_index=True, unique=True, on_delete=fields.SET_NULL)
    guild = fields.GuildField(on_delete=fields.CASCADE)
    # if tournament is None, it's a matchmaking match
    tournament = fields.ForeignKey(Tournament, null=True, blank=True, on_delete=fields.CASCADE)
    in_dms = fields.BooleanField()
    player_1 = fields.ForeignKey(Participant, on_delete=fields.CASCADE)
    player_2 = fields.ForeignKey(Participant, on_delete=fields.CASCADE)
    player_1_score = fields.SmallIntegerField(default=0)
    player_2_score = fields.SmallIntegerField(default=0)
    current_game = fields.SmallIntegerField(default=1)
    last_game_won_by = fields.SmallIntegerField(null=True)
    wins_required = fields.SmallIntegerField(default=2)
    winner = fields.ForeignKey(Participant, null=True, blank=True, on_delete=fields.CASCADE)
