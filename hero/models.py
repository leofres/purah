"""discord-hero: Discord Application Framework for humans

:copyright: (c) 2019-2020 monospacedmagic et al.
:license: Apache-2.0 OR MIT
"""

import discord
from django.conf import settings as django_settings
from django.db import models

import hero
from hero import fields


class Model(models.Model):
    class Meta:
        abstract = True
        app_label = 'hero'

    _cached_core = None
    _is_loaded = False

    @property
    def _core(self):
        """The :class:`Core`. Should only be accessed from within the
        model class itself.
        """
        if self._cached_core is None:
            self._cached_core = hero.get_cache(django_settings.NAMESPACE).core
        return self._cached_core

    @property
    def _extension(self):
        if self._meta.app_label == 'hero':
            return None
        return self._core._extensions[self._meta.app_label]

    @property
    def is_loaded(self):
        return self._is_loaded

    def load(self):
        self.refresh_from_db()
        self._is_loaded = True


class CoreSettings(Model):
    name = fields.CharField(primary_key=True, max_length=64)
    prefixes = fields.SeparatedValuesField(max_length=256, default='!')
    description = fields.TextField(max_length=512, null=True)
    lang = fields.LanguageField()


class DiscordModel(Model):
    class Meta:
        abstract = True

    _discord_obj = None
    _discord_cls = None

    @classmethod
    def connect(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, cls.discord_cls):
            raise TypeError(f"discord_obj has to be a discord.{cls.discord_cls.__name__} "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(id=discord_obj.id)
        obj._discord_obj = discord_obj
        obj.load()
        return obj

    @classmethod
    def get(cls, *args, **kwargs):
        if isinstance(args[0], cls._discord_cls):
            if len(args) != 1:
                raise TypeError(f"Unexpected arguments {' '.join(args[1:])}")
            obj = super().get(id=args[0].id, **kwargs)
            obj._discord_obj = args[0]
            return obj
        return super().get(*args, **kwargs)

    @classmethod
    def get_or_create(cls, *args, **kwargs):
        if isinstance(args[0], cls._discord_cls):
            if len(args) != 1:
                raise TypeError(f"Unexpected arguments {' '.join(args[1:])}")
            obj = super().get_or_create(id=args[0].id, **kwargs)
            obj._discord_obj = args[0]
            return obj
        return super().get_or_create(*args, **kwargs)

    @classmethod
    def create(cls, *args, **kwargs):
        if isinstance(args[0], cls._discord_cls):
            if len(args) != 1:
                raise TypeError(f"Unexpected arguments {' '.join(args[1:])}")
            obj = super().create(id=args[0].id, **kwargs)
            obj._discord_obj = args[0]
            return obj
        return super().create(*args, **kwargs)

    @classmethod
    async def fetch(cls):
        raise NotImplemented

    @property
    def is_fetched(self):
        return self._discord_obj is not None

    def __getattr__(self, name):
        if hasattr(self._discord_obj, name):
            return getattr(self._discord_obj, name)

    def __dir__(self):
        tmp = super(DiscordModel, self).__dir__()

    def __str__(self):
        if self.is_fetched:
            return self.name
        else:
            return str(self.id)

    def __int__(self):
        return self.id

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return self.id


# USER_ACCESS_CACHE_KEY = "{user.id}_{queried_field}_{method}"


class User(DiscordModel):
    id = models.BigIntegerField(primary_key=True)
    is_staff = fields.BooleanField(default=False, db_index=True)
    is_active = fields.BooleanField(default=True, db_index=True)
    language = fields.LanguageField()

    _discord_cls = discord.User

    def delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)
        self.__class__.create(id=self.id, is_active=False)

    def load(self):
        super().load()
        if not self.is_active:
            raise self.InactiveUser(f"The user {self.id} is inactive")

    async def fetch(self) -> discord.User:
        if not self._is_loaded:
            self.load()
        discord_user = self._core.get_user(self.id)
        if discord_user is None:
            discord_user = await self._core.fetch_user(self.id)
        self._discord_obj = discord_user
        return discord_user


