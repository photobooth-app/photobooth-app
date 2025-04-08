<?php
/*
 * IMPORTANT:
 * 1. The API key ($APIKEY) must be changed to a random value.
 *    This key is used to connect the photo booth app with the server, and it must match the key set in the photo booth app configuration.
 *    Leaving the API key as the default value poses a security risk, and the script will not function properly until it is changed.
 *
 * 2. The share button will only be visible when accessing the page via a secure connection (HTTPS).
 *    If you do not use HTTPS, the share button will not be displayed.
 */

// Documentation at https://photobooth-app.org/setup/configuration/qrshareservice/

// Include necessary files
require_once('config.php');
require_once('translations.php');
require_once('functions.php');

// PHP configuration
ini_set('display_errors', 0);
ini_set('display_startup_errors', 0);
ini_set("log_errors", 1);
ini_set("error_log", "php-error.log");
error_reporting(E_ALL);

// Prevents nginx from additional buffering, as the long-running job would fail otherwise
// nginx has additional buffer to php, php buffer is emptied but nginx isn't
header('X-Accel-Buffering: no'); // https://stackoverflow.com/a/25017347
ob_implicit_flush(true);   // always flush the buffer after each write, without requiring an additional call to flush

try {
    // Set up database connection
    $db = new SQLite3($DB_FILENAME);
    $db->busyTimeout(200);
    // WAL mode has better control over concurrency.
    // Source: https://www.sqlite.org/wal.html
    #$db->exec('PRAGMA journal_mode = wal;');

    // Setup checks
    # Create working directory
    if (!is_dir($WORK_DIRECTORY)) {
        mkdir($WORK_DIRECTORY);
    }

    # Create database
    $db->exec("CREATE TABLE IF NOT EXISTS upload_requests(
        file_identifier TEXT PRIMARY KEY,
        filename TEXT,
        last_modified TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'pending'
    )");

    if (($_POST["action"] ?? null) == "upload" && ($_POST["id"] ?? null)) {
        // Action: Upload a file identified by id.
        // Once the file is uploaded, mark it as "uploaded" in the database
        // Ongoing download action would check for the "uploaded" flag and then return the file

        api_key_set();

        $file_identifier = $_POST["id"];

        // Plausibility check for apikey
        if ($_POST["apikey"] !== $APIKEY) {
            $db->exec("UPDATE upload_requests SET status = 'upload_failed' WHERE file_identifier = '" . $file_identifier . "'");
            throw new RuntimeException(translate('error_api_key'));
        }

        // File upload plausibility checks
        if (!isset($_FILES["upload_file"])) {
            # Set status to error so ongoing download can stop waiting
            $db->exec("UPDATE upload_requests SET status = 'upload_failed' WHERE file_identifier = '" . $file_identifier . "'");
            throw new RuntimeException(translate('error_no_file_uploaded') . " ($file_identifier)");
        }
        if ($_FILES['upload_file']['error'] != UPLOAD_ERR_OK) {
            throw new RuntimeException(translate('error_processing_file') . " Error code=" . $_FILES['upload_file']['error']);
        }

        $filepath = $_FILES['upload_file']['tmp_name'];

        if (empty($filepath)) {
            throw new RuntimeException(translate('error_tmp_name_empty'));
        }
        try {
            $mimetype = mime_content_type($filepath);
        } catch (ValueError $e) {
            throw new RuntimeException(translate('error_mimetype'));
        }

        if (filesize($filepath) === 0) {
            throw new RuntimeException(translate('error_empty_file'));
        }
        if (filesize($filepath) > $ALLOWED_UPLOAD_MAX_SIZE) {
            throw new RuntimeException(translate('error_large_file'));
        }
        if (!in_array($mimetype, array_keys($ALLOWED_UPLOAD_TYPES))) {
            throw new RuntimeException(translate('error_not_allowed'));
        }

        // Filename for storing the uploaded file in the working directory
        $filename = basename($filepath);
        $extension = $ALLOWED_UPLOAD_TYPES[$mimetype];

        // Query entry for ID to double-check that currently uploaded file was actually requested and job was assigned
        $results = $db->querySingle("SELECT * FROM upload_requests WHERE file_identifier='" . $file_identifier . "' AND status='job_assigned'", true);

        if (!empty($results)) {
            $db->exec("UPDATE upload_requests SET status = 'uploading' WHERE file_identifier = '" . $file_identifier . "'");

            // Save uploaded file
            $newFilepath = $WORK_DIRECTORY . "/" . $filename . "." . $extension;
            if (!copy($filepath, $newFilepath)) { // Copy file, returns false if failed
                throw new RuntimeException(translate('error_move_file'));
            }
            unlink($filepath); // Delete temporary file

            // Mark as uploaded
            $db->exec("UPDATE upload_requests SET filename = '$filename.$extension', status = 'uploaded' WHERE file_identifier = '" . $file_identifier . "'");

            echo translate('upload_success');
        } else {
            throw new RuntimeException(translate('error_job_processing'));
        }
    } elseif (($_POST["action"] ?? null) == "upload_queue") {
        // Long-running task to wait for dl request
        api_key_set();

        // Plausibility check for apikey
        if ($_POST["apikey"] !== $APIKEY) {
            throw new RuntimeException(translate('error_api_key'));
        }

        $LOOP_TIME = 0.5; # Loop every x seconds
        $LOOP_TIME_MAX = 240; # after x seconds script will end and client will likely create a new connection at the latest

        $time_processed = 0;
        do {
            $results = $db->querySingle("SELECT * FROM upload_requests WHERE status = 'pending'", true);

            if (!empty($results)) {
                // Non-empty results should be uploaded by photo booth app
                $db->exec("UPDATE upload_requests SET status = 'job_assigned' WHERE file_identifier = '" . $results['file_identifier'] . "'");
                echo json_encode($results);
            } else {
                # nothing to do; send ping message to ensure connection health and regular input for shareservice.py
                echo json_encode(['ping' => time()]);
            }
            # Add line break so Python backend can read it
            echo "\n";

            # Flush content to output
            if (ob_get_level() > 0) ob_flush(); # clear internal buffer (needed for PHP built-in webserver during testing)
            flush();    # Flush output buffer

            # Wait before next iteration
            usleep($LOOP_TIME * 1000 * 1000);
            $time_processed += $LOOP_TIME;
        } while ($time_processed <= $LOOP_TIME_MAX);
    } elseif (($_GET["action"] ?? null) == "download" && ($_GET["id"] ?? null)) {
        api_key_set();
        $file_identifier = $_GET["id"];

        $db->exec("REPLACE INTO upload_requests (
                file_identifier, 
                status
                ) VALUES (
                '$file_identifier',
                'pending')");

        $time_waited = 0;
        do {
            $results = $db->querySingle("SELECT * FROM upload_requests WHERE file_identifier= '$file_identifier'", true);

            if (!empty($results) && $results["status"] == "uploaded") {
                $file = $WORK_DIRECTORY . "/" . $results["filename"];
                if (file_exists($file)) {
                    $mimetype = mime_content_type($file);
                    $fileData = file_get_contents($file);
                    $base64EncodedData = base64_encode($fileData);
                    $isImage = in_array($mimetype, ['image/png', 'image/jpeg', 'image/gif']);
                    $isVideo = ($mimetype == 'video/mp4');

                    include('view_template.php'); // Include the HTML/CSS template
                    exit;
                } else {
                    throw new RuntimeException(translate('error_cannot_find_file'));
                }
            } elseif (!empty($results) && $results["status"] == "upload_failed") {
                throw new RuntimeException(translate('error_upload_failed'));
            }
            usleep(500 * 1000);
            $time_waited += 0.5;
        } while ($time_waited <= $TIMEOUT_DOWNLOAD);

        throw new RuntimeException(translate('error_timeout'));
    } elseif (($_GET["action"] ?? null) == "info") {
        // Endpoint can be used by the photo booth app to check if it's communicating with the correct URL
        echo json_encode([
            "version" => $VERSION,
            "name" => translate('info_name'),
        ]);
    } else {
        http_response_code(406);
        error_log(translate('endpoint_not_exist'));
        error_log(json_encode($_GET));
    }
} catch (RuntimeException $e) {
    $error_message = translate('error_runtime') . $e->getMessage();
    
    // Log error information
    error_log($error_message);
    error_log(json_encode($_GET));
    error_log(json_encode($_POST));
    error_log(json_encode($_FILES));
    
    // Display user-friendly error page
    if (($_GET["action"] ?? null) == "download" || isset($_SERVER['HTTP_ACCEPT']) && strpos($_SERVER['HTTP_ACCEPT'], 'text/html') !== false) {
        // Use HTML error page for browser requests
        include('error_template.php'); // Include the error page template
    } else {
        // Plain text for API requests
        http_response_code(500);
        header('Content-Type: text/plain; charset=UTF-8');
        echo $error_message;
    }
}