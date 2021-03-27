from datetime import datetime, timedelta

from hero import async_using_db, fields, models

from .matchmaking_setup import MatchmakingSetup
from .participant import Participant
from .ruleset import Ruleset
from .tournament import Tournament


class Match(models.Model):
    class Meta:
        get_latest_by = 'started_at'

    id = fields.BigAutoField(primary_key=True)
    channel = fields.TextChannelField(null=True, blank=True, db_index=True, unique=True, on_delete=fields.SET_NULL)
    guild = fields.GuildField(on_delete=fields.CASCADE)
    voice_channel = fields.VoiceChannelField(null=True, blank=True, on_delete=fields.SET_NULL)
    # if tournament is None, it's a matchmaking match
    tournament = fields.ForeignKey(Tournament, null=True, blank=True, on_delete=fields.CASCADE)
    setup = fields.ForeignKey(MatchmakingSetup, null=True, blank=True, on_delete=fields.SET_NULL)
    management_message = fields.MessageField(null=True, blank=True, on_delete=fields.SET_NULL)
    ranked = fields.BooleanField()
    in_dms = fields.BooleanField()
    # if matchmaking match, looking is player_1, offering is player_2
    player_1 = fields.UserField(db_index=True, on_delete=fields.CASCADE)
    player_1_rating = fields.IntegerField(null=True, blank=True)
    player_1_deviation = fields.IntegerField(null=True, blank=True)
    player_1_volatility = fields.FloatField(null=True, blank=True)
    player_1_global_rating = fields.IntegerField(null=True, blank=True)
    player_1_global_deviation = fields.IntegerField(null=True, blank=True)
    player_1_global_volatility = fields.FloatField(null=True, blank=True)
    player_1_score = fields.SmallIntegerField(default=0)
    player_2 = fields.UserField(db_index=True, on_delete=fields.CASCADE)
    player_2_rating = fields.IntegerField(null=True, blank=True)
    player_2_deviation = fields.IntegerField(null=True, blank=True)
    player_2_volatility = fields.FloatField(null=True, blank=True)
    player_2_global_rating = fields.IntegerField(null=True, blank=True)
    player_2_global_deviation = fields.IntegerField(null=True, blank=True)
    player_2_global_volatility = fields.FloatField(null=True, blank=True)
    player_2_score = fields.SmallIntegerField(default=0)
    current_game = fields.SmallIntegerField(default=1)
    wins_required = fields.SmallIntegerField(default=3)
    ruleset = fields.ForeignKey(Ruleset, null=True, blank=True, on_delete=fields.PROTECT)
    # if winner is None, match is active / ongoing
    # if winner is Purah, it was a friendly match
    winner = fields.UserField(null=True, blank=True, db_index=True, on_delete=fields.CASCADE)
    started_at = fields.DateTimeField(auto_now_add=True, db_index=True)
    ended_at = fields.DateTimeField(null=True, blank=True)
    spectating_message = fields.MessageField(null=True, blank=True, on_delete=fields.SET_NULL)
    match_end_message = fields.MessageField(null=True, blank=True, on_delete=fields.SET_NULL)

    @classmethod
    def ranked_matches_today_qs(cls, player_1, player_2, guild=None):
        one_day_ago = datetime.now() - timedelta(hours=18)  # let's be generous
        if guild is None:
            qs = (
                cls.objects.filter(started_at__gt=one_day_ago, tournament=None, ranked=True,
                                   player_1=player_1, player_2=player_2)
                | cls.objects.filter(started_at__gt=one_day_ago, tournament=None, ranked=True,
                                     player_1=player_2, player_2=player_1)
            )
        else:
            qs = (
                cls.objects.filter(guild=guild, started_at__gt=one_day_ago, tournament=None,
                                   ranked=True, player_1=player_1, player_2=player_2)
                | cls.objects.filter(guild=guild, started_at__gt=one_day_ago, tournament=None,
                                     ranked=True, player_1=player_2, player_2=player_1)
            )
        return qs

    @async_using_db
    def get_match_participants(self):
        if self.tournament is None:
            return None, None
        member_1 = models.Member.objects.get(user=self.player_1, guild=self.guild)
        participant_1 = Participant.objects.get(pk=member_1)
        member_2 = models.Member.objects.get(user=self.player_2, guild=self.guild)
        participant_2 = Participant.objects.get(pk=member_2)
        return participant_1, participant_2
