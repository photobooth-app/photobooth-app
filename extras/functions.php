<?php
/**
 * Checks if the connection is secure
 * 
 * @return bool True if the connection is secure, false otherwise
 */
function isSecure() {
    if (
        (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || $_SERVER['SERVER_PORT'] == 443
    ) {
        return true;
    }

    // Check for HTTPS in "X-Forwarded-Proto" header for reverse proxies
    if (!empty($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {
        return true;
    }

    return false;
}

/**
 * Checks if the API key is properly set
 * 
 * @throws RuntimeException if API key is not set or is default
 */
function api_key_set() {
    global $APIKEY;

    // die if APIKEY is not set
    if (strlen($APIKEY) < 8) {
        throw new RuntimeException(translate('error_empty_apikey'));
    }
    if (stripos($APIKEY, "changedefault!") !== false) {
        throw new RuntimeException(translate('error_default_apikey'));
    }
}