# test_core.py
from core.calculations import *
import math

def run_test():
    # Example numbers pulled straight from app.py debug output
    rho = 0.00238       # slugs/ft3
    V = 150             # ft/s
    weight = 2000       # lbs
    n = 1.0             # load factor
    wing_area = 160
    CD0 = 0.03
    AR = 7.0
    e = 0.8
    cl_max = 1.5
    hp = 100
    V_kts = 88
    V_max_kts = 143
    T_static_factor = 2.6
    gamma = 0
    cg_drag_factor = 1.0
    gear_drag_factor = 1.0

    print("\n=== TEST: Dynamic Pressure ===")
    q = compute_dynamic_pressure(rho, V)
    print("q:", q)

    print("\n=== TEST: CL ===")
    CL = compute_lift_coefficient(weight, n, q, wing_area, cl_max)
    print("CL clipped:", CL)

    print("\n=== TEST: CD ===")
    CD = compute_drag_coefficient(CD0, CL, AR, e, cg_drag_factor, gear_drag_factor)
    print("CD:", CD)

    print("\n=== TEST: Drag ===")
    D = compute_drag(q, wing_area, CD)
    print("Drag:", D)

    print("\n=== TEST: Thrust Available ===")
    T = compute_thrust_available(hp, V_kts, V_max_kts, T_static_factor)
    print("Thrust Available:", T)

    print("\n=== TEST: Ps ===")
    Ps = compute_ps(T, D, V, weight, gamma)
    print("Ps (kts/sec):", Ps)


if __name__ == "__main__":
    run_test()
