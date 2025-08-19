#########################################################################################
#########################  Show and load styling for layers #############################
#########################################################################################
import os
import re
import json
import hashlib
from qgis.core import QgsMapLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox



def extract_typename(uri):
    """
    Extract the typename from a QGIS layer URI string.
    """
    match = re.search(r"typename=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        typename = match.group(1) or match.group(2) or match.group(3)
        return typename
    else:
        return None


def extract_base_url(uri):
    """
    Extract the base URL from a QGIS layer URI string.

    Example:
        uri = "pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='beheerstedelijkwater:BeheerLeiding' url='https://service.pdok.nl/rioned/beheerstedelijkwater/wfs/v1_0"
        extract_base_url(uri)
        # returns: "'https://service.pdok.nl/rioned/beheerstedelijkwater/wfs/v1_0'"

        uri = "pagingEnabled=true restrictToRequestBBOX=1 srsname=EPSG:28992 typename=beheerstedelijkwater:BeheerLeiding url=https://service.pdok.nl/rioned/beheerstedelijkwater/wfs/v1_0"
        extract_base_url(uri)
        # returns: "'https://service.pdok.nl/rioned/beheerstedelijkwater/wfs/v1_0'"

    The function looks for url='...', url="...", or url=... in the string and returns the value with single quotes.
    """
    match = re.search(r"url=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        url = match.group(1) or match.group(2) or match.group(3)
        return url
    else:
        return None


class StyleManager:
    """
    Class to manage the styling of layers
    """
    def __init__(self, dlg, plugin_dir, working_dir, creator, log):

        assert dlg is not None, "StyleManager: dlg is None"
        assert plugin_dir is not None, "StyleManager: plugin_dir is None"
        assert working_dir is not None, "StyleManager: working_dir is None"
        assert creator is not None, "StyleManager: creator is None"
        assert log is not None, "StyleManager: log is None"
        
        self.dlg = dlg
        self.creator = creator
        self.log = log

        self.plugin_styling_path = os.path.join(plugin_dir, "resources", "styling", "styling.json")
        self.plugin_styling_files_path = os.path.join( plugin_dir, "resources", "styling", "qml_files")
        assert os.path.exists(self.plugin_styling_path), f"StyleManager: plugin_styling_path does not exist: {self.plugin_styling_path}"
        assert os.path.exists(self.plugin_styling_files_path), f"StyleManager: plugin_styling_files_path does not exist: {self.plugin_styling_files_path}"

        self.set_working_directory(working_dir)
        
        self.dlg.stylingGroupBox.setToolTip("Selecteer maar één laag om de styling aan te passen")


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

    def style_code(self, style_name: str, source: str):
        """
        Create the name for a styling file. Encoded with md5 for better readability.

        :param style_name: Name given by a user to a styling.
        :type style_name: str

        :param source: Uri path to the layer source.
        :type source: str
        """
        md = hashlib.md5(str(source).encode("utf"))
        text = md.hexdigest()
        return str(style_name.lower() + '_' + text) 

    def load_styling(self):
        style_name = self.dlg.stylingComboBox.currentText()
        layer = self.dlg.stylingComboBox.currentData()
        # self.log(f"style name is {style_name}")
        style_code = self.style_code(style_name, layer.source())

        if not layer == None:
            path = f"{self.plugin_styling_files_path}/{style_code}.qml"
            layer.loadNamedStyle(path)
            layer.triggerRepaint()
            layer.setCustomProperty( "layerStyle", style_name )

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
        style_code = self.style_code(style_name, source)

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

        # TODO naam blijft staan in de lijst van de lagen

    def save_styling(self, selected_layers):
        """
        Save the styling of the current layer to a qml file
        """
        # enable or disable the styling-functions
        if len(selected_layers) != 1:
            return

        # collect parameters
        style_name = self.dlg.saveStylingLineEdit.text()
        if style_name == "":
            return
        
        layer = selected_layers[0]
        layer_name = layer.name()
        source = layer.source()
        self.log(f"source: {source}")
        url = extract_base_url(source)
        self.log(f"url: {url}")
        typename = extract_typename(source)
        self.log(f"typename: {typename}")
        # url = layer.url()  # url is the uri of the layer
        # typename = layer.typename()  # typename is the name of the layer
        
        style_code = self.style_code(style_name, source)
        qml_file = f"{style_code}.qml"
        
        if self.creator == "Plugin":
            json_path = self.plugin_styling_path
            qml_folder = self.plugin_styling_files_path
        else:
            json_path = self.user_styling_path
            qml_folder = self.user_styling_files_path

        qml_path = os.path.join(qml_folder, qml_file)
        self.log(f"Saving style to path: {qml_path}")

        
        try:
            with open(json_path, "r", encoding="utf-8") as feedsjson:
                feeds = json.load(feedsjson)
        except Exception as e:
            feeds = []

        style_code = self.style_code(style_name, source)
        existing_layer = None
        for feed in feeds:
            self.log(feed)
            if hasattr(feed, "source"):
                if feed["source"] == source:
                    self.log("here1")
                    existing_layer = feed
                    existing_styles = existing_layer["styles"]

                    # Check if a style with the same name exists
                    for style in existing_styles:
                        if style["file"] == style_code:
                            overwrite = QMessageBox.question(
                                self.dlg,
                                "Bestand bestaat al",
                                f"De opmaak {style_name} bestaat al. Wilt u het overschrijven?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            )
                            if overwrite == QMessageBox.StandardButton.No:
                                return
                    
                    # Remove the old style information
                    for i, layer in enumerate(feeds):
                        if layer["source"] == source:
                            feeds.pop(i)

            elif hasattr(feed, "url"):
                if feed["url"] == url:
                    self.log("here2")
                    existing_layer = feed
                    existing_styles = existing_layer["styles"]

                    # Check if a style with the same name exists
                    for style in existing_styles:
                        if style["file"] == style_code:
                            overwrite = QMessageBox.question(
                                self.dlg,
                                "Bestand bestaat al",
                                f"De opmaak {style_name} bestaat al. Wilt u het overschrijven?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            )
                            if overwrite == QMessageBox.StandardButton.No:
                                return
                            
                        # Remove the old style information
                        for i, layer in enumerate(feeds):
                            if layer["url"] == url:
                                feeds.pop(i)



        # use the layer["source"] (uri) as the id to match styling options (the rest can be changed easily).
        # TODO: what about services where you define the styling when you send the request? remove and reload?
        if layer.type() == QgsMapLayer.VectorLayer:
            layer.saveNamedStyle(qml_path) # does this overwrite automatically?
        else:
            return

        style_dict = {
            "name": style_name,
            "file": style_code,
            "creator": self.creator
        }
        
        if existing_layer:
            existing_styles.append(style_dict)
            data = {
                "layer_name": layer_name,
                "creator": self.creator,
                "typename": typename,
                "url": url,
                "styles": existing_styles,
            }
        else:
            data = {
                "layer_name": layer_name,
                "creator": self.creator,
                "typename": typename,
                "url": url,
                "styles": style_dict,
            }
        # layers_list.append(layer_dict)
        
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

            layer_style_list = []
            # Load plugin styles
            try:
                with open(self.plugin_styling_path, "r", encoding="utf-8") as f:
                    layer_style_list.extend(json.load(f))
            except:
                pass

            # Load user styles
            # if self.creator != "Plugin":
            if os.path.exists(self.user_styling_path):
                try:
                    with open(self.user_styling_path, "r", encoding="utf-8") as f:
                        layer_style_list.extend(json.load(f))
                except:
                    pass

            for layer in layer_style_list:
                    
                # url = layer.url()  # url is the uri of the layer
                # typename = layer.typename()  # typename is the name of the layer
                    
                if hasattr(layer, "url"):
                    if data.url() == layer["url"] and data.typename() == layer["typename"]:
                        styles = layer["styles"]
                        for style in styles:
                            if style["creator"].lower() != "plugin":
                                display_name = f'{style["name"]} | toegevoegd door: {style["creator"]}'
                            else:
                                display_name = style["name"]

                            self.dlg.stylingComboBox.addItem(display_name, data)
                elif hasattr(layer, "source"):
                    if data.source() == layer["source"]:
                        styles = layer["styles"]
                        for style in styles:
                            if style["creator"].lower() != "plugin":
                                display_name = f'{style["name"]} | toegevoegd door: {style["creator"]}'
                            else:
                                display_name = style["name"]

                            self.dlg.stylingComboBox.addItem(display_name, data)

