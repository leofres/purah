from hero import async_using_db, fields, models

from ..regions import RegionField


class Player(models.Model):
    user = fields.OneToOneField(models.User, primary_key=True, on_delete=fields.CASCADE)
    challonge_username = fields.CharField(null=True, blank=True, unique=True, max_length=64)
    challonge_user_id = fields.BigIntegerField(null=True, blank=True, unique=True)
    region = RegionField(null=True, blank=True, db_index=True)
    rating = fields.IntegerField(db_index=True, default=1500)
    deviation = fields.IntegerField(default=350)
    volatility = fields.FloatField(default=0.06)

    @async_using_db
    def get_last_ranked_match(self):
        from ..models import Match
        user = self.user
        qs = (
            Match.objects.filter(guild__guildsetup__verified=True, ranked=True, player_1=user)
            | Match.objects.filter(guild__guildsetup__verified=True, ranked=True, player_2=user)
        )
        return qs.latest()
