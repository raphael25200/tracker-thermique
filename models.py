from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Evenement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    heure = db.Column(db.String(10), nullable=True)
    zone = db.Column(db.String(100), nullable=False)
    region = db.Column(db.String(30), nullable=True, index=True)
    type_evenement = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    source_url = db.Column(db.String(500), nullable=True, unique=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    intensite = db.Column(db.Float, nullable=True)
    frp = db.Column(db.Float, nullable=True, index=True)
    satellite = db.Column(db.String(20), nullable=True)
    confidence = db.Column(db.String(5), nullable=True)
    daynight = db.Column(db.String(2), nullable=True)
    bright_ti5 = db.Column(db.Float, nullable=True)
    scan = db.Column(db.Float, nullable=True)
    track = db.Column(db.Float, nullable=True)
    version = db.Column(db.String(20), nullable=True)

    def __repr__(self):
        return f"<Evenement {self.id} - {self.zone}>"