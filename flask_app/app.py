from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory user storage for demonstration purposes
users = {}

@app.route('/users', methods=['GET'])
def get_users():
    return jsonify(users), 200

@app.route('/users', methods=['POST'])
def create_user():
    user_id = request.json.get('user_id')
    user_type = request.json.get('user_type')
    
    if not user_id or not user_type:
        return jsonify({"error": "User ID and User Type are required."}), 400

    if user_id in users:
        return jsonify({"error": "User already exists."}), 400

    users[user_id] = {"user_id": user_id, "user_type": user_type}
    return jsonify(users[user_id]), 201

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    user = users.get(user_id)
    if user:
        return jsonify(user), 200
    return jsonify({"error": "User not found."}), 404

if __name__ == '__main__':
    app.run(debug=True) 