from setuptools import find_packages, setup

setup(
    name='apple-api',
    version='0.0.1',
    description='Python wrapper around Apple AppStoreConnect API',
    author='Divyansh Agicha',
    author_email='div.agicha@gmail.com',
    # packages=find_packages('src'),
    package_dir={'': 'src'},
    packages=find_packages(include=['apple_api', 'apple_api.*']),
    install_requires=[
        'certifi==2022.12.7',
        'cffi==1.15.1',
        'charset-normalizer==2.1.1',
        'cryptography==2.9.2',
        'idna==3.4',
        'pycparser==2.21',
        'PyJWT==1.7.1',
        'python-dotenv==0.21.0',
        'requests==2.28.1',
        'six==1.16.0',
        'urllib3==1.26.13',
    ],
    entry_points={
        'console_scripts': []
    }
)
