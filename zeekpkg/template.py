"""
A module for instantiating different types of Zeek packages.
"""
import json
import os
import shutil

from . import (
    __version__,
    LOG,
)

class Error(Exception):
    """Base class for any template-related errors."""

class InputError(Error):
    """Something's amiss in the input arguments for a package."""

class OutputError(Error):
    """Something's going wrong while producing template output."""


class Args():
    """This class represents the input required to instantiate a package."""
    def __init__(self, name, namespace=None, template_dir=None):
        self.vals = {
            'PACKAGE_NAME': name,
            'PACKAGE_NS': namespace or '',
            'PACKAGE_NS_COLONS': namespace + '::' if namespace else '',
            'PACKAGE_NS_UNDERSCORE': namespace + '_' if namespace else '',
            'PACKAGE_SLUG': name.lower().replace('-', '_'),
        }

        # By default we locate the template input tree within our package.
        # It ends up there via package_data in setup.py.
        self.template_dir = template_dir or os.path.dirname(
            os.path.abspath(__file__)) + os.sep + 'templates'

    def name(self):
        return self.vals['PACKAGE_NAME']

    def namespace(self):
        return self.vals['PACKAGE_NS']

    def slug(self):
        return self.vals['PACKAGE_SLUG']

    def json_data(self):
        return {
            'name': self.name(),
            'namespace': self.namespace(),
        }


class Template:
    """Common functionality for all template types."""

    # This string, set by subclasses, helps select the relevant
    # template input tree on disk.
    FEATURE = None

    def __init__(self):
        self._overlays = []
        # The toplevel package output directory, usually a folder in
        # the output directory, named after the package. Set when
        # instantiating.
        self.package_dir = None

    def add_overlay(self, overlay):
        self._overlays.append(overlay)

    def validate(self, args):
        self._validate_impl(args)
        for ovly in self._overlays:
            ovly.validate(args)

    def instantiate(self, args, output_dir, use_force=False):
        self.package_dir = output_dir + os.sep + args.slug()
        self._instantiate_impl(args, output_dir, use_force)

        for ovly in self._overlays:
            ovly.instantiate(args, output_dir, use_force=use_force)

    def _replace(self, args, content): # pylint: disable=no-self-use
        for key in args.vals:
            if isinstance(content, str):
                content = content.replace('@' + key + '@', args.vals[key])
            else:
                content = content.replace(bytes('@' + key + '@', 'ascii'),
                                          bytes(args.vals[key], 'ascii'))
        return content

    def _walk(self, args):
        prefix = args.template_dir + os.sep + self.FEATURE
        for root, _, files in os.walk(prefix):
            for fname in files:
                in_file = root + os.sep + fname

                # Substitutes directory and file names
                out_path = self._replace(args, root[len(prefix)+1:])
                out_file = self._replace(args, fname)

                # Substitute file content.
                try:
                    with open(in_file, 'rb') as hdl:
                        out_content = self._replace(args, hdl.read())
                except IOError as err:
                    LOG.warning('skipping instantiation of %s: %s', in_file, err)
                    continue
                yield in_file, out_path, out_file, out_content

    def _validate_impl(self, args):
        pass

    def _instantiate_impl(self, args, output_dir, use_force):
        # pylint: disable=unused-argument
        for orig_file, path_name, file_name, content in self._walk(args):
            out_dir = os.path.join(self.package_dir, path_name)
            out_file = os.path.join(out_dir, file_name)
            os.makedirs(out_dir, exist_ok=True)
            try:
                with open(out_file, 'wb') as hdl:
                    hdl.write(content)
                shutil.copymode(orig_file, out_file)
            except IOError as err:
                LOG.warning(err)


class PackageTemplate(Template):
    """Basic template for a basic script-layer-only Zeek package."""
    FEATURE = 'package'

    def _validate_impl(self, args):
        if not args.name() or not args.name().isalnum():
            raise InputError('package name "{}" must be alphanumeric'
                             .format(args.name()))
        if args.namespace() and not args.namespace().isalnum():
            raise InputError('package namespace "{}" must be alphanumeric'
                             .format(args.namespace))
        if not os.path.isdir(args.template_dir):
            raise Error('template directory "{}" is unavailable'
                        .format(args.template_dir))

    def _instantiate_impl(self, args, output_dir, use_force):
        if os.path.isdir(self.package_dir):
            if use_force:
                try:
                    shutil.rmtree(self.package_dir)
                    LOG.info('Removed existing template output directory %s', self.package_dir)
                except OSError as err:
                    raise OutputError('could not remove output directory {}: {}'
                                      .format(self.package_dir, err)) from err
            else:
                raise OutputError('output directory {} already exists.'
                                  .format(self.package_dir))

        super()._instantiate_impl(args, output_dir, use_force)

        # Preserve template itself for baselining in future migrations
        shutil.copytree(args.template_dir, self.package_dir + os.sep + '.zkg/template')

        # Record the invocation details for posterity:
        try:
            with open(self.package_dir + os.sep + '.zkg/template.json', 'w') as hdl:
                json.dump({
                    'args': args.json_data(),
                    'version': __version__,
                }, hdl, indent=4)
        except IOError as err:
            raise OutputError('could not record template instantiation details: {}'
                              .format(err)) from err


class Overlay(Template):
    """Overlays add additional features to a template."""


class PluginOverlay(Overlay):
    """This overlay adds plugin support to a Zeek package."""
    FEATURE = 'plugin'

    def _validate_impl(self, args):
        if not args.namespace():
            raise InputError('no namespace provided. See --namespace.')
