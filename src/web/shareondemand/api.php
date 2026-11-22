<?php
declare(strict_types=1);

namespace Photobooth;
use RuntimeException;
use function strlen, count, intval; // use global functions

const APIKEY = "changedefault!";   // <-- user changes this


class AuthException extends RuntimeException
{
}


final class ShareService
{
    private const array ALLOWED_TYPES = [
        'image/png' => 'png',
        'image/jpeg' => 'jpg',
        'image/jpg' => 'jpg',
        'image/avif' => 'avif',
        'image/webp' => 'webp',
        'image/gif' => 'gif',
        'video/mp4' => 'mp4',
    ];

    public function __construct(
        private string $apiKey,
        private string $workDir,
        private string $jobDir,
        private int $maxSize = 25 * 2 ** 20, //25 Mb
        private int $timeout = 15   // s
    ) {
        ini_set('display_startup_errors', 0);
        ini_set('display_errors', 0);
        ini_set('log_errors', 1);
        ini_set('error_log', __DIR__ . "/php-error.log");
    }

    private function validateApiKey(string $key): void
    {
        if (strlen($this->apiKey) < 8) {
            throw new AuthException('The API key is empty or too short! The key needs to be at least 8 characters.');
        }
        if ($this->apiKey == "changedefault!") {
            throw new AuthException('The API key is the default value! You need to set a custom api key.');
        }
        if ($key !== $this->apiKey) {
            throw new AuthException("Invalid API key!");
        }
    }

    private function clearJob(string $id): void
    {
        // just keep uploaded status
        foreach (["pending", "assigned", "failed"] as $s) {
            @unlink($this->jobFile($id, $s));
        }
    }


    private function jobFile(string $id, string $status): string
    {
        return "$this->jobDir/$id.$status";
    }

    private function setStatus(string $id, string $status): void
    {
        $this->clearJob($id);
        file_put_contents($this->jobFile($id, $status), "1");
    }

    private function hasStatus(string $id, string $status): bool
    {
        return file_exists($this->jobFile($id, $status));
    }

    private function hasAnyStatus(string $id): bool
    {
        return count(glob($this->jobFile($id, "*"))) > 0;
    }



    public function getPendingJob(): void
    {
        $this->validateApiKey($_POST['apikey'] ?? '');



        $pending = glob("$this->jobDir/*.pending");

        if (!empty($pending)) {
            $file = basename($pending[0]);
            $id = explode(".", $file)[0];

            // error_log("pending job sent to client waiting for ack, id $id");
            echo json_encode(["id" => $id]) . "\n";
        } else {
            echo json_encode(["ping" => time()]) . "\n";

        }
    }

    public function accept(): void
    {
        $this->validateApiKey($_POST['apikey'] ?? '');
        $id = $_POST['id'] ?? null;

        if (!$id) {
            throw new RuntimeException("Missing id");
        }

        if (!$this->hasStatus($id, "pending")) {
            throw new RuntimeException("Job not pending");
        }

        $this->setStatus($id, "assigned");

        echo json_encode(["detail" => "accepted"]);
    }

    public function upload(): void
    {
        $this->validateApiKey($_POST['apikey'] ?? '');

        $id = $_POST['id'] ?? null;

        if (!$id) {
            throw new RuntimeException("Missing id");
        }

        if (!$this->hasStatus($id, "assigned")) {
            throw new RuntimeException("File not assigned to a client to upload, id=$id");
        }

        if (!isset($_FILES['upload_file'])) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("No file uploaded");
        }

