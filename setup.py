import sys
from setuptools import setup
import glob

setup(
    name = "openBMC",
    version = "0.1",
    packages = ["openBMC"],
    author = "Kevin Wang",
    author_email = "unknown@unknow.com",
    description = "openBMC module for RPI",
    license = "MIT",
    keywords = "test",
    url = "",
    data_files=[('/etc/dbus-1/system.d/', glob.glob('backend/*.conf')),
    			('share/dbus-1/system-services', glob.glob('backend/*.service'))],
)
