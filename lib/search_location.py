#########################################################################################
####################  Search for locations for the zoom functionality ###################
#########################################################################################
import re
from enum import Enum
import json
import urllib.parse
from osgeo import ogr
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtCore import Qt, QTimer, QRegularExpression
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry, QgsProject, QgsRectangle, QgsWkbTypes
from qgis.PyQt.QtWidgets import QCompleter

from .constants import SERVICE_ENDPOINT
from .http_client import get_request_json


class Projection(Enum):
    def __str__(self):
        return str(self.value)

    EPSG_4326 = "EPSG:4326"
    EPSG_28992 = "EPSG:28992"

class LsType(Enum):
    adres = "adres"
    appartementsrecht = "appartementsrecht"
    buurt = "buurt"
    gemeente = "gemeente"
    hectometerpaal = "hectometerpaal"
    perceel = "perceel"
    postcode = "postcode"
    provincie = "provincie"
    weg = "weg"
    wijk = "wijk"
    waterschap = "waterschap"
    woonplaats = "woonplaats"

    def geom_type(self) -> QgsWkbTypes:
        geom_type_mapping = {
            "adres": QgsWkbTypes.Point,
            "appartementsrecht": QgsWkbTypes.MultiPoint,
            "buurt": QgsWkbTypes.MultiPolygon,
            "gemeente": QgsWkbTypes.MultiPolygon,
            "hectometerpaal": QgsWkbTypes.Point,
            "perceel": QgsWkbTypes.Polygon,
            "postcode": QgsWkbTypes.Point,
            "provincie": QgsWkbTypes.MultiPolygon,
            "weg": QgsWkbTypes.MultiLineString,
            "wijk": QgsWkbTypes.MultiPolygon,
            "waterschap": QgsWkbTypes.MultiPolygon,
            "woonplaats": QgsWkbTypes.MultiPolygon,
        }
        return geom_type_mapping[self.value]

class TypeFilter:
    # Default types requested, match default types of LS service, see:
    # https://github.com/PDOK/locatieserver/wiki/API-Locatieserver#31request-url
    default_types = [
        LsType.gemeente,
        LsType.woonplaats,
        LsType.weg,
        LsType.adres,
        LsType.postcode,
        LsType.waterschap,
    ]

    def __init__(self, filter_types: "list[LsType]"):
        self.types: "list[LsType]" = filter_types

    @classmethod  # cls==self for class methods see https://stackoverflow.com/a/4795306/1763690
    def new_with_default_values(cls):
        "Initialize TypeFilter with default values"
        return cls(cls.default_types)

    def add_type(self, type: LsType):
        self.types.append(type)

    def __str__(self):
        filter_types_str = list(map(lambda x: x.value, self.types))
        filter_types_str = " OR ".join(filter_types_str)
        return urllib.parse.quote(f"type:({filter_types_str})")

    def rev_geo_filter(self):
        filter_types_str = list(map(lambda x: f"type={x.value}", self.types))
        return "&".join(filter_types_str)


