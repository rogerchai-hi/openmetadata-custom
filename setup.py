from setuptools import find_packages, setup

base_requirements = ["evidently"]
setup(name="datadrift-tests",
      version="0.3.0a2",
      description="OpenMetadata Custom Data Drift Tests",
      packages=find_packages(),
      install_requires=list(base_requirements)
     )