
import gpxpy
import gpxpy.gpx
from math import radians, sin, cos, sqrt, atan2, ceil
import streamlit as st

def haversine_distance(p1, p2):
    R = 6371
    lat1, lon1 = p1.latitude, p1.longitude
    lat2, lon2 = p2.latitude, p2.longitude
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def round_quarter_hour(hours):
    return round((hours * 4 + 0.9999) // 1) / 4

def round_up_km(km):
    return ceil(km)

def fmt_hm(hours):
    h = int(hours)
    m = int(round((hours - h) * 60))
    return f"{h}h {m}m" if h or m else "0h"

def generate_advanced_training_plan(total_distance, weeks, days_per_week=5, include_strength=True, by="km"):
    plan = []
    phases = ["Base"] * (weeks//4) + ["Build"] * (weeks//4*2) + ["Peak"] * (weeks//4) + ["Taper"] * (weeks - (weeks//4*4))
    while len(phases) < weeks: phases.append("Taper")

    if by == "hours":
        if total_distance <= 50:
            peak_weekly_volume = 7
        elif total_distance <= 100:
            peak_weekly_volume = 10
        elif total_distance <= 160:
            peak_weekly_volume = 13
        else:
            peak_weekly_volume = 15
    else:
        peak_weekly_volume = total_distance * 0.85

    for week in range(1, weeks+1):
        phase = phases[week-1]
        if phase == "Base":
            week_factor = 0.6 + 0.05*(week%4)
        elif phase == "Build":
            week_factor = 0.75 + 0.05*(week%4)
        elif phase == "Peak":
            week_factor = 0.95
        else:
            taper_factors = [0.7,0.5,0.3]
            week_factor = taper_factors[min(week-1,2)] if week-1 < len(taper_factors) else 0.3

        week_volume = peak_weekly_volume * week_factor
        long_run_sat = week_volume * 0.4
        long_run_sun = week_volume * 0.25
        remaining_volume = week_volume - (long_run_sat + long_run_sun)

        # rounding
        if by == "hours":
            week_volume = round_quarter_hour(week_volume)
            long_run_sat = round_quarter_hour(long_run_sat)
            long_run_sun = round_quarter_hour(long_run_sun)
            remaining_volume = week_volume - (long_run_sat + long_run_sun)
        else:
            week_volume = round_up_km(week_volume)
            long_run_sat = round_up_km(long_run_sat)
            long_run_sun = round_up_km(long_run_sun)
            remaining_volume = week_volume - (long_run_sat + long_run_sun)

        day_layout = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        days = []
        for day in day_layout:
            if day == "Sat":
                desc = fmt_hm(long_run_sat) if by=="hours" else f"{long_run_sat} km"
                days.append(f"{day}: Long run ~{desc}")
            elif day == "Sun":
                desc = fmt_hm(long_run_sun) if by=="hours" else f"{long_run_sun} km"
                days.append(f"{day}: Long run ~{desc} (back-to-back)")
            elif day in ["Tue","Thu"]:
                mid_vol = remaining_volume * 0.25
                if by == "hours":
                    mid_vol = round_quarter_hour(mid_vol)
                else:
                    mid_vol = round_up_km(mid_vol)
                quality = "Workout (hills/tempo)" if phase in ["Build","Peak"] and week%2==0 else "Moderate run"
                desc = fmt_hm(mid_vol) if by=="hours" else f"{mid_vol} km"
                days.append(f"{day}: {quality} ~{desc}")
            elif day == "Wed" and days_per_week > 5:
                mid_vol = remaining_volume * 0.2
                if by == "hours":
                    mid_vol = round_quarter_hour(mid_vol)
                else:
                    mid_vol = round_up_km(mid_vol)
                desc = fmt_hm(mid_vol) if by=="hours" else f"{mid_vol} km"
                days.append(f"{day}: Easy run ~{desc}")
            elif day in ["Mon","Fri"] and include_strength:
                days.append(f"{day}: Strength / cross-training")
            else:
                days.append(f"{day}: Rest or short walk")

        plan.append({
            "Week": week,
            "Phase": phase,
            "Total": fmt_hm(week_volume) if by=="hours" else week_volume,
            "Long runs": f"{fmt_hm(long_run_sat)} + {fmt_hm(long_run_sun)}" if by=="hours" else f"{long_run_sat} + {long_run_sun} km",
            "Plan": days
        })
    return plan

st.title("Ultra Pacing & Advanced Training Plan")

uploaded_file = st.file_uploader("Upload your GPX file", type=["gpx"])
use_default = False
total_dist = 0

if uploaded_file is not None:
    gpx = gpxpy.parse(uploaded_file)
    points = [pt for tr in gpx.tracks for seg in tr.segments for pt in seg.points]
    total_dist = sum([haversine_distance(points[i], points[i+1]) for i in range(len(points)-1)])
else:
    race_choice = st.selectbox("Or pick a default race distance:",
        ["Marathon (42.2 km)", "Half Marathon (21.1 km)", "50 km Ultra",
         "100 km Ultra", "50 Mile Ultra (80 km)", "100 Mile Ultra (160 km)"])
    if race_choice.startswith("Marathon"):
        total_dist = 42.2
    elif race_choice.startswith("Half"):
        total_dist = 21.1
    elif race_choice.startswith("50 km"):
        total_dist = 50
    elif race_choice.startswith("100 km"):
        total_dist = 100
    elif race_choice.startswith("50 Mile"):
        total_dist = 80
    elif race_choice.startswith("100 Mile"):
        total_dist = 160
    use_default = True

mode = st.radio("Choose planning feature:", ("Pacing Plan","Advanced Training Plan"))

if mode == "Pacing Plan":
    legs = [(total_dist, 0)]
    submode = st.radio("Choose pacing mode:", ("Set target finish time","Set target pace"))
    if submode == "Set target finish time":
        target_time = st.number_input("Target Finish Time (hours)", value=5.0)
        if st.button("Generate Pacing Strategy"):
            plan, total_time = compute_leg_paces_by_time(legs, target_time)
            st.table(plan)
            st.success(f"Estimated Finish Time: {round(total_time,2)} hours")
    else:
        target_pace = st.number_input("Target Average Pace (min/km)", value=6.0)
        if st.button("Generate Pacing Strategy"):
            plan, total_time = compute_leg_times_by_pace(legs, target_pace)
            st.table(plan)
            st.success(f"Estimated Total Time: {round(total_time,2)} hours")
else:
    by_mode = st.radio("Plan by:", ("Distance (km)","Time (hours)"))
    by = "km" if by_mode == "Distance (km)" else "hours"
    weeks = st.number_input("Number of weeks to train", min_value=4, max_value=52, value=16, step=1)
    days_per_week = st.number_input("Days per week", min_value=3, max_value=7, value=5, step=1)
    include_strength = st.checkbox("Include 1-2 strength days", value=True)
    if st.button("Generate Advanced Training Plan"):
        plan = generate_advanced_training_plan(total_dist, weeks, days_per_week, include_strength, by)
        for week in plan:
            st.markdown(f"### Week {week['Week']} ({week['Phase']})")
            st.markdown(f"**Total {by}:** {week['Total']} &nbsp;&nbsp; **Long runs:** {week['Long runs']}")
            for day in week["Plan"]:
                st.write(f"- {day}")
