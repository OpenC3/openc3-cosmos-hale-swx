# Copyright 2026 OpenC3, Inc
# All Rights Reserved.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE.md for more details.

# This file may also be used under the terms of a commercial license
# if purchased from OpenC3, Inc.

import os

from openc3.interfaces.protocols.protocol import Protocol
from openc3.utilities.logger import Logger


class ApiKeyProtocol(Protocol):
    """Injects the HaleSWx API key into every outgoing HTTP request.

    The SECRET keyword in plugin.txt delivers the key through an environment
    variable. Injection uses private copies of the request metadata and headers
    so it does not add the key to the command packet's logged extra fields.
    """

    def __init__(self, header="X-API-KEY", env_var="HALE_API_KEY", allow_empty_data=None):
        super().__init__(allow_empty_data)
        self.header = header
        self.env_var = env_var
        self.warned = False

    # HTTP conversion can return the packet's shared extra dictionary. Command
    # logging happens after the write, so copy both dictionaries we modify.
    def write_data(self, data, extra=None):
        api_key = os.environ.get(self.env_var)
        if api_key:
            extra = dict(extra or {})
            headers = dict(extra.get("HTTP_HEADERS") or {})
            extra["HTTP_HEADERS"] = headers
            headers[self.header] = api_key
        elif not self.warned:
            # Only warn once to avoid flooding the log on every periodic command
            self.warned = True
            Logger.warn(
                f"ApiKeyProtocol: {self.env_var} is not set. "
                "Create the secret in Admin / Secrets and restart the interface."
            )
        return super().write_data(data, extra)
