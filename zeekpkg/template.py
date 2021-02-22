"""
A module for instantiating different types of Zeek packages.
"""
import abc
import configparser
import json
import re
import os
import shutil
import sys

import git

from . import (__version__, LOG)

from .package import (
    METADATA_FILENAME,
    name_from_path,
)

from ._util import (
    delete_path,
    git_checkout,
    git_clone,
    git_default_branch,
    git_recursive_update,
    git_version_tags,
    load_source,
    make_dir,
    slugify,
)

class Error(Exception):
    """Base class for any template-related errors."""

class InputError(Error):
    """Something's amiss in the input arguments for a package."""

class OutputError(Error):
    """Something's going wrong while producing template output."""

class LoadError(Error):
    """Something's going wrong while retrieving a template."""

class GitError(LoadError):
    """There's git trouble while producing template output."""


class TemplateArgs():

    """This class represents the input required to instantiate a package."""
    def __init__(self):
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

    @staticmethod
    def load(config, template, version=None):
        if os.path.isdir(template):
            # We are loading a template explicitly as-is from somewhere on disk
            if version is not None:
                LOG.warning('ignoring version request "%s" on local template', version)
            try:
                repo = git.Repo(template)
                if not repo.is_dirty():
                    version = repo.head.ref.commit.hexsha[:8]
            except git.InvalidGitRepositoryError:
                pass
            templatedir = template
        else:
            # We're loading from a git URL. We'll maintain it in the
            # zkg state folder's clones subdirectory.
            template_clonedir = os.path.join(
                config.get('paths', 'state_dir'), 'clones', 'template')
            templatedir = os.path.join(template_clonedir, name_from_path(template))
            make_dir(template_clonedir)

            try:
                if os.path.isdir(templatedir):
                    repo = git.Repo(templatedir)
                    git_recursive_update(repo)
                else:
                    repo = git_clone(template, templatedir)
            except git.exc.GitCommandError as error:
                msg = 'failed to update template "{}": {}'.format(template, error)
                LOG.error(msg)
                raise GitError(msg) from error

            if version is None:
                version_tags = git_version_tags(repo)

                if len(version_tags):
                    version = version_tags[-1]
                else:
                    version = git_default_branch(repo)

            try:
                git_checkout(repo, version)
            except git.exc.GitCommandError as error:
                msg = 'failed to checkout branch/version "{}" of package {}: {}'.format(
                    version, template, error)
                LOG.warn(msg)
                raise GitError(msg) from error

        try:
            mod = load_source(os.path.join(templatedir, '__init__.py'))
            return mod.TemplateInfo(templatedir, version)
        except Exception as error:
            msg = 'failed to load template "{}": {}'.format(template, error)
            LOG.exception(msg)
            raise LoadError(msg) from error

    def __init__(self, templatedir, version=None):
        self._templatedir = templatedir
        self._version = version

    def templatedir(self):
        return self._templatedir

    def name(self):
        """A name for this template (not the instance).

        Derived from the repository name."""
        return name_from_path(self._templatedir)

    def version(self):
        """A version string for the template.

        A git tag, branch, or commit hash for the version of the template.
        May be None.
        """
        return self._version

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
        self._packagedir = None # Set when we instantiate

    @abc.abstractmethod
    def contentdir(self):
        """Returns the directory in which this specific template's contents
        reside in the overall template tree."""
        return None

    def add_feature(self, feature):
        self._features.append(feature)

    def do_validate(self, targs):
        self.validate(targs)
        for feature in self._features:
            feature.validate(targs)

    def validate(self, targs):
        pass

    def do_instantiate(self, tinfo, targs, packagedir, use_force=False):
        self._packagedir = packagedir

        self.instantiate(tinfo, targs)

        for feature in self._features:
            feature.do_instantiate(tinfo, targs, packagedir, use_force=use_force)

    def _replace(self, targs, content): # pylint: disable=no-self-use
        for key, val in targs.vals.items():
            pat = '@' + key + '@'
            if not isinstance(content, str):
                pat = bytes(pat, 'ascii')
                val = bytes(val, 'ascii')
            content = re.sub(pat, val, content, flags=re.IGNORECASE)

        return content

    def _walk(self, tinfo, targs):
        prefix = os.path.join(tinfo.templatedir(), self.contentdir())
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
                except IOError as error:
                    LOG.warning('skipping instantiation of %s: %s', in_file, error)
                    continue
                yield in_file, out_path, out_file, out_content

    def instantiate(self, tinfo, targs):
        for orig_file, path_name, file_name, content in self._walk(tinfo, targs):
            out_dir = os.path.join(self._packagedir, path_name)
            out_file = os.path.join(out_dir, file_name)
            os.makedirs(out_dir, exist_ok=True)
            try:
                with open(out_file, 'wb') as hdl:
                    hdl.write(content)
                shutil.copymode(orig_file, out_file)
            except IOError as error:
                LOG.warning('I/O error while instantiating "%s": %s', out_file, error)


class Package(_TemplateBase):
    def do_instantiate(self, tinfo, targs, packagedir, use_force=False):
        self._prepare_packagedir(packagedir, use_force)
        super().do_instantiate(tinfo, targs, packagedir, use_force)
        self._update_metadata(tinfo, targs)
        self._git_init(tinfo)

    def _prepare_packagedir(self, packagedir, use_force=False):
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
        os.makedirs(packagedir, exist_ok=True)

    def _update_metadata(self, tinfo, targs):
        config = configparser.ConfigParser(delimiters='=')
        config.optionxform = str
        section = 'template'
        manifest_file = os.path.join(self._packagedir, METADATA_FILENAME)

        if config.read(manifest_file):
            config.remove_section(section)
            config.add_section(section)
            config.set(section, 'source', tinfo.name())
            config.set(section, 'version', tinfo.version() or 'unversioned')
            config.set(section, 'zkg_version', __version__)
            if self._features:
                val = ','.join(sorted([f.name() for f in self._features]))
                config.set(section, 'features', val)
            data = targs.canonical_data()
            for key in sorted(data.keys()):
                config.set(section, 'arg.' + key, data[key])

        with open(manifest_file, 'w') as hdl:
            config.write(hdl)

    def _git_init(self, tinfo):
        """Initialize git repo and commit package content."""
        repo = git.Repo.init(self._packagedir)
        for fname in repo.untracked_files:
            repo.index.add(fname)

        features_info = ''
        if self._features:
            names = sorted(['"' + f.name() + '"' for f in self._features])
            if len(names) == 1:
                features_info = ' with feature {}'.format(names[0])
            else:
                features_info = ' with features '
                features_info += ', '.join(names[:-1])
                features_info += ' and ' + names[-1]

        ver_info = tinfo.version()
        ver_info = 'no versioning' if ver_info is None else 'version ' + ver_info
        repo.index.commit("""Initial commit.

zkg {} created this content from template "{}"
using {}{}.""".format(__version__, tinfo.name(), ver_info, features_info))

class Feature(_TemplateBase):
    """Features overlay additional functionality onto a template."""

    def name(self):
        """A name for this feature. Defaults to its content directory."""
        return self.contentdir() or 'unnamed'
