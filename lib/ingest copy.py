#########################################################################################
######################################  Show and load layers ############################
#########################################################################################

from urllib.parse import urlsplit, urlencode, urlparse, parse_qs, urlunparse, parse_qsl
import urllib.request, urllib.parse, urllib.error
import json
import os.path
# from owslib.wms import WebMapService
# from owslib.wfs import WebFeatureService
from owslib.csw import CatalogueServiceWeb  # type: ignore
from owslib.util import cleanup_namespaces, bind_url, add_namespaces, OrderedDict, Authentication, openURL, http_post
# import urllib2, 
import re
import requests
import xml.etree.ElementTree as ET
from .constants import PLUGIN_NAME
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl
from qgis.core import QgsNetworkAccessManager

from qgis.PyQt.QtXml import QDomDocument, QDomElement
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtCore import Qt, QRegularExpression, QSortFilterProxyModel, QItemSelectionModel
from qgis.PyQt.QtWidgets import QAbstractItemView
from qgis.core import (Qgis, QgsProject, QgsLayerTreeLayer, QgsRasterLayer,
                       QgsVectorLayer, QgsVectorTileLayer, QgsCoordinateReferenceSystem,
                       QgsFeatureRequest)


class IngestLayersManager():
    def __init__(self, dlg, iface, plugin_dir, log):

        assert dlg is not None, "LayerManager: dlg is None"
        assert iface is not None, "LayerManager: iface is None"
        assert plugin_dir is not None, "LayerManager: plugin_dir is None"
        assert log is not None, "LayerManager: log is None"

        self.dlg = dlg
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.log = log
        

        # Set default layer loading behaviour
        self.service_type_mapping = {
            "wms": "WMS",
            "wmts": "WMTS",
            "wfs": "WFS",
            "wcs": "WCS",
            "api features": "OGC API - Features",
            "api tiles": "OGC API - Tiles",
        }


    def extract_url_to_json(self, url):
        """Extracts body at the provided url location and return the body as a json.
        url should be a string containing a valid, properly encoded URL 
        """
        with urllib.request.urlopen(url) as response:
            body = response.read()
            # self.log(response.read(50))
            # self.log(f"dir(response): {dir(response)}")
            # self.log(f"info: {response.info()}")
            self.log(f"Retrieving data from {url}")
            self.log(f'Retrieved {len(body)} characters')

            character_set = response.headers.get_content_charset()
            self.log(character_set)
            if character_set is None:
                character_set = "utf-8"
            
            try:
                decoded_body = body.decode(character_set)
                return json.loads(decoded_body)
            except Exception as e:
                self.log(f"Failed to extract url: {url}. Error message: {e}")
                return None
            
    def extract_csw(self, url):
        self.log(f"url: {url}")
        data = {'service': 'CSW', 'version': '2.0.2', 'request': 'GetCapabilities'}
        tst = urlencode(data)
        self.log(tst)
        request = '%s%s' % (bind_url(url), tst)
        self.log(request)
        response = openURL(
            request, None, 'Get', timeout=30, auth=None,
            headers=None).read()
        self.log(response)
        return
        csw = CatalogueServiceWeb(url)
        self.log(f"csw: {csw}")
        self.log(csw.identification.type)
        return
        with urllib.request.urlopen(url) as response:
            body = response.read()
            # self.log(response.read(50))
            # self.log(f"dir(response): {dir(response)}")
            # self.log(f"info: {response.info()}")
            self.log(f"Retrieving data from {url}")
            self.log(f'Retrieved {len(body)} characters')
            self.log(f'{body}')

            character_set = response.headers.get_content_charset()
            self.log(character_set)
            if character_set is None:
                character_set = "utf-8"
            
            try:
                self.log(type(body))
                decoded_body = body.decode(character_set)
                self.log(decoded_body)
                self.log(type(decoded_body))
                # json_body = ET.parse(body)
                # self.log(type(json_body))
                # self.log(json_body)
                # return json.loads(decoded_body)
            except Exception as e:
                self.log(f"fail at url: {url}")
                self.log(f"error message: {e}")
                return None

    def get_pdok_meta_data(self):
        pdok_api_url = 'https://api.pdok.nl/index.json'
        body = self.extract_url_to_json(pdok_api_url)
        api_list = body["apis"]

        pdok_list = []
        for child in api_list:
            new_data = child["links"][0]["href"]
            pdok_list.append(new_data)

        self.pdok_path = os.path.join(self.plugin_dir, "resources", "layers", "meta", "pdok_api_list.json")
        try:
            with open(self.pdok_path, encoding="utf-8", mode="w") as f:
                json.dump(pdok_list, f, indent='\t')
        except Exception as e:
            self.log(e)
            return

    def get_pdok_data(self):
        try:
            with open(self.pdok_path, encoding="utf-8", mode="r") as f:
                pdok_apis = json.load(f)
        except Exception as e:
            self.log(e)
            return

        pdok_api_list = []
        for url in pdok_apis:

            try:
                meta = self.extract_url_to_json(url)
            except Exception as e:
                self.log(e)
                continue

            for link in meta["links"]:
                if link["rel"] == "data":
                    try:
                        data_body = self.extract_url_to_json(link["href"])
                        collections = data_body["collections"]

                        for c in collections:
                            body = {}
                            body["name"] = c["id"]
                            body["title"] = c["title"]
                            body["abstract"] = c["description"]
                            body["service_url"] = link["href"]
                            body["service_title"] = meta["title"]
                            body["service_abstract"] = meta["description"]
                            body["service_type"] = "api features"

                            pdok_api_list.append(body)
                    except Exception as e:
                        self.log(e)
                        continue


        path = os.path.join(self.plugin_dir, "resources", "layers", "pdok", "api_list.json")
        self.log(f"path: {path}")
        self.log(f"saving layer info to {path}")
        with open(path, encoding="utf-8", mode="w") as f:
            json.dump(pdok_api_list, f, indent='\t')
            # f.write(pdok_api_list)
        # self.log(body[:15])
        
        # with open(json_path, "w", encoding="utf-8") as feedsjson:
        #     json.dump(existing_data, feedsjson, indent='\t')

    def get_all_pdok_data(self):
        url = 'https://www.pdok.nl/datasets'
        body = self.extract_url_to_json(url)
        self.log(body)

    def get_layer_list(self):
        # self.get_all_pdok_data()
        csw_url = "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw"
        # csw = CatalogueServiceWeb(csw_url)
        # return
        # csw_url = "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw?service=CSW&request=GetCapabilities"
        with urllib.request.urlopen(csw_url) as response:
            body = response.read()
            self.log(body)
        
        # self.log(csw)
        # Service_urls = csw.getService_urls()
        # self.log(Service_urls)
        # records = csw.getrecords()
        # self.log(records)
        # return
        body = self.extract_csw(csw_url)
        self.log(body)
        
        path = os.path.join(self.plugin_dir, "resources", "layers", "meta", "pdok_list.json")
        try:
            with open(path, encoding="utf-8", mode="w") as f:
                json.dump(body, f, indent='\t')
        except Exception as e:
            self.log(e)
            return
        return
        # csw = CatalogueServiceWeb(csw_url, version='3.0.0', timeout=50, skip_caps=True)
        csw = CatalogueServiceWeb(csw_url, version='3.0.0', skip_caps=True)
        self.log(csw)
        csw.getdomain('GetRecords.resultType')
        # self.log(csw.identification.type)
        # [self.log(op.name) for op in csw.operations]
        # self.get_pdok_meta_data()
        # self.get_pdok_data()

        # https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/page/Voor%20ontwikkelaars?page=Voor%20ontwikkelaars
        # https://www.pdok.nl/ogcapi
        # https://www.pdok.nl/features
        # https://www.pdok.nl/pdc-afnemers-van-data#DIENSTEN_VOOR_AFNEMERS
        # https://opendata.zuid-holland.nl/geonetwork/srv/dut/catalog.search#/metadata/14096698-04A3-444E-B22C-1EB539D2D74B

        # url = 'https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0?request=GetCapabilities'
        # https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1/api?f=json
        # https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1
        # url = 'https://api.pdok.nl/hwh/waterschappen-hydrografie/ogc/v1/sitemap.xml'
        # url = 'https://api.pdok.nl/sitemap.xml'
        # url = 'https://api.pdok.nl/index.json'
        # url = 'https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1/collections?f=json'
        # url = 'https://opendata.zuid-holland.nl/geonetwork/srv/dut/catalog.search#/map'
        # https://opendata.zuid-holland.nl/geonetwork/srv/dut/catalog.search#/search?facet.q=type%2Fdataset%26keyword%2Fwater&resultType=details&sortBy=popularity&fast=index&_content_type=json&from=1&to=20
        # url = 'https://opendata.zuid-holland.nl/geonetwork/srv/dut/catalog.search#/metadata/14096698-04A3-444E-B22C-1EB539D2D74B'
