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
    nadmap.thema_manager.creator = "Gebruiker"
    print(f"nadmap_mock: {nadmap.creator}")
    nadmap.working_dir = QSettings().value('NADmaps/working_dir')
    print(nadmap.working_dir)
    nadmap.user_thema_path = os.path.join(nadmap.working_dir, "themas/user_themas.json")
    print(nadmap.user_thema_path)
    nadmap.selected_active_layers = [QgsRasterLayer("source_1", "name_1"), QgsVectorLayer("source_2", "name_2")]
    nadmap.dlg.saveThemaLineEdit.setText("test theme name")
    return nadmap

def test_save_thema(nadmap_mock):
    # Save a theme with dummy layer and check the resulting json
    print(f"test_save_thema: {nadmap_mock.creator}")
    nadmap_mock.thema_manager.save_thema(all=False, selected_active_layers = nadmap_mock.selected_active_layers)

    # Check whether the json contains expected values
    with open(nadmap_mock.user_thema_path) as json_file:
        json_data = json.load(json_file)
        assert len(json_data) == 1
        assert json_data[0]["thema_name"] == "test theme name"
        assert json_data[0]["creator"] == "Gebruiker"
        assert len(json_data[0]["layers"]) == 2
        assert json_data[0]["layers"][0]["name"] == "name_1"
        assert json_data[0]["layers"][0]["source"] == "source_1"
        assert json_data[0]["layers"][0]["provider_type"] == "gdal"
        assert json_data[0]["layers"][0]["layer_type"] == "Raster"
        assert json_data[0]["layers"][1]["name"] == "name_2"
        assert json_data[0]["layers"][1]["source"] == "source_2"
        assert json_data[0]["layers"][1]["provider_type"] == "ogr"
        assert json_data[0]["layers"][1]["layer_type"] == "Vector"

def test_delete_thema(nadmap_mock):
    # Save two themes with dummy layer, remove one and check the resulting json
    nadmap_mock.thema_manager.save_thema(all=False, selected_active_layers = nadmap_mock.selected_active_layers)
    nadmap_mock.dlg.saveThemaLineEdit.setText("test theme name_2")
    nadmap_mock.thema_manager.save_thema(all=False, selected_active_layers = nadmap_mock.selected_active_layers)

    # Check whether the json contains expected values for two themes
    with open(nadmap_mock.user_thema_path) as json_file:
        json_data = json.load(json_file)
        assert len(json_data) == 2  # two themes
        assert json_data[0]["thema_name"] == "test theme name"
        assert json_data[1]["thema_name"] == "test theme name_2"
    
    # Now we'll delete the first theme
    setattr(nadmap_mock.thema_manager, "current_thema", dict())
    nadmap_mock.thema_manager.current_thema["thema_name"] = "test theme name"
    nadmap_mock.thema_manager.current_thema["creator"] = "Gebruiker"
    nadmap_mock.thema_manager.delete_thema()

    # Check whether the json contains expected values for one theme
    with open(nadmap_mock.user_thema_path) as json_file:
        json_data = json.load(json_file)
        assert len(json_data) == 1  # 1 theme
        assert json_data[0]["thema_name"] == "test theme name_2"
        assert json_data[0]["creator"] == "Gebruiker"
        assert len(json_data[0]["layers"]) == 2
