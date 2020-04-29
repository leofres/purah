"""discord-hero: Discord Application Framework for humans

:copyright: (c) 2019-2020 monospacedmagic et al.
:license: Apache-2.0 OR MIT
"""

from functools import partial

from asgiref.sync import sync_to_async

import discord

from django.db import router, signals, transaction
from django.db.models import (BigIntegerField, BooleanField, CharField, CASCADE,
                              DateField, DateTimeField, DecimalField, FloatField,
                              ForeignKey as _ForeignKey, ForeignObject,
                              IntegerField, ManyToManyField as _ManyToManyField,
                              SET_DEFAULT, SET_NULL, SmallIntegerField, TextField)
from django.db.models.fields.related_descriptors import (ManyToManyDescriptor as _ManyToManyDescriptor,
                                                         ReverseManyToOneDescriptor as _ReverseManyToOneDescriptor,
                                                         create_forward_many_to_many_manager,
                                                         create_reverse_many_to_one_manager)
from django.db.models.fields.related import lazy_related_operation, create_many_to_many_intermediary_model
from django.utils.functional import cached_property

from .i18n import Languages
from .errors import InactiveUser


# Make calls to related fields async
# (kinda hacky since Django does not provide an
# easy way to override the (Many)RelatedManager used)
class ReverseManyToOneDescriptor(_ReverseManyToOneDescriptor):
    @cached_property
    def related_manager_cls(self):
        related_model = self.rel.related_model

        class RelatedManager(create_reverse_many_to_one_manager(
            related_model._default_manager.__class__,
            self.rel,
        )):
            @sync_to_async
            def create(self, **kwargs):
                self.sync_create(**kwargs)

            def sync_create(self, **kwargs):
                kwargs[self.field.name] = self.instance
                db = router.db_for_write(self.model, instance=self.instance)
                return super(RelatedManager, self.db_manager(db)).sync_create(**kwargs)
            sync_create.alters_data = True

            @sync_to_async
            def get_or_create(self, **kwargs):
                self.sync_get_or_create(**kwargs)

            def sync_get_or_create(self, **kwargs):
                kwargs[self.field.name] = self.instance
                db = router.db_for_write(self.model, instance=self.instance)
                return super(RelatedManager, self.db_manager(db)).sync_get_or_create(**kwargs)
            sync_get_or_create.alters_data = True

            @sync_to_async
            def update_or_create(self, **kwargs):
                return self.sync_update_or_create(**kwargs)

            def sync_update_or_create(self, **kwargs):
                kwargs[self.field.name] = self.instance
                db = router.db_for_write(self.model, instance=self.instance)
                return super(RelatedManager, self.db_manager(db)).sync_create(**kwargs)
            sync_update_or_create.alters_data = True

            @sync_to_async
            def clear(self, *, bulk=True):
                self.sync_clear(bulk=bulk)

            def sync_clear(self, *, bulk=True):
                self._clear(self, bulk)
            sync_clear.alters_data = True

            @sync_to_async
            def set(self, objs, *, bulk=True, clear=False):
                return self.sync_set(objs, bulk=bulk, clear=clear)

            def sync_set(self, objs, *, bulk=True, clear=False):
                objs = tuple(objs)
                if self.field.null:
                    db = router.db_for_write(self.model, instance=self.instance)
                    with transaction.atomic(using=db, savepoint=False):
                        if clear:
                            self.clear(bulk=bulk)
                            self.sync_add(*objs, bulk=bulk)
                        else:
                            old_objs = set(self.using(db).all())
                            new_objs = []
                            for obj in objs:
                                if obj in old_objs:
                                    old_objs.remove(obj)
                                else:
                                    new_objs.append(obj)

                            self.sync_remove(*old_objs, bulk=bulk)
                            self.sync_add(*new_objs, bulk=bulk)
                else:
                    self.add(*objs, bulk=bulk)
            sync_set.alters_data = True

            @sync_to_async
            def remove(self, *args, **kwargs):
                return self.sync_remove(*args, **kwargs)

            def sync_remove(self, *args, **kwargs):
                return super(RelatedManager, self).remove(*args, **kwargs)
            sync_remove.alters_data = True

            @sync_to_async
            def add(self, *args, **kwargs):
                return self.sync_add(*args, **kwargs)

            def sync_add(self, *args, **kwargs):
                return super(RelatedManager, self).add(*args, **kwargs)
            sync_add.alters_data = True

        return RelatedManager


