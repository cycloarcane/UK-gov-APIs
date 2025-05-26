#!/usr/bin/env python3
"""
uk_bank_holidays.py — FastMCP tool for UK Bank Holidays API

FastMCP tools
────────────
    get_all_bank_holidays(region=None, ...)
    get_bank_holidays_by_year(year, region=None, ...)
    is_bank_holiday(date, region="all", ...)
    get_next_bank_holidays(region=None, limit=5, ...)
    get_upcoming_bank_holidays(days_ahead=30, region=None, ...)
    get_bank_holiday_by_date(date, region=None, ...)
    compare_regions_by_year(year, ...)
    get_regional_differences(year, ...)
    analyze_bank_holiday_patterns(start_year=None, end_year=None, ...)
    get_bank_holiday_statistics(region=None, ...)

Returns
───────
    {
      "status": "success",
      "data": [...],
      "region": "england-and-wales",
      "count": 8,
      "metadata": {...}
    }

Dependencies
────────────
    pip install requests

Setup
─────
    No API key required - UK Bank Holidays API is completely free and open
    Uses official UK Government data from gov.uk
"""

import json
import os
import sys
import time
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import re
from collections import defaultdict, Counter

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
logger = logging.getLogger("uk_bank_holidays")

mcp = FastMCP("uk_bank_holidays")  # MCP route → /uk_bank_holidays
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

# API configuration
BASE_URL = "https://www.gov.uk/bank-holidays.json"
VALID_REGIONS = ["england-and-wales", "scotland", "northern-ireland"]

# Rate limiting - be respectful to government API
_LAST_CALL_AT: float = 0.0
DEFAULT_RATE_LIMIT = 0.5  # 2 requests per second max


def _rate_limit(calls_per_second: float = DEFAULT_RATE_LIMIT) -> None:
    """Rate limiting for bank holidays API requests"""
    global _LAST_CALL_AT
    
    min_interval = 1.0 / calls_per_second
    wait = _LAST_CALL_AT + min_interval - time.time()
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL_AT = time.time()


def _get_cache_key(operation: str) -> str:
    """Generate a cache key"""
    import hashlib
    cache_str = f"bank_holidays_{operation}"
    return hashlib.md5(cache_str.encode()).hexdigest()


def _get_from_cache(cache_key: str, max_age: int = 86400) -> Optional[Dict[str, Any]]:
    """Try to get results from cache (default 24 hours)"""
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
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.warning(f"Cache write error: {e}")


