"""discord-hero: Discord Application Framework for humans

:copyright: (c) 2019-2020 monospacedmagic et al.
:license: Apache-2.0 OR MIT
"""

# temporary fix until Django's ORM is async
from asgiref.sync import sync_to_async

import discord
from django.conf import settings as django_settings
from django.core.exceptions import NON_FIELD_ERRORS
from django.db import connection, connections, models as _models, transaction
from django.db.models.constants import LOOKUP_SEP
from django.db.models.expressions import Case, Expression, Value, When
from django.db.models.functions import Cast

import hero
from hero import fields


class QuerySet(_models.QuerySet):
    @sync_to_async
    def get(self, *args, **kwargs):
        return super(QuerySet, self).get(*args, **kwargs)

    def sync_get(self, *args, **kwargs):
        return super(QuerySet, self).get(*args, **kwargs)

    @sync_to_async
    def create(self, *args, **kwargs):
        self.create(*args, **kwargs)

    def sync_create(self, *args, **kwargs):
        obj = self.model(**kwargs)
        self._for_write = True
        obj.sync_save(force_insert=True, using=self.db)
        return obj

    async def get_or_create(self, *args, **kwargs):
        return await self._get_or_create(*args, **kwargs)

    @sync_to_async
    def _get_or_create(self, *args, **kwargs):
        return super(QuerySet, self).get_or_create(*args, **kwargs)

    def sync_get_or_create(self, *args, **kwargs):
        return super(QuerySet, self).get_or_create(*args, **kwargs)

    @sync_to_async
    def update_or_create(self, defaults=None, **kwargs):
        self.sync_update_or_create(defaults=defaults, **kwargs)

    def sync_update_or_create(self, defaults=None, **kwargs):
        defaults = defaults or {}
        self._for_write = True
        with transaction.atomic(using=self.db):
            try:
                obj = self.select_for_update().sync_get(**kwargs)
            except self.model.DoesNotExist:
                params = self._extract_model_params(defaults, **kwargs)
                # Lock the row so that a concurrent update is blocked until
                # after update_or_create() has performed its save.
                obj, created = self._create_object_from_params(kwargs, params, lock=True)
                if created:
                    return obj, created
            for k, v in defaults.items():
                setattr(obj, k, v() if callable(v) else v)
            obj.sync_save(using=self.db)
        return obj, False

    @sync_to_async
    def bulk_create(self, *args, **kwargs):
        return super(QuerySet, self).bulk_create(*args, **kwargs)

    def sync_bulk_create(self, *args, **kwargs):
        return super(QuerySet, self).bulk_create(*args, **kwargs)

    # have to reimplement this because there is a query method call (update)
    # in there which has to be changed to sync_update
    @sync_to_async
    def bulk_update(self, objs, _fields, batch_size=None):
        return self.sync_bulk_update(objs, _fields, batch_size=None)

    def sync_bulk_update(self, objs, _fields, batch_size=None):
        if batch_size is not None and batch_size < 0:
            raise ValueError('Batch size must be a positive integer.')
        if not _fields:
            raise ValueError('Field names must be given to bulk_update().')
        objs = tuple(objs)
        if any(obj.pk is None for obj in objs):
            raise ValueError('All bulk_update() objects must have a primary key set.')
        _fields = [self.model._meta.get_field(name) for name in _fields]
        if any(not f.concrete or f.many_to_many for f in _fields):
            raise ValueError('bulk_update() can only be used with concrete fields.')
        if any(f.primary_key for f in _fields):
            raise ValueError('bulk_update() cannot be used with primary key fields.')
        if not objs:
            return
        # PK is used twice in the resulting update query, once in the filter
        # and once in the WHEN. Each field will also have one CAST.
        max_batch_size = connections[self.db].ops.bulk_batch_size(['pk', 'pk'] + _fields, objs)
        batch_size = min(batch_size, max_batch_size) if batch_size else max_batch_size
        requires_casting = connections[self.db].features.requires_casted_case_in_updates
        batches = (objs[i:i + batch_size] for i in range(0, len(objs), batch_size))
        updates = []
        for batch_objs in batches:
            update_kwargs = {}
            for _field in _fields:
                when_statements = []
                for obj in batch_objs:
                    attr = getattr(obj, _field.attname)
                    if not isinstance(attr, Expression):
                        attr = Value(attr, output_field=_field)
                    when_statements.append(When(pk=obj.pk, then=attr))
                case_statement = Case(*when_statements, output_field=_field)
                if requires_casting:
                    case_statement = Cast(case_statement, output_field=_field)
                update_kwargs[_field.attname] = case_statement
            updates.append(([obj.pk for obj in batch_objs], update_kwargs))
        with transaction.atomic(using=self.db, savepoint=False):
            for pks, update_kwargs in updates:
                self.filter(pk__in=pks).sync_update(**update_kwargs)
    sync_bulk_update.alters_data = True

    @sync_to_async
    def count(self):
        return super(QuerySet, self).count()

    def sync_count(self):
        return super(QuerySet, self).count()

    @sync_to_async
    def in_bulk(self, *args, **kwargs):
        return super(QuerySet, self).in_bulk(*args, **kwargs)

    def sync_in_bulk(self, *args, **kwargs):
        return super(QuerySet, self).in_bulk(*args, **kwargs)

    @sync_to_async
    def iterator(self, *args, **kwargs):
        return super(QuerySet, self).iterator(*args, **kwargs)

    def __aiter__(self):
        return sync_to_async(self.__iter__, thread_sensitive=True)()

    async def latest(self, *args, **kwargs):
        return await self._latest(*args, **kwargs)

    @sync_to_async
    def _latest(self, *args, **kwargs):
        return super(QuerySet, self).latest(*args)

    def sync_latest(self, *args, **kwargs):
        return super(QuerySet, self).latest(*args)

    async def earliest(self, *args, **kwargs):
        return await self.__earliest(*args, **kwargs)

    @sync_to_async
    def __earliest(self, *args, **kwargs):
        return super(QuerySet, self).earliest(*args)

    def sync_earliest(self, *args, **kwargs):
        return super(QuerySet, self).earliest(*args)

    async def first(self):
        await self._first()

    @sync_to_async
    def _first(self):
        return super(QuerySet, self).first()

    def sync_first(self):
        return super(QuerySet, self).first()

    async def last(self):
        await self._last()

    @sync_to_async
    def _last(self):
        return super(QuerySet, self).last()

    def sync_last(self):
        return super(QuerySet, self).last()

    @sync_to_async
    def aggregate(self, *args, **kwargs):
        return super(QuerySet, self).aggregate(*args, **kwargs)

    def sync_aggregate(self, *args, **kwargs):
        return super(QuerySet, self).aggregate(*args, **kwargs)

    @sync_to_async
    def exists(self):
        return super(QuerySet, self).exists()

    def sync_exists(self):
        return super(QuerySet, self).exists()

    @sync_to_async
    def update(self, *args, **kwargs):
        return super(QuerySet, self).update(**kwargs)

    def sync_update(self, *args, **kwargs):
        return super(QuerySet, self).update(**kwargs)

    @sync_to_async
    def delete(self, *args, **kwargs):
        return super(QuerySet, self).delete()

    def sync_delete(self, *args, **kwargs):
        return super(QuerySet, self).delete()


