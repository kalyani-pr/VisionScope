import os
import shutil
import time
from flask import Flask, Response, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import cv2
from ultralytics import YOLO  # Using the YOLOv8 library
from firebase_config import auth_client  # Firebase is set up for authentication

import requests

app = Flask(__name__)
app.secret_key = 'your_actual_secret_key'

FIREBASE_API_KEY = 'YOUR_API_KEY_HERE'

# Path to custom YOLO model
MODEL_PATH = r'best.pt'  

# Load custom YOLO model
model = YOLO(MODEL_PATH)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')  # Folder for uploaded files
RESULTS_FOLDER = os.path.join(app.root_path, 'runs', 'detect')  # Path where YOLO saves results
STATIC_RESULTS_FOLDER = os.path.join(app.root_path, 'static', 'results')  # Static folder for Flask

# Ensure the directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)
os.makedirs(STATIC_RESULTS_FOLDER, exist_ok=True)

# Home route to redirect to signup
@app.route('/')
def home():
    return render_template('home.html')

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        payload = {
            'email': email,
            'password': password,
            'returnSecureToken': True
        }
        response = requests.post(f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}', json=payload)

        if response.status_code == 200:
            user = auth_client.create_user_with_email_and_password(email, password)
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for('login'))
        else:
            error_message = response.json().get('error', {}).get('message', 'An unknown error occurred.')
            flash(error_message)
    return render_template('signup.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        payload = {
            'email': email,
            'password': password,
            'returnSecureToken': True
        }
        # Send a request to Firebase Authentication
        response = requests.post(f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}', json=payload)
        
        if response.status_code == 200:
            user = auth_client.sign_in_with_email_and_password(email, password)
            session['user'] = user['idToken']  # Save user's session
            return redirect(url_for('index'))
        else:
            error_message = response.json().get('error', {}).get('message', 'An unknown error occurred.')
            flash(error_message)
    return render_template('login.html')

# Forgot Password Route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        try:
            auth_client.send_password_reset_email(email)
            flash("Password reset email sent!", "success")
        except Exception as e:
            error_message = str(e)
            flash("Error sending password reset email: " + error_message, "danger")
    return render_template('forgot_password.html')

#Dashboard route
@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

#Image upload route
@app.route('/image_upload', methods=['GET', 'POST'])
def image_upload():
    if 'user' not in session:
        return redirect(url_for('login'))

    detected_objects = []
    image_path = ''
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file uploaded.", "danger")
            return redirect(url_for('image_upload'))

        file = request.files['file']
        if file.filename == '':
            flash("No selected file.", "danger")
            return redirect(url_for('image_upload'))

        # Save uploaded file
        filename = secure_filename(file.filename)
        file_extension = filename.rsplit('.', 1)[-1].lower()
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Image handling
        if file_extension in ALLOWED_EXTENSIONS:
            img = cv2.imread(filepath)
            if img is None:
                flash("Error loading image.", "danger")
                return redirect(url_for('image_upload'))

            # YOLO prediction
            results = model.predict(img, save=True, save_dir=RESULTS_FOLDER, conf=0.25)

            relevant_classes = {'Bus', 'Bushes', 'Person', 'Truck', 'backpack', 'bench', 'bicycle', 'boat', 
                                'branch', 'car', 'chair', 'clock', 'crosswalk', 'door', 'elevator', 
                                'fire_hydrant', 'green_light', 'gun', 'handbag', 'motorcycle', 'person', 
                                'pothole', 'rat', 'red_light', 'scooter', 'sheep', 'stairs', 'stop_sign', 
                                'suitcase', 'traffic light', 'traffic_cone', 'train', 'tree', 'truck', 'umbrella', 
                                'yellow_light'}

            # Collect detected objects with confidence >= 0.25
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls.item())
                    class_name = result.names[class_id]
                    confidence = float(box.conf.item())

                    if class_name in relevant_classes and confidence >= 0.25:
                        detected_objects.append(f"{class_name} ({confidence:.2f})")

            # If no objects are detected, set a message
            if not detected_objects:
                detected_objects = ["No relevant objects detected."]

            # Find the most recent YOLO prediction folder dynamically
            latest_folder = max([os.path.join(RESULTS_FOLDER, d) for d in os.listdir(RESULTS_FOLDER)], key=os.path.getmtime)

            # Find the YOLO-predicted image (assuming YOLO saves it as image0.jpg)
            yolo_result_image = os.path.join(latest_folder, 'image0.jpg')

            # Check if the image exists
            if not os.path.exists(yolo_result_image):
                flash("YOLO result image not found.", "danger")
                return redirect(url_for('image_upload'))

            # Move the YOLO result image to static/results for Flask to serve
            static_image_path = os.path.join(STATIC_RESULTS_FOLDER, filename)
            shutil.copy(yolo_result_image, static_image_path)  # Copy YOLO result to static folder

            # Use url_for to get the path to display the image
            image_path = url_for('static', filename=f'results/{filename}')

        else:
            flash('Allowed image types are: png, jpg, jpeg')

    return render_template('image_upload.html', detected_objects=detected_objects, image_path=image_path)

#Video Upload route
@app.route('/video_upload', methods=['GET', 'POST'])
def video_upload():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ALLOWED_EXTENSIONS = {'mp4'}

    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file uploaded.", "danger")
            return redirect(url_for('image_upload'))

        file = request.files['file']
        if file.filename == '':
            flash("No selected file.", "danger")
            return redirect(url_for('image_upload'))

        # Save uploaded file
        filename = secure_filename(file.filename)
        file_extension = filename.rsplit('.', 1)[-1].lower()
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        if file_extension in ALLOWED_EXTENSIONS:
            video_path = filepath  # replace with your video path
            cap = cv2.VideoCapture(video_path)

            # get video dimensions
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Define the codec and create VideoWriter object
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter('output.mp4', fourcc, 30.0, (frame_width, frame_height))

            # initialize the YOLOv8 model here
            model = YOLO('best.pt')

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break         

                # do YOLOv9 detection on the frame here
                #model = YOLO('best.pt')
                results = model(frame, save=True)  #working
                print(results)
                cv2.waitKey(1)

                res_plotted = results[0].plot()
                cv2.imshow("result", res_plotted)
                    
                # write the frame to the output video
                out.write(res_plotted)

                if cv2.waitKey(1) == ord('q'):
                    break

            return video_feed()            
        
        else: 
            flash('Allowed extension types: mp4')
    
    return render_template('video_upload.html')

def get_frame():
    folder_path = os.getcwd()
    mp4_files = 'output.mp4'
    video = cv2.VideoCapture(mp4_files)  # detected video path
    while True:
        success, image = video.read()
        if not success:
            break
        ret, jpeg = cv2.imencode('.jpg', image) 
      
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')   
        time.sleep(0.1)  #control the frame rate to display one frame every 100 milliseconds: 


# function to display the detected objects video on html page
@app.route("/video_feed")
def video_feed():
    print("function called")

    return Response(get_frame(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# Logout route
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)