import configparser
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
PLUGIN_DIR = Path(__file__).parent.parent

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
    logger.info(metadata_file)
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
