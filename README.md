# Behind The Page – TCP Chat Visualization

Behind The Page is a web-based TCP chat application built with Python to demonstrate real-time socket programming. The project implements a multi-client chat system using low-level TCP sockets and visualizes socket events live in a browser dashboard.

The goal of the project is to make TCP communication easier to understand by showing events such as client connection, message sending, message receiving, disconnection, and the TCP handshake flow.

## Features

* Multi-client TCP chat system
* Real-time socket event visualization
* TCP server using Python sockets
* Client connection handling using threading
* Live dashboard using Flask and Flask-SocketIO
* TCP handshake animation: SYN, SYN-ACK, ACK
* Message broadcasting between connected clients
* Cross-network testing support using ngrok

## Technologies Used

* Python
* TCP Sockets
* Flask
* Flask-SocketIO
* Python Threading
* HTML
* CSS
* JavaScript
* ngrok

## Project Structure

```text
behind-the-page-tcp-chat-visualization/
│
├── app.py
├── server.py
├── tcp_client.py
├── requirements.txt
├── README.md
└── templates/
    └── index.html
```

## How It Works

The project separates the TCP communication logic from the web dashboard.

* `server.py` handles the TCP server using `socket()`, `bind()`, `listen()`, and `accept()`.
* `tcp_client.py` creates TCP client connections and handles sending and receiving messages.
* `app.py` connects the TCP chat system to the Flask-SocketIO dashboard.
* `index.html` displays the chat interface and real-time socket visualization.

Each browser session creates its own TCP client connection. When users connect, send messages, or disconnect, the dashboard updates live to show the related socket events.

## TCP Concepts Demonstrated

* `socket()`
* `bind()`
* `listen()`
* `accept()`
* `connect()`
* `send()`
* `recv()`
* `close()`

## Running the Project

Install the required libraries:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python app.py
```

Open the browser at:

```text
http://127.0.0.1:5000
```

## Testing

The project was tested with:

* Multiple browser tabs on the same machine
* Multiple users connected at the same time
* Local network access
* Cross-network access using ngrok

## Contributors

* Assil Sabbagh
* Cynthia Issa

## Conclusion

This project demonstrates how TCP socket programming works in a real multi-client application. The live dashboard helps visualize networking concepts that are usually hidden, making the project useful for learning socket programming, TCP communication, and client-server architecture.
