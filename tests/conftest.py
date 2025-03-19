import pytest
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSettings

_singletons = {}

@pytest.fixture(autouse=True)
def qgis_app_initialized():
    """Make sure qgis is initialized for testing."""
    if "app" not in _singletons:
        app = QgsApplication([], False)
        app.initQgis()
        _singletons["app"] = app

class QgisInterfaceMock(object):
    def __getattr__(self, name):
        def mock(*args, **kwargs):
            return None
        return mock
    
@pytest.fixture()
def iface_mock():
    return QgisInterfaceMock()

@pytest.fixture(autouse=True)
def settings_mock():
    QSettings().setValue('locale/userLocale', "nl")