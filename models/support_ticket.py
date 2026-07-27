from datetime import datetime
from models.db import db

class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'in_progress', 'resolved'
    priority = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high'
    category = db.Column(db.String(100), nullable=False)  # 'Billing', 'Technical', 'General', etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # We can also add an admin reply field if admins can reply to tickets
    admin_reply = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<SupportTicket {self.id}: {self.subject} ({self.status})>'
