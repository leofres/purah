from hero import models, fields


class MatchCategory(models.Model):
    category = fields.OneToOneField(models.CategoryChannel, primary_key=True, on_delete=fields.CASCADE)
    number = fields.SmallIntegerField()
