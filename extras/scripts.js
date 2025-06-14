document.addEventListener('DOMContentLoaded', function() {
    const mediaContent = document.getElementById('media-content');
    const mediaPlaceholder = document.querySelector('.media-placeholder');
    
    // Function to handle media load
    function handleMediaLoaded() {
        if (mediaPlaceholder) {
            // Fade out the placeholder
            mediaPlaceholder.style.opacity = '0';
            
            // Fade in the media content
            setTimeout(() => {
                mediaContent.style.opacity = '1';
                
                // Remove placeholder after transition
                setTimeout(() => {
                    if (mediaPlaceholder.parentNode) {
                        mediaPlaceholder.parentNode.removeChild(mediaPlaceholder);
                    }
                }, 500);
            }, 300);
        } else {
            // If no placeholder, just show the media
            mediaContent.style.opacity = '1';
        }
    }
    
    // Handle different media types
    if (mediaContent) {
        if (mediaContent.tagName === 'IMG') {
            // For images
            if (mediaContent.complete) {
                // Image is already loaded (from cache)
                handleMediaLoaded();
            } else {
                // Wait for image to load
                mediaContent.onload = handleMediaLoaded;
            }
            
            // Fallback in case the image fails to trigger onload
            setTimeout(() => {
                if (mediaContent.style.opacity === '0') {
                    handleMediaLoaded();
                }
            }, 2000);
        } else if (mediaContent.tagName === 'VIDEO') {
            // For videos
            mediaContent.setAttribute('preload', 'auto');
            mediaContent.setAttribute('playsinline', '');
            
            // Video can be played
            mediaContent.oncanplay = handleMediaLoaded;
            
            // Fallback for videos
            setTimeout(() => {
                if (mediaContent.style.opacity === '0') {
                    handleMediaLoaded();
                }
            }, 2000);
        }
    }
});

function showToast(message) {
    try {
        const toast = document.getElementById('toast');
        if (!toast) return;
        
        // Clear previous timers if toast is already shown
        if (toast.timeoutId) {
            clearTimeout(toast.timeoutId);
        }
        
        toast.textContent = message;
        toast.classList.add('visible');
        
        // Save timer to cancel it if needed
        toast.timeoutId = setTimeout(() => {
            toast.classList.remove('visible');
        }, 3000);
    } catch (e) {
        console.error('Error showing toast:', e);
    }
}

async function shareContent() {
    // Check if Web Share API is available
    if (!navigator.share) {
        try {
            // Fallback for older browsers
            const urlField = document.createElement('textarea');
            urlField.value = window.location.href;
            urlField.style.position = 'fixed';
            urlField.style.opacity = '0';
            document.body.appendChild(urlField);
            urlField.focus();
            urlField.select();
            
            const successful = document.execCommand('copy');
            document.body.removeChild(urlField);
            
            if (successful) {
                showToast(document.getElementById('copy-success-message').value);
            } else {
                showToast(document.getElementById('copy-error-message').value);
            }
        } catch (err) {
            console.error('Error copying to clipboard:', err);
            showToast(document.getElementById('copy-error-message').value);
        }
        return;
    }
    
    try {
        // Disable share button to prevent multiple clicks
        const shareButtons = document.querySelectorAll('.share-btn');
        shareButtons.forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.7';
        });
        
        // Use Web Share API with file
        const mediaContentSrc = document.getElementById('media-content').src;
        const response = await fetch(mediaContentSrc);
        const blob = await response.blob();
        const file = new File([blob], document.getElementById('filename').value, {
            type: document.getElementById('mimetype').value
        });
        
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            // Share with file
            await navigator.share({
                files: [file],
                title: document.getElementById('share-title').value,
                text: document.getElementById('share-text').value
            });
            showToast(document.getElementById('success-share-message').value);
        } else {
            // Fallback to sharing without file (link only)
            await navigator.share({
                title: document.getElementById('share-title').value,
                text: document.getElementById('share-text').value,
                url: window.location.href
            });
            showToast(document.getElementById('success-share-message').value);
        }
    } catch (error) {
        console.error('Error sharing:', error);
        showToast(document.getElementById('error-share-message').value);
    } finally {
        // Re-enable share button
        setTimeout(() => {
            const shareButtons = document.querySelectorAll('.share-btn');
            shareButtons.forEach(btn => {
                btn.disabled = false;
                btn.style.opacity = '1';
            });
        }, 1000);
    }
}