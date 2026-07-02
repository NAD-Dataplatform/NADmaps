#########################################################################################
##############################  Export canvas as image or pdf ###########################
#########################################################################################

import os
from .constants import (
    PLACEMENT_OPTIONS, 
    PRINT_QUALITY_OPTIONS,
    PAPER_OPTIONS,
    FORMAT_OPTIONS,
)

from qgis.core import (
    QgsProject, QgsLayout, QgsLayoutExporter, QgsLayoutItemMap,
    QgsLayoutItemLegend, QgsLayoutItemScaleBar, QgsLayoutItemPicture,
    QgsLayoutSize, QgsLayoutPoint, QgsUnitTypes, QgsLayoutItemLabel, 
    QgsLegendSettings, QgsTextFormat
)
from qgis.PyQt.QtCore import Qt, QSizeF
from PyQt5.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import QMessageBox


class ExportManager:
    def __init__(self, dlg, iface, log):
        self.project = QgsProject.instance()

        if log is None: raise ValueError("ExportManager: log is None")
        self.log = log
        
        if dlg is None: self.log("ExportManager: dlg is None", level=2)
        if iface is None: self.log("ExportManager: iface is None", level=2)

        self.dlg = dlg
        self.iface = iface
        
        self.working_dir = None
        self.working_dir_available = False
        
        # Unknown what this does. TODO Check and document in the future
        QgsLegendSettings().setWrapChar(' ')
        
        # Interactions
        self.dlg.lineEdit_FileName.textChanged.connect(    self.check_map_name)
        self.dlg.checkBox_Noordpijl.stateChanged.connect(  self.set_noordpijl_placement_combobox )
        self.dlg.checkBox_Legenda.stateChanged.connect(    self.set_legenda_placement_combobox )
        self.dlg.checkBox_Schaalbalk.stateChanged.connect( self.set_schaalbalk_placement_combobox )
        self.dlg.checkBox_Titel.stateChanged.connect(      self.set_titel_line_edit )

        self.dlg.pushButton_ExporteerMap.clicked.connect(  self.export_map_button_pressed)

    def set_working_directory(self, path):
        """Set the working directory for the plugin"""
        if not path:
            return
        if not os.path.isdir(path):
            return
        
        self.working_dir_available = True
        self.working_dir = path

    def check_map_name(self):
        """
        If no filename is supplied, then exporting is not possible.
        """
        tooltip = "Geen bestandsnaam ingevuld of geen werkmap geselecteerd in het Instellingen-tabblad."
        enable = False

        map_name = self.dlg.lineEdit_FileName.text()
        if map_name and self.working_dir_available:
            enable = True
            tooltip = ""

        self.dlg.pushButton_ExporteerMap.setEnabled(enable)
        self.dlg.pushButton_ExporteerMap.setToolTip(tooltip)

    def init_export_comboboxes(self):
        """
        Initialize ui content in the export tab.
        """

        self.dlg.comboBox_PapierFormaat.clear()
        for item in PAPER_OPTIONS:
            self.dlg.comboBox_PapierFormaat.addItem(item)
        self.dlg.comboBox_PapierFormaat.setCurrentIndex(0)

        self.dlg.comboBox_BestandsFormaat.clear()
        for item in FORMAT_OPTIONS:
            self.dlg.comboBox_BestandsFormaat.addItem(item)
        self.dlg.comboBox_BestandsFormaat.setCurrentIndex(0)

        print_quality_options = list(PRINT_QUALITY_OPTIONS.keys())
        self.dlg.comboBox_PrintQuality.clear()
        for item in print_quality_options:
            self.dlg.comboBox_PrintQuality.addItem(item)

        self.dlg.comboBox_LegendaPlacement.clear()
        self.dlg.comboBox_SchaalbalkPlacement.clear()
        self.dlg.comboBox_NoordpijlPlacement.clear()
        for item in PLACEMENT_OPTIONS:
            self.dlg.comboBox_LegendaPlacement.addItem(item)
            self.dlg.comboBox_SchaalbalkPlacement.addItem(item)
            self.dlg.comboBox_NoordpijlPlacement.addItem(item)
        
        self.set_legenda_placement_combobox()
        self.set_schaalbalk_placement_combobox()
        self.set_noordpijl_placement_combobox()
        self.set_titel_line_edit()


    #############################################
    # track changes to export settings

    def set_noordpijl_placement_combobox(self):
        if self.dlg.checkBox_Noordpijl.isChecked():
            self.dlg.comboBox_NoordpijlPlacement.setVisible(True)
            self.dlg.comboBox_NoordpijlPlacement.setEnabled(True)
            self.dlg.comboBox_NoordpijlPlacement.setFocus()
            self.dlg.comboBox_NoordpijlPlacement.setCurrentText("Linksboven")
        else:
            self.dlg.comboBox_NoordpijlPlacement.setVisible(False)

    def set_legenda_placement_combobox(self):
        if self.dlg.checkBox_Legenda.isChecked():
            self.dlg.comboBox_LegendaPlacement.setVisible(True)
            self.dlg.comboBox_LegendaPlacement.setEnabled(True)
            self.dlg.comboBox_LegendaPlacement.setFocus()
            self.dlg.comboBox_LegendaPlacement.setCurrentText("Rechtsonder")
        else:
            self.dlg.comboBox_LegendaPlacement.setVisible(False)

    def set_schaalbalk_placement_combobox(self):
        if self.dlg.checkBox_Schaalbalk.isChecked():
            self.dlg.comboBox_SchaalbalkPlacement.setVisible(True)
            self.dlg.comboBox_SchaalbalkPlacement.setEnabled(True)
            self.dlg.comboBox_SchaalbalkPlacement.setFocus()
            self.dlg.comboBox_SchaalbalkPlacement.setCurrentText("Linksonder")
        else:
            self.dlg.comboBox_SchaalbalkPlacement.setVisible(False)

    def set_titel_line_edit(self):
        if self.dlg.checkBox_Titel.isChecked():
            self.dlg.lineEdit_Titel.setText(self.dlg.lineEdit_FileName.text())
            self.dlg.lineEdit_Titel.setVisible(True)
            self.dlg.spinBox_TitelFontSize.setVisible(True)
            self.dlg.lineEdit_Titel.setEnabled(True)
            self.dlg.lineEdit_Titel.setFocus()
        else:
            self.dlg.lineEdit_Titel.setVisible(False)
            self.dlg.spinBox_TitelFontSize.setVisible(False)


    #############################################
    # Build layout methods

    def _get_page_size(self, format_string: str) -> QSizeF:
        if not format_string:
            format_string = "A4 staand"

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
   
    def _add_title(self, layout, title_text, y_offset, font_size=20):
        title = QgsLayoutItemLabel(layout)
        title.setText(title_text)
        # title.setFont(QFont("Arial", font_size)) #TODO: Python deprecation warning -> setTextFormat since 3.24
        format = QgsTextFormat()
        format.setFont(QFont("Arial"))
        format.setSize(font_size)
        title.setTextFormat(format)
        title.setHAlign(Qt.AlignmentFlag.AlignHCenter)
        title.adjustSizeToText()  # To set reference point correctly

        title_width = title.sizeWithUnits().width()
        title_height = title.sizeWithUnits().height()
        title.setFixedSize(QgsLayoutSize(title_width+10, title_height, QgsUnitTypes.LayoutMillimeters))

        title.setBackgroundEnabled(True)
        title.setBackgroundColor(QColor(255, 255, 255, 230)) # White with 10% transparency

        # Center at top of page
        page = layout.pageCollection().pages()[0]
        x_center = page.pageSize().width() / 2
        
        title.setReferencePoint(1) # Top middle
        title.attemptMove(QgsLayoutPoint(x_center, y_offset, QgsUnitTypes.LayoutMillimeters), True)

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
        # Create legend
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item)
        legend.setLegendFilterByMapEnabled(True)
        legend.setAutoUpdateModel(True)
        legend.attemptResize(QgsLayoutSize(50, 50, QgsUnitTypes.LayoutMillimeters))
        legend.setReferencePoint(reference_point)
        legend.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters), True)
        legend.setTitle("Legenda")
        legend.setBackgroundColor(QColor(255, 255, 255, 230))  # White with 10% transparency
        layout.addLayoutItem(legend)

    def _add_scale_bar(self, layout, x, y, reference_point, map_item):
        scale_bar = QgsLayoutItemScaleBar(layout)
        scale_bar.setStyle('Single Box')
        scale_bar.setLinkedMap(map_item)
        scale_bar.applyDefaultSize() #1/5 of map item width
        scale_bar.setReferencePoint(reference_point)
        scale_bar.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters), True)
        layout.addLayoutItem(scale_bar)
    

    def _build_layout(self) -> QgsLayout:
        """
        Build a QgsLayout object using the input values
        
        :return: layout object with all QGIS export settings
        :rtype: QgsLayout
        """
        layout = QgsLayout(self.project)
        layout.initializeDefaults()
       
        # Get paper size
        paper_format = self.dlg.comboBox_PapierFormaat.currentText()
        paper_size = self._get_page_size(paper_format)
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

        # Use the provided extent
        canvas = self.iface.mapCanvas()
        if not canvas:
            raise ValueError("ExportManager: Canvas not available.")
        
        map_item.zoomToExtent(canvas.extent())
        map_item.setMapRotation(canvas.rotation())

        layout.addLayoutItem(map_item)

        # Add north arrow if needed
        include_north = self.dlg.checkBox_Noordpijl.isChecked(),
        if include_north:
            north_placement = self.dlg.comboBox_NoordpijlPlacement.currentText()
            north_item_width = round(map_item_width * 0.1)
            # Get north position
            x_north, y_north, reference_point_north = self._get_position_based_on_placement(
                placement=north_placement,
                x_offset=x_offset,
                y_offset=y_offset,
                map_item_width=map_item_width,
                map_item_height=map_item_height,
                margin=5
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
        include_title = self.dlg.checkBox_Titel.isChecked()
        if include_title:
            title = self.dlg.lineEdit_Titel.text()
            if title:
                title_font_size = self.dlg.spinBox_TitelFontSize.value()
                self._add_title(layout, title, y_offset, title_font_size)

        # Add legend if needed
        include_legend = self.dlg.checkBox_Legenda.isChecked()
        if include_legend:
            legend_placement = self.dlg.comboBox_LegendaPlacement.currentText()
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
        include_scale = self.dlg.checkBox_Schaalbalk.isChecked()
        if include_scale:
            scale_bar_placement = self.dlg.comboBox_SchaalbalkPlacement.currentText()
            # Get scalebar position
            x_scale_bar, y_scale_bar, reference_point_scale_bar = self._get_position_based_on_placement(
                placement=scale_bar_placement,
                x_offset=x_offset,
                y_offset=y_offset,
                map_item_width=map_item_width,
                map_item_height=map_item_height,
                margin=5
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
    

    #############################################
    # Main exporter methods

    def _check_layer_name_length(self, layers):
        """
        In case layer names are too long, we shorten them to less then 25 characters
        """
        if not layers:
            self.log("Geen lagen gevonden in het project!", 0)
            return

        # Wrap layer name if too long
        max_length = 25
        mapping_dict = {}
        
        for layer in layers.values():
            old_name = layer.name()
            if len(old_name) > max_length:
                new_name = old_name[:max_length] + "…"
                self.long_layer_names = True
            else:
                new_name = old_name
            layer.setName(new_name)
            # store in dict
            mapping_dict[new_name] = old_name

        return mapping_dict

    def _exporter(self, layout: QgsLayout, filepath: str) -> bool:
        """
        Docstring for _exporter
        
        :param layout: Snapshot of canvas layout
        :type layout: QgsLayout
        :param filepath: Description
        :type filepath: str
        :return: Description
        :rtype: bool
        """
        # Get dpi (quality)
        print_quality = self.dlg.comboBox_PrintQuality.currentText()
        dpi = PRINT_QUALITY_OPTIONS.get(print_quality)

        # Initialize exporter object
        exporter = QgsLayoutExporter(layout)
        
        # Get the file extension
        filetype = os.path.splitext(filepath)[1][1:]  

        if filetype.upper() == "PNG":
            export_settings_img = QgsLayoutExporter.ImageExportSettings()
            export_settings_img.dpi = dpi
            result = exporter.exportToImage(filepath, export_settings_img)
        elif filetype.upper() == "PDF":
            export_settings_pdf = QgsLayoutExporter.PdfExportSettings()
            export_settings_pdf.dpi = dpi
            result = exporter.exportToPdf(filepath, export_settings_pdf)
        else:
            raise ValueError("Unsupported file type")
        
        # Wrap layer name if too long
        if self.dlg.checkBox_Legenda.isChecked():
            layers = self.project.mapLayers()
            mapping_dict = self._check_layer_name_length(layers)
            for layer in layers.values():
                old_name = mapping_dict.get(layer.name())
                layer.setName(old_name)

        return result == QgsLayoutExporter.Success

    def _generate_export_path(self):
        map_name = self.dlg.lineEdit_FileName.text()
        if not map_name:
            return

        file_format = self.dlg.comboBox_BestandsFormaat.currentText()
        return os.path.join(self.working_dir, "export", f"{map_name}.{file_format.lower()}")

    def export_map_button_pressed(self):
        if not self.working_dir_available:
            self.log("Geen opslaglocatie gevonden. Selecteer eerst de juiste werkmap in de Instellingen.", level=1)
            return

        file_path = self._generate_export_path()
        if not file_path:
            self.log("Geen bestandsnaam opgegeven", 1)
            return
        if os.path.exists(file_path):
            overwrite = QMessageBox.question(
                self.dlg,
                "Bestand bestaat al",
                f"Het bestand {file_path} bestaat al. Wilt u het overschrijven?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if overwrite == QMessageBox.StandardButton.No:
                return

        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))

        layout = self._build_layout()

        success = self._exporter(layout, file_path)
        if success:
            self.log(f"Kaart succesvol geëxporteerd naar {file_path}", 3)
            QMessageBox.information(
                self.dlg,
                "Export succesvol",
                f"De kaart is succesvol geëxporteerd naar {file_path}.",
            )
        else:
            self.log(f"Fout bij het exporteren van de kaart naar {file_path}", 2)
            QMessageBox.critical(
                self.dlg,
                "Export mislukt",
                f"Het exporteren van de kaart naar {file_path} is mislukt.",
            )
