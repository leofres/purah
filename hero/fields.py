"""discord-hero: Discord Application Framework for humans

:copyright: (c) 2019-2020 monospacedmagic et al.
:license: Apache-2.0 OR MIT
"""

import discord

from django.db.models import (BigIntegerField, BooleanField, CharField, CASCADE,
                              DateField, DateTimeField, DecimalField, FloatField,
                              ForeignKey, IntegerField, ManyToManyField,
                              SET_DEFAULT, SET_NULL, SmallIntegerField, TextField)

from .i18n import Languages
from .errors import InactiveUser


class DiscordField(ForeignKey):
    _discord_cls = None
    _discord_obj = None

    def __init__(self, *args, **kwargs):
        # TODO investigate why this is needed
        try:
            kwargs.pop('to')
        except KeyError:
            pass
        super(DiscordField, self).__init__(type(self)._discord_cls.__name__,
                                           **kwargs)


class UserField(DiscordField):
    _discord_cls = discord.User

    def validate(self, value, model_instance):
        if value.is_inactive:
            raise InactiveUser(f"The user {value.id} is inactive")


class GuildField(DiscordField):
    _discord_cls = discord.Guild


class MemberField(DiscordField):
    _discord_cls = discord.Member


class TextChannelField(DiscordField):
    _discord_cls = discord.TextChannel


class VoiceChannelField(DiscordField):
    _discord_cls = discord.VoiceChannel


class RoleField(DiscordField):
    _discord_cls = discord.Role


class EmojiField(DiscordField):
    _discord_cls = discord.Emoji


class MessageField(DiscordField):
    _discord_cls = discord.Message


class ManyDiscordField(ManyToManyField):
    _discord_cls = None
    _discord_obj = None

    def __init__(self, *args, **kwargs):
        super(ManyDiscordField, self).__init__(type(self)._discord_cls.__name__, *args,
                                               **kwargs)


class ManyUsersField(ManyDiscordField):
    _discord_cls = discord.User


class ManyGuildsField(ManyDiscordField):
    _discord_cls = discord.Guild


class ManyTextChannelsField(ManyDiscordField):
    _discord_cls = discord.TextChannel


class ManyVoiceChannelsField(ManyDiscordField):
    _discord_cls = discord.VoiceChannel


class ManyRolesField(ManyDiscordField):
    _discord_cls = discord.Role


class ManyEmojisField(ManyDiscordField):
    _discord_cls = discord.Emoji


class ManyMembersField(ManyDiscordField):
    _discord_cls = discord.Member


class ManyMessagesField(ManyDiscordField):
    _discord_cls = discord.Message


class NamespaceField(ForeignKey):
    def __init__(self, **kwargs):
        super().__init__(to='CoreSettings', on_delete=CASCADE)


class LanguageField(CharField):
    def __init__(self, **kwargs):
        kwargs['max_length'] = 16
        kwargs['default'] = Languages.default
        super().__init__(**kwargs)

    def get_prep_value(self, value: Languages) -> str:
        return value.value

    def from_db_value(self, value, expression, connection):
        return Languages(value)

    def to_python(self, value: str) -> Languages:
        if isinstance(value, Languages):
            return value
        if value is None:
            return Languages.default
        try:
            return Languages(value)
        except ValueError:
            raise ValueError(
                "{language_value} is not a valid language".format(language_value=value)
            )


class SeparatedValuesField(TextField):
    def to_python(self, value):
        if not value:
            return ''
        if isinstance(value, list):
            return value
        return value.split(';')

    def get_prep_value(self, value):
        if not value:
            return ''
        return ';'.join(value)

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)
