"""
A module for instantiating different types of Zeek packages.
"""
import abc
import configparser
import importlib.machinery
import json
import re
import os
import shutil
import sys
import types

from . import (
    __version__,
    LOG,
)

from .package import (
    METADATA_FILENAME,
)

from ._util import (
    delete_path,
    slugify,
)

class Error(Exception):
    """Base class for any template-related errors."""

class InputError(Error):
    """Something's amiss in the input arguments for a package."""

class OutputError(Error):
    """Something's going wrong while producing template output."""


class TemplateArgs():

    """This class represents the input required to instantiate a package."""
    def __init__(self, tinfo):
        self.templatedir = tinfo.templatedir()
        self.vals = {}
        self.derivatives = set()

    def define(self, key, val, is_derivative=False):
        self.vals[key] = val
        if is_derivative:
            self.derivatives.add(key)

    def get(self, key, default=None):
        return self.vals.get(key, default)

    def canonical_data(self):
        res = {}
        for key, val in self.vals.items():
            if val and not key in self.derivatives:
                res[key] = val
        return res


class TemplateInfo(metaclass=abc.ABCMeta):
    """Base class for any template. Templates need to define this in their
    toplevel __init__.py and implement at least the abstract functions."""

    DEFAULT_TEMPLATEDIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'default_template')

    @staticmethod
    def instantiate(templatedir=None):
        templatedir = os.path.abspath(templatedir or TemplateInfo.DEFAULT_TEMPLATEDIR)
        dirname = os.path.basename(templatedir)
        filename = os.path.join(templatedir, '__init__.py')

        # We need to load this module, reobustly. This is not Python's finest hour...
        # https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
        loader = importlib.machinery.SourceFileLoader('template_' + dirname, filename)
        if hasattr(loader, 'exec_module'):
            mod = types.ModuleType(loader.name)
            loader.exec_module(mod)
        else:
            mod = loader.load_module()
        return mod.TemplateInfo(templatedir)

    def __init__(self, templatedir):
        self._templatedir = templatedir

    def templatedir(self):
        return self._templatedir

    @abc.abstractmethod
    def name(self):
        """A name for this template (not the instance)"""
        return None

    @abc.abstractmethod
    def version(self):
        """A version string describing the template."""
        return None

    @abc.abstractmethod
    def argparse_setup(self, parser):
        """Adds required command-line arguments to the argparse parser."""

    @abc.abstractmethod
    def argparse_process(self, args, targs):
        """Processes given command line arguments into template arguments."""

    @abc.abstractmethod
    def get_package(self):
        """Returns zeekpkg.template.Package instance.

        Every template must provide a package to start from.
        """
        return None

    def get_features(self): # pylint: disable=no-self-use
        """Returns list of any features provided by the template.

        If supported, each list member must be a zeekpkg.template.Feature instance.
        """
        return []


class _TemplateBase(metaclass=abc.ABCMeta):
    """Abstract base class with Common functionality for all template data."""

    def __init__(self):
        self._features = []

    @abc.abstractmethod
    def content_dir(self):
        """Returns the directory in which this specific template's contents
        reside in the overall template tree."""
        return None

    def add_feature(self, feature):
        self._features.append(feature)

    def validate(self, targs):
        # Base validation for any template instantiation:
        if not os.path.isdir(targs.templatedir):
            raise Error(
                'template directory "{}" is unavailable'
                .format(targs.templatedir))

        if not targs.get('name'):
            raise InputError('template must provide name for the new package')

        if not targs.get('name').isalnum():
            raise InputError(
                'package name "{}" must be alphanumeric'
                .format(targs.get('name')))

        for feature in self._features:
            feature.validate(targs)

    def instantiate(self, tinfo, targs, packagedir, use_force=False):
        # pylint: disable=unused-argument
        self._instantiate(targs, packagedir, use_force)
        for feature in self._features:
            feature.instantiate(tinfo, targs, packagedir, use_force)

    def _replace(self, targs, content): # pylint: disable=no-self-use
        for key, val in targs.vals.items():
            pat = '@' + key + '@'
            if not isinstance(content, str):
                pat = bytes(pat, 'ascii')
                val = bytes(val, 'ascii')
            content = re.sub(pat, val, content, flags=re.IGNORECASE)

        return content

    def _walk(self, targs):
        prefix = os.path.join(targs.templatedir, self.content_dir())
        for root, _, files in os.walk(prefix):
            for fname in files:
                in_file = root + os.sep + fname

                # Substitutes directory and file names
                out_path = self._replace(targs, root[len(prefix)+1:])
                out_file = self._replace(targs, fname)

                # Substitute file content.
                try:
                    with open(in_file, 'rb') as hdl:
                        out_content = self._replace(targs, hdl.read())
                except IOError as err:
                    LOG.warning('skipping instantiation of %s: %s', in_file, err)
                    continue
                yield in_file, out_path, out_file, out_content

    def _instantiate(self, targs, packagedir, use_force):
        # pylint: disable=unused-argument
        for orig_file, path_name, file_name, content in self._walk(targs):
            out_dir = os.path.join(packagedir, path_name)
            out_file = os.path.join(out_dir, file_name)
            os.makedirs(out_dir, exist_ok=True)
            try:
                with open(out_file, 'wb') as hdl:
                    hdl.write(content)
                shutil.copymode(orig_file, out_file)
            except IOError as err:
                LOG.warning(err)

    def _update_metadata(self, tinfo, targs, packagedir):
        config = configparser.ConfigParser(delimiters='=')
        config.optionxform = str
        section = 'template'
        manifest_file = os.path.join(packagedir, METADATA_FILENAME)

        if config.read(manifest_file):
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, 'source', tinfo.name())
            config.set(section, 'version', tinfo.version())
            config.set(section, 'zkg_version', __version__)
            if self._features:
                val = ','.join(sorted([f.name() for f in self._features]))
                config.set(section, 'features', val)
            data = targs.canonical_data()
            for key in sorted(data.keys()):
                config.set(section, 'arg.' + key, data[key])

        with open(manifest_file, 'w') as hdl:
            config.write(hdl)


class Package(_TemplateBase):
    def instantiate(self, tinfo, targs, packagedir, use_force=False):
        if os.path.isdir(packagedir):
            if use_force:
                try:
                    delete_path(packagedir)
                    LOG.info('Removed existing package directory %s', packagedir)
                except OSError as err:
                    raise OutputError('could not remove package directory {}: {}'
                                      .format(packagedir, err)) from err
            else:
                raise OutputError('package directory {} already exists. Use'
                                  ' --force to delete and recreate.'
                                  .format(packagedir))
        else:
            os.makedirs(packagedir, exist_ok=True)

        super().instantiate(tinfo, targs, packagedir, use_force)

        self._update_metadata(tinfo, targs, packagedir)


class Feature(_TemplateBase):

    """Features overlay additional functionality onto a template."""

    def name(self):
        """A name for this feature. Defaults to its content directory."""
        return self.content_dir() or 'unnamed'
