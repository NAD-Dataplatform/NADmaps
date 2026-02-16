#########################################################################################
######################################  Show and load layers ############################
#########################################################################################
import urllib.request, urllib.parse, urllib.error
import json
import os.path

from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QAbstractItemView
from qgis.PyQt.QtCore import (
    Qt,
    QSettings,
    QRegularExpression,
    QSortFilterProxyModel,
    QPoint
)
from qgis.core import (
    Qgis,
    QgsSettings,
    QgsProject,
    QgsLayerTreeLayer,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsVectorTileLayer,
    QgsCoordinateReferenceSystem,
    QgsDataSourceUri,
)

from .constants import SERVICE_TYPE_MAPPING

from .utility import (
    extract_spatialiate_db,
    extract_spatialiate_table,
    extract_spatialiate_geom_column
)

def create_wfs_layer(layername, url, title=None):
    maxnumfeatures = QgsSettings().value( "NADmaps/maxNumFeatures", 5000, type=int )

    if QSettings().value("NADmaps/maxNumFeaturesCheck", False, type=bool) == True:
        uri = f" pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0' maxNumFeatures='{maxnumfeatures}'"
    else:
        uri = f" pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0'"
    return QgsVectorLayer(uri, title, "wfs")

def create_wms_layer(layer, layername, url, title=None):
    if "imgformats" in layer:
        imgformat = layer["imgformats"].split(",")[0]
    else:
        imgformat = "image/png"

    try:
        crs = layer["crs"].split(",")[0]
    except:
        crs = "EPSG:28992"

    if "styles" in layer:
        selected_style_name = layer["styles"][0]["name"]
        selected_style_title = layer["styles"][0]["title"]
        if selected_style_title != "":
            title += f" [{selected_style_title}]"
        else:
            title += f" [{selected_style_name}]"
    else:
        selected_style_name = "default"

    uri = f"crs={crs}&layers={layername}&styles={selected_style_name}&format={imgformat}&url={url}"
    return QgsRasterLayer(uri, title, "wms")

def create_wcs_layer(layername, url, title=None):
    format = "GEOTIFF"
    uri = f"cache=AlwaysNetwork&crs=EPSG:28992&format={format}&identifier={layername}&url={url.split('?')[0]}"
    return QgsRasterLayer(uri, title, "wcs")

def create_oaf_layer(layername, url, title=None):
    maxnumfeatures = QgsSettings().value( "NADmaps/maxNumFeatures", 5000, type=int )
    
    if QSettings().value("NADmaps/maxNumFeaturesCheck", False, type=bool) == True:
        uri = f" pagingEnabled='true' pageSize='100' restrictToRequestBBOX='1' preferCoordinatesForWfsT11='false' typename='{layername}' url='{url}' maxNumFeatures='{maxnumfeatures + 1}'"
    else:
        uri = f" pagingEnabled='true' pageSize='100' restrictToRequestBBOX='1' preferCoordinatesForWfsT11='false' typename='{layername}' url='{url}'"
    return QgsVectorLayer(uri, title, "OAPIF")

def build_tileset_url(url, tileset_id, for_request):
    url_template = url + "/tiles/" + tileset_id
    if for_request:
        return url_template + "/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt"
    return url_template + "/{z}/{y}/{x}?f=mvt"

def create_oat_layer(layer, url, title=None):
    crs = "EPSG:3857"
    # used_tileset = [
    #     tileset
    #     for tileset in layer["tiles"][0]["tilesets"]
    #     if tileset["tileset_crs"].endswith(crs.split(":")[1])
    # ][0]

    style = 0
    name = layer["styles"][style]["name"]
    title += f" [{name}]"
    selected_style_url = layer["styles"][style]["url"]

    # tileset_id = used_tileset["tileset_id"]
    tileset_id = "WebMercatorQuad"
    url_template = build_tileset_url(url, tileset_id, True)

    # maxz_coord = used_tileset["tileset_max_zoomlevel"]
    maxz_coord = 11
    minz_coord = 0

    type = "xyz"
    uri = f"styleUrl={selected_style_url}&url={url_template}&type={type}&zmax={maxz_coord}&zmin={minz_coord}&http-header:referer="

    tile_layer = QgsVectorTileLayer(uri, title)
    tile_layer.setCrs(srs=QgsCoordinateReferenceSystem(crs))
    tile_layer.loadDefaultStyle()
    return tile_layer

