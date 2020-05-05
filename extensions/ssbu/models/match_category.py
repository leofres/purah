from hero import models, fields


class MatchCategory(models.CategoryChannel):
    class Meta:
        unique_together = (('guild', 'number'),)

    number = fields.SmallIntegerField(db_index=True)
