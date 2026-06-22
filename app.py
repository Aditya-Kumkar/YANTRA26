import streamlit as st
import numpy as np
from sklearn.metrics import r2_score

st.set_page_config(page_title="AI Lightweight Optimizer", layout="wide")
st.title("Optimized Beam Designer")

st.markdown("Design the lightest possible beam that **doesn't break, bend too much, or buckle**.")

# -------------------------------------------------
# MATERIAL DATABASE
# -------------------------------------------------

materials = {
    "Aluminum": {"E": 69e9, "yield": 275e6, "density": 2700},
    "Titanium": {"E": 110e9, "yield": 880e6, "density": 4430},
    "Composite": {"E": 140e9, "yield": 600e6, "density": 1600},
}

# -------------------------------------------------
# SIDEBAR SETTINGS
# -------------------------------------------------

st.sidebar.header("Design Settings")

material_choice = st.sidebar.selectbox("Material", list(materials.keys()))
beam_type = st.sidebar.selectbox(
    "Beam Type",
    ["Cantilever", "Simply Supported", "Fixed-Fixed"]
)

cross_section = st.sidebar.selectbox(
    "Cross Section",
    ["Rectangular", "I-Beam"]
)

F = st.sidebar.number_input("Load (N)", 100, 10000, 1000, step=50)
L = st.sidebar.number_input("Length (m)", 0.1, 3.0, 0.2, step=0.05)
FOS = st.sidebar.number_input("Factor of Safety", 1, 5, 4, step=1)
max_deflection = st.sidebar.number_input(
    "Max Deflection (mm)", 0.1, 20.0, 0.8, step=0.1
) / 1000

# Fix dimensions
fix_dims = st.sidebar.checkbox("Fix Any Dimensions?")
fixed = {}

if fix_dims:

    if cross_section == "Rectangular":
        options = st.sidebar.multiselect(
            "Select Dimensions to Fix",
            ["Thickness (mm)", "Height (mm)"]
        )

        if "Thickness (mm)" in options:
            fixed["t"] = st.sidebar.number_input(
                "Thickness (mm)", 1.0, 100.0, 10.0
            ) / 1000

        if "Height (mm)" in options:
            fixed["h"] = st.sidebar.number_input(
                "Height (mm)", 10.0, 500.0, 50.0
            ) / 1000

    else:
        options = st.sidebar.multiselect(
            "Select Dimensions to Fix",
            [
                "Total Height (mm)",
                "Web Thickness (mm)",
                "Flange Thickness (mm)",
                "Flange Width (mm)"
            ]
        )

        if "Total Height (mm)" in options:
            fixed["h"] = st.sidebar.number_input(
                "Total Height (mm)", 20.0, 500.0, 100.0
            ) / 1000

        if "Web Thickness (mm)" in options:
            fixed["tw"] = st.sidebar.number_input(
                "Web Thickness (mm)", 1.0, 50.0, 5.0
            ) / 1000

        if "Flange Thickness (mm)" in options:
            fixed["tf"] = st.sidebar.number_input(
                "Flange Thickness (mm)", 1.0, 50.0, 8.0
            ) / 1000

        if "Flange Width (mm)" in options:
            fixed["bf"] = st.sidebar.number_input(
                "Flange Width (mm)", 10.0, 500.0, 80.0
            ) / 1000

# -------------------------------------------------
# MATERIAL PROPERTIES
# -------------------------------------------------

props = materials[material_choice]
E = props["E"]
yield_strength = props["yield"]
rho = props["density"]
allowable_stress = yield_strength / FOS

# -------------------------------------------------
# SECTION PROPERTIES
# -------------------------------------------------

def rectangular_section(t, h):
    I = (t * h**3) / 12
    area = t * h
    return I, area

def ibeam_section(h, tw, tf, bf):

    if 2*tf >= h:
        return None, None

    web_height = h - 2*tf

    I_web = (tw * web_height**3) / 12
    I_flange = 2 * (
        (bf * tf**3) / 12 +
        bf * tf * ((h/2 - tf/2)**2)
    )

    I = I_web + I_flange
    area = (tw * web_height) + 2 * (bf * tf)

    return I, area

# -------------------------------------------------
# BEAM PHYSICS
# -------------------------------------------------