def _fetch_bank_holidays_data(use_cache: bool = True, cache_max_age: int = 86400) -> Dict[str, Any]:
    """Fetch bank holidays data from the API"""
    if not REQUESTS_AVAILABLE:
        return {
            "status": "error",
            "message": "requests not available. Install with: pip install requests"
        }
    
    if use_cache:
        cache_key = _get_cache_key("all_data")
        cached_result = _get_from_cache(cache_key, cache_max_age)
        if cached_result:
            return cached_result
    
    try:
        _rate_limit()
        
        headers = {
            "User-Agent": "UK-Bank-Holidays-MCP-Client/1.0",
            "Accept": "application/json"
        }
        
        response = requests.get(BASE_URL, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            result = {
                "status": "success",
                "data": data,
                "fetched_at": datetime.now().isoformat(),
                "source": BASE_URL
            }
            
            if use_cache:
                _save_to_cache(cache_key, result)
            
            return result
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
    """Validate date format (YYYY-MM-DD)"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _validate_region(region: str) -> bool:
    """Validate region name"""
    return region in VALID_REGIONS


def _parse_date(date_str: str) -> datetime:
    """Parse date string to datetime object"""
    return datetime.strptime(date_str, "%Y-%m-%d")


def _format_bank_holiday(holiday: Dict[str, Any], region: str) -> Dict[str, Any]:
    """Format bank holiday data with additional metadata"""
    formatted = {
        "title": holiday.get("title", ""),
        "date": holiday.get("date", ""),
        "region": region,
        "notes": holiday.get("notes", ""),
        "bunting": holiday.get("bunting", False),
        "is_substitute": "substitute" in holiday.get("notes", "").lower(),
        "weekday": _parse_date(holiday["date"]).strftime("%A") if holiday.get("date") else None
    }
    
    # Add year for easy filtering
    if holiday.get("date"):
        formatted["year"] = int(holiday["date"].split("-")[0])
    
    return formatted


@mcp.tool()
def check_bank_holidays_api_status() -> Dict[str, Any]:
    """
    Check if the UK Bank Holidays API is available and working.
    
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
    result = _fetch_bank_holidays_data(use_cache=False)
    
    api_working = result["status"] == "success"
    
    return {
        "status": "ok" if api_working else "error",
        "api_available": api_working,
        "dependencies": {"requests": True},
        "message": "UK Bank Holidays API is accessible" if api_working else result.get("message", "API not accessible"),
        "base_url": BASE_URL,
        "regions_supported": VALID_REGIONS,
        "data_source": "Official UK Government data"
    }


@mcp.tool()
def get_all_bank_holidays(
    region: Optional[str] = None,
    use_cache: bool = True,
    cache_max_age: int = 86400
) -> Dict[str, Any]:
    """
    Get all bank holidays for specified region(s).
    
    Args:
        region: Region to get holidays for ("england-and-wales", "scotland", "northern-ireland", or None for all)
        use_cache: Whether to use caching
        cache_max_age: Maximum age of cached data in seconds
        
    Returns:
        Dict containing bank holidays data
    """
    if region and not _validate_region(region):
        return {
            "status": "error",
            "message": f"Invalid region. Must be one of: {', '.join(VALID_REGIONS)}"
        }
    
    data_result = _fetch_bank_holidays_data(use_cache, cache_max_age)
    
    if data_result["status"] != "success":
        return data_result
    
    raw_data = data_result["data"]
    
    if region:
        # Single region
        if region not in raw_data:
            return {
                "status": "error",
                "message": f"Region '{region}' not found in data"
            }
        
        holidays = [_format_bank_holiday(holiday, region) for holiday in raw_data[region]["events"]]
        
        return {
            "status": "success",
            "region": region,
            "data": holidays,
            "count": len(holidays),
            "years_covered": sorted(list(set(h["year"] for h in holidays))),
            "fetched_at": data_result["fetched_at"]
        }
    else:
        # All regions
        all_holidays = []
        for region_name, region_data in raw_data.items():
            for holiday in region_data["events"]:
                all_holidays.append(_format_bank_holiday(holiday, region_name))
        
        return {
            "status": "success",
            "region": "all",
            "data": all_holidays,
            "count": len(all_holidays),
            "regions_included": list(raw_data.keys()),
            "years_covered": sorted(list(set(h["year"] for h in all_holidays))),
            "fetched_at": data_result["fetched_at"]
        }


@mcp.tool()
def get_bank_holidays_by_year(
    year: int,
    region: Optional[str] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get bank holidays for a specific year.
    
    Args:
        year: Year to get holidays for (e.g., 2024)
        region: Region to filter by (optional)
        use_cache: Whether to use caching
        
    Returns:
        Dict containing bank holidays for the specified year
    """
    if year < 2019 or year > 2030:
        return {
            "status": "error",
            "message": "Year must be between 2019 and 2030 (based on available data)"
        }
    
    all_holidays_result = get_all_bank_holidays(region, use_cache)
    
    if all_holidays_result["status"] != "success":
        return all_holidays_result
    
    year_holidays = [h for h in all_holidays_result["data"] if h["year"] == year]
    
    # Sort by date
    year_holidays.sort(key=lambda x: x["date"])
    
    return {
        "status": "success",
        "year": year,
        "region": region or "all",
        "data": year_holidays,
        "count": len(year_holidays),
        "regions_included": list(set(h["region"] for h in year_holidays)),
        "fetched_at": all_holidays_result.get("fetched_at")
    }


@mcp.tool()
def is_bank_holiday(
    date: str,
    region: str = "all",
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Check if a specific date is a bank holiday.
    
    Args:
        date: Date to check in YYYY-MM-DD format
        region: Region to check ("all", "england-and-wales", "scotland", or "northern-ireland")
        use_cache: Whether to use caching
        
    Returns:
        Dict containing bank holiday status for the date
    """
    if not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM-DD format (e.g., '2024-12-25')"
        }
    
    if region != "all" and not _validate_region(region):
        return {
            "status": "error",
            "message": f"Invalid region. Must be 'all' or one of: {', '.join(VALID_REGIONS)}"
        }
    
    all_holidays_result = get_all_bank_holidays(None if region == "all" else region, use_cache)
    
    if all_holidays_result["status"] != "success":
        return all_holidays_result
    
    # Find holidays on this date
    matching_holidays = [h for h in all_holidays_result["data"] if h["date"] == date]
    
    if region != "all":
        matching_holidays = [h for h in matching_holidays if h["region"] == region]
    
    is_holiday = len(matching_holidays) > 0
    
    return {
        "status": "success",
        "date": date,
        "region": region,
        "is_bank_holiday": is_holiday,
        "holidays": matching_holidays,
        "count": len(matching_holidays),
        "weekday": _parse_date(date).strftime("%A")
    }


@mcp.tool()
def get_next_bank_holidays(
    region: Optional[str] = None,
    limit: int = 5,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get the next upcoming bank holidays.
    
    Args:
        region: Region to get holidays for (optional)
        limit: Maximum number of holidays to return
        use_cache: Whether to use caching
        
    Returns:
        Dict containing upcoming bank holidays
    """
    if limit < 1 or limit > 50:
        return {
            "status": "error",
            "message": "Limit must be between 1 and 50"
        }
    
    all_holidays_result = get_all_bank_holidays(region, use_cache)
    
    if all_holidays_result["status"] != "success":
        return all_holidays_result
    
    today = datetime.now().date()
    upcoming_holidays = []
    
    for holiday in all_holidays_result["data"]:
        holiday_date = _parse_date(holiday["date"]).date()
        if holiday_date >= today:
            upcoming_holidays.append({
                **holiday,
                "days_until": (holiday_date - today).days
            })
    
    # Sort by date and limit
    upcoming_holidays.sort(key=lambda x: x["date"])
    upcoming_holidays = upcoming_holidays[:limit]
    
    return {
        "status": "success",
        "region": region or "all",
        "data": upcoming_holidays,
        "count": len(upcoming_holidays),
        "next_holiday": upcoming_holidays[0] if upcoming_holidays else None,
        "today": today.isoformat()
    }


@mcp.tool()
def get_upcoming_bank_holidays(
    days_ahead: int = 30,
    region: Optional[str] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get bank holidays occurring within a specified number of days.
    
    Args:
        days_ahead: Number of days ahead to look for holidays
        region: Region to get holidays for (optional)
        use_cache: Whether to use caching
        
    Returns:
        Dict containing bank holidays within the timeframe
    """
    if days_ahead < 1 or days_ahead > 365:
        return {
            "status": "error",
            "message": "days_ahead must be between 1 and 365"
        }
    
    all_holidays_result = get_all_bank_holidays(region, use_cache)
    
    if all_holidays_result["status"] != "success":
        return all_holidays_result
    
    today = datetime.now().date()
    end_date = today + timedelta(days=days_ahead)
    
    upcoming_holidays = []
    
    for holiday in all_holidays_result["data"]:
        holiday_date = _parse_date(holiday["date"]).date()
        if today <= holiday_date <= end_date:
            upcoming_holidays.append({
                **holiday,
                "days_until": (holiday_date - today).days
            })
    
    # Sort by date
    upcoming_holidays.sort(key=lambda x: x["date"])
    
    return {
        "status": "success",
        "region": region or "all",
        "timeframe_days": days_ahead,
        "data": upcoming_holidays,
        "count": len(upcoming_holidays),
        "period": {
            "start": today.isoformat(),
            "end": end_date.isoformat()
        }
    }


@mcp.tool()
def get_bank_holiday_by_date(
    date: str,
    region: Optional[str] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get detailed information about bank holiday(s) on a specific date.
    
    Args:
        date: Date to check in YYYY-MM-DD format
        region: Region to check (optional, defaults to all regions)
        use_cache: Whether to use caching
        
    Returns:
        Dict containing detailed bank holiday information for the date
    """
    if not _validate_date(date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM-DD format"
        }
    
    holiday_check = is_bank_holiday(date, region or "all", use_cache)
    
    if holiday_check["status"] != "success":
        return holiday_check
    
    result = {
        "status": "success",
        "date": date,
        "region": region or "all",
        "is_bank_holiday": holiday_check["is_bank_holiday"],
        "weekday": holiday_check["weekday"],
    }
    
    if holiday_check["is_bank_holiday"]:
        holidays = holiday_check["holidays"]
        result.update({
            "holidays": holidays,
            "count": len(holidays),
            "regions_affected": list(set(h["region"] for h in holidays)),
            "titles": [h["title"] for h in holidays],
            "has_bunting": any(h["bunting"] for h in holidays),
            "substitute_days": [h for h in holidays if h["is_substitute"]]
        })
    else:
        result.update({
            "holidays": [],
            "count": 0,
            "message": f"No bank holidays found on {date}"
        })
    
    return result


@mcp.tool()
def compare_regions_by_year(year: int, use_cache: bool = True) -> Dict[str, Any]:
    """
    Compare bank holidays across different UK regions for a specific year.
    
    Args:
        year: Year to compare
        use_cache: Whether to use caching
        
    Returns:
        Dict containing regional comparison data
    """
    if year < 2019 or year > 2030:
        return {
            "status": "error",
            "message": "Year must be between 2019 and 2030"
        }
    
    comparison = {
        "status": "success",
        "year": year,
        "regions": {}
    }
    
    for region in VALID_REGIONS:
        region_holidays = get_bank_holidays_by_year(year, region, use_cache)
        if region_holidays["status"] == "success":
            comparison["regions"][region] = {
                "holidays": region_holidays["data"],
                "count": region_holidays["count"],
                "unique_holidays": []
            }
    
    # Find unique holidays per region
    all_dates = set()
    for region_data in comparison["regions"].values():
        all_dates.update(h["date"] for h in region_data["holidays"])
    
    for region, region_data in comparison["regions"].items():
        region_dates = set(h["date"] for h in region_data["holidays"])
        other_regions_dates = set()
        
        for other_region, other_data in comparison["regions"].items():
            if other_region != region:
                other_regions_dates.update(h["date"] for h in other_data["holidays"])
        
        unique_dates = region_dates - other_regions_dates
        region_data["unique_holidays"] = [
            h for h in region_data["holidays"] if h["date"] in unique_dates
        ]
    
    # Summary statistics
    comparison["summary"] = {
        "total_unique_dates": len(all_dates),
        "common_holidays": len(all_dates) - sum(len(r["unique_holidays"]) for r in comparison["regions"].values()),
        "region_counts": {region: data["count"] for region, data in comparison["regions"].items()},
        "most_holidays": max(comparison["regions"].items(), key=lambda x: x[1]["count"])[0],
        "fewest_holidays": min(comparison["regions"].items(), key=lambda x: x[1]["count"])[0]
    }
    
    return comparison


@mcp.tool()
def get_regional_differences(year: int, use_cache: bool = True) -> Dict[str, Any]:
    """
    Analyze differences in bank holidays between UK regions for a specific year.
    
    Args:
        year: Year to analyze
        use_cache: Whether to use caching
        
    Returns:
        Dict containing analysis of regional differences
    """
    comparison = compare_regions_by_year(year, use_cache)
    
    if comparison["status"] != "success":
        return comparison
    
    differences = {
        "status": "success",
        "year": year,
        "analysis": {}
    }
    
    # Analyze unique holidays by region
    for region, data in comparison["regions"].items():
        unique_holidays = data["unique_holidays"]
        differences["analysis"][region] = {
            "unique_count": len(unique_holidays),
            "unique_holidays": unique_holidays,
            "notable_differences": []
        }
        
        # Add notable differences
        for holiday in unique_holidays:
            if "St Patrick's Day" in holiday["title"]:
                differences["analysis"][region]["notable_differences"].append("Has St Patrick's Day")
            elif "St Andrew's Day" in holiday["title"]:
                differences["analysis"][region]["notable_differences"].append("Has St Andrew's Day")
            elif "2nd January" in holiday["title"]:
                differences["analysis"][region]["notable_differences"].append("Has 2nd January holiday")
            elif "Battle of the Boyne" in holiday["title"]:
                differences["analysis"][region]["notable_differences"].append("Has Battle of the Boyne (Orangemen's Day)")
            elif holiday["title"] != holiday["title"]:  # Different summer bank holiday dates
                differences["analysis"][region]["notable_differences"].append(f"Different timing for {holiday['title']}")
    
    # Common holidays across all regions
    common_dates = set(comparison["regions"][VALID_REGIONS[0]]["holidays"][0]["date"] for h in comparison["regions"][VALID_REGIONS[0]]["holidays"])
    for region in VALID_REGIONS[1:]:
        region_dates = set(h["date"] for h in comparison["regions"][region]["holidays"])
        common_dates &= region_dates
    
    differences["common_holidays"] = {
        "count": len(common_dates),
        "dates": sorted(list(common_dates))
    }
    
    return differences


@mcp.tool()
def analyze_bank_holiday_patterns(
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    region: Optional[str] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Analyze patterns in bank holidays over multiple years.
    
    Args:
        start_year: Starting year for analysis (default: 2019)
        end_year: Ending year for analysis (default: current year + 2)
        region: Region to analyze (optional, defaults to all)
        use_cache: Whether to use caching
        
    Returns:
        Dict containing pattern analysis
    """
    if start_year is None:
        start_year = 2019
    if end_year is None:
        end_year = datetime.now().year + 2
    
    if start_year < 2019 or end_year > 2030 or start_year >= end_year:
        return {
            "status": "error",
            "message": "Invalid year range. Must be between 2019-2030 and start_year < end_year"
        }
    
    all_holidays_result = get_all_bank_holidays(region, use_cache)
    
    if all_holidays_result["status"] != "success":
        return all_holidays_result
    
    # Filter holidays by year range
    holidays = [h for h in all_holidays_result["data"] if start_year <= h["year"] <= end_year]
    
    analysis = {
        "status": "success",
        "period": {"start_year": start_year, "end_year": end_year},
        "region": region or "all",
        "total_holidays": len(holidays),
        "patterns": {}
    }
    
    # Analyze by month
    months = defaultdict(int)
    for holiday in holidays:
        month = int(holiday["date"].split("-")[1])
        months[month] += 1
    
    analysis["patterns"]["by_month"] = {
        "data": dict(months),
        "busiest_month": max(months.items(), key=lambda x: x[1])[0] if months else None,
        "quietest_month": min(months.items(), key=lambda x: x[1])[0] if months else None
    }
    
    # Analyze by weekday
    weekdays = Counter(h["weekday"] for h in holidays)
    analysis["patterns"]["by_weekday"] = {
        "data": dict(weekdays),
        "most_common_day": weekdays.most_common(1)[0][0] if weekdays else None
    }
    
    # Analyze substitute days
    substitute_count = sum(1 for h in holidays if h["is_substitute"])
    analysis["patterns"]["substitute_days"] = {
        "count": substitute_count,
        "percentage": round((substitute_count / len(holidays)) * 100, 2) if holidays else 0
    }
    
    # Analyze bunting
    bunting_count = sum(1 for h in holidays if h["bunting"])
    analysis["patterns"]["bunting"] = {
        "count": bunting_count,
        "percentage": round((bunting_count / len(holidays)) * 100, 2) if holidays else 0
    }
    
    # Holiday titles frequency
    titles = Counter(h["title"].split()[0] for h in holidays)  # First word of title
    analysis["patterns"]["common_holiday_types"] = dict(titles.most_common(5))
    
    return analysis


@mcp.tool()
def get_bank_holiday_statistics(
    region: Optional[str] = None,
    year: Optional[int] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get comprehensive statistics about bank holidays.
    
    Args:
        region: Region to analyze (optional)
        year: Specific year to analyze (optional, defaults to all years)
        use_cache: Whether to use caching
        
    Returns:
        Dict containing comprehensive statistics
    """
    holidays_result = get_all_bank_holidays(region, use_cache)
    
    if holidays_result["status"] != "success":
        return holidays_result
    
    holidays = holidays_result["data"]
    
    if year:
        holidays = [h for h in holidays if h["year"] == year]
        if not holidays:
            return {
                "status": "success",
                "message": f"No holidays found for year {year}",
                "statistics": {}
            }
    
    stats = {
        "status": "success",
        "region": region or "all",
        "year": year or "all",
        "total_holidays": len(holidays),
        "statistics": {}
    }
    
    if not holidays:
        return stats
    
    # Basic counts
    stats["statistics"]["basic_counts"] = {
        "total": len(holidays),
        "with_bunting": sum(1 for h in holidays if h["bunting"]),
        "substitute_days": sum(1 for h in holidays if h["is_substitute"]),
        "years_covered": len(set(h["year"] for h in holidays))
    }
    
    # Monthly distribution
    monthly_dist = defaultdict(int)
    for holiday in holidays:
        month = int(holiday["date"].split("-")[1])
        monthly_dist[month] += 1
    
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    stats["statistics"]["monthly_distribution"] = {
        month_names[month-1]: count for month, count in monthly_dist.items()
    }
    
    # Weekday distribution
    weekday_dist = Counter(h["weekday"] for h in holidays)
    stats["statistics"]["weekday_distribution"] = dict(weekday_dist)
    
    # Year-over-year if multiple years
    if len(set(h["year"] for h in holidays)) > 1:
        yearly_counts = defaultdict(int)
        for holiday in holidays:
            yearly_counts[holiday["year"]] += 1
        stats["statistics"]["yearly_counts"] = dict(yearly_counts)
    
    # Common holiday names
    title_counts = Counter(h["title"] for h in holidays)
    stats["statistics"]["most_common_holidays"] = dict(title_counts.most_common(10))
    
    # Regional distribution (if all regions)
    if not region:
        regional_counts = defaultdict(int)
        for holiday in holidays:
            regional_counts[holiday["region"]] += 1
        stats["statistics"]["regional_distribution"] = dict(regional_counts)
    
    return stats


@mcp.tool()
def bank_holiday_business_impact(
    start_date: str,
    end_date: str,
    region: Optional[str] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Analyze business impact of bank holidays within a date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        region: Region to analyze (optional)
        use_cache: Whether to use caching
        
    Returns:
        Dict containing business impact analysis
    """
    if not _validate_date(start_date) or not _validate_date(end_date):
        return {
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM-DD format"
        }
    
    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)
    
    if start_dt >= end_dt:
        return {
            "status": "error",
            "message": "Start date must be before end date"
        }
    
    all_holidays_result = get_all_bank_holidays(region, use_cache)
    
    if all_holidays_result["status"] != "success":
        return all_holidays_result
    
    # Filter holidays within date range
    holidays_in_range = []
    for holiday in all_holidays_result["data"]:
        holiday_dt = _parse_date(holiday["date"])
        if start_dt <= holiday_dt <= end_dt:
            holidays_in_range.append({
                **holiday,
                "weekday_impact": "weekday" if holiday_dt.weekday() < 5 else "weekend"
            })
    
    # Calculate business days lost
    total_days = (end_dt - start_dt).days + 1
    weekdays_in_range = sum(1 for i in range(total_days) 
                           if (start_dt + timedelta(days=i)).weekday() < 5)
    
    weekday_holidays = [h for h in holidays_in_range if h["weekday_impact"] == "weekday"]
    
    analysis = {
        "status": "success",
        "period": {
            "start": start_date,
            "end": end_date,
            "total_days": total_days
        },
        "region": region or "all",
        "business_impact": {
            "total_holidays": len(holidays_in_range),
            "weekday_holidays": len(weekday_holidays),
            "weekend_holidays": len(holidays_in_range) - len(weekday_holidays),
            "total_weekdays": weekdays_in_range,
            "business_days_lost": len(weekday_holidays),
            "business_day_reduction_percentage": round((len(weekday_holidays) / weekdays_in_range) * 100, 2) if weekdays_in_range > 0 else 0
        },
        "holidays": holidays_in_range,
        "recommendations": []
    }
    
    # Add recommendations
    if len(weekday_holidays) > 0:
        analysis["recommendations"].append(f"Plan for {len(weekday_holidays)} business day(s) lost to bank holidays")
    
    if len(weekday_holidays) > 2:
        analysis["recommendations"].append("Consider spreading project deadlines around bank holiday periods")
    
    # Check for holiday clusters
    holiday_dates = [_parse_date(h["date"]) for h in holidays_in_range]
    for i, date in enumerate(holiday_dates[:-1]):
        if (holiday_dates[i+1] - date).days <= 7:
            analysis["recommendations"].append("Holiday cluster detected - plan for extended reduced productivity period")
            break
    
    return analysis


if __name__ == "__main__":
    mcp.run(transport="stdio")