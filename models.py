from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models


class User(AbstractBaseUser):
    id = models.BigIntegerField(primary_key=True)
    is_superuser = models.BooleanField(default=False, db_index=True)
    is_staff = models.BooleanField(default=False, db_index=True)
    command_count = models.IntegerField(default=0)

    USERNAME_FIELD = 'id'

    def get_full_name(self):
        return str(self.id)

    def get_short_name(self):
        return str(self.id)[0:7]

    def __int__(self):
        return self.id


class Guild(models.Model):
    # I can't normalize this any further :/
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=64, unique=True, db_index=True)
    register_time = models.TimeField('date registered', auto_now=True)
    invite_link = models.CharField(max_length=64, unique=True, db_index=True)
    url = models.CharField(max_length=256, unique=True)
    is_deleted = models.BooleanField(default=False)

    def __int__(self):
        return self.id


class Channel(models.Model):
    id = models.BigIntegerField(primary_key=True)
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE)

    def __int__(self):
        return self.id


class Role(models.Model):
    id = models.BigIntegerField(primary_key=True)
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE)

    def __int__(self):
        return self.id


class Message(models.Model):
    id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    content = models.TextField(max_length=2000)
    clean_content = models.TextField(max_length=2000)

    def __int__(self):
        return self.id


class Member(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE)

    def __int__(self):
        return self.id
