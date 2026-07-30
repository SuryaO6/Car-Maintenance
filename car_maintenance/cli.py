"""Command-line interface: interactive menu (default) plus scriptable subcommands.

Run with no arguments for the original interactive menu experience.
Run with a subcommand (e.g. `python cli.py predict`) to script it / use in CI,
cron jobs, etc. -- something the original couldn't do at all.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime

import storage
import service_config
from models import Vehicle, ServiceRecord, MileageSnapshot
from predictor import predict_all, compute_stats

DRIVING_CONDITIONS = ["Normal", "Harsh", "Light"]


class Color:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"

    @staticmethod
    def wrap(text, code):
        if not sys.stdout.isatty():
            return text
        return f"{code}{text}{Color.END}"


STATUS_COLOR = {
    "overdue": Color.RED,
    "due_soon": Color.YELLOW,
    "ok": Color.GREEN,
    "no_record": Color.CYAN,
}


def require_vehicle(garage: storage.Garage):
    vehicle = garage.active_vehicle()
    if vehicle is None:
        print("No active vehicle. Set one up first (option 1 / `setup`).\n")
    return vehicle


def cmd_setup(garage: storage.Garage, name=None, mileage=None, condition=None):
    name = name or input("Car name/model: ").strip()
    mileage = float(mileage) if mileage is not None else float(input("Current odometer reading (km): "))

    if condition is None:
        print("Driving conditions:", ", ".join(DRIVING_CONDITIONS))
        condition = input("Mostly driving in which condition? ").strip().title()
    if condition not in DRIVING_CONDITIONS:
        print("Didn't recognize that, defaulting to 'Normal'.")
        condition = "Normal"

    vehicle = garage.vehicles.get(name, Vehicle(name=name))
    vehicle.current_mileage = mileage
    vehicle.driving_condition = condition
    vehicle.mileage_log.append(MileageSnapshot(mileage=mileage, date=datetime.now().strftime("%Y-%m-%d")))
    garage.vehicles[name] = vehicle
    garage.active = name
    storage.save_garage(garage)
    print(f"Saved {name} at {mileage:.0f} km, driving condition: {condition}.\n")


def cmd_switch(garage: storage.Garage, name: str):
    if name not in garage.vehicles:
        known = ", ".join(garage.vehicles) or "(none)"
        print(f"No vehicle named '{name}'. Known vehicles: {known}\n")
        return
    garage.active = name
    storage.save_garage(garage)
    print(f"Switched to {name}.\n")


def cmd_list_vehicles(garage: storage.Garage):
    if not garage.vehicles:
        print("No vehicles set up yet.\n")
        return
    print("\n----- Garage -----")
    for name, v in garage.vehicles.items():
        marker = " (active)" if name == garage.active else ""
        print(f"  {name}{marker}: {v.current_mileage:.0f} km, {v.driving_condition}")
    print("------------------\n")


def cmd_update_mileage(garage: storage.Garage, mileage=None):
    vehicle = require_vehicle(garage)
    if not vehicle:
        return
    mileage = float(mileage) if mileage is not None else float(input("New odometer reading (km): "))
    if mileage < vehicle.current_mileage:
        print("That's less than the last reading, are you sure? Skipping update.\n")
        return
    vehicle.current_mileage = mileage
    vehicle.mileage_log.append(MileageSnapshot(mileage=mileage, date=datetime.now().strftime("%Y-%m-%d")))
    storage.save_garage(garage)
    print(f"Mileage updated to {mileage:.0f} km.\n")


def cmd_log_service(garage: storage.Garage, service=None, cost=None, notes="", interactive=True):
    vehicle = require_vehicle(garage)
    if not vehicle:
        return

    intervals = service_config.load_intervals()
    if service is None:
        print("Service types:", ", ".join(intervals.keys()))
        service = input("Which service was done? ").strip().title()

    if service not in intervals and interactive:
        print(f"'{service}' isn't a known service type -- logging it as a custom entry.")
        add = input("Add it to the interval config too? (y/n): ").strip().lower()
        if add == "y":
            km = float(input("Interval in km: "))
            months = int(input("Interval in months: "))
            service_config.add_or_update_service(service, km, months)

    if cost is None and interactive:
        raw_cost = input("Cost (optional, press enter to skip): ").strip()
        cost = float(raw_cost) if raw_cost else None

    entry = ServiceRecord(
        service=service, mileage=vehicle.current_mileage,
        date=datetime.now().strftime("%Y-%m-%d"), cost=cost, notes=notes,
    )
    vehicle.service_log.append(entry)
    storage.save_garage(garage)
    print(f"Logged {service} at {vehicle.current_mileage:.0f} km.\n")


def cmd_view_history(garage: storage.Garage):
    vehicle = require_vehicle(garage)
    if not vehicle:
        return
    if not vehicle.service_log:
        print("No service history recorded yet.\n")
        return

    print(f"\n----- Service History: {vehicle.name} -----")
    for entry in sorted(vehicle.service_log, key=lambda e: e.mileage):
        cost_str = f"Rs.{entry.cost:.2f}" if entry.cost else "-"
        print(f"  {entry.date}  |  {entry.mileage:>8.0f} km  |  {entry.service:<20} |  {cost_str}")
    print("--------------------------------------\n")


def cmd_predict(garage: storage.Garage):
    vehicle = require_vehicle(garage)
    if not vehicle:
        return
    intervals = service_config.load_intervals()

    print(f"\n----- Maintenance Predictions for {vehicle.name} -----")
    print(f"(Driving condition: {vehicle.driving_condition})\n")

    for result in predict_all(vehicle, intervals):
        color = STATUS_COLOR.get(result.status, "")
        label = Color.wrap(result.service, Color.BOLD)
        print(f"{label}: {Color.wrap(result.message, color)}")

    print("\n--- Tips ---")
    if vehicle.driving_condition == "Harsh":
        print("Harsh driving conditions mean your intervals are tightened by 20%. "
              "Consider checking fluids more frequently than the numbers above suggest.")
    if not vehicle.service_log:
        print("No service history yet, log your first service to get more accurate predictions.")
    print("-------------------------------------------\n")


def cmd_stats(garage: storage.Garage):
    vehicle = require_vehicle(garage)
    if not vehicle:
        return
    stats = compute_stats(vehicle)
    print(f"\n----- Stats: {vehicle.name} -----")
    print(f"Total services logged: {stats['total_services']}")
    print(f"Total spent: Rs.{stats['total_spent']:.2f}")
    if stats["most_common_service"]:
        print(f"Most frequent service: {stats['most_common_service']}")
    for service, count in stats["service_counts"].items():
        print(f"  {service}: {count}x")
    print("----------------------------\n")


def cmd_export(garage: storage.Garage, path=None):
    vehicle = require_vehicle(garage)
    if not vehicle:
        return
    path = path or f"{vehicle.name.replace(' ', '_')}_service_history.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "mileage_km", "service", "cost", "notes"])
        for e in sorted(vehicle.service_log, key=lambda e: e.mileage):
            writer.writerow([e.date, e.mileage, e.service, e.cost or "", e.notes])
    print(f"Exported service history to {path}\n")


def interactive_menu():
    garage = storage.load_garage()

    menu = """===== AI Car Maintenance Predictor =====
