import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, current_app
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from datetime import datetime, timedelta
import pymysql
from pymysql.cursors import DictCursor
import logging
import json
# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Location:
    def __init__(self, id, name, latitude, longitude, notify, notification_lead_time, cloud_coverage_threshold, created_at, user_id):
        self.id = id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.notify = notify
        self.notification_lead_time = notification_lead_time
        self.cloud_coverage_threshold = cloud_coverage_threshold
        self.created_at = created_at
        self.user_id = user_id

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'notify': self.notify,
            'notification_lead_time': self.notification_lead_time,
            'cloud_coverage_threshold': self.cloud_coverage_threshold,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_id': self.user_id
        }


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# Database configuration
db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'root'),
    'db': os.environ.get('DB_NAME', 'landsat_app'),
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}
  # Email configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'alenva214@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'qwer123478')
app.config['USGS_API_URL'] = 'https://m2m.cr.usgs.gov/api/api/json/stable'
app.config['USGS_USERNAME'] = os.environ.get('USGS_USERNAME')
app.config['USGS_PASSWORD'] = os.environ.get('USGS_PASSWORD')

mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if user:
                return User(user['id'], user['username'], user['email'], user['password_hash'])
    return None

def get_db_connection():
    return pymysql.connect(**db_config)

@app.route('/')
def root():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                
                logging.debug(f"Fetched user: {user}")

        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], user['username'], user['email'], user['password_hash'])
            login_user(user_obj)
            return jsonify({'message': 'Logged in successfully', 'redirect': url_for('index')})
        
        logging.warning(f"Login failed for user: {username}")
        return jsonify({'error': 'Invalid username or password'}), 401
    
    return render_template('login.html')

@app.route('/index')
@login_required
def index():
    return render_template('index.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    return jsonify({'error': 'Username already exists'}), 400

                password_hash = generate_password_hash(password)
                cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                                   (username, email, password_hash))
                conn.commit()
                    
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                    
        new_user = User(user['id'], user['username'], user['email'], user['password_hash'])
        login_user(new_user)
        return jsonify({'message': 'Registered successfully'})
    
    return render_template('register.html')



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'})
def get_usgs_api_token():
    url = f"{app.config['USGS_API_URL']}/login"
    payload = {
        "username": app.config['USGS_USERNAME'],
        "password": app.config['USGS_PASSWORD']
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()['data']
def get_landsat_data(latitude, longitude, cloud_coverage_threshold):
    token = get_usgs_api_token()
    
    url = f"{app.config['USGS_API_URL']}/scene-search"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    headers = {
        "X-Auth-Token": token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "datasetName": "landsat_ot_c2_l2",
        "spatialFilter": {
            "filterType": "mbr",
            "lowerLeft": {
                "latitude": float(latitude) - 0.1,
                "longitude": float(longitude) - 0.1
            },
            "upperRight": {
                "latitude": float(latitude) + 0.1,
                "longitude": float(longitude) + 0.1
            }
        },
        "temporalFilter": {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d")
        },
        "metadataType": "full",
        "maxResults": 10
    }
    
    try:
        logging.debug(f"Sending request to USGS API with payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, headers=headers, json=payload)
        
        logging.debug(f"USGS API Response Status: {response.status_code}")
        logging.debug(f"USGS API Response Content: {response.text[:1000]}")
        
        response.raise_for_status()
        landsat_data = response.json()
        
        filtered_data = []
        for scene in landsat_data.get('data', {}).get('results', []):
            try:
                cloud_cover = float(scene.get('cloudCover', '100'))
                if cloud_cover <= float(cloud_coverage_threshold):
                    filtered_data.append(scene)
            except ValueError:
                logging.warning(f"Invalid cloud cover value for scene: {scene.get('displayId')}")
        
        if filtered_data:
            return {
                'message': 'Landsat data fetched successfully.',
                'data': filtered_data
            }
        else:
            return {
                'message': 'No Landsat scenes found for the given parameters.',
                'data': []
            }

    except requests.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {str(http_err)}")
        return {'error': f'HTTP error occurred: {str(http_err)}'}
    except Exception as err:
        logging.error(f"Unexpected error: {str(err)}")
        return {'error': f'Failed to fetch Landsat data: {str(err)}'}

def send_notification(user_email, location_name, next_pass):
    try:
        message = Message("Upcoming Landsat Pass",
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[user_email])
        message.body = f"Hello,\n\nThere is an upcoming Landsat pass for your location '{location_name}' at {next_pass}.\n\nBest regards,\nLandsat Notification System"
        mail.send(message)
        logging.info(f"Notification sent to {user_email} for location {location_name}")
    except Exception as e:
        logging.error(f"Failed to send notification email: {str(e)}")
@app.route('/submit_location', methods=['POST'])
@login_required
def submit_location():
    try:
        data = request.json
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))
        name = data.get('name', f"Location at {latitude}, {longitude}")
        notification_lead_time = data.get('notification_lead_time', 24)
        cloud_coverage_threshold = data.get('cloud_coverage_threshold', 15.0)
        
        if not latitude or not longitude:
            return jsonify({'error': 'Latitude and longitude are required'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO locations (name, latitude, longitude, user_id, notification_lead_time, cloud_coverage_threshold)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, float(latitude), float(longitude), current_user.id, int(notification_lead_time), float(cloud_coverage_threshold)))
                conn.commit()
                
                cursor.execute("SELECT * FROM locations WHERE id = LAST_INSERT_ID()")
                new_location_data = cursor.fetchone()
                
                new_location = Location(
                    id=new_location_data['id'],
                    name=new_location_data['name'],
                    latitude=new_location_data['latitude'],
                    longitude=new_location_data['longitude'],
                    notify=new_location_data['notify'],
                    notification_lead_time=new_location_data['notification_lead_time'],
                    cloud_coverage_threshold=new_location_data['cloud_coverage_threshold'],
                    created_at=new_location_data['created_at'],
                    user_id=new_location_data['user_id']
                )
        
        # Fetch Landsat data
        landsat_data = get_landsat_data(latitude, longitude, cloud_coverage_threshold)
        
        return jsonify({
            'message': f'Saved location: {name}',
            'location': new_location.to_dict(),
            'landsat_data': landsat_data
        })
    except Exception as e:
        current_app.logger.error(f"Error in submit_location: {str(e)}")
        return jsonify({'error': 'An error occurred while submitting the location'}), 500
