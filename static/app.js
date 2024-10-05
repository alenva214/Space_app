document.addEventListener('DOMContentLoaded', () => {
    const latitudeInput = document.getElementById('latitude');
    const longitudeInput = document.getElementById('longitude');
    const submitButton = document.getElementById('submit-location');
    const resultDiv = document.getElementById('result');
    const locationNameInput = document.getElementById('location-name');
    const cloudCoverageInput = document.getElementById('cloud-coverage');
    const notificationLeadTimeInput = document.getElementById('notification-lead-time');

    // Initialize the map
    const map = L.map('map').setView([0, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    let marker;

    map.on('click', (e) => {
        const { lat, lng } = e.latlng;
        latitudeInput.value = lat.toFixed(6);
        longitudeInput.value = lng.toFixed(6);

        if (marker) {
            map.removeLayer(marker);
        }
        marker = L.marker([lat, lng]).addTo(map);
    });

    submitButton.addEventListener('click', () => {
        const latitude = latitudeInput.value;
        const longitude = longitudeInput.value;
        const name = locationNameInput.value || `Location at ${latitude}, ${longitude}`;
        const cloudCoverage = cloudCoverageInput.value;
        const notificationLeadTime = notificationLeadTimeInput.value;
    
        if (latitude && longitude) {
            fetch('/submit_location', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    latitude,
                    longitude,
                    name,
                    cloud_coverage_threshold: cloudCoverage,
                    notification_lead_time: notificationLeadTime
                }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.overpasses && data.overpasses.length > 0) {
                    const overpassList = data.overpasses.map(time => `<li>${time}</li>`).join('');
                    resultDiv.innerHTML = `${data.message}<br>Upcoming Landsat overpasses:<ul>${overpassList}</ul>`;
                } else {
                    resultDiv.textContent = `${data.message}<br>No upcoming Landsat overpasses found for this location.`;
                }
                fetchSavedLocations();
            })
            .catch((error) => {
                console.error('Error:', error);
                resultDiv.textContent = 'An error occurred while submitting the location.';
            });
        } else {
            resultDiv.textContent = 'Please enter both latitude and longitude.';
        }
    });

    function fetchSavedLocations() {
        fetch('/get_locations')
            .then(response => response.json())
            .then(locations => {
                const locationList = document.getElementById('saved-locations');
                locationList.innerHTML = locations.map(loc => 
                    `<li>${loc.name} (${loc.latitude}, ${loc.longitude}) - Cloud coverage: ${loc.cloud_coverage_threshold}%, Notification lead time: ${loc.notification_lead_time}h</li>`
                ).join('');
            })
            .catch(error => console.error('Error:', error));
    }

    fetchSavedLocations();
});

document.getElementById('submit-location').addEventListener('click', () => {
    const latitude = document.getElementById('latitude').value;
    const longitude = document.getElementById('longitude').value;
    const name = document.getElementById('location-name').value;
    const cloudCoverage = document.getElementById('cloud-coverage').value;
    const notificationLeadTime = document.getElementById('notification-lead-time').value;

    if (latitude && longitude) {
        fetch('/submit_location', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                latitude: parseFloat(latitude),
                longitude: parseFloat(longitude),
                name: name,
                cloud_coverage_threshold: parseFloat(cloudCoverage),
                notification_lead_time: parseInt(notificationLeadTime)
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
            } else {
                alert(data.message);
                // Update the UI with the new location and Landsat data
                updateLocationList(data.location);
                displayLandsatData(data.landsat_data);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while submitting the location.');
        });
    } else {
        alert('Please enter both latitude and longitude.');
    }
});
