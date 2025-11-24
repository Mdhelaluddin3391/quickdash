# apps/delivery/utils.py
import math

def haversine_distance(lat1, lng1, lat2, lng2):
    """
    Do coordinates ke beech ki distance calculate karta hai (Haversine Formula).
    Returns: Distance in Kilometers (km)
    """
    if any(x is None for x in [lat1, lng1, lat2, lng2]):
        return float('inf') # Agar location na ho toh infinite distance maano

    # Earth radius in kilometers
    R = 6371.0

    # Convert degrees to radians
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(d_lat / 2) * math.sin(d_lat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lng / 2) * math.sin(d_lng / 2))
         
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance