// Function to scroll to the bottom of the chat messages
function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Simulate AI typing effect
async function simulateTyping(messageElement, text) {
    let i = 0;
    messageElement.innerHTML = ''; // Clear initial text
    
    while (i < text.length) {
        messageElement.innerHTML += text.charAt(i);
        i++;
        scrollToBottom();
        await new Promise(resolve => setTimeout(resolve, 50)); // Typing speed
    }
}

// Event listener for message form submission
document.addEventListener('DOMContentLoaded', () => {
    scrollToBottom(); // Scroll to bottom on page load

    const messageForm = document.getElementById('message-form');
    if (messageForm) {
        messageForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const userInputField = messageForm.querySelector('input[name="user_input"]');
            const conversationId = messageForm.querySelector('input[name="conversation_id"]').value;

            const userMessageContent = userInputField.value.trim();
            if (!userMessageContent) return; // Don't send empty messages
            
            const chatMessagesContainer = document.getElementById('chat-messages');
            
            // 1. Add user message to UI immediately
            const userMessageDiv = document.createElement('div');
            userMessageDiv.classList.add('message', 'user');
            userMessageDiv.innerHTML = `<p>${userMessageContent}</p>`;
            chatMessagesContainer.appendChild(userMessageDiv);
            scrollToBottom();
            
            userInputField.value = ''; // Clear input field

            // 2. Show typing indicator for AI response
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) {
                typingIndicator.style.display = 'block';
                scrollToBottom();
            }

            // 3. Send message to backend via AJAX
            const formData = new FormData();
            formData.append('user_input', userMessageContent);
            formData.append('conversation_id', conversationId);

            try {
                const response = await fetch(messageForm.action, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    const aiResponseContent = data.ai_response;

                    // Hide typing indicator
                    if (typingIndicator) {
                        typingIndicator.style.display = 'none';
                    }

                    // 4. Add AI response to UI with typing simulation
                    const aiMessageDiv = document.createElement('div');
                    aiMessageDiv.classList.add('message', 'ai');
                    const aiMessageParagraph = document.createElement('p');
                    aiMessageDiv.appendChild(aiMessageParagraph);
                    chatMessagesContainer.appendChild(aiMessageDiv);
                    scrollToBottom();

                    await simulateTyping(aiMessageParagraph, aiResponseContent);

                } else {
                    console.error('Failed to send message:', response.status, response.statusText);
                    // Display an error message if the API call fails
                    const errorMessageDiv = document.createElement('div');
                    errorMessageDiv.classList.add('message', 'ai'); // Display error as an AI message
                    errorMessageDiv.innerHTML = '<p>Error: Could not get a response from AI. Please try again. AI MODEL is reinitializing from being scaled down.</p>';
                    chatMessagesContainer.appendChild(errorMessageDiv);
                    scrollToBottom();
                    if (typingIndicator) {
                        typingIndicator.style.display = 'none';
                    }
                }
            } catch (error) {
                console.error('Network error or unexpected response:', error);
                const errorMessageDiv = document.createElement('div');
                errorMessageDiv.classList.add('message', 'ai');
                errorMessageDiv.innerHTML = '<p>Error: Network issue. Please check your connection.</p>';
                chatMessagesContainer.appendChild(errorMessageDiv);
                scrollToBottom();
                if (typingIndicator) {
                    typingIndicator.style.display = 'none';
                }
            }
        });
    }

    // Rename Modal Logic
    const renameModal = document.getElementById('renameModal');
    const closeButton = document.querySelector('.close-button');
    const renameForm = document.getElementById('renameForm');
    const newTitleInput = document.getElementById('newTitleInput');
    const conversationIdInput = document.getElementById('renameConversationId');

    document.querySelectorAll('.edit-chat-btn').forEach(button => {
        button.addEventListener('click', function() {
            const convId = this.dataset.conversationId;
            const currentTitle = this.dataset.currentTitle;
            
            conversationIdInput.value = convId;
            newTitleInput.value = currentTitle;
            renameForm.action = `/chat/${convId}/rename`;
            renameModal.style.display = 'flex'; // Use flex to center with align-items/justify-content
        });
    });

    if (closeButton) {
        closeButton.addEventListener('click', () => {
            renameModal.style.display = 'none';
        });
    }

    window.addEventListener('click', (event) => {
        if (event.target == renameModal) {
            renameModal.style.display = 'none';
        }
    });

    // Handle rename form submission with fetch
    if (renameForm) {
        renameForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const convId = conversationIdInput.value;
            const newTitle = newTitleInput.value.trim();

            if (!newTitle) {
                showSnackbar('New title cannot be empty.', 'error');
                return;
            }

            try {
                const response = await fetch(`/chat/${convId}/rename`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `conversation_id=${encodeURIComponent(convId)}&new_title=${encodeURIComponent(newTitle)}`
                });

                const data = await response.json();

                if (response.ok) {
                    showSnackbar(data.message, data.category);
                    // Update the conversation title in the sidebar immediately
                    const conversationItem = document.querySelector(`.conversation-item[data-conversation-id="${convId}"]`);
                    if (conversationItem) {
                        conversationItem.querySelector('.conversation-title').textContent = data.new_title;
                        conversationItem.dataset.currentTitle = data.new_title; // Update dataset for future edits
                    }
                    // If currently viewing this conversation, update its header
                    const chatHeader = document.querySelector('.chat-header');
                    if (chatHeader && chatHeader.dataset.conversationId === convId) {
                        chatHeader.querySelector('h2').textContent = data.new_title;
                    }
                    renameModal.style.display = 'none';
                } else {
                    showSnackbar(data.message, data.category || 'error');
                }
            } catch (error) {
                console.error('Error renaming conversation:', error);
                showSnackbar('Network error. Could not rename conversation.', 'error');
            }
        });
    }

    // Handle delete conversation with fetch
    document.querySelectorAll('.delete-chat-btn').forEach(button => {
        button.addEventListener('click', async function(event) {
            event.preventDefault();
            if (!confirm('Are you sure you want to delete this conversation?')) {
                return;
            }

            const form = this.closest('form');
            const conversationId = form.action.split('/').slice(-2, -1)[0]; // Extract ID from action URL

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `conversation_id=${encodeURIComponent(conversationId)}`
                });

                const data = await response.json();

                if (response.ok) {
                    showSnackbar(data.message, data.category);
                    form.closest('.conversation-item').remove(); // Remove item from sidebar
                    // Redirect to chat or update UI if current conversation was deleted
                    if (window.location.pathname.includes(`/chat/${conversationId}`)) {
                        window.location.href = '/chat'; // Go back to general chat page
                    }
                } else {
                    showSnackbar(data.message, data.category || 'error');
                }
            } catch (error) {
                console.error('Error deleting conversation:', error);
                showSnackbar('Network error. Could not delete conversation.', 'error');
            }
        });
    });

    // Search functionality
    const searchBtn = document.querySelector('.search-btn');
    const searchContainer = document.getElementById('searchContainer');
    const searchInput = document.getElementById('searchInput');
    const searchCloseBtn = document.querySelector('.search-close-btn');
    const conversationItems = document.querySelectorAll('.conversation-item');

    searchBtn.addEventListener('click', () => {
        searchContainer.classList.add('active');
        searchInput.focus();
    });

    searchCloseBtn.addEventListener('click', () => {
        searchContainer.classList.remove('active');
        searchInput.value = '';
        conversationItems.forEach(item => {
            item.style.display = ''; // Show all conversations
        });
    });

    searchInput.addEventListener('keyup', () => {
        const searchTerm = searchInput.value.toLowerCase();
        conversationItems.forEach(item => {
            const title = item.dataset.title.toLowerCase();
            if (title.includes(searchTerm)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    });
});

// Function to display a snackbar message
function showSnackbar(message, category = 'info') {
    const snackbar = document.getElementById('snackbar');
    if (snackbar) {
        snackbar.textContent = message;
        snackbar.className = 'snackbar show'; // Reset classes and add 'show'
        
        // Add category class for styling (success, error)
        if (category === 'success') {
            snackbar.classList.add('success');
        } else if (category === 'error') {
            snackbar.classList.add('error');
        } else {
            // Default style if no specific category
            snackbar.classList.add('info'); // You might want to define '.snackbar.info' in CSS
        }

        setTimeout(function(){
            snackbar.className = snackbar.className.replace("show", "");
            snackbar.classList.remove('success', 'error', 'info'); // Clean up classes
        }, 3000); // Hide after 3 seconds
    }
} 