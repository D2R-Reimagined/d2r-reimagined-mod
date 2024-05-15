const fs = require('fs');
const jsonPath = '../data/local/lng/strings/item-names.json';
const file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
let json = JSON.parse(file);

try {
    // Process each object in the array
    json = json.map(obj => {
        const defaultLanguageValue = obj.enUS;

        // Check and replace empty string properties with the 'enUS' value
        for (const key in obj) {
            if (obj[key] === "") {
                obj[key] = defaultLanguageValue;
            }
        }

        return obj;
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("File successfully written!");
        }
    });

} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}
