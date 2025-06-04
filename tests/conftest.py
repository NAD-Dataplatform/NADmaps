import tempfile
from unittest.mock import Mock

import pytest
from qgis.core import QgsApplication
from qgis.gui import QgsLayerTreeView, QgsMapCanvas
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QMainWindow, QDockWidget

_singletons = {}

@pytest.fixture(autouse=True)
def qgis_app_initialized():
    """Make sure qgis is initialized for testing."""
    if "app" not in _singletons:
        app = QgsApplication([], False)
        app.initQgis()
        _singletons["app"] = app

class MainWinWithDockArea(QMainWindow):
    def __init__(self):
        super().__init__()
        self._docked_widgets = []

    def dockWidgetArea(self, widget: QDockWidget):
        return Qt.LeftDockWidgetArea

    def addDockWidget(self, area, widget):
        self._docked_widgets.append((area, widget))

class QgisInterfaceMock():
    def __init__(self):
        self._main_win = MainWinWithDockArea()

    def __getattr__(self, name):
        def mock(*args, **kwargs):
            if name == "layerTreeView":
                return QgsLayerTreeView()
            if name == "mapCanvas":
                return Mock()
            return None
        return mock
    
    def mainWindow(self):
        return self._main_win

    def addDockWidget(self, area, widget):
        self._main_win.addDockWidget(area, widget)
    
@pytest.fixture()
def iface_mock():
    return QgisInterfaceMock()

@pytest.fixture(autouse=True)
def settings_mock():
    temp_dir = tempfile.TemporaryDirectory()
    QSettings().setValue('locale/userLocale', "nl")
    QSettings().setValue('NADmaps/working_dir', temp_dir.name)
