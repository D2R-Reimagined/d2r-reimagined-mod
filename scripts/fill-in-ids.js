const fs = require('fs');

let skipUntil = 30000;
/**
 * Item Modifiers
 */
let jsonPath = '../data/local/lng/strings/item-modifiers.json';
let file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
let json = JSON.parse(file);
let startingIndex = 48000; //Replace with whatever u want to start at;
try {
    // Process each object in the array
    json = json.map(obj => {
        return fillInIds(obj);
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("Item Modifiers successfully written!");
        }
    });
} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}


/**
 * Item Name Affixes
 */
jsonPath = '../data/local/lng/strings/item-nameaffixes.json';
file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
json = JSON.parse(file);
startingIndex = 49000;
try {
    // Process each object in the array
    json = json.map(obj => {
        return fillInIds(obj);
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("Item Name Affixes successfully written!");
        }
    });
} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}

/**
 * Item Names
 */
jsonPath = '../data/local/lng/strings/item-names.json';
file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
json = JSON.parse(file);
startingIndex = 50000;
try {
    // Process each object in the array
    json = json.map(obj => {
        return fillInIds(obj);
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("Item Names successfully written!");
        }
    });
} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}

/**
 * Item Runes
 */
jsonPath = '../data/local/lng/strings/item-runes.json';
file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
json = JSON.parse(file);
startingIndex = 53500;
try {
    // Process each object in the array
    json = json.map(obj => {
        return fillInIds(obj);
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("Item Runes successfully written!");
        }
    });
} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}

/**
 * Levels
 */
jsonPath = '../data/local/lng/strings/levels.json';
file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
json = JSON.parse(file);
startingIndex = 54000;
try {
    // Process each object in the array
    json = json.map(obj => {
        return fillInIds(obj);
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("Levels successfully written!");
        }
    });
} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}

/**
 * Monsters
 */
jsonPath = '../data/local/lng/strings/monsters.json';
file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
json = JSON.parse(file);
startingIndex = 55000;
try {
    // Process each object in the array
    json = json.map(obj => {
        return fillInIds(obj);
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("Monsters successfully written!");
        }
    });
} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}

/**
 * Skills
 */
jsonPath = '../data/local/lng/strings/skills.json';
file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
json = JSON.parse(file);
startingIndex = 56000;
try {
    // Process each object in the array
    json = json.map(obj => {
        return fillInIds(obj);
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("Skills successfully written!");
        }
    });
} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}

/**
 * UI
 */
jsonPath = '../data/local/lng/strings/ui.json';
file = fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, '');
json = JSON.parse(file);
startingIndex = 57000;
try {
    // Process each object in the array
    json = json.map(obj => {
        return fillInIds(obj);
    });

    // Overwrite the file with the modified JSON
    fs.writeFile(jsonPath, JSON.stringify(json, null, 4), err => {
        if (err) {
            console.error("Error writing file:", err);
        } else {
            console.log("UI successfully written!");
        }
    });
} catch (parseError) {
    console.error("Error parsing JSON:", parseError);
}


function fillInIds(obj) {
    if (obj.id < skipUntil) {
        return obj;
    }
    obj.id = startingIndex;
    startingIndex++;
    return obj;
}
