"""discord-hero: Discord Application Framework for humans

:copyright: (c) 2019-2020 monospacedmagic et al.
:license: Apache-2.0 OR MIT
"""

from importlib.util import spec_from_file_location, module_from_spec
import os

from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

import hero


class Extension:
    def __init__(self, name: str, module):
        self.name = name
        self._module = module

    def get_models(self):
        from hero.models import Model
        try:
            models_module = self._module.models
            module_dict = models_module.__dict__
            try:
                to_import = models_module.__all__
            except AttributeError:
                to_import = [name for name in module_dict if not name.startswith('_')]

            return [module_dict[name] for name in to_import
                    if issubclass(module_dict[name], Model)]
        except AttributeError:
            return []

    def __getattr__(self, item):
        return getattr(self._module, item, None)

    def __str__(self):
        return self.name


class Extensions(dict):
    def __init__(self, name: str = None):
        self.name = name or 'default'
        self._extensions = ['essentials']
        self._local_extensions = []
        self.loaded_by_core = []
        super(Extensions, self).__init__()

    @property
    def data(self):
        return self._extensions + self._local_extensions

    def load(self):
        with open(os.path.join(hero.ROOT_DIR, 'extensions.txt')) as extensions_file:
            _tmp = ';'.join(extensions_file.readlines())
        os.environ['EXTENSIONS'] = _tmp
        with open(os.path.join(hero.ROOT_DIR, 'local_extensions.txt')) as local_extensions_file:
            _local_tmp = ';'.join(local_extensions_file.readlines())
        os.environ['LOCAL_EXTENSIONS'] = _local_tmp
        _extensions = os.getenv('EXTENSIONS')
        if _extensions:
            self._extensions = ['essentials'] + _extensions.split(';')
        else:
            self._extensions = ['essentials']
        _local_extensions = os.getenv('LOCAL_EXTENSIONS')
        if _local_extensions:
            self._local_extensions = _local_extensions.split(';')
        else:
            self._local_extensions = []
        _gen = ((_name, Extension(_name, self.get_extension_module(_name, local=False)))
                for _name in self._extensions)
        _local_gen = ((_name, Extension(_name, self.get_extension_module(_name, local=True)))
                      for _name in self._local_extensions)
        self.clear()
        self.update(_gen)
        self.update(_local_gen)

    @classmethod
    def get_extension_module(cls, name: str, local: bool):
        if local:
            spec = spec_from_file_location(f'hero.extensions.{name}',
                                           os.path.join(hero.ROOT_DIR, 'extensions',
                                                        name, '__init__.py'))
        else:
            spec = spec_from_file_location(f'hero.extensions.{name}',
                                           os.path.join(hero.LIB_ROOT_DIR, 'extensions',
                                                        name, '__init__.py'))
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class Config:
    def __init__(self, test):
        self.test = test
        self._load()

    def _load(self):
        """expects environment variables to exist already"""
        self.bot_token = os.getenv('BOT_TOKEN')


    @property
    def file_name(self):
        return '.testenv' if self.test else '.env'

    @property
    def file_path(self):
        return os.path.join(hero.ROOT_DIR, self.file_name)

    def reload(self):
        load_dotenv(self.file_path)

    def generate_config_dict(self):
        _config = {
            'PROD': os.getenv('PROD', self.test),
            'NAMESPACE': os.getenv('NAMESPACE', 'default'),
            'SECRET_KEY': os.getenv('SECRET_KEY', get_random_secret_key()),
            'BOT_TOKEN': os.getenv('BOT_TOKEN'),
            'DB_TYPE': os.getenv('DB_TYPE', 'sqlite'),
            'DB_NAME': os.getenv('DB_NAME', None),
            'DB_USER': os.getenv('DB_USER', None),
            'DB_PASSWORD': os.getenv('DB_PASSWORD', None),
            'DB_HOST': os.getenv('DB_HOST', None),
            'DB_PORT': os.getenv('DB_PORT', None),
            'CACHE_TYPE': os.getenv('CACHE_TYPE', 'simple'),
            'CACHE_HOST': os.getenv('CACHE_HOST', None),
            'CACHE_PORT': os.getenv('CACHE_PORT', None),
            'CACHE_PASSWORD': os.getenv('CACHE_PASSWORD', None),
            'CACHE_DB': os.getenv('CACHE_DB', 0)
        }
        _config = {key: value for key, value in _config.items() if value is not None}
        return _config

    def _generate_dotenv_file(self, config: dict):
        dotenv_lines = [f"export {key}={value}" for key, value in config.items()]
        dotenv_lines.append("")
        dotenv_lines = '\n'.join(dotenv_lines)
        with open(self.file_path, 'w+') as dotenv_file:
            dotenv_file.write(dotenv_lines)

    def save(self, config_dict=None):
        if config_dict is None:
            config_dict = self.generate_config_dict()
        self._generate_dotenv_file(config_dict)
        self.reload()
