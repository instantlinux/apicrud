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
    packages=('apicrud', 'apicrud.media', 'apicrud.messaging'),
    include_package_data=True,
    install_requires=[
        'alembic>=1.4.1',
        'connexion>=2.6.0',
        'connexion[swagger-ui]',
        'cryptography>=2.1.4',
        'Flask>=1.1.1',
        'Flask-Cors>=3.0.8',
        'geocoder>=1.38.1',
        'itsdangerous>=1.1.0',
        'PyJWT>=1.7.1',
        'passlib>=1.7.2',
        'pycryptodomex>=3.9.6',
        'PyMySQL>=0.9.3',
        'pytz>=2019.3',
        'redis>=3.4.1',
        'requests>=2.23.0',
        'SQLAlchemy>=1.3.15',
        'SQLAlchemy-Utils>=0.36.2',
        'swagger-ui-bundle>=0.0.6',
        'urllib3>=1.25.8'],
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
        'Programming Language :: Python :: 3.8'
    ]
)
