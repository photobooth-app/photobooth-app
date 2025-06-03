<?php
// Set HTTP response code
http_response_code(500);
header('Content-Type: text/html; charset=UTF-8');
?>
<!DOCTYPE html>
<html lang="<?php echo $current_language; ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo translate('error_title'); ?> - Photo Booth</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="error-container">
        <div class="error-icon">⚠️</div>
        <h1><?php echo translate('error_title'); ?></h1>
        <div class="error-message">
            <p><?php echo translate('error_message'); ?></p>
        </div>
        <a href="javascript:location.reload()" class="button"><?php echo translate('reload_button'); ?></a>
    </div>
</body>
</html>