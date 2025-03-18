FROM qgis/qgis:final-3_34_13

RUN apt-get update && apt-get install -y python3-pyqt5.qtwebsockets && apt-get clean
RUN pip3 install pytest
