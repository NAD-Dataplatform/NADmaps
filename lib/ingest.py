######################################################################################### 
######################################  Show and load layers ############################ 
######################################################################################### 
# TODO 
# opslag via xml <- deze eerst, misschien makkelijker 
# handmatig (achtergrondkaarten) 
# CSW voor pdok & provincie zuidholland 

# in lijst inklapbare categorieen
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
from owslib.util import Authentication

from urllib.parse import urlsplit, urlencode, urlparse, parse_qs, urlunparse, parse_qsl 
import urllib.request, urllib.parse, urllib.error 
import xml.etree.ElementTree as ET 
from .constants import PLUGIN_NAME 
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

        self.auth = Authentication(cert=certifi.where())
        # self.auth = Authentication(verify=certifi.where())
        # self.auth = Authentication(verify=False)

        # Set default layer loading behaviour 
        self.service_type_mapping = {
            "wms": "WMS",
            "wmts": "WMTS",
            "wfs": "WFS",
            "wcs": "WCS",
            "api features": "OGC API - Features",
            "api tiles": "OGC API - Tiles",
        } 
        self.protocol_to_type_mapping = {
            "OGC:WMS": "wms",
            "OGC:WMTS": "wmts",
            "OGC:WFS": "wfs",
            "OGC:WCS": "wcs",
            "OGC:API features": "api features",
            "OGC:API tiles": "api tiles",
        } 
        self.wfs_urls = {
            "hhd": {
                "url": "https://dservices.arcgis.com/f6rHQPZpXXOzhDXU/arcgis/services/LeggerDelfland/WFSServer?service=wfs&request=getcapabilities",
                "title": "Legger Delfland",
            },
            "klimaatatlas": {
                "url": "https://apps.geodan.nl/public/data/org/gws/YWFMLMWERURF/kea_public/wfs?request=getCapabilities",
                "title": "Klimaatatlas",
            },
        } 
        self.wms_urls = {
            "klimaatatlas": {
                "url": "https://apps.geodan.nl/public/data/org/gws/YWFMLMWERURF/kea_public/wms?request=getCapabilities",
                "title": "Klimaatatlas",
            },
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

    def ingest_wfs_layers(self):
        for source in self.wfs_urls: 
            url = self.wfs_urls[source]["url"] 
            service_title = self.wfs_urls[source]["title"] 
            wfs = WebFeatureService(url, version="2.0.0", auth=self.auth) 

            wfs_items = wfs.items() 
            layer_list = [] 
            for _, c in wfs_items: 
                layer = { 
                    "name": c.id, 
                    "title": c.title, 
                    "abstract": service_title, 
                    "service_url": url, 
                    "service_title": service_title, 
                    "service_abstract": service_title, 
                    "service_type": "wfs", 
                } 
                layer_list.append(layer) 
            self.save_json_file(layer_list, f"wfs-{source}") 

    def ingest_wms_layers(self): 
        for source in self.wms_urls: 
            url = self.wms_urls[source]["url"] 
            service_title = self.wms_urls[source]["title"] 
            wms = WebMapService(url, version="1.3.0", auth=self.auth) 
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
                    self.log(f"   url: {url}") 
                    continue 

                # construct layer object 
                layer = { 
                    "name": c.id, 
                    "title": c.title, 
                    "abstract": service_title, 
                    "styles": styles, 
                    "crs": crs, 
                    "service_url": url, 
                    "service_title": service_title, 
                    "service_abstract": service_title, 
                    "service_type": "wms", 
                } 
                layer_list.append(layer) 
            self.save_json_file(layer_list, f"wms-{source}") 

    def ingest_gwsw_layers(self): 
        base_url = "https://geodata.gwsw.nl/" 
        nad_ids = [ 
            "Delft", "DenHaag",
        ]

    def get_layers(self): 
        # get_csw_lists() 
        self.ingest_wfs_layers()
        self.ingest_wms_layers()

    def get_csw_lists(self): 
        """
        Get and save layers through a CSW url 
        Docstring for get_csw_lists
        
        :param self: Description
        """
        csw_urls = { 
            # "pzh": "https://opendata.zuid-holland.nl/geonetwork/srv/dut/csw", # only has wfs and wms layers 
            "pdok": "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw", 
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

    def compare_files(self):
        """
        get layers takes the layers from one json file and compares them, saving the differences 
        
        :param self: Description
        """
        pdok_list = [] 
        geo_list = [] 
        pdok_path = os.path.join(self.plugin_dir, "resources", "layers", "raw", "pdok_test.json") # list from pdok services plugin 
        geo_path = os.path.join(self.plugin_dir, "resources", "layers", "raw2", "layer_list_pdok.json") # list nationaal georegister that mention pdok 

        with open(pdok_path, "r", encoding="utf-8") as f: 
            pdok_list.extend(json.load(f)) 

        with open(geo_path, "r", encoding="utf-8") as f: 
            geo_list.extend(json.load(f)) 

        diff_layer_list = [] 
        for obj in pdok_list: 
            if obj not in geo_list: 
                diff_layer_list.append(obj) 
        # Save metadata to JSON 
        path = self.create_directory("raw2") # add the raw-data folder to gitignore 
        diff_list_path = os.path.join( 
            path, 
            f"lost_list.json", 
        ) 
        try: 
            with open(diff_list_path, encoding="utf-8", mode="w") as f: 
                json.dump(diff_layer_list, f, indent=4) 
                self.log(f"[get_layers] Saved {len(diff_layer_list)} records to {diff_list_path}", lvl=3) 
        except Exception as e: 
                self.log(f"[get_layers] Failed to save recordes: {e}") 

    def COMMENTEDSTUFF(self): 
        pass 
        # def csw_format_layer(self, csw_list): 
        #     self.log("here!") 
        #     layer_list = [] 
        #     layer = None 
        #     for record in csw_list: 
        #         service_type = record["service_type"] 
        #         if service_type == "wfs": 
        #             layer = { 
        #                 "name": record["name"], 
        #                 "title": record["title"], 
        #                 "abstract": "abstract" 
        #                 "service_url": record["url"], 
        #                 "service_title": "service_title", 
        #                 "service_abstract": record["abstract"], 
        #                 "service_type": "wfs", 
        #             } 
        #         elif service_type == "wms": 
        #             layer = { 
        #                 "name": "top25raster", 
        #                 "title": "TOP25raster", 
        #                 "abstract": "TOP25raster wordt softwarematig afgeleid uit TOP10NL. Het Kadaster heeft gekozen voor een detailniveau dat uitstekend geschikt is voor middenschalige toepassingen. TOP25raster is geschikt als topografische ondergrond in GIS, CAD en Desktop Mapping.", 
        #                 "styles": [ 
        #                     { 
        #                         "title": "TOP25raster", 
        #                         "name": "default" 
        #                     } 
        #                 ], 
        #                 "crs": "EPSG:28992,EPSG:25831,EPSG:25832,EPSG:3034,EPSG:3035,EPSG:3857,EPSG:4258,EPSG:4326,CRS:84", 
        #                 "minscale": "4000", 
        #                 "maxscale": "50000", 
        #                 "imgformats": "image/png,image/jpeg,image/png; mode=8bit,image/vnd.jpeg-png,image/vnd.jpeg-png8", 
        #                 "service_url": "https://service.pdok.nl/brt/topraster/wms/v1_0?request=GetCapabilities&service=WMS", 
        #                 "service_title": "BRT TOPraster", 
        #                 "service_abstract": "Deze WMS bevat verschillende producten van de Basisregistratie Topografie (BRT) in rastervorm.", 
        #                 "service_type": "wms", 
        #             } 

            # WFS 

            # name = getattr(r, "title", "") 
            # uris = getattr(r, "uris", []) 
            # has_getcapabilities = any("request=GetCapabilities" in uri.get("url", "") for uri in uris ) 
            # self.log(f"layer: {name} has getcapabilities: {has_getcapabilities} or ") 
            #         "name": getattr(r, "title", ""), 
            #         "title": getattr(r, "title", ""), 
            #         "abstract": getattr(r, "title", ""), 

            #         "styles": getattr(r, "title", ""), # for wms, wmts, api tiles 
            #         "tiles": getattr(r, "tiles", ""), # for api tiles 
            #         "crs": getattr(r, "crs", ""), # for wms, wmts, api tiles (alleen correct in webmercators crs epsg 3857) 
            #         "tilematrixsets": getattr(r, "crs", ""), # for wmts 
            #         "imgformats": getattr(r, "title", ""), # for wmts 

            #         "service_url": getattr(r, "title", ""), 
            #         "service_title": getattr(r, "title", ""), 
            #         "service_abstract": getattr(r, "title", ""), 
            #         "service_type": getattr(r, "title", ""), 

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

########################## OLD CODE ########################################## 

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