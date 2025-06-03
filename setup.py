from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in liseniq/__init__.py
from liseniq import __version__ as version

setup(
	name='liseniq',
	version=version,
	description='LisenIQ',
	author='Mentum Group',
	author_email='adolfo.hernandez@mentum.group',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
