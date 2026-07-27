from models.db import db

class ChatbotIntent(db.Model):
    __tablename__ = 'chatbot_intents'
    
    id = db.Column(db.Integer, primary_key=True)
    intent_name = db.Column(db.String(50), unique=True, nullable=False)
    patterns = db.Column(db.Text, nullable=False)  # JSON-encoded list of pattern sentences
    responses = db.Column(db.Text, nullable=False)  # JSON-encoded list of response templates
    
    def __repr__(self):
        return f'<ChatbotIntent {self.intent_name}>'
