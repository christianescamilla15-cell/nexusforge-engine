"""NexusForge Engine — Automation starter generator."""

from setuptools import setup, find_packages

setup(
    name="nexusforge-engine",
    version="0.1.0",
    description="Generate enterprise automation projects from natural language prompts",
    author="Christian Hernandez",
    author_email="christian@nexusforge.dev",
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
        ],
    },
)
