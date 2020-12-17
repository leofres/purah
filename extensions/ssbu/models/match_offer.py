from hero import fields, models

from .match_search import MatchSearch


class MatchOffer(models.Model):
    message = fields.OneToOneField(models.Message, primary_key=True, on_delete=fields.CASCADE)
    offering = fields.MemberField(on_delete=fields.CASCADE)
    offered_to = fields.MemberField(on_delete=fields.CASCADE)
