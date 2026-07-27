import os
import re
import math
import random
import pickle
import json

# Standard English stopwords to filter out noise
STOP_WORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd",
    'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers',
    'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
    'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
    'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out',
    'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't",
    'should', "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn',
    "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't",
    'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't",
    'shouldn', "shouldn't", 'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
}

def clean_text(text):
    """Lowercase text, remove punctuation, and tokenize."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    tokens = text.split()
    # Filter stopwords and short terms
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]
    return tokens

class SimpleTFIDF:
    def __init__(self):
        self.vocab = {}          # word -> index
        self.idf = []            # list of idf values matching vocab index
        self.doc_vectors = []    # list of L2-normalized document vectors
        self.doc_intents = []    # list of intents matching doc_vectors
        self.intents_data = {}   # intent_name -> list of responses

    def fit(self, training_data):
        """
        training_data format:
        [
            {"intent_name": "greeting", "patterns": ["hi", "hello"], "responses": ["Hey!"]}
        ]
        """
        self.vocab = {}
        self.idf = []
        self.doc_vectors = []
        self.doc_intents = []
        self.intents_data = {}

        # 1. Parse data, save responses and gather all patterns
        all_docs = []
        doc_intent_names = []

        for item in training_data:
            intent = item["intent_name"]
            self.intents_data[intent] = item["responses"]
            for pattern in item["patterns"]:
                tokens = clean_text(pattern)
                if tokens:
                    all_docs.append(tokens)
                    doc_intent_names.append(intent)

        if not all_docs:
            # Fallback if no documents contain words after filtering
            all_docs = [["hello"]]
            doc_intent_names = ["greeting"]
            self.intents_data["greeting"] = ["Hello!"]

        # 2. Build Vocabulary
        vocab_set = sorted(list(set(word for doc in all_docs for word in doc)))
        self.vocab = {word: idx for idx, word in enumerate(vocab_set)}
        vocab_size = len(self.vocab)

        # 3. Calculate IDF
        num_docs = len(all_docs)
        doc_counts = [0] * vocab_size
        for doc in all_docs:
            unique_words = set(doc)
            for word in unique_words:
                if word in self.vocab:
                    doc_counts[self.vocab[word]] += 1

        self.idf = [0.0] * vocab_size
        for i in range(vocab_size):
            # Standard smooth IDF: ln((1 + N) / (1 + DF)) + 1
            self.idf[i] = math.log((1 + num_docs) / (1 + doc_counts[i])) + 1.0

        # 4. Vectorize documents (patterns)
        for tokens, intent in zip(all_docs, doc_intent_names):
            vector = self._vectorize_tokens(tokens)
            self.doc_vectors.append(vector)
            self.doc_intents.append(intent)

    def _vectorize_tokens(self, tokens):
        """Convert a list of tokens to an L2-normalized TF-IDF vector."""
        vocab_size = len(self.vocab)
        vector = [0.0] * vocab_size
        if not tokens:
            return vector

        # Term counts
        counts = {}
        for token in tokens:
            if token in self.vocab:
                counts[token] = counts.get(token, 0) + 1

        # TF * IDF
        for word, count in counts.items():
            idx = self.vocab[word]
            tf = count / len(tokens)
            vector[idx] = tf * self.idf[idx]

        # L2 normalization
        magnitude = math.sqrt(sum(val ** 2 for val in vector))
        if magnitude > 0:
            vector = [val / magnitude for val in vector]

        return vector

    def predict(self, query):
        """
        Predict the intent, similarity score (confidence), and returns a response.
        """
        tokens = clean_text(query)
        # If the cleaned text is empty, check for raw greetings or fallbacks
        if not tokens:
            # Check basic words directly if tokens filter everything out
            raw_words = query.lower().strip().split()
            if any(w in ["hi", "hello", "hey", "hola", "yo"] for w in raw_words):
                return "greeting", 0.8, random.choice(self.intents_data.get("greeting", ["Hello!"]))
            return "fallback", 0.0, self.get_fallback_response()

        query_vector = self._vectorize_tokens(tokens)
        
        # Calculate Cosine Similarities (dot products since normalized)
        best_intent = "fallback"
        best_score = 0.0

        for doc_vector, intent in zip(self.doc_vectors, self.doc_intents):
            score = sum(q * d for q, d in zip(query_vector, doc_vector))
            if score > best_score:
                best_score = score
                best_intent = intent

        # Intent classification threshold
        threshold = 0.18
        if best_score >= threshold and best_intent in self.intents_data:
            responses = self.intents_data[best_intent]
            response = random.choice(responses)
            return best_intent, round(best_score, 4), response
        else:
            return "fallback", round(best_score, 4), self.get_fallback_response()

    def get_fallback_response(self):
        fallbacks = [
            "I'm not sure I understand. Could you rephrase your question?",
            "I'm sorry, I didn't quite get that. Can you provide more details?",
            "I don't have information on that topic. Would you like me to connect you to a human customer agent?",
            "I'm still learning and couldn't match your query. You can ask about order status, returns, technical support, or billing. Alternatively, you can escalate this issue."
        ]
        return random.choice(fallbacks)


# Global Engine Manager
class ChatbotEngine:
    def __init__(self, model_dir=None):
        if model_dir is None:
            model_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_dir = model_dir
        self.model_path = os.path.join(self.model_dir, "model.pkl")
        self.intents_json_path = os.path.join(self.model_dir, "intents.json")
        self.model = None

    def load_model(self):
        """Load model from pickle, or auto-train if not found."""
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                # Quick verification
                if hasattr(self.model, "vocab") and self.model.vocab:
                    return True
            except Exception as e:
                print(f"Error loading model pickle: {e}. Retraining...")
        
        # Train and save on the fly
        return self.train_and_save()

    def train_and_save(self, db_intents=None):
        """Train the TF-IDF model on intents.json and optional DB overrides, and save model.pkl."""
        training_data = []

        # Load from DB intents if provided
        if db_intents:
            for item in db_intents:
                try:
                    patterns = json.loads(item.patterns)
                    responses = json.loads(item.responses)
                    training_data.append({
                        "intent_name": item.intent_name,
                        "patterns": patterns,
                        "responses": responses
                    })
                except Exception as e:
                    print(f"Error loading DB intent {item.intent_name}: {e}")

        # Fallback/merge with default intents.json
        if not training_data and os.path.exists(self.intents_json_path):
            try:
                with open(self.intents_json_path, "r") as f:
                    data = json.load(f)
                    training_data = data.get("intents", [])
            except Exception as e:
                print(f"Error loading intents.json: {e}")

        if not training_data:
            # Minimal fallback dataset
            training_data = [
                {
                    "intent_name": "greeting",
                    "patterns": ["hi", "hello", "hey", "greetings"],
                    "responses": ["Hello! How can I help you today?"]
                }
            ]

        # Train simple TF-IDF
        model = SimpleTFIDF()
        model.fit(training_data)
        self.model = model

        # Save to model.pkl
        try:
            os.makedirs(self.model_dir, exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump(model, f)
            return True
        except Exception as e:
            print(f"Error saving model.pkl: {e}")
            return False

    def get_response(self, message):
        """Get response for message. Lazy loads if model is not loaded."""
        if not self.model:
            self.load_model()
        return self.model.predict(message)


# Single shared instance of ChatbotEngine
chatbot_engine = ChatbotEngine()