def create_wmts_layer(layer, layername, url, title=None):
    if Qgis.QGIS_VERSION_INT < 10900:
        return None
    url = quote_wmts_url(url)
    imgformat = layer["imgformats"].split(",")[0]

    tilematrixsets = layer["tilematrixsets"]
    if tilematrixsets.startswith("EPSG:"):
        tilematrixset = "EPSG:28992"
        crs = "EPSG:28992"
    elif tilematrixsets.startswith("OGC:1.0"):
        tilematrixset = "OGC:1.0:GoogleMapsCompatible"
        crs = "EPSG:3857"
    else:
        tilematrixset = tilematrixsets
        crs = "EPSG:28992"

    uri = f"crs={crs}&tileMatrixSet={tilematrixset}&layers={layername}&styles=default&format={imgformat}&url={url}"
    return QgsRasterLayer(uri, title, "wms")

def quote_wmts_url(url):
    """
    Quoten wmts url is nodig omdat qgis de query param `SERVICE=WMS` erachter plakt als je de wmts url niet quote.
    Dit vermoedelijk omdat de wmts laag wordt toegevoegd mbv de wms provider: `return QgsRasterLayer(uri, title, "wms")`.
    Wat op basis van de documentatie wel de manier is om een wmts laag toe te voegen.
    """
    parse_result = urllib.parse.urlparse(url)
    location = f"{parse_result.scheme}://{parse_result.netloc}{parse_result.path}"
    query = parse_result.query
    query_escaped_quoted = urllib.parse.quote_plus(query)
    url = f"{location}?{query_escaped_quoted}"
    return url

def create_spatialite_layer(layer, title=None):
    # https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/loadlayer.html
    source = layer["source"]
    
    db = extract_spatialiate_db(source)
    schema = ''
    table = extract_spatialiate_table(source)
    geom_column = extract_spatialiate_geom_column(source)
    
    uri = QgsDataSourceUri()
    uri.setDatabase(db)
    uri.setDataSource(schema, table, geom_column)
    return QgsVectorLayer(uri.uri(), title, 'spatialite')

