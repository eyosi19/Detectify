from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
import requests
from bs4 import BeautifulSoup
import json
import os
import difflib
import schedule
from datetime import datetime
import logging
from selenium import webdriver
import base64
from io import BytesIO
from datetime import datetime
from flask_caching import Cache
from flask_compress import Compress


app = Flask(__name__)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/doc')
def doc():
    return render_template('doc.html')

# Configure Flask-Session to use filesystem-based sessions
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

Compress(app)

# Configure logging to a file
logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Log the start of the application
logging.info("Starting the application")

# Function to fetch website info and create baseline with screenshot
def fetch_and_create_baseline_with_screenshot(url):
    try:
        # Configure Chrome WebDriver options
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')

        # Initialize Chrome WebDriver
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        # Take a screenshot
        screenshot = driver.get_screenshot_as_png()

        screenshot_base64 = base64.b64encode(BytesIO(screenshot).read()).decode('utf-8')
        # Convert the screenshot to base64

        # Fetch other website info
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            textual_content = soup.get_text()
            dom_tree = soup.prettify()  
            content_length = len(response.text)
            current_info = {
                "textual_content": textual_content,
                "dom_tree": dom_tree,
                "content_length": content_length,
                "screenshot": screenshot_base64
            }
            baseline_info = load_baseline(url)

             # Check if baseline already exists
            baseline_info = load_baseline(url)
            if baseline_info is None:
                create_baseline(url, current_info)
                return current_info
            
            changes = compare_with_baseline_with_screenshot(url, current_info, baseline_info)
            if changes:
                logging.warning("Defacement detected on %s. Changes: %s", url, changes)
            else:
                logging.warning("No defacement detected on %s.", url)

            return current_info
        else:
            logging.warning("Failed to fetch and create baseline for URL %s. HTTP status code: %d", url, response.status_code)
            return None
    except Exception as e:
        logging.error("Error fetching and creating baseline for URL %s: %s", url, str(e))
        return None
    finally:
        driver.quit()

    # Function to load baseline
def load_baseline(url):
    domain_name = url.split('//')[-1].split('/')[0].replace('.', '_')
    json_file_path = os.path.join('baseline', f'{domain_name}_baseline.json')
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r', encoding='utf-8') as json_file:
            baseline_info = json.load(json_file)
            return baseline_info
    else:
        return None

# Function to compare with baseline with screenshot
def compare_with_baseline_with_screenshot(url, current_info, baseline_info):
    # Check for None values
    if current_info is None or baseline_info is None:
        logging.warning("Unable to compare with baseline. Current or baseline information is None.")
        return []

    changes = []
    excluded_elements = ['script', 'style', 'meta', 'link', 'noscript']

    # Check if textual content has changed
    if current_info['textual_content'] != baseline_info['textual_content']:
        logging.warning("Textual content changed on %s.", url)
        changes.append({
            "type": "Textual content",
            "details": list(difflib.unified_diff(baseline_info['textual_content'].splitlines(), current_info['textual_content'].splitlines()))
        })

    # Check if DOM structure has changed
    if current_info['dom_tree'] != baseline_info['dom_tree']:
        logging.warning("DOM structure changed on %s.", url)
        current_dom = remove_elements(current_info['dom_tree'], excluded_elements)
        baseline_dom = remove_elements(current_info['dom_tree'], excluded_elements)
        if current_dom != baseline_dom:
            changes.append({
                "type": "DOM Structure",
                "details": list(difflib.unified_diff(baseline_info['dom_tree'].splitlines(), current_info['dom_tree'].splitlines()))

            })
    # Check if content length has changed
    if current_info['content_length'] != baseline_info['content_length']:
        logging.warning("Content length changed on %s.", url)

        # Format the details horizontally
        details = f"Changed from: {baseline_info['content_length']} to {current_info['content_length']}"

        # Convert the horizontal details to a list of characters
        details_list = list(details)

        # Create a single string with each character on a horizontal line
        horizontal_details = '\n'.join(details_list)

        changes.append({
            "type": "Content length",
            "details": horizontal_details
        })

    # Check if screenshot has changed
    if current_info['screenshot'] != baseline_info.get('screenshot'):
        logging.warning("Screenshot changed on %s.", url)
        changes.append({
            "type": "Screenshot",
            "details": "Changed"
        })

    # Log defacement detection
    if changes:
        logging.warning("Defacement detected on %s. Changes: %s", url, changes)
    else:
        logging.info("No defacement detected on %s.", url)

    return changes


def remove_elements(dom_tree, excluded_elements):
    # Remove specified elements and their content from the DOM tree
    soup = BeautifulSoup(dom_tree, 'html.parser')
    for element in soup(excluded_elements):
        element.decompose()
    return soup.prettify()