class Guild(DiscordModel):
    id = models.BigIntegerField(primary_key=True)
    home = models.BooleanField(default=False)
    register_time = models.DateTimeField(auto_now_add=True)
    invite_code = models.CharField(null=True, max_length=64, db_index=True)
    prefix = models.CharField(null=True, max_length=64)
    language = fields.LanguageField()
    members = models.ManyToManyField(to='User', through='Member')

    _discord_cls = discord.Guild

    @property
    def invite_url(self):
        return f'https://discord.gg/{self.invite_code}'

    @invite_url.setter
    def invite_url(self, value: str):
        if not isinstance(value, str):
            raise TypeError("invite_url must be a str")
        try:
            self.invite_code = value.split('://discord.gg/')[1]
        except IndexError:
            try:
                self.invite_code = value.split('://discordapp.com/invite/')[1]
            except IndexError:
                try:
                    self.invite_code = value.split('://discord.com/invite/')[1]
                except IndexError:
                    raise ValueError("Not a valid invite URL.")

    async def fetch(self) -> discord.Guild:
        discord_guild = self._core.get_guild(self.id)
        if discord_guild is None:
            discord_guild = await self._core.fetch_guild(self.id)
        self._discord_obj = discord_guild
        return discord_guild


class TextChannel(DiscordModel):
    id = models.BigIntegerField(primary_key=True)
    guild = fields.GuildField(on_delete=models.CASCADE)
    language = fields.LanguageField()

    _discord_cls = discord.TextChannel

    async def fetch(self) -> discord.TextChannel:
        discord_text_channel = self._core.get_channel(self.id)
        if discord_text_channel is None:
            discord_text_channel = await self._core.fetch_channel(self.id)
        self._discord_obj = discord_text_channel
        return discord_text_channel


class VoiceChannel(DiscordModel):
    id = models.BigIntegerField(primary_key=True)
    guild = fields.GuildField(on_delete=models.CASCADE)

    _discord_cls = discord.VoiceChannel

    async def fetch(self) -> discord.VoiceChannel:
        discord_voice_channel = self._core.get_channel(self.id)
        if discord_voice_channel is None:
            discord_voice_channel = await self._core.fetch_channel(self.id)
        self._discord_obj = discord_voice_channel
        return discord_voice_channel


class Role(DiscordModel):
    id = models.BigIntegerField(primary_key=True)
    guild = fields.GuildField(on_delete=models.CASCADE)

    _discord_cls = discord.Role

    async def fetch(self) -> discord.Role:
        discord_role = self.guild._discord_obj.get_role(self.id)
        if discord_role is None:
            discord_role = await self.guild._discord_obj.fetch_role(self.id)
        self._discord_obj = discord_role
        return discord_role


class Emoji(DiscordModel):
    id = models.BigIntegerField(primary_key=True)
    guild = fields.GuildField(on_delete=models.CASCADE)
    name = fields.CharField(max_length=64)
    animated = models.BooleanField()

    _discord_cls = discord.PartialEmoji

    async def fetch(self) -> discord.PartialEmoji:
        discord_emoji = self._core.get_channel(self.id)
        if discord_emoji is None:
            discord_emoji = await self._core.fetch_channel(self.id)
        self._discord_obj = discord_emoji
        return discord_emoji


class Member(DiscordModel):
    class Meta:
        unique_together = (('user', 'guild'),)

    auto_id = models.BigAutoField(primary_key=True)
    user = fields.UserField(on_delete=models.CASCADE)
    guild = fields.GuildField(on_delete=models.CASCADE)

    def __getattribute__(self, name):
        if name == 'id':
            _discord_obj = getattr(self, '_discord_obj', None)
            if _discord_obj is not None:
                return self._discord_obj.id
        return super().__getattribute__(name)

    _discord_cls = discord.Member

    @classmethod
    def connect(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, discord.Member):
            raise TypeError(f"discord_obj has to be a discord.Member "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(user=User.connect(discord_obj.user), guild=Guild.connect(discord_obj.guild))
        obj._discord_obj = discord_obj
        obj.load()
        return obj


class Message(DiscordModel):
    id = models.BigIntegerField(primary_key=True)
    channel = fields.TextChannelField(db_index=True, on_delete=models.CASCADE)
    author = fields.UserField(db_index=True, on_delete=models.CASCADE)
    guild = fields.GuildField(db_index=True, on_delete=models.CASCADE)

    _discord_cls = discord.Message


class Settings(Model):
    class Meta:
        abstract = True

    namespace = fields.NamespaceField(primary_key=True)
