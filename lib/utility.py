import re
import urllib.parse


# wfs and ogc api features

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


# wms and wmts

def extract_layers(uri):
    """
    Extract the layers (WMS or WMTS layername) from a QGIS layer URI string.
    """
    match = re.search(r"layers=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        layers = match.group(1) or match.group(2) or match.group(3)
        layers = layers.split("&", 1)[0]
        return layers
    else:
        return None

def extract_tilematrixset(uri):
    """
    Extract the tilematrixset (WMS or WMTS) from a QGIS layer URI string.
    """
    match = re.search(r"tileMatrixSet=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        tilematrixset = match.group(1) or match.group(2) or match.group(3)
        tilematrixset = tilematrixset.split("&", 1)[0]
        return tilematrixset
    else:
        return None

def extract_format(uri):
    """
    Extract the format (WMS or WMTS) from a QGIS layer URI string.
    """
    match = re.search(r"format=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        format = match.group(1) or match.group(2) or match.group(3)
        format = format.split("&", 1)[0]
        return format
    else:
        return None

def extract_crs(uri):
    """
    Extract the crs from a QGIS layer URI string.
    """
    match = re.search(r"crs=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        crs = match.group(1) or match.group(2) or match.group(3)
        crs = crs.split("&", 1)[0]
        return crs
    else:
        return None

def extract_wms_title(title):
    """
    Extract the layers (WMS or WMTS layername) from a QGIS layer URI string.
    """
    title = title.split(" [", 1)[0]
    if title:
        return title
    else:
        return ""

def extract_wms_style_name(uri):
    """
    Extract the styles (WMS or WMTS) from a QGIS layer URI string.
    """
    match = re.search(r"styles=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        styles = match.group(1) or match.group(2) or match.group(3)
        styles = styles.split("&", 1)[0]
        return styles
    else:
        return "default"

def extract_wms_style_title(title):
    """
    Extract the layers (WMS or WMTS layername) from a QGIS layer URI string.
    """
    match = re.search(r"\[([^]]+)\]", title)
    # dbname = re.search(r"(?:([^\s]+))", match)
    if match:
        style_title = match.group(1)
        return style_title
    else:
        return ""


# ogc api tiles

def extract_oat_url(uri):
    """
    Extract the base URL from a QGIS OGC API Tiles layer URI string.

    Example:
        uri = "styleUrl=https://api.pdok.nl/brt/top10nl/ogc/v1/styles/brt_top10nl__netherlandsrdnewquad?f=mapbox&url=https://api.pdok.nl/brt/top10nl/ogc/v1/tiles/WebMercatorQuad/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt&type=xyz&zmax=17&zmin=0&http-header:referer="
        extract_oat_url(uri)
        # returns: "'https://api.pdok.nl/brt/top10nl/ogc/v1'"

    The function looks for url='...', url="...", or url=... in the string and returns the value with single quotes.
    """
    match = re.search(r"url=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        url = match.group(1) or match.group(2) or match.group(3)
        url = url.split("/tiles", 1)[0]
        url = urllib.parse.unquote(url)
        return url
    else:
        return uri

def extract_oat_style_url(uri):
    """
    Extract the base URL from a QGIS OGC API Tiles layer URI string.

    Example:
        uri = "styleUrl=https://api.pdok.nl/brt/top10nl/ogc/v1/styles/brt_top10nl__netherlandsrdnewquad?f=mapbox&url=https://api.pdok.nl/brt/top10nl/ogc/v1/tiles/WebMercatorQuad/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt&type=xyz&zmax=17&zmin=0&http-header:referer="
        extract_oat_style_url(uri)
        # returns: "'https://api.pdok.nl/brt/top10nl/ogc/v1/styles/brt_top10nl__netherlandsrdnewquad?f=mapbox'"

    The function looks for url='...', url="...", or url=... in the string and returns the value with single quotes.
    """
    match = re.search(r"styleUrl=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        url = match.group(1) or match.group(2) or match.group(3)
        url = url.split("&", 1)[0]
        url = urllib.parse.unquote(url)
        return url
    else:
        return uri

def extract_oat_title(layer_name):
    """
    Extract the title from a QGIS OGC API Tiles layer URI string.

    Example:
        layer_name = "BRT TOP10NL - Tiles [BRT TOP10NL Standaardvisualisatie (NetherlandsRDNewQuad)]"
        extract_oat_url(layer_name)
        # returns: "'BRT TOP10NL - Tiles'"
    """
    title = layer_name.split(" [", 1)[0]
    return title

def extract_oat_style(layer_name):
    """
    Extract the title from a QGIS OGC API Tiles layer URI string.

    Example:
        layer_name = "BRT TOP10NL - Tiles [BRT TOP10NL Standaardvisualisatie (NetherlandsRDNewQuad)]"
        extract_oat_url(layer_name)
        # returns: "'BRT TOP10NL Standaardvisualisatie (NetherlandsRDNewQuad)'"
    """
    style_name = layer_name.split(" [", 1)[1]
    style_name = style_name[:-1]
    return style_name


# wcs

def extract_identifier(uri):
    """
    Extract the layername/identifier from a QGIS WCS layer URI string.

    Example:
        uri = "cache=AlwaysNetwork&crs=EPSG:28992&format=GEOTIFF&identifier=dsm_05m&url=https://service.pdok.nl/rws/ahn/wcs/v1_0"
        extract_identifier(uri)
        # returns: "'dsm_05m'"
    """
    match = re.search(r"identifier=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        identifier = match.group(1) or match.group(2) or match.group(3)
        identifier = identifier.split("&", 1)[0]
        return identifier
    else:
        return None

def extract_wcs_url(uri):
    """
    Extract the url from a QGIS WCS layer URI string.

    Example:
        uri = "cache=AlwaysNetwork&crs=EPSG:28992&format=GEOTIFF&identifier=dsm_05m&url=https://service.pdok.nl/rws/ahn/wcs/v1_0"
        extract_wcs_url(uri)
        # returns: "'https://service.pdok.nl/rws/ahn/wcs/v1_0?request=GetCapabilities&service=WCS'"
    """
    match = re.search(r"url=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        url = match.group(1) or match.group(2) or match.group(3)
        # url += "?request=GetCapabilities&service=WCS"
        url = urllib.parse.unquote(url)
        return url
    else:
        return None


# url for wfs, api features, wms or wmts

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
        url = urllib.parse.unquote(url)
        return url
    else:
        uri = urllib.parse.unquote(uri)
        return uri


# Spatialite functions

def extract_spatialiate_db(uri):
    match = re.search(r"dbname=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        dbname = match.group(1) or match.group(2) or match.group(3)
        return dbname
    else:
        return None

def extract_spatialiate_table(uri):
    match = re.search(r"table=(?:'([^']*)\"?|\"([^\"]*)\"?|([^\s]+))", uri)
    if match:
        table = match.group(1) or match.group(2) or match.group(3)
        return table
    else:
        return None

def extract_spatialiate_geom_column(uri):
    """
    Extract the geometry column from a spatialite URI string.

    Example:
        uri = "dbname='C:/Users/svanderhoeven/Documents/Overige/test.sqlite' table='layer'(geometry) sql="
        extract_spatialiate_geom_column(uri)
        # returns: "'geometry'"

    The function looks for table='...', table="...", or table=... in the string and returns the value with single quotes.
    """
    match = re.search(r"\(([^)]*)\)", uri)
    # dbname = re.search(r"(?:([^\s]+))", match)
    if match:
        geometry = match.group(1)
        return geometry
    else:
        return None
    

#########################################################################################
# Base and composite functions

def extract_service_type(uri, provider_type):
    """
    Extract the layer type from a QGIS layer source string and layer providerType.
    """
    service_type = provider_type
    if "wmts" in uri.lower():
        # https://docs.qgis.org/3.40/en/docs/server_manual/services/wmts.html
        service_type = "wmts"
    if provider_type == "OAPIF":
        # https://docs.qgis.org/3.40/en/docs/server_manual/services/ogcapif.html
        service_type = "api features"
    if provider_type == "xyzvectortiles" and "http" in uri.lower():
        # local vector tiles are also a possibility:
        # https://docs.qgis.org/3.40/en/docs/user_manual/working_with_vector_tiles/vector_tiles.html#supported-formats
        service_type = "api tiles"
    return service_type

def extract_name(uri, service_type, title=""):
    if service_type == "wfs" or service_type == "api features":
        name = extract_typename(uri)
    elif service_type == "wms" or service_type == "wmts":
        name = extract_layers(uri)
    elif service_type == "api tiles":
        name = extract_oat_title(title)
    elif service_type == "wcs":
        name = extract_identifier(uri)
    else:
        name = title
    return name

def extract_url(uri, service_type):
    if service_type == "wfs" or service_type == "api features" or service_type == "wms" or service_type == "wmts":
        url = extract_base_url(uri)
    elif service_type == "api tiles":
        url = extract_oat_url(uri)
    elif service_type == "wcs":
        url = extract_wcs_url(uri)
    else:
        url = uri
    return url