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

    def get_prep_value(self, value: Regions):
        if value is None:
            return None
        return value.value

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return Regions(value)

    def to_python(self, value: str):
        if value is None:
            return None
        if isinstance(value, Regions):
            return value
        try:
            return Regions(value)
        except ValueError:
            raise ValueError(
                "{region_value} is not a valid region".format(region_value=value)
            )
