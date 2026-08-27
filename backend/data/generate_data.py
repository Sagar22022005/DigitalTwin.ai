"""
data/generate_data.py — Generates 7 days of synthetic telemetry by running
the SimPy simulator with periodic fault injection for model training.

Run: python data/generate_data.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.assembly_line import AssemblyLineSimulation, DB_PATH

if __name__ == "__main__":
    print("=" * 60)
    print("AI AssemblyTwin — Historical Data Generator")
    print("=" * 60)

    # Clean slate
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Cleared existing DB: {DB_PATH}")

    sim = AssemblyLineSimulation(speed_multiplier=200.0)  # 200x faster than real time

    # Inject faults mid-generation for training variety
    # Day 3: bottleneck at station 12
    sim.inject_fault("bottleneck", 12)
    sim.run_historical(days=2)
    sim.reset()

    # Day 5: defect at station 7
    sim.inject_fault("defect", 7)
    sim.run_historical(days=2)
    sim.reset()

    # Days 6-7: normal operation
    sim.run_historical(days=3)

    print("\nData generation complete.")
    print(f"DB location: {DB_PATH}")
    print("Next: python data/train_models.py")
