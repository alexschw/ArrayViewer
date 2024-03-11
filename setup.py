""" Setup Module """
import os
import sys
from setuptools import setup, find_packages
from ArrayViewer import __version__
if os.name == 'nt':
    try:
        from win32com.client import Dispatch
        from win32com.shell import shell
        from win32com.shell.shellcon import CSIDL_DESKTOP
        winload = True
    except:
        winload = False

PACKAGE_NAME = "ArrayViewer"

with open('requirements.txt') as req_file:
    REQUIREMENTS = req_file.readlines()
with open("README.md", "r") as readme_file:
    LONG_DESC = readme_file.read()

def post_install():
    """ Windows post install function. """
    try:
        desktop = shell.SHGetSpecialFolderPath(0, CSIDL_DESKTOP)
        prefix = sys.prefix
        if '--user' in sys.argv:
            siteP = [n for n in sys.path
                     if 'site-packages' in os.path.split(n)[1]]
            for p in siteP:
                prefix = os.path.split(p)[0]
                if os.path.isfile(os.path.join(prefix,
                                               "Scripts", "aview.exe")):
                    break
        script = os.path.join(prefix, "Scripts", "aview.exe")
        if not os.path.isfile(script):
            raise FileNotFoundError
        dpt = Dispatch('WScript.Shell')
        sh = dpt.CreateShortcut(os.path.join(desktop, "ArrayViewer.lnk"))
        sh.Targetpath = script
        sh.WorkingDirectory = os.path.split(script)[0]
        sh.save()
    except:
        print("No shortcut created!")

if __name__ == "__main__":
    if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
        data_files = [('share/icons', ['aview_logo.svg'])]
    elif os.name == 'nt':
        data_files = [('scripts', ['aview_logo.svg'])]

    setup(
        name=PACKAGE_NAME,
        version=__version__,
        license='GPLv3',
        packages=find_packages(),
        author="Alex Schwarz",
        author_email="schwarz-alex@mail.de",
        url="https://github.com/alexschw/ArrayViewer",
        install_requires=REQUIREMENTS,
        scripts=['aview'],
        data_files=data_files,
        entry_points={"gui_scripts": ["aview = ArrayViewer.Viewer:main",]},
        python_requires=">=3.6",
        description="ArrayViewer",
        package_data={'ArrayViewer':['*.py']},
        long_description=LONG_DESC,
        long_description_content_type="text/markdown",
    )
    if os.name == "nt" and winload and 'install' in sys.argv:
        post_install()
