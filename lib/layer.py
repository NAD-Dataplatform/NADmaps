#########################################################################################
######################################  Show and load layers ############################
#########################################################################################
import urllib.request, urllib.parse, urllib.error
import json
import os.path
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService

# import urllib2,

# import urllib2,
import re
import requests
import xml.etree.ElementTree as ET
from .constants import PLUGIN_NAME

from qgis.PyQt.QtXml import QDomDocument, QDomElement
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtCore import (
    Qt,
    QRegularExpression,
    QSortFilterProxyModel,
    QItemSelectionModel,
)
from qgis.PyQt.QtCore import (
    Qt,
    QRegularExpression,
    QSortFilterProxyModel,
    QItemSelectionModel,
)
from qgis.PyQt.QtWidgets import QAbstractItemView
from qgis.core import QgsSettings
from qgis.core import (
    Qgis,
    QgsProject,
    QgsLayerTreeLayer,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsVectorTileLayer,
    QgsCoordinateReferenceSystem,
    QgsFeatureRequest,
)
from qgis.core import QgsSettings
from qgis.core import (
    Qgis,
    QgsProject,
    QgsLayerTreeLayer,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsVectorTileLayer,
    QgsCoordinateReferenceSystem,
    QgsFeatureRequest,
)


def create_wfs_layer(layername, url, maxnumfeatures, return_layer=False, title=None):
    uri = f" pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0' maxNumFeatures='{maxnumfeatures}'"
    if return_layer:
        return QgsVectorLayer(uri, title, "wfs")
    return uri


def create_wms_layer(layer, layername, url, return_layer=False, title=None):
    imgformat = layer["imgformats"].split(",")[0]
    crs = "EPSG:28992"

    style = layer["styles"]
    if style is not None:
        selected_style_name = style[0]["name"]
    else:
        selected_style_name = "default"

    uri = f"crs={crs}&layers={layername}&styles={selected_style_name}&format={imgformat}&url={url}"
    if return_layer:
        return QgsRasterLayer(uri, title, "wms")
    return uri


def create_wcs_layer(layername, url, return_layer=False, title=None):
    format = "GEOTIFF"
    uri = f"cache=AlwaysNetwork&crs=EPSG:28992&format={format}&identifier={layername}&url={url.split('?')[0]}"
    if return_layer:
        return QgsRasterLayer(uri, title, "wcs")
    return uri


def create_oaf_layer(layername, url, maxnumfeatures, return_layer=False, title=None):
    uri = f" pagingEnabled='true' pageSize='100' restrictToRequestBBOX='1' preferCoordinatesForWfsT11='false' typename='{layername}' url='{url}' maxNumFeatures='{maxnumfeatures + 1}'"
    if return_layer:
        return QgsVectorLayer(uri, title, "OAPIF")
    return uri


def build_tileset_url(url, tileset_id, for_request):
    url_template = url + "/tiles/" + tileset_id
    if for_request:
        return url_template + "/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt"
    return url_template + "/{z}/{y}/{x}?f=mvt"


def create_oat_layer(layer, url, return_layer=False, title=None):
    crs = "EPSG:3857"
    used_tileset = [
        tileset
        for tileset in layer["tiles"][0]["tilesets"]
        if tileset["tileset_crs"].endswith(crs.split(":")[1])
    ][0]

    style = 0
    name = layer["styles"][style]["name"]
    title += f" [{name}]"
    selected_style_url = layer["styles"][style]["url"]

    url_template = build_tileset_url(url, used_tileset["tileset_id"], True)
    maxz_coord = used_tileset["tileset_max_zoomlevel"]

    minz_coord = 0

    type = "xyz"
    uri = f"styleUrl={selected_style_url}&url={url_template}&type={type}&zmax={maxz_coord}&zmin={minz_coord}&http-header:referer="
    if return_layer:
        tile_layer = QgsVectorTileLayer(uri, title)
        tile_layer.setCrs(srs=QgsCoordinateReferenceSystem(crs))
        tile_layer.loadDefaultStyle()
        return tile_layer
    return uri