        $tmp_name = $_FILES['upload_file']['tmp_name'];
        if (!$tmp_name || filesize($tmp_name) === 0) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("Empty file");
        }
        if (filesize($tmp_name) > $this->maxSize) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("File too large");
        }

        $mime = mime_content_type($tmp_name);
        if (!isset(self::ALLOWED_TYPES[$mime])) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("File type $mime not allowed");
        }

        $ext = self::ALLOWED_TYPES[$mime];
        $filename = "$id.$ext";
        $dest = "$this->workDir/$filename";

        if (!move_uploaded_file($tmp_name, $dest)) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("Failed to store file $tmp_name to $dest");
        }

        $this->setStatus($id, "uploaded");

        echo json_encode([
            "detail" => "ok",
            "type" => "message"
        ]);
    }

    public function download(): void
    {
        $id = $_GET['id'] ?? null;
        if (!$id) {
            throw new RuntimeException("Missing id");
        }

        $revision = $_GET['rev'] ?? null;
        if ($revision !== null) {
            if (!is_string($revision) || !ctype_digit($revision)) {
                throw new RuntimeException("Invalid revision");
            }
            $id .= "_$revision";
        }

        if (!$this->hasAnyStatus($id)) {
            $this->setStatus($id, "pending");
        }

        $wait = 0;
        while ($wait < $this->timeout) {
            // first to check if the file is already avail on server:
            if ($this->hasStatus($id, "uploaded")) {
                $file = glob("$this->workDir/$id.*")[0] ?? null;
                if (!$file || !file_exists($file)) {
                    throw new RuntimeException("File missing");
                }

                header("Content-Type: " . mime_content_type($file));
                readfile($file);
                return;
            }

            //second check is to see if the upload failed, inform about it but delete the job data so it could be uploaded again.
            if ($this->hasStatus($id, "failed")) {
                $this->clearJob($id);
                throw new RuntimeException("Upload failed");
            }

            usleep(500_000);
            $wait += 0.5;
            continue;


        }

        $this->clearJob($id);
        throw new RuntimeException("Timeout waiting for photobooth");
    }

    public function version(): void
    {
        echo json_encode([
            "detail" => "1",
            "type" => "version"
        ]);
    }

    public function setupFolders(): void
    {
        if (!is_dir($this->workDir))
            if (!mkdir($this->workDir, 0775, true))
                throw new RuntimeException("The workDir $this->workDir is not writeable.");
        if (!is_dir($this->jobDir))
            if (!mkdir($this->jobDir, 0775, true))
                throw new RuntimeException("The jobDir $this->jobDir is not writeable.");
    }

    public function cleanupOldFiles(int $maxAgeSeconds = 600): void
    {
        $now = time();

        // Cleanup job files
        foreach (glob("$this->jobDir/*.*") as $file) {
            if (is_file($file)) {
                $age = $now - filemtime($file);
                if ($age > $maxAgeSeconds) {
                    @unlink($file);
                }
            }
        }

        // Cleanup uploaded media files
        foreach (glob("$this->workDir/*.*") as $file) {
            if (is_file($file)) {
                $age = $now - filemtime($file);
                if ($age > $maxAgeSeconds) {
                    @unlink($file);
                }
            }
        }
    }
}

$service = new ShareService(
    apiKey: APIKEY,
    workDir: __DIR__ . "/uploads",
    jobDir: __DIR__ . "/jobs"
);

try {
    // lockfile to setup folders and cleanup because otherwise multiple requests could interfere
    // setupfolder checks in thread A if folder exists, no, then creates it and in thread B it also not exists, tries to recreate the now existing dir
    $lock = fopen(sys_get_temp_dir() . "/share_service_setup.lock", "c");
    flock($lock, LOCK_EX);
    $service->setupFolders();
    $service->cleanupOldFiles();   // auto-cleanup
    flock($lock, LOCK_UN);
    fclose($lock);



    $action = $_REQUEST['action'] ?? null;

    switch ($action) {
        case "getpendingjob":
            $service->getPendingJob();
            break;
        case "accept":
            $service->accept();
            break;
        case "upload":
            $service->upload();
            break;
        case "download":
            $service->download();
            break;
        case "version":
            $service->version();
            break;
        default:
            http_response_code(400); // bad request
            echo json_encode([
                "detail" => "unknown action",
                "type" => "error"
            ]);
    }
} catch (AuthException $e) {
    error_log("AuthException: " . $e->getMessage());

    http_response_code(401);

    echo json_encode([
        "detail" => $e->getMessage(),
        "type" => "auth_error"
    ]);
} catch (RuntimeException $e) {
    error_log("RuntimeException: " . $e->getMessage());

    // JSON is safest for browser + photobooth
    http_response_code(500);

    echo json_encode([
        "detail" => $e->getMessage(),
        "type" => "error"
    ]);


}
