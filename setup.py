from setuptools import setup

setup(
    name='py_gitlab',
    author='Yoni Samoded @w00fmeow',
    version='0.0.1',
    package_dir={"": "py_gitlab"},
    install_requires=[
        'asyncio == 3.4.3',
        'aiohttp == 3.8.1',
    ],
    entry_points={
        'console_scripts': [
            'py_gitlab = src.cli:main',
        ]
    },
)
