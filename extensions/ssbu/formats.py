from challonge import TournamentType as Formats

from hero.fields import CharField


class FormatField(CharField):
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
                "{region_value} is not a valid region".format(region_value=value)
            )
