from flask import Flask, request, jsonify,render_template
from pymongo import MongoClient
from datetime import datetime
from bson import json_util  # Import json_util
import os

app = Flask(__name__)
client=MongoClient(os.getenv('URI'))
db = client['test']  # Create a database called "github_events"
collection = db['my_collection']  # Collection to store GitHub events

# Serve plain text on the home route 
@app.route('/')
def index():
    return render_template('index.html')

    return '''
    <h1>Recent GitHub Events</h1>
    <ul id="events"></ul>

    <script>
        function fetchEvents() {
            fetch('/events')
                .then(response => response.json())
                .then(data => {
                    const eventsList = document.getElementById('events');
                    eventsList.innerHTML = '';  // Clear old data
                    if (!Array.isArray(data)){
                    data=Array.from(data)
                    }
                    data.forEach(event => {
                        const li = document.createElement('li');
                        li.textContent = `${event.author} ${event.action} to ${event.to_branch} on ${new Date(event.timestamp)}`;
                        eventsList.appendChild(li);
                    });
                });
        }

        // Poll the events every 15 seconds
        setInterval(fetchEvents, 15000);
        fetchEvents();  // Initial fetch on page load
    </script>
    '''


# Webhook endpoint to receive GitHub actions
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json
    if not data:
        return jsonify({"error": "No data received"}), 400
    event_type = request.headers.get('X-GitHub-Event')

    if event_type == "push":
        event_data = {
            "action": event_type,
            "author": data.get('sender', {}).get('login'),
            "from_branch": data.get('ref', '').split('/')[-1],  # Extract branch from ref
            "to_branch": "",  # Push event doesn't have a 'to_branch'
            "timestamp": datetime.utcnow()
        }
    elif event_type == "pull_request":
        event_data = {
            "action": event_type,
            "author": data.get('sender', {}).get('login'),
            "from_branch": data.get('pull_request', {}).get('head', {}).get('ref', ''),
            "to_branch": data.get('pull_request', {}).get('base', {}).get('ref', ''),  # Corrected to base.ref
            "timestamp": datetime.utcnow()
        }
    elif event_type == "merge":
        event_data = {
            "action": event_type,
            "author": data.get('sender', {}).get('login'),
            "from_branch": data.get('pull_request', {}).get('head', {}).get('ref', ''),
            "to_branch": data.get('pull_request', {}).get('base', {}).get('ref', ''),
            "timestamp": datetime.utcnow()
        }
    else:
        return jsonify({"error": "Unsupported event type"}), 400

    # Save event data to MongoDB
    collection.insert_one(event_data)
    return jsonify({"status": "success"}), 200

# API endpoint to fetch events for the UI 
@app.route('/events', methods=['GET'])
def get_events():
    # Fetch latest events (within the last 15 seconds) from MongoDB
    events = list(collection.find().sort("timestamp", -1).limit(10))
    formatted_events = []

    for event in events:
        action = event["action"]
        author = event["author"]
        from_branch = event["from_branch"]
        to_branch = event["to_branch"]
        timestamp = event["timestamp"].strftime("%d %b %Y - %I:%M %p UTC")

        if action == "push":
            formatted_event = f"{author} pushed to {to_branch} on {timestamp}"
        elif action == "pull_request":
            formatted_event = f"{author} submitted a pull request from {from_branch} to {to_branch} on {timestamp}"
        elif action == "merge":
            formatted_event = f"{author} merged branch {from_branch} to {to_branch} on {timestamp}"
        else:
            pass

        formatted_events.append(formatted_event)
    return json_util.dumps(formatted_events), 200
    #return jsonify(events), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
