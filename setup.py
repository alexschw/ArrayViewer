""" Setup Module """
from setuptools import setup, find_packages

PACKAGE_NAME = "ArrayViewer"
VERSION = "1.0"

with open('requirements.txt') as req_file:
    REQUIREMENTS = req_file.readlines()
with open("README.md", "r") as readme_file:
    LONG_DESC = readme_file.read()


if __name__ == "__main__":
    setup(
        name=PACKAGE_NAME,
        version=VERSION,
        license='GPLv3',
        packages=find_packages(),
        author="Alex Schwarz",
        author_email="schwarz-alex@mail.de",
        url="https://github.com/alexschw/ArrayViewer",
        install_requires=REQUIREMENTS,
        scripts=['aview'],
        python_requires=">=3.0",
        description="ArrayViewer",
        package_data={'ArrayViewer':['*.py']},
        long_description=LONG_DESC,
        long_description_content_type="text/markdown",
    )
