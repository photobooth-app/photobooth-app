<?php
/*
 * IMPORTANT:
 * 1. The API key ($APIKEY) must be changed to a random value. 
 *    This key is used to pair the photobooth app with the server, and it needs to match the key set in the photobooth app configuration.
 *    Leaving the API key as the default is a security risk, and the script will not function correctly until it is changed.
 *
 * 2. The Share button will only be visible if the page is accessed via a secure connection (HTTPS).
 *    If you are not using HTTPS, the Share button will not appear.
 */

// documentation see https://photobooth-app.org/setup/configuration/qrshareservice/

// configuration options
$APIKEY = "changedefault!";                 // set apikey to a random value, of at least 8 chars. The same apikey needs to be set in photobooth app to pair both systems
$WORK_DIRECTORY = __DIR__ . "/uploads";     // __DIR__ is the directory of the current PHP file
$ALLOWED_UPLOAD_MAX_SIZE = 25 * 2 ** 20;    // 25MB max file size to upload
$TIMEOUT_DOWNLOAD = 15;                     // if photobooth-app upload is not completed within this timeout, it's considered as an error and error is displayed instead image

// Translation variables
$translations = [
    'error_no_file_uploaded' => 'There is no file uploaded',
    'error_processing_file' => 'Error processing uploaded file!',
    'error_api_key' => 'APIKEY not correct! Check APIKEY in dl.php and photobooth config.',
    'error_empty_file' => 'The file is empty.',
    'error_large_file' => 'The file is too large',
    'error_not_allowed' => 'File not allowed.',
    'error_cannot_find_file' => 'Cannot find uploaded file',
    'error_upload_failed' => 'Photobooth had problems uploading the file, check photobooth log for errors',
    'download_or_share' => 'Download or Share Your File',
    'download_button' => 'Download',
    'share_button' => 'Share',
    'share_title' => 'Photobooth File',
    'share_text' => 'Check out this file I took!',
    'successful_share' => 'Successful share',
    'error_sharing' => 'Error sharing',
    'error_runtime' => 'Runtime error: ',
    'endpoint_not_exist' => 'Endpoint does not exist!',
    'info_version' => 'version',
    'info_name' => 'photobooth-app file upload extension',
];

// internal constants - do not change below this!
$VERSION = 2;
$DB_FILENAME = "jobs.sqlite3";
$ALLOWED_UPLOAD_TYPES = [
    'image/png' => 'png',
    'image/jpeg' => 'jpg',
    'image/gif' => 'gif',
    'video/mp4' => 'mp4',
];

// setup php ini
ini_set('display_errors', 0);
ini_set('display_startup_errors', 0);
ini_set("log_errors", 1);
ini_set("error_log", "php-error.log");
error_reporting(E_ALL);

// prevent nginx from additional buffering because the long running job would fail then
// nginx has additional buffer to php, the php buffer is flushed, but nginx not
header('X-Accel-Buffering: no'); // https://stackoverflow.com/a/25017347
ob_implicit_flush(true);   // flush always after any write to buffer without additional call to flush needed.

function text_to_image($text, $image_width = 400, $colour = array(0, 244, 34), $background = array(0, 0, 0))
{
    # some endpoints usually output images
    # if there is an error in the process, a placeholder image is generated so
    # there is at least something shown to the user why it failed
    $font = 50;
    $line_height = 15;
    $padding = 5;
    $text = wordwrap($text, ($image_width / 10));
    $lines = explode("\n", $text);
    $image = imagecreate($image_width, ((count($lines) * $line_height)) + ($padding * 2));
    $background = imagecolorallocate($image, $background[0], $background[1], $background[2]);
    $colour = imagecolorallocate($image, $colour[0], $colour[1], $colour[2]);
    imagefill($image, 0, 0, $background);
    $i = $padding;

    foreach ($lines as $line) {
        imagestring($image, $font, $padding, $i, trim($line), $colour);
        $i += $line_height;
    }

    header("Content-type: image/jpeg");
    header('Content-Disposition: inline; filename="err.jpg"');
    http_response_code(500);
    imagejpeg($image);
    imagedestroy($image);
}

function api_key_set()
{
    global $APIKEY;

    // die if APIKEY is not set
    if (strlen($APIKEY) < 8) {
        throw new RuntimeException('$APIKEY is empty or too short in dl.php script! Configure $APIKEY in dl.php and photoboothapp-config to pair systems.');
    }
    if (stripos($APIKEY, "changedefault!") !== false) {
        throw new RuntimeException('$APIKEY is default in dl.php script! Change $APIKEY in dl.php and photoboothapp-config to pair systems.');
    }
}

