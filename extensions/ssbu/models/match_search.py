from hero import fields, models

from .matchmaking_setup import MatchmakingSetup


class MatchSearch(models.Model):
    message = fields.OneToOneField(models.Message, primary_key=True, on_delete=fields.CASCADE)
    looking = fields.MemberField(on_delete=fields.CASCADE)
    setup = fields.ForeignKey(MatchmakingSetup, on_delete=fields.CASCADE)
