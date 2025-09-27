from flask import Flask

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

from app.models import db

migrate = Migrate()
login_manager = LoginManager()

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
login_manager.login_view = 'login'
from app import models, routes  # Import models and routes

@app.template_filter('format_time')
def format_time_filter(time_obj):
    if time_obj:
        return time_obj.strftime('%H:%M')
    return 'N/A'


