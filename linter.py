#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

import re
import yaml
import click
import requests

from jsonschema.validators import Draft4Validator
from jsonschema import FormatChecker

from isodate import parse_duration, parse_date, parse_datetime


class Ckan:
    def __init__(self, url):
        self.url = url + '/api/3/action/'
        self.s = requests.Session()
        self.s.headers.update({
            'User-Agent': 'ckan-lint (portal.gov.cz link checker compatible)',
        })

    def get(self, url, **params):
        r = self.s.get(self.url + url, params=params).json()
        assert isinstance(r, dict) and r.get('success')
        return r.get('result')

    def list_packages(self):
        return self.get('package_list')

    def get_package(self, id):
        return self.get('package_show', id=id)



class CustomFormatChecker(FormatChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def check_duration(x):
            if re.match(r'^R\d*$', x):
                return x

            try:
                return parse_duration(x)
            except:
                pass

            try:
                return parse_date(x)
            except:
                pass

            try:
                return parse_datetime(x)
            except:
                pass

            return False

        @self.checks('interval')
        def check_interval(x):
            if not isinstance(x, str):
                return False

            try:
                map(check_duration, x.split('/', 1))
            except:
                return False

            return True

        @self.checks('date')
        def check_date(x):
            if not isinstance(x, str):
                return False

            try:
                parse_date(x)
            except:
                return False

            return True


def remove_empty_values(data):
    if isinstance(data, dict):
        for k, v in list(data.items()):
            if v is None or v == '':
                del data[k]

            remove_empty_values(v)

    elif isinstance(data, list):
        for v in data:
            remove_empty_values(v)


@click.version_option('0.1.0')
@click.command('lint')
@click.option('--schema', '-s', type=click.File('r'),
              default='schema.yaml',
              help='Schema file to check the CKAN against.')
@click.argument('url', type=str)
def lint(schema, url):
    """
    Check portal datasets and resources against the specified schema.

    The supplied schema file must be a YAML with a valid JSONSchema.
    """

    schema = yaml.load(schema)
    validator = Draft4Validator(schema, format_checker=CustomFormatChecker())
    ckan = Ckan(url)

    for name in ckan.list_packages():
        package = ckan.get_package(name)
        remove_empty_values(package)

        # Would be cool, but does not actually hold...
        #if 'license_url' in package:
        #    if 'license_link' not in package:
        #        package['license_link'] = package['license_url']

        # As per specification.
        if 'license_link' in package:
            for resource in package.get('resources', []):
                if 'license_link' not in resource:
                    resource['license_link'] = package['license_link']

        if validator.is_valid(package):
            click.echo('Package {!r}: OK'.format(name))
            click.echo('')
            continue

        click.echo('Package {!r}:'.format(name))

        for error in validator.iter_errors(package):
            if error.path:
                path = '/'.join(map(str, error.path))
                click.echo('  - {!r}: {}'.format(path, error.message))
            else:
                click.echo('  - {}'.format(error.message))

        click.echo('')


if __name__ == '__main__':
    lint()


# vim:set sw=4 ts=4 et:
