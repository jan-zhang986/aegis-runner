from setuptools import setup, find_packages

setup(
    name="aegis-sdk",
    version="1.1.0",
    description="Aegis Test as Code SDK for Pytest and Python Testing Projects",
    author="Aegis Team",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "pytest11": [
            "aegis = aegis.plugin",
        ],
    },
)
