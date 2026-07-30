# Injects a simulated solar storm into the HALE_SWX telemetry packets so the
# limits, the native screen and the HALESWX widget charts can be exercised
# without waiting on real space weather.
#
# Run from Script Runner. Each stage pauses so the screens can be watched, and
# the last stage puts the values back where they started.
#
# The ap limits under test come from cmd_tlm/_spacewx_response.txt:
#   LIMITS DEFAULT 1 ENABLED -2 -1 48 100
# so ap 48 is yellow (~Kp 5, G1) and ap 100 is red (~Kp 6.7, G3).
#
# Each stage is dated a day later than the one before it. PACKET_TIME is derived
# from OBSERVED_DATE, so stages that all carried the same date would land on one
# instant in the logs and the historical tools would keep only the last of them.

from datetime import datetime, timedelta, timezone

TARGET = "HALE_SWX"
PACKETS = ["FORECAST_RESPONSE", "NOWCAST_RESPONSE"]
DAYS = 15
STAGE_WAIT = 20  # Seconds to hold each stage so the screens can be compared

# name, ap, Kp, F10.7 (sfu), sunspot number
STAGES = [
    ("Quiet sun", 6, 1.75, 143.3, 109),
    ("Active, below storm level", 22, 4.00, 190.0, 140),
    ("G1 minor storm - ap crosses yellow", 56, 5.33, 235.0, 175),
    ("G3 strong storm - ap crosses red", 120, 7.00, 305.0, 220),
    ("G5 extreme storm", 300, 8.67, 410.0, 290),
    ("Back to quiet", 6, 1.75, 143.3, 109),
]


def ramp(end, start_fraction=0.35):
    """A DAYS long series climbing to end, so the charts show a rising event
    rather than a flat line at the new value."""
    start = end * start_fraction
    step = (end - start) / (DAYS - 1)
    return [round(start + step * i, 2) for i in range(DAYS)]


def flat(value):
    return [value] * DAYS


def days_from(first):
    return [(first + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(DAYS)]


def inject_stage(packet, ap, kp, f107, isn, latest):
    # The observed window ends on the stage's own day and the forecast picks up
    # the day after, the same shape a real document has
    observed_dates = days_from(latest - timedelta(days=DAYS - 1))
    predicted_dates = days_from(latest + timedelta(days=1))
    inject_tlm(
        TARGET,
        packet,
        {
            # Dates place the packet on the log timeline and give the charts and
            # the widget table their x axis
            "OBSERVED_DATE": observed_dates[-1],
            "PREDICTED_DATE": predicted_dates[0],
            "OBSERVED_DATES": observed_dates,
            "PREDICTED_DATES": predicted_dates,
            "OBSERVED_POINTS": DAYS,
            "PREDICTED_POINTS": DAYS,
            # Scalars drive the tiles, the LABELVALUEs and the ap limits
            "OBSERVED_AP_AVG": ap,
            "OBSERVED_KP_AVG": kp,
            "OBSERVED_F107_OBS": f107,
            "OBSERVED_F107_ADJ": round(f107 * 1.03, 1),
            "OBSERVED_ISN": isn,
            "PREDICTED_AP_AVG": ap,
            "PREDICTED_KP_AVG": kp,
            "PREDICTED_F107_OBS": f107,
            "PREDICTED_ISN": isn,
            # Arrays drive the ARRAYPLOTs and the widget's line and bar charts
            "OBSERVED_AP_AVGS": ramp(ap),
            "OBSERVED_KP_AVGS": ramp(kp),
            "OBSERVED_F107_OBSS": ramp(f107),
            "OBSERVED_ISNS": ramp(isn),
            "PREDICTED_AP_AVGS": flat(ap),
            "PREDICTED_KP_AVGS": flat(kp),
            "PREDICTED_F107_OBSS": flat(f107),
            "PREDICTED_ISNS": flat(isn),
        },
    )


start = datetime.now(timezone.utc).date()
for stage, (name, ap, kp, f107, isn) in enumerate(STAGES):
    latest = start + timedelta(days=stage)
    for packet in PACKETS:
        inject_stage(packet, ap, kp, f107, isn, latest)
    print(f"{name} ({latest}): ap={ap} nT, Kp={kp}, F10.7={f107} sfu, ISN={isn}")
    # get_tlm_values returns [value, limits_state] per item
    value, limits_state = get_tlm_values([f"{TARGET}__{PACKETS[0]}__OBSERVED_AP_AVG__CONVERTED"])[0]
    print(f"  OBSERVED_AP_AVG is {value} nT, limits state {limits_state}")
    wait(STAGE_WAIT)

print("Done. The injected values stay in the CVT until the next real poll,")
print(f"or send {TARGET} GET_FORECAST / GET_NOWCAST to refetch immediately.")
print(f"In the historical tools the stages run {start} to {start + timedelta(days=len(STAGES) - 1)}.")