def create_new_layer(layer):
    servicetype = layer["service_type"]
    title = layer["title"]
    layername = layer["name"]
    url = layer["service_url"]

    if servicetype == "wms":
        return create_wms_layer(layer, layername, url, title)
    elif servicetype == "wmts":
        return create_wmts_layer(layer, layername, url, title)
    elif servicetype == "wfs":
        return create_wfs_layer(layername, url, title)
    elif servicetype == "wcs":
        return create_wcs_layer(layername, url, title)
    elif servicetype == "api features":
        return create_oaf_layer(layername, url, title)
    elif servicetype == "api tiles":
        return create_oat_layer(layer, url, title)
    elif servicetype == "spatialite":
        return create_spatialite_layer(layer, title)
    else:
        try:
            layer_type = layer["layer_type"]
            if layer_type == "Vector":
                uri = layer["source"]
                return QgsVectorLayer(uri, title, servicetype)
            elif layer_type == "Raster":
                uri = layer["source"]
                return QgsRasterLayer(uri, title, servicetype)
        except:
            raise ValueError(
                f"Unsupported service type: {servicetype}. Supported types are: wms, wmts, wfs, wcs, api features, api tiles."
            )


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

        ##################################################################
        # Model for the list of all active layers
        self.mapsModel = QStandardItemModel()

        self.proxyModelMaps = QSortFilterProxyModel()
        self.proxyModelMaps.setSourceModel(self.mapsModel)
        # self.proxyModelMaps.setFilterKeyColumn(0)

        self.dlg.activeMapListView.setModel(self.proxyModelMaps)
        self.dlg.activeMapListView.setEditTriggers( QAbstractItemView.EditTrigger.NoEditTriggers )
        
        QgsProject.instance().layerTreeRoot().layerOrderChanged.connect( lambda: self.update_active_layers_list() )
        QgsProject.instance().layerTreeRoot().nameChanged.connect( lambda: self.update_active_layers_list() )

        ##################################################################
        # Model for the list of all layers available via the plugin
        self.layerModel = QStandardItemModel()

        # Add filtering model
        self.layerProxyModel = QSortFilterProxyModel()
        self.layerProxyModel.setSourceModel(self.layerModel)
        self.layerProxyModel.setFilterKeyColumn(3)

        self.layerProxyModel.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.layerProxyModel.setRecursiveFilteringEnabled(True) # Filter on children as well
        
        # Attach model to GUI object mapListView
        self.dlg.mapListView.setModel(self.layerProxyModel)
        self.dlg.mapListView.setAlternatingRowColors(True)
        self.dlg.mapListView.setEditTriggers( QAbstractItemView.EditTrigger.NoEditTriggers )

        self.dlg.mapListView.selectionModel().selectionChanged.connect( self.get_current_layer )
        self.dlg.mapListView.doubleClicked.connect( lambda: self.load_layer(None) )  # Using lambda here to prevent sending signal parameters to the loadService() function

        self.dlg.searchLineEdit.textChanged.connect(self.filter_layers)

        ##################################################################
        # Set default layer loading behaviour
        self.service_type_mapping = SERVICE_TYPE_MAPPING
        self.default_tree_locations = {
            "wms": "top",
            "wmts": "bottom",
            "wfs": "top",
            "wcs": "top",
            "api features": "top",
            "api tiles": "bottom",
        }

    ############################# Search in all layers list ######################

    def filter_layers(self, string: str):
        """
        Filter the list of layers using the search bar

        :param string: str
        Text written by the user in the search bar
        """
        # self.dlg.mapListView.selectRow(0)

        strlist = string.strip().split(" ")
        string = ""
        for s in strlist:
            string += f"{s}.*"

        regexp = QRegularExpression(
            string,
            QRegularExpression.PatternOption.CaseInsensitiveOption
            | QRegularExpression.PatternOption.InvertedGreedinessOption,
        )

        self.layerProxyModel.setFilterRegularExpression(regexp)

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
        """
        Update the table with active layers in the project
        """
        self.mapsModel.clear()

        root = QgsProject.instance().layerTreeRoot()
        layers = root.layerOrder() # returns List[QgsMapLayer]

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
                # Layer name (first column, so we add json layer data as a hidden value)
                itemLayername = QStandardItem(str(layer.name()))

                # Service type
                provider_type = layer.providerType()
                if "WMTS" in layer.source():
                    provider_type = "wmts"

                stype = (
                    self.service_type_mapping[provider_type]
                    if provider_type in self.service_type_mapping
                    else provider_type.upper()
                )

                itemType = QStandardItem(str(stype))
                
                # Styling
                style_name = layer.customProperty("layerStyle", "")
                if "|" in style_name:
                    style_name = style_name.split("|")[0].strip()

                itemStyle = QStandardItem(str(style_name))

                # Source url
                itemSource = QStandardItem(str(layer.source()))
                itemSource.setToolTip(str(layer.source()))

                # Table ordering filter
                itemOrder = QStandardItem(str(i))

                # Pass data to user role (hidden data object attached to table cell)
                layer_tree_layer = root.findLayer(layer)
                itemLayername.setData( layer, Qt.ItemDataRole.UserRole )        # get data: self.dlg.activeMapListView.selectedIndexes()[0].data(Qt.ItemDataRole.UserRole)
                itemType.setData( layer_tree_layer, Qt.ItemDataRole.UserRole )  # get data: self.dlg.activeMapListView.selectedIndexes()[1].data(Qt.ItemDataRole.UserRole)

                self.mapsModel.appendRow(
                    [itemLayername, itemType, itemStyle, itemSource, itemOrder]
                )

        # Format the table
        self.mapsModel.setHorizontalHeaderLabels(["Laagnaam", "Type", "Opmaak", "Bron", "Index"])
        self.mapsModel.horizontalHeaderItem(4).setTextAlignment( Qt.AlignmentFlag.AlignLeft )
        self.mapsModel.horizontalHeaderItem(3).setTextAlignment( Qt.AlignmentFlag.AlignLeft )
        self.mapsModel.horizontalHeaderItem(2).setTextAlignment( Qt.AlignmentFlag.AlignLeft )
        self.mapsModel.horizontalHeaderItem(1).setTextAlignment( Qt.AlignmentFlag.AlignLeft )
        self.mapsModel.horizontalHeaderItem(0).setTextAlignment( Qt.AlignmentFlag.AlignLeft )
        
        self.dlg.activeMapListView.horizontalHeader().setStretchLastSection(True)
        self.dlg.activeMapListView.hideColumn(4)
        self.dlg.activeMapListView.setColumnWidth(0, 200)  # set name to 300px (there are some huge layernames)
        self.dlg.activeMapListView.horizontalHeader().setStretchLastSection(True)

    ############################# All web layer list #############################

    def load_layer_list(self) -> dict:
        """
        Load the list of all map layers a Qt table.
        
        :return layer_list: dict
        """
        file_path = os.path.join(self.plugin_dir, "resources", "layers")
        layer_files = [pos_json for pos_json in os.listdir(file_path) if pos_json.endswith('.json')]
        self.log(f"layer files found: {layer_files}")

        meta_data = self.get_meta_data()

        layer_list = []
        for file_name in layer_files:
            title = None
            if file_name == "all-nad.json":
                title = "NAD kaartlagen"
            else:
                # Add title from metadata to the layer
                for dataset in meta_data:
                    meta_data_name = f"{dataset['name']}-{dataset['service_type']}.json"
                    if meta_data_name == file_name:
                        service_type = (
                            self.service_type_mapping[dataset["service_type"]]
                            if dataset["service_type"] in self.service_type_mapping
                            else dataset["service_type"].upper()
                        )
                        title = f"{dataset['title']} [{service_type}]"

            if not title:
                self.log(f"Dataset with file name {file_name} has no metadata.")
                continue

            layers = self.add_source_rows(file_name, file_path, title)
            layer_list.extend(layers)

        # Format the table layout
        self.dlg.mapListView.hideColumn(2)             # hide Service name
        self.dlg.mapListView.hideColumn(3)             # hide itemFilter column
        self.dlg.mapListView.setColumnWidth( 0, 300 )  # set name to 300px (there are some huge layernames)

        self.layerModel.setHorizontalHeaderLabels(["Laagnaam", "Type", "Service", "Filter"])
        self.layerModel.horizontalHeaderItem(2).setTextAlignment( Qt.AlignmentFlag.AlignLeft )
        self.layerModel.horizontalHeaderItem(1).setTextAlignment( Qt.AlignmentFlag.AlignLeft )
        self.layerModel.horizontalHeaderItem(0).setTextAlignment( Qt.AlignmentFlag.AlignLeft )

        # TODO: expand the first parent
        point = QPoint(0, 0)
        first_row = self.dlg.mapListView.indexAt(point)
        self.dlg.mapListView.setExpanded(first_row, True)

        return layer_list

    def add_source_rows(self, json_file: str, file_path: str, title: str) -> dict:
        """
        Add a row to the layerModel (QStandardItemModel) in table format. 
        We fill the column values with text and add the serviceLayer-data to the UserRole of the first column.
        See: https://www.riverbankcomputing.com/static/Docs/PyQt4/qt.html#ItemDataRole-enum
        
        :param json_file: json object with info like service type (wfs, wms, etc.), name and url
        """
        layer_path = os.path.join(file_path, json_file)
        with open(layer_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create parent item (subheader)
        parent = QStandardItem(title)
        parent_row = [parent, QStandardItem(""), QStandardItem(""), QStandardItem("")]

        for layer in data:
            # Layer name (first column, so we add json layer data as a hidden value)
            layername = layer["title"]
            itemLayername = QStandardItem(str(layer["title"]))
            itemLayername.setData(layer, Qt.ItemDataRole.UserRole)

            # Service type
            stype = (
                self.service_type_mapping[layer["service_type"]]
                if layer["service_type"] in self.service_type_mapping
                else layer["service_type"].upper()
            )
            itemType = QStandardItem(str(stype))

            # Service name (e.g. PDOK or Legger Delfland)
            itemServicetitle = QStandardItem(str(layer["service_title"]))

            # Item filter (used to search filter in. This column is hidden from the user)
            itemFilter = QStandardItem(
                f"{layer['service_type']} {layername} {layer['service_title']} {layer['service_abstract']}"
            )

            # tooltip = "Dubbelklik om een kaartlaag in te laden"
            tooltip = layer["service_abstract"]
            itemType.setToolTip(tooltip)
            itemLayername.setToolTip(tooltip)
            itemServicetitle.setToolTip(tooltip)

            parent.appendRow(
                [itemLayername, itemType, itemServicetitle, itemFilter]
            )

        self.layerModel.appendRow(parent_row)

        return data

    def get_meta_data(self):
        source_path = os.path.join(self.plugin_dir, "resources", "layer_sources")
        source_filepaths = [os.path.join(root, name)
             for root, dirs, files in os.walk(source_path) # walk: to recursively iterate through a directory and all its subdirectories
             for name in files
             if name.endswith(".json") and not name.endswith("main_csw.json")] # get all json files except file containing the CatalogueServiceWeb urls

        meta_data = []
        for source in source_filepaths:
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta_data.extend(data)

        return meta_data

    def load_layer(self, tree_location=None):
        """Adds a QgsLayer to the project and layer tree.
        tree_location can be 'default', 'top', 'bottom'
        """
        if self.current_layer is None:
            return

        servicetype = self.current_layer["service_type"]
        if tree_location is None:
            tree_location = self.default_tree_locations[servicetype]

        new_layer = create_new_layer(self.current_layer)
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
