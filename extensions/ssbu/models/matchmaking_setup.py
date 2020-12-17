from hero import fields, models

from .ruleset import Ruleset


class MatchmakingSetup(models.Model):
    channel = fields.OneToOneField(models.TextChannel, primary_key=True, on_delete=fields.CASCADE)
    name = fields.CharField(max_length=64)
    matchmaking_message = fields.MessageField(on_delete=fields.CASCADE)
    ruleset = fields.ForeignKey(Ruleset, null=True, blank=True, on_delete=fields.SET_NULL)
    looking_role = fields.RoleField(on_delete=fields.CASCADE)
    available_role = fields.RoleField(on_delete=fields.CASCADE)
    ranked = fields.BooleanField(default=False)
