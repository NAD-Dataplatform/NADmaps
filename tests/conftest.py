import tempfile
from unittest.mock import Mock

import pytest
from qgis.core import QgsApplication
from qgis.gui import QgsLayerTreeView, QgsMapCanvas
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QMainWindow

_singletons = {}

@pytest.fixture(autouse=True)
def qgis_app_initialized():
    """Make sure qgis is initialized for testing."""
    if "app" not in _singletons:
        app = QgsApplication([], False)
        app.initQgis()
        _singletons["app"] = app

class QgisInterfaceMock():
    def __getattr__(self, name):
        def mock(*args, **kwargs):
            if name == "layerTreeView":
                return QgsLayerTreeView()
            if name == "mapCanvas":
                return Mock()
            return None
        return mock
    
    def mainWindow(self):
        """Mock the main window to return a mock mainwindow with a dockWidgetArea."""
        mock_canvas = QMainWindow()
        mock_canvas.dockWidgetArea = Qt.LeftDockWidgetArea
        return mock_canvas
    
@pytest.fixture()
def iface_mock():
    return QgisInterfaceMock()

@pytest.fixture(autouse=True)
def settings_mock():
    temp_dir = tempfile.TemporaryDirectory()
    QSettings().setValue('locale/userLocale', "nl")
    QSettings().setValue('NADmaps/working_dir', temp_dir.name)
