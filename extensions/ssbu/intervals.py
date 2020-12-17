from enum import Enum

from hero import fields


class Intervals(Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    BIWEEKLY = 'biweekly'
    MONTHLY = 'monthly'

    @classmethod
    async def convert(cls, ctx, argument):
        return Intervals(argument)


class IntervalField(fields.CharField):
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
        return Intervals(value)

    def to_python(self, value: str):
        if value is None:
            return None
        if isinstance(value, Intervals):
            return value
        try:
            return Intervals(value)
        except ValueError:
            raise ValueError(
                "{interval_value} is not a valid interval".format(interval_value=value)
            )
