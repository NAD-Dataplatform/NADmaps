import json
import os.path

import pytest
from qgis.core import QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import QSettings

from ..nad_maps import NADMaps


@pytest.fixture()
def selected_active_layers():
    return [
        QgsRasterLayer("url='source_1_url' typename='source_1_typename'", "name_1"),
        QgsVectorLayer("url='source_2_url' typename='source_2_typename'", "name_2"),
    ]


@pytest.fixture()
def nadmap_mock(iface_mock, selected_active_layers):
    # Preset some member of NADMaps to allow testing
    nadmap = NADMaps(iface_mock)
    nadmap.initGui()
    # nadmap.setup_models()
    nadmap.creator = "Gebruiker"
    nadmap.thema_manager.creator = "Gebruiker"
    nadmap.working_dir = QSettings().value("NADmaps/working_dir")
    nadmap.thema_manager.user_thema_path = os.path.join(
        nadmap.working_dir, "themas/user_themas.json"
    )
    nadmap.selected_active_layers = selected_active_layers
    nadmap.dlg.saveThemaLineEdit.setText("test theme name")
    return nadmap


@pytest.fixture()
def thema_manager_mock(nadmap_mock):
    # Returns a fully initialized thema_manager
    return nadmap_mock.thema_manager


def test_save_thema(thema_manager_mock, selected_active_layers):
    # Save a theme with dummy layer and check the resulting json
    thema_manager_mock.save_thema(
        all=False, selected_active_layers=selected_active_layers
    )

    # Check whether the json contains expected values
    with open(thema_manager_mock.user_thema_path) as json_file:
        json_data = json.load(json_file)
        assert len(json_data) == 1
        assert json_data[0]["thema_name"] == "test theme name"
        assert json_data[0]["creator"] == "Gebruiker"
        assert len(json_data[0]["layers"]) == 2
        assert json_data[0]["layers"][0]["name"] == "name_1"
        assert json_data[0]["layers"][0]["source"] == "source_1_url source_1_typename"
        assert json_data[0]["layers"][0]["provider_type"] == "gdal"
        assert json_data[0]["layers"][0]["layer_type"] == "Raster"
        assert json_data[0]["layers"][1]["name"] == "name_2"
        assert json_data[0]["layers"][1]["source"] == "source_2_url source_2_typename"
        assert json_data[0]["layers"][1]["provider_type"] == "ogr"
        assert json_data[0]["layers"][1]["layer_type"] == "Vector"


def test_delete_thema(nadmap_mock, thema_manager_mock, selected_active_layers):
    # Save two themes with dummy layer, remove one and check the resulting json
    thema_manager_mock.save_thema(
        all=False, selected_active_layers=selected_active_layers
    )
    nadmap_mock.dlg.saveThemaLineEdit.setText("test theme name_2")
    thema_manager_mock.save_thema(
        all=False, selected_active_layers=selected_active_layers
    )

    # Check whether the json contains expected values for two themes
    with open(thema_manager_mock.user_thema_path) as json_file:
        json_data = json.load(json_file)
        assert len(json_data) == 2  # two themes
        assert json_data[0]["thema_name"] == "test theme name"
        assert json_data[1]["thema_name"] == "test theme name_2"

    # Now we'll delete the first theme
    setattr(thema_manager_mock, "current_thema", dict())
    thema_manager_mock.current_thema["thema_name"] = "test theme name"
    thema_manager_mock.current_thema["creator"] = "Gebruiker"
    thema_manager_mock.delete_thema()

    # Check whether the json contains expected values for one theme
    with open(thema_manager_mock.user_thema_path) as json_file:
        json_data = json.load(json_file)
        assert len(json_data) == 1  # 1 theme
        assert json_data[0]["thema_name"] == "test theme name_2"
        assert json_data[0]["creator"] == "Gebruiker"
        assert len(json_data[0]["layers"]) == 2
