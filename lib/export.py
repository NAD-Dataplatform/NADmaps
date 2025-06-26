import os

from qgis.core import (
    QgsProject, QgsLayout, QgsLayoutExporter, QgsLayoutItemMap,
    QgsLayoutItemLegend, QgsLayoutItemScaleBar, QgsLayoutItemPicture,
    QgsLayoutSize, QgsLayoutPoint, QgsUnitTypes, QgsLayoutItemLabel
)
from PyQt5.QtCore import QSizeF
from PyQt5.QtGui import QColor, QFont

class ExportManager:
    def __init__(self, project=None):
        self.project = project or QgsProject.instance()

    def build_layout(self, settings: dict) -> QgsLayout:
        layout = QgsLayout(self.project)
        layout.initializeDefaults()

        # Get paper size
        paper_size = self._get_page_size(settings.get("paper_format", "A4 staand"))
        page = layout.pageCollection().pages()[0]
        page.setPageSize(QgsLayoutSize(paper_size.width(), paper_size.height(), QgsUnitTypes.LayoutMillimeters))

        # Calculate the map item size
        map_item_width = paper_size.width() * 0.9
        map_item_height = paper_size.height() * 0.9

        # Create map item based on current canvas
        map_item = QgsLayoutItemMap(layout)
        map_item.setRect(paper_size.width() * 0.1, paper_size.height() * 0.1,
                         map_item_width, map_item_height)
        map_item.setFrameEnabled(False)

        # Position the map item centered on the page
        x_offset = (paper_size.width() - map_item_width) / 2
        y_offset = (paper_size.height() - map_item_height) / 2
        map_item.attemptMove(QgsLayoutPoint(x_offset, y_offset, QgsUnitTypes.LayoutMillimeters))

        # Use the provided extent (from the settings_dict)
        canvas = settings.get("canvas", None)
        if not canvas:
            raise ValueError("Canvas not provided in settings.")
        
        # Set the extent, scale, and rotation from the canvas
        map_item.setExtent(canvas.extent())
        map_item.setScale(canvas.scale())
        map_item.setMapRotation(canvas.rotation())

        layout.addLayoutItem(map_item)

        # Add north arrow if needed
        #TODO 1: Positie van pijl op afdruk op basis van instelling (nu altijd linksboven)
        if settings.get("include_north"):
            self._add_north_arrow(layout, x=20, y=20, size_mm=20)

        # Add title if needed
        if settings.get("include_title"):
            title = settings.get("title", "")
            if title:
                font_size = settings.get("title_font_size", 20)
                self._add_title(layout, title, font_size)

        # Add legend if needed
        if settings.get("include_legend"):
            legend = QgsLayoutItemLegend(layout)
            legend.setLinkedMap(map_item)
            legend.attemptResize(QgsLayoutSize(50, 50, QgsUnitTypes.LayoutMillimeters))
            legend.attemptMove(QgsLayoutPoint(x_offset, y_offset, QgsUnitTypes.LayoutMillimeters)) 
            legend.setTitle("Legenda")
            legend.setBackgroundColor(QColor(255, 255, 255, 150))  # White with 60% transparency
            layout.addLayoutItem(legend)

        if settings.get("include_scale"):
            scale_bar = QgsLayoutItemScaleBar(layout)
            scale_bar.setStyle('Single Box')
            scale_bar.setLinkedMap(map_item)
            scale_bar.applyDefaultSize()
            scale_bar.attemptMove(
                QgsLayoutPoint(x_offset + map_item_width - 50, y_offset + map_item_height - 20, QgsUnitTypes.LayoutMillimeters)
            ) # Position it at the bottom right corner of the map item
            layout.addLayoutItem(scale_bar)

        return layout

    def _add_title(self, layout, title_text, font_size=20):
        title = QgsLayoutItemLabel(layout)
        title.setText(title_text)

        # Fix 'setFont() deprecated' > use textFormat()
        fmt = title.textFormat()
        font = QFont("Arial", font_size)
        fmt.setFont(font)
        title.setTextFormat(fmt)

        # Center bovenaan de pagina
        page = layout.pageCollection().pages()[0]
        x = page.pageSize().width() / 2
        title.attemptMove(QgsLayoutPoint(x, 10, QgsUnitTypes.LayoutMillimeters))

        layout.addLayoutItem(title)

    def _add_north_arrow(self, layout, x=10, y=10, size_mm=20):

        # Path to SVG file relative to lib folder
        base_dir = os.path.dirname(__file__)  # = path to 'lib/'
        svg_path = os.path.abspath(os.path.join(base_dir, "..", "resources", "north-arrow.svg"))

        # Create arrow
        north_arrow = QgsLayoutItemPicture(layout)
        north_arrow.setPicturePath(svg_path)
        north_arrow.setSvgFillColor(QColor(0, 0, 0))
        north_arrow.setSvgStrokeColor(QColor(255, 255, 255))
        # Shouldn't be necessary
        north_arrow.refreshPicture() # Fix cache
        north_arrow.update() # Fix cache

        # Set size (square)
        north_arrow.attemptResize(QgsLayoutSize(size_mm, size_mm, QgsUnitTypes.LayoutMillimeters))

        # Set position
        north_arrow.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
       
        # Rotate according to orientation
        rotation = layout.referenceMap().mapRotation()
        north_arrow.setRotation(-rotation)  # to compensate
        
        # Add to layout
        layout.addLayoutItem(north_arrow)

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

        filetype = os.path.splitext(filepath)[1][1:]  # Get the file extension without the dot
        if filetype.upper() == "PNG":
            result = exporter.exportToImage(filepath, QgsLayoutExporter.ImageExportSettings())
        elif filetype.upper() == "PDF":
            result = exporter.exportToPdf(filepath, QgsLayoutExporter.PdfExportSettings())
        else:
            raise ValueError("Unsupported file type")

        return result == QgsLayoutExporter.Success
