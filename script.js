console.log("Just to prove script is working")

// {type: "updateMouth", size: 1, message: "string"} // Open
// {type: "updateMouth", size: 0, message: "string"} // Closed

var url = 'ws://localhost:8001/api'

let ws

function showMessage(message) {
    window.setTimeout(() => window.alert(message), 50);
}

function iterateArrayWithDelay(inputArray) {
    console.log(inputArray);
    inputArray = inputArray.map(parseFloat);
    console.log(inputArray);
    let i = 0;
    let interval = setInterval(function() {
        if (i >= inputArray.length) {
            clearInterval(interval);
            console.log('Interval complete');
            return;
        }
        setFrame(Math.round(inputArray[i])+1);
        console.log('28 i is: ' + i);
        i += 1;
    }, 1000); 
}

function connect(){    
    ws = new WebSocket('ws://localhost:8001');

    ws.onopen = () => {
        console.log('WebSocket connection opened');
        // ws.send(`{"msg_user": "Pdgeorge", "msg_server": "pdgeorge", "msg_msg": "Wake up Dabi, it's time to get to work.", "formatted_msg": "twitch:Pdgeorge: Wake up Dabi, it's time to get to work."}`)
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Received data:', data);
        switch (data.type) {
            case 'updateMouth':
                // setFrame(data.size);
                iterateArrayWithDelay(data.pattern);
                break;
            default:
                console.log(`There is no ${data.type} prepared.`)
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket connection closed. Attempting to reconnect in 1 second...');
        setTimeout(connect, 1000); // Attempt to reconnect after 1 second
    };
}


// Everything below this is for 2 frame Dabi
function setFrame(frame) {
    console.log('set frame', frame);
    resetFrames();

    document.querySelectorAll('img')[frame - 1].style.display = 'block';
}

function resetFrames() {
    document.querySelectorAll('img').forEach(function (entry) {
        entry.style.display = 'none';
    });
}

setFrame(1);
connect();
