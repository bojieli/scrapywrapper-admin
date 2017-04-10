from datetime import datetime
from flask import url_for, Markup
from app import db
from decimal import Decimal
from sqlalchemy import orm
try:
    from flask_login import current_user
except:
    current_user=None

class Task(db.Model):
    __tablename__ = 'tasks'

    # we do not need an ID, but ORM requires it
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # we have two non-independent foreign keys to make query easier
    name = db.Column(db.String(200))
    sync_frequency = db.Column(db.Integer)
    sync_time = db.Column(db.Integer)
    incremental_sync = db.Column(db.Integer)

    sync_is_in_progress = db.Column(db.Integer)
    sync_process_id = db.Column(db.Integer)
    last_sync_record_id = db.Column(db.Integer, db.ForeignKey('sync_records.id'))
    total_records = db.Column(db.Integer)

    last_sync_record = db.relationship('SyncRecord', foreign_keys=[last_sync_record_id])

    def __repr__(self):
        return self.name

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

