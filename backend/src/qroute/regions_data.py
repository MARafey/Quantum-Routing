"""Cross-border relief regions: (name, lat, lon, country, hub).  Coordinates are approximate city centres."""

from __future__ import annotations

TR, SY, BD, IN, NP = "Türkiye", "Syria", "Bangladesh", "India", "Nepal"

TURKIYE_SYRIA = [
    ("Adana", 37.0000, 35.3213, TR, True), ("Gaziantep", 37.0662, 37.3833, TR, True),
    ("Mersin", 36.8121, 34.6415, TR, True), ("Şanlıurfa", 37.1591, 38.7969, TR, True),
    ("Diyarbakır", 37.9144, 40.2306, TR, True),
    ("Kahramanmaraş", 37.5858, 36.9371, TR, False), ("Antakya", 36.2021, 36.1600, TR, False),
    ("İskenderun", 36.5872, 36.1735, TR, False), ("Osmaniye", 37.0742, 36.2478, TR, False),
    ("Malatya", 38.3552, 38.3095, TR, False), ("Adıyaman", 37.7648, 38.2786, TR, False),
    ("Kilis", 36.7184, 37.1212, TR, False), ("Elazığ", 38.6810, 39.2264, TR, False),
    ("Reyhanlı (Hatay)", 36.2690, 36.5700, TR, False),
    ("Aleppo", 36.2021, 37.1343, SY, False), ("Idlib", 35.9306, 36.6339, SY, False),
    ("Hama", 35.1318, 36.7578, SY, False), ("Latakia", 35.5317, 35.7919, SY, False),
    ("Azaz", 36.5864, 37.0467, SY, False), ("Manbij", 36.5281, 37.9544, SY, False),
    ("Afrin", 36.5117, 36.8670, SY, False),
]

BENGAL_FLOODS = [
    ("Dhaka", 23.8103, 90.4125, BD, True), ("Kolkata", 22.5726, 88.3639, IN, True),
    ("Chattogram", 22.3569, 91.7832, BD, True), ("Guwahati", 26.1445, 91.7362, IN, True),
    ("Sylhet", 24.8949, 91.8687, BD, False), ("Khulna", 22.8456, 89.5403, BD, False),
    ("Rajshahi", 24.3745, 88.6042, BD, False), ("Barishal", 22.7010, 90.3535, BD, False),
    ("Rangpur", 25.7439, 89.2752, BD, False), ("Mymensingh", 24.7471, 90.4203, BD, False),
    ("Cox's Bazar", 21.4272, 92.0058, BD, False), ("Jessore", 23.1634, 89.2182, BD, False),
    ("Siliguri", 26.7271, 88.3953, IN, False), ("Agartala", 23.8315, 91.2868, IN, False),
    ("Shillong", 25.5788, 91.8933, IN, False), ("Malda", 25.0108, 88.1411, IN, False),
    ("Bongaon", 23.0400, 88.8300, IN, False), ("Silchar", 24.8333, 92.7789, IN, False),
    ("Comilla", 23.4607, 91.1809, BD, False), ("Bogura", 24.8465, 89.3773, BD, False),
]

NEPAL_HIMALAYA = [
    ("Kathmandu", 27.7172, 85.3240, NP, True), ("Lucknow", 26.8467, 80.9462, IN, True),
    ("Patna", 25.5941, 85.1376, IN, True), ("Biratnagar", 26.4525, 87.2718, NP, True),
    ("Pokhara", 28.2096, 83.9856, NP, False), ("Gorkha", 28.0000, 84.6300, NP, False),
    ("Bharatpur", 27.6833, 84.4333, NP, False), ("Birgunj", 27.0104, 84.8770, NP, False),
    ("Butwal", 27.7000, 83.4500, NP, False), ("Nepalgunj", 28.0500, 81.6167, NP, False),
    ("Dhangadhi", 28.6833, 80.6000, NP, False), ("Janakpur", 26.7288, 85.9260, NP, False),
    ("Hetauda", 27.4287, 85.0322, NP, False), ("Dharan", 26.8065, 87.2846, NP, False),
    ("Gorakhpur", 26.7606, 83.3732, IN, False), ("Muzaffarpur", 26.1209, 85.3647, IN, False),
    ("Siliguri", 26.7271, 88.3953, IN, False), ("Darbhanga", 26.1542, 85.8918, IN, False),
    ("Bhairahawa", 27.5056, 83.4500, NP, False), ("Itahari", 26.6667, 87.2833, NP, False),
    ("Dhulikhel", 27.6194, 85.5389, NP, False),
]

# id -> (name, bbox (lat_min, lat_max, lon_min, lon_max), cities)
DATA = {
    "turkiye-syria": ("Türkiye–Syria earthquake (2023)", (34.0, 40.0, 33.0, 42.0), TURKIYE_SYRIA),
    "bengal-floods": ("Bengal floods (Bangladesh + India)", (20.5, 28.0, 87.0, 93.5), BENGAL_FLOODS),
    "nepal-himalaya": ("Nepal–India Himalaya earthquake", (24.5, 30.0, 79.5, 89.0), NEPAL_HIMALAYA),
}
