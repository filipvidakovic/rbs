package ftn.siit.rbs.oblak.server.controller;

import ftn.siit.rbs.oblak.server.entity.FunctionRecord;
import ftn.siit.rbs.oblak.server.service.FunctionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;
import java.net.URI;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/functions")
public class FunctionController {

    private static final Logger log = LoggerFactory.getLogger(FunctionController.class);

    private static final String HASH_REGEX = "^[a-f0-9]{64}$";

    private final FunctionService functionService;

    public FunctionController(FunctionService functionService) {
        this.functionService = functionService;
    }

    // ── Upload ────────────────────────────────────────────────────────────────

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<Map<String, String>> upload(
            @RequestPart("file") MultipartFile file,
            @RequestPart(value = "requirements", required = false) MultipartFile requirements
    ) throws IOException {

        // ── Input validation ───────────────────────────────────────────────────
        if (file == null || file.isEmpty()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "No file provided or file is empty."));
        }

        if (!isPythonFile(file)) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error",
                            "Only Python (.py) files are accepted. "
                            + "Received: " + file.getOriginalFilename()));
        }

        if (requirements != null && !isEmpty(requirements) && !isTextFile(requirements)) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "requirements must be a plain-text file."));
        }

        // ── Delegate to service (may throw CodeVerificationException → 422) ───
        String urlHash = functionService.uploadAndRegister(file, requirements);

        String invokeUrl = "/api/v1/functions/" + urlHash + "/invoke";
        log.info("Function uploaded successfully – hash={}", urlHash);

        return ResponseEntity
                .created(URI.create(invokeUrl))
                .body(Map.of(
                        "urlHash",   urlHash,
                        "invokeUrl", invokeUrl
                ));
    }

    // ── Invocation placeholder ────────────────────────────────────────────────

    @PostMapping("/{urlHash}/invoke")
    public ResponseEntity<Map<String, String>> invoke(
            @PathVariable String urlHash
    ) {
        if (!urlHash.matches(HASH_REGEX)) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "Invalid function hash format."));
        }

        FunctionRecord record = functionService.resolveFunction(urlHash);

        log.info("Invocation requested for hash={} path={}",
                urlHash, record.getStoragePath());

        // TODO: Send an execution request to the Firecracker Orchestrator service
        //       (e.g. via an internal REST call or a message queue).
        //       For now, we confirm the function exists and return its storage path
        //       so the orchestrator can locate handler.py.
        return ResponseEntity.accepted()
                .body(Map.of(
                        "status",      "ACCEPTED",
                        "urlHash",     record.getUrlHash(),
                        "storagePath", record.getStoragePath(),
                        "message",     "Execution request received. "
                                       + "The Firecracker orchestrator will run your function."
                ));
    }

    // ── Metadata lookup ───────────────────────────────────────────────────────

    @GetMapping("/{urlHash}")
    public ResponseEntity<Map<String, String>> getMetadata(
            @PathVariable String urlHash
    ) {
        if (!urlHash.matches(HASH_REGEX)) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "Invalid function hash format."));
        }

        FunctionRecord record = functionService.resolveFunction(urlHash);

        return ResponseEntity.ok(Map.of(
                "urlHash",          record.getUrlHash(),
                "originalFilename", record.getOriginalFilename(),
                "storagePath",      record.getStoragePath(),
                "status",           record.getStatus().name(),
                "createdAt",        record.getCreatedAt().toString()
        ));
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private boolean isPythonFile(MultipartFile file) {
        String name = file.getOriginalFilename();
        if (name == null || !name.endsWith(".py")) {
            return false;
        }
        String ct = file.getContentType();
        // Accept common MIME types used for Python files.
        return ct == null
                || ct.startsWith("text/")
                || ct.equals("application/octet-stream")
                || ct.equals("application/x-python")
                || ct.equals("application/x-python-code");
    }

    private boolean isTextFile(MultipartFile file) {
        String ct = file.getContentType();
        return ct == null || ct.startsWith("text/") || ct.equals("application/octet-stream");
    }

    private boolean isEmpty(MultipartFile file) {
        return file == null || file.isEmpty();
    }
}