def create_wmts_layer(layer, layername, url, return_layer=False, title=None):
    if Qgis.QGIS_VERSION_INT < 10900:
        return None
    url = quote_wmts_url(url)
    imgformat = layer["imgformats"].split(",")[0]
    tilematrixset = layer["tilematrixsets"]
    crs = "EPSG:28992"

    uri = f"crs={crs}&tileMatrixSet={tilematrixset}&layers={layername}&styles=default&format={imgformat}&url={url}"
    if return_layer:
        return QgsRasterLayer(uri, title, "wms")
    return uri


def quote_wmts_url(url):
    """
    Quoten wmts url is nodig omdat qgis de query param `SERVICE=WMS` erachter plakt als je de wmts url niet quote.
    Dit vermoedelijk omdat de wmts laag wordt toegevoegd mbv de wms provider: `return QgsRasterLayer(uri, title, "wms")`.
    Wat op basis van de documentatie wel de manier is om een wmts laag toe te voegen.
    """
    parse_result = urllib.parse.urlparse(url)
    location = f"{parse_result.scheme}://{parse_result.netloc}/{parse_result.path}"
    query = parse_result.query
    query_escaped_quoted = urllib.parse.quote_plus(query)
    url = f"{location}?{query_escaped_quoted}"
    return url


class LayerManager:
    def __init__(self, dlg, iface, plugin_dir, style_manager, log):
        assert dlg is not None, "LayerManager: dlg is None"
        assert iface is not None, "LayerManager: iface is None"
        assert plugin_dir is not None, "LayerManager: plugin_dir is None"
        assert style_manager is not None, "LayerManager: style_manager is None"
        assert log is not None, "LayerManager: log is None"

        self.dlg = dlg
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.style_manager = style_manager
        self.log = log
        self.maxnumfeatures = QgsSettings().value(
            "nadmaps/wfs_maxnumfeatures", 5000, type=int
        )

        # Model for the list of all active layers
        self.mapsModel = QStandardItemModel()

        self.proxyModelMaps = QSortFilterProxyModel()
        self.proxyModelMaps.setSourceModel(self.mapsModel)
        # self.proxyModelMaps.setFilterKeyColumn(1)

        self.dlg.activeMapListView.setModel(self.proxyModelMaps)
        self.dlg.activeMapListView.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.dlg.activeMapListView.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        # Model for the list of all layers available via the plugin
        self.layerModel = QStandardItemModel()
        self.layerFilter = QSortFilterProxyModel()
        self.layerFilter.setSourceModel(self.layerModel)
        self.layerFilter.setFilterKeyColumn(4)

        self.layerProxyModel = QSortFilterProxyModel()
        self.layerProxyModel.setSourceModel(self.layerFilter)
        self.layerProxyModel.setFilterKeyColumn(3)

        self.dlg.mapListView.setModel(self.layerProxyModel)
        self.dlg.mapListView.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.dlg.mapListView.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.dlg.mapListView.selectionModel().selectionChanged.connect(
            self.get_current_layer
        )
        self.dlg.mapListView.doubleClicked.connect(
            lambda: self.load_layer(None)
        )  # Using lambda here to prevent sending signal parameters to the loadService() function

        self.dlg.searchLineEdit.textChanged.connect(self.filter_layers)

        QgsProject.instance().layerTreeRoot().layerOrderChanged.connect(
            lambda: self.update_active_layers_list()
        )
        QgsProject.instance().layerTreeRoot().nameChanged.connect(
            lambda: self.update_active_layers_list()
        )
        QgsProject.instance().layerTreeRoot().layerOrderChanged.connect(
            lambda: self.update_active_layers_list()
        )
        QgsProject.instance().layerTreeRoot().nameChanged.connect(
            lambda: self.update_active_layers_list()
        )

        # Set default layer loading behaviour
        self.service_type_mapping = {
            "wms": "WMS",
            "wmts": "WMTS",
            "wfs": "WFS",
            "wcs": "WCS",
            "api features": "OGC API - Features",
            "api tiles": "OGC API - Tiles",
        }

        self.default_tree_locations = {
            "wms": "top",
            "wmts": "bottom",
            "wfs": "top",
            "wcs": "top",
            "api features": "top",
            "api tiles": "bottom",
        }

        # bounding polygon
        # self.bound_file_path = "C:\Users\svanderhoeven\Documents\BGT Inlooptool 2024\gemeentegrens\naam_Delft.gpkg"
        # Get the polygon layer
        # polygon_name = "naam_Delft"

    ############################# Search in all layers list ######################

    def filter_layers(self, string):
        # remove selection if one row is selected
        self.dlg.mapListView.selectRow(0)
        self.layerProxyModel.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.layerProxyModel.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        strlist = string.strip().split(" ")
        string = ""
        for s in strlist:
            string += f"{s}.*"
        # print(f"string: {string}")
        # self.log(f"List string {string}")
        regexp = QRegularExpression(
            string,
            QRegularExpression.PatternOption.CaseInsensitiveOption
            | QRegularExpression.PatternOption.InvertedGreedinessOption,
        )
        regexp = QRegularExpression(
            string,
            QRegularExpression.PatternOption.CaseInsensitiveOption
            | QRegularExpression.PatternOption.InvertedGreedinessOption,
        )
        self.layerProxyModel.setFilterRegularExpression(regexp)
        self.layerProxyModel.insertRow

    ############################# Active layer list #############################

    def get_current_layer(self, selectedIndexes):
        if len(selectedIndexes) == 0:
            self.current_layer = None
            return

        self.dlg.mapListView.scrollTo(self.dlg.mapListView.selectedIndexes()[0])
        # itemType holds the data (== column 1) hence self.dlg.mapListView.selectedIndexes()[1], see itemType.setData(serviceLayer, Qt.ItemDataRole.UserRole)
        self.current_layer = self.dlg.mapListView.selectedIndexes()[0].data(
            Qt.ItemDataRole.UserRole
        )

    def update_active_layers_list(self):
        """Update the table with active layers in the project"""
        self.mapsModel.clear()

        # https://doc.qt.io/qt-6/qtwidgets-itemviews-simpletreemodel-example.html
        # layers = QgsProject.instance().mapLayers().values() # https://qgis.org/pyqgis/3.40/core/QgsMapLayer.html
        root = QgsProject.instance().layerTreeRoot()
        layers = root.layerOrder()

        if len(layers) < 1:
            itemLayername = QStandardItem(str(""))
            itemType = QStandardItem(str(""))
            itemStylingTitle = QStandardItem(str(""))
            itemSource = QStandardItem(str(""))
            itemOrder = QStandardItem(str(""))
            self.mapsModel.appendRow(
                [itemLayername, itemType, itemStylingTitle, itemSource, itemOrder]
            )
        else:
            for i, layer in enumerate(layers):
                # layer is the same value as QgsVectorLayer(uri, title, "wfs"), e.g. <QgsVectorLayer: 'Riolering WFS: Leiding' (WFS)>
                # self.log(f"Layer {layer} has name: {layer.name()} of type {layer.type()} with source {layer.source()}", 3)
                # https://gis.stackexchange.com/questions/383425/whats-a-provider-in-pyqgis-and-how-many-types-of-providers-exist
                layer_tree_layer = root.findLayer(
                    layer
                )  # QgsLayerTreeLayer: subclass of https://qgis.org/pyqgis/3.40/core/QgsLayerTreeNode.html
                layer_tree_layer = root.findLayer(
                    layer
                )  # QgsLayerTreeLayer: subclass of https://qgis.org/pyqgis/3.40/core/QgsLayerTreeNode.html
                provider_type = layer.providerType()

                itemLayername = QStandardItem(str(layer.name()))
                stype = (
                    self.service_type_mapping[provider_type]
                    if provider_type in self.service_type_mapping
                    else provider_type.upper()
                )
                itemType = QStandardItem(str(stype))
                style_name = layer.customProperty("layerStyle", "")
                if "|" in style_name:
                    style_name = style_name.split("|")[0].strip()

                itemStyle = QStandardItem(str(style_name))
                itemSource = QStandardItem(str(layer.source()))
                itemSource.setToolTip(str(layer.source()))
                itemOrder = QStandardItem(str(i))

                itemLayername.setData(
                    layer, Qt.ItemDataRole.UserRole
                )  # get data: self.dlg.activeMapListView.selectedIndexes()[0].data(Qt.ItemDataRole.UserRole)
                itemType.setData(
                    layer_tree_layer, Qt.ItemDataRole.UserRole
                )  # get data: self.dlg.activeMapListView.selectedIndexes()[1].data(Qt.ItemDataRole.UserRole)

                itemLayername.setData(
                    layer, Qt.ItemDataRole.UserRole
                )  # get data: self.dlg.activeMapListView.selectedIndexes()[0].data(Qt.ItemDataRole.UserRole)
                itemType.setData(
                    layer_tree_layer, Qt.ItemDataRole.UserRole
                )  # get data: self.dlg.activeMapListView.selectedIndexes()[1].data(Qt.ItemDataRole.UserRole)

                self.mapsModel.appendRow(
                    [itemLayername, itemType, itemStyle, itemSource, itemOrder]
                )

        self.mapsModel.setHeaderData(4, Qt.Orientation.Horizontal, "Index")
        self.mapsModel.setHeaderData(3, Qt.Orientation.Horizontal, "Bron")
        self.mapsModel.setHeaderData(2, Qt.Orientation.Horizontal, "Opmaak")
        self.mapsModel.setHeaderData(1, Qt.Orientation.Horizontal, "Type")
        self.mapsModel.setHeaderData(0, Qt.Orientation.Horizontal, "Laagnaam")
        self.mapsModel.horizontalHeaderItem(4).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(3).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(2).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(1).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(0).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(4).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(3).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(2).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(1).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.mapsModel.horizontalHeaderItem(0).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.dlg.activeMapListView.horizontalHeader().setStretchLastSection(True)
        self.dlg.activeMapListView.hideColumn(4)

        self.dlg.activeMapListView.setColumnWidth(
            0, 200
        )  # set name to 300px (there are some huge layernames)
        self.dlg.activeMapListView.horizontalHeader().setStretchLastSection(True)
        self.dlg.activeMapListView.sortByColumn(4, Qt.AscendingOrder)

    ############################# All web layer list #############################

    def load_layer_list(self):
        self.layers_nad = []
        # add a new json file with layer description to the resources/layers folder
        self.layer_files = [
            "layers-nad.json",  # eigen kaartlagen
            "layers-gwsw.json",  # gwsw
            "layers-pzh.json",  # provincie zuid-holland
            "layers-klimaatatlas.json",  # klimaatatlas
            "layers-pdok.json",  # pdok
            "layers-nad.json",  # eigen kaartlagen
            "layers-gwsw.json",  # gwsw
            "layers-pzh.json",  # provincie zuid-holland
            "layers-klimaatatlas.json",  # klimaatatlas
            "layers-pdok.json",  # pdok
        ]

        for file in self.layer_files:
            layer_path = os.path.join(self.plugin_dir, "resources/layers", file)
            with open(layer_path, "r", encoding="utf-8") as f:
                self.layers_nad.extend(json.load(f))

        for layer in self.layers_nad:
            if isinstance(layer["name"], str):
                self.add_source_row(layer)

        self.dlg.mapListView.verticalHeader().setSectionsClickable(False)
        self.dlg.mapListView.horizontalHeader().setSectionsClickable(False)
        # hide itemFilter column:
        self.dlg.mapListView.hideColumn(3)
        self.dlg.mapListView.setColumnWidth(
            0, 250
        )  # set name to 300px (there are some huge layernames)
        self.dlg.mapListView.horizontalHeader().setStretchLastSection(True)
        # self.dlg.mapListView.resizeColumnsToContents()

        self.layerModel.setHeaderData(2, Qt.Orientation.Horizontal, "Service")
        self.layerModel.setHeaderData(1, Qt.Orientation.Horizontal, "Type")
        self.layerModel.setHeaderData(0, Qt.Orientation.Horizontal, "Laagnaam")
        self.layerModel.horizontalHeaderItem(2).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.layerModel.horizontalHeaderItem(1).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.layerModel.horizontalHeaderItem(0).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.layerModel.horizontalHeaderItem(2).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.layerModel.horizontalHeaderItem(1).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )
        self.layerModel.horizontalHeaderItem(0).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

    def add_source_row(self, serviceLayer):
        # you can attache different "data's" to to an QStandarditem
        # default one is the visible one:
        stype = (
            self.service_type_mapping[serviceLayer["service_type"]]
            if serviceLayer["service_type"] in self.service_type_mapping
            else serviceLayer["service_type"].upper()
        )
        itemType = QStandardItem(str(stype))
        # userrole is a free form one:
        # only attach the data to the first item
        # service layer = a dict/object with all props of the layer
        # https://www.riverbankcomputing.com/static/Docs/PyQt4/qt.html#ItemDataRole-enum
        # tooltip = "Dubbelklik om een kaartlaag in te laden"
        tooltip = serviceLayer["service_abstract"]
        itemType.setToolTip(tooltip)
        # only wms services have styles (sometimes)
        layername = serviceLayer["title"]
        styles_string = ""
        if "styles" in serviceLayer:
            styles_string = " ".join(
                [" ".join(x.values()) for x in serviceLayer["styles"]]
            )

        itemLayername = QStandardItem(str(serviceLayer["title"]))
        itemLayername.setData(serviceLayer, Qt.ItemDataRole.UserRole)
        itemLayername.setToolTip(tooltip)
        # itemFilter is the item used to search filter in. That is why layername is a combi of layername + filter here
        itemFilter = QStandardItem(
            f"{serviceLayer['service_type']} {layername} {serviceLayer['service_title']} {serviceLayer['service_abstract']} {styles_string}"
            f"{serviceLayer['service_type']} {layername} {serviceLayer['service_title']} {serviceLayer['service_abstract']} {styles_string}"
        )
        itemServicetitle = QStandardItem(str(serviceLayer["service_title"]))
        itemServicetitle.setToolTip(tooltip)
        self.layerModel.appendRow(
            [itemLayername, itemType, itemServicetitle, itemFilter]
        )

    def load_layer(self, tree_location=None):
        """Adds a QgsLayer to the project and layer tree.
        tree_location can be 'default', 'top', 'bottom'
        """
        if self.current_layer is None:
            return

        servicetype = self.current_layer["service_type"]
        if tree_location is None:
            tree_location = self.default_tree_locations[servicetype]

        new_layer = self.create_new_layer()
        if new_layer is None:
            return

        if tree_location not in ["default", "top", "bottom"]:
            # TODO: proper error handling
            return

        if tree_location == "default":
            QgsProject.instance().addMapLayer(new_layer, True)
            return

        QgsProject.instance().addMapLayer(new_layer, False)
        new_layer_tree_layer = QgsLayerTreeLayer(new_layer)
        layer_tree = self.iface.layerTreeCanvasBridge().rootGroup()
        if tree_location == "top":
            layer_tree.insertChildNode(0, new_layer_tree_layer)
        if tree_location == "bottom":
            layer_tree.insertChildNode(-1, new_layer_tree_layer)

    def create_new_layer(self):
        servicetype = self.current_layer["service_type"]
        title = self.current_layer["title"]
        layername = self.current_layer["name"]
        url = self.current_layer["service_url"]

        if servicetype == "wms":
            return create_wms_layer(
                self.current_layer, layername, url, return_layer=True, title=title
            )
        elif servicetype == "wmts":
            return create_wmts_layer(
                self.current_layer, layername, url, return_layer=True, title=title
            )
        elif servicetype == "wfs":
            return create_wfs_layer(
                layername,
                url,
                maxnumfeatures=self.maxnumfeatures,
                return_layer=True,
                title=title,
            )
        elif servicetype == "wcs":
            return create_wcs_layer(layername, url, return_layer=True, title=title)
        elif servicetype == "api features":
            return create_oaf_layer(
                layername,
                url,
                maxnumfeatures=self.maxnumfeatures,
                return_layer=True,
                title=title,
            )
        elif servicetype == "api tiles":
            return create_oat_layer(
                self.current_layer, url, return_layer=True, title=title
            )
        else:
            self.show_warning(
                f"""Sorry, dit type laag: '{servicetype.upper()}'
                kan niet worden geladen door de plugin of door QGIS.
                Is het niet beschikbaar als wms, wmts, wfs, api features of api tiles (vectortile)?
                """
            )
            return
