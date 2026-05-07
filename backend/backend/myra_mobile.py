from flask import Flask, request, jsonify
import json

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "name": "Myra AI",
        "status": "running on mobile",
        "message": "Main yahan hoon! /chat par message bhejo"
    })

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'GET':
        msg = request.args.get('message', '')
    else:
        data = request.get_json()
        msg = data.get('message', '') if data else ''
    
    if not msg:
        return jsonify({"error": "Kuch to bolo! message bhejo"})
    
    # Simple responses
    responses = {
        "hi": "Hello! Main Myra, aapki AI assistant",
        "hello": "! Kaise ho?",
        "kaise ho": "Main theek hoon, aap batao?",
        "name": "Mera naam Myra hai",
        "bye": "Bye! Phir baat karte hain"
    }
    
    reply = responses.get(msg.lower(), f"Aapne kaha: {msg}")
    
    return jsonify({
        "reply": reply,
        "you": msg
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🤖 MYRA AI IS RUNNING ON MOBILE!")
    print("="*50)
    print("📱 Browser me kholo: http://localhost:5000")
    print("💬 Chat karo: http://localhost:5000/chat?message=hello")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
