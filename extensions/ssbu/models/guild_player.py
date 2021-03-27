from hero import async_using_db, fields, models


class GuildPlayer(models.Model):
    member = fields.OneToOneField(models.Member, primary_key=True, on_delete=fields.CASCADE)
    rating = fields.IntegerField(db_index=True, default=1500)
    deviation = fields.IntegerField(default=350)
    volatility = fields.FloatField(default=0.06)

    @async_using_db
    def get_last_ranked_match(self):
        from ..models import Match

        guild = self.member.guild
        user = self.member.user
        qs = (
            Match.objects.filter(guild=guild, ranked=True, player_1=user)
            | Match.objects.filter(guild=guild, ranked=True, player_2=user)
        )
        return qs.latest()
