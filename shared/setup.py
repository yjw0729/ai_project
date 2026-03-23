from setuptools import setup, find_packages

setup(
    name="pytest-sxp-shared",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pydantic>=2.0.0",
    ],
)
