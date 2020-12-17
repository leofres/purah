from enum import Enum

from hero import fields


class Formats(Enum):
    single_elimination = 'single elimination'
    double_elimination = 'double elimination'
    round_robin = 'round robin'
    swiss = 'swiss'

    @classmethod
    async def convert(cls, ctx, argument):
        # may need to be converted to a challonge.TournamentType afterwards
        return Formats(argument)


class FormatField(fields.CharField):
    def __init__(self, **kwargs):
        kwargs['max_length'] = 32
        super().__init__(**kwargs)

    def get_prep_value(self, value: Formats) -> str:
        return value.value

    def from_db_value(self, value, expression, connection):
        return Formats(value)

    def to_python(self, value: str) -> Formats:
        if isinstance(value, Formats):
            return value
        try:
            return Formats(value)
        except ValueError:
            raise ValueError(
                "{format_value} is not a valid format".format(format_value=value)
            )

