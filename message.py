from datetime import datetime
from models.db import db

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    sender = db.Column(db.String(20), nullable=False)  # 'user', 'bot', 'agent'
    message_text = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(50), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Message {self.id} (Sender: {self.sender}, Intent: {self.intent})>'
