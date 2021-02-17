import collections
import os
import zeekpkg.template

class Package(zeekpkg.template.Package):
    def content_dir(self):
        return 'package'

    def validate(self, args):
        if args.get('namespace') and not args.get('namespace').isalnum():
            raise zeekpkg.template.InputError(
                'package namespace "{}" must be alphanumeric'
                .format(args.get('namespace')))


class Plugin(zeekpkg.template.Feature):
    def content_dir(self):
        return 'plugin'

    def validate(self, args):
        if not args.get('namespace'):
            raise zeekpkg.template.InputError(
                'plugins require a namespace argument')

        if not args.get('namespace').isalnum():
            raise zeekpkg.template.InputError(
                'package namespace "{}" must be alphanumeric'
                .format(args.get('namespace')))


class GithubCi(zeekpkg.template.Feature):
    def content_dir(self):
        return 'github-ci'


class TemplateInfo(zeekpkg.template.TemplateInfo):
    def name(self):
        return 'zkg-default'

    def version(self):
        return zeekpkg.__version__

    def argparse_setup(self, parser):
        parser.add_argument(
            '--name', metavar='STRING', required=True,
            help='The name of the package, e.g. "FooBar". Required.')
        parser.add_argument(
            '--namespace', metavar='STRING',
            help='A namespace for the package, e.g. "MyOrg". Required'
            ' only when including a plugin in your package.')

    def argparse_process(self, args, targs):
        targs.define('name', args.name)
        targs.define('ns', args.namespace or '')
        targs.define('ns_colons', args.namespace + '::' if args.namespace else '', True)
        targs.define('ns_underscore', args.namespace + '_' if args.namespace else '', True)
        targs.define('slug', zeekpkg.template.slugify(args.name), True)

    def get_package(self):
        return Package()

    def get_features(self):
        return [Plugin(), GithubCi()]