class ManyToManyDescriptor(_ManyToManyDescriptor):
    @cached_property
    def related_manager_cls(self):
        related_model = self.rel.related_model if self.reverse else self.rel.model

        class ManyRelatedManager(create_forward_many_to_many_manager(
            related_model._default_manager.__class__,
            self.rel,
            reverse=self.reverse,
        )):
            @sync_to_async
            def create(self, **kwargs):
                self.sync_create(**kwargs)

            def sync_create(self, *, through_defaults=None, **kwargs):
                db = router.db_for_write(self.instance.__class__, instance=self.instance)
                new_obj = super(ManyRelatedManager, self.db_manager(db)).sync_create(**kwargs)
                self.add(new_obj, through_defaults=through_defaults)
                return new_obj
            sync_create.alters_data = True

            @sync_to_async
            def get_or_create(self, *, through_defaults=None, **kwargs):
                self.sync_get_or_create(through_defaults=through_defaults, **kwargs)

            def sync_get_or_create(self, *, through_defaults=None, **kwargs):
                db = router.db_for_write(self.instance.__class__, instance=self.instance)
                obj, created = super(ManyRelatedManager, self.db_manager(db)).sync_get_or_create(**kwargs)
                # We only need to add() if created because if we got an object back
                # from get() then the relationship already exists.
                if created:
                    self.sync_add(obj, through_defaults=through_defaults)
                return obj, created
            sync_get_or_create.alters_data = True

            @sync_to_async
            def update_or_create(self, *, through_defaults=None, **kwargs):
                return self.sync_update_or_create(through_defaults=through_defaults, **kwargs)

            def sync_update_or_create(self, *, through_defaults=None, **kwargs):
                db = router.db_for_write(self.instance.__class__, instance=self.instance)
                obj, created = super(ManyRelatedManager, self.db_manager(db)).sync_update_or_create(**kwargs)
                # We only need to add() if created because if we got an object back
                # from get() then the relationship already exists.
                if created:
                    self.sync_add(obj, through_defaults=through_defaults)
                return obj, created
            sync_update_or_create.alters_data = True

            @sync_to_async
            def clear(self):
                self.sync_clear()

            def sync_clear(self):
                db = router.db_for_write(self.through, instance=self.instance)
                with transaction.atomic(using=db, savepoint=False):
                    signals.m2m_changed.send(
                        sender=self.through, action="pre_clear",
                        instance=self.instance, reverse=self.reverse,
                        model=self.model, pk_set=None, using=db,
                    )
                    self._remove_prefetched_objects()
                    filters = self._build_remove_filters(super().get_queryset().using(db))
                    self.through._default_manager.using(db).filter(filters).sync_delete()

                    signals.m2m_changed.send(
                        sender=self.through, action="post_clear",
                        instance=self.instance, reverse=self.reverse,
                        model=self.model, pk_set=None, using=db,
                    )
            sync_clear.alters_data = True

            @sync_to_async
            def set(self, objs, *, clear=False, through_defaults=None):
                return self.sync_set(objs, clear=clear, through_defaults=through_defaults)

            def sync_set(self, objs, *, clear=False, through_defaults=None):
                # Force evaluation of `objs` in case it's a queryset whose value
                # could be affected by `manager.clear()`. Refs #19816.
                objs = tuple(objs)

                db = router.db_for_write(self.through, instance=self.instance)
                with transaction.atomic(using=db, savepoint=False):
                    if clear:
                        self.sync_clear()
                        self.sync_add(*objs, through_defaults=through_defaults)
                    else:
                        old_ids = set(self.using(db).values_list(self.target_field.target_field.attname, flat=True))

                        new_objs = []
                        for obj in objs:
                            fk_val = (
                                self.target_field.get_foreign_related_value(obj)[0]
                                if isinstance(obj, self.model) else obj
                            )
                            if fk_val in old_ids:
                                old_ids.remove(fk_val)
                            else:
                                new_objs.append(obj)

                        self.sync_remove(*old_ids)
                        self.sync_add(*new_objs, through_defaults=through_defaults)
            sync_set.alters_data = True

            @sync_to_async
            def remove(self, *args, **kwargs):
                return self.sync_remove(*args, **kwargs)

            def sync_remove(self, *args, **kwargs):
                return super(ManyRelatedManager, self).remove(*args, **kwargs)
            sync_remove.alters_data = True

            def _remove_items(self, source_field_name, target_field_name, *objs):
                # source_field_name: the PK colname in join table for the source object
                # target_field_name: the PK colname in join table for the target object
                # *objs - objects to remove. Either object instances, or primary
                # keys of object instances.
                if not objs:
                    return

                # Check that all the objects are of the right type
                old_ids = set()
                for obj in objs:
                    if isinstance(obj, self.model):
                        fk_val = self.target_field.get_foreign_related_value(obj)[0]
                        old_ids.add(fk_val)
                    else:
                        old_ids.add(obj)

                db = router.db_for_write(self.through, instance=self.instance)
                with transaction.atomic(using=db, savepoint=False):
                    # Send a signal to the other end if need be.
                    signals.m2m_changed.send(
                        sender=self.through, action="pre_remove",
                        instance=self.instance, reverse=self.reverse,
                        model=self.model, pk_set=old_ids, using=db,
                    )
                    target_model_qs = super().get_queryset()
                    if target_model_qs._has_filters():
                        old_vals = target_model_qs.using(db).filter(**{
                            '%s__in' % self.target_field.target_field.attname: old_ids})
                    else:
                        old_vals = old_ids
                    filters = self._build_remove_filters(old_vals)
                    self.through._default_manager.using(db).filter(filters).sync_delete()

                    signals.m2m_changed.send(
                        sender=self.through, action="post_remove",
                        instance=self.instance, reverse=self.reverse,
                        model=self.model, pk_set=old_ids, using=db,
                    )

            @sync_to_async
            def add(self, *args, **kwargs):
                return self.sync_add(*args, **kwargs)

            def sync_add(self, *args, **kwargs):
                return super(ManyRelatedManager, self).add(*args, **kwargs)
            sync_add.alters_data = True

            def _add_items(self, source_field_name, target_field_name, *objs, through_defaults=None):
                # source_field_name: the PK fieldname in join table for the source object
                # target_field_name: the PK fieldname in join table for the target object
                # *objs - objects to add. Either object instances, or primary keys of object instances.
                through_defaults = through_defaults or {}

                # If there aren't any objects, there is nothing to do.
                if objs:
                    target_ids = self._get_target_ids(target_field_name, objs)
                    db = router.db_for_write(self.through, instance=self.instance)
                    can_ignore_conflicts, must_send_signals, can_fast_add = self._get_add_plan(db, source_field_name)
                    if can_fast_add:
                        self.through._default_manager.using(db).bulk_create([
                            self.through(**{
                                '%s_id' % source_field_name: self.related_val[0],
                                '%s_id' % target_field_name: target_id,
                            })
                            for target_id in target_ids
                        ], ignore_conflicts=True)
                        return

                    missing_target_ids = self._get_missing_target_ids(
                        source_field_name, target_field_name, db, target_ids
                    )
                    with transaction.atomic(using=db, savepoint=False):
                        if must_send_signals:
                            signals.m2m_changed.send(
                                sender=self.through, action='pre_add',
                                instance=self.instance, reverse=self.reverse,
                                model=self.model, pk_set=missing_target_ids, using=db,
                            )

                        # Add the ones that aren't there already.
                        self.through._default_manager.using(db).bulk_create([
                            self.through(**through_defaults, **{
                                '%s_id' % source_field_name: self.related_val[0],
                                '%s_id' % target_field_name: target_id,
                            })
                            for target_id in missing_target_ids
                        ], ignore_conflicts=can_ignore_conflicts)

                        if must_send_signals:
                            signals.m2m_changed.send(
                                sender=self.through, action='post_add',
                                instance=self.instance, reverse=self.reverse,
                                model=self.model, pk_set=missing_target_ids, using=db,
                            )

        return ManyRelatedManager


