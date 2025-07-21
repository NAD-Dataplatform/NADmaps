PLUGIN_NAME = "NAD Kaarten"
PLUGIN_ID = "nad_maps"
ADMIN_USERNAMES = ['svanderhoeven', 'devandenberg']
# ADMIN_USERNAMES = ['Stijn.Overmeen']
# ADMIN_USERNAMES = ['']
SERVICE_ENDPOINT = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
PAPER_OPTIONS = [
    "A4 staand",
    "A4 liggend",
    "A0 staand", 
    "A0 liggend"
]
FORMAT_OPTIONS = ["PNG", "PDF"]
PLACEMENT_OPTIONS = [
    "Linksboven",
    "Rechtsboven",
    "Linksonder",
    "Rechtonder"
]
PRINT_QUALITY_OPTIONS = {
    "Lage kwaliteit": 72,
    "Normale kwaliteit": 150,
    "Hoge kwaliteit": 300,
    "Zeer hoge kwaliteit": 600,
    "Maximale kwaliteit": 1200
}
