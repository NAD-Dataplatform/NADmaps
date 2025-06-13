#########################################################################################
######################################  Show and load layers ############################
#########################################################################################
import urllib.request, urllib.parse, urllib.error
import json
import os.path
from .constants import PLUGIN_NAME

from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtCore import Qt, QRegularExpression, QSortFilterProxyModel, QItemSelectionModel
from qgis.PyQt.QtWidgets import QAbstractItemView
from qgis.core import (Qgis, QgsProject, QgsLayerTreeLayer, QgsRasterLayer,
                       QgsVectorLayer, QgsVectorTileLayer, QgsCoordinateReferenceSystem,
                       QgsFeatureRequest)


class LayerManager():
    def __init__(self, dlg, iface, plugin_dir, tr, style_manager, log):

        assert dlg is not None, "LayerManager: dlg is None"
        assert iface is not None, "LayerManager: iface is None"
        assert plugin_dir is not None, "LayerManager: plugin_dir is None"
        assert tr is not None, "LayerManager: tr is None"
        assert style_manager is not None, "LayerManager: style_manager is None"
        assert log is not None, "LayerManager: log is None"

        self.dlg = dlg
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.tr = tr
        self.style_manager = style_manager
        self.log = log
        
        # Model for the list of all active layers
        self.mapsModel = QStandardItemModel()

        self.proxyModelMaps = QSortFilterProxyModel()
        self.proxyModelMaps.setSourceModel(self.mapsModel)
        # self.proxyModelMaps.setFilterKeyColumn(1)

        self.dlg.activeMapListView.setModel(self.proxyModelMaps)
        self.dlg.activeMapListView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    
        # Model for the list of all layers available via the plugin
        self.layerModel = QStandardItemModel()
        self.layerFilter = QSortFilterProxyModel()
        self.layerFilter.setSourceModel(self.layerModel)
        self.layerFilter.setFilterKeyColumn(4)

        self.layerProxyModel = QSortFilterProxyModel()
        self.layerProxyModel.setSourceModel(self.layerFilter)
        self.layerProxyModel.setFilterKeyColumn(3)

        self.dlg.mapListView.setModel(self.layerProxyModel)
        self.dlg.mapListView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.dlg.mapListView.selectionModel().selectionChanged.connect(self.get_current_layer)
        self.dlg.mapListView.doubleClicked.connect(lambda: self.load_layer(None))  # Using lambda here to prevent sending signal parameters to the loadService() function

        self.dlg.searchLineEdit.textChanged.connect(self.filter_layers)

        QgsProject.instance().layerTreeRoot().layerOrderChanged.connect(lambda: self.update_active_layers_list())
        QgsProject.instance().layerTreeRoot().nameChanged.connect(lambda: self.update_active_layers_list())

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
        self.layerProxyModel.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        strlist = string.strip().split(" ")
        string = ""
        for s in strlist:
            string += f"{s}.*"
        # print(f"string: {string}")
        # self.log(f"List string {string}")
        regexp = QRegularExpression(string, QRegularExpression.PatternOption.CaseInsensitiveOption | QRegularExpression.PatternOption.InvertedGreedinessOption)
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
                layer_tree_layer = root.findLayer(layer) # QgsLayerTreeLayer: subclass of https://qgis.org/pyqgis/3.40/core/QgsLayerTreeNode.html
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
                
                itemLayername.setData(layer, Qt.ItemDataRole.UserRole) # get data: self.dlg.activeMapListView.selectedIndexes()[0].data(Qt.ItemDataRole.UserRole)
                itemType.setData(layer_tree_layer, Qt.ItemDataRole.UserRole) # get data: self.dlg.activeMapListView.selectedIndexes()[1].data(Qt.ItemDataRole.UserRole)

                self.mapsModel.appendRow(
                    [itemLayername, itemType, itemStyle, itemSource, itemOrder]
                )

        self.mapsModel.setHeaderData(4, Qt.Orientation.Horizontal, "Index")
        self.mapsModel.setHeaderData(3, Qt.Orientation.Horizontal, "Bron")
        self.mapsModel.setHeaderData(2, Qt.Orientation.Horizontal, "Opmaak")
        self.mapsModel.setHeaderData(1, Qt.Orientation.Horizontal, "Type")
        self.mapsModel.setHeaderData(0, Qt.Orientation.Horizontal, "Laagnaam")
        self.mapsModel.horizontalHeaderItem(4).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.mapsModel.horizontalHeaderItem(3).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.mapsModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.mapsModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.mapsModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
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
        self.layer_files = [
            "layers-nad.json", # eigen kaartlagen
            "layers-gwsw.json", # gwsw
            "layers-pzh.json", # provincie zuid-holland
            "layers-klimaatatlas.json", # klimaatatlas
            "layers-pdok.json", # pdok
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
        self.layerModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layerModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layerModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignmentFlag.AlignLeft)

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
        itemType.setToolTip(self.tr(tooltip))
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
            f'{serviceLayer["service_type"]} {layername} {serviceLayer["service_title"]} {serviceLayer["service_abstract"]} {styles_string}'
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
            return self.create_wms_layer(layername, title, url)
        elif servicetype == "wmts":
            return self.create_wmts_layer(layername, title, url, servicetype)
        elif servicetype == "wfs":
            return self.create_wfs_layer(layername, title, url)
            # layer = self.create_wfs_layer(layername, title, url)
            # return layer
        elif servicetype == "wcs":
            return self.create_wcs_layer(layername, title, url)
        elif servicetype == "api features":
            return self.create_oaf_layer(layername, title, url)
        elif servicetype == "api tiles":
            return self.create_oat_layer(title, url)
        else:
            self.show_warning(
                f"""Sorry, dit type laag: '{servicetype.upper()}'
                kan niet worden geladen door de plugin of door QGIS.
                Is het niet beschikbaar als wms, wmts, wfs, api features of api tiles (vectortile)?
                """
            )
            return

    def create_wfs_layer(self, layername, title, url):
        uri = f" pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0'"
        # uri = f" pagingEnabled='true' preferCoordinatesForWfsT11='false' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0'"

        # pagingEnabled='true' preferCoordinatesForWfsT11='false' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='gwsw:Default_Lijn' url='https://geodata.gwsw.nl/Maassluis' version='auto'
        return QgsVectorLayer(uri, title, "wfs")
        
    def create_wms_layer(self, layername, title, url):
        imgformat = self.current_layer["imgformats"].split(",")[0]
        crs = "EPSG:28992"

        style = self.current_layer["styles"]
        if style is not None:
            selected_style_name = style[0]["name"]
        else:
            selected_style_name = "default"

        uri = f"crs={crs}&layers={layername}&styles={selected_style_name}&format={imgformat}&url={url}"
        return QgsRasterLayer(uri, title, "wms")

    def create_wcs_layer(self, layername, title, url):
        # HACK to get WCS to work:
        # 1) fixed format to "GEOTIFF"
        # 2) remove the '?request=getcapabiliteis....' part from the url, unknown why this is required compared to wms/wfs
        # better approach would be to add the supported format(s) to the layers-pdok.json file and use that - this should be the approach when more
        # WCS services will be published by PDOK (currently it is only the AHN WCS)
        format = "GEOTIFF"
        uri = f"cache=AlwaysNetwork&crs=EPSG:28992&format={format}&identifier={layername}&url={url.split('?')[0]}"
        return QgsRasterLayer(uri, title, "wcs")

    def create_oaf_layer(self, layername, title, url):
        uri = f" pagingEnabled='true' restrictToRequestBBOX='1' preferCoordinatesForWfsT11='false' typename='{layername}' url='{url}'"
        return QgsVectorLayer(uri, title, "OAPIF")

    def build_tileset_url(self, url, tileset_id, for_request):
        url_template = url + "/tiles/" + tileset_id
        if for_request:
            return url_template + "/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt"
        return url_template + "/{z}/{y}/{x}?f=mvt"

    def create_oat_layer(self, title, url):
        # CRS does not work as expected in qgis/gdal. We can set a crs (non-webmercator), but it is rendered incorrectly.
        crs = "EPSG:3857"
        used_tileset = [
            tileset
            for tileset in self.current_layer["tiles"][0]["tilesets"]
            if tileset["tileset_crs"].endswith(crs.split(":")[1])
        ][0]

        # styleUrl=https://api.pdok.nl/lv/bag/ogc/v1_0/styles/bag_standaardvisualisatie_compleet__webmercatorquad?f=mapbox&url=https://api.pdok.nl/lv/bag/ogc/v1_0/tiles/WebMercatorQuad/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt&type=xyz&zmax=17&zmin=0&http-header:referer=
        # styleUrl=https://api.pdok.nl/lv/bag/ogc/v1_0/styles/bag_standaardvisualisatie__europeanetrs89_laeaquad?f=mapbox&url=https://api.pdok.nl/lv/bag/ogc/v1_0/tiles/NetherlandsRDNewQuad/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt&type=xyz&zmax=12&zmin=0&http-header:referer=
        # styleUrl=https://api.pdok.nl/lv/bag/ogc/v1_0/styles/bag_standaardvisualisatie_compleet__europeanetrs89_laeaquad?f=mapbox&url=https://api.pdok.nl/lv/bag/ogc/v1_0/tiles/NetherlandsRDNewQuad/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt&type=xyz&zmax=12&zmin=0&http-header:referer=
        # Style toevoegen in laag vanuit ui
        # selected_style = self.get_selected_style()
        # selected_style_url = "bgt_standaardvisualisatie__netherlandsrdnewquad"
        style = 0
        name = self.current_layer["styles"][style]["name"]
        title += f" [{name}]"
        selected_style_url = self.current_layer["styles"][style]["url"]

        # if selected_style is not None:
        #     selected_style_url = selected_style["url"]
        #     title += f" [{selected_style['name']}]"
        # if selected_style is not None:
        #     selected_style_url = selected_style["url"]
        #     title += f" [{selected_style['name']}]"

        url_template = self.build_tileset_url(url, used_tileset["tileset_id"], True)
        
        maxz_coord = used_tileset["tileset_max_zoomlevel"]

        # Although the vector tiles are only rendered for a specific zoom-level @PDOK (see maxz_coord),
        # we need to set the minimum z value to 0, which gives better performance, see https://github.com/qgis/QGIS/issues/54312
        minz_coord = 0

        type = "xyz"
        uri = f"styleUrl={selected_style_url}&url={url_template}&type={type}&zmax={maxz_coord}&zmin={minz_coord}&http-header:referer="
        tile_layer = QgsVectorTileLayer(uri, title)
        # styleUrl=https://api.pdok.nl/lv/bag/ogc/v1_0/styles/bag_standaardvisualisatie__netherlandsrdnewquad?f=mapbox&url=https://api.pdok.nl/lv/bag/ogc/v1_0/tiles/WebMercatorQuad/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt&type=xyz&zmax=17&zmin=0&http-header:referer=
        # Set the VT layer CRS and load the styleUrl
        tile_layer.setCrs(srs=QgsCoordinateReferenceSystem(crs))
        tile_layer.loadDefaultStyle()
        return tile_layer

    def create_wmts_layer(self, layername, title, url, servicetype):
        if Qgis.QGIS_VERSION_INT < 10900:
            self.show_warning(
                f"""Sorry, dit type layer: '{servicetype.upper()}'
                kan niet worden geladen in deze versie van QGIS.
                Misschien kunt u QGIS 2.0 installeren (die kan het WEL)?
                Of is de laag niet ook beschikbaar als wms of wfs?"""
            )
            return None
        url = self.quote_wmts_url(url)
        imgformat = self.current_layer["imgformats"].split(",")[0]
        tilematrixset = self.current_layer["tilematrixsets"]
        crs = "EPSG:28992"

        uri = f"crs={crs}&tileMatrixSet={tilematrixset}&layers={layername}&styles=default&format={imgformat}&url={url}"
        return QgsRasterLayer(
            uri, title, "wms"
        )  # LET OP: `wms` is correct, zie ook quote_wmts_url

    def quote_wmts_url(self, url):
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
