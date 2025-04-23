import json
import os.path

import pytest
from qgis.core import QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import QSettings

from ..nad_maps import NADMaps


@pytest.fixture()
def nadmap_mock(iface_mock, tmp_path):
    # Preset some member of NADMaps to allow testing
    nadmap = NADMaps(iface_mock)
    nadmap.initGui()
    # nadmap.setup_models()
    nadmap.creator = "Gebruiker"
    nadmap.working_dir = QSettings().value('NADmaps/working_dir')
    print(nadmap.working_dir)
    nadmap.user_thema_path = os.path.join(nadmap.working_dir, "themas/thema.json")
    print(nadmap.user_thema_path)
    nadmap.selected_active_layers = [QgsRasterLayer("source_1", "name_1"), QgsVectorLayer("source_2", "name_2")]
    nadmap.dlg.saveThemaLineEdit.setText("test theme name")
    return nadmap