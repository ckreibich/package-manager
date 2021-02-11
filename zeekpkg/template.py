"""
A module for instantiating different types of Zeek packages.
"""
import os

from . import (
    LOG,
)

class Error(Exception):
    """Base class for any template-related errors."""


class InputError(Error):
    """Something's amiss in the input arguments for a package."""


class TemplateArgs():
    """This class represents all input knowledge we require to
    instantiate a package."""
    def __init__(self, name, namespace=None, template_dir=None):
        self.vals = {
            'PACKAGE_NAME': name,
            'PACKAGE_NAMESPACE': namespace or '',
            'PACKAGE_NAMESPACE_SEP': namespace + '::' if namespace else '',
            'PACKAGE_SLUG': name.lower().replace('-', '_'),
        }

        self.template_dir = template_dir or os.path.dirname(os.path.abspath(__file__)) + os.sep + 'templates'

    def name(self):
        return self.vals['PACKAGE_NAME']

    def namespace(self):
        return self.vals['PACKAGE_NAMESPACE']

    def slug(self):
        return self.vals['PACKAGE_SLUG']

    def validate(self):
        if not self.name() or not self.name().isalnum():
            raise InputError('Package name "{}" must be alphanumeric'
                             .format(self.name()))
        if self.namespace() and not self.namespace().isalnum():
            raise InputError('Package namespace "{}" must be alphanumeric'
                             .format(self.namespace))
        if not os.path.isdir(self.template_dir):
            raise Error('Template directory "{}" is unavailable'
                        .format(self.template_dir))


class _TemplateBase:
    """Common functionality for templates and overlays."""
    def __init__(self):
        self._args = None

    def instantiate(self, output_dir):
        pass

    def _replace(self, content):
        for key in self._args.vals:
            content = content.replace('@' + key + '@', self._args.vals[key])
        return content

    def _walk(self):
        if self._args is None:
            return

        prefix = self._args.template_dir + os.sep + 'base'
        for root, _, files in os.walk(prefix):
            for f in files:
                in_file = root + os.sep + f
                out_path = self._replace(root[len(prefix)+1:])
                out_file = self._replace(f)
                try:
                    with open(in_file) as hdl:
                        out_content = self._replace(hdl.read())
                except IOError:
                    continue
                yield out_path, out_file, out_content


class PackageTemplate(_TemplateBase):
    """Basic template for a plain, script-layer-only Zeek package."""
    def __init__(self):
        super().__init__()
        self._overlays = []

    def populate(self, args):
        args.validate()
        self._args = args

    def add_overlay(self, overlay):
        self._overlays.append(overlay)

    def instantiate(self, output_dir):
        for path_name, file_name, content in self._walk():
            LOG.debug('Instantiating %s / %s' % (path_name, file_name))
            os.makedirs(path_name)
            try:
                with open(file_name, 'w') as hdl:
                    hdl.write(content)
            except IOError:
                pass
        for ovly in self._overlays:
            ovly.instantiate(output_dir)


class PackageOverlay(_TemplateBase):
    """Overlays are partial templates that apply on top of another,,
    with customized behavior for individual files as needed.
    """
    def __init__(self, tmpl):
        super().__init__()
        self._tmpl = tmpl


class PluginOverlay(PackageOverlay):
    def instantiate(self, output_dir):
        for path_name, file_name, content in self._walk():
            os.makedirs(path_name)
            try:
                with open(file_name, 'w') as hdl:
                    hdl.write(content)
            except IOError:
                pass


class SpicyOverlay(PackageOverlay):
    # Future work. :)
    pass
