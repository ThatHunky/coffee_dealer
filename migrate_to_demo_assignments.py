"""
Seed demo assignments for the current month (October 2025) with all solo and combo assignments.
Run this script to populate the database with visible assignments for emoji rendering tests.
"""

from datetime import date

from src.models import Assignment
from src.repo import repo

# October 2025
year = 2025
month = 10

# Demo assignments: solo and combos
demo_assignments = [
    # Solo
    Assignment.from_people(date(year, month, 1), ["diana"]),
    Assignment.from_people(date(year, month, 2), ["dana"]),
    Assignment.from_people(date(year, month, 3), ["zhenya"]),
    # Combos
    Assignment.from_people(date(year, month, 4), ["diana", "dana"]),
    Assignment.from_people(date(year, month, 5), ["diana", "zhenya"]),
    Assignment.from_people(date(year, month, 6), ["dana", "zhenya"]),
    # All three
    Assignment.from_people(date(year, month, 7), ["diana", "dana", "zhenya"]),
]

for a in demo_assignments:
    repo.upsert(a)
print("✅ Seeded demo assignments for October 2025.")
