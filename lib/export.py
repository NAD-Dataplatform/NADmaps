import os

from qgis.core import (
    QgsProject, QgsLayout, QgsLayoutExporter, QgsLayoutItemMap,
    QgsLayoutItemLegend, QgsLayoutItemScaleBar, QgsLayoutItemPicture,
    QgsLayoutSize, QgsLayoutPoint, QgsUnitTypes
)
from PyQt5.QtCore import QSizeF
from PyQt5.QtGui import QColor

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
        if settings.get("include_north"):
            pass # skip for now

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
