from hero import fields, models

from .doubles_match import DoublesMatch
from .participant_team import ParticipantTeam


class DoublesGame(models.Model):
    match = fields.ForeignKey(DoublesMatch, null=True, on_delete=fields.SET_NULL)
    number = fields.SmallIntegerField()
    guild = fields.GuildField(null=True, on_delete=fields.SET_NULL)
    first_to_strike = fields.ForeignKey(ParticipantTeam, null=True, on_delete=fields.SET_NULL)
    striking_message = fields.MessageField(null=True, on_delete=fields.SET_NULL)
    striked_stages = fields.SeparatedValuesField(default=[], max_length=64)
    suggested_stage = fields.SmallIntegerField(null=True, blank=True)
    suggested_by = fields.ForeignKey(ParticipantTeam, null=True, on_delete=fields.SET_NULL)
    suggestion_accepted = fields.BooleanField(null=True, blank=True)
    picked_stage = fields.SmallIntegerField(null=True, blank=True)
    winner = fields.ForeignKey(ParticipantTeam, null=True, blank=True, on_delete=fields.SET_NULL)
    needs_confirmation_by = fields.ForeignKey(ParticipantTeam, null=True, blank=True, on_delete=fields.SET_NULL)
