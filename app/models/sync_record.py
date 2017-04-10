from datetime import datetime
from app import db

class SyncRecord(db.Model):
    __tablename__ = 'sync_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    begin_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    crawled_webpages = db.Column(db.Integer)
    total_records = db.Column(db.Integer)
    new_records = db.Column(db.Integer)
    updated_records = db.Column(db.Integer)
    saved_images = db.Column(db.Integer)
    error_count = db.Column(db.Integer)

    status = db.Column(db.Integer, default=0)

    task = db.relationship('Task', foreign_keys=[task_id], backref=db.backref('sync_records', order_by=begin_time.desc()))

    def __repr__(self):
        return self.task.name + '@' + str(self.begin_time)

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