function isSecure()
{
    if (
        (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || $_SERVER['SERVER_PORT'] == 443
    ) {
        return true;
    }

    // Check for HTTPS in the "X-Forwarded-Proto" header for reverse proxies
    if (!empty($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {
        return true;
    }

    return false;
}

try {
    // db connection setup
    $db = new SQLite3($DB_FILENAME);
    $db->busyTimeout(200);
    // WAL mode has better control over concurrency.
    // Source: https://www.sqlite.org/wal.html
    #$db->exec('PRAGMA journal_mode = wal;');


    // setup checks
    # create working directory
    if (!is_dir($WORK_DIRECTORY)) {
        mkdir($WORK_DIRECTORY);
    }

    # create DB
    $db->exec("CREATE TABLE IF NOT EXISTS upload_requests(
        file_identifier TEXT PRIMARY KEY,
        filename TEXT,
        last_modified TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'pending'
    )");

    if (($_POST["action"] ?? null) == "upload" && ($_POST["id"] ?? null)) {
        // action: upload a file, identified by id.
        // once file uploaded, mark it as "uploaded" in db
        // ongoing download-action would check for "uploaded" mark and return the file then

        api_key_set();

        $file_identifier = $_POST["id"];

        // sanity check for apikey
        if ($_POST["apikey"] !== $APIKEY) {
            $db->exec("UPDATE upload_requests SET status = 'upload_failed' WHERE file_identifier = '" . $file_identifier . "'");
            throw new RuntimeException($translations['error_api_key']);
        }

        // file upload sanity checks
        if (!isset($_FILES["upload_file"])) {
            # set status to fail so ongoing download can stop waiting
            $db->exec("UPDATE upload_requests SET status = 'upload_failed' WHERE file_identifier = '" . $file_identifier . "'");
            throw new RuntimeException($translations['error_no_file_uploaded'] . " ($file_identifier)");
        }
        if ($_FILES['upload_file']['error'] != UPLOAD_ERR_OK) {
            throw new RuntimeException($translations['error_processing_file'] . " Errorcode=" . $_FILES['upload_file']['error']);
        }

        $filepath = $_FILES['upload_file']['tmp_name'];

        if (empty($filepath)) {
            throw new RuntimeException("tmp_name is empty, pls check php settings (upload size, ...)!");
        }
        try {
            $mimetype = mime_content_type($filepath);
        } catch (ValueError $e) {
            throw new RuntimeException("Mimetype of file could not be detected. Aborting.");
        }

        if (filesize($filepath) === 0) {
            throw new RuntimeException($translations['error_empty_file']);
        }
        if (filesize($filepath) > $ALLOWED_UPLOAD_MAX_SIZE) {
            throw new RuntimeException($translations['error_large_file']);
        }
        if (!in_array($mimetype, array_keys($ALLOWED_UPLOAD_TYPES))) {
            throw new RuntimeException($translations['error_not_allowed']);
        }

        // filename to store the uploaded file to in work directory
        $filename = basename($filepath);
        $extension = $ALLOWED_UPLOAD_TYPES[$mimetype];

        // query entry for id to double-check that currently uploaded file was actually requested and job assigned
        $results = $db->querySingle("SELECT * FROM upload_requests WHERE file_identifier='" . $file_identifier . "' AND status='job_assigned'", true);

        if (!empty($results)) {
            $db->exec("UPDATE upload_requests SET status = 'uploading' WHERE file_identifier = '" . $file_identifier . "'");

            // save uploaded file
            $newFilepath = $WORK_DIRECTORY . "/" . $filename . "." . $extension;
            if (!copy($filepath, $newFilepath)) { // Copy the file, returns false if failed
                throw new RuntimeException("Can't move file.");
            }
            unlink($filepath); // Delete the temp file

            // mark as uploaded
            $db->exec("UPDATE upload_requests SET filename = '$filename.$extension', status = 'uploaded' WHERE file_identifier = '" . $file_identifier . "'");

            echo "file successfully saved and ready to download";
        } else
            throw new RuntimeException("error processing job");
    } elseif (($_GET["action"] ?? null) == "upload_queue") {
        // longrunning task to wait for dl request
        api_key_set();

        $LOOP_TIME = 0.5; # loop every x seconds
        $LOOP_TIME_MAX = 240; # after x seconds, the script terminates and the client is expected to create a new connection latest

        $time_processed = 0;
        do {
            $results = $db->querySingle("SELECT * FROM upload_requests WHERE status = 'pending'", true);

            if (!empty($results)) {
                // non-empty results is to upload by photobooth-app
                $db->exec("UPDATE upload_requests SET status = 'job_assigned' WHERE file_identifier = '" . $results['file_identifier'] . "'");
                echo json_encode($results);
            } else {
                # nothing to do; send ping message to ensure connection health and have regular input to shareservice.py
                echo json_encode(['ping' => time()]);
            }
            # add newline so python backend can read it
            echo "\n";

            # flush content to output
            if (ob_get_level() > 0) ob_flush(); # flush internal buffer (needed for php builtin webserver during testing)
            flush();    # flush output buffer

            # wait before next iteration
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

                    echo "<!DOCTYPE html>
                        <html lang='en'>
                        <head>
                        <meta charset='UTF-8'>
                        <meta name='viewport' content='width=device-width, initial-scale=1.0'>
                        <title>{$translations['download_or_share']}</title>
                        <style>
                            body { font-family: Arial, sans-serif; margin: 0; padding: 10px; background-color: #f4f4f4; color: #333; text-align: center; }
                            img, video { max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px; padding: 5px; }
                            button { padding: 10px 20px; font-size: 16px; cursor: pointer; background-color: #0084ff; color: white; border: none; border-radius: 5px; margin-top: 10px; }
                            button:hover { background-color: #0056b3; }
                        </style>
                        </head>
                        <body>
                        <h1>{$translations['download_or_share']}</h1>";

                    if ($isImage) {
                        echo "<img src='data:$mimetype;base64,$base64EncodedData' alt='Image'>";
                    } elseif ($isVideo) {
                        echo "<video controls loop autoplay muted>
                            <source src='data:$mimetype;base64,$base64EncodedData' type='$mimetype'>
                            Your browser does not support the video tag.
                          </video>";
                    }

                    echo "<br>
                        <a href='data:$mimetype;base64,$base64EncodedData' download='" . $results["filename"] . "'><button>{$translations['download_button']}</button></a>";

                    // Show share button only if the page is accessed via HTTPS
                    if (isSecure()) {
                        echo "<button onclick='shareImage()'>{$translations['share_button']}</button>
                        <script>
                        function shareImage() {
                            if (!navigator.share) {
                                alert('Web share is not supported in your browser.');
                                return;
                            }

                            const file = new File([Uint8Array.from(atob('$base64EncodedData'), c => c.charCodeAt(0))], '" . $results["filename"] . "', {type: '$mimetype'});

                            navigator.share({
                                files: [file],
                                title: '{$translations['share_title']}',
                                text: '{$translations['share_text']}'
                            })
                            .then(() => console.log('{$translations['successful_share']}'))
                            .catch((error) => console.log('{$translations['error_sharing']}', error));
                        }
                        </script>";
                    }

                    echo "</body>
                        </html>";
                    exit;
                } else {
                    throw new RuntimeException($translations['error_cannot_find_file']);
                }
            } elseif (!empty($results) && $results["status"] == "upload_failed") {
                throw new RuntimeException($translations['error_upload_failed']);
            }
            usleep(500 * 1000);
            $time_waited += 0.5;
        } while ($time_waited <= $TIMEOUT_DOWNLOAD);

        throw new RuntimeException("photobooth did not upload the requested image within time :( no internet? service disabled?");
    } elseif (($_GET["action"] ?? null) == "list") {
        api_key_set();
        echo "<pre>";
        $results = $db->query("SELECT * FROM upload_requests ORDER BY last_modified DESC");
        while ($row = $results->fetchArray(SQLITE3_ASSOC)) {
            print_r($row);
        }
        echo "</pre>";
    } elseif (($_GET["action"] ?? null) == "info") {
        // endpoint can be used by photobooth-app to check it's communicating with the correct URL
        echo json_encode([
            "version" => $VERSION,
            "name" => $translations['info_name'],
        ]);
    } else {
        http_response_code(406);
        error_log($translations['endpoint_not_exist']);
        error_log(json_encode($_GET));
    }
} catch (RuntimeException $e) {
    http_response_code(500);

    if (!(($_GET["action"] ?? null) == "download")) {
        # if download action, output exception as image, otherwise as text
        echo $translations['error_runtime'] . $e->getMessage();
    } else {
        text_to_image($translations['error_runtime'] . $e->getMessage());
    }

    error_log($translations['error_runtime'] . $e->getMessage());
    error_log(json_encode($_GET));
    error_log(json_encode($_POST));
    error_log(json_encode($_FILES));
}
