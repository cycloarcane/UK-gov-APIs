#!/usr/bin/env python3
"""
uk_police_api.py — FastMCP tool for accessing UK Police data via data.police.uk API

FastMCP tools
────────────
    get_police_forces(...)
    get_specific_force(force_id, ...)
    get_neighbourhoods(force_id, ...)
    get_specific_neighbourhood(force_id, neighbourhood_id, ...)
    get_crimes_street_point(lat, lng, date=None, category=None, ...)
    get_crimes_street_area(poly, date=None, category=None, ...)
    get_crimes_no_location(force_id, date=None, category=None, ...)
    get_crime_outcomes(crime_id, ...)
    get_outcomes_at_location(lat, lng, date=None, ...)
    get_stop_search_force(force_id, date=None, ...)
    get_stop_search_location(lat, lng, date=None, ...)
    get_crime_categories(date=None, ...)
    locate_neighbourhood(lat, lng, ...)
    get_available_dates(...)

Returns
───────
    {
      "status": "success",
      "data": [...],
      "count": 5,
      "metadata": {...}
    }

Dependencies
────────────
    pip install requests

Setup
─────
    No API key required - UK Police API is open access
    Rate limiting is applied automatically to respect the service
"""

import json
import os
import sys
import time
import logging
from typing import Any, Dict, List, Optional, Union
import re
from datetime import datetime, timedelta

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("uk_police")

mcp = FastMCP("uk_police")  # MCP route → /uk_police
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

# API configuration
BASE_URL = "https://data.police.uk/api"

# Rate limiting
_LAST_CALL_AT: float = 0.0
DEFAULT_RATE_LIMIT = 0.5  # 2 requests per second to be respectful


def _rate_limit(calls_per_second: float = DEFAULT_RATE_LIMIT) -> None:
    """Rate limiting for police API requests"""
    global _LAST_CALL_AT
    
    min_interval = 1.0 / calls_per_second
    wait = _LAST_CALL_AT + min_interval - time.time()
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL_AT = time.time()


def _get_cache_key(operation: str, **kwargs) -> str:
    """Generate a cache key"""
    import hashlib
    serializable_kwargs = {
        k: v for k, v in kwargs.items() 
        if isinstance(v, (str, int, float, bool, type(None)))
    }
    cache_str = f"{operation}_{json.dumps(serializable_kwargs, sort_keys=True)}"
    return hashlib.md5(cache_str.encode()).hexdigest()


def _get_from_cache(cache_key: str, max_age: int = 3600) -> Optional[Dict[str, Any]]:
    """Try to get results from cache"""
    cache_file = os.path.join(_CACHE_DIR, f"{cache_key}.json")
    
    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < max_age:
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
    return None


def _save_to_cache(cache_key: str, data: Dict[str, Any]) -> None:
    """Save results to cache"""
    cache_file = os.path.join(_CACHE_DIR, f"{cache_key}.json")
    try:
        with open(cache_file, 'w') as f:
            json.dump(data, f)
    except IOError as e:
        logger.warning(f"Cache write error: {e}")


