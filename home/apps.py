from django.apps import AppConfig
from datetime import datetime, timedelta
import pytz

import logging
logger = logging.getLogger(__name__)



class HomeConfig(AppConfig):
    name = 'home'

def convert_utc_to_local(utc_time, timezone_offset):
    """
    Converts UTC datetime to local time using the provided timezone offset.

    Args:
        utc_time (datetime): The UTC datetime to convert.
        timezone_offset (str): The timezone offset in the format ±HHMM (e.g., '-0500').

    Returns:
        datetime: The adjusted local datetime.
    """
    logger.debug("Time conversion is in progress")
    if not utc_time or not timezone_offset:
        logger.debug("utc_time or timezone_offset is not present here")
        return utc_time

    # Determine the sign of the offset
    sign = 1 if timezone_offset[0] == '+' else -1
    hours = int(timezone_offset[1:3])
    minutes = int(timezone_offset[3:5])
    offset = timedelta(hours=hours, minutes=minutes)

    # Apply the correct operation based on the sign
    if sign == 1:
        local_time = utc_time + offset
    else:
        local_time = utc_time - offset

    logger.debug(f"UTC: {utc_time} | Offset: {timezone_offset} | Local: {local_time}")
    return local_time