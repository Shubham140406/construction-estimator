document.addEventListener('DOMContentLoaded', () => {
    // --- CHATBOT UI ELEMENT REFERENCES ---
    const chatWindow = document.getElementById('chat-window');
    const toggleBtn = document.getElementById('chatbot-toggle-btn');
    const closeBtn = document.getElementById('close-chat-btn');
    const chatBody = document.getElementById('chat-body');
    const chatInput = document.getElementById('chat-input');
    const chatSubmitBtn = document.getElementById('chat-submit-btn');

    // --- CHATBOT EVENT LISTENERS ---
    toggleBtn.addEventListener('click', () => toggleChatWindow());
    closeBtn.addEventListener('click', () => toggleChatWindow(false));
    chatSubmitBtn.addEventListener('click', handleUserInput);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleUserInput();
        }
    });

    // --- "AI" KNOWLEDGE BASE & COMMANDS ---
    const commandRegistry = [
        // Existing commands (no changes)
        { name: 'greeting', regex: /^(hi|hello|hey|yo)$/i, handler: handleGreeting },
        { name: 'add_element', regex: /(?:add|insert)\s(?:an?|(\d+))?\s*(circular|square|rectangle)?\s*(footing|column|beam|slab|wall)s?\s(?:of|with|at|dimensions)?\s?(\d*\.?\d+)\s?(?:x|by)\s?(\d*\.?\d+)(?:\s?(?:x|by)\s?(\d*\.?\d+))?/i, handler: handleAddingElement },
        { name: 'add_custom_item', regex: /(?:add|insert)\s(?:an?|(\d+))?\s(.+?)\s(?:of|at|for|costing|price|range)\s(?:of)?\s?₹?(\d*\.?\d+)/i, handler: handleAddingCustomItem },
        { name: 'update_rate', regex: /(?:set|update)\s(.+?)\s(?:rate|cost)\s(?:to|is)\s?₹?(\d*\.?\d+)/i, handler: handleUpdateRate },
        
        // **NEW** More powerful and flexible commands
        { name: 'clear_section', regex: /(?:clear|remove|delete)\s(?:all)?\s*(footings|columns|beams|slabs|walls|plumbing|electrical)/i, handler: handleClearSection },
        { name: 'count_items', regex: /(?:how many|count)\s*(footings|columns|beams|slabs|walls|plumbing items|electrical items)\s*(?:are there|have i added)?/i, handler: handleCountItems },
        { name: 'navigate', regex: /(?:go to|show me|open)\s(?:the)?\s*(substructure|superstructure|masonry|brickwork|plumbing|electrical|rates)\s*(?:section|tab|part)?/i, handler: handleNavigation },
        { name: 'calculation', regex: /(?:calculate|what is|compute|convert)\s(.+)/i, handler: handleCalculation },
        { name: 'query_info', regex: /(what is|what's|tell me about|explain|show me|define)\s(?:the|an?)?\s?(.+)/i, handler: handleInfoRequest },
        { name: 'help', regex: /help/i, handler: handleHelp },
        { name: 'clear_chat', regex: /clear chat/i, handler: () => { chatBody.innerHTML = ''; addBotMessage("Chat cleared!"); } }
    ];

    // **NEW & EXPANDED** Knowledge Base
    const knowledgeBase = {
        'steel percentage': "Steel percentage is a crucial assumption for RCC cost. In this app, we assume:<ul><li><b>Footings:</b> 1.0%</li><li><b>Columns:</b> 2.5%</li><li><b>Beams:</b> 2.0%</li><li><b>Slabs:</b> 1.2%</li></ul>These percentages are relative to the total concrete volume of the element.",
        'm20': "M20 is a grade of concrete with a characteristic compressive strength of 20 N/mm². The mix ratio used in this estimator is <b>1:1.5:3</b> (1 part Cement, 1.5 parts Sand, 3 parts Aggregate). It's a very common grade for residential RCC work.",
        'mortar mix': "The mortar mix for brickwork is assumed to be <b>1:6</b> (1 part Cement, 6 parts Sand). This is a standard mix for masonry walls that are not load-bearing.",
        'bricks per m3': "We assume <b>500 standard bricks</b> are needed for every cubic meter (m³) of brickwork. This accounts for the volume of the bricks themselves plus the mortar joints.",
        'dry volume': "The dry volume factor (1.54 for concrete, 1.33 for mortar) is used because sand and aggregate have voids between particles. We need to account for this extra volume of dry materials to achieve the desired wet, compacted volume.",
        'plinth area': "The Plinth Area method is a quick estimation technique. It multiplies the total built-up area of a building by a standard cost per square meter. It's great for initial budgeting but is less accurate than the detailed 'Pro Estimator'.",
        'density': "Density is mass per unit volume. We use it to convert volumes of materials to weight (kilograms). The key assumptions are:<ul><li><b>Cement:</b> 1440 kg/m³</li><li><b>Steel:</b> 7850 kg/m³</li></ul>",
        'rcc': "RCC stands for Reinforced Cement Concrete. It's a composite material where concrete's high compressive strength is combined with steel's high tensile strength (from reinforcement bars, or 'rebar'). This makes it ideal for beams, slabs, and columns.",
        'pcc': "PCC stands for Plain Cement Concrete. It's concrete without any steel reinforcement. It has good compressive strength but is weak in tension. It's often used in foundations below the main RCC footing as a leveling course.",
        'curing': "Curing is the process of maintaining adequate moisture and temperature in concrete after it's been placed. It's critical for hydration of the cement, which allows the concrete to achieve its designed strength. Curing usually involves keeping the surface wet for 7-14 days.",
        'formwork': "Formwork (or shuttering) is the temporary mold or structure used to contain fresh concrete and shape it into the desired form. It is removed after the concrete has gained sufficient strength.",
        'dpc': "DPC stands for Damp-Proof Course. It's a waterproof barrier, usually a layer of plastic or specialized mortar, laid at the plinth level to prevent ground moisture from rising into the walls.",
        'brands': (query) => {
            const itemMap = { 'faucet': 'faucet', 'tap': 'faucet', 'toilet': 'toilet_flush', 'flush': 'toilet_flush', 'pipe': 'pipes', 'fan': 'fan', 'light': 'light', 'wire': 'wire' };
            const itemKey = Object.keys(itemMap).find(key => query.includes(key));
            return itemKey ? getBrandNamesFor(itemMap[itemKey]) : "I can provide brand info for faucets, toilets, pipes, fans, lights, and wires. Which one are you interested in?";
        }
    };

    // --- CHATBOT CORE FUNCTIONS ---

    function toggleChatWindow(forceOpen = null) {
        const isHidden = chatWindow.classList.contains('hidden');
        if (forceOpen === true || (forceOpen === null && isHidden)) {
            chatWindow.classList.remove('hidden');
            if (chatBody.children.length === 0) {
                addBotMessage("Hello! I'm your Estimator Assistant. How can I help? Type 'help' to see what I can do.", true);
            }
            chatInput.focus();
        } else {
            chatWindow.classList.add('hidden');
        }
    }

    function handleUserInput() {
        const userInput = chatInput.value.trim();
        if (userInput === '') return;
        addUserMessage(userInput);
        processCommand(userInput);
        chatInput.value = '';
    }

    function processCommand(userInput) {
        for (const command of commandRegistry) {
            const match = userInput.toLowerCase().match(command.regex);
            if (match) {
                // Prevent 'what is' from matching 'calculate what is'
                if (command.name === 'calculation' && commandRegistry.find(c => c.name === 'query_info' && userInput.toLowerCase().match(c.regex))) {
                    continue;
                }
                command.handler(match);
                return;
            }
        }
        handleUnknownCommand(userInput);
    }

    // --- CHATBOT ACTION HANDLERS (Existing & New) ---

    function handleGreeting() {
        const responses = ["Hello there!", "Hi! How can I assist with your estimate today?", "Hey! Ready to calculate some costs."];
        addBotMessage(responses[Math.floor(Math.random() * responses.length)]);
    }
    
    function handleAddingCustomItem(match) {
        const [_, quantityStr, itemName, price] = match;
        const quantity = parseInt(quantityStr) || 1;
        const itemCategories = {
            plumbing: ['tap', 'faucet', 'toilet', 'flush', 'basin', 'shower', 'pipe', 'sink', 'geyser'],
            electrical: ['fan', 'light', 'switch', 'socket', 'wire', 'mcb', 'fuse']
        };
        let category = null;
        if (itemCategories.plumbing.some(keyword => itemName.includes(keyword))) { category = 'plumbing'; } 
        else if (itemCategories.electrical.some(keyword => itemName.includes(keyword))) { category = 'electrical'; }
        if (!category) { addBotMessage(`I'm not sure if '${itemName}' is a plumbing or electrical item. Could you be more specific?`); return; }
        const itemType = itemName.trim().replace(/\s/g, '_');
        const brand = category === 'plumbing' ? 'CustomPlumbing' : 'CustomElectrical';
        addItemToForm(itemType, brand, quantity, 0, parseFloat(price));
        addBotMessage(`OK, I've added ${quantity} custom '${itemName}'(s) at ₹${price} each to the ${category} section.`);
        // **MODIFIED** - Now uses the navigation handler
        handleNavigation([null, category]); 
    }

    function handleAddingElement(match) {
        const [_, quantityStr, shape, elementType, dim1, dim2, dim3] = match;
        const quantity = parseInt(quantityStr) || 1;
        const dims = [dim1, dim2, dim3].filter(Boolean);
        if (!['footing', 'column', 'beam', 'slab', 'wall'].includes(elementType)) {
            addBotMessage(`I can't add an element of type '${elementType}'.`);
            return;
        }
        addBotMessage(`Sure, adding ${quantity} ${shape || ''} ${elementType}(s) with dimensions ${dims.join('x')}.`);
        const accordionMap = { footing: 'substructure', column: 'superstructure', beam: 'superstructure', slab: 'superstructure', wall: 'masonry' };
        handleNavigation([null, accordionMap[elementType]]); // Navigate to the right section
        
        // Timeout allows the accordion to open before we add the element
        setTimeout(() => {
            for (let i = 0; i < quantity; i++) {
                const addButton = document.querySelector(`button[onclick="addElement('${elementType}')"]`);
                if (!addButton) return;
                addButton.click();
                const container = document.getElementById(`${elementType}s-container`);
                const newGroup = container.lastElementChild;
                if (!newGroup) return;
                // ... (rest of the logic is the same as your original file)
                 try {
                    const inputs = { length: newGroup.querySelector('input[name="length[]"]'), width: newGroup.querySelector('input[name="width[]"]'), height: newGgroup.querySelector('input[name="height[]"]'), depth: newGroup.querySelector('input[name="depth[]"]'), thickness: newGroup.querySelector('input[name="thickness[]"]') };
                    const shapeSelect = newGroup.querySelector('select[name="type[]"]');
                    if (shapeSelect && shape) { shapeSelect.value = shape.charAt(0).toUpperCase() + shape.slice(1); updateShapeFields(shapeSelect); }
                    if (elementType === 'footing' || elementType === 'beam' || elementType === 'slab') { if (inputs.length) inputs.length.value = dims[0] || ''; if (inputs.width) inputs.width.value = dims[1] || ''; if (inputs.depth) inputs.depth.value = dims[2] || ''; } 
                    else if (elementType === 'column') { if (shape === 'circular') { if (inputs.length) inputs.length.value = dims[0] || ''; if (inputs.height) inputs.height.value = dims[1] || ''; } else { if (inputs.length) inputs.length.value = dims[0] || ''; if (inputs.width) inputs.width.value = dims[1] || ''; if (inputs.height) inputs.height.value = dims[2] || ''; } } 
                    else if (elementType === 'wall') { if (inputs.length) inputs.length.value = dims[0] || ''; if (inputs.height) inputs.height.value = dims[1] || ''; if (inputs.thickness) inputs.thickness.value = dims[2] || ''; }
                    if (i === quantity - 1) { newGroup.scrollIntoView({ behavior: 'smooth', block: 'center' }); newGroup.style.transition = 'background-color 0.5s'; newGroup.style.backgroundColor = '#dbeafe'; setTimeout(() => { newGroup.style.backgroundColor = '#fafafa'; }, 2000); }
                } catch (error) { addBotMessage(`I added the ${elementType}, but had trouble setting dimensions.`); console.error("Chatbot Error:", error); }
            }
        }, 500); // 500ms delay for accordion animation
    }
    
    function handleUpdateRate(match) {
        const [_, material, rate] = match;
        const materialKey = material.trim().toLowerCase().replace(/\s/g, '_');
        const inputElement = document.getElementById(`rate_${materialKey}`);
        if (inputElement) {
            inputElement.value = rate;
            addBotMessage(`Done! I've updated the rate for ${material} to ${rate}.`);
            handleNavigation([null, 'rates']); // Navigate to rates tab
            inputElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            inputElement.style.transition = 'background-color 0.5s';
            inputElement.style.backgroundColor = '#fef9c3';
            setTimeout(() => { inputElement.style.backgroundColor = '#f8fafc'; }, 2000);
        } else {
            addBotMessage(`I couldn't find an input for '${material}'. Please check the spelling or update it manually on the 'Rates' tab.`);
        }
    }

    // **MODIFIED** More robust info request handler
    function handleInfoRequest(match) {
        const query = match[2].toLowerCase().replace('?', '').trim();
        const keywords = Object.keys(knowledgeBase);
        const foundKeyword = keywords.find(k => query.includes(k));

        if (foundKeyword) {
            const answer = knowledgeBase[foundKeyword];
            addBotMessage(typeof answer === 'function' ? answer(query) : answer, true);
        } else {
            addBotMessage("I'm not sure about that. I can answer questions about construction topics like:<ul><li>RCC, PCC, Curing, DPC</li><li>M20 & Mortar mix ratios</li><li>Material densities & properties</li><li>Available brands for fixtures</li></ul><p class='mt-2'>Try asking 'What is RCC?' or 'Tell me about curing'.</p>", true);
        }
    }

    // **NEW** Handles navigation commands
    function handleNavigation(match) {
        let section = match[1].toLowerCase().trim();
        if (section === 'brickwork') section = 'masonry'; // Alias
        
        const accordionMap = {
            substructure: 'substructure-accordion',
            superstructure: 'superstructure-accordion',
            masonry: 'masonry-accordion',
            plumbing: 'plumbing-accordion',
            electrical: 'electrical-accordion',
            rates: 'rates-accordion'
        };
        const sectionId = accordionMap[section];

        if (sectionId) {
            // This function is defined in index.html and attached to window
            if (window.switchView) {
                window.switchView('pro-estimator-view', sectionId);
                addBotMessage(`Navigating to the ${section} section.`);
            } else {
                addBotMessage("Sorry, I'm having trouble navigating right now.");
            }
        } else {
            addBotMessage(`I can't find a section called '${section}'.`);
        }
    }

    // **NEW** Handles clearing form sections
    function handleClearSection(match) {
        const section = match[1].toLowerCase().trim();
        const containerMap = {
            footings: 'footings-container',
            columns: 'columns-container',
            beams: 'beams-container',
            slabs: 'slabs-container',
            walls: 'walls-container',
            plumbing: 'plumbing-container',
            electrical: 'electrical-container'
        };
        const containerId = containerMap[section];
        
        if (containerId) {
            const container = document.getElementById(containerId);
            if(container && container.children.length > 0) {
                container.innerHTML = '';
                addBotMessage(`Done. I've cleared all ${section} from the form.`);
            } else {
                addBotMessage(`The ${section} section is already empty.`);
            }
        } else {
             addBotMessage(`I'm not sure how to clear '${section}'.`);
        }
    }
    
    // **NEW** Handles counting items in the form
    function handleCountItems(match) {
        let section = match[1].toLowerCase().trim().replace(' items', '');
        const containerMap = {
            footings: 'footings-container',
            columns: 'columns-container',
            beams: 'beams-container',
            slabs: 'slabs-container',
            walls: 'walls-container',
            plumbing: 'plumbing-container',
            electrical: 'electrical-container'
        };
        const containerId = containerMap[section];
        if (containerId) {
            const container = document.getElementById(containerId);
            const count = container ? container.getElementsByClassName('input-group').length : 0;
            addBotMessage(`You have added <b>${count}</b> ${section === 'plumbing' || section === 'electrical' ? section + ' items' : section}.`, true);
        } else {
            addBotMessage(`I can't count '${section}'.`);
        }
    }

    // **NEW** Handles simple calculations and conversions
    function handleCalculation(match) {
        let query = match[1].toLowerCase().trim();
        let result = null;
        
        // Conversion: ft to m
        let convMatch = query.match(/(\d*\.?\d+)\s*ft\s*(to|in)\s*m/);
        if (convMatch) {
            const feet = parseFloat(convMatch[1]);
            result = `${feet} ft is equal to <b>${(feet * 0.3048).toFixed(2)} meters</b>.`;
        }
        
        // Conversion: m to ft
        convMatch = query.match(/(\d*\.?\d+)\s*m\s*(to|in)\s*ft/);
        if (convMatch) {
            const meters = parseFloat(convMatch[1]);
            result = `${meters} m is equal to <b>${(meters / 0.3048).toFixed(2)} feet</b>.`;
        }
        
        // Area
        let areaMatch = query.match(/area of\s*(\d*\.?\d+)\s*(?:by|x)\s*(\d*\.?\d+)/);
        if (areaMatch) {
            const l = parseFloat(areaMatch[1]);
            const w = parseFloat(areaMatch[2]);
            result = `The area is <b>${(l * w).toFixed(2)}</b> square units.`;
        }

        // Volume
        let volMatch = query.match(/volume of\s*(\d*\.?\d+)\s*(?:by|x)\s*(\d*\.?\d+)\s*(?:by|x)\s*(\d*\.?\d+)/);
        if (volMatch) {
            const l = parseFloat(volMatch[1]);
            const w = parseFloat(volMatch[2]);
            const h = parseFloat(volMatch[3]);
            result = `The volume is <b>${(l * w * h).toFixed(2)}</b> cubic units.`;
        }
        
        if (result) {
            addBotMessage(result, true);
        } else {
            // Pass to info request if no calculation pattern matched
            handleInfoRequest([null, null, query]);
        }
    }

    // **MODIFIED** Help command now includes the new features
    function handleHelp() {
        addBotMessage(`I'm a powerful assistant! You can ask me to:
        <ul class="list-disc list-inside mt-2 text-sm">
            <li><b>Add items:</b> "add a 5x4x0.3 footing"</li>
            <li><b>Add custom items:</b> "add a shower tap for 8000"</li>
            <li><b>Update rates:</b> "set steel rate to 90"</li>
            <li><b>Navigate:</b> "show me the plumbing section"</li>
            <li><b>Clear sections:</b> "clear all columns"</li>
            <li><b>Count items:</b> "how many walls have I added?"</li>
            <li><b>Ask questions:</b> "what is rcc?" or "explain curing"</li>
            <li><b>Do calculations:</b> "calculate area of 10x12" or "convert 100ft to m"</li>
            <li><b>Clear history:</b> "clear chat"</li>
        </ul>`, true);
    }
    
    // **MODIFIED** Smarter fallback for unknown commands
    function handleUnknownCommand(command) {
        if (command.match(/add|insert/i)) {
             addBotMessage("I can add structural items (e.g., 'add a 5x4x0.3 footing') or custom fixtures (e.g., 'add a custom light for 500'). Please check the format.");
        } else if (command.match(/rate|cost|set/i)) {
             addBotMessage("To set a rate, please use the format: 'set cement rate to 500'.");
        } else if (command.match(/clear|delete|remove/i)) {
             addBotMessage("You can clear a whole section, like 'clear all footings' or 'clear plumbing'.");
        } else if (command.match(/how|what|why|explain/i)) {
             addBotMessage("I can answer many construction questions. Try asking 'what is concrete curing?' or 'tell me about the M20 mix'.");
        } else {
             addBotMessage("Sorry, I didn't understand that. Type 'help' to see the commands I know.");
        }
    }

    // --- CHATBOT UI & APP HELPER FUNCTIONS ---

    function addUserMessage(message) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'chat-message user';
        msgDiv.textContent = message;
        chatBody.appendChild(msgDiv);
        scrollToBottom();
    }

    function addBotMessage(message, isHtml = false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'chat-message bot';
        if (isHtml) {
            msgDiv.innerHTML = message;
        } else {
            msgDiv.textContent = message;
        }
        chatBody.appendChild(msgDiv);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function getBrandNamesFor(itemType) {
        // This function relies on the 'window.companyRates' variable defined in index.html
        if (window.companyRates && window.companyRates[itemType]) {
            const brands = Object.keys(window.companyRates[itemType]).map(b => b.charAt(0).toUpperCase() + b.slice(1));
            return `Available brands for ${itemType.replace('_',' ')} are: <b>${brands.join(', ')}</b>.`;
        }
        return `I couldn't retrieve brand information for ${itemType}.`;
    }
});