1. Set up / update car info
2. Update current mileage
3. Log a completed service
4. View service history
5. Predict maintenance needs
6. View stats
7. Export history to CSV
8. List vehicles / switch active vehicle
9. Exit"""

    while True:
        print(menu)
        choice = input("Choose an option (1-9): ").strip()

        if choice == "1":
            cmd_setup(garage)
        elif choice == "2":
            cmd_update_mileage(garage)
        elif choice == "3":
            cmd_log_service(garage)
        elif choice == "4":
            cmd_view_history(garage)
        elif choice == "5":
            cmd_predict(garage)
        elif choice == "6":
            cmd_stats(garage)
        elif choice == "7":
            cmd_export(garage)
        elif choice == "8":
            cmd_list_vehicles(garage)
            name = input("Switch to (enter name, or blank to cancel): ").strip()
            if name:
                cmd_switch(garage, name)
        elif choice == "9":
            print("Bye! Your data has been saved.")
            break
        else:
            print("That's not a valid option, try again.\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Car Maintenance Predictor")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("setup", help="Set up or update a vehicle")
    p.add_argument("--name", required=True)
    p.add_argument("--mileage", required=True, type=float)
    p.add_argument("--condition", default="Normal")

    p = sub.add_parser("mileage", help="Update the active vehicle's mileage")
    p.add_argument("--value", required=True, type=float)

    p = sub.add_parser("service", help="Log a completed service")
    p.add_argument("--type", required=True)
    p.add_argument("--cost", type=float, default=None)
    p.add_argument("--notes", default="")

    sub.add_parser("history", help="View service history")
    sub.add_parser("predict", help="Predict upcoming maintenance")
    sub.add_parser("stats", help="View maintenance statistics")

    p = sub.add_parser("export", help="Export history to CSV")
    p.add_argument("--path", default=None)

    p = sub.add_parser("switch", help="Switch the active vehicle")
    p.add_argument("--name", required=True)

    sub.add_parser("list", help="List all vehicles in the garage")

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.command:
        interactive_menu()
        return

    garage = storage.load_garage()

    if args.command == "setup":
        cmd_setup(garage, name=args.name, mileage=args.mileage, condition=args.condition)
    elif args.command == "mileage":
        cmd_update_mileage(garage, mileage=args.value)
    elif args.command == "service":
        cmd_log_service(garage, service=args.type, cost=args.cost, notes=args.notes, interactive=False)
    elif args.command == "history":
        cmd_view_history(garage)
    elif args.command == "predict":
        cmd_predict(garage)
    elif args.command == "stats":
        cmd_stats(garage)
    elif args.command == "export":
        cmd_export(garage, path=args.path)
    elif args.command == "switch":
        cmd_switch(garage, args.name)
    elif args.command == "list":
        cmd_list_vehicles(garage)


if __name__ == "__main__":
    main()
