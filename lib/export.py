import os
from .constants import PLACEMENT_OPTIONS

from qgis.core import (
    QgsProject, QgsLayout, QgsLayoutExporter, QgsLayoutItemMap,
    QgsLayoutItemLegend, QgsLayoutItemScaleBar, QgsLayoutItemPicture,
    QgsLayoutSize, QgsLayoutPoint, QgsUnitTypes, QgsLayoutItemLabel, QgsLegendSettings
)
from PyQt5.QtCore import QSizeF
from PyQt5.QtGui import QColor, QFont

QgsLegendSettings().setWrapChar(' ')

class ExportManager:
    def __init__(self, dlg, log, project=None):
        self.project = project or QgsProject.instance()

        assert dlg is not None, "ExportManager: dlg is None"
        assert log is not None, "ExportManager: log is None"

        self.dlg = dlg
        self.log = log

    def build_layout(self, settings: dict) -> QgsLayout:
        layout = QgsLayout(self.project)
        layout.initializeDefaults()
       
        # Get dpi
        self.dpi = settings.get('dpi')

        # Get paper size
        paper_size = self._get_page_size(settings.get("paper_format", "A4 staand"))
        page = layout.pageCollection().pages()[0]
        page.setPageSize(QgsLayoutSize(paper_size.width(), paper_size.height(), QgsUnitTypes.LayoutMillimeters))
        self.log(f"paper_size: {paper_size}")

        # Calculate the map item size
        map_item_width = round(paper_size.width() * 0.9)
        map_item_height = round(paper_size.height() * 0.9)
        self.log("# Calculate the map item size")
        self.log(f"map_item_width: {map_item_width}")
        self.log(f"map_item_height: {map_item_height}")

        # Create map item based on current canvas
        map_item = QgsLayoutItemMap(layout)
        map_item.setFrameEnabled(False)    
            # Set size
        map_item.attemptResize(QgsLayoutSize(map_item_width, map_item_height, QgsUnitTypes.LayoutMillimeters))
        self.log(f"attemptRisize. width: {map_item_width} height: {map_item_height}")
            # Position the map item centered on the page
        x_offset = round((paper_size.width() - map_item_width) / 2)
        y_offset = round((paper_size.height() - map_item_height) / 2)
        map_item.attemptMove(QgsLayoutPoint(x_offset, y_offset, QgsUnitTypes.LayoutMillimeters))

        # Use the provided extent (from the settings_dict)
        canvas = settings.get("canvas", None)
        if not canvas:
            raise ValueError("Canvas not provided in settings.")
        
        # Set the extent, scale, and rotation from the canvas
            #TODO Onderstaande 2 regels geven controle over schaal en vlak maar hierdoor wordt bij staande afdruk een deel van de pagina leeg gelaten
        # map_item.setExtent(canvas.extent())
        # map_item.setScale(canvas.scale())
            #TODO Met deze regel wordt de pagina netjes gevuld maar heb je geen controle over de schaal
        map_item.zoomToExtent(canvas.extent())
        map_item.setMapRotation(canvas.rotation())

        layout.addLayoutItem(map_item)

        #TODO get size (widht and height can be different)
        #Size
        north_item_width = round(map_item_width * 0.1) #round(paper_size.height() * 0.03)

        location = self.dlg.comboBox_NoordpijlPlacement.currentText()
        self.log(f"location: {location}")
        self.log(f"Len location {len(location)}")

        # Get position
        x_north, y_north = self._get_position_based_on_location(
            location=location,
            x_offset=x_offset,
            y_offset=y_offset,
            map_item_width=map_item_width,
            map_item_height=map_item_height,
            item_width=north_item_width*0.6,
            item_height=north_item_width,
            margin=10
        )

        self.log(f"x north {x_north}")
        self.log(f"y_norht {y_north}")

        # Add north arrow if needed
        #TODO 1: Positie van pijl op afdruk op basis van instelling (nu altijd rechtsboven)
        if settings.get("include_north"):
            self._add_north_arrow(layout, x=x_north, y=y_north, size_mm=north_item_width) # Hier ook positie en grootte meegeven
            
        # Add title if needed
        if settings.get("include_title"):
            title = settings.get("title", "")
            if title:
                font_size = settings.get("title_font_size", 20)
                self._add_title(layout, title, font_size)

        # Add legend if needed
        if settings.get("include_legend"):
            self._add_legend(layout, x_offset=x_offset, y_offset=y_offset, map_item=map_item)

        # Add scalebar if needed
        scale_bar_margin = 0 # TODO
        if settings.get("include_scale"):
            self._add_scale_bar(layout, x_offset=x_offset, x_margin=scale_bar_margin, y_offset=y_offset,map_item_width=map_item_width, map_item_height=map_item_height, map_item=map_item)

        return layout
    
    def _get_position_based_on_location(self, location, x_offset, y_offset, map_item_width, map_item_height, item_width, item_height, margin=0):
        if location not in PLACEMENT_OPTIONS:
            raise ValueError(f"location not in PLACEMENT_OPTIONS: {PLACEMENT_OPTIONS}")
        
        if location == "Linksonder":
            x = x_offset + margin
            y = y_offset + map_item_height - margin - item_height

        if location == "Linksboven":
            x = x_offset + margin
            y = y_offset + margin
            
        if location == "Rechtsonder":
            x = x_offset + map_item_width - margin - item_width
            y = y_offset + map_item_height - margin - item_height

        if location == "Rechtsboven":
            x = x_offset + map_item_width - margin - item_width
            y = y_offset + margin

        return x, y

    def _add_title(self, layout, title_text, font_size=20):
        title = QgsLayoutItemLabel(layout)
        title.setText(title_text)
        title.setFont(QFont("Arial", font_size)) #TODO: Python deprecation warning

        #Fix 'setFont() is deprecated' > use textFormat()
            #TODO Met onderstaande code lukt het niet om de fontsize aan te passen
        # fmt = title.textFormat()
        # font = QFont("Arial", font_size)
        # self.log(f"font size: {font_size}")
        # fmt.setFont(font)
        # title.setTextFormat(fmt)
        # title.adjustSizeToText() #Take font_size in account
        # title.refresh() #Just to be sure

        # Center at top of page
        page = layout.pageCollection().pages()[0]
        x_center = page.pageSize().width() / 2
        title.attemptMove(QgsLayoutPoint(x_center, 10, QgsUnitTypes.LayoutMillimeters))

        layout.addLayoutItem(title)

    def _add_north_arrow(self, layout, x, y, size_mm):       
        # Path to SVG file relative to lib folder
        base_dir = os.path.dirname(__file__)  # = path to 'lib/'
        svg_path = os.path.abspath(os.path.join(base_dir, "..", "resources", "north-arrow.svg"))

        # Create arrow
        north_arrow = QgsLayoutItemPicture(layout)
        north_arrow.setPicturePath(svg_path)
        north_arrow.setSvgFillColor(QColor(0, 0, 0)) # black
        north_arrow.setSvgStrokeColor(QColor(255, 255, 255)) # White
        # Shouldn't be necessary
        north_arrow.refreshPicture() # Fix cache
        north_arrow.update() # Fix cache

        # Set size (square)
        north_arrow.attemptResize(QgsLayoutSize(size_mm, size_mm, QgsUnitTypes.LayoutMillimeters))

        # Set position
        north_arrow.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
        # self.log(f"x: {x_offset + map_item_width - north_margin}")
        # self.log(f"y: {y_offset + north_margin}")
        # self.log(f"Combobox text: {self.dlg.comboBox_NoordpijlPlacement.currentText()}")
        #TODO Instellen op basis van papierformaat en keuze van de gebruiker
       
        # Rotate according to orientation
        rotation = layout.referenceMap().mapRotation()
        north_arrow.setRotation(-rotation)  # to compensate
        
        # Add to layout
        layout.addLayoutItem(north_arrow)

    def _add_legend(self, layout, x_offset, y_offset, map_item):

        # TODO loop over all layers, wrap name  
        layers = self.project.mapLayers()
        max_length = 25

        self.mapping_dict = {}

        if not layers:
             self.log("Geen lagen gevonden in het project!", 0)
        else:      
             for layer in layers.values():
                 old_name = layer.name()
                 if len(old_name) > max_length:
                     new_name = old_name[:max_length] + "…"
                 else:
                     new_name = old_name
                 layer.setName(new_name)
                # store in dict
                 self.mapping_dict[new_name] = old_name

        self.log(f"mapping_dict {self.mapping_dict}")

        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item)
        legend.attemptResize(QgsLayoutSize(50, 50, QgsUnitTypes.LayoutMillimeters))
        legend.attemptMove(QgsLayoutPoint(x_offset, y_offset, QgsUnitTypes.LayoutMillimeters)) 
        legend.setTitle("Legenda")
        legend.setBackgroundColor(QColor(255, 255, 255, 150))  # White with 60% transparency
        layout.addLayoutItem(legend)

    def _wrap_text(text, max_length):
        return '\n'.join(text[i:i+max_length] for i in range(0, len(text), max_length))


    def _add_scale_bar(self, layout, x_offset, x_margin, y_offset,map_item_width, map_item_height, map_item):
        self.log(f"_add_scale_bar x_margin: {x_margin}")
        scale_bar = QgsLayoutItemScaleBar(layout)
        scale_bar.setStyle('Single Box')
        scale_bar.setLinkedMap(map_item)
        scale_bar.applyDefaultSize() #1/5 of map item width
        scale_bar.attemptMove(
            QgsLayoutPoint(x_offset + map_item_width - x_margin, y_offset + map_item_height - 20, QgsUnitTypes.LayoutMillimeters)
        ) # Position it at the bottom right corner of the map item
        # self.log(f"x_position: {x_offset + map_item_width - 50} y_position: {y_offset + map_item_height - 20}")
        # self.log(f"Scale bar height (func): {scale_bar.height()}")
        layout.addLayoutItem(scale_bar)
    
    def _get_page_size(self, format_string: str) -> QSizeF:
        parts = format_string.lower().split()
        size_lookup = {
            "a4": QSizeF(210, 297),
            "a3": QSizeF(297, 420),
            "a0": QSizeF(841, 1189)
        }

        size = size_lookup.get(parts[0], QSizeF(210, 297))
        if len(parts) > 1 and parts[1] == "liggend":
            size.transpose()

        return size

    def export(self, layout: QgsLayout, filepath: str) -> bool:
        exporter = QgsLayoutExporter(layout)

        export_settings_img = QgsLayoutExporter.ImageExportSettings()
        export_settings_img.dpi = self.dpi
        self.log(f"dpi: {self.dpi}")
     
        export_settings_pdf = QgsLayoutExporter.PdfExportSettings()
        export_settings_pdf.dpi = self.dpi

        filetype = os.path.splitext(filepath)[1][1:]  # Get the file extension without the dot
        if filetype.upper() == "PNG":
            result = exporter.exportToImage(filepath, export_settings_img)
        elif filetype.upper() == "PDF":
            result = exporter.exportToPdf(filepath, export_settings_pdf)
        else:
            raise ValueError("Unsupported file type")
        
        self._set_layer_names_to_original()

        return result == QgsLayoutExporter.Success
    

    def _set_layer_names_to_original(self):
        layers = self.project.mapLayers()
        for layer in layers.values():
            old_name = self.mapping_dict.get(layer.name())
            self.log(f"old_name = {old_name}")
            layer.setName(old_name)