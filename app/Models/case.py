from flask_sqlalchemy import SQLAlchemy
import datetime

db = SQLAlchemy()

class FemicideCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(512), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    has_nna_mention = db.Column(db.Boolean, default=False)
    is_validated = db.Column(db.Boolean, default=False)
    scraped_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<Caso {self.id}: {self.title}>'