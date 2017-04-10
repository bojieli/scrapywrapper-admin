from datetime import datetime
from app import db

class ErrorLog(db.Model):
    __tablename__ = 'error_log'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sync_record_id = db.Column(db.Integer, db.ForeignKey('sync_records.id'))

    time = db.Column(db.DateTime())
    url = db.Column(db.Text())
    raw_response = db.Column(db.Text())
    message = db.Column(db.Text())

    sync_record = db.relationship('SyncRecord', backref='error_logs')

    def __repr__(self):
        return self.message

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

