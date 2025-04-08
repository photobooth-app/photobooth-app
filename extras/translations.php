<?php
// Translation variables
$translations = [
    // API and file handling errors
    'error_no_file_uploaded' => 'No file was uploaded',
    'error_processing_file' => 'Error processing the uploaded file!',
    'error_api_key' => 'APIKEY incorrect! Check APIKEY in photoservice.php and in the Photo Booth configuration.',
    'error_empty_file' => 'The file is empty.',
    'error_large_file' => 'The file is too large',
    'error_not_allowed' => 'File not allowed.',
    'error_cannot_find_file' => 'Cannot find uploaded file',
    'error_upload_failed' => 'Photo booth had problems uploading the file, check the photo booth log for errors',
    'error_runtime' => 'Runtime error: ',
    'endpoint_not_exist' => 'Endpoint does not exist!',
    
    // UI elements
    'download_or_share' => 'Your Photo Booth Capture',
    'download_button' => 'Download',
    'share_button' => 'Share',
    'fullscreen_button' => 'Fullscreen',
    'exit_fullscreen_button' => 'Exit Fullscreen',
    
    // Share functionality
    'share_title' => 'Photo Booth File',
    'share_text' => 'Check out this file I captured!',
    'successful_share' => 'Successfully shared',
    'error_sharing' => 'Error while sharing',
    'copy_clipboard_success' => 'Link copied to clipboard! You can share it now.',
    'copy_clipboard_error' => 'Copy failed. Please copy the link manually.',
    
    // System info
    'info_version' => 'Version',
    'info_name' => 'Photo Booth App File Upload Extension',
    
    // Error page
    'error_title' => 'An error occurred',
    'error_message' => 'The request could not be processed. The image may not be available yet or the connection to the photo booth has been interrupted.',
    'reload_button' => 'Reload',
    
    // Timeout errors
    'error_timeout' => 'Photo booth did not upload the requested image within the time limit :( No internet? Service disabled?',
    
    // Technical error messages
    'error_mimetype' => 'File mimetype could not be recognized. Aborting.',
    'error_empty_apikey' => '$APIKEY is empty or too short in photoservice.php script! Configure $APIKEY in photoservice.php and photo-booth-app-config to connect systems.',
    'error_default_apikey' => '$APIKEY is default in photoservice.php script! Change $APIKEY in photoservice.php and photo-booth-app-config to connect systems.',
    'error_job_processing' => 'Error processing the job',
    'error_move_file' => 'Cannot move file.',
    'error_tmp_name_empty' => 'tmp_name is empty, please check PHP settings (upload size, ...)!',
    
    // Success messages
    'upload_success' => 'File successfully saved and ready for download',
];

// Language settings
$supported_languages = ['de', 'en', 'es', 'fr']; // supported languages
$default_language = 'en'; // Default language set to English
$current_language = $default_language;

// Detect user language (via GET parameter or browser settings)
if (isset($_GET['lang']) && in_array($_GET['lang'], $supported_languages)) {
    $current_language = $_GET['lang'];
    // Optional: Save language in session or cookie
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
    $_SESSION['language'] = $current_language;
} elseif (isset($_SESSION['language']) && in_array($_SESSION['language'], $supported_languages)) {
    $current_language = $_SESSION['language'];
} elseif (isset($_SERVER['HTTP_ACCEPT_LANGUAGE'])) {
    // Read browser language
    $browser_languages = explode(',', $_SERVER['HTTP_ACCEPT_LANGUAGE']);
    foreach ($browser_languages as $browser_language) {
        $lang_code = substr(trim($browser_language), 0, 2);
        if (in_array($lang_code, $supported_languages)) {
            $current_language = $lang_code;
            break;
        }
    }
}

// Load translations from JSON file if available
$language_file = "langs/{$current_language}.json";
if (file_exists($language_file)) {
    $json_translations = json_decode(file_get_contents($language_file), true);
    if ($json_translations && is_array($json_translations)) {
        // Override default translations with values from the JSON file
        $translations = array_merge($translations, $json_translations);
    }
}

/**
 * Helper function to translate a text
 * 
 * @param string $key The translation key
 * @param array $replacements Optional: Replacements for placeholders in {name} format
 * @return string The translated string
 */
function translate($key, $replacements = []) {
    global $translations, $default_language;
    
    // If the key doesn't exist, return the key itself
    if (!isset($translations[$key])) {
        return $key;
    }
    
    $text = $translations[$key];
    
    // Apply replacements
    foreach ($replacements as $placeholder => $value) {
        $text = str_replace("{{$placeholder}}", $value, $text);
    }
    
    return $text;
}