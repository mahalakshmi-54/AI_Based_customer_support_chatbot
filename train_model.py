import os
import sys

# Ensure parent directory is in path so we can import chatbot_engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.chatbot_engine import chatbot_engine

def train():
    print("Training chatbot model...")
    success = chatbot_engine.train_and_save()
    if success:
        print("Success! Model trained and saved as model.pkl.")
    else:
        print("Error: Training failed.")

if __name__ == "__main__":
    train()
