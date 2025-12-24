"""Setup script for mg-cli."""

from setuptools import setup, find_packages

setup(
    name="mg-cli",
    version="0.1.0",
    description="Monthly Games CLI Tool for Firebase and Ads SDK management",
    author="Monthly Games",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'mg_cli': ['templates/*'],
    },
    install_requires=[
        'click>=8.0.0',
        'pyyaml>=6.0',
        'jinja2>=3.0.0',
    ],
    entry_points={
        'console_scripts': [
            'mg-cli=mg_cli.cli:main',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
