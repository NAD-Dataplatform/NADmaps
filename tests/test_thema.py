import json

import pytest
from qgis.core import QgsRasterLayer, QgsVectorLayer

from ..nad_maps import NADMaps


@pytest.fixture()
def nadmap_mock(iface_mock, tmp_path):
    # Preset some member of NADMaps to allow testing
    nadmap = NADMaps(iface_mock)
    nadmap.initGui()
    # nadmap.setup_models()
    nadmap.creator = "Gebruiker"
    nadmap.user_thema_path = tmp_path / "resources/themas/thema.json"
    nadmap.selected_active_layers = [QgsRasterLayer("source_1", "name_1"), QgsVectorLayer("source_2", "name_2")]
    nadmap.dlg.saveThemaLineEdit.setText("test theme name")
    return nadmap

def test_save_thema(nadmap_mock):
    # Save a theme with dummy layer and check the resulting json
    print(f"print: {nadmap_mock.user_thema_path}")
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
        assert json_data[0]["layers"][1]["provider_type"] == "gdal"
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
    setattr(nadmap_mock, "current_thema", dict())
    nadmap_mock.current_thema["thema_name"] = "test theme name"
    nadmap_mock.current_thema["creator"] = "Gebruiker"
    nadmap_mock.thema_manager.delete_thema()

    # Check whether the json contains expected values for one theme
    with open(nadmap_mock.user_thema_path) as json_file:
        json_data = json.load(json_file)
        assert len(json_data) == 1  # 1 theme
        assert json_data[0]["thema_name"] == "test theme name_2"
        assert json_data[0]["creator"] == "Gebruiker"
        assert len(json_data[0]["layers"]) == 2
