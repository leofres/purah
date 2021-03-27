from hero import fields, models

from .match import Match
from ..stages import Stage


class Game(models.Model):
    match = fields.ForeignKey(Match, null=True, on_delete=fields.SET_NULL)
    number = fields.SmallIntegerField()
    guild = fields.GuildField(null=True, db_index=True, on_delete=fields.SET_NULL)
    player_1_fighter = fields.SmallIntegerField(null=True, blank=True)
    player_2_fighter = fields.SmallIntegerField(null=True, blank=True)
    first_to_strike = fields.UserField(null=True, on_delete=fields.SET_NULL)
    striking_message = fields.MessageField(null=True, on_delete=fields.SET_NULL)
    striked_stages = fields.SeparatedValuesField(default=[], max_length=64,
                                                 converter=Stage.parse, serializer=Stage.serialize)
    suggested_stage = fields.SmallIntegerField(null=True, blank=True)
    suggested_by = fields.UserField(null=True, on_delete=fields.SET_NULL)
    suggestion_accepted = fields.BooleanField(null=True, blank=True)
    picked_stage = fields.SmallIntegerField(null=True, blank=True)
    winner = fields.UserField(null=True, blank=True, on_delete=fields.SET_NULL)
    needs_confirmation_by = fields.UserField(null=True, blank=True, on_delete=fields.SET_NULL)

    def is_striked(self, stage):
        return stage in self.striked_stages
