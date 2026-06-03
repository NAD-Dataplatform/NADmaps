######################################################################################### 
######################################  Show and load layers ############################ 
######################################################################################### 
# TODO 
# opslag via xml <- deze eerst, misschien makkelijker 
# handmatig (achtergrondkaarten) 
# CSW voor pdok & provincie zuidholland 

import certifi

import json 
import os.path 
import os 
import re 

import requests 
from owslib.csw import CatalogueServiceWeb  # type: ignore 
from owslib.util import cleanup_namespaces, bind_url, add_namespaces, OrderedDict, Authentication, openURL, http_post
from owslib.wfs import WebFeatureService 
from owslib.wms import WebMapService

from urllib.parse import urlsplit, urlencode, urlparse, parse_qs, urlunparse, parse_qsl 
import urllib.request, urllib.parse, urllib.error 
import xml.etree.ElementTree as ET
from .constants import SERVICE_TYPE_MAPPING
from qgis.PyQt.QtNetwork import QNetworkRequest 
from qgis.PyQt.QtCore import QUrl 
from qgis.core import QgsNetworkAccessManager

from qgis.PyQt.QtCore import Qt 
from qgis.core import Qgis 

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
        
        # cert = certifi.where() # C:\OSGeo4W\apps\Python312\Lib\site-packages\certifi\cacert.pem
        # cert = False # Skips certification (not for production!)
        # self.auth = Authentication(cert=cert)
        # self.auth = Authentication(verify=False)

        # Set default layer loading behaviour
        self.csw_file_name = "main_csw.json"
        self.url_file_name = "url_list.json"

        self.service_type_mapping = SERVICE_TYPE_MAPPING
        self.protocol_to_type_mapping = {
            "OGC:WMS": "wms",
            "OGC:WMTS": "wmts",
            "OGC:WFS": "wfs",
            "OGC:WCS": "wcs",
            "OGC:API features": "api features",
            "OGC:API tiles": "api tiles",
        }

    def save_json_file(self, data, filename, subpath=None):
        """
        Save json data to specified filepath 
        
        :param data: json body to save
        :param filename: name of file
        """
        if subpath:
            dir_path = os.path.join(self.plugin_dir, "resources", subpath)
        else:
            dir_path = os.path.join(self.plugin_dir, "resources")

        if not os.path.exists(dir_path): 
            os.makedirs(dir_path, exist_ok=True) 

        path = os.path.join(dir_path, f"{filename}.json") 

        try: 
            with open(path, encoding="utf-8", mode="w") as f: 
                json.dump(data, f, indent=4) 
                self.log(f"[save_json_file] Saved {len(data)} records to {path}", lvl=3) 
        except Exception as e: 
            self.log(f"[save_json_file] Failed to save recordes. Error message: {e}") 

    ############################# Ingest getCapabilities files #############################

    def ingest_wfs_layers(self, urls):
        for service_data in urls:
            service_url = service_data["service_url"] 
            service_name = service_data["name"]
            service_title = service_data["title"]

            try:
                wfs = WebFeatureService(service_url, version="2.0.0")
            except Exception as e:
                self.log(f"Kon de {service_name} WebFeatureService niet vinden. Error {e}")
                continue
            # wfs = WebFeatureService(url, version="2.0.0", auth=self.auth)

            wfs_items = wfs.items()
            layer_list = []
            for _, c in wfs_items:
                layer = {
                    "name": c.id,
                    "title": c.title,
                    "abstract": service_title,
                    "service_url": service_url,
                    "service_title": service_title,
                    "service_abstract": service_title,
                    "service_type": "wfs",
                }
                layer_list.append(layer)
            self.save_json_file(layer_list, f"{service_name}-wfs", "layers") 

    def ingest_wms_layers(self, urls):
        for service_data in urls:
            service_url = service_data["service_url"]
            service_name = service_data["name"]
            service_title = service_data["title"]
            
            try:
                wms = WebMapService(service_url, version="1.3.0")
            except Exception as e:
                self.log(f"Kon de {service_name} WebMapService niet vinden. Error {e}")
                continue
            
            wms_items = wms.items()
            layer_list = []
            for _, c in wms_items:
                # get styles
                styles = []
                for s in c.styles:
                    style = {
                        "title": c.styles[s]["title"],
                        "name": s
                    }
                    styles.append(style)
                # get crs value
                crs = ""
                if "EPSG:28992" in c.crsOptions:
                    crs = "EPSG:28992"
                elif "EPSG:4326" in c.crsOptions:
                    crs = "EPSG:4326"
                else: 
                    self.log(f"Layer {c.title} has no relevant crs options. Ignore layer...")
                    self.log(f"   url: {service_url}")
                    continue

                # construct layer object
                layer = {
                    "name": c.id,
                    "title": c.title,
                    "abstract": service_title,
                    "styles": styles,
                    "crs": crs,
                    "service_url": service_url,
                    "service_title": service_title,
                    "service_abstract": service_title,
                    "service_type": "wms",
                }
                layer_list.append(layer)
                
            self.save_json_file(layer_list, f"{service_name}-wms", "layers")

    def ingest_gwsw_layers(self):
        base_url = "https://geodata.gwsw.nl"
        nad_ids = {
            "Delft"          : "Delft",
            "DenHaag"        : "Den Haag",
            "Lansingerland"  : "Lansingerland",
            "Leidschendam"   : "Leidschendam-Voorburg",
            "Maassluis"      : "Maassluis",
            "Middendelfland" : "Midden-Delfland",
            "Pijnacker"      : "Pijnacker-Nootdorp",
            "Rijswijk"       : "Rijswijk",
            "Schiedam"       : "Schiedam",
            "Vlaardingen"    : "Vlaardingen",
            "Westland"       : "Westland",
            "Zoetermeer"     : "Zoetermeer",
            "WS_WaterschappenAfvalwaterKeten": "Waterschappen",
        }
        gwsw_names = {
            "gwsw:Default_Buitengrens" : "Gebied",
            "gwsw:Default_Punt"        : "Rioolput",
            "gwsw:Default_Punt_deel"   : "Rioolput deel",
            "gwsw:Default_Lijn"        : "Rioolleiding",
            "gwsw:Default_Lijn_deel"   : "Rioolleiding deel",
        }

        layer_list = []
        for id in nad_ids:
            url = f"{base_url}/{id}"

            try:
                wfs = WebFeatureService(url, version="2.0.0")
            except Exception as e:
                self.log(f"Kon de {url} WebFeatureService niet vinden. Error {e}")
                continue
            
            wfs_items = wfs.items()
            for _, c in wfs_items:
                title = f"{nad_ids[id]}: {gwsw_names[c.id]}"
                
                layer = {
                    "name": c.id,
                    "title": title,
                    "abstract": "",
                    "service_url": url,
                    "service_title": "Stedelijk Water (Riolering) WFS",
                    "service_abstract": "Systemen voor stedelijk water met kenmerken gericht op beheeractiviteiten. Deze dataset omvat informatie over rioleringsgebieden bestaande uit riool-, transportstelsels  bestaande uit putten, (aansluit)leidingen, lozingspunten, pompen en gemalen. Deze service is opgezet conform het GWSW, Gegevens Woordenboek Stedelijk Water, van stichting Rioned. Voor meer informatie over de gebruikte termen, definities en samenhang van de objecten zie https://data.gwsw.nl",
                    "service_type": "wfs",
                }
                layer_list.append(layer)

        self.save_json_file(layer_list, f"gwsw-wfs", "layers")

    def get_url_layers(self):
        # do stuff
        source_path = os.path.join(self.plugin_dir, "resources", "layer_sources", self.url_file_name)
        self.des_path = os.path.join(self.plugin_dir, "resources", "layers", "url_generated")

        with open(source_path, "r", encoding="utf-8") as f:
            url_list = json.load(f)
            
        wfs_urls = [url_data for url_data in url_list if url_data["service_type"] == "wfs"]
        wms_urls = [url_data for url_data in url_list if url_data["service_type"] == "wms"]

        self.log(f"Found {len(wfs_urls)} WFS urls and {len(wms_urls)} WMS urls", 0)

        # 4. Run the service type ingest functions
        self.ingest_wfs_layers(wfs_urls)
        self.ingest_wms_layers(wms_urls)
        self.ingest_gwsw_layers()
    
    def get_csw_layers(self):
        # do stuff
        source_path = os.path.join(self.plugin_dir, "resources", "layer_sources", "csw_result")
        
        source_filepaths = [os.path.join(root, name)
             for root, dirs, files in os.walk(source_path) # walk: to recursively iterate through a directory and all its subdirectories
             for name in files
             if name.endswith(".json")] # get all json files except file containing the CatalogueServiceWeb urls
        
        source_files = [f for f in os.listdir(source_path)]

        for source in source_files:
            self.log(f"[get_csw_layers] source: {source}")
            with open(os.path.join(source_path, source), "r", encoding="utf-8") as f:
                data = json.load(f)

            # self.log(data)
            # WFS (WebFeatureService)
            continue
            wfs_urls = [url_data for url_data in data if url_data["service_type"] == "wfs"]
            self.ingest_wfs_layers(wfs_urls, source)


    # def get_csw_layers(self):
    #     # do stuff

    def get_layers(self):
        # 1. Get all relevant json files
        source_path = os.path.join(self.plugin_dir, "resources", "layer_sources", "csw_result")
        
        source_filepaths = [os.path.join(root, name)
             for root, dirs, files in os.walk(source_path) # walk: to recursively iterate through a directory and all its subdirectories
             for name in files
             if name.endswith(".json") and not name.endswith(self.csw_file_name)] # get all json files except file containing the CatalogueServiceWeb urls
        
        self.log(f"List of source files: {source_filepaths}", 0)
        
        # 2. Gather all the resulting urls
        url_list = []
        for source_path in source_filepaths:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            url_list.extend(data)

        # 3. Split between service type
        wfs_urls = [url_data for url_data in url_list if url_data["service_type"] == "wfs"]
        wms_urls = [url_data for url_data in url_list if url_data["service_type"] == "wms"]
        
        self.log(f"Found {len(wfs_urls)} WFS urls and {len(wms_urls)} WMS urls", 0)

        # 4. Run the service type ingest functions
        self.ingest_wfs_layers(wfs_urls)
        self.ingest_wms_layers(wms_urls)
        self.ingest_gwsw_layers()
        

    ############################# Read CatalogueServiceWeb-URLs #############################

    def _format_csw_layer(self, record: object, csw_name: str) -> dict:
        """
        Reshape the format of the csw-record object and adds the service type.

        :param record: Record containing a layer definition.
            Can contain multiple services (WFS, WMS, etc.) per layer.
        :type record: json object
        
        List with record fields in CSW response:
        'xml', 'rdf', 'identifier', 'identifiers', 'type', 'title', 'alternative', 'ispartof', 'abstract', 'date', 'created', 'issued', 'relation',
        'temporal', 'uris', 'references', 'modified', 'creator', 'publisher', 'coverage', 'contributor', 'language', 'source', 'rightsholder',
        'accessrights', 'license', 'format', 'subjects', 'rights', 'spatial', 'bbox', 'bbox_wgs84'
        """
        uris = getattr(record, "uris", [])

        csw_list_classified = []
        for uri in uris:
            protocol = uri["protocol"]
            name = uri["name"]
            url = uri["url"]
            
            if csw_name == "PDOK" and not ("https://api.pdok.nl/" in url or "https://service.pdok.nl/" in url):
                # nationaal georegister bevat allemaal andere datasets die niet relevant zijn, zoals die van zeeland, groningen, etc.
                # in dat geval willen we dit record negeren
                continue

            if name is None:
                name = getattr(record, "title", "") # TODO check if this leads to problems when opening a layer
            service_type = None # desired info

            # If the protocol tells us what service type we are dealing with, then that's preferable
            if any(p == protocol for p in self.protocol_to_type_mapping):
                service_type = self.protocol_to_type_mapping[protocol]
                
                # Sometimes we get a protocol but the url is not useful for us
                if service_type in ("wfs", "wms", "wmts", "wcs") and not "request=GetCapabilities" in url:
                    continue
            elif protocol == "" and "request=GetCapabilities" in url:
                if "wfs" in url.lower():
                    service_type = "wfs"
                elif "wms" in url.lower():
                    service_type = "wms"
                elif "wmts" in url.lower():
                    service_type = "wmts"
                else:
                    continue

            if service_type is not None:
                layer_def = {
                    "name": name,
                    "title": getattr(record, "title", ""),
                    "abstract": getattr(record, "abstract", ""),
                    "date": getattr(record, "date", ""),
                    "source": getattr(record, "source", ""),
                    "subjects": getattr(record, "subjects", ""),
                    "service_type": service_type,
                    "service_url": url,
                }
                csw_list_classified.append(layer_def)
            else:
                continue

        return csw_list_classified

    def get_csw_result(self): 
        """
        Read CatalogueServiceWeb-URLs to retrieve available services.
        
        :param data: list with JSON objects containing CatalogueServiceWeb-URLs
        """
        csw_path = os.path.join(self.plugin_dir, "resources", "layer_sources", self.csw_file_name)
        
        with open(csw_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for csw_data in data: 
            csw_name = csw_data["name"]
            csw_url = csw_data["url"]
            
            # tijdelijk wat ophalen zonder SSL checks
            # auth = Authentication(verify=False)
            # csw = CatalogueServiceWeb(csw_url, timeout=60, auth=auth)
            try:
                csw = CatalogueServiceWeb(csw_url, timeout=60)
            except Exception as e:
                self.log(f"Kon de {csw_name} CatalogueServiceWeb niet vinden. Foutmelding: {e}")
                # continue

            self.log(f"[get_csw_lists] csw received: {csw}", lvl=0)
            page_size = 50
            all_records = {}
            start = 0

            self.log(f"[get_csw_lists] Beginnen met gepagineerd ophalen van records. Aantal records per keer={page_size}", lvl=0)
            while True:
                try:
                    csw.getrecords2(startposition=start, maxrecords=page_size, esn="full")
                except Exception as e:
                    self.log(f"[get_csw_lists] Kon geen records ophalen op startpositie={start}. Foutmelding: {e}")
                    break

                if not csw.records:
                    self.log(f"[get_csw_lists] Geen records meer beschikbaar op startpositie={start}")
                    break

                all_records.update(csw.records)

                if len(csw.records) < page_size:
                    break

                start += page_size
                break # TODO: remove to get all data from the catalogue services

            self.log(f"[get_csw_lists] Ophalen records afgerond. Totaal={len(all_records)}", lvl=0)

            try:
                csw_list = []
                for _, record in all_records.items():
                    csw_record = self._format_csw_layer(record, csw_name)
                    csw_list.extend(csw_record)
            except Exception as e:
                self.log(e)

            self.log(f"[get_csw_lists] Formatting records naar een CSW lijst afgerond. Totaal={len(csw_list)}", lvl=0)
            if len(csw_list) == 0:
                self.log(f"[get_csw_lists] CSW lijst was leeg voor URL: {csw_url}")
                continue
            
            # Save data to JSON
            self.save_json_file(csw_list, csw_name, os.path.join("layer_sources", "csw_result"))