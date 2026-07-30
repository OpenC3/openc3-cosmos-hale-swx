# Copyright 2026 OpenC3, Inc
# All Rights Reserved.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE.md for more details.

# This file may also be used under the terms of a commercial license
# if purchased from OpenC3, Inc.


from datetime import datetime, timezone

from openc3.conversions.conversion import Conversion


class ObservedDateConversion(Conversion):
    """Packet time from the document's own latest observed day.

    A CssiSpaceWeather document describes a specific day, which is not the day
    it was received. Reading an archived document, or replaying a set of them,
    otherwise stamps every packet with the wall clock time of the fetch, so the
    log holds three months of space weather all at one instant.

    An item named PACKET_TIME overrides the received time, so defining one with
    this conversion puts each packet on the log timeline at the day it actually
    describes, and Data Extractor, Telemetry Grapher and playback all line up.

    Falls back to the received time when the date is missing, which is what a
    fresh (all NUL) buffer looks like before a response has been parsed.
    """

    def __init__(self, item_name="OBSERVED_DATE"):
        super().__init__()
        self.item_name = item_name
        self.converted_type = "TIME"
        self.converted_bit_size = 0
        self.params = [item_name]

    def call(self, value, packet, buffer):
        try:
            date = packet.read(self.item_name, "CONVERTED", buffer)
        except Exception:
            date = None
        if not date:
            return packet.received_time or datetime.now(timezone.utc)
        try:
            # Dates are YYYY-MM-DD with no time of day; the document covers the
            # whole UTC day, so anchor it at midnight
            return datetime.strptime(str(date).strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return packet.received_time or datetime.now(timezone.utc)

    def __str__(self):
        return f"ObservedDateConversion {self.item_name}"

    def to_config(self, read_or_write):
        return f"    {read_or_write}_CONVERSION {self.__class__.__name__} {self.item_name}\n"
