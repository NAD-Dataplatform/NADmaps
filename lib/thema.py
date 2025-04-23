#########################################################################################
##############  Manage thema sets (a list of one or more map layers) ####################
#########################################################################################
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
import os
import json
from qgis.PyQt.QtCore import Qt, QRegularExpression, QSortFilterProxyModel, QItemSelectionModel
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtWidgets import QAbstractItemView
# from .load_layers import load_thema_layer
from .style import StyleManager


class ThemaManager:
    """
    Class to manage the thema sets (a list of one or more map layers)
    """
    def __init__(self, dlg, popup, plugin_dir, working_dir, creator, log):

        assert dlg is not None, "ThemaManager: dlg is None"
        assert popup is not None, "ThemaManager: popup is None"
        assert plugin_dir is not None, "ThemaManager: plugin_dir is None"
        assert working_dir is not None, "ThemaManager: working_dir is None"
        assert creator is not None, "ThemaManager: creator is None"
        assert log is not None, "ThemaManager: log is None"

        self.plugin_thema_path = os.path.join(plugin_dir, "resources", "themas", "thema.json")
        self.plugin_styling_path = os.path.join(plugin_dir, "resources", "styling", "styling.json")
        self.plugin_styling_files_path = os.path.join( plugin_dir, "resources", "styling", "qml_files")
        assert os.path.exists(self.plugin_thema_path), f"ThemaManager: plugin_thema_path does not exist: {self.plugin_thema_path}"

        self.set_working_directory(working_dir)
        
        self.dlg = dlg
        self.creator = creator
        self.log = log
        self.style_manager = StyleManager(dlg=self.dlg, popup=popup, plugin_dir=plugin_dir, working_dir=working_dir, creator=creator, log=self.log)

        self.current_thema = None
        self.current_layer = None
        self.themaModel = QStandardItemModel()
        self.dlg.themaView.setModel(self.themaModel)

        self.themaModel = QStandardItemModel()
        self.favoriteFilterThema = QSortFilterProxyModel()
        self.favoriteFilterThema.setSourceModel(self.themaModel)
        self.favoriteFilterThema.setFilterKeyColumn(1)
        self.favoriteFilterThema.setFilterRole(Qt.CheckStateRole) # https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSortFilterProxyModel.html#PySide6.QtCore.QSortFilterProxyModel.setFilterRole

        self.userFilterThema = QSortFilterProxyModel()
        self.userFilterThema.setSourceModel(self.favoriteFilterThema)
        self.userFilterThema.setFilterKeyColumn(2) # change this when you want to order by something else (like order in layer panel)

        self.dlg.themaView.setModel(self.userFilterThema)
        self.dlg.themaView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.themaViewSelectionModel = QItemSelectionModel(self.dlg.themaView.model())
        
        self.themaMapModel = QStandardItemModel()
        
        self.proxyModelThemaMaps = QSortFilterProxyModel()
        self.proxyModelThemaMaps.setSourceModel(self.themaMapModel)

        self.dlg.themaMapListView.setModel(self.proxyModelThemaMaps)
        self.dlg.themaMapListView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)


        self.dlg.themaView.clicked.connect(
            lambda cell: self.update_favorites(cell)
        )
        # Update the display with a list of map layers within the selected thema
        self.dlg.themaView.selectionModel().selectionChanged.connect(
            self.show_thema_layers
        )
        # TODO: what does this do?
        self.dlg.themaView.selectionModel().select(
            self.themaModel.index(0,0), QItemSelectionModel.Select | QItemSelectionModel.Rows
        )
        
        self.dlg.themaView.doubleClicked.connect(
            lambda: self.load_thema_layers()
        )  # Using lambda here to prevent sending signal parameters to the loadService() function

        self.service_type_mapping = {
            "wms": "WMS",
            "wmts": "WMTS",
            "wfs": "WFS",
            "wcs": "WCS",
            "api features": "OGC API - Features",
            "api tiles": "OGC API - Tiles",
        }

        self.layer_type_mapping = {
            0: "Vector",
            1: "Raster",
            2: "Plugin",
            3: "WMS",
            4: "WMTS",
            5: "ArcGISMapServer",
            6: "ArcGISFeatureServer",
            7: "XYZ",
            8: "WFS",
            9: "PostGIS",
            10: "Database"
        }
        # self.log("Finished init ThemaManager")

    def set_working_directory(self, path):
        """Set the working directory for the plugin"""
        # some checks if the path is not empty or a directory
        if not path:
            return
        if not os.path.isdir(path):
            return
        
        os.makedirs(path, exist_ok=True)
        os.makedirs(os.path.join(path, "themas"), exist_ok=True)

        self.user_thema_path = os.path.join( path, "themas", "user_themas.json")
        self.user_thema_favorite_path = os.path.join( path, "themas", "favorites.json")
        self.user_styling_path = os.path.join(path, "styling", "styling.json")
        self.user_styling_files_path = os.path.join(path, "styling", "qml_files")

    def delete_thema(self):
        """Delete an existing thema (only user defined themas should be deleted)"""

        # Find the thema name to be deleted
        thema_name = self.current_thema["thema_name"]

        # Check whether the thema is a plugin or user defined thema
        if self.current_thema["creator"] == "Plugin" and self.creator != "Plugin":
            self.log("Plugin thema's cannot be deleted")
            return
        
        if self.current_thema["creator"] == "Plugin":
            json_path = self.plugin_thema_path
        else:
            json_path = self.user_thema_path
            
        with open(json_path, "r", encoding="utf-8") as f:
            jsondata = json.load(f)

        # Iterate through the json list and remove the object with the selected name
        jsondata = [obj for obj in jsondata if obj["thema_name"] != thema_name]
        
        with open(json_path, "w", encoding="utf-8") as feedsjson:
            json.dump(jsondata, feedsjson, indent='\t')

        self.update_thema_list()

    def save_thema(self, all: bool, selected_active_layers):
        """
        Save a collection of layers in order to later quickly load them
        """
        if self.creator == "Plugin":
            json_path = self.plugin_thema_path
        else:
            json_path = self.user_thema_path
        
        # Collect a json string with a thema_name and a list of layer names
        thema_name = self.dlg.saveThemaLineEdit.text()
        print(self.creator)
        string = "{\"thema_name\": \"" + thema_name + "\", "
        string = f"{string}\"creator\": \"{self.creator}\"," # creator
        string = string + "\"layers\": [{"

        # https://doc.qt.io/qt-6/qabstractitemmodel.html#details # documentation p1
        # https://doc.qt.io/qt-6/qt.html#ItemDataRole-enum # documentation p2
        if all == False:
            selected_layers = selected_active_layers
        else:
            # selected_layers = QgsProject.instance().mapLayers().values()
            root = QgsProject.instance().layerTreeRoot()
            selected_layers = root.layerOrder()
            # selected_layers = set(index.siblingAtColumn(0) for index in selectedIndexes)

        # self.log(f"List of active selected layers is {selected_layers}, with length is {len(selected_layers)}")
        for i, layer in enumerate(selected_layers):
            layer_type = self.layer_type_mapping[layer.type()]
            # self.log(f"layer.type is {layer.type()} and layer_type is {layer_type}")
            styling = layer.customProperty( 'layerStyle', '' )
            # self.log(f"Info of layer {layer.name()}, styling is {layer.customProperty( "layerStyle", "" )}, provider_type: {layer.providerType()}, layer_type: {layer_type}, source: {layer.source()}")
            string = f"{string}\"name\": \"{layer.name()}\"," # layer name
            string = f"{string}\"source\": \"{layer.source()}\"," # source
            string = f"{string}\"styling\": \"{styling}\"," # styling
            string = f"{string}\"provider_type\": \"{layer.providerType()}\"," # provider_type
            string = f"{string}\"layer_type\": \"{layer_type}\"" # service_type
            # string = string + "\"styling\": \"" + layer.styling() + "\"," # styling
            if i == len(selected_layers) - 1:
                string = string + "}]"
            else:
                string = string + "}, {"
        string = string + "}"

        data = json.loads(string)
        # https://stackoverflow.com/questions/12994442/how-to-append-data-to-a-json-file
        try:
            with open(json_path, "r", encoding="utf-8") as feedsjson:
                feeds = json.load(feedsjson)
        except:
            feeds = []

        with open(json_path, "w", encoding="utf-8") as feedsjson:
            feeds.append(data)
            json.dump(feeds, feedsjson, indent='\t')
        
        self.update_thema_list()
        self.dlg.saveThemaLineEdit.clear()

    def filter_thema_list(self):
        plugin_thema_check = self.dlg.pluginThemaCheckBox.isChecked()
        user_thema_check = self.dlg.userThemaCheckBox.isChecked()
        fav_thema_check = self.dlg.favoriteThemaCheckBox.isChecked()

        if plugin_thema_check and user_thema_check:
            string = f"Plugin|{self.creator}"
        elif plugin_thema_check:
            string = "Plugin"
        elif user_thema_check:
            string = self.creator
        else:
            string = "leeg" # exact string is unimportant, any other string will empty the list

        regexp = QRegularExpression(string)
        self.userFilterThema.setFilterRegularExpression(regexp)

        if fav_thema_check:
            value = "2"
        else:
            value = "0|1|2"

        regexp_fav = QRegularExpression(value)
        self.favoriteFilterThema.setFilterRegularExpression(regexp_fav)

    def update_thema_list(self):
        """Add a thema to the thema model"""
        self.themaModel.clear()
        
        themas = []
        with open(self.plugin_thema_path, "r", encoding="utf-8") as f:
            themas.extend(json.load(f))
        if self.creator != "Plugin":
            if os.path.exists(self.user_thema_path):
                with open(self.user_thema_path, "r", encoding="utf-8") as f:
                    themas.extend(json.load(f))

        try:
            with open(self.user_thema_favorite_path, "r", encoding="utf-8") as f:
                favorites = json.load(f)
        except:
            favorites = None
    
        themas_exist = False
        for thema in themas:
            itemThema = QStandardItem(str(thema["thema_name"]))
            itemFavorite = QStandardItem()
            itemFavorite.setCheckable(True)
            try:
                if favorites and favorites[thema["thema_name"]] == "favorite":
                    itemFavorite.setCheckState(2)
            except:
                itemFavorite.setCheckState(0)
            itemSource = QStandardItem(str(thema["creator"]))
            itemFilter = QStandardItem(f'{thema["thema_name"]} {thema["layers"]}')
            # https://doc.qt.io/qt-6/qstandarditem.html#setData
            itemThema.setData(thema, Qt.ItemDataRole.UserRole)
            self.themaModel.appendRow(
                [itemThema, itemFavorite, itemSource, itemFilter]
            )
            themas_exist = True
        
        # if no thema is leftover after selection, then present an empty row
        if not themas_exist:
            itemThema = QStandardItem(str(""))
            itemFavorite = QStandardItem()
            itemFavorite.setCheckable(True)
            itemSource = QStandardItem(str(""))
            itemFilter = QStandardItem(str(""))
            self.themaModel.appendRow(
                [itemThema, itemFavorite, itemSource, itemFilter]
            )

        self.themaModel.setHeaderData(2, Qt.Orientation.Horizontal, "Bron")
        self.themaModel.setHeaderData(1, Qt.Orientation.Horizontal, "Favoriet")
        self.themaModel.setHeaderData(0, Qt.Orientation.Horizontal, "Thema")
        self.themaModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.themaModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.themaModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.dlg.themaView.horizontalHeader().setStretchLastSection(True)
        self.dlg.themaView.hideColumn(3)
        self.dlg.themaView.setColumnWidth(
            0, 300
        )  # set name to 300px (there are some huge layernames)
        self.dlg.themaView.horizontalHeader().setStretchLastSection(True)
        self.dlg.themaView.sortByColumn(0, Qt.AscendingOrder)

    def update_favorites(self, cell):
        if cell.column() == 1:
            model = self.dlg.themaView.model()
            # self.log(f"cell is {cell} (row: {cell.row()}, col: {cell.column()}) and model row count: {model.rowCount()}")
            string = "{"
            for r in range(model.rowCount()):
                thema = model.index(r, 0)
                thema_name = thema.data()
                favorite = model.index(r, 1)
                value = favorite.data(Qt.ItemDataRole.CheckStateRole) # https://doc.qt.io/qt-6/qt.html#CheckState-enum
                # self.log(f"Update favorites: CheckStateRole is {value} and DisplayRole is {thema.data(Qt.ItemDataRole.DisplayRole)}")
                if value == 2:
                    checkstate = "favorite"
                else:
                    checkstate = "regular"

                string = string + "\"" + thema_name + "\": \"" + checkstate + "\""
                if r == model.rowCount() - 1:
                    string = string + "}"
                else:
                    string = string + ","

            data = json.loads(string)
            try:
                with open(self.user_thema_favorite_path, "w", encoding="utf-8") as file:
                    json.dump(data, file, indent='\t')
            except Exception as e:
                self.log(f"Tried to write favorite themas to json file, but received this error: {e}")


