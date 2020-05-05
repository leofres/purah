from hero import fields, models


class SsbuSettings(models.Settings):
    challonge_username = fields.CharField(max_length=64)
    challonge_api_key = fields.CharField(max_length=128)
