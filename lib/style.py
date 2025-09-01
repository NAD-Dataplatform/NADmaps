#########################################################################################
#########################  Show and load styling for layers #############################
#########################################################################################
import os
import re
import json
import hashlib
from qgis.core import (
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsLayerTreeLayer,
    QgsVectorTileLayer,
    QgsCoordinateReferenceSystem
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox

from .utility import (
    extract_name,
    extract_url,
    extract_service_type,
    extract_wms_style_name,
    extract_wms_style_title,
    extract_crs,
    extract_oat_style,
    extract_oat_style_url,
)


def get_style_code(style_name: str, url: str, name: str):
    """
    Create the name for a styling file. Encoded with md5 for better readability.
    """
    code = str(url + '_' + name)
    md = hashlib.md5(code.encode("utf"))
    text = md.hexdigest()
    return str(style_name.lower() + '_' + text) 


class StyleManager:
    """
    Class to manage the styling of layers
    """
    def __init__(self, dlg, iface, plugin_dir, working_dir, creator, log):

        assert dlg is not None, "StyleManager: dlg is None"
        assert iface is not None, "StyleManager: iface is None"
        assert plugin_dir is not None, "StyleManager: plugin_dir is None"
        assert working_dir is not None, "StyleManager: working_dir is None"
        assert creator is not None, "StyleManager: creator is None"
        assert log is not None, "StyleManager: log is None"
        
        self.dlg = dlg
        self.iface = iface
        self.creator = creator
        self.log = log

        self.plugin_styling_path = os.path.join(plugin_dir, "resources", "styling", "styling.json")
        self.plugin_styling_files_path = os.path.join( plugin_dir, "resources", "styling", "qml_files")
        assert os.path.exists(self.plugin_styling_path), f"StyleManager: plugin_styling_path does not exist: {self.plugin_styling_path}"
        assert os.path.exists(self.plugin_styling_files_path), f"StyleManager: plugin_styling_files_path does not exist: {self.plugin_styling_files_path}"

        self.set_working_directory(working_dir)
        
        self.dlg.stylingGroupBox.setToolTip("Selecteer maar één laag om de styling aan te passen")

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
            10: "Database",
        }

    def set_working_directory(self, path):
        """Set the working directory for the plugin"""
        # some checks if the path is not empty or a directory
        if not path:
            return
        if not os.path.isdir(path):
            return
        
        os.makedirs(path, exist_ok=True)
        os.makedirs(os.path.join(path, "styling"), exist_ok=True)
        
        self.user_styling_path = os.path.join(path, "styling", "styling.json")
        self.user_styling_files_path = os.path.join(path, "styling", "qml_files")

    def set_layer_list(self, layer_list):
        self.layer_list = layer_list

    def get_layer_style_list(self):
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
        
        return layer_style_list

    def load_styling(self):
        style_title = self.dlg.stylingComboBox.currentText()
        data = self.dlg.stylingComboBox.currentData()

        try:
            uri = data.source()
            title = data.name()
            service_type = extract_service_type(uri, data.providerType())
            name = extract_name(uri, service_type, title)
            url = extract_url(uri, service_type)
            
            if service_type == "wms" or service_type == "wmts" or service_type == "api tiles":
                root = QgsProject.instance().layerTreeRoot()
                tree_node = root.findLayer(data)

                visible = tree_node.itemVisibilityChecked()
                expanded = tree_node.isExpanded()

                layers = root.layerOrder()
                position = 0
                for i, layer in enumerate(layers):
                    if layer.id() == data.id():
                        position = i
                        break
                
                # style_name = style_name.replace(" ", "_")
                
                if service_type == "wms" or service_type == "wmts":
                    # get the required style name (e.g. style title is "Aantal inwoners", but we require the name: "bevolkingskern_aantal_inwoners")
                    for l in self.layer_list:
                        if l["service_url"] == url and l["name"] == name:
                            style_options = l["styles"]
                            for style_option in style_options:
                                if style_option["title"] == style_title:
                                    style_name = style_option["name"]
                                    new_style_title = style_option["title"]
                                    break
                            break
                    
                    old_style_title = extract_wms_style_title(title)
                    title = title.replace(f" [{old_style_title}]", f" [{new_style_title}]")
                    
                    style = extract_wms_style_name(uri)
                    new_uri = uri.replace(style, style_name)

                    new_layer = QgsRasterLayer(new_uri, title, "wms") 
                    
                elif service_type == "api tiles":
                    # style = extract_oat_style(title)
                    style_url = extract_oat_style_url(uri)
                    crs = extract_crs(uri)

                    for l in self.layer_list:
                        if l["service_url"] == url and l["name"] == name:
                            style_options = l["styles"]
                            for style_option in style_options:
                                if style_option["name"] == style_title:
                                    new_style_url = style_option["url"]
                                    break
                            break
                    
                    new_uri = uri.replace(style_url, new_style_url)
                    new_layer = QgsVectorTileLayer(new_uri, title)
                    new_layer.setCrs(srs=QgsCoordinateReferenceSystem(crs))
                    new_layer.loadDefaultStyle()

                # return to code relevant for both wms/wmts and api tiles
                QgsProject.instance().removeMapLayers([data.id()])
                QgsProject.instance().addMapLayer(new_layer, False)
                new_layer_tree_layer = QgsLayerTreeLayer(new_layer)
                layer_tree = self.iface.layerTreeCanvasBridge().rootGroup()
                layer_tree.insertChildNode(position, new_layer_tree_layer)

                new_tree_node = root.findLayer(new_layer)
                new_tree_node.setExpanded(expanded)
                new_tree_node.setItemVisibilityChecked(visible)

                # new_layer.loadDefaultStyle()
                new_layer.setCustomProperty( "layerStyle", style_title )
            else:
                layer_style_list = self.get_layer_style_list()
                for layer in layer_style_list:
                    if layer["name"] == name and layer["service_url"] == url:
                        for style in layer["styles"]:
                            if style["name"] == style_title:
                                style_file = style["file"] + '.qml'
                                
                        if layer["creator"] == "Plugin":
                            path = os.path.join(self.plugin_styling_files_path, style_file)
                        else:
                            path = os.path.join(self.user_styling_files_path, style_file)

                self.log(f"Loading style from path: {path}")
                data.loadNamedStyle(path) # https://qgis.org/pyqgis/master/core/QgsMapLayer.html#qgis.core.QgsMapLayer.loadNamedStyle
                data.triggerRepaint()
                
                # in all cases add the style name to the layer properties
                data.setCustomProperty( "layerStyle", style_title )
        except Exception as e:
            self.log(f"Failed to load style: {style_title}. Error message: {e}")

    def save_styling(self, layer):
        """
        Save the styling of the current layer to a qml file
        """
        # collect parameters
        style_name = self.dlg.saveStylingLineEdit.text()
        if style_name == "":
            return

        layer_type = self.layer_type_mapping[layer.type()]
        uri = layer.source()  # source is the uri of the layer, https://qgis.org/pyqgis/master/core/QgsMapLayer.html#qgis.core.QgsMapLayer.source
        title = layer.name()
        style_code = get_style_code(style_name, uri, title)

        if "\"" in uri:
            uri = uri.replace('"', '\'') # For solving situations like this: Oracle source is "DB"."LAYER" 
        
        service_type = extract_service_type(uri, layer.providerType())
        self.log(f"service type at save styling: {service_type}")
        name = extract_name(uri, service_type, title)
        url = extract_url(uri, service_type)

        if service_type == "wms" or service_type == "wmts" or service_type == "api tiles":
            return
        # # get extra data
        # if service_type == "wms" or service_type == "wmts":
        #     style = extract_wms_styles(uri)
        # elif service_type == "api tiles":
        #     oat_style = extract_oat_style(title)
        #     style_url = extract_oat_style_url(uri)

        # get the storage path
        if self.creator == "Plugin":
            json_path = self.plugin_styling_path
            qml_folder = self.plugin_styling_files_path
        else:
            json_path = self.user_styling_path
            qml_folder = self.user_styling_files_path

        qml_file = f"{style_code}.qml"
        qml_path = os.path.join(qml_folder, qml_file)
        self.log(f"Saving style to path: {qml_path}")
        
        try:
            with open(json_path, "r", encoding="utf-8") as feedsjson:
                feeds = json.load(feedsjson)
        except Exception as e:
            feeds = []

        # collect existing data
        existing_styles = []
        for i, feed in enumerate(feeds):
            if feed["service_url"] == url and feed["name"] == name:
                existing_styles = feed["styles"]

                # Check if a style with the same name exists
                for j, style in enumerate(existing_styles):
                    if style["file"] == style_code:
                        overwrite = QMessageBox.question(
                            self.dlg,
                            "Bestand bestaat al",
                            f"De opmaak {style_name} bestaat al. Wilt u het overschrijven?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        )
                        if overwrite == QMessageBox.StandardButton.No:
                            return
                        existing_styles.pop(j)
                feeds.pop(i)

        if layer_type == "Vector":
            self.log(type(layer))
            layer.saveNamedStyle(qml_path) # https://qgis.org/pyqgis/master/core/QgsMapLayer.html#qgis.core.QgsMapLayer.saveNamedStyle
        else:
            return

        style_dict = {
            "name": style_name,
            "file": style_code,
            "creator": self.creator
        }
        
        existing_styles.append(style_dict)
        data = {
            "name": name,
            "title": title,
            "service_url": url,
            "creator": self.creator,
            "styles": existing_styles,
        }

        with open(json_path, "w", encoding="utf-8") as feedsjson:
            feeds.append(data)
            json.dump(feeds, feedsjson, indent="\t")

        layer.setCustomProperty( "layerStyle", style_name )
        self.dlg.saveStylingLineEdit.clear()

        # self.update_active_layers_list()
        self.update_styling_list()

    def update_styling_list(self):
        """Update the dropdown menu with saved styling options"""
        self.dlg.stylingComboBox.clear()
        selectedIndexes = self.dlg.activeMapListView.selectedIndexes()
        nr_of_selected_rows = len(set(index.row() for index in selectedIndexes))

        # enable or disable the styling-functions
        if nr_of_selected_rows == 1:
            data = self.dlg.activeMapListView.selectedIndexes()[0].data(
                Qt.ItemDataRole.UserRole
            )

            uri = data.source()  # source is the uri of the layer
            title = data.name()
            display_name = ""

            if "\"" in uri:
                uri = uri.replace('"', '\'') # For solving situations like this: Oracle source is "DB"."LAYER" 
            service_type = extract_service_type(uri, data.providerType())

            name = extract_name(uri, service_type, title)
            url = extract_url(uri, service_type)


            if service_type == "wms" or service_type == "wmts" or service_type == "api tiles":
                existing_layer = False

                if service_type == "api tiles":
                    display_name = extract_oat_style(title)
                    self.log(display_name)
                        
                    for layer in self.layer_list:
                        if layer["name"] == name and layer["service_url"] == url:
                            styles = layer["styles"]
                            existing_layer = True
                            for style in styles:
                                title = style["name"]
                                self.dlg.stylingComboBox.addItem(title, data)
                            break

                else:
                    display_name = extract_wms_style_name(uri)
                    for layer in self.layer_list:
                        if layer["name"] == name and layer["service_url"] == url:
                            styles = layer["styles"]
                            existing_layer = True
                            for style in styles:
                                title = style["title"]
                                if title == "":
                                    title = style["name"]
                                self.dlg.stylingComboBox.addItem(title, data)
                            break


                # in case the user added a raster layer that is not in the list
                if not existing_layer:
                    self.dlg.stylingComboBox.addItem(display_name, data)
                
            else:
                # Load vector styles which are all user/plugin defined (not available in web services)
                layer_style_list = self.get_layer_style_list()
                for layer in layer_style_list:
                    if url == layer["service_url"] and name == layer["name"]:
                        styles = layer["styles"]
                        for style in styles:
                            if style["creator"].lower() != "plugin":
                                display_name = f'{style["name"]} | toegevoegd door: {style["creator"]}'
                            else:
                                display_name = style["name"]

                            self.dlg.stylingComboBox.addItem(display_name, data)

            # in all cases add the style name to the layer properties
            data.setCustomProperty( "layerStyle", display_name )

    def delete_styling(self):
        """Delete an existing style (only user-defined styles should be deleted)."""
        if self.creator == "Plugin":
            json_path = self.plugin_styling_path
            qml_folder = self.plugin_styling_files_path
        else:
            json_path = self.user_styling_path
            qml_folder = self.user_styling_files_path

        # Find the style name to be deleted
        style_name = self.dlg.stylingComboBox.currentText()
        if "|" in style_name:
            style_name = style_name.split("|")[0].strip()
        data = self.dlg.stylingComboBox.currentData()
        current_style = data.customProperty("layerStyle", "")

        if data is None:
            self.log("No layer selected for deleting the style.")
            return

        source = data.source()
        style_code = get_style_code(style_name, source)

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                jsondata = json.load(f)
        except Exception as e:
            self.log(f"Failed to read JSON file: {e}")
            return

        new_jsondata = []
        current_layer = None

        for layer in jsondata:
            if layer["source"] == source:
                current_layer = layer
            else:
                new_jsondata.append(layer)

        if current_layer is None or "styles" not in current_layer:
            self.log("No matching layer or styles found in the JSON file.")
            return

        existing_styles = current_layer["styles"]
        # Preserve other style options if they exist
        styles = [obj for obj in existing_styles if obj["file"] != style_code]

        if styles:
            current_layer["styles"] = styles
            new_jsondata.append(current_layer)

        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(new_jsondata, f, indent=4)
        except Exception as e:
            self.log(f"Failed to write to JSON file: {e}")
            return

        # Delete the QML file
        file_path = os.path.join(qml_folder, f"{style_code}.qml")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self.log(f"Deleted QML file: {file_path}")
            except Exception as e:
                self.log(f"Failed to delete QML file: {e}")
        else:
            self.log(f"QML file not found: {file_path}")

        self.update_styling_list()
        if style_name == current_style:
            data.setCustomProperty( "layerStyle", "" )
        # self.update_active_layers_list()
