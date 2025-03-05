import urllib.request, urllib.parse, urllib.error
from .constants import PLUGIN_NAME

from qgis.core import (
    Qgis,
    QgsProject,
    QgsLayerTreeLayer,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsVectorTileLayer,
    QgsMessageLog,
    QgsCoordinateReferenceSystem
)

# Set default layer loading behaviour
default_tree_locations = {
    "wms": "top",
    "wmts": "bottom",
    "wfs": "top",
    "wcs": "top",
    "api features": "top",
    "api tiles": "bottom",
}


# This functions loads a layer where the uri is already known and saved to a thema
def load_thema_layer(title, uri, layer_type, provider_type):
    "Create and load a layer from the thema layer-list"
    if layer_type == "VectorLayer":
        result = QgsVectorLayer(uri, title, provider_type)
    elif layer_type == "RasterLayer":
        result = QgsRasterLayer(uri, title, provider_type)
    # return QgsProject.instance().addMapLayer(result, True)
    return result

# These are functions to load webservice-layers for the first time from the list of all layers
class LoadLayers(object):
    def __init__(self, iface, current_layer, tree_location=None):
        self.iface = iface
        self.current_layer = current_layer
        self.tree_location = tree_location


    def load_layer(self):
        """Adds a QgsLayer to the project and layer tree.
        tree_location can be 'default', 'top', 'bottom'
        """
        QgsMessageLog.logMessage(str(self.current_layer), PLUGIN_NAME, 0)
        if self.current_layer is None:
            return

        servicetype = self.current_layer["service_type"]
        tree_location = self.tree_location
        if tree_location is None:
            tree_location = default_tree_locations[servicetype]
        
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
            layer = self.create_wfs_layer(layername, title, url)
            return layer
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
        QgsMessageLog.logMessage(str(uri), PLUGIN_NAME, 0)
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