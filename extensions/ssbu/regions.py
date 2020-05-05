import enum

from hero.fields import CharField


class Regions(enum.Enum):
    AFRICA = 'af'
    ASIA = 'as'
    EUROPE = 'eu'
    NORTH_AMERICA = 'na'
    OCEANIA = 'oc'
    SOUTH_AMERICA = 'sa'


class RegionField(CharField):
    def __init__(self, **kwargs):
        kwargs['max_length'] = 2
        super().__init__(**kwargs)

    def get_prep_value(self, value: Regions) -> str:
        return value.value

    def from_db_value(self, value, expression, connection):
        return Regions(value)

    def to_python(self, value: str) -> Regions:
        if isinstance(value, Regions):
            return value
        try:
            return Regions(value)
        except ValueError:
            raise ValueError(
                "{region_value} is not a valid language".format(region_value=value)
            )
