from hero import fields, models

from ..regions import RegionField


class Player(models.Model):
    user = fields.OneToOneField(models.User, primary_key=True, on_delete=fields.CASCADE)
    challonge_username = fields.CharField(null=True, blank=True, unique=True, max_length=64)
    challonge_user_id = fields.BigIntegerField(null=True, blank=True, unique=True)
    elo = fields.IntegerField(db_index=True, default=1000)
    region = RegionField(null=True, blank=True, db_index=True)
