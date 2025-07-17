PLUGIN_NAME = "NAD Kaarten"
PLUGIN_ID = "nad_maps"
ADMIN_USERNAMES = ['svanderhoeven']
# ADMIN_USERNAMES = ['Stijn.Overmeen']
# ADMIN_USERNAMES = ['']
SERVICE_ENDPOINT = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
PAPER_OPTIONS = [
    "A4 staand",
    "A4 liggend",
    "A3 staand",
    "A3 liggend",
    "A0 staand",
    "A0 liggend"
]
FORMAT_OPTIONS = ["PNG", "PDF"]
PLACEMENT_OPTIONS = [
    "Linksboven",
    "Rechtsboven",
    "Linksonder",
    "Rechtsonder"
]
PRINT_QUALITY_OPTIONS = {
    "Standaard (150 DPI)": 150,
    "Hoog (300 DPI)": 300,
    "Zeer hoog (600 DPI)": 600,
}
