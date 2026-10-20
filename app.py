import os
import csv
import io
import logging
from dotenv import load_dotenv
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from automation import run_add_employee, fetch_employees

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=os.path.join("logs", "app.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

LAST_EMPLOYEES = []
LAST_STATUS = "Ready"
LAST_MESSAGE = "Fill the form and start an automation run."


@app.get("/")
def index():
    return render_template(
        "index.html",
        employees=LAST_EMPLOYEES,
        status=LAST_STATUS,
        message=LAST_MESSAGE,
    )


@app.post("/add-employee")
def add_employee():
    global LAST_EMPLOYEES, LAST_STATUS, LAST_MESSAGE
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    first_name = request.form.get("first_name", "").strip()
    middle_name = request.form.get("middle_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    employee_id = request.form.get("employee_id", "").strip()

    if not all([username, password, first_name, last_name]):
        flash("Username, password, first name and last name are required.", "error")
        return redirect(url_for("index"))

    LAST_STATUS = "Running"
    LAST_MESSAGE = "Automation is running. Please do not close the browser window."
    logging.info("Add employee automation requested for employee_id=%s", employee_id or "(auto)")
    try:
        result = run_add_employee(
            username=username,
            password=password,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            employee_id=employee_id,
        )
        LAST_STATUS = "Success" if result["success"] else "Failed"
        LAST_MESSAGE = result["message"]
        if result.get("success"):
            flash(LAST_MESSAGE, "success")
        else:
            flash(LAST_MESSAGE, "error")
        if result.get("employees") is not None:
            LAST_EMPLOYEES = result["employees"]
        logging.info("Automation result: %s", LAST_STATUS)
    except Exception as exc:
        LAST_STATUS = "Failed"
        LAST_MESSAGE = f"Automation error: {exc}"
        flash(LAST_MESSAGE, "error")
        logging.exception("Automation crashed")

    return redirect(url_for("index"))


@app.post("/fetch-employees")
def fetch_employee_list():
    global LAST_EMPLOYEES, LAST_STATUS, LAST_MESSAGE
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Please enter your username and password to fetch the employee list.", "error")
        return redirect(url_for("index"))

    LAST_STATUS = "Running"
    LAST_MESSAGE = "Fetching employee list from OrangeHRM..."
    try:
        result = fetch_employees(username, password)
        LAST_STATUS = "Success" if result["success"] else "Failed"
        LAST_MESSAGE = result["message"]
        flash(
            LAST_MESSAGE,
            "success" if result.get("success") else "error"
        )
        LAST_EMPLOYEES = result.get("employees", [])
        logging.info("Fetch employees result: %s; count=%s", LAST_STATUS, len(LAST_EMPLOYEES))
    except Exception as exc:
        LAST_STATUS = "Failed"
        LAST_MESSAGE = f"Fetch error: {exc}"
        flash(LAST_MESSAGE, "error")
        logging.exception("Employee list fetch crashed")
    return redirect(url_for("index"))


@app.get("/download-csv")
def download_csv():
    fieldnames = ["employee_id", "first_name", "last_name"]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for employee in LAST_EMPLOYEES:
        writer.writerow({
            "employee_id": employee.get("employee_id", ""),
            "first_name": employee.get("first_name", ""),
            "last_name": employee.get("last_name", "")
        })

    csv_data = output.getvalue()
    mem = io.BytesIO(csv_data.encode("utf-8-sig"))
    mem.seek(0)

    filename = f"employees_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
