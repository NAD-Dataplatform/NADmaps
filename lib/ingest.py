######################################################################################### 
################################## Ingest web service layers ############################ 
######################################################################################### 

import json
import os.path
import os
import requests
import certifi
from concurrent.futures import ThreadPoolExecutor, as_completed

from owslib.csw import CatalogueServiceWeb  # type: ignore 
from owslib.wfs import WebFeatureService 
from owslib.wms import WebMapService
from owslib.wmts import WebMapTileService
from owslib.wcs import WebCoverageService, wcs110  # type: ignore
from owslib.ogcapi.features import Features

from .constants import SERVICE_TYPE_MAPPING

class IngestLayersManager(): 
    def __init__(self, dlg, iface, plugin_dir, log):
        if dlg is None: raise ValueError("LayerManager: dlg is None")
        if iface is None: raise ValueError("LayerManager: iface is None")
        if plugin_dir is None: raise ValueError("LayerManager: plugin_dir is None")
        if log is None: raise ValueError("LayerManager: log is None")

        self.dlg = dlg
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.log = log
        
        self.log("Init IngestLayersManager")
        self.session = requests.Session()
        
        # cert = False # Skips certification (not for production!)
        # self.auth = Authentication(verify=False)
        # cert = certifi.where() # C:\OSGeo4W\apps\Python312\Lib\site-packages\certifi\cacert.pem
        # self.auth = Authentication(cert=cert)

        # Set layer loading behaviour
        self.csw_file_name = "csw_list.json"
        self.url_file_name = "url_list.json"

        self.service_type_mapping = SERVICE_TYPE_MAPPING
        for service_type in SERVICE_TYPE_MAPPING:
            self.dlg.CSWLoadComboBox.addItem(service_type)
        self.dlg.CSWLoadComboBox.setCurrentIndex(3)

        source_path = os.path.join(self.plugin_dir, "resources", "layer_sources", "csw_result")
        for file in os.listdir(source_path):
            self.dlg.CSWsourceComboBox.addItem(file)

        self.protocol_to_type_mapping = {
            "OGC:WMS": "wms",
            "OGC:WMTS": "wmts",
            "OGC:WFS": "wfs",
            "OGC:WCS": "wcs",
            "OGC:API features": "api features",
            "OGC:API tiles": "api tiles",
        }
        self.ingest_fn_mapping = {
            "wfs": self._ingest_wfs_layers,
            "wms": self._ingest_wms_layers,
            "wmts": self._ingest_wmts_layers,
            "wcs": self._ingest_wcs_layers,
            "api features": self._ingest_oaf_layers,
            "api tiles": self._ingest_oat_layers,
        }
        

    def save_json_file(self, data: list[dict], filename: str, subpath: str | None = None) -> None:
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
        except Exception as e: 
            self.log(f"[save_json_file] Failed to save recordes. Error message: {e}") 

    def cleanup_folder(self, subpath: str | None) -> None:
        if not subpath:
            self.log("[cleanup_folder] Geen subpath opgegeven; cleanup overgeslagen", lvl=0)
            return
        
        dir_path = os.path.join(self.plugin_dir, "resources", subpath)
        
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                try:
                    os.unlink(file_path)
                except Exception as e:
                    self.log(f"[cleanup_folder] Kon bestand niet verwijderen: {file_path}. Foutmelding: {e}")
                    continue
        else:
            self.log(f"[cleanup_folder] Folder bestond nog niet: {dir_path}", lvl=0)

    def remove_duplicates(self, dict_list: list[dict]) -> list[dict]:
        self.log(f"[remove_duplicates] length before: {len(dict_list)}")

        seen = set()
        result = []
        for d in dict_list:
            key = (
                d.get("name", ""),
                d.get("title", ""),
                d.get("service_type", "")
            )
            if key not in seen:
                seen.add(key)
                result.append(d)

        self.log(f"[remove_duplicates] length after: {len(result)}")
        return result

    ############################# Fetch getCapabilities files #############################

    def _ingest_gwsw_layers(self) -> None:
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
                wfs = WebFeatureService(url, version="2.0.0", timeout=30)
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

        self.save_json_file(layer_list, "gwsw-wfs", os.path.join("layers", "custom"))


    def _ingest_wfs_layers(self, service_data: dict[str, any]) -> list[dict[str, any]]:

        service_url = service_data["service_url"]
        service_name = service_data["name"]
        #TODO: check service_data["abstract"] to add to the layer-data

        try:
            wfs = WebFeatureService(service_url, version="2.0.0", timeout=30)
        except Exception as e:
            self.log(f"Kon de {service_name} WebFeatureService niet vinden. Error {e}")
            return []
        # wfs = WebFeatureService(url, version="2.0.0", auth=self.auth)

        layers = []
        for _, c in wfs.items():
            # ==== abstract ====
            abstract = ""
            if c.abstract:
                abstract = c.abstract

            layers.append({
                "name": c.id,
                "title": c.title,
                "abstract": abstract,
                "service_url": service_url,
                "service_title": service_data["title"],
                "service_abstract": service_data.get("abstract", ""),
                "service_type": "wfs",
            })
        return layers

    def _ingest_wms_layers(self, service_data: dict[str, any]) -> list[dict[str, any]]:
        service_url = service_data["service_url"]
        service_name = service_data["name"]

        try:
            wms = WebMapService(service_url, version="1.3.0", timeout=30)
        except Exception as e:
            self.log(f"Kon de {service_name} WebMapService niet vinden. Error {e}")
            return []
        
        layers = []
        for _, c in wms.items():
            # ==== styles ====
            styles = []
            for s in c.styles:
                style = {
                    "title": c.styles[s]["title"],
                    "name": s
                }
                styles.append(style)
            # ==== crs ====
            crs = ""
            if "EPSG:28992" in c.crsOptions:
                crs = "EPSG:28992"
            elif "EPSG:4326" in c.crsOptions:
                crs = "EPSG:4326"
            else: 
                self.log(f"Layer {c.title} has no relevant crs options. Ignore layer...")
                self.log(f"   url: {service_url}")
                continue
            # ==== abstract ====
            abstract = ""
            if c.abstract:
                abstract = c.abstract

            # construct layer object
            layers.append({
                "name": c.id,
                "title": c.title,
                "abstract": abstract,
                "styles": styles,
                "crs": crs,
                "service_url": service_url,
                "service_title": service_data["title"],
                "service_abstract": service_data.get("abstract", ""),
                "service_type": "wms",
            })
        return layers

    def _ingest_oaf_layers(self, service_data: dict[str, any]) -> list[dict[str, any]]:
        service_url = service_data["service_url"]
        service_name = service_data["name"]

        try:
            oaf = Features(service_url, timeout=30)
        except Exception as e:
            self.log(f"[ingest_oaf_layers] Kon de {service_name} OGC API Features niet vinden. Error {e}")
            return []

        collections = oaf.collections()['collections']

        if len(collections) == 0:
            self.log(f"[ingest_oaf_layers] url {service_url} voor service {service_name} had geen inhoud. Wordt overgeslagen...")
            return []

        layers = []
        for entry in collections:
            layers.append({
                "name": entry["id"],
                "title": entry["title"],
                "abstract": entry.get("description", ""),
                "service_url": service_url,
                "service_title": service_data["title"],
                "service_abstract": service_data.get("abstract", ""),
                "service_type": "api features",
            })
        return layers

    def _ingest_oat_layers(self, service_data: dict[str, any]) -> list[dict[str, any]]:
        service_url = service_data["service_url"]
        service_name = service_data["name"]

        try:
            response = self.session.get(service_url, timeout=(5, 30))
        except Exception as e:
            self.log(f"Kon de {service_name} OGC API Tiles niet vinden. Foutmelding: {e}")
            return []

        response.raise_for_status()
        body = response.json()

        layers = []
        styles = []
        tiles = []
        name = ""
        abstract = ""
        for link in body["links"]:
            # ==== styles ====
            if link["href"].endswith("styles"):
                styles_data = self.session.get(link['href'], timeout=(5, 30)).json()
                for s in styles_data["styles"]:
                    style = {
                        "id": s["id"],
                        "name": s["title"],
                        "url": s["links"][1]["href"]
                    }
                    styles.append(style)

            # ==== tiles ====
            if link["href"].endswith("tiles"):
                tiles_data = self.session.get(link['href'], timeout=(5, 30)).json()
                abstract = tiles_data["description"]
                name = tiles_data["title"]

                if name == "":
                    self.log(f"[ingest_oat_layers] url {service_url} voor service {service_name} had geen title. Wordt overgeslagen...")
                    continue

                tilesets = []
                for t in tiles_data["tilesets"]:
                    tile_limits = t["tileMatrixSetLimits"]
                    max_zoomlevel = 0
                    for l in tile_limits:
                        zoomlevel = int(l["tileMatrix"])
                        if zoomlevel > max_zoomlevel:
                            max_zoomlevel = zoomlevel

                    tileset = {
                        "tileset_id": t["tileMatrixSetId"],
                        "tileset_crs": t["crs"],
                        "tileset_max_zoomlevel": max_zoomlevel
                    }
                    tilesets.append(tileset)

                tile_data = {
                    "title": tiles_data["title"],
                    "abstract": abstract,
                    "tilesets" : tilesets
                }
                tiles.append(tile_data)
            
            # check if the layer has actual tilesets
            if len(tiles) == 0:
                continue

            layers.append({
                "name": name,
                "title": name,
                "abstract": abstract,
                "styles": styles,
                "tiles": tiles,
                "service_url": service_url,
                "service_title": body["title"],
                "service_abstract": body.get("description", ""),
                "service_type": "api tiles",
            })

        return layers

    def _ingest_wmts_layers(self, service_data: dict[str, any]) -> list[dict[str, any]]:
        service_url = service_data["service_url"]
        service_name = service_data["name"]
        
        try:
            wmts = WebMapTileService(service_url, timeout=30)
        except Exception as e:
            self.log(f"Kon de {service_name} WebMapTileService niet vinden. Error {e}")
            return []

        layers = []
        for _, c in wmts.items():
            styles = []
            for style_name, style_object in c.styles.items():
                title = ""
                if "title" in style_object:
                    title = style_object["title"]
                
                style = {
                    "title": title,
                    "name": style_name
                }
                styles.append(style)

            tilematrixsets = ",".join(list(c.tilematrixsetlinks.keys()))
            imgformats = ",".join(c.formats)
            
            layers.append({
                "name": c.id,
                "title": c.title,
                "abstract": c.get("abstract", ""),
                "styles": styles,
                "tiles": tilematrixsets,  # "tilematrixsets": "EPSG:28992,EPSG:3857,EPSG:4258,EPSG:4326,EPSG:25831,EPSG:25832,OGC:1.0:GoogleMapsCompatible"
                "imgformats": imgformats, # "imgformats": "image/jpeg"
                "service_url": service_url,
                "service_title": service_data["title"],
                "service_abstract": service_data.get("abstract", ""),
                "service_type": "wmts",
            })
        return layers

    def _ingest_wcs_layers(self, service_data: dict[str, any]) -> list[dict[str, any]]:
        service_url = service_data["service_url"]
        service_name = service_data["name"]

        try:
            wcs = WebCoverageService(service_url)
        except Exception as e:
            self.log(f"Kon de {service_name} WebCoverageService niet vinden. Error {e}")
            return []

        layers = []
        for _, c in wcs.items():
            layers.append({
                "name": c.id,
                "title": wcs.identification.title,
                "abstract": wcs.identification.abstract,
                "service_url": service_url,
                "service_title": service_data["title"],
                "service_abstract": service_data.get("abstract", ""),
                "service_type": "wcs",
            })

        return layers            


    def _ingest(self, service_type: str, urls: list[dict], subpath: str):
        function = self.ingest_fn_mapping.get(service_type)
        if function is None:
            self.log(f"[_ingest] Onbekend service type: {service_type}", lvl=2)
            return

        if not urls:
            self.log(f"[_ingest] Geen URLs gevonden voor service type: {service_type}", lvl=1)
            return

        self.cleanup_folder(subpath)
        layer_list = []

        max_workers = min(8, len(urls))  # stel conservatief in
        self.log(f"[_ingest] Start parallel ingest voor {service_type} met {max_workers} workers", lvl=0)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_service = {
                executor.submit(function, service_data): service_data
                for service_data in urls
            }

            for future in as_completed(future_to_service):
                service_data = future_to_service[future]
                try:
                    layers = future.result()
                    if layers:
                        layer_list.extend(layers)
                except Exception as e:
                    self.log(f"[_ingest] Fout bij service url ({service_data.get('service_url', '')}). Foutmelding: {e}", lvl=1)

        if not layer_list:
            self.log(f"[_ingest] Geen lagen gevonden voor service type: {service_type}", lvl=1)
            return

        new_list = self.remove_duplicates(layer_list)
        self.save_json_file(new_list, service_type, subpath)


    ############################# Read list of getCapabilities-URLs #############################

    def get_url_layers(self) -> None:
        source_path = os.path.join(self.plugin_dir, "resources", "layer_sources", self.url_file_name)
        des_path = os.path.join("layers", "url_generated")

        with open(source_path, "r", encoding="utf-8") as f:
            source_list = json.load(f)
            
        self.log(f"Found {len(source_list)} sources", lvl=0)

        self.cleanup_folder(des_path)

        for source in source_list:
            # get correct function for service type (e.g. wfs requires _ingest_wfs_layers())
            function = self.ingest_fn_mapping.get(source['service_type'])
            # call function to retrieve data
            service_data = function(source)
            # store results
            self.save_json_file(service_data, f"{source['name']}-{source['service_type']}", des_path)

        self._ingest_gwsw_layers()
    
    ############################# Read list of CatalogueServiceWeb-URLs #############################


    def get_csw_layers(self) -> None:
        source_path = os.path.join(self.plugin_dir, "resources", "layer_sources", "csw_result")
        service = self.dlg.CSWLoadComboBox.currentText()
        source = self.dlg.CSWsourceComboBox.currentText()

        if service not in self.ingest_fn_mapping:
            self.log(f"[get_csw_layers] Onbekende service: {service}", lvl=2)

        source_name = source.split('.')[0]

        self.log(f"[get_csw_layers] source: {source}")
        self.log(f"[get_csw_layers] source_name: {source_name}")
        self.log(f"[get_csw_layers] service: {service}")

        # ===========================
        # read list with csw metadata
        with open(os.path.join(source_path, source), "r", encoding="utf-8") as f:
            data = json.load(f)

        # ===========================
        # query and save layer data files by type
        urls = [url_data for url_data in data if url_data["service_type"] == service]
        self._ingest(service, urls, os.path.join("layers", "csw_generated", source_name, service))

    ############################# Read CatalogueServiceWeb metadata-URLs #############################

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

            # Sometimes we do not get a protocol so we want to deduce the service type based on the url
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

    def get_csw_result(self) -> None: 
        """
        Read CatalogueServiceWeb-URLs to retrieve available services.
        
        :param data: list with JSON objects containing CatalogueServiceWeb-URLs
        """
        self.log("[get_csw_result] start", lvl=0)
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
                if self.auth:
                    csw = CatalogueServiceWeb(csw_url, timeout=60, auth=self.auth)
                else:
                    csw = CatalogueServiceWeb(csw_url, timeout=60)
            except Exception as e:
                self.log(f"Kon de {csw_name} CatalogueServiceWeb niet vinden. Foutmelding: {e}")
                continue

            self.log(f"[get_csw_result] csw received: {csw}", lvl=0)
            page_size = 50
            all_records = {}
            start = 0

            self.log(f"[get_csw_result] Beginnen met gepagineerd ophalen van records. Aantal records per keer={page_size}", lvl=0)
            while True:
                try:
                    csw.getrecords2(startposition=start, maxrecords=page_size, esn="full")
                except Exception as e:
                    self.log(f"[get_csw_result] Kon geen records ophalen op startpositie={start}. Foutmelding: {e}")
                    break

                if not csw.records:
                    self.log(f"[get_csw_result] Geen records meer beschikbaar op startpositie={start}")
                    break

                self.log(f"csw results: {csw.results}")
                all_records.update(csw.records)

                if len(csw.records) < page_size:
                    break

                start += page_size

            self.log(f"[get_csw_result] Ophalen records afgerond. Totaal={len(all_records)}", lvl=0)


            csw_list = []
            try:
                for _, record in all_records.items():
                    try:
                        csw_record = self._format_csw_layer(record, csw_name)
                        if len(csw_record) > 0:
                            csw_list.extend(csw_record)
                    except Exception as e:
                        self.log(f"[get_csw_result] Kon record niet verwerken: {record}. Foutmelding: {e}")
                        continue

            except Exception as e:
                self.log(f"[get_csw_result] Verwerken van lijst met records is mislukt. Foutmelding: {e}")


            self.log(f"[get_csw_result] Formatting records naar een CSW lijst afgerond. Totaal={len(csw_list)}", lvl=0)
            if len(csw_list) == 0:
                self.log(f"[get_csw_result] CSW lijst was leeg voor URL: {csw_url}")
                continue
            
            # Save data to JSON
            self.save_json_file(csw_list, csw_name, os.path.join("layer_sources", "csw_result"))