import os

class Config:
    # MySQL Database Configuration
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'  # or a dedicated user you created
    MYSQL_PASSWORD = 'root'  # the password you set during installation
    MYSQL_DB = 'facial_attendance_db'
    MYSQL_PORT = 3306
    
    
    
    SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://root@localhost/attendance_db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'MYATTENDANCEPROJECT'  

    # Facial data upload settings
    UPLOAD_FOLDER = 'facial_data'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}