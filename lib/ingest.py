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
# from owslib.util import cleanup_namespaces, bind_url, add_namespaces, OrderedDict, Authentication, openURL, http_post
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
        self.service_type_mapping = SERVICE_TYPE_MAPPING
        self.protocol_to_type_mapping = {
            "OGC:WMS": "wms",
            "OGC:WMTS": "wmts",
            "OGC:WFS": "wfs",
            "OGC:WCS": "wcs",
            "OGC:API features": "api features",
            "OGC:API tiles": "api tiles",
        } 


    def save_json_file(self, data, filename):
        """
        Save json data to specified filepath 
        
        :param data: json body to save
        :param filename: path to file
        """
        dir_path = os.path.join( 
            self.plugin_dir, 
            "resources", 
            "layers",
        ) 
        if not os.path.exists(dir_path): 
            os.makedirs(dir_path, exist_ok=True) 

        path = os.path.join(dir_path, f"{filename}.json") 

        try: 
            with open(path, encoding="utf-8", mode="w") as f: 
                json.dump(data, f, indent=4) 
                self.log(f"[save_json_file] Saved {len(data)} records to {path}", lvl=3) 
        except Exception as e: 
            self.log(f"[save_json_file] Failed to save recordes. Error message: {e}") 

    def ingest_wfs_layers(self, urls):
        for service_data in urls:
            service_url = service_data["url"] 
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
            self.save_json_file(layer_list, f"{service_name}-wfs") 

    def ingest_wms_layers(self, urls):
        for service_data in urls:
            service_url = service_data["url"]
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
                
            self.save_json_file(layer_list, f"{service_name}-wms")

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
                self.log(f"c.id = {c.id}")
                title = f"{nad_ids[id]}: {gwsw_names[c.id]}"
                self.log(f"title = {title}")
                
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

        self.save_json_file(layer_list, f"gwsw-wfs")

    def get_layers(self):
        # 1. Extract service urls from CatalogueServiceWeb urls
        # get_csw_lists()
        
        # 2. Add csw urls to list
        source_path = os.path.join(self.plugin_dir, "resources", "layer_sources")
        
        source_filepaths = [os.path.join(root, name)
             for root, dirs, files in os.walk(source_path) # walk: to recursively iterate through a directory and all its subdirectories
             for name in files
             if name.endswith(".json") and not name.endswith("main_csw.json")] # get all json files except file containing the CatalogueServiceWeb urls
        
        self.log(f"List of source files: {source_filepaths}", 0)
        
        # 3. Gather all the resulting urls
        url_list = []
        for source_path in source_filepaths:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            url_list.extend(data)

        # 4. Split between service type
        wfs_urls = [url_data for url_data in url_list if url_data["service_type"] == "wfs"]
        wms_urls = [url_data for url_data in url_list if url_data["service_type"] == "wms"]
        
        self.log(f"Found {len(wfs_urls)} WFS urls and {len(wms_urls)} WMS urls", 0)

        # 5. Run the service type ingest functions
        self.ingest_wfs_layers(wfs_urls)
        self.ingest_wms_layers(wms_urls)
        self.ingest_gwsw_layers()
        return
        # 4. special ones like gwsw?
        

    def get_csw_lists(self): 
        """
        Get and save layers through a CSW url 
        Docstring for get_csw_lists
        
        :param self: Description
        """
        csw_urls = { 
            "pzh": "https://opendata.zuid-holland.nl/geonetwork/srv/dut/csw", # only has wfs and wms layers 
            # "pdok": "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw", 
        } 
        # https://qgis.org/pyqgis/3.44/core/QgsAuthConfigurationStorage.html#qgis.core.QgsAuthConfigurationStorage.storeCertIdentity # opslaan van een PEM bestand in QGIS 
        # pdok: https://service.pdok.nl & https://api.pdok.nl, maar nationaalgeoregister heeft ook vanalles zoals https://opengeodata.zeeland.nl/, https://data.rivm.nl/ of https://maps.bodemdata.nl 
        # toewerken naar getcapabilities url list en die uitlezen, bijv.: 
            # "https://service.pdok.nl/cbs/wijkenbuurten/2017/wms/v1_0?request=GetCapabilities", 
            # "https://service.pdok.nl/cbs/wijkenbuurten/2017/wfs/v1_0?request=GetCapabilities", 

        for source in csw_urls: 
            csw_url = csw_urls[source] 
            # Retrieve list with objects from CSW url 
            csw_list = self.get_csw_list(csw_url) 
            # def_list = self.complete_layer_data(csw_list) 

            if len(csw_list) == 0: 
                self.log(f"[get_layers] CSW list was empty for url: {csw_url}") 
                continue 

            # Save metadata to JSON 
            self.save_json_file(csw_list, f"layers-{source}") 


    def complete_layer_data(self, csw_list: list): 
        self.log(f"[complete_layer_data] Start for list length: {len(csw_list)}") 
        layer_list = [] 
        layer = None 
        for record in csw_list: 
            service_type = record["service_type"] 
            if service_type == "wfs": 
                layer = { 
                    "name": record["name"], 
                    "title": record["title"], 
                    "abstract": "abstract", 
                    "service_url": record["service_url"], 
                    "service_title": "service_title", 
                    "service_abstract": record["abstract"], 
                    "service_type": record["service_type"], 
                } 

    def get_csw_list(self, csw_url: str):
        """
        Retrieve list of layer definition objects from a CSW url. 

        :param csw_url: Url to CSW definition of available layer services. 
        :type csw_url: str 
        """
        try: 
            csw = CatalogueServiceWeb(csw_url, timeout=60) 
            # csw = CatalogueServiceWeb(csw_url, version="2.0.2", timeout=60) 
        except Exception as e: 
            self.log(f"[get_csw_list] Failed to connect: {e}") 
            return 
        self.log(f"Number of datasets available: {len(csw.records.keys())}") 
        page_size = 50 
        all_records = {} 
        start = 0 

        self.log(f"[get_layer_list] Starting paged fetch with page_size={page_size}", lvl=0) 
        while True: 
            try: 
                csw.getrecords2(startposition=start, maxrecords=page_size, esn="full") 
                # getrecords2 options: 
                    # maxrecords=maxrecord, 
                    # cql=query, 
                        # protocol_key = "OnlineResourceType" 
                        # query = f"type='service' AND organisationName='{svc_owner}' AND {protocol_key}='{protocol}'" 
                    # startposition=start, 
                    # esn="full", 
                    # outputschema="http://www.isotc211.org/2005/gmd", 
                    # sortby="CreationDate:A" 
            except Exception as e: 
                self.log(f"[get_layer_list] Failed to fetch records at start={start}: {e}") 
                break 

            if not csw.records: 
                self.log(f"[get_layer_list] No more records at start={start}") 
                break 

            # self.log(f"[get_layer_list] Retrieved {len(csw.records)} records (start={start})", lvl=0) 

            all_records.update(csw.records) 

            # stop when fewer results than requested 
            if len(csw.records) < page_size: 
                break 

            start += page_size 
            # break # TODO delete this part afterwards 
            # if start > 50: 
            #     break # TODO delete this part afterwards 

        self.log(f"[get_layer_list] Finished. Total records fetched: {len(all_records)}", lvl=0) 

        try: 
            csw_list = [] 
            for _, record in all_records.items(): 
                csw_layers = self._format_csw_layer(record) 
                for layer in csw_layers: 
                    if layer: 
                        csw_list.append(layer) 
        except Exception as e: 
            self.log(f"[get_layer_list] Failed to save records to list: {e}") 
        return csw_list 

    def _format_csw_layer(self, record: object):
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
            url = uri["url"] 
            name = uri["name"] 
            service_type = None # desired info 

            if url is not None: 
                if any(p == protocol for p in self.protocol_to_type_mapping): 
                    service_type = self.protocol_to_type_mapping[protocol] 
                    if service_type in ("wfs", "wms", "wmts", "wcs") and not "request=GetCapabilities" in url: 
                        service_type = None 

                    # if service_type == "wfs" or service_type == "wms" 
                elif protocol == "" and "request=GetCapabilities" in url: 
                    if "wfs" in url.lower(): 
                        service_type = "wfs" 
                    elif "wms" in url.lower(): 
                        service_type = "wms" 
                    elif "wmts" in url.lower(): 
                        service_type = "wmts" 
            # if service_type is not None: 
            # if service_type: 
            if name is None: 
                name = getattr(record, "title", "") # TODO check if this leads to problems when opening a layer 
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

        return csw_list_classified 