#########################################################################################
############  Update and load list of layers that are part of a thema set ###############
#########################################################################################

    def show_thema_layers(self, selectedIndexes):
        """Show the layers that are part of a thema"""
        if len(selectedIndexes) == 0:
            self.current_layer = None
            return
        
        self.current_thema = self.dlg.themaView.selectedIndexes()[0].data(
            Qt.ItemDataRole.UserRole
        )
        if not self.current_thema == None:
            self.thema_layers = self.current_thema["layers"]
            self.update_thema_layers()

    def load_thema_layers(self):
        """Load the layers of this thema to the canvas"""
        thema_layers = self.thema_layers
        # create a group to load into to
        root = QgsProject.instance().layerTreeRoot()
        group_name = self.current_thema["thema_name"]
        group = root.insertGroup(0, group_name)
        # https://gis.stackexchange.com/questions/397789/sorting-layers-by-name-in-one-specific-group-of-qgis-layer-tree
        for layer in thema_layers:
            name = layer["name"]
            layer_type = layer["layer_type"]
            uri = layer["source"]
            provider_type = layer["provider_type"]
            style = layer["styling"]
            # title, layer_type, provider_type, uri
            self.current_layer = layer
            result = self.load_thema_layer(name, uri, layer_type, provider_type)
            QgsProject.instance().addMapLayer(result, False) # If True (by default), the layer will be added to the legend and to the main canvas
            group.addLayer(result) # Add the layer to the group
            # check if styling is saved in .resources.styling styling.json
            # if so, then apply that style, else apply no style

            if not style == "":

                layer_style_list = []
                # Load plugin styles
                try:
                    with open(self.plugin_styling_path, "r", encoding="utf-8") as f:
                        layer_style_list.extend(json.load(f))
                except:
                    pass

                # Load user styles
                if os.path.exists(self.user_styling_path):
                    try:
                        with open(self.user_styling_path, "r", encoding="utf-8") as f:
                            layer_style_list.extend(json.load(f))
                    except:
                        pass

                style_code = self.style_manager.style_code(style, uri)
                path = f"{self.plugin_styling_files_path}/{style_code}.qml"
                result.loadNamedStyle(path)
                result.triggerRepaint()
                result.setCustomProperty( "layerStyle", style )

        # self.iface.layerTreeView().collapseAllNodes()
        # self.update_active_layers_list()

    # This functions loads a layer where the uri is already known and saved to a thema
    def load_thema_layer(self, title, uri, layer_type, provider_type):
        "Create and load a layer from the thema layer-list"
        if layer_type == "Vector":
            result = QgsVectorLayer(uri, title, provider_type)
        elif layer_type == "Raster":
            result = QgsRasterLayer(uri, title, provider_type)
        # return QgsProject.instance().addMapLayer(result, True)
        return result

    def update_thema_layers(self):
        """Update the list of layers contained with this thema"""
        thema_layers = self.thema_layers
        
        self.themaMapModel.clear()

        if len(thema_layers) < 1:
            itemLayername = QStandardItem(str(""))
            itemProvider = QStandardItem(str(""))
            itemSource = QStandardItem(str(""))
            self.themaMapModel.appendRow(
                [itemLayername, itemProvider, itemSource]
            )
        else:
            for layer in thema_layers:
                itemLayername = QStandardItem(str(layer["name"]))
                stype = (
                    self.service_type_mapping[layer["provider_type"]]
                    if layer["provider_type"] in self.service_type_mapping
                    else layer["provider_type"].upper()
                )
                itemProvider = QStandardItem(str(stype))
                itemStyle = QStandardItem(str(layer["styling"]))
                # itemStyle = QStandardItem(str("styling"))
                itemSource = QStandardItem(str(layer["source"]))
                self.themaMapModel.appendRow(
                    [itemLayername, itemProvider, itemStyle, itemSource]
                )
        
        self.themaMapModel.setHeaderData(3, Qt.Orientation.Horizontal, "Bron")
        self.themaMapModel.setHeaderData(2, Qt.Orientation.Horizontal, "Opmaak")
        self.themaMapModel.setHeaderData(1, Qt.Orientation.Horizontal, "Type")
        self.themaMapModel.setHeaderData(0, Qt.Orientation.Horizontal, "Laagnaam")
        self.themaMapModel.horizontalHeaderItem(3).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.themaMapModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.themaMapModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.themaMapModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.dlg.themaMapListView.horizontalHeader().setStretchLastSection(True)
        # self.dlg.themaMapListView.hideColumn(3)
        
        self.dlg.themaMapListView.setColumnWidth(
            0, 200
        )  # set name to 300px (there are some huge layernames)
        self.dlg.themaMapListView.horizontalHeader().setStretchLastSection(True)
