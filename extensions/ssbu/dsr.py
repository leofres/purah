from enum import Enum

from hero import fields

from .stages import Stage


class DSR(Enum):
    off = 'off'
    on = 'on'
    modified = 'modified'

    async def get_dsr_stages(self, match):
        from .models import Game, Match
        match: Match

        if self is DSR.off:
            return []

        games_qs = Game.objects.filter(match=match)
        num_games = await games_qs.async_count()
        if num_games <= 2:
            return []

        player_1 = await match.player_1
        player_2 = await match.player_2
        current_game = await Game.objects.async_get(match=match, number=num_games)
        striking = await current_game.first_to_strike
        if player_1.id == striking.id:
            picking = player_2
        else:
            picking = player_1

        games: list = await games_qs.filter(winner=picking).async_to_list()
        if self is DSR.on:
            return [Stage(game.picked_stage) for game in games]
        if self is DSR.modified:
            if games:
                return [Stage(games[-1].picked_stage)]
            return []


class DSRField(fields.CharField):
    def __init__(self, **kwargs):
        kwargs['max_length'] = 32
        super().__init__(**kwargs)

    def get_prep_value(self, value):
        if value is None:
            return None
        return value.value

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return DSR(value)

    def to_python(self, value: str):
        if value is None:
            return None
        if isinstance(value, DSR):
            return value
        try:
            return DSR(value)
        except ValueError:
            raise ValueError(
                "{dsr_value} is not a valid DSR setting".format(dsr_value=value)
            )
