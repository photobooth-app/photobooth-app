<?php
// Configuration options
$APIKEY = "changeme!";                 // Set APIkey to a random value, at least 8 characters. The same APIkey must be set in the photo booth app to connect both systems
$WORK_DIRECTORY = __DIR__ . "/uploads";     // __DIR__ is the directory of the current PHP file
$ALLOWED_UPLOAD_MAX_SIZE = 25 * 2 ** 20;    // 25MB maximum file size for upload
$TIMEOUT_DOWNLOAD = 15;                     // If the photo booth app upload is not completed within this timeout, it is considered an error and an error is displayed instead of the image

// Internal constants - do not change anything below!
$VERSION = 2;
$DB_FILENAME = "jobs.sqlite3";
$ALLOWED_UPLOAD_TYPES = [
    'image/png' => 'png',
    'image/jpeg' => 'jpg',
    'image/gif' => 'gif',
    'video/mp4' => 'mp4',
];