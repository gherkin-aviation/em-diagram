# core/calculations.py

"""
Centralized aerodynamic + performance calculations.
All Ps, drag, thrust, stall, turn rate, turn radius math lives here.
This makes the EM app modular, testable, and faster.
"""

# core/calculations.py
import numpy as np
import math

g = 32.174  # ft/s²

def compute_dynamic_pressure(rho, V):
    """q = 0.5 * rho * V^2"""
    return 0.5 * rho * (V ** 2)


def compute_cl(weight, load_factor, q, wing_area, cl_max):
    """
    CL = W * n / (q S) with clipping at CL_max.
    """
    if q <= 0:
        return 0.0
    CL = weight * load_factor / (q * wing_area)
    return min(CL, cl_max)


def compute_cd(CD0, CL, AR, e, cg_drag_factor=1.0, gear_drag_factor=1.0):
    """
    CD = (CD0 + CL^2 / (pi * AR * e)) * CG_factor * gear_factor
    """
    induced = (CL ** 2) / (math.pi * AR * e)
    CD = (CD0 + induced) * cg_drag_factor * gear_drag_factor
    return CD


def compute_drag(q, wing_area, CD):
    """D = q S CD"""
    return q * wing_area * CD


def compute_thrust_available(hp, V_kts, V_max_kts, T_static_factor):
    """
    T_static = T_static_factor * hp
    Thrust available decays quadratically with airspeed.
    """
    T_static = T_static_factor * hp
    V_fraction = np.clip(V_kts / V_max_kts, 0, 1)
    T_available = T_static * (1 - V_fraction ** 2)
    return max(T_available, 0)


def compute_ps_knots_per_sec(T, D, V, weight, gamma_deg):
    """
    Ps = ((T - D) * V / W - g * sin(gamma)) / 1.68781
    Returns Ps in knots/second
    """
    gamma = math.radians(gamma_deg)
    ps_fps = (T - D) * (V / weight) - g * math.sin(gamma)
    return ps_fps / 1.68781
