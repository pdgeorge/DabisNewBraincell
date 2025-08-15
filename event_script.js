const socket = new WebSocket('ws://localhost:8002');

// Connection opened
socket.addEventListener('open', function (event) {
    console.log('WebSocket connection opened');
});

// Listen for messages
socket.addEventListener('message', function (event) {
    console.log('Message from server:', event.data);

    // Assuming the server sends a new image URL as plain text
    const newImageUrl = event.data;

    // Update the image src
    const image = document.getElementById('AIimage');
    image.src = newImageUrl;
});

// Handle WebSocket connection close
socket.addEventListener('close', function (event) {
    console.log('WebSocket connection closed');
});

// Handle WebSocket errors
socket.addEventListener('error', function (event) {
    console.error('WebSocket error:', event);
});