class ForeignKey(_ForeignKey):
    related_accessor_class = ReverseManyToOneDescriptor


class ManyToManyField(_ManyToManyField):
    def contribute_to_class(self, cls, name, **kwargs):
        # To support multiple relations to self, it's useful to have a non-None
        # related name on symmetrical relations for internal reasons. The
        # concept doesn't make a lot of sense externally ("you want me to
        # specify *what* on my non-reversible relation?!"), so we set it up
        # automatically. The funky name reduces the chance of an accidental
        # clash.
        if self.remote_field.symmetrical and (
            self.remote_field.model == "self" or self.remote_field.model == cls._meta.object_name):
            self.remote_field.related_name = "%s_rel_+" % name
        elif self.remote_field.is_hidden():
            # If the backwards relation is disabled, replace the original
            # related_name with one generated from the m2m field name. Django
            # still uses backwards relations internally and we need to avoid
            # clashes between multiple m2m fields with related_name == '+'.
            self.remote_field.related_name = "_%s_%s_+" % (cls.__name__.lower(), name)

        super(_ManyToManyField, self).contribute_to_class(cls, name, **kwargs)

        # The intermediate m2m model is not auto created if:
        #  1) There is a manually specified intermediate, or
        #  2) The class owning the m2m field is abstract.
        #  3) The class owning the m2m field has been swapped out.
        if not cls._meta.abstract:
            if self.remote_field.through:
                def resolve_through_model(_, model, field):
                    field.remote_field.through = model
                lazy_related_operation(resolve_through_model, cls, self.remote_field.through, field=self)
            elif not cls._meta.swapped:
                self.remote_field.through = create_many_to_many_intermediary_model(self, cls)

        # Add the descriptor for the m2m relation.
        setattr(cls, self.name, ManyToManyDescriptor(self.remote_field, reverse=False))

        # Set up the accessor for the m2m table name for the relation.
        self.m2m_db_table = partial(self._get_m2m_db_table, cls._meta)

    def contribute_to_related_class(self, cls, related):
        # Internal M2Ms (i.e., those with a related name ending with '+')
        # and swapped models don't get a related descriptor.
        if not self.remote_field.is_hidden() and not related.related_model._meta.swapped:
            setattr(cls, related.get_accessor_name(), ManyToManyDescriptor(self.remote_field, reverse=True))

        # Set up the accessors for the column names on the m2m table.
        self.m2m_column_name = partial(self._get_m2m_attr, related, 'column')
        self.m2m_reverse_name = partial(self._get_m2m_reverse_attr, related, 'column')

        self.m2m_field_name = partial(self._get_m2m_attr, related, 'name')
        self.m2m_reverse_field_name = partial(self._get_m2m_reverse_attr, related, 'name')

        get_m2m_rel = partial(self._get_m2m_attr, related, 'remote_field')
        self.m2m_target_field_name = lambda: get_m2m_rel().field_name
        get_m2m_reverse_rel = partial(self._get_m2m_reverse_attr, related, 'remote_field')
        self.m2m_reverse_target_field_name = lambda: get_m2m_reverse_rel().field_name


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