########################## OLD CODE ########################################## 

    def extract_oat_info(self, url): 
        with urllib.request.urlopen(url) as response: 
            body = response.read().decode("utf-8") 
            try: 
                json_data = json.loads(body) 
                return json_data 
            except Exception: 
                self.log(f"[_read_url] Failed to load json_data from url: {url}") 
                return 
            for link in json_data["links"]: 
                if link["rel"] == "service-desc": 
                    link_description = link["href"] 
                elif link["rel"].endswith("styles"): 
                    link_styles = link["href"] 
                elif link["rel"].endswith("tilesets-vector"): 
                    link_tiles = link["href"] 
                elif link["rel"].endswith("tiling-schemes"): 
                    link_matrix_sets = link["href"] 
                self.log(f"descr: {link_description}, styles: {link_styles}, tiles: {link_tiles}, matrix_sets: {link_matrix_sets}") 

    def assign_service_type(self, csw_list: list): 
        csw_list_classified = [] 
        for record in csw_list: 

            uris = record["uris"] 
            for uri in uris: 
                protocol = uri["protocol"] 
                url = uri["url"] 
                name = uri["name"] 
                service_type = None # desired info 

                if url is not None: 
                    if any(p == protocol for p in self.protocol_to_type_mapping): 
                        service_type = self.protocol_to_type_mapping[protocol] 

                        # if service_type == "wfs" or service_type == "wms" 
                    elif protocol == "" and "request=GetCapabilities" in url: 
                        if "wfs" in url.lower(): 
                            service_type = "wfs" 
                        elif "wms" in url.lower(): 
                            service_type = "wms" 
                        elif "wmts" in url.lower(): 
                            service_type = "wmts" 
                # if service_type is not None: 
                if service_type: 
                    if name is None: 
                        name = record["title"] # TODO check if this leads to problems when opening a layer 
                    layer_def = { 
                        "name": name, 
                        "title": record["title"], 
                        "abstract": record["abstract"], 
                        "date": record["date"], 
                        "source": record["source"], 
                        "subjects": record["subjects"], 
                        "service_type": service_type, 
                        "service_url": url, 
                    } 
                    csw_list_classified.append(layer_def) 

        return csw_list_classified 