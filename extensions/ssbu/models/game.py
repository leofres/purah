from hero import fields, models

from .match import Match
from .participant import Participant


class Game(models.Model):
    match = fields.ForeignKey(Match, null=True, on_delete=fields.SET_NULL)
    number = fields.SmallIntegerField()
    guild = fields.GuildField(null=True, on_delete=fields.SET_NULL)
    first_to_strike = fields.ForeignKey(Participant, null=True, on_delete=fields.SET_NULL)
    striking_message = fields.MessageField(null=True, on_delete=fields.SET_NULL)
    striked_stages = fields.SeparatedValuesField(default=[])
    suggested_stage = fields.SmallIntegerField(null=True, blank=True)
    suggested_by = fields.ForeignKey(Participant, null=True, on_delete=True)
    suggestion_accepted = fields.BooleanField(null=True, blank=True)
    picked_stage = fields.SmallIntegerField(null=True, blank=True)
    winner = fields.ForeignKey(Participant, null=True, blank=True, on_delete=fields.SET_NULL)
    needs_confirmation_by = fields.ForeignKey(Participant, null=True, blank=True, on_delete=fields.SET_NULL)