def beam_response(I, area, h):

    if beam_type == "Cantilever":
        M = F * L
        deflection = (F * L**3) / (3 * E * I)
        K = 2

    elif beam_type == "Simply Supported":
        M = F * L / 4
        deflection = (F * L**3) / (48 * E * I)
        K = 1

    else:
        M = F * L / 8
        deflection = (F * L**3) / (192 * E * I)
        K = 0.5

    c = h / 2
    stress = (M * c) / I

    volume = area * L
    weight = rho * volume
    Pcr = (np.pi**2 * E * I) / ((K * L)**2)

    stress_ratio = stress / allowable_stress
    defl_ratio = deflection / max_deflection
    buckling_ratio = (F * FOS) / Pcr

    safe = (stress_ratio <= 1) and \
           (defl_ratio <= 1) and \
           (buckling_ratio <= 1)

    governing = max(
        [("Stress", stress_ratio),
         ("Deflection", defl_ratio),
         ("Buckling", buckling_ratio)],
        key=lambda x: x[1]
    )[0]

    return {
        "stress": stress,
        "deflection": deflection,
        "volume": volume,
        "weight": weight,
        "stress_ratio": stress_ratio,
        "defl_ratio": defl_ratio,
        "buckling_ratio": buckling_ratio,
        "governing": governing,
        "safe": safe
    }

# -------------------------------------------------
# OPTIMIZATION
# -------------------------------------------------

best = None
best_weight = float("inf")

if cross_section == "Rectangular":

    t_range = [fixed["t"]] if "t" in fixed else np.linspace(0.002, 0.02, 30)
    h_range = [fixed["h"]] if "h" in fixed else np.linspace(0.03, 0.2, 30)

    for t in t_range:
        for h in h_range:
            I, area = rectangular_section(t, h)
            result = beam_response(I, area, h)

            if result["safe"] and result["weight"] < best_weight:
                best_weight = result["weight"]
                best = {"t": t, "h": h, **result}

else:

    h_range  = [fixed["h"]]  if "h"  in fixed else np.linspace(0.05, 0.3, 15)
    tw_range = [fixed["tw"]] if "tw" in fixed else np.linspace(0.003, 0.02, 15)
    tf_range = [fixed["tf"]] if "tf" in fixed else np.linspace(0.005, 0.03, 15)
    bf_range = [fixed["bf"]] if "bf" in fixed else np.linspace(0.02, 0.3, 15)

    for h in h_range:
        for tw in tw_range:
            for tf in tf_range:
                for bf in bf_range:

                    I, area = ibeam_section(h, tw, tf, bf)
                    if I is None:
                        continue

                    result = beam_response(I, area, h)

                    if result["safe"] and result["weight"] < best_weight:
                        best_weight = result["weight"]
                        best = {"h": h, "tw": tw, "tf": tf, "bf": bf, **result}

if best is None:
    st.error("No feasible design found.")
    st.stop()

# -------------------------------------------------
# RESULTS
# -------------------------------------------------

st.metric("Optimized Weight", f"{best['weight']:.3f} kg")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Optimized Geometry")

    if cross_section == "Rectangular":
        st.write(f"Thickness: {best['t']*1000:.2f} mm")
        st.write(f"Height: {best['h']*1000:.2f} mm")
    else:
        st.write(f"Total Height: {best['h']*1000:.2f} mm")
        st.write(f"Web Thickness: {best['tw']*1000:.2f} mm")
        st.write(f"Flange Thickness: {best['tf']*1000:.2f} mm")
        st.write(f"Flange Width: {best['bf']*1000:.2f} mm")

    st.write(f"Volume: {best['volume']:.6f} m³")

with col2:
    st.subheader("Performance Metrics")
    st.write(f"Stress: {best['stress']/1e6:.2f} MPa")
    st.write(f"Deflection: {best['deflection']*1000:.2f} mm")
    st.write(f"Governing Constraint: {best['governing']}")

# -------------------------------------------------
# UTILIZATION WARNINGS
# -------------------------------------------------

max_ratio = max(
    best["stress_ratio"],
    best["defl_ratio"],
    best["buckling_ratio"]
)

if max_ratio > 1:
    st.error("Design is unsafe.")
elif max_ratio > 0.9:
    st.warning("Design very close to failure.")
elif max_ratio > 0.75:
    st.info("Design approaching limits.")






