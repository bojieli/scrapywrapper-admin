from datetime import datetime
from app import db

class DevUpdate(db.Model):
    __tablename__ = 'dev_updates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    time = db.Column(db.DateTime())

    title = db.Column(db.Text())
    content = db.Column(db.Text())

    task = db.relationship('Task', foreign_keys=[task_id], backref='dev_updates')

    def __repr__(self):
        return self.title

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