class Manager(_models.manager.BaseManager.from_queryset(QuerySet)):
    pass


class Model(_models.Model):
    class Meta:
        abstract = True
        # app_label = 'hero'
        base_manager_name = 'objects'
        default_manager_name = 'custom_default_manager'

    objects = Manager()
    custom_default_manager = Manager()
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
        return self._core.__extensions[self._meta.app_label]

    @property
    def is_loaded(self):
        return self._is_loaded

    @sync_to_async
    def load(self):
        self.refresh_from_db()
        self._is_loaded = True

    def sync_load(self):
        self.refresh_from_db()
        self._is_loaded = True

    @sync_to_async
    def save(self, validate=True, **kwargs):
        if validate:
            self.validate()
        super().save(**kwargs)

    def sync_save(self, validate=True, **kwargs):
        if validate:
            self.sync_validate()
        super().save(**kwargs)

    @sync_to_async
    def validate(self):
        self.full_clean()

    def sync_validate(self):
        self.full_clean()

    @sync_to_async
    def delete(self, keep_parents=False, **kwargs):
        super().delete(keep_parents=keep_parents, **kwargs)

    def sync_delete(self, keep_parents=False, **kwargs):
        super().delete(keep_parents=keep_parents, **kwargs)

    @sync_to_async
    @classmethod
    def get(cls, **kwargs):
        return cls.objects.get(**kwargs)

    @classmethod
    def sync_get(cls, **kwargs):
        return cls.objects.get(**kwargs)

    @sync_to_async
    @classmethod
    def create(cls, **kwargs):
        return cls.objects.create(**kwargs)

    @classmethod
    def sync_create(cls, **kwargs):
        return cls.objects.create(**kwargs)

    @sync_to_async
    @classmethod
    def get_or_create(cls, defaults=None, **kwargs):
        return cls.objects.get_or_create(defaults=defaults, **kwargs)

    @classmethod
    def sync_get_or_create(cls, defaults=None, **kwargs):
        return cls.objects.get_or_create(defaults=defaults, **kwargs)

    @sync_to_async
    @classmethod
    def update_or_create(cls, defaults=None, **kwargs):
        return cls.objects.update_or_create(defaults=defaults, **kwargs)

    @classmethod
    def sync_update_or_create(cls, defaults=None, **kwargs):
        return cls.objects.update_or_create(defaults=defaults, **kwargs)

    def refresh_from_db(self, using=None, fields=None):
        """
        Reload field values from the database.

        By default, the reloading happens from the database this instance was
        loaded from, or by the read router if this instance wasn't loaded from
        any database. The using parameter will override the default.

        Fields can be used to specify which fields to reload. The fields
        should be an iterable of field attnames. If fields is None, then
        all non-deferred fields are reloaded.

        When accessing deferred fields of an instance, the deferred loading
        of the field will call this method.
        """
        if fields is None:
            self._prefetched_objects_cache = {}
        else:
            prefetched_objects_cache = getattr(self, '_prefetched_objects_cache', ())
            for field in fields:
                if field in prefetched_objects_cache:
                    del prefetched_objects_cache[field]
                    fields.remove(field)
            if not fields:
                return
            if any(LOOKUP_SEP in f for f in fields):
                raise ValueError(
                    'Found "%s" in fields argument. Relations and transforms '
                    'are not allowed in fields.' % LOOKUP_SEP)

        hints = {'instance': self}
        db_instance_qs = self.__class__._base_manager.db_manager(using, hints=hints).filter(pk=self.pk)

        # Use provided fields, if not set then reload all non-deferred fields.
        deferred_fields = self.get_deferred_fields()
        if fields is not None:
            fields = list(fields)
            db_instance_qs = db_instance_qs.only(*fields)
        elif deferred_fields:
            fields = [f.attname for f in self._meta.concrete_fields
                      if f.attname not in deferred_fields]
            db_instance_qs = db_instance_qs.only(*fields)

        db_instance = db_instance_qs.sync_get()
        non_loaded_fields = db_instance.get_deferred_fields()
        for field in self._meta.concrete_fields:
            if field.attname in non_loaded_fields:
                # This field wasn't refreshed - skip ahead.
                continue
            setattr(self, field.attname, getattr(db_instance, field.attname))
            # Clear cached foreign keys.
            if field.is_relation and field.is_cached(self):
                field.delete_cached_value(self)

        # Clear cached relations.
        for field in self._meta.related_objects:
            if field.is_cached(self):
                field.delete_cached_value(self)

        self._state.db = db_instance._state.db

    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        """
        Try to update the model. Return True if the model was updated (if an
        update query was done and a matching row was found in the DB).
        """
        filtered = base_qs.filter(pk=pk_val)
        if not values:
            # We can end up here when saving a model in inheritance chain where
            # update_fields doesn't target any field in current model. In that
            # case we just say the update succeeded. Another case ending up here
            # is a model with just PK - in that case check that the PK still
            # exists.
            return update_fields is not None or filtered.sync_exists()
        if self._meta.select_on_save and not forced_update:
            return (
                filtered.sync_exists() and
                # It may happen that the object is deleted from the DB right after
                # this check, causing the subsequent UPDATE to return zero matching
                # rows. The same result can occur in some rare cases when the
                # database returns zero despite the UPDATE being executed
                # successfully (a row is matched and updated). In order to
                # distinguish these two cases, the object's existence in the
                # database is again checked for if the UPDATE query returns 0.
                (filtered._update(values) > 0 or filtered.sync_exists())
            )
        return filtered._update(values) > 0

    def _perform_unique_checks(self, unique_checks):
        errors = {}

        for model_class, unique_check in unique_checks:
            # Try to look up an existing object with the same values as this
            # object's values for all the unique field.

            lookup_kwargs = {}
            for field_name in unique_check:
                f = self._meta.get_field(field_name)
                lookup_value = getattr(self, f.attname)
                # TODO: Handle multiple backends with different feature flags.
                if (lookup_value is None or
                    (lookup_value == '' and connection.features.interprets_empty_strings_as_nulls)):
                    # no value, skip the lookup
                    continue
                if f.primary_key and not self._state.adding:
                    # no need to check for unique primary key when editing
                    continue
                lookup_kwargs[str(field_name)] = lookup_value

            # some fields were skipped, no reason to do the check
            if len(unique_check) != len(lookup_kwargs):
                continue

            qs = model_class._default_manager.filter(**lookup_kwargs)

            # Exclude the current object from the query if we are editing an
            # instance (as opposed to creating a new one)
            # Note that we need to use the pk as defined by model_class, not
            # self.pk. These can be different fields because model inheritance
            # allows single model to have effectively multiple primary keys.
            # Refs #17615.
            model_class_pk = self._get_pk_val(model_class._meta)
            if not self._state.adding and model_class_pk is not None:
                qs = qs.exclude(pk=model_class_pk)
            if qs.sync_exists():
                if len(unique_check) == 1:
                    key = unique_check[0]
                else:
                    key = NON_FIELD_ERRORS
                errors.setdefault(key, []).append(self.unique_error_message(model_class, unique_check))

        return errors


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
    async def from_discord_obj(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, cls.discord_cls):
            raise TypeError(f"discord_obj has to be a discord.{cls.discord_cls.__name__} "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(id=discord_obj.id)
        obj._discord_obj = discord_obj
        await obj.load()
        return obj

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
        return hash(self.id)


# USER_ACCESS_CACHE_KEY = "{user.id}_{queried_field}_{method}"


class User(DiscordModel):
    id = fields.BigIntegerField(primary_key=True)
    is_staff = fields.BooleanField(default=False, db_index=True)
    is_active = fields.BooleanField(default=True, db_index=True)
    language = fields.LanguageField()

    _discord_cls = discord.User

    @sync_to_async
    def delete(self, using=None, keep_parents=False):
        super().sync_delete(using=using, keep_parents=keep_parents)
        self.__class__.create(id=self.id, is_active=False)

    def sync_delete(self, using=None, keep_parents=False):
        super().sync_delete(using=using, keep_parents=keep_parents)
        self.__class__.create(id=self.id, is_active=False)

    @sync_to_async
    def load(self):
        super().sync_load()
        if not self.is_active:
            raise self.InactiveUser(f"The user {self.id} is inactive")

    def sync_load(self):
        super().sync_load()
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
    id = fields.BigIntegerField(primary_key=True)
    home = fields.BooleanField(default=False)
    register_time = fields.DateTimeField(auto_now_add=True)
    invite_code = fields.CharField(null=True, max_length=64, db_index=True)
    prefix = fields.CharField(null=True, max_length=64)
    language = fields.LanguageField()
    members = fields.ManyToManyField(to='User', through='Member')

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
    id = fields.BigIntegerField(primary_key=True)
    guild = fields.GuildField(on_delete=fields.CASCADE)
    language = fields.LanguageField()

    _discord_cls = discord.TextChannel

    @classmethod
    async def from_discord_obj(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, cls.discord_cls):
            raise TypeError(f"discord_obj has to be a discord.{cls.discord_cls.__name__} "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(id=discord_obj.id, guild=Guild.from_discord_obj(discord_obj.guild))
        obj._discord_obj = discord_obj
        await obj.load()
        return obj

    async def fetch(self) -> discord.TextChannel:
        discord_text_channel = self._core.get_channel(self.id)
        if discord_text_channel is None:
            discord_text_channel = await self._core.fetch_channel(self.id)
        self._discord_obj = discord_text_channel
        return discord_text_channel


class VoiceChannel(DiscordModel):
    id = fields.BigIntegerField(primary_key=True)
    guild = fields.GuildField(on_delete=fields.CASCADE)

    _discord_cls = discord.VoiceChannel

    @classmethod
    async def from_discord_obj(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, cls.discord_cls):
            raise TypeError(f"discord_obj has to be a discord.{cls.discord_cls.__name__} "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(id=discord_obj.id, guild=Guild.from_discord_obj(discord_obj.guild))
        obj._discord_obj = discord_obj
        await obj.load()
        return obj

    async def fetch(self) -> discord.VoiceChannel:
        discord_voice_channel = self._core.get_channel(self.id)
        if discord_voice_channel is None:
            discord_voice_channel = await self._core.fetch_channel(self.id)
        self._discord_obj = discord_voice_channel
        return discord_voice_channel


class Role(DiscordModel):
    id = fields.BigIntegerField(primary_key=True)
    guild = fields.GuildField(on_delete=fields.CASCADE)

    _discord_cls = discord.Role

    @classmethod
    async def from_discord_obj(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, cls.discord_cls):
            raise TypeError(f"discord_obj has to be a discord.{cls.discord_cls.__name__} "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(id=discord_obj.id, guild=Guild.from_discord_obj(discord_obj.guild))
        obj._discord_obj = discord_obj
        await obj.load()
        return obj

    async def fetch(self) -> discord.Role:
        discord_role = self.guild._discord_obj.get_role(self.id)
        if discord_role is None:
            discord_role = await self.guild._discord_obj.fetch_role(self.id)
        self._discord_obj = discord_role
        return discord_role


class Emoji(DiscordModel):
    id = fields.BigIntegerField(primary_key=True)
    guild = fields.GuildField(on_delete=fields.CASCADE)
    name = fields.CharField(max_length=64)
    animated = fields.BooleanField()

    _discord_cls = discord.PartialEmoji

    @classmethod
    async def from_discord_obj(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, cls.discord_cls):
            raise TypeError(f"discord_obj has to be a discord.{cls.discord_cls.__name__} "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(id=discord_obj.id, guild=Guild.from_discord_obj(discord_obj.guild),
                  name=discord_obj.name, animated=discord_obj.animated)
        obj._discord_obj = discord_obj
        await obj.load()
        return obj

    async def fetch(self) -> discord.PartialEmoji:
        discord_emoji = self._core.get_channel(self.id)
        if discord_emoji is None:
            discord_emoji = await self._core.fetch_channel(self.id)
        self._discord_obj = discord_emoji
        return discord_emoji


class Member(DiscordModel):
    class Meta:
        unique_together = (('user', 'guild'),)

    auto_id = _models.BigAutoField(primary_key=True)
    user = fields.UserField(on_delete=fields.CASCADE)
    guild = fields.GuildField(on_delete=fields.CASCADE)

    def __getattr__(self, name):
        if name == 'id':
            _discord_obj = getattr(self, '_discord_obj', None)
            if _discord_obj is not None:
                return self._discord_obj.id

    _discord_cls = discord.Member

    @classmethod
    async def from_discord_obj(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, discord.Member):
            raise TypeError(f"discord_obj has to be a discord.Member "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(user=User.from_discord_obj(discord_obj.user), guild=Guild.from_discord_obj(discord_obj.guild))
        obj._discord_obj = discord_obj
        await obj.load()
        return obj


class Message(DiscordModel):
    id = fields.BigIntegerField(primary_key=True)
    channel = fields.TextChannelField(db_index=True, on_delete=fields.CASCADE)
    author = fields.UserField(db_index=True, on_delete=fields.CASCADE)
    guild = fields.GuildField(db_index=True, on_delete=fields.CASCADE)

    _discord_cls = discord.Message

    @classmethod
    async def from_discord_obj(cls, discord_obj):
        """Create a Hero object from a Discord object"""
        if not isinstance(discord_obj, cls.discord_cls):
            raise TypeError(f"discord_obj has to be a discord.{cls.discord_cls.__name__} "
                            f"but a {type(discord_obj).__name__} was passed")
        obj = cls(id=discord_obj.id, channel=TextChannel.from_discord_obj(discord_obj.channel),
                  author=Member.from_discord_obj(discord_obj.author),
                  guild=Guild.from_discord_obj(discord_obj.guild))
        obj._discord_obj = discord_obj
        await obj.load()
        return obj


class Settings(Model):
    class Meta:
        abstract = True

    namespace = fields.NamespaceField(primary_key=True)
