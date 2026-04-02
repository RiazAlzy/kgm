document.addEventListener('alpine:init', () => {
    Alpine.data('chatApp', () => ({
        ws: null,
        messages:[],
        inputMessage: '',
        isProcessing: false,
        currentStatus: 'Thinking...',
        
        init() {
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            this.ws = new WebSocket(protocol + window.location.host + '/ws/chat/stream/');
            
            this.ws.onopen = () => {
                console.log("Connected to LangGraph Agent");
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'status') {
                    // Update Agentic UI Status
                    this.currentStatus = data.message;
                } 
                else if (data.type === 'token') {
                    // Check if last message is from AI. If not, create it.
                    let lastMsg = this.messages[this.messages.length - 1];
                    if (!lastMsg || lastMsg.role !== 'ai') {
                        this.messages.push({ role: 'ai', content: '' });
                        lastMsg = this.messages[this.messages.length - 1];
                    }
                    // Append stream chunk
                    lastMsg.content += data.content;
                    this.scrollToBottom();
                } 
                else if (data.type === 'end') {
                    // Workflow finished
                    this.isProcessing = false;
                    this.currentStatus = '';
                    this.scrollToBottom();
                }
            };

            this.ws.onclose = () => {
                console.warn("WebSocket disconnected. Reconnection logic could be added here.");
            };
        },

        sendMessage() {
            const msg = this.inputMessage.trim();
            if (!msg || this.isProcessing) return;

            // Immediately push user msg to UI
            this.messages.push({ role: 'user', content: msg });
            
            // Set UI to loading state
            this.isProcessing = true;
            this.currentStatus = 'Analyzing query...';
            this.inputMessage = '';
            
            this.scrollToBottom();

            // Fire off to backend LangGraph consumer
            this.ws.send(JSON.stringify({
                message: msg
            }));
        },

        scrollToBottom() {
            // Using setTimeout to allow Alpine DOM updates to process first
            setTimeout(() => {
                const anchor = document.getElementById('scroll-anchor');
                if (anchor) {
                    anchor.scrollIntoView({ behavior: 'smooth' });
                }
            }, 50);
        }
    }));
});