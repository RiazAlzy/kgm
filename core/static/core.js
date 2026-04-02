document.addEventListener('alpine:init', () => {
    Alpine.data('uploadState', () => ({
        init() {
            const input = document.getElementById('fileInput');
            const dropzone = document.getElementById('dropzone');
            
            input.addEventListener('change', (e) => {
                if(e.target.files.length > 0) {
                    this.uploadFile(e.target.files[0]);
                }
            });

            // Drag and drop styling
            ['dragenter', 'dragover'].forEach(eventName => {
                dropzone.addEventListener(eventName, (e) => {
                    e.preventDefault(); dropzone.classList.add('border-indigo-500', 'bg-indigo-50');
                });
            });['dragleave', 'drop'].forEach(eventName => {
                dropzone.addEventListener(eventName, (e) => {
                    e.preventDefault(); dropzone.classList.remove('border-indigo-500', 'bg-indigo-50');
                });
            });

            dropzone.addEventListener('drop', (e) => {
                const files = e.dataTransfer.files;
                if(files.length > 0) this.uploadFile(files[0]);
            });
        },

        async uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);

            // Hide CSRF token handling complexity for brevity
            const csrfToken = document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];

            try {
                const response = await fetch('/upload/', {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-CSRFToken': csrfToken || '' }
                });

                const data = await response.json();
                
                if (response.ok || response.status === 409) {
                    // Activate HTMX UI polling
                    const container = document.getElementById('progress-container');
                    container.classList.remove('hidden');
                    
                    // Manually trigger htmx to load the initial progress state via the returned file hash
                    container.innerHTML = `<div hx-get="/progress/${data.hash}/" hx-trigger="load"></div>`;
                    htmx.process(container);
                } else {
                    alert(data.error || 'Upload failed');
                }
            } catch (err) {
                console.error("Upload error:", err);
            }
        }
    }));
});