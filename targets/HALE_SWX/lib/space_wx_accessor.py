# Copyright 2026 OpenC3, Inc
# All Rights Reserved.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE.md for more details.

# This file may also be used under the terms of a commercial license
# if purchased from OpenC3, Inc.


from functools import lru_cache

from openc3.accessors.json_accessor import JsonAccessor, json_dumps, json_loads

# Fixed width column layout of a CssiSpaceWeather data line:
# FORMAT(I4,I3,I3,I5,I3,8I3,I4,8I4,I4,F4.1,I2,I4,F6.1,I2,5F6.1)
# See https://www.celestrak.com/SpaceData/SpaceWx-format.asp
KP_START = 18
KP_WIDTH = 3
AP_START = 46
AP_WIDTH = 4
SCALAR_FIELDS = [
    ("year", 0, 4, int),
    ("month", 4, 7, int),
    ("day", 7, 10, int),
    ("bsrn", 10, 15, int),
    ("nd", 15, 18, int),
    ("kp_sum", 42, 46, int),
    ("ap_avg", 78, 82, int),
    ("cp", 82, 86, float),
    ("c9", 86, 88, int),
    ("isn", 88, 92, int),
    ("f107_adj", 92, 98, float),
    ("q", 98, 100, int),
    ("ctr81_adj", 100, 106, float),
    ("lst81_adj", 106, 112, float),
    ("f107_obs", 112, 118, float),
    ("ctr81_obs", 118, 124, float),
    ("lst81_obs", 124, 130, float),
]
# Row values collected into per section arrays for plotting
SERIES_FIELDS = [
    "date",
    "kp_sum",
    "kp_avg",
    "ap_avg",
    "cp",
    "c9",
    "isn",
    "f107_adj",
    "ctr81_adj",
    "lst81_adj",
    "f107_obs",
    "ctr81_obs",
    "lst81_obs",
]


def _field(line, start, stop, cast):
    value = line[start:stop].strip()
    if not value:
        return None
    try:
        return cast(value)
    except ValueError:
        return None


def _parse_row(line):
    row = {name: _field(line, start, stop, cast) for name, start, stop, cast in SCALAR_FIELDS}
    if row["year"] is None or row["month"] is None or row["day"] is None:
        return None
    row["date"] = f"{row['year']:04d}-{row['month']:02d}-{row['day']:02d}"
    row["kp"] = [
        _field(line, KP_START + i * KP_WIDTH, KP_START + (i + 1) * KP_WIDTH, int) for i in range(8)
    ]
    row["ap"] = [
        _field(line, AP_START + i * AP_WIDTH, AP_START + (i + 1) * AP_WIDTH, int) for i in range(8)
    ]
    # Kp is reported multiplied by 10, so the daily sum of the 8 three hourly
    # values is divided by 80 to get the average true Kp index
    row["kp_avg"] = round(row["kp_sum"] / 80.0, 2) if row["kp_sum"] is not None else None
    return row


@lru_cache(maxsize=4)
def _parse(text):
    """Parses a CssiSpaceWeather document into a dict.

    Header keywords (DATATYPE, VERSION, UPDATED, ...) become lowercase keys.
    Each BEGIN / END block becomes a lowercase key holding count, rows, series
    and the first / latest row for convenient scalar access.
    """
    result = {"raw": text}
    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        keyword, _, remainder = stripped.partition(" ")
        keyword = keyword.upper()
        if keyword == "BEGIN":
            section = {"count": 0, "rows": [], "series": {name: [] for name in SERIES_FIELDS}}
            result[remainder.strip().lower()] = section
            continue
        if keyword == "END":
            section = None
            continue
        if section is not None:
            row = _parse_row(line)
            if row is None:
                continue
            section["rows"].append(row)
            for name in SERIES_FIELDS:
                section["series"][name].append(row[name])
            continue
        if keyword.startswith("NUM_"):
            continue  # Row counts are derived from the rows actually parsed
        result[keyword.lower()] = remainder.strip()

    for value in result.values():
        if isinstance(value, dict) and "rows" in value:
            value["count"] = len(value["rows"])
            value["first"] = value["rows"][0] if value["rows"] else {}
            value["latest"] = value["rows"][-1] if value["rows"] else {}
    return result


class SpaceWxAccessor(JsonAccessor):
    """Reads CssiSpaceWeather formatted text using JSONPath keys.

    The fixed width document is parsed into a dict and then the JsonAccessor
    JSONPath logic pulls out individual items, e.g. $.observed.latest.f107_obs

    Writes (e.g. inject_tlm) first rewrite the buffer as JSON, which _decode
    also understands, and then the stock JsonAccessor write logic applies.
    """

    @classmethod
    def class_read_item(cls, item, buffer):
        return super().class_read_item(item, cls._decode(buffer))

    @classmethod
    def class_read_items(cls, items, buffer):
        return super().class_read_items(items, cls._decode(buffer))

    @classmethod
    def class_write_item(cls, item, value, buffer):
        cls._jsonify(buffer)
        return super().class_write_item(item, value, buffer)

    @classmethod
    def class_write_items(cls, items, values, buffer):
        cls._jsonify(buffer)
        return super().class_write_items(items, values, buffer)

    @classmethod
    def _jsonify(cls, buffer):
        """Rewrites a CssiSpaceWeather text buffer as equivalent JSON in place."""
        if isinstance(buffer, bytearray):
            buffer[0:] = bytearray(json_dumps(cls._decode(buffer)), encoding="utf-8")

    @classmethod
    def _decode(cls, buffer):
        if isinstance(buffer, (bytes, bytearray)):
            text = bytes(buffer).decode(encoding="utf-8", errors="replace")
        elif isinstance(buffer, str):
            text = buffer
        else:
            return buffer  # Already parsed
        # A fresh packet buffer (e.g. from inject_tlm) is all NUL bytes
        text = text.strip("\x00")
        if text.lstrip().startswith("{"):
            return json_loads(text)  # Buffer was rewritten by a write
        return _parse(text)
