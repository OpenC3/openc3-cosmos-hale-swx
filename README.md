# OpenC3 COSMOS Hale Space Weather Forecast plugin

<p align="center">
  <img src="public/store_img.png" alt="HaleSWx" width="480">
</p>


OpenC3 COSMOS plugin for the [HaleSWx](https://haleswx.com) space weather API. It
polls the `/forecast` and `/nowcast` endpoints, decodes the CelesTrak
`CssiSpaceWeather` documents they return into COSMOS telemetry, and ships screens
plus a custom widget for viewing the results.

## What you get

| Piece | Where |
|---|---|
| `GET_FORECAST` / `GET_NOWCAST` commands | `targets/HALE_SWX/cmd_tlm/cmd.txt` |
| `FORECAST_RESPONSE`, `NOWCAST_RESPONSE`, `ERROR_RESPONSE` packets | `targets/HALE_SWX/cmd_tlm/tlm.txt` and `_spacewx_response.txt` |
| COSMOS-native screen | `targets/HALE_SWX/screens/hale_swx.txt` |
| Custom widget screens | `targets/HALE_SWX/screens/forecast.txt`, `nowcast.txt` |
| Storm simulation script | `targets/HALE_SWX/procedures/solar_storm_test.py` |

## Install

1. Build the gem (needs `node` and `pnpm` for the widget):

   ```bash
   pnpm install
   rake build VERSION=1.0.0
   ```

   Or in the OpenC3 node container:

   ```bash
   docker run -it -v `pwd`:/openc3/local:z -w /openc3/local openc3inc/openc3-node sh
   /openc3/local $ pnpm install && rake build VERSION=1.0.0
   ```

2. Install the `.gem` through **Admin → Plugins**.

3. Create the API key secret in **Admin → Secrets**, named `HALE_API_KEY`, then
   connect the interface.

### Plugin variables

| Variable | Default | Purpose |
|---|---|---|
| `hale_target_name` | `HALE_SWX` | Target name |
| `hostname` | `api.haleswx.com` | API hostname |
| `protocol` | `https` | `http` or `https` |
| `port` | `443` | API port |
| `poll_period` | `12` | Hours between polls; `0` disables polling |

The interface sends `GET_FORECAST` and `GET_NOWCAST` on connect
(`OPTION CONNECT_CMD`) so a fresh install has data immediately, then repeats them
every `poll_period` hours via `OPTION PERIODIC_CMD`.

## The API key

The key is never written into the plugin configuration or the command log. It is
delivered as an environment variable by the `SECRET` keyword and added to the
request headers at send time by a write protocol:

```
PROTOCOL WRITE api_key_protocol.py X-API-KEY HALE_API_KEY
SECRET ENV HALE_API_KEY HALE_API_KEY
```

## Limits

`OBSERVED_AP_AVG` and `PREDICTED_AP_AVG` are limits checked:

```
LIMITS DEFAULT 1 ENABLED -2 -1 48 100
```

ap 48 is roughly Kp 5 (G1 storm) and ap 100 is roughly Kp 6.7 (G3), so yellow
means a storm is underway and red means a strong one.

## Testing without waiting for real space weather

`targets/HALE_SWX/procedures/solar_storm_test.py` walks a simulated storm from
quiet through G1, G3 and G5 and back, injecting both scalars and the 15-day
arrays with a pause between stages so the limits and charts can be watched.

Run it from Script Runner. Note that `inject_tlm` writes item values into the
packet buffer and `SpaceWxAccessor` is currently read-only, so the accessor needs
to accept writes before the script will run end to end.

## License

See [LICENSE.md](LICENSE.md).
