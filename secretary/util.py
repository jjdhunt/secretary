from datetime import datetime
import pytz
from typing import Annotated

def convert_time_to_iso8601(datetime_str: Annotated[str, 'datetime in YYYY-MM-DD HH:MM:SS +UTC_offset format']):
    # Try to convert the input string into a datetime. Will fail if it is not formatted as "YYYY-MM-DD HH:MM:SS +UTC"
    try:
        local = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S %z')
    except:
        return None
    
    # Convert to UTC
    utc_dt = local.astimezone(pytz.utc)
    
    # Format to ISO 8601
    return utc_dt.isoformat()

def convert_iso8601_to_local(utc_time_str, timezone_str):

    # Try to convert the input string into a datetime. Will fail if it is not formatted as ISO
    try:
        if utc_time_str.endswith('Z'):
            utc_time_str = utc_time_str[:-1] + '+00:00'
        utc_time = datetime.fromisoformat(utc_time_str)
    except:
        return None
    
    # Ensure the datetime object is aware (has timezone info)
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)

    # Convert to the specified local timezone
    local_tz = pytz.timezone(timezone_str)
    local_time = utc_time.astimezone(local_tz)

    # Format the local time as a string "YYYY-MM-DD HH:MM:SS +UTC"
    return local_time.strftime('%Y-%m-%d %H:%M:%S %z')