package ftn.siit.rbs.oblak.server.controller;

import java.io.IOException;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.nio.file.Path;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import ftn.siit.rbs.oblak.server.entity.FunctionRecord;
import ftn.siit.rbs.oblak.server.service.FunctionService;

@RestController
@RequestMapping("/api/functions")
public class FunctionController {

    private static final Logger log = LoggerFactory.getLogger(FunctionController.class);

    private static final String HASH_REGEX = "^[a-f0-9]{64}$";
    
    private static final String ERROR_KEY = "error";
    private static final String URL_HASH_KEY = "urlHash";

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
                    .body(Map.of(ERROR_KEY, "No file provided or file is empty."));
        }

        if (!isPythonFile(file)) {
            return ResponseEntity.badRequest()
                    .body(Map.of(ERROR_KEY,
                            "Only Python (.py) files are accepted. "
                            + "Received: " + file.getOriginalFilename()));
        }

        if (requirements != null && !isEmpty(requirements) && !isTextFile(requirements)) {
            return ResponseEntity.badRequest()
                    .body(Map.of(ERROR_KEY, "requirements must be a plain-text file."));
        }

        // ── Delegate to service (may throw CodeVerificationException → 422) ───
        String urlHash = functionService.uploadAndRegister(file, requirements);

        String invokeUrl = "/api/functions/" + urlHash + "/invoke";
        log.info("Function uploaded successfully – hash={}", urlHash);

        return ResponseEntity
                .created(URI.create(invokeUrl))
                .body(Map.of(
                        URL_HASH_KEY,   urlHash,
                        "invokeUrl", invokeUrl
                ));
    }

    // ── Invocation ────────────────────────────────────────────────────────────

    @PostMapping("/{urlHash}/invoke")
    public ResponseEntity<Map<String, Object>> invoke(
            @PathVariable String urlHash
    ) {
        if (!urlHash.matches(HASH_REGEX)) {
            return ResponseEntity.badRequest()
                    .body(Map.of(ERROR_KEY, "Invalid function hash format."));
        }

        FunctionRecord functionRecord = functionService.resolveFunction(urlHash);

        log.info("Invocation requested for hash={} path={}",
                urlHash, functionRecord.getStoragePath());
        
        try {
            Path folderPath = Paths.get(functionRecord.getStoragePath());
            Path filePath = folderPath.resolve("handler.py");

            String codeContent = Files.readString(filePath);
            String requirementsContent = "";

            if (functionRecord.getRequirementsPath() != null) {
                requirementsContent = Files.readString(Paths.get(functionRecord.getRequirementsPath()));
            }

            Map<String, Object> rustPayload = new HashMap<>();
            rustPayload.put("function_hash", urlHash);
            rustPayload.put("code", codeContent);
            rustPayload.put("requirements", requirementsContent.isEmpty() ? null : requirementsContent);

            RestTemplate restTemplate = new RestTemplate();
            String rustOrchestratorUrl = "http://localhost:8081/api/v1/execute";

            ResponseEntity<Map> rustResponse = restTemplate.postForEntity(
                rustOrchestratorUrl,
                rustPayload,
                Map.class
            );

            return ResponseEntity.ok(rustResponse.getBody());
        } catch (IOException e) {
                log.error("Greška prilikom čitanja fajlova sa diska: {}", e.getMessage());
                return ResponseEntity.internalServerError()
                        .body(Map.of(ERROR_KEY, "Could not read function files from storage."));
        } catch (RestClientException e) {
                log.error("Greška u komunikaciji sa Rust Orkestratorom: {}", e.getMessage());
                return ResponseEntity.internalServerError()
                        .body(Map.of(ERROR_KEY, "Firecracker orchestrator service is unreachable."));
        }
    }

    // ── Metadata lookup ───────────────────────────────────────────────────────

    @GetMapping("/{urlHash}")
    public ResponseEntity<Map<String, String>> getMetadata(
            @PathVariable String urlHash
    ) {
        if (!urlHash.matches(HASH_REGEX)) {
            return ResponseEntity.badRequest()
                    .body(Map.of(ERROR_KEY, "Invalid function hash format."));
        }

        FunctionRecord functionRecord = functionService.resolveFunction(urlHash);

        return ResponseEntity.ok(Map.of(
                URL_HASH_KEY,          functionRecord.getUrlHash(),
                "originalFilename", functionRecord.getOriginalFilename(),
                "storagePath",      functionRecord.getStoragePath(),
                "status",           functionRecord.getStatus().name(),
                "createdAt",        functionRecord.getCreatedAt().toString()
        ));
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private boolean isPythonFile(MultipartFile file) {
        String name = file.getOriginalFilename();
        if (name == null || !name.endsWith(".py")) {
            return false;
        }
        String ct = file.getContentType();
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