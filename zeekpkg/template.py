"""
A module for instantiating different types of Zeek packages.
"""
import os
import shutil

from . import (
    LOG,
)

class Error(Exception):
    """Base class for any template-related errors."""


class InputError(Error):
    """Something's amiss in the input arguments for a package."""


class OutputError(Error):
    """Something's going wrong while producing template output."""


class Args():
    """This class represents all input knowledge we require to
    instantiate a package."""
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


class Template:
    """Common functionality for all template types."""

    FEATURE = None

    def __init__(self):
        self._overlays = []

    def add_overlay(self, overlay):
        self._overlays.append(overlay)

    def validate(self, args):
        self._validate_impl(args)
        for ovly in self._overlays:
            ovly.validate(args)

    def instantiate(self, args, output_dir, use_force=False):
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
                # Make any required substitutions to path and file names
                out_path = self._replace(args, root[len(prefix)+1:])
                out_file = self._replace(args, fname)
                # Make substitutions to file content itself.
                try:
                    with open(in_file, 'rb') as hdl:
                        out_content = self._replace(args, hdl.read())
                except IOError as err:
                    LOG.warning('skipping instantiation of %s: %s', in_file, err)
                    continue
                yield out_path, out_file, out_content

    def _validate_impl(self, args):
        pass

    def _instantiate_impl(self, args, output_dir, use_force):
        # pylint: disable=unused-argument
        prefix = output_dir + os.sep + args.slug()
        for path_name, file_name, content in self._walk(args):
            os.makedirs(os.path.join(prefix, path_name), exist_ok=True)
            try:
                with open(os.path.join(prefix, path_name, file_name), 'wb') as hdl:
                    hdl.write(content)
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
        prefix = output_dir + os.sep + args.slug()
        if os.path.isdir(prefix):
            if use_force:
                try:
                    shutil.rmtree(prefix)
                    LOG.info('Removed existing template output directory %s', prefix)
                except OSError as err:
                    raise OutputError('could not remove output directory {}: {}'
                                      .format(prefix, err)) from err
            else:
                raise OutputError('output directory {} already exists.'.format(prefix))

        super()._instantiate_impl(args, output_dir, use_force)


class Overlay(Template):
    """Overlays add specific features to another template."""


class PluginOverlay(Overlay):
    """This overlay adds plugin support to a Zeek package."""
    FEATURE = 'plugin'

    def _validate_impl(self, args):
        if not args.namespace():
            raise InputError('no namespace provided. See --namespace.')
