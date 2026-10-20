# OrangeHRM RPA Dashboard

## 1. Clone the Repository

```bash
git clone <repository-url>
cd OrangeHRM_RPA_Dashboard
```

Replace `<repository-url>` with your Git repository URL.

## 2. Install Packages

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `python` does not work, try `py`.

## 3. Configure Environment Variables

Create a file named .env in the project root directory, alongside app.py and automation.py.

Add the following configuration:

```env
FLASK_SECRET_KEY=paste-your-generated-key-here
ORANGEHRM_BASE_URL=https://opensource-demo.orangehrmlive.com/

FLASK_SECRET_KEY — Used by Flask to secure session data.

ORANGEHRM_BASE_URL — Specifies the OrangeHRM website URL.


## 3. Run the Application

```bash
python app.py
```

Open the dashboard in your browser:

`http://127.0.0.1:5000`

## 4. Folder Structure

```text
OrangeHRM_RPA_Dashboard/
├── app.py
├── automation.py
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   └── style.css
├── logs/
│    ├── app.log
│    └── automation.log
├── exports/
│   └── employees.csv
└── screenshots/
    ├── Dashboard_before_automation.png
    ├── Dashboard_after_automation.png
    └── Employee_list_after_automation.png
```

- `app.py` — Flask dashboard and application routes.
- `automation.py` — Selenium automation, employee verification, pagination, logging, error handling, and CSV export.
- `requirements.txt` — Required Python packages.
- `templates/index.html` — Dashboard HTML.
- `static/style.css` — Dashboard styling.
- `logs/` — Application and automation logs.
- `exports/` — Generated employee CSV file.
- `screenshots/` — Screenshots saved manually.

## 5. How It Works

1. Enter your OrangeHRM username and password in the dashboard.
2. To add an employee, enter the first name, last name, and optional middle name and employee ID. Click **Start Automation**.
3. Selenium opens Chrome, logs in, navigates to PIM, and submits the employee form.
4. The automation checks form validation errors and verifies the saved first, middle, and last names.
5. It fetches employee records and attempts to navigate through the available pagination pages.
6. Retrieved records are exported to `exports/employees.csv` when records are available.
7. Click **Fetch / Refresh** to fetch the employee list without adding an employee.
8. Click **CSV** to download the employee records currently loaded in the dashboard.

## 6. Error Handling and Logs

The application handles:

- Missing required form fields.
- Page and element timeouts.
- Selenium WebDriver errors.
- Employee form validation errors.
- Employee name verification failures.
- CSV export and unexpected automation errors.

Log files:

- `logs/app.log` — Application logs.
- `logs/automation.log` — Automation logs.

If an error occurs, check the relevant log file for details.