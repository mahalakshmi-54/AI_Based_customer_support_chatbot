import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func

from config import Config
from models.db import db
from models.user import User
from models.conversation import Conversation
from models.message import Message
from models.faq import FAQ
from models.support_ticket import SupportTicket
from models.chatbot_intent import ChatbotIntent
from chatbot.chatbot_engine import chatbot_engine

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Helper: Admin decorator
    def admin_required(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_admin():
                flash('Access denied. Admin privileges required.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function

    # --- GENERAL ROUTES ---
    
    @app.route('/')
    def index():
        # Get active categories for FAQs on landing page
        faqs = FAQ.query.limit(6).all()
        return render_template('index.html', faqs=faqs)

    # --- AUTHENTICATION ---

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password')
            role = request.form.get('role', 'customer') # Allow selecting role for development convenience
            
            # Simple validation
            if not username or not email or not password:
                flash('All fields are required.', 'danger')
                return render_template('register.html')
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists.', 'danger')
                return render_template('register.html')
                
            if User.query.filter_by(email=email).first():
                flash('Email already registered.', 'danger')
                return render_template('register.html')
            
            new_user = User(username=username, email=email, role=role)
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
            
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password')
            
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                flash(f'Welcome back, {user.username}!', 'success')
                if user.is_admin():
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'danger')
                
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

    # --- CUSTOMER FEATURES ---

    @app.route('/dashboard')
    @login_required
    def dashboard():
        if current_user.is_admin():
            return redirect(url_for('admin_dashboard'))
            
        # Get customer tickets
        tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.created_at.desc()).all()
        # Get recent conversations
        conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()
        
        return render_template('dashboard.html', tickets=tickets, conversations=conversations)

    @app.route('/chat/new')
    @login_required
    def new_chat():
        # Create a new conversation session
        conv = Conversation(user_id=current_user.id, title=f"Chat Session - {datetime.now().strftime('%b %d, %H:%M')}")
        db.session.add(conv)
        db.session.commit()
        
        # Add greeting message automatically
        greeting = Message(
            conversation_id=conv.id,
            sender='bot',
            message_text="Hello! I am your AI Customer Support assistant. How can I help you today? You can ask me about product info, orders, payments, refunds, or submit a support ticket.",
            intent='greeting',
            confidence=1.0
        )
        db.session.add(greeting)
        db.session.commit()
        
        return redirect(url_for('chat_session', conversation_id=conv.id))

    @app.route('/chat/<int:conversation_id>')
    @login_required
    def chat_session(conversation_id):
        conv = Conversation.query.get_or_404(conversation_id)
        # Security check: verify this chat belongs to the user
        if conv.user_id != current_user.id and not current_user.is_admin():
            flash('Access denied.', 'danger')
            return redirect(url_for('dashboard'))
            
        # Retrieve message history
        messages = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.asc()).all()
        return render_template('chat.html', conversation=conv, messages=messages)

    @app.route('/chat/history')
    @login_required
    def chat_history():
        conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()
        return render_template('dashboard.html', conversations=conversations, tickets=[]) # Reuse dashboard or show filter

    @app.route('/ticket/new', methods=['POST'])
    @login_required
    def new_ticket():
        subject = request.form.get('subject', '').strip()
        category = request.form.get('category', 'General')
        priority = request.form.get('priority', 'medium')
        description = request.form.get('description', '').strip()
        
        if not subject or not description:
            flash('Subject and description are required.', 'danger')
            return redirect(url_for('dashboard'))
            
        ticket = SupportTicket(
            user_id=current_user.id,
            subject=subject,
            category=category,
            priority=priority,
            description=description,
            status='pending'
        )
        db.session.add(ticket)
        db.session.commit()
        
        flash('Support ticket created successfully! We will get back to you shortly.', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/chat/<int:conversation_id>/escalate', methods=['POST'])
    @login_required
    def escalate_chat(conversation_id):
        conv = Conversation.query.get_or_404(conversation_id)
        if conv.user_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('dashboard'))
            
        # Mark conversation as escalated
        conv.status = 'escalated'
        
        # Gather last few user messages to form support ticket description
        user_msgs = Message.query.filter_by(conversation_id=conv.id, sender='user').order_by(Message.created_at.desc()).limit(3).all()
        user_msgs.reverse()
        
        description_parts = [f"Escalated from Chat Session #{conv.id}."]
        if user_msgs:
            description_parts.append("\nRecent customer queries in this chat:")
            for m in user_msgs:
                description_parts.append(f"- \"{m.message_text}\"")
        else:
            description_parts.append("\nNo messages sent yet.")
            
        # Create a support ticket automatically
        ticket = SupportTicket(
            user_id=current_user.id,
            subject=f"Escalated Support Request (Chat #{conv.id})",
            category="Technical",
            priority="high",
            description="\n".join(description_parts),
            status="pending"
        )
        db.session.add(ticket)
        
        # Save escalation bot response
        escalation_reply = Message(
            conversation_id=conv.id,
            sender='bot',
            message_text="I have escalated this conversation to a human support agent. A support ticket has been created on your behalf, and our team will follow up soon. You can track its status on your dashboard.",
            intent="escalate",
            confidence=1.0
        )
        db.session.add(escalation_reply)
        db.session.commit()
        
        flash('Your request has been escalated to a human agent. A support ticket was created.', 'success')
        return redirect(url_for('chat_session', conversation_id=conv.id))


    # --- CHATBOT REST API ---

    @app.route('/api/chat', methods=['POST'])
    def api_chat():
        data = request.get_json() or {}
        message_text = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        
        if not message_text or not conversation_id:
            return jsonify({'error': 'Message and conversation_id are required.'}), 400
            
        conv = Conversation.query.get(conversation_id)
        if not conv:
            return jsonify({'error': 'Conversation not found.'}), 404
            
        # If user is logged in, verify ownership
        if current_user.is_authenticated and conv.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'error': 'Unauthorized.'}), 403
            
        # 1. Save user message to database
        user_msg = Message(
            conversation_id=conv.id,
            sender='user',
            message_text=message_text
        )
        db.session.add(user_msg)
        db.session.commit()
        
        # 2. Get bot response from NLP engine
        intent, confidence, response_text = chatbot_engine.get_response(message_text)
        
        # 3. Save bot response to database
        bot_msg = Message(
            conversation_id=conv.id,
            sender='bot',
            message_text=response_text,
            intent=intent,
            confidence=confidence
        )
        db.session.add(bot_msg)
        db.session.commit()
        
        return jsonify({
            'response': response_text,
            'intent': intent,
            'confidence': confidence
        })


    # --- ADMIN ROUTES ---

    @app.route('/admin/dashboard')
    @login_required
    @admin_required
    def admin_dashboard():
        # KPI calculations
        total_users = User.query.count()
        total_conversations = Conversation.query.count()
        total_tickets = SupportTicket.query.count()
        resolved_tickets = SupportTicket.query.filter_by(status='resolved').count()
        pending_tickets = SupportTicket.query.filter_by(status='pending').count()
        
        # Recent queries
        recent_queries = Message.query.filter_by(sender='user').order_by(Message.created_at.desc()).limit(8).all()
        
        # Intent counts for Chart.js
        intent_stats = db.session.query(
            Message.intent, func.count(Message.id)
        ).filter(
            Message.sender == 'bot', Message.intent != None, Message.intent != ''
        ).group_by(Message.intent).all()
        
        intents_labels = [i[0] for i in intent_stats]
        intents_data = [i[1] for i in intent_stats]
        
        # Ticket status summary
        ticket_stats = db.session.query(
            SupportTicket.status, func.count(SupportTicket.id)
        ).group_by(SupportTicket.status).all()
        
        ticket_labels = [t[0].replace('_', ' ').capitalize() for t in ticket_stats]
        ticket_data = [t[1] for t in ticket_stats]

        # Conversations over last 7 days
        today = datetime.utcnow().date()
        daily_labels = []
        daily_counts = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            count = Conversation.query.filter(
                func.date(Conversation.created_at) == day_str
            ).count()
            daily_labels.append(day.strftime('%b %d'))
            daily_counts.append(count)

        # Monthly chatbot usage (last 6 months)
        monthly_labels = []
        monthly_counts = []
        for i in range(5, -1, -1):
            # approximate months
            first_of_month = (datetime.utcnow().replace(day=1) - timedelta(days=i*30)).replace(day=1).date()
            month_str = first_of_month.strftime('%Y-%m')
            count = Message.query.filter(
                func.strftime('%Y-%m', Message.created_at) == month_str
            ).count()
            monthly_labels.append(first_of_month.strftime('%b %Y'))
            monthly_counts.append(count)

        analytics = {
            'intents_labels': intents_labels,
            'intents_data': intents_data,
            'ticket_labels': ticket_labels,
            'ticket_data': ticket_data,
            'daily_labels': daily_labels,
            'daily_counts': daily_counts,
            'monthly_labels': monthly_labels,
            'monthly_counts': monthly_counts
        }
        
        return render_template(
            'admin/dashboard.html',
            total_users=total_users,
            total_conversations=total_conversations,
            total_tickets=total_tickets,
            resolved_tickets=resolved_tickets,
            pending_tickets=pending_tickets,
            recent_queries=recent_queries,
            analytics=analytics
        )

    @app.route('/admin/tickets', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_tickets():
        if request.method == 'POST':
            # Reply to ticket
            ticket_id = request.form.get('ticket_id')
            reply_text = request.form.get('admin_reply', '').strip()
            new_status = request.form.get('status', 'resolved')
            
            ticket = SupportTicket.query.get_or_404(ticket_id)
            ticket.admin_reply = reply_text
            ticket.status = new_status
            db.session.commit()
            
            flash(f"Replied to ticket #{ticket_id} and status updated to '{new_status}'.", 'success')
            return redirect(url_for('admin_tickets'))
            
        # GET request: load tickets
        tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
        return render_template('admin/tickets.html', tickets=tickets)

    @app.route('/admin/tickets/<int:ticket_id>/status', methods=['POST'])
    @login_required
    @admin_required
    def admin_update_ticket_status(ticket_id):
        status = request.form.get('status')
        ticket = SupportTicket.query.get_or_404(ticket_id)
        if status in ['pending', 'in_progress', 'resolved']:
            ticket.status = status
            db.session.commit()
            flash(f"Ticket #{ticket_id} status updated to {status}.", 'success')
        return redirect(url_for('admin_tickets'))

    @app.route('/admin/faqs')
    @login_required
    @admin_required
    def admin_faqs():
        faqs = FAQ.query.order_by(FAQ.category, FAQ.question).all()
        return render_template('admin/faqs.html', faqs=faqs)

    @app.route('/admin/faqs/add', methods=['POST'])
    @login_required
    @admin_required
    def admin_add_faq():
        question = request.form.get('question', '').strip()
        answer = request.form.get('answer', '').strip()
        category = request.form.get('category', 'General').strip()
        
        if not question or not answer:
            flash('Question and answer are required.', 'danger')
            return redirect(url_for('admin_faqs'))
            
        faq = FAQ(question=question, answer=answer, category=category)
        db.session.add(faq)
        db.session.commit()
        
        flash('FAQ added successfully.', 'success')
        return redirect(url_for('admin_faqs'))

    @app.route('/admin/faqs/edit/<int:faq_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_edit_faq(faq_id):
        faq = FAQ.query.get_or_404(faq_id)
        faq.question = request.form.get('question', '').strip()
        faq.answer = request.form.get('answer', '').strip()
        faq.category = request.form.get('category', 'General').strip()
        
        db.session.commit()
        flash('FAQ updated successfully.', 'success')
        return redirect(url_for('admin_faqs'))

    @app.route('/admin/faqs/delete/<int:faq_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_faq(faq_id):
        faq = FAQ.query.get_or_404(faq_id)
        db.session.delete(faq)
        db.session.commit()
        flash('FAQ deleted successfully.', 'success')
        return redirect(url_for('admin_faqs'))

    @app.route('/admin/users')
    @login_required
    @admin_required
    def admin_users():
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('admin/users.html', users=users)

    @app.route('/admin/users/<int:user_id>/role', methods=['POST'])
    @login_required
    @admin_required
    def admin_update_user_role(user_id):
        role = request.form.get('role')
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash('You cannot change your own role.', 'warning')
            return redirect(url_for('admin_users'))
            
        if role in ['customer', 'admin']:
            user.role = role
            db.session.commit()
            flash(f"User {user.username} role updated to {role}.", 'success')
        return redirect(url_for('admin_users'))

    @app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_user(user_id):
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash('You cannot delete your own account.', 'warning')
            return redirect(url_for('admin_users'))
            
        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.username} deleted successfully.", 'success')
        return redirect(url_for('admin_users'))

    @app.route('/admin/chats')
    @login_required
    @admin_required
    def admin_chats():
        conversations = Conversation.query.order_by(Conversation.created_at.desc()).all()
        return render_template('admin/chat_history.html', conversations=conversations)

    @app.route('/admin/chats/<int:conversation_id>')
    @login_required
    @admin_required
    def admin_chat_detail(conversation_id):
        conv = Conversation.query.get_or_404(conversation_id)
        messages = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.asc()).all()
        return render_template('admin/chat_detail.html', conversation=conv, messages=messages)

    # --- DATABASE INITIALIZATION & RETRAINING ---
    
    with app.app_context():
        # Create all tables if they don't exist
        db.create_all()
        
        # 1. Seed default accounts if empty
        if not User.query.first():
            # Seed Admin
            admin_user = User(username='admin', email='admin@support.com', role='admin')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            
            # Seed Customer
            customer_user = User(username='customer', email='customer@support.com', role='customer')
            customer_user.set_password('customer123')
            db.session.add(customer_user)
            
            db.session.commit()
            print("Default users seeded: admin/admin123 and customer/customer123")
            
        # 2. Seed FAQs if empty
        if not FAQ.query.first():
            default_faqs = [
                FAQ(question="What is your return policy?", answer="We offer a 30-day money-back guarantee for unused items in their original packaging. You can request a refund directly through the support system.", category="Refunds"),
                FAQ(question="What payment methods do you accept?", answer="We accept all major credit cards (Visa, MasterCard, American Express), PayPal, and Apple Pay.", category="Payments"),
                FAQ(question="How do I track my order?", answer="To track your order, you can ask our chatbot or look under the order tracking page in your account dashboard. You will need your Order ID.", category="Orders"),
                FAQ(question="How can I contact technical support?", answer="You can submit a support ticket via your dashboard, or escalate your chat conversation with our AI chatbot to a human agent.", category="Technical")
            ]
            db.session.bulk_save_objects(default_faqs)
            db.session.commit()
            print("Default FAQs seeded.")

        # 3. Seed Chatbot Intents if empty
        if not ChatbotIntent.query.first():
            intents_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chatbot', 'intents.json')
            if os.path.exists(intents_file):
                try:
                    with open(intents_file, 'r') as f:
                        data = json.load(f)
                        db_intents = []
                        for item in data.get('intents', []):
                            db_intent = ChatbotIntent(
                                intent_name=item['intent_name'],
                                patterns=json.dumps(item['patterns']),
                                responses=json.dumps(item['responses'])
                            )
                            db_intents.append(db_intent)
                        db.session.bulk_save_objects(db_intents)
                        db.session.commit()
                        print("Intents table seeded from intents.json.")
                except Exception as e:
                    print(f"Error seeding intents: {e}")

        # 4. Train Chatbot on Startup from Database
        try:
            db_intents = ChatbotIntent.query.all()
            chatbot_engine.train_and_save(db_intents)
            print("Chatbot NLP engine retrained successfully from database entries.")
        except Exception as e:
            print(f"Error training NLP model on startup: {e}")

    return app

app = create_app()

if __name__ == '__main__':
    # Run server locally
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