class SearchLocationManager:
    """
    Class to search and zoom to locations through a search bar.
    """
    def __init__(self, dlg, iface, log):
        
        assert dlg is not None, "StyleManager: dlg is None"
        assert log is not None, "StyleManager: log is None"

        self.dlg = dlg
        self.iface = iface
        self.log = log
        
        # Timer on the search bar
        self.timer_toolbar_search = QTimer()
        self.timer_toolbar_search.setSingleShot(True)
        self.timer_toolbar_search.setInterval(200)
        self.timer_toolbar_search.timeout.connect(self.toolbar_search_get_suggestions)

        # Search bars
        self.dlg.zoomLineEdit.textEdited.connect(
            lambda: self.timer_toolbar_search.start()
        )
        self.dlg.zoomButton.clicked.connect(lambda: self.zoom_button())

        self.proj_mapping = {
            Projection.EPSG_28992: "_rd",
            Projection.EPSG_4326: "_ll",
        }

        self.zoom_dict = {
            "adres": 794,
            "perceel": 794,
            "hectometer": 1587,
            "weg": 3175,
            "postcode": 6350,
            "woonplaats": 25398,
            "gemeente": 50797,
            "provincie": 812750,
        }


    def zoom_button(self):
        search_text = self.dlg.zoomLineEdit.text()
        result = self.suggest_query(search_text, self.create_type_filter())[0]["weergavenaam"]
        self.dlg.zoomLineEdit.setText(result)
        suggest_text = self.dlg.zoomLineEdit.text()
        self.on_toolbar_suggest_activated(suggest_text)


    def create_type_filter(self):
        """
        This creates a TypeFilter (Filter Query, see https://github.com/PDOK/locatieserver/wiki/Zoekvoorbeelden-Locatieserver) based on the checkboxes in the dialog. Defaults to []
        """
        
        self.fq_checkboxes = {
            LsType.gemeente,
            LsType.woonplaats,
            LsType.weg,
            LsType.postcode,
            LsType.adres,
            LsType.perceel,
            LsType.hectometerpaal,
            LsType.waterschap,
        }
        filter = TypeFilter([])
        for key in self.fq_checkboxes:
            filter.add_type(key)
        return filter


    def url_encode_query_string(self, query_string):
        return urllib.parse.quote(query_string)

    def suggest_query(
        self,
        query,
        type_filter=TypeFilter.new_with_default_values(),
        rows=10,
    ) -> "list[dict]":
        """

        Returns list of dict with fields: type, weergavenaam, id score
        For example:
            {
                "type": "gemeente",
                "weergavenaam": "Gemeente Amsterdam",
                "id": "gem-0b2a8b92856b27f86fbd67ab35808ebf",
                "score": 19.91312
            }
        Raises PdokServicesNetworkException when request fails
        """
        if len(type_filter.types) == 0:
            return []
        # TODO: add fields filter, with fl=id,geometrie_ll/rd or *
        query = self.url_encode_query_string(query)
        query_string = f"q={query}&rows={rows}&fq={type_filter}"
        url = f"{SERVICE_ENDPOINT}/suggest?{query_string}"
        content_obj = get_request_json(url)
        result = content_obj["response"]["docs"]
        return result


    def toolbar_search_get_suggestions(self):
        def create_model(_suggestions):
            model = QStandardItemModel()
            for s in _suggestions:
                key = s["weergavenaam"]
                it = QStandardItem(key)
                it.setData(s, Qt.ItemDataRole.UserRole)
                model.appendRow(it)
            return model
        search_text = self.dlg.zoomLineEdit.text()
        if len(search_text) <= 1:
            self.dlg.zoomLineEdit.setCompleter(None)
            return
        results = self.suggest_query(search_text, self.create_type_filter())
        # https://stackoverflow.com/questions/5129211/qcompleter-custom-completion-rules
        self.completer = QCompleter()
        self.model = create_model(results)
        self.completer.setModel(self.model)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.dlg.zoomLineEdit.setCompleter(self.completer)
        self.dlg.zoomLineEdit.show()
        self.completer.complete()
        self.completer.activated.connect(self.on_toolbar_suggest_activated)
        return

    def on_toolbar_suggest_activated(self, suggest_text):
        object = None
        
        items = self.model.findItems(suggest_text) # get a list of suggested items
        if len(items) == 0:  # check should not be necessary
            return
        item = items[0] # take selected item
        data = item.data(Qt.ItemDataRole.UserRole)
        lookup_id = data["id"] # eg. gem-0b2a8b92856b27f86fbd67ab35808ebf
        try:
            object = self.lookup_object(lookup_id, Projection.EPSG_28992)
        except Exception as e:
            self.log(f"Failed to lookup an object in the search and zoom function. Error message: {e}")

        if object is None:
            return
        self.zoom_to_result(object)


    def lookup_object(self, object_id: str, proj: Projection) -> dict:
        """
        Raises PdokServicesNetworkException when request fails
        """
        # TODO: add fields filter, with fl=id,geometrie_ll/rd or fl=*
        def process_geom_fields(_result_item):
            geom_suffix = self.proj_mapping[proj]
            geom_name = f"geometrie{geom_suffix}"
            geoms = {}
            if geom_name in _result_item:
                geoms.update(
                    {"wkt_geom": _result_item[geom_name]}
                )  # Note: dict.update modifies IN place (no return value), see https://peps.python.org/pep-0584/
            centroid_name = f"centroide{geom_suffix}"
            geoms.update(
                {"wkt_centroid": _result_item[centroid_name]}
            )
            for geom_type in ["centroide", "geometrie"]:
                for p in Projection:
                    geom_suffix = self.proj_mapping[p]
                    geom_name = f"{geom_type}{geom_suffix}"
                    _result_item.pop(geom_name, None)
            _result_item.update(geoms) 
            return _result_item
    
        object_id = self.url_encode_query_string(object_id)
        query_string = f"id={object_id}&fl=*"  # return all fields with fl=*
        url = f"{SERVICE_ENDPOINT}/lookup?{query_string}"
        content_obj = get_request_json(url)
        if content_obj["response"]["numFound"] != 1:
            return None
        result = content_obj["response"]["docs"][0]
        filter_result = process_geom_fields(result)
        return filter_result


    def zoom_to_result(self, data):
        # just always transform from 28992 to mapcanvas crs
        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        crs28992 = QgsCoordinateReferenceSystem.fromEpsgId(28992)
        crsTransform = QgsCoordinateTransform(crs28992, crs, QgsProject.instance())

        adrestekst = "{} - {}".format(data["type"], data["weergavenaam"])
        adrestekst_lower = adrestekst.lower()

        z = 1587
        for z_type in self.zoom_dict.keys():
            if adrestekst_lower.startswith(
                z_type
            ):  # maybe find better way to infer return type?
                z = self.zoom_dict[z_type]

        geom = QgsGeometry.fromWkt(data["wkt_geom"])
        geom.transform(crsTransform)
        geom_type = geom.type()

        geom_type_dict = {
            QgsWkbTypes.PointGeometry: "point",
            QgsWkbTypes.LineGeometry: "linestring",
            QgsWkbTypes.PolygonGeometry: "polygon",
        }
        if geom_type not in geom_type_dict:
            self.info(
                f"unexpected geomtype return by ls: {geom_type}"
            )  # TODO: better error handling
            return

        geom_bbox = geom.boundingBox()
        rect = QgsRectangle(geom_bbox)
        rect.scale(1.2)
        self.iface.mapCanvas().zoomToFeatureExtent(rect)
        # for point features it is required to zoom to predefined zoomlevel depending on return type
        if re.match(r"^POINT", data["wkt_geom"]):
            self.iface.mapCanvas().zoomScale(z)
        self.iface.mapCanvas().refresh()


