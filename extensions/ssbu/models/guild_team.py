from hero import fields, models

from .team import Team


class GuildTeam(models.Model):
    class Meta:
        unique_together = (('team', 'guild'),)

    team = fields.ForeignKey(Team, on_delete=fields.CASCADE)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)
    guild_elo = fields.IntegerField(db_index=True, default=1000)
