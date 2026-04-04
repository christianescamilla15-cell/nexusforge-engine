"""NexusForge Engine v1.0 -- Automation project generator."""

from setuptools import setup, find_packages

setup(
    name="nexusforge-engine",
    version="1.0.0",
    description="Generate enterprise automation projects from natural language prompts",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Christian Hernandez",
    author_email="christian@nexusforge.dev",
    url="https://github.com/ChristianHernandez/nexusforge-engine",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pyyaml",
        "jinja2",
        "typer",
        "rich",
        "pydantic",
        "jsonschema",
    ],
    entry_points={
        "console_scripts": [
            "nexusforge=cli.new_project:main",
            "nexusforge-stats=cli.stats:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
    ],
)