def get_landsat_overpasses(latitude, longitude, start_date, end_date):
    token = get_usgs_api_token()
    
    url = f"{app.config['USGS_API_URL']}/scene-search"
    
    headers = {
        "X-Auth-Token": token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "datasetName": "landsat_ot_c2_l2",
        "spatialFilter": {
            "filterType": "mbr",
            "lowerLeft": {
                "latitude": float(latitude) - 0.1,
                "longitude": float(longitude) - 0.1
            },
            "upperRight": {
                "latitude": float(latitude) + 0.1,
                "longitude": float(longitude) + 0.1
            }
        },
        "temporalFilter": {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d")
        },
        "metadataType": "full"
    }
    
    try:
        logging.debug(f"Sending request to USGS API for overpasses with payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, headers=headers, json=payload)
        
        logging.debug(f"USGS API Overpass Response Status: {response.status_code}")
        logging.debug(f"USGS API Overpass Response Content: {response.text[:1000]}")
        
        response.raise_for_status()
        data = response.json()
        
        overpasses = []
        for scene in data.get('data', {}).get('results', []):
            acquisition_date = scene.get('acquisitionDate')
            if acquisition_date:
                overpasses.append(datetime.strptime(acquisition_date, "%Y-%m-%d %H:%M:%S"))
        
        return sorted(overpasses)
    except requests.HTTPError as http_err:
        logging.error(f"HTTP error occurred while fetching overpasses: {str(http_err)}")
        return []
    except Exception as e:
        logging.error(f"Error fetching Landsat overpass data: {e}")
        return []
def check_and_notify():
    with app.app_context():
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT l.*, u.email FROM locations l JOIN users u ON l.user_id = u.id WHERE l.notify = TRUE")
                    locations_data = cursor.fetchall()
            
            for location_data in locations_data:
                start_date = datetime.now() + timedelta(hours=location_data['notification_lead_time'])
                end_date = start_date + timedelta(days=1)
                overpasses = get_landsat_overpasses(location_data['latitude'], location_data['longitude'], start_date, end_date)
                if overpasses:
                    next_pass = overpasses[0]
                    send_notification(location_data['email'], location_data['name'], next_pass)
        except Exception as e:
            logging.error(f"Error in check_and_notify: {str(e)}")

@app.route('/get_locations', methods=['GET'])
@login_required
def get_locations():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM locations WHERE user_id = %s", (current_user.id,))
                locations = cursor.fetchall()
                
        return jsonify([{
            'id': loc['id'],
            'name': loc['name'],
            'latitude': loc['latitude'],
            'longitude': loc['longitude'],
            'notify': loc['notify'],
            'notification_lead_time': loc['notification_lead_time'],
            'cloud_coverage_threshold': loc['cloud_coverage_threshold'],
            'created_at': loc['created_at'].isoformat() if loc['created_at'] else None
        } for loc in locations])
    except Exception as e:
        logging.error(f"Error fetching locations: {str(e)}")
        return jsonify({'error': 'Failed to fetch locations'}), 500
@app.teardown_appcontext
def shutdown_scheduler(error=None):
    if scheduler.running:
        scheduler.shutdown()


def get_landsat_sr_data(latitude, longitude, date):
    url = f"https://landsatlook.usgs.gov/data/v1/sr?lat={latitude}&lon={longitude}&date={date}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException as e:
        print(f"Error fetching Landsat SR data: {e}")
        return None
    


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_and_notify, trigger="interval", hours=24)
    scheduler.start()
    
    try:
        app.run(debug=True)
    finally:
        scheduler.shutdown()