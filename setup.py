import io
import os.path
import setuptools
from setuptools.command.test import test as TestCommand

setup_ver = {}
with open('apicrud/_version.py') as file:
    exec(file.read(), setup_ver)

__long_desc__ = io.open(os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'README.md'), encoding='utf-8').read()


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = [
            '--junitxml', 'tests/test-result.xml',
            '--ignore', 'media',
            '--cov-report', 'term-missing',
            '--cov-report', 'html',
            '--cov-report', 'xml']
        self.test_suite = True

    def run_tests(self):
        import pytest
        pytest.main(self.test_args)


setuptools.setup(
    version=setup_ver.get('__version__'),
    name='apicrud',
    description='Flask REST framework for role-based access',
    long_description=__long_desc__,
    long_description_content_type='text/markdown',
    keywords='api flask rbac rest',
    author='Rich Braun',
    author_email='docker@instantlinux.net',
    url='https://github.com/instantlinux/apicrud',
    license='Apache License Version 2.0',
    scripts=[],
    package_data=dict(apicrud=['*.yaml', 'i18n/*/LC_MESSAGES/*.mo',
                               'templates/*.j2']),
    packages=('apicrud', 'apicrud.auth', 'apicrud.controllers',
              'apicrud.media', 'apicrud.messaging', 'apicrud.test'),
    include_package_data=True,
    install_requires=[
        'alembic>=1.6.2',
        'Authlib>=0.15.3,<1.0.0',
        'babel>=2.8.0',
        'b2sdk>=1.7.0',
        'boto3>=1.16.47',
        'botocore>=1.19.47',
        'cachetools>=4.2.2',
        'connexion>=2.7.0',
        'connexion[swagger-ui]',
        'cryptography>=3.3.2',
        'Flask>=1.1.2',
        'Flask-Babel>=2.0.0',
        'Flask-Cors>=3.0.10',
        'geocoder>=1.38.1',
        'itsdangerous>=1.1.0',
        'ldap3>=2.9',
        'PyJWT>=2.1.0',
        'passlib>=1.7.4',
        'pycryptodomex>=3.9.9',
        'PyMySQL>=1.0.2',
        'pyotp>=2.6.0',
        'pytz>=2021.1',
        'redis>=3.5.3',
        'requests>=2.25.1',
        'SQLAlchemy>=1.3.24,<1.4.0',
        'SQLAlchemy-Utils>=0.37.0',
        'swagger-ui-bundle>=0.0.8',
        'urllib3>=1.26.4'],
    python_requires='>=3.6',
    test_suite='tests',
    cmdclass={'test': PyTest},
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ]
)
