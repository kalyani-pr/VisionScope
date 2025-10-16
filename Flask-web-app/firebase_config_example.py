import pyrebase

firebaseConfig = {
    "apiKey": "YOUR_API_KEY_HERE",
    "authDomain": "your-app.firebaseapp.com",
    "databaseURL": "your-databaseURL.firebaseio.com",
    "projectId": "your-project-id",
    "storageBucket": "your-app.appspot.com",
    "messagingSenderId": "your-messaging-sender-id",
    "appId": "your-app-id"
}

firebase = pyrebase.initialize_app(config)
auth_client = firebase.auth()