"""Web UI for the AI Car Maintenance Predictor.

A thin Flask layer over the existing models/storage/predictor/service_config
modules -- no logic is duplicated here, it's the same engine the CLI uses.
Run with `python app.py` and open http://127.0.0.1:5000
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, Response

import storage
import service_config
from models import Vehicle, ServiceRecord, MileageSnapshot
from predictor import predict_all, compute_stats

app = Flask(__name__)
app.secret_key = "car-maintenance-dev-key"  # fine for a local single-user tool

DRIVING_CONDITIONS = ["Normal", "Harsh", "Light"]


def _garage():
    return storage.load_garage()


@app.route("/")
def dashboard():
    garage = _garage()
    vehicle = garage.active_vehicle()

    predictions = []
    stats = None
    if vehicle:
        intervals = service_config.load_intervals()
        predictions = predict_all(vehicle, intervals)
        stats = compute_stats(vehicle)

    return render_template(
        "index.html",
        garage=garage,
        vehicle=vehicle,
        predictions=predictions,
        stats=stats,
        conditions=DRIVING_CONDITIONS,
        service_types=list(service_config.load_intervals().keys()),
    )


@app.route("/setup", methods=["POST"])
def setup():
    garage = _garage()
    name = request.form["name"].strip()
    mileage = float(request.form["mileage"])
    condition = request.form.get("condition", "Normal")
    if condition not in DRIVING_CONDITIONS:
        condition = "Normal"

    vehicle = garage.vehicles.get(name, Vehicle(name=name))
    vehicle.current_mileage = mileage
    vehicle.driving_condition = condition
    vehicle.mileage_log.append(
        MileageSnapshot(mileage=mileage, date=datetime.now().strftime("%Y-%m-%d"))
    )
    garage.vehicles[name] = vehicle
    garage.active = name
    storage.save_garage(garage)
    flash(f"Saved {name} at {mileage:.0f} km.", "ok")
    return redirect(url_for("dashboard"))


@app.route("/switch", methods=["POST"])
def switch():
    garage = _garage()
    name = request.form["name"]
    if name in garage.vehicles:
        garage.active = name
        storage.save_garage(garage)
        flash(f"Switched to {name}.", "ok")
    return redirect(url_for("dashboard"))


@app.route("/mileage", methods=["POST"])
def mileage():
    garage = _garage()
    vehicle = garage.active_vehicle()
    if not vehicle:
        flash("Set up a vehicle first.", "error")
        return redirect(url_for("dashboard"))

    value = float(request.form["value"])
    if value < vehicle.current_mileage:
        flash("New reading is lower than the last one -- skipped.", "error")
        return redirect(url_for("dashboard"))

    vehicle.current_mileage = value
    vehicle.mileage_log.append(
        MileageSnapshot(mileage=value, date=datetime.now().strftime("%Y-%m-%d"))
    )
    storage.save_garage(garage)
    flash(f"Mileage updated to {value:.0f} km.", "ok")
    return redirect(url_for("dashboard"))


@app.route("/service", methods=["POST"])
def log_service():
    garage = _garage()
    vehicle = garage.active_vehicle()
    if not vehicle:
        flash("Set up a vehicle first.", "error")
        return redirect(url_for("dashboard"))

    service_name = request.form.get("service_select", "").strip()
    if service_name == "__custom__":
        service_name = request.form.get("custom_name", "").strip().title()
        km = request.form.get("custom_km")
        months = request.form.get("custom_months")
        if service_name and km and months:
            service_config.add_or_update_service(service_name, float(km), int(months))

    cost_raw = request.form.get("cost", "").strip()
    cost = float(cost_raw) if cost_raw else None
    notes = request.form.get("notes", "").strip()

    if not service_name:
        flash("Pick or name a service before logging it.", "error")
        return redirect(url_for("dashboard"))

    entry = ServiceRecord(
        service=service_name, mileage=vehicle.current_mileage,
        date=datetime.now().strftime("%Y-%m-%d"), cost=cost, notes=notes,
    )
    vehicle.service_log.append(entry)
    storage.save_garage(garage)
    flash(f"Logged {service_name} at {vehicle.current_mileage:.0f} km.", "ok")
    return redirect(url_for("dashboard"))


@app.route("/history")
def history():
    garage = _garage()
    vehicle = garage.active_vehicle()
    entries = sorted(vehicle.service_log, key=lambda e: e.mileage) if vehicle else []
    return render_template("history.html", garage=garage, vehicle=vehicle, entries=entries)


@app.route("/export")
def export():
    garage = _garage()
    vehicle = garage.active_vehicle()
    if not vehicle:
        flash("Set up a vehicle first.", "error")
        return redirect(url_for("dashboard"))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "mileage_km", "service", "cost", "notes"])
    for e in sorted(vehicle.service_log, key=lambda e: e.mileage):
        writer.writerow([e.date, e.mileage, e.service, e.cost or "", e.notes])

    filename = f"{vehicle.name.replace(' ', '_')}_service_history.csv"
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


if __name__ == "__main__":
    app.run(debug=True)
