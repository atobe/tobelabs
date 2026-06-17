from pathlib import Path
from setuptools import setup  # type: ignore

tobelib_path: str = (Path(__file__).parent.parent / "tobelib").as_uri()

setup(
    install_requires=[
        f"tobelib @ {tobelib_path}"
    ]
)
