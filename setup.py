import setuptools

setuptools.setup(
    name="steamdepcalc",
    description="A script that calculates best steam skins for buying from 3rd party and sell in steam.",
    version="0.0.2",
    author="Extamov",
    license="GPL-3.0",
    packages=setuptools.find_packages("."),
    install_requires=open("requirements.txt", encoding="utf-8").read().splitlines(),
    entry_points={"console_scripts": ["steamdepcalc=steamdepcalc.__main__:entrypoint"]},
    include_package_data=True,
)
