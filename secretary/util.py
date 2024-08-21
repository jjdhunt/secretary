from datetime import datetime
import pytz
from typing import Annotated

def convert_time_to_iso8601(datetime_str: Annotated[str, 'datetime in YYYY-MM-DD HH:MM:SS format'],
                            timezone_str):
    # Try to convert the input string into a datetime. Will fail if it is not formatted as "YYYY-MM-DD HH:MM:SS"
    try:
        local = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    # Set the timezone for the datetime object
    local = pytz.timezone(timezone_str).localize(local)
    
    # Convert to UTC
    utc_dt = local.astimezone(pytz.utc)
    
    # Format to ISO 8601
    return utc_dt.isoformat()