# Function to fetch website info
def fetch_website_info(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            textual_content = soup.get_text()
            dom_tree = soup.prettify()
            content_length = len(response.text)
            return {
                "textual_content": textual_content,
                "dom_tree": dom_tree,
                "content_length": content_length
            }
        else:
            logging.warning("Failed to fetch website info for URL %s. HTTP status code: %d", url, response.status_code)
            return None
    except Exception as e:
        logging.error("Error fetching website info for URL %s: %s", url, str(e))
        return None

# Function to create baseline
def create_baseline(url, info):
    domain_name = url.split('//')[-1].split('/')[0].replace('.', '_')
    json_file_path = os.path.join('baseline', f'{domain_name}_baseline.json')
    if os.path.exists(json_file_path):
        logging.info("Baseline already exists for URL %s. Skipping creation.", url)
    else:
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(info, json_file, ensure_ascii=False, indent=4)
        logging.info("Baseline created for URL %s", url)

# Function to create baseline or load it if it already exists
def create_or_load_baseline(url):
    baseline_info = load_baseline(url)
    if baseline_info is None:
        baseline_info = fetch_and_create_baseline_with_screenshot(url)
        create_baseline(url, baseline_info)
    return baseline_info


# Function to compare with baseline
def compare_with_baseline(url, current_info, baseline_info):
    textual_content_changed = current_info['textual_content'] != baseline_info['textual_content']
    dom_changed = current_info['dom_tree'] != baseline_info['dom_tree']
    content_length_changed = current_info['content_length'] != baseline_info['content_length']
    changes = []

    # Log information about each type of change
    if textual_content_changed:
        logging.warning("Textual content changed on %s.", url)
        changes.append({"type": "Textual content", "details": list(difflib.unified_diff(baseline_info['textual_content'].splitlines(), current_info['textual_content'].splitlines()))})
    if dom_changed:
        logging.warning("DOM structure changed on %s.", url)
        changes.append({"type": "DOM structure", "details": list(difflib.unified_diff(baseline_info['dom_tree'].splitlines(), current_info['dom_tree'].splitlines()))})
    if content_length_changed:
        logging.warning("Content length changed on %s.", url)
        changes.append({"type": "Content length", "details": "Changed"})

    return changes

# Function to check if a website is alive
def check_website_alive(url):
    try:
        response = requests.get(url)
        return response.status_code == 200
    except Exception as e:
        logging.error("Error checking website status for URL %s: %s", url, str(e))
        return False

# Function to periodically check website status for all monitored websites
def check_website_statuses():
    for website_name, website_info in monitored_websites.items():
        url = website_info['url']
        current_info = fetch_and_create_baseline_with_screenshot(url)
        baseline_info = monitored_websites[website_name].get('baseline')
        if check_website_alive(url):
            website_status = "Alive"
        else:
            website_status = "Down"

        if baseline_info:
                changes = compare_with_baseline_with_screenshot(url, current_info, baseline_info)
                if changes:
                    website_status = "Changed"
        
        monitored_websites[website_name]['status'] = website_status
        monitored_websites[website_name]['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        logging.info("Website %s status: %s", website_name, website_status)

# Modify the initialization of monitored_websites to include baseline information
monitored_websites = {
    'Apache': {'url': 'http://10.0.2.15', 'last_checked': 'N/A', 'status': 'Up'},
    'Minister Of Education': {'url': 'https://moe.gov.et', 'last_checked': 'N/A', 'status': 'Up'},
}

for website_name, website_info in monitored_websites.items():
    website_info['baseline'] = create_or_load_baseline(website_info['url'])

# Schedule the website status check to run every 60 seconds
schedule.every(60).seconds.do(check_website_statuses)

@app.route("/")
def index():
    return redirect(url_for('dashboard'))

@app.route("/dashboard")
def dashboard():
    check_website_statuses()  # Update website statuses
    return render_template("dashboard.html", monitored_websites=monitored_websites)

# Function to add a website and immediately create its baseline, including screenshots
def add_and_create_baseline_with_screenshot(new_url):
    website_name = new_url.split('//')[-1].split('/')[0]
    monitored_websites[website_name] = {'url': new_url, 'status': 'Alive'}
    current_info = fetch_and_create_baseline_with_screenshot(new_url)  # Save baseline immediately

    if current_info is not None:
        baseline_info = monitored_websites[website_name].get('baseline')
        if baseline_info:
            changes = compare_with_baseline_with_screenshot(new_url, current_info, baseline_info)
            if changes:
                monitored_websites[website_name]['status'] = 'Changed'
            else:
                monitored_websites[website_name]['status'] = 'Alive'
        monitored_websites[website_name]['baseline'] = current_info  # Store baseline
    else:
        logging.warning("Failed to create baseline for URL %s", new_url)


@app.route("/add_website", methods=["POST"])
def add_website():
    new_url = request.form.get("new_url")
    if new_url:
        website_name = new_url.split('//')[-1].split('/')[0]
        monitored_websites[website_name] = {'url': new_url, 'last_checked': 'N/A', 'status': 'Alive'}
        monitored_websites[website_name]['baseline'] = create_or_load_baseline(new_url)
    return redirect(url_for('dashboard'))

@app.route("/monitor/<website_name>")
def monitor_website(website_name):
    if website_name in monitored_websites:
        url = monitored_websites[website_name]['url']
        current_info = fetch_and_create_baseline_with_screenshot(url)
        baseline_info = monitored_websites[website_name].get('baseline')  # Get stored baseline

        if current_info is not None:
            session['website_info'] = current_info
            website_status = "Alive" if check_website_alive(url) else "Down"
            session['website_status'] = website_status
            changes = compare_with_baseline_with_screenshot(url, current_info, baseline_info)
            defacement_detected = any('added' in change['type'] for change in changes)  # Check if any added changes
        else:
            # Unable to fetch website info
            session['website_info'] = {"textual_content": "Unable to fetch this website.", "dom_tree": "", "content_length": ""}
            website_status = "Down"
            session['website_status'] = website_status
            changes = []
            defacement_detected = False

        logging.info("Monitoring specific website: %s", website_name)

        return render_template(
            "monitor_specific.html",
            website_info=session['website_info'],
            website_status=website_status,
            changes=changes,
            defacement_detected=defacement_detected,
            last_time_checked=monitored_websites[website_name].get('last_checked', '')
        )

    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    app.run(debug=True)