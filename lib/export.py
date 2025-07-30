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

        # Calculate the map item size
        map_item_width = round(paper_size.width() * 0.9)
        map_item_height = round(paper_size.height() * 0.9)

        # Create map item based on current canvas
        map_item = QgsLayoutItemMap(layout)
        map_item.setFrameEnabled(False)    
            # Set size
        map_item.attemptResize(QgsLayoutSize(map_item_width, map_item_height, QgsUnitTypes.LayoutMillimeters))
            # Position the map item centered on the page
        x_offset = round((paper_size.width() - map_item_width) / 2)
        y_offset = round((paper_size.height() - map_item_height) / 2)
        map_item.attemptMove(QgsLayoutPoint(x_offset, y_offset, QgsUnitTypes.LayoutMillimeters))

        # Use the provided extent (from the settings_dict)
        canvas = settings.get("canvas", None)
        if not canvas:
            raise ValueError("Canvas not provided in settings.")
        
        map_item.zoomToExtent(canvas.extent())
        map_item.setMapRotation(canvas.rotation())

        layout.addLayoutItem(map_item)

        # Element parameters

        # North arrow
        north_item_width = round(map_item_width * 0.1)
        north_placement = self.dlg.comboBox_NoordpijlPlacement.currentText()
        # Legend
        legend_placement = self.dlg.comboBox_LegendaPlacement.currentText()
        # Scale bar
        scale_bar_placement = self.dlg.comboBox_SchaalbalkPlacement.currentText()       

        # Add north arrow if needed
        if settings.get("include_north"):
        # Get north position
            x_north, y_north, reference_point_north = self._get_position_based_on_placement(
                placement=north_placement,
                x_offset=x_offset,
                y_offset=y_offset,
                map_item_width=map_item_width,
                map_item_height=map_item_height,
                margin=10
            )
            # Create north
            self._add_north_arrow(
                layout,
                x=x_north,
                y=y_north,
                reference_point=reference_point_north,
                size_mm=north_item_width
            )
            
        # Add title if needed
        if settings.get("include_title"):
            title = settings.get("title", "")
            if title:
                font_size = settings.get("title_font_size", 20)
                self._add_title(layout, title, font_size)

        # Add legend if needed
        if settings.get("include_legend"):
            # Get correct position
            x_legend, y_legend, reference_point_legend = self._get_position_based_on_placement(
                placement=legend_placement,
                x_offset=x_offset,
                y_offset=y_offset,
                map_item_width=map_item_width,
                map_item_height=map_item_height,
                margin=0 # Place legend in corner of the map
            )
            # Create legend
            self._add_legend(
                layout,
                x=x_legend,
                y=y_legend,
                reference_point=reference_point_legend,
                map_item=map_item
            )

        # Add scalebar if needed
        if settings.get("include_scale"):
        # Get scalebar position
            x_scale_bar, y_scale_bar, reference_point_scale_bar = self._get_position_based_on_placement(
                placement=scale_bar_placement,
                x_offset=x_offset,
                y_offset=y_offset,
                map_item_width=map_item_width,
                map_item_height=map_item_height,
                margin=10
            )
            # Create scale bar
            self._add_scale_bar(
                layout, 
                x=x_scale_bar,
                y=y_scale_bar,
                reference_point=reference_point_scale_bar,
                map_item=map_item
            )

        return layout
    
    def _get_position_based_on_placement(self, placement, x_offset, y_offset, map_item_width, map_item_height, margin=0):
        if placement not in PLACEMENT_OPTIONS:
            raise ValueError(f"location not in PLACEMENT_OPTIONS: {PLACEMENT_OPTIONS}")
        
        if placement == "Linksboven":
            x = x_offset + margin
            y = y_offset + margin
            reference_point = 0

        if placement == "Rechtsboven":
            x = x_offset + map_item_width - margin
            y = y_offset + margin
            reference_point = 2

        if placement == "Linksonder":
            x = x_offset + margin
            y = y_offset + map_item_height - margin
            reference_point = 6
            
        if placement == "Rechtsonder":
            x = x_offset + map_item_width - margin
            y = y_offset + map_item_height - margin
            reference_point = 8

        return x, y, reference_point

    def _add_title(self, layout, title_text, font_size=20):
        title = QgsLayoutItemLabel(layout)
        title.setText(title_text)
        title.setFont(QFont("Arial", font_size)) #TODO: Python deprecation warning

        # Center at top of page
        page = layout.pageCollection().pages()[0]
        x_center = page.pageSize().width() / 2
        title.attemptMove(QgsLayoutPoint(x_center, 10, QgsUnitTypes.LayoutMillimeters))

        layout.addLayoutItem(title)

    def _add_north_arrow(self, layout, x, y, reference_point, size_mm):       
        # Path to SVG file relative to lib folder
        base_dir = os.path.dirname(__file__)  # = path to 'lib/'
        svg_path = os.path.abspath(os.path.join(base_dir, "..", "resources", "north-arrow.svg"))

        # Create arrow
        north_arrow = QgsLayoutItemPicture(layout)
        north_arrow.setPicturePath(svg_path)
        north_arrow.setSvgFillColor(QColor(0, 0, 0)) # black
        north_arrow.setSvgStrokeColor(QColor(255, 255, 255)) # White
        north_arrow.refreshPicture()
        north_arrow.update()

        # Set size (square)
        north_arrow.attemptResize(QgsLayoutSize(size_mm, size_mm, QgsUnitTypes.LayoutMillimeters))

        # Set position
        north_arrow.setReferencePoint(reference_point)
        north_arrow.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters), True)
       
        # Rotate according to orientation
        rotation = layout.referenceMap().mapRotation()
        north_arrow.setRotation(-rotation)  # to compensate
        
        # Add to layout
        layout.addLayoutItem(north_arrow)

    def _add_legend(self, layout, x, y, reference_point, map_item):

        # Wrap layer name if too long
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
        
        # Create legend
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item)
        legend.setLegendFilterByMapEnabled(True)
        legend.setAutoUpdateModel(True)
        legend.attemptResize(QgsLayoutSize(50, 50, QgsUnitTypes.LayoutMillimeters))
        legend.setReferencePoint(reference_point)
        legend.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters), True)
        legend.setTitle("Legenda")
        legend.setBackgroundColor(QColor(255, 255, 255, 150))  # White with 60% transparency
        layout.addLayoutItem(legend)

    def _add_scale_bar(self, layout, x, y, reference_point, map_item):
        scale_bar = QgsLayoutItemScaleBar(layout)
        scale_bar.setStyle('Single Box')
        scale_bar.setLinkedMap(map_item)
        scale_bar.applyDefaultSize() #1/5 of map item width
        scale_bar.setReferencePoint(reference_point)
        scale_bar.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters), True)
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
     
        export_settings_pdf = QgsLayoutExporter.PdfExportSettings()
        export_settings_pdf.dpi = self.dpi

        filetype = os.path.splitext(filepath)[1][1:]  # Get the file extension without the dot
        if filetype.upper() == "PNG":
            result = exporter.exportToImage(filepath, export_settings_img)
        elif filetype.upper() == "PDF":
            result = exporter.exportToPdf(filepath, export_settings_pdf)
        else:
            raise ValueError("Unsupported file type")
        
        #TODO: Only excecute if layer names are wrapped
        if self.dlg.checkBox_Legenda.isChecked():
            self._set_layer_names_to_original()

        return result == QgsLayoutExporter.Success
    

    def _set_layer_names_to_original(self):
        layers = self.project.mapLayers()
        for layer in layers.values():
            old_name = self.mapping_dict.get(layer.name())
            layer.setName(old_name)