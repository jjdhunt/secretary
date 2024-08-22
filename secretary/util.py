from datetime import datetime
import pytz
from typing import Annotated

def convert_time_to_iso8601(datetime_str: Annotated[str, 'datetime in YYYY-MM-DD HH:MM:SS +UTC_offset format']):
    # Try to convert the input string into a datetime. Will fail if it is not formatted as "YYYY-MM-DD HH:MM:SS +UTC"
    try:
        local = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S %z')
    except ValueError:
        return None
    
    # Convert to UTC
    utc_dt = local.astimezone(pytz.utc)
    
    # Format to ISO 8601
    return utc_dt.isoformat()