def _make_request(endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Make a request to the UK Police API"""
    if not REQUESTS_AVAILABLE:
        return {
            "status": "error",
            "message": "requests not available. Install with: pip install requests"
        }
    
    try:
        _rate_limit()
        
        url = f"{BASE_URL}/{endpoint}"
        headers = {
            "User-Agent": "UK-Police-MCP-Client/1.0",
            "Accept": "application/json"
        }
        
        response = requests.get(url, params=params or {}, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "data": data,
                "count": len(data) if isinstance(data, list) else 1
            }
        elif response.status_code == 404:
            return {
                "status": "success",
                "data": [],
                "count": 0,
                "message": "No data found for the specified parameters"
            }
        elif response.status_code == 503:
            return {
                "status": "error",
                "message": "Service temporarily unavailable or request too large (>10,000 results)"
            }
        else:
            return {
                "status": "error",
                "message": f"API error: HTTP {response.status_code}",
                "details": response.text[:200] if response.text else None
            }
            
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Request timed out after 30 seconds"
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }


def _validate_date(date_str: str) -> bool:
    """Validate date format (YYYY-MM)"""
    if not date_str:
        return True
    
    pattern = r'^\d{4}-\d{2}$'
    return re.match(pattern, date_str) is not None


def _validate_coordinates(lat: Union[str, float], lng: Union[str, float]) -> bool:
    """Validate latitude and longitude"""
    try:
        lat_float = float(lat)
        lng_float = float(lng)
        return -90 <= lat_float <= 90 and -180 <= lng_float <= 180
    except (ValueError, TypeError):
        return False


@mcp.tool()
def check_police_api_status() -> Dict[str, Union[str, Dict[str, bool]]]:
    """
    Check if the UK Police API is available and working.
    
    Returns:
        A dictionary with API status information
    """
    if not REQUESTS_AVAILABLE:
        return {
            "status": "error",
            "message": "requests library not available",
            "dependencies": {"requests": False},
            "installation_instructions": ["requests: pip install requests"]
        }
    
    # Test the API with a simple request
    result = _make_request("forces")
    
    return {
        "status": "ok" if result["status"] == "success" else "error",
        "api_available": result["status"] == "success",
        "dependencies": {"requests": True},
        "message": "UK Police API is accessible" if result["status"] == "success" else result.get("message", "API not accessible"),
        "base_url": BASE_URL
    }


@mcp.tool()
def get_police_forces(use_cache: bool = True, cache_max_age: int = 86400) -> Dict[str, Any]:
    """
    Get a list of all police forces available via the API.
    
    Args:
        use_cache: Whether to use caching (default: True)
        cache_max_age: Maximum age of cached data in seconds (default: 24 hours)
        
    Returns:
        Dict containing list of police forces with their IDs and names
    """
    if use_cache:
        cache_key = _get_cache_key("forces")
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("forces")
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_specific_force(
    force_id: str, 
    use_cache: bool = True, 
    cache_max_age: int = 86400
) -> Dict[str, Any]:
    """
    Get detailed information about a specific police force.
    
    Args:
        force_id: Police force identifier (e.g., 'leicestershire', 'metropolitan')
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing detailed force information including contact details
    """
    if not force_id or not isinstance(force_id, str):
        return {
            "status": "error",
            "message": "force_id must be a non-empty string"
        }
    
    if use_cache:
        cache_key = _get_cache_key("force", force_id=force_id)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request(f"forces/{force_id}")
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_neighbourhoods(
    force_id: str,
    use_cache: bool = True,
    cache_max_age: int = 3600
) -> Dict[str, Any]:
    """
    Get all neighbourhoods for a specific police force.
    
    Args:
        force_id: Police force identifier
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing list of neighbourhoods with IDs and names
    """
    if not force_id or not isinstance(force_id, str):
        return {
            "status": "error",
            "message": "force_id must be a non-empty string"
        }
    
    if use_cache:
        cache_key = _get_cache_key("neighbourhoods", force_id=force_id)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request(f"{force_id}")
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_specific_neighbourhood(
    force_id: str,
    neighbourhood_id: str,
    use_cache: bool = True,
    cache_max_age: int = 3600
) -> Dict[str, Any]:
    """
    Get detailed information about a specific neighbourhood.
    
    Args:
        force_id: Police force identifier
        neighbourhood_id: Neighbourhood identifier
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing detailed neighbourhood information
    """
    if not force_id or not neighbourhood_id:
        return {
            "status": "error",
            "message": "Both force_id and neighbourhood_id must be provided"
        }
    
    if use_cache:
        cache_key = _get_cache_key("neighbourhood", force_id=force_id, neighbourhood_id=neighbourhood_id)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request(f"{force_id}/{neighbourhood_id}")
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_crimes_street_point(
    lat: Union[str, float],
    lng: Union[str, float],
    date: Optional[str] = None,
    category: Optional[str] = None,
    use_cache: bool = True,
    cache_max_age: int = 1800
) -> Dict[str, Any]:
    """
    Get crimes within a 1-mile radius of a specific location.
    
    Args:
        lat: Latitude coordinate
        lng: Longitude coordinate
        date: Date in YYYY-MM format (optional, defaults to latest available)
        category: Crime category to filter by (optional)
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing list of crimes near the specified location
    """
    if not _validate_coordinates(lat, lng):
        return {
            "status": "error",
            "message": "Invalid coordinates. Latitude must be between -90 and 90, longitude between -180 and 180"
        }
    
    if date and not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM format (e.g., '2024-01')"
        }
    
    params = {
        "lat": str(lat),
        "lng": str(lng)
    }
    
    if date:
        params["date"] = date
    if category:
        params["category"] = category
    
    if use_cache:
        cache_key = _get_cache_key("crimes_street_point", **params)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("crimes-street/all-crime", params)
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_crimes_street_area(
    poly: str,
    date: Optional[str] = None,
    category: Optional[str] = None,
    use_cache: bool = True,
    cache_max_age: int = 1800
) -> Dict[str, Any]:
    """
    Get crimes within a custom area defined by a polygon.
    
    Args:
        poly: Polygon coordinates as lat/lng pairs separated by colons (e.g., "52.268,0.543:52.794,0.238:52.130,0.478")
        date: Date in YYYY-MM format (optional)
        category: Crime category to filter by (optional)
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing list of crimes within the specified area
    """
    if not poly or not isinstance(poly, str):
        return {
            "status": "error",
            "message": "poly parameter must be a non-empty string of lat/lng coordinates"
        }
    
    if date and not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM format (e.g., '2024-01')"
        }
    
    # Basic validation of polygon format
    coord_pairs = poly.split(":")
    if len(coord_pairs) < 3:
        return {
            "status": "error",
            "message": "Polygon must have at least 3 coordinate pairs"
        }
    
    for pair in coord_pairs[:3]:  # Check first 3 pairs
        coords = pair.split(",")
        if len(coords) != 2:
            return {
                "status": "error",
                "message": "Invalid coordinate format. Use lat,lng:lat,lng format"
            }
        try:
            lat, lng = float(coords[0]), float(coords[1])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                return {
                    "status": "error",
                    "message": f"Invalid coordinates in pair {pair}"
                }
        except ValueError:
            return {
                "status": "error",
                "message": f"Invalid numeric coordinates in pair {pair}"
            }
    
    params = {"poly": poly}
    if date:
        params["date"] = date
    if category:
        params["category"] = category
    
    if use_cache:
        cache_key = _get_cache_key("crimes_street_area", **params)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("crimes-street/all-crime", params)
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_crimes_no_location(
    force_id: str,
    date: Optional[str] = None,
    category: Optional[str] = None,
    use_cache: bool = True,
    cache_max_age: int = 1800
) -> Dict[str, Any]:
    """
    Get crimes with no location information for a specific force.
    
    Args:
        force_id: Police force identifier
        date: Date in YYYY-MM format (optional)
        category: Crime category to filter by (optional)
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing list of crimes with no location data
    """
    if not force_id:
        return {
            "status": "error",
            "message": "force_id must be provided"
        }
    
    if date and not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM format"
        }
    
    params = {"force": force_id}
    if date:
        params["date"] = date
    if category:
        params["category"] = category
    
    if use_cache:
        cache_key = _get_cache_key("crimes_no_location", **params)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("crimes-no-location", params)
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_crime_outcomes(crime_id: str, use_cache: bool = True, cache_max_age: int = 3600) -> Dict[str, Any]:
    """
    Get outcomes for a specific crime by its persistent ID.
    
    Args:
        crime_id: Persistent crime identifier
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing crime outcome information
    """
    if not crime_id:
        return {
            "status": "error",
            "message": "crime_id must be provided"
        }
    
    if use_cache:
        cache_key = _get_cache_key("crime_outcomes", crime_id=crime_id)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request(f"outcomes-for-crime/{crime_id}")
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_outcomes_at_location(
    lat: Union[str, float],
    lng: Union[str, float],
    date: Optional[str] = None,
    use_cache: bool = True,
    cache_max_age: int = 1800
) -> Dict[str, Any]:
    """
    Get crime outcomes at a specific location.
    
    Args:
        lat: Latitude coordinate
        lng: Longitude coordinate
        date: Date in YYYY-MM format (optional)
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing crime outcomes at the specified location
    """
    if not _validate_coordinates(lat, lng):
        return {
            "status": "error",
            "message": "Invalid coordinates"
        }
    
    if date and not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM format"
        }
    
    params = {
        "lat": str(lat),
        "lng": str(lng)
    }
    
    if date:
        params["date"] = date
    
    if use_cache:
        cache_key = _get_cache_key("outcomes_at_location", **params)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("outcomes-at-location", params)
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_stop_search_force(
    force_id: str,
    date: Optional[str] = None,
    use_cache: bool = True,
    cache_max_age: int = 1800
) -> Dict[str, Any]:
    """
    Get stop and search data for a specific police force.
    
    Args:
        force_id: Police force identifier
        date: Date in YYYY-MM format (optional)
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing stop and search records for the force
    """
    if not force_id:
        return {
            "status": "error",
            "message": "force_id must be provided"
        }
    
    if date and not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM format"
        }
    
    params = {"force": force_id}
    if date:
        params["date"] = date
    
    if use_cache:
        cache_key = _get_cache_key("stop_search_force", **params)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("stops-force", params)
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_stop_search_location(
    lat: Union[str, float],
    lng: Union[str, float],
    date: Optional[str] = None,
    use_cache: bool = True,
    cache_max_age: int = 1800
) -> Dict[str, Any]:
    """
    Get stop and search data within a 1-mile radius of a location.
    
    Args:
        lat: Latitude coordinate
        lng: Longitude coordinate
        date: Date in YYYY-MM format (optional)
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing stop and search records near the location
    """
    if not _validate_coordinates(lat, lng):
        return {
            "status": "error",
            "message": "Invalid coordinates"
        }
    
    if date and not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM format"
        }
    
    params = {
        "lat": str(lat),
        "lng": str(lng)
    }
    
    if date:
        params["date"] = date
    
    if use_cache:
        cache_key = _get_cache_key("stop_search_location", **params)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("stops-street", params)
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_crime_categories(date: Optional[str] = None, use_cache: bool = True, cache_max_age: int = 86400) -> Dict[str, Any]:
    """
    Get available crime categories, optionally for a specific date.
    
    Args:
        date: Date in YYYY-MM format (optional)
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing list of available crime categories
    """
    if date and not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM format"
        }
    
    params = {}
    if date:
        params["date"] = date
    
    if use_cache:
        cache_key = _get_cache_key("crime_categories", **params)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("crime-categories", params)
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def locate_neighbourhood(
    lat: Union[str, float],
    lng: Union[str, float],
    use_cache: bool = True,
    cache_max_age: int = 3600
) -> Dict[str, Any]:
    """
    Find the neighbourhood policing team responsible for a specific location.
    
    Args:
        lat: Latitude coordinate
        lng: Longitude coordinate
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing neighbourhood information for the location
    """
    if not _validate_coordinates(lat, lng):
        return {
            "status": "error",
            "message": "Invalid coordinates"
        }
    
    params = {
        "lat": str(lat),
        "lng": str(lng)
    }
    
    if use_cache:
        cache_key = _get_cache_key("locate_neighbourhood", **params)
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("locate-neighbourhood", params)
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def get_available_dates(use_cache: bool = True, cache_max_age: int = 86400) -> Dict[str, Any]:
    """
    Get list of available dates for crime data.
    
    Args:
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing list of available dates
    """
    if use_cache:
        cache_key = _get_cache_key("available_dates")
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    result = _make_request("crimes-street-dates")
    
    if result["status"] == "success" and use_cache:
        _save_to_cache(cache_key, result)
    
    return result


@mcp.tool()
def comprehensive_area_report(
    lat: Union[str, float],
    lng: Union[str, float],
    date: Optional[str] = None,
    radius_miles: float = 1.0,
    include_outcomes: bool = True,
    include_stop_search: bool = True
) -> Dict[str, Any]:
    """
    Generate a comprehensive crime and policing report for an area.
    
    Args:
        lat: Latitude coordinate
        lng: Longitude coordinate
        date: Date in YYYY-MM format (optional)
        radius_miles: Search radius in miles (API uses 1-mile radius)
        include_outcomes: Whether to include crime outcomes
        include_stop_search: Whether to include stop and search data
        
    Returns:
        Dict with comprehensive area analysis
    """
    if not _validate_coordinates(lat, lng):
        return {
            "status": "error",
            "message": "Invalid coordinates"
        }
    
    result = {
        "status": "success",
        "location": {"lat": float(lat), "lng": float(lng)},
        "date": date or "latest",
        "neighbourhood_info": {},
        "crime_data": {},
        "outcomes_data": {},
        "stop_search_data": {},
        "summary": {}
    }
    
    # Get neighbourhood information
    logger.info(f"Getting neighbourhood info for {lat}, {lng}")
    neighbourhood_result = locate_neighbourhood(lat, lng)
    result["neighbourhood_info"] = neighbourhood_result
    
    # Get crime data
    logger.info(f"Getting crime data for {lat}, {lng}")
    crime_result = get_crimes_street_point(lat, lng, date)
    result["crime_data"] = crime_result
    
    # Get outcomes if requested
    if include_outcomes:
        logger.info(f"Getting outcomes data for {lat}, {lng}")
        outcomes_result = get_outcomes_at_location(lat, lng, date)
        result["outcomes_data"] = outcomes_result
    
    # Get stop and search data if requested
    if include_stop_search:
        logger.info(f"Getting stop and search data for {lat}, {lng}")
        stop_search_result = get_stop_search_location(lat, lng, date)
        result["stop_search_data"] = stop_search_result
    
    # Generate summary
    crime_count = crime_result.get("count", 0) if crime_result.get("status") == "success" else 0
    outcomes_count = result["outcomes_data"].get("count", 0) if include_outcomes else 0
    stop_search_count = result["stop_search_data"].get("count", 0) if include_stop_search else 0
    
    # Analyze crime categories
    crime_categories = {}
    if crime_result.get("status") == "success" and crime_result.get("data"):
        for crime in crime_result["data"]:
            category = crime.get("category", "unknown")
            crime_categories[category] = crime_categories.get(category, 0) + 1
    
    result["summary"] = {
        "total_crimes": crime_count,
        "total_outcomes": outcomes_count,
        "total_stop_searches": stop_search_count,
        "crime_categories": crime_categories,
        "most_common_crime": max(crime_categories.items(), key=lambda x: x[1])[0] if crime_categories else None,
        "area_assessment": "high activity" if crime_count > 50 else "medium activity" if crime_count > 20 else "low activity"
    }
    
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")