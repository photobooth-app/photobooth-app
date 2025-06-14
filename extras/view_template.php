<!DOCTYPE html>
<html lang="<?php echo $current_language; ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo translate('download_or_share'); ?></title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container" id="main-container">
        <h1><?php echo translate('download_or_share'); ?></h1>
        <div class="media-container" id="media-container">
            <?php if ($isImage): ?>
                <div class="media-placeholder"><div class="loader"></div></div>
                <img src="data:<?php echo $mimetype; ?>;base64,<?php echo $base64EncodedData; ?>" alt="Image" id="media-content" style="opacity: 0;">
            <?php elseif ($isVideo): ?>
                <div class="media-placeholder"><div class="loader"></div></div>
                <video controls loop autoplay muted id="media-content" style="opacity: 0;">
                    <source src="data:<?php echo $mimetype; ?>;base64,<?php echo $base64EncodedData; ?>" type="<?php echo $mimetype; ?>">
                    Your browser does not support the video tag.
                </video>
            <?php endif; ?>
        </div>
        <div class="button-container">
            <a href="data:<?php echo $mimetype; ?>;base64,<?php echo $base64EncodedData; ?>" download="<?php echo $results["filename"]; ?>" class="button download-btn">
                <span class="icon">⬇️</span> <?php echo translate('download_button'); ?>
            </a>
            <?php if (isSecure()): ?>
                <button onclick="shareContent()" class="button share-btn">
                    <span class="icon">📤</span> <?php echo translate('share_button'); ?>
                </button>
            <?php endif; ?>
        </div>
    </div>
    <div id="toast" class="toast"></div>
    
    <!-- Hidden values for JavaScript -->
    <input type="hidden" id="copy-success-message" value="<?php echo translate('copy_clipboard_success'); ?>">
    <input type="hidden" id="copy-error-message" value="<?php echo translate('copy_clipboard_error'); ?>">
    <input type="hidden" id="success-share-message" value="<?php echo translate('successful_share'); ?>">
    <input type="hidden" id="error-share-message" value="<?php echo translate('error_sharing'); ?>">
    <input type="hidden" id="share-title" value="<?php echo translate('share_title'); ?>">
    <input type="hidden" id="share-text" value="<?php echo translate('share_text'); ?>">
    <input type="hidden" id="filename" value="<?php echo $results["filename"]; ?>">
    <input type="hidden" id="mimetype" value="<?php echo $mimetype; ?>">
    
    <script src="scripts.js"></script>
</body>
</html>