import logging
import os
import csv
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException

load_dotenv()
ORANGEHRM_BASE_URL = os.environ.get("ORANGEHRM_BASE_URL", "https://opensource-demo.orangehrmlive.com/")
WAIT_SECONDS = 20

class LoginFailedError(Exception):
    pass

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=os.path.join("logs", "automation.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

def make_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    return webdriver.Chrome(options=options)

def wait_click(wait, by, selector):
    element = wait.until(EC.element_to_be_clickable((by, selector)))
    element.click()
    return element

def login(driver, wait, username, password):
    driver.get(ORANGEHRM_BASE_URL)

    user = wait.until(
        EC.visibility_of_element_located((By.NAME, "username"))
    )
    user.clear()
    user.send_keys(username)

    pwd = wait.until(
        EC.visibility_of_element_located((By.NAME, "password"))
    )
    pwd.clear()
    pwd.send_keys(password)

    wait_click(wait, By.CSS_SELECTOR, "button[type='submit']")

    def check_login_result(d):
        alerts = d.find_elements(
            By.CSS_SELECTOR, ".oxd-alert-content-text"
        )

        for alert in alerts:
            try:
                if alert.is_displayed() and alert.text.strip():
                    return ("error", alert.text.strip())
            except StaleElementReferenceException:
                continue

        dashboard = d.find_elements(
            By.CSS_SELECTOR, "nav[aria-label='Sidepanel']"
        )

        if dashboard:
            return ("success", "")

        return False

    result = wait.until(check_login_result)

    if result[0] == "error":
        logging.warning("Login failed: %s", result[1])
        raise LoginFailedError(
            "Login failed: Invalid username or password."
        )

    logging.info("Login successful")

def logout_if_possible(driver, wait):
    try:
        wait_click(wait, By.CSS_SELECTOR, "span.oxd-userdropdown-tab")
        wait_click(wait, By.XPATH, "//a[normalize-space()='Logout']")
        wait.until(EC.visibility_of_element_located((By.NAME, "username")))
        logging.info("Logout successful")
    except Exception:
        logging.warning("Logout could not be confirmed; browser will be closed")

def go_to_pim(driver, wait):
    driver.get(
        ORANGEHRM_BASE_URL + "web/index.php/pim/viewEmployeeList"
    )

    wait.until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, ".oxd-form")
        )
    )

    wait_click(
        wait,
        By.XPATH,
        "//button[@type='submit' and normalize-space()='Search']"
    )

    wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".oxd-table-body")
        )
    )

    logging.info("Employee List searched: %s", driver.current_url)

def read_employee_table(driver, wait):
    body = wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".oxd-table-body")
        )
    )

    wait.until(
        lambda d: (
            len(d.find_elements(
                By.CSS_SELECTOR,
                ".oxd-table-body .oxd-table-row"
            )) > 0
            or "No Records Found" in body.text
        )
    )

    rows = driver.find_elements(
        By.CSS_SELECTOR,
        ".oxd-table-body .oxd-table-row"
    )

    employees = []

    for row in rows:
        cells = row.find_elements(
            By.CSS_SELECTOR, ".oxd-table-cell"
        )
        values = [cell.text.strip() for cell in cells]

        if len(values) >= 4 and any(value.strip() for value in values):
            employees.append({
                "employee_id": values[1],
                "first_name": values[2],
                "last_name": values[3]
            })

    logging.info(
        "Rows detected after Search: %s", len(employees)
    )

    if not employees:
        logging.warning(
            "No employee rows after Search. Table text: %s",
            body.text
        )

    return employees



def find_next_button(driver):
    buttons = driver.find_elements(
        By.CSS_SELECTOR,
        "nav[aria-label='Pagination Navigation'] "
        "button.oxd-pagination-page-item--previous-next"
    )

    for button in buttons:
        try:
            if not button.is_displayed():
                continue

            icon = button.find_elements(
                By.CSS_SELECTOR, "i.bi-chevron-right"
            )

            if icon:
                return button
        except Exception:
            continue

    return None

def fetch_list_after_login(driver, wait):
    go_to_pim(driver, wait)

    all_employees = []
    page_number = 1

    while True:
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".oxd-table-body")
            )
        )

        page_employees = []
        rows_count = 0
        page_read = False

        for attempt in range(3):
            try:
                rows = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".oxd-table-body .oxd-table-row"
                )

                rows_count = len(rows)
                page_employees = []

                for row in rows:
                    cells = row.find_elements(
                        By.CSS_SELECTOR, ".oxd-table-cell"
                    )
                    values = [cell.text.strip() for cell in cells]

                    if len(values) >= 4 and any(values):
                        page_employees.append({
                            "employee_id": values[1],
                            "first_name": values[2],
                            "last_name": values[3],
                        })

                page_read = True
                break

            except StaleElementReferenceException:
                logging.warning(
                    "Stale table element on page %s; retry %s of 3.",
                    page_number, attempt + 1
                )

                if attempt < 2:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".oxd-table-body")
                        )
                    )

        if not page_read:
            logging.error(
                "Could not read page %s after 3 attempts.",
                page_number
            )
            break

        logging.info(
            "Page %s: table rows=%s, valid employee rows=%s",
            page_number, rows_count, len(page_employees)
        )

        logging.info(
            "Employee IDs on current page: %s",
            [employee.get("employee_id") for employee in page_employees]
        )

        all_employees.extend(page_employees)

        logging.info(
            "Added records for page %s: %s; total records collected: %s",
            page_number,
            len(page_employees),
            len(all_employees)
        )

        try:
            next_button = find_next_button(driver)

            if next_button is None:
                logging.info(
                    "Next button not found. Inspect the HTML of the pagination buttons."
                )
                break

            classes = next_button.get_attribute("class") or ""
            aria_disabled = next_button.get_attribute("aria-disabled")
            is_disabled = (
                next_button.get_attribute("disabled") is not None
                or aria_disabled == "true"
                or "disabled" in classes.split()
            )

            if is_disabled:
                logging.info("Next button is disabled; last page reached.")
                break

            old_signature = [
                row.text
                for row in driver.find_elements(
                    By.CSS_SELECTOR,
                    ".oxd-table-body .oxd-table-row"
                )
            ]

            next_button = find_next_button(driver)

            if next_button is None:
                logging.info("Next button disappeared; stopping pagination.")
                break

            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                next_button
            )

            driver.execute_script(
                "arguments[0].click();",
                next_button
            )

        except StaleElementReferenceException:
            logging.warning(
                "Pagination element became stale on page %s; stopping safely.",
                page_number
            )
            break

        target_page = page_number + 1

        def target_page_selected(d):
            try:
                buttons = d.find_elements(
                    By.CSS_SELECTOR,
                    "nav[aria-label='Pagination Navigation'] "
                    "button.oxd-pagination-page-item--page"
                )

                return any(
                    "page-selected" in (
                        button.get_attribute("class") or ""
                    )
                    and (button.text or "").strip() == str(target_page)
                    for button in buttons
                )
            except StaleElementReferenceException:
                return False

        try:
            WebDriverWait(driver, WAIT_SECONDS).until(
                target_page_selected
            )

            logging.info(
                "Page %s successfully selected.",
                target_page
            )

        except TimeoutException:
            logging.warning(
                "Page %s was not selected after clicking Next.",
                target_page
            )
            break

        page_number = target_page

    logging.info(
        "Pagination finished. Total employee rows collected=%s",
        len(all_employees)
    )

    logging.info("Final employee data for CSV: %s", all_employees)

    return all_employees

def run_add_employee(username, password, first_name, middle_name, last_name, employee_id=""):
    driver = None

    try:
        driver = make_driver()
        wait = WebDriverWait(driver, WAIT_SECONDS)

        login(driver, wait, username, password)
        go_to_pim(driver, wait)

        wait_click(wait, By.XPATH, "//button[normalize-space()='Add']")

        wait.until(
            EC.visibility_of_element_located((By.NAME, "firstName"))
        )

        driver.find_element(By.NAME, "firstName").clear()
        driver.find_element(By.NAME, "firstName").send_keys(first_name)

        middle_input = driver.find_element(By.NAME, "middleName")
        middle_input.clear()
        if middle_name:
            middle_input.send_keys(middle_name)

        last_input = driver.find_element(By.NAME, "lastName")
        last_input.clear()
        last_input.send_keys(last_name)

        if employee_id and employee_id.strip():
            id_input = wait.until(
                EC.visibility_of_element_located((
                    By.XPATH,
                    "//label[normalize-space()='Employee Id']"
                    "/ancestor::div[contains(@class,'oxd-input-group')]//input"
                ))
            )

            custom_id = employee_id.strip()
            id_input.click()
            id_input.send_keys(Keys.CONTROL, "a")
            id_input.send_keys(Keys.BACKSPACE)
            id_input.send_keys(custom_id)

            actual_id = (id_input.get_attribute("value") or "").strip()

            if actual_id != custom_id:
                raise ValueError(
                    f"Employee ID mismatch: expected {custom_id}, got {actual_id}"
                )

        expected_first_name = first_name.strip()
        expected_middle_name = middle_name.strip() if middle_name else ""
        expected_last_name = last_name.strip()

        logging.info(
            "Submitting employee form: first=%r, middle=%r, last=%r, employee_id=%r",
            expected_first_name,
            expected_middle_name,
            expected_last_name,
            employee_id
        )

        wait_click(wait, By.CSS_SELECTOR, "button[type='submit']")

        try:
            WebDriverWait(driver, 4).until(
                lambda d: any(
                    element.is_displayed() and element.text.strip()
                    for element in d.find_elements(
                        By.CSS_SELECTOR,
                        "span.oxd-input-field-error-message"
                    )
                )
            )

            error_messages = [
                element.text.strip()
                for element in driver.find_elements(
                    By.CSS_SELECTOR,
                    "span.oxd-input-field-error-message"
                )
                if element.is_displayed() and element.text.strip()
            ]

            if error_messages:
                error_message = "; ".join(dict.fromkeys(error_messages))

                logging.warning(
                    "OrangeHRM form validation failed: %s",
                    error_message
                )

                return {
                    "success": False,
                    "message": f"Employee could not be added: {error_message}",
                    "employees": []
                }

        except LoginFailedError as exc:
            logging.warning("%s", exc)
            return {
                "success": False,
                "message": str(exc),
                "employees": []
            }

        except TimeoutException:
            pass

        wait.until(
            EC.visibility_of_element_located((
                By.XPATH,
                "//h6[normalize-space()='Personal Details']"
            ))
        )

        logging.info("Personal Details page opened: %s", driver.current_url)

        def names_are_loaded(d):
            try:
                first_fields = d.find_elements(By.NAME, "firstName")
                middle_fields = d.find_elements(By.NAME, "middleName")
                last_fields = d.find_elements(By.NAME, "lastName")

                if not first_fields or not middle_fields or not last_fields:
                    return False

                first_value = (
                    first_fields[0].get_attribute("value") or ""
                ).strip()
                middle_value = (
                    middle_fields[0].get_attribute("value") or ""
                ).strip()
                last_value = (
                    last_fields[0].get_attribute("value") or ""
                ).strip()

                return (
                    first_value == expected_first_name
                    and middle_value == expected_middle_name
                    and last_value == expected_last_name
                )

            except Exception:
                return False

        try:
            WebDriverWait(driver, 10).until(names_are_loaded)
        except TimeoutException:
            logging.error(
                "Expected name values did not appear within 10 seconds."
            )

        def read_field(field_name):
            fields = driver.find_elements(By.NAME, field_name)

            for field in fields:
                if field.is_displayed():
                    return (field.get_attribute("value") or "").strip()

            return ""

        saved_first_name = read_field("firstName")
        saved_middle_name = read_field("middleName")
        saved_last_name = read_field("lastName")

        logging.info(
            "Employee verification values: first=%r, middle=%r, last=%r",
            saved_first_name,
            saved_middle_name,
            saved_last_name
        )

        if (
            saved_first_name != expected_first_name
            or saved_middle_name != expected_middle_name
            or saved_last_name != expected_last_name
        ):
            for field in driver.find_elements(By.CSS_SELECTOR, "input"):
                try:
                    if field.is_displayed():
                        logging.info(
                            "Visible input diagnostic: name=%r, value=%r, placeholder=%r",
                            field.get_attribute("name"),
                            field.get_attribute("value"),
                            field.get_attribute("placeholder")
                        )
                except Exception:
                    pass

            raise ValueError(
                "Employee verification failed: saved name does not match submitted name. "
                f"Expected: {expected_first_name} {expected_middle_name} {expected_last_name}; "
                f"Saved: {saved_first_name} {saved_middle_name} {saved_last_name}. "
                "See logs/automation.log for visible input diagnostics."
            )

        logging.info(
            "Employee creation verified: %s %s %s",
            saved_first_name,
            saved_middle_name,
            saved_last_name
        )

        go_to_pim(driver, wait)
        employees = fetch_list_after_login(driver, wait)

        if employees:
            csv_path = export_employees_to_csv(employees)
            logging.info("CSV export completed: %s", csv_path)

        return {
            "success": True,
            "message": (
                f"Employee {first_name} {last_name} added and verified successfully."
            ),
            "employees": employees
        }

    except TimeoutException:
        logging.exception("Timeout during add employee")
        return {
            "success": False,
            "message": (
                "Timeout: OrangeHRM page or element did not load in time. "
                "Please check logs/automation.log."
            ),
            "employees": []
        }

    except WebDriverException as exc:
        logging.exception("WebDriver error")
        return {
            "success": False,
            "message": f"Browser/WebDriver error: {exc.msg[:240]}",
            "employees": []
        }

    except Exception as exc:
        logging.exception("Unexpected add employee error")
        return {
            "success": False,
            "message": f"Automation failed: {exc}",
            "employees": []
        }

    finally:
        if driver:
            try:
                logout_if_possible(driver, WebDriverWait(driver, 5))
            except Exception:
                logging.exception("Logout failed after add employee")
            finally:
                try:
                    driver.quit()
                except Exception:
                    logging.exception("Browser close failed")


def export_employees_to_csv(employees):
    os.makedirs("exports", exist_ok=True)

    file_path = os.path.abspath(
        os.path.join("exports", "employees.csv")
    )

    fieldnames = ["employee_id", "first_name", "last_name"]

    logging.info("CSV export received %s employee records", len(employees))

    with open(
        file_path,
        mode="w",
        newline="",
        encoding="utf-8-sig"
    ) as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()

        for employee in employees:
            row = {
                "employee_id": employee.get("employee_id", ""),
                "first_name": employee.get("first_name", ""),
                "last_name": employee.get("last_name", "")
            }
            writer.writerow(row)

    logging.info("CSV export completed: %s", file_path)

    with open(file_path, mode="r", newline="", encoding="utf-8-sig") as csvfile:
        saved_rows = list(csv.DictReader(csvfile))

    logging.info("CSV verification: %s data rows written", len(saved_rows))

    return file_path


def fetch_employees(username, password):
    driver = None
    try:
        driver = make_driver()
        wait = WebDriverWait(driver, WAIT_SECONDS)
        login(driver, wait, username, password)
        employees = fetch_list_after_login(driver, wait)
        if employees:
            csv_path = export_employees_to_csv(employees)
            logging.info("CSV export completed: %s", csv_path)
        if not employees:
            return {
                "success": False,
                "message": (
                    "Employee list opened, but no rows were extracted."
                    "Please check logs/automation.log."
                ),
                "employees": []
            }
        return {
            "success": True,
            "message": (
                f"Fetched {len(employees)} employee records from all pages."
            ),
            "employees": employees
        }
    except LoginFailedError as exc:
        logging.warning("%s", exc)
        return {
            "success": False,
            "message": str(exc),
            "employees": []
        }
    except TimeoutException:
        logging.exception("Timeout during employee fetch")
        return {
            "success": False,
            "message": "Employee list failed to load. Please check the logs and screenshot.",
            "employees": []
        }
    except WebDriverException as exc:
        logging.exception("WebDriver error during employee fetch")
        return {"success": False, "message": f"Browser/WebDriver error: {exc.msg[:240]}", "employees": []}
    except Exception as exc:
        logging.exception("Unexpected fetch error")
        return {"success": False, "message": f"Employee list fetch failed: {exc}", "employees": []}
    finally:
        if driver:
            try:
                wait = WebDriverWait(driver, 5)
                logout_if_possible(driver, wait)
            except Exception:
                logging.exception("Logout failed during employee fetch")
            finally:
                try:
                    driver.quit()
                except Exception:
                    logging.exception("Browser close failed")
