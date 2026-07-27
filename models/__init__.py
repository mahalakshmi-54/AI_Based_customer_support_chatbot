from models.db import db
from models.user import User
from models.conversation import Conversation
from models.message import Message
from models.faq import FAQ
from models.support_ticket import SupportTicket
from models.chatbot_intent import ChatbotIntent

__all__ = ['db', 'User', 'Conversation', 'Message', 'FAQ', 'SupportTicket', 'ChatbotIntent']
