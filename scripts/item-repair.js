const fs = require('fs');
const path = require('path');

// Define the file path
const filePath = path.join(__dirname, '../data/local/lng/strings/item-names.json');

// Read the JSON file
fs.readFile(filePath, 'utf8', (err, data) => {
    if (err) {
        console.error('Error reading file:', err);
        return;
    }

    // Parse the JSON data
    let items = JSON.parse(data);

    // Sort the array by the `id` field
    items.sort((a, b) => a.id - b.id);

    // Reassign the `id` field to be sequential starting from 1060
    let newId = 1060;
    items.forEach(item => {
        item.id = newId++;
    });

    // Write the modified array back to the JSON file
    fs.writeFile(filePath, JSON.stringify(items, null, 4), 'utf8', (err) => {
        if (err) {
            console.error('Error writing file:', err);
            return;
        }
        console.log('File has been updated.');
    });
});