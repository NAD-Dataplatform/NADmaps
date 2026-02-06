import os
import json
from owslib.csw import CatalogueServiceWeb

import ssl
import socket

def getPEMFile(url):

    hostname = 'www.python.org'
    context = ssl.create_default_context()

    with socket.create_connection((hostname, 443)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            return(ssock.version())
    #     s = ssl.Connection(ctx, s)
    #     s.set_connect_state()
    #     s.set_tlsext_host_name(str.encode(dst[0]))

    #     s.sendall(str.encode('HEAD / HTTP/1.0\n\n'))

    #     peerCertChain = s.get_peer_cert_chain()
    #     pemFile = ''

    #     for cert in peerCertChain:
    #         pemFile += crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8")

    # return pemFile

class IngestLayersManager:
    def __init__(self, dlg, iface, plugin_dir, log):
        assert dlg is not None, "LayerManager: dlg is None"
        assert iface is not None, "LayerManager: iface is None"
        assert plugin_dir is not None, "LayerManager: plugin_dir is None"
        assert log is not None, "LayerManager: log is None"

        self.dlg = dlg
        self.iface = iface
        self.plugin_dir = plugin_dir
        self.log = log

    def get_layer_list(self):
        url = "www.nationaalgeoregister.nl"
        result = getPEMFile(url)
        self.log(f"cert_str: {result}")
        cert = ssl.get_server_certificate((url, 443))
        self.log(f"cert_str: {cert}")

        # csw_url = "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw"
        csw_urls = [
            "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw",
            "http://nationaalgeoregister.nl/geonetwork/srv/dut/inspire",
            "https://opendata.zuid-holland.nl/geonetwork/srv/dut/csw",
        ]

        # https://qgis.org/pyqgis/3.44/core/QgsAuthConfigurationStorage.html#qgis.core.QgsAuthConfigurationStorage.storeCertIdentity # opslaan van een PEM bestand in QGIS

        for csw_url in csw_urls:
            self.log(f"[get_layer_list] Connecting to {csw_url}")
            try:
                csw = CatalogueServiceWeb(csw_url, version="2.0.2", timeout=60)
            except Exception as e:
                self.log(f"[get_layer_list] Failed to connect: {e}")
                return

            page_size = 50
            all_records = {}
            start = 0

            self.log(
                f"[get_layer_list] Starting paged fetch with page_size={page_size}"
            )
            while True:
                try:
                    csw.getrecords2(
                        startposition=start, maxrecords=page_size, esn="full"
                    )
                except Exception as e:
                    self.log(
                        f"[get_layer_list] Failed to fetch records at start={start}: {e}"
                    )
                    break

                if not csw.records:
                    self.log(f"[get_layer_list] No more records at start={start}")
                    break

                self.log(
                    f"[get_layer_list] Retrieved {len(csw.records)} records (start={start})"
                )

                all_records.update(csw.records)

                # stop when fewer results than requested
                if len(csw.records) < page_size:
                    break

                # break  # TODO temp break for now
                start += page_size

            self.log(
                f"[get_layer_list] Finished. Total records fetched: {len(all_records)}"
            )

            # Save metadata to JSON
            domain_part = csw_url.split("https://")[1].split(".nl")[
                0
            ]  # Extract the part between 'https://' and '.nl' for filename
            path = os.path.join(
                self.plugin_dir,
                "resources",
                "layers",
                "meta",
                "raw",
                f"{domain_part}.json",
            )
            try:
                serializable = {
                    getattr(r, "title", ""): {
                        "title": getattr(r, "title", ""),
                        "abstract": getattr(r, "abstract", ""),
                        "uris": getattr(r, "uris", []),
                    }
                    for _, r in all_records.items()
                    if getattr(r, "uris", [])
                    and any(
                        "request=GetCapabilities" in uri.get("url", "")
                        for uri in getattr(r, "uris", [])
                    )
                    # only add records with URIs (not empty list) and GetCapabilities in any of the URL values
                    # TODO Siebrand check if you want this filtering here for the raw export
                }

                with open(path, encoding="utf-8", mode="w") as f:
                    json.dump(serializable, f, indent=2)
                self.log(f"[get_layer_list] Saved {len(all_records)} records to {path}")
            except Exception as e:
                self.log(f"[get_layer_list] Failed to save records: {e}")