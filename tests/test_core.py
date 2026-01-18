# test_core.py
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    CL = compute_cl(weight, n, q, wing_area, cl_max)
    print("CL clipped:", CL)

    print("\n=== TEST: CD ===")
    CD = compute_cd(CD0, CL, AR, e, cg_drag_factor, gear_drag_factor)
    print("CD:", CD)

    print("\n=== TEST: Drag ===")
    D = compute_drag(q, wing_area, CD)
    print("Drag:", D)

    print("\n=== TEST: Thrust Available ===")
    T = compute_thrust_available(hp, V_kts, V_max_kts, T_static_factor)
    print("Thrust Available:", T)

    print("\n=== TEST: Ps ===")
    Ps = compute_ps_knots_per_sec(T, D, V, weight, gamma)
    print("Ps (kts/sec):", Ps)


def run_turn_physics_tests():
    """Test the new turn physics functions."""
    print("\n" + "=" * 50)
    print("TURN PHYSICS TESTS")
    print("=" * 50)

    # Test load factor
    print("\n=== TEST: Load Factor ===")
    n_45 = compute_load_factor(45)
    n_60 = compute_load_factor(60)
    print(f"Load factor at 45° bank: {n_45:.3f} G (expected: 1.414)")
    print(f"Load factor at 60° bank: {n_60:.3f} G (expected: 2.000)")
    assert abs(n_45 - 1.414) < 0.01, "45° bank load factor incorrect"
    assert abs(n_60 - 2.0) < 0.01, "60° bank load factor incorrect"

    # Test turn rate from bank angle
    print("\n=== TEST: Turn Rate from Bank ===")
    tr_45_100 = compute_turn_rate_from_bank(100, 45)
    print(f"Turn rate at 100 kts, 45° bank: {tr_45_100:.2f} °/s")
    # Expected: g * tan(45) / (100 * 1.68781) = 32.174 / 168.781 = 0.1906 rad/s = 10.9 °/s
    assert abs(tr_45_100 - 10.9) < 0.5, "Turn rate calculation incorrect"

    # Test turn radius
    print("\n=== TEST: Turn Radius ===")
    radius = compute_turn_radius(100, 45)
    print(f"Turn radius at 100 kts, 45° bank: {radius:.0f} ft")
    # Expected: V² / (g * tan(45)) = (168.781)² / 32.174 = 885 ft
    assert abs(radius - 885) < 10, "Turn radius calculation incorrect"

    # Test turn rate from load factor
    print("\n=== TEST: Turn Rate from Load Factor ===")
    tr_from_n = compute_turn_rate_from_load_factor(100, 2.0)  # 60° bank = 2G
    print(f"Turn rate at 100 kts, 2G: {tr_from_n:.2f} °/s")
    # Expected: g * sqrt(4-1) / V = 32.174 * 1.732 / 168.781 = 0.33 rad/s = 18.9 °/s
    assert abs(tr_from_n - 18.9) < 1.0, "Turn rate from load factor incorrect"

    print("\n✓ All turn physics tests passed!")


def run_atmosphere_tests():
    """Test atmospheric calculations."""
    print("\n" + "=" * 50)
    print("ATMOSPHERE TESTS")
    print("=" * 50)

    # Test density altitude
    print("\n=== TEST: Density Altitude ===")
    da = compute_density_altitude(5000, 30)  # 5000 ft PA, 30°C (hot day)
    isa_temp = 15 - (5000 * 0.0019812)  # ~5°C at 5000 ft
    expected_da = 5000 + 120 * (30 - isa_temp)  # ~8000 ft
    print(f"DA at 5000 ft PA, 30°C OAT: {da:.0f} ft (ISA temp: {isa_temp:.1f}°C)")
    assert da > 7000, "Density altitude should be high on hot day"

    # Test pressure altitude
    print("\n=== TEST: Pressure Altitude ===")
    pa = compute_pressure_altitude(1000, 29.42)  # 1000 ft field, low pressure
    print(f"PA at 1000 ft, 29.42 inHg: {pa:.0f} ft (expected: 1500 ft)")
    assert abs(pa - 1500) < 10, "Pressure altitude calculation incorrect"

    # Test TAS
    print("\n=== TEST: True Airspeed ===")
    tas = compute_true_airspeed(100, 8000)  # 100 KIAS at 8000 ft DA
    print(f"TAS at 100 KIAS, 8000 ft DA: {tas:.1f} kts")
    # At 8000 ft, TAS should be ~12-15% higher than IAS
    assert tas > 110 and tas < 120, "TAS calculation seems off"

    print("\n✓ All atmosphere tests passed!")


def run_stall_tests():
    """Test stall speed calculations."""
    print("\n" + "=" * 50)
    print("STALL SPEED TESTS")
    print("=" * 50)

    # Test accelerated stall
    print("\n=== TEST: Accelerated Stall Speed ===")
    vs_2g = compute_stall_speed_at_load_factor(50, 2.0)
    print(f"Stall speed at 2G (Vs0=50): {vs_2g:.1f} kts (expected: 70.7)")
    assert abs(vs_2g - 70.7) < 0.5, "Accelerated stall calculation incorrect"

    # Test interpolation
    print("\n=== TEST: Stall Speed Interpolation ===")
    stall_data = {"weights": [2000, 2300, 2550], "speeds": [47, 50, 53]}
    vs_2150 = interpolate_stall_speed(stall_data, 2150)
    print(f"Interpolated Vs at 2150 lbs: {vs_2150:.1f} kts")
    assert vs_2150 > 47 and vs_2150 < 50, "Interpolation seems off"

    print("\n✓ All stall tests passed!")


if __name__ == "__main__":
    run_test()
    run_turn_physics_tests()
    run_atmosphere_tests()
    run_stall_tests()
    print("\n" + "=" * 50)
    print("ALL TESTS PASSED!")
    print("=" * 50)
