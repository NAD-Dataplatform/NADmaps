import configparser
import logging
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent

from ..nad_maps import NADMaps


def test_metadata():

    required_metadata = [
        "name",
        "description",
        "version",
        "qgisMinimumVersion",
        "email",
        "author",
        "about",
        "tracker",
        "repository",
    ]

    metadata_file = PLUGIN_DIR / "metadata.txt"
    metadata = []
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(metadata_file, encoding="utf-8")
    message = 'Cannot find a section named "general" in %s' % metadata_file
    assert parser.has_section("general"), message
    metadata.extend(parser.items("general"))

    for key in required_metadata:
        message = 'Cannot find mandatory metadata "%s" in metadata source (%s).' % (
            key,
            metadata_file,
        )
        assert key in dict(metadata), message

def test_smoke(iface_mock):
    assert NADMaps(iface_mock)
    