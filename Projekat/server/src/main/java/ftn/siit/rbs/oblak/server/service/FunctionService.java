package ftn.siit.rbs.oblak.server.service;

import ftn.siit.rbs.oblak.server.entity.FunctionRecord;
import ftn.siit.rbs.oblak.server.exception.CodeVerificationException;
import ftn.siit.rbs.oblak.server.repository.FunctionRecordRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.*;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Service
public class FunctionService {

    private static final Logger log = LoggerFactory.getLogger(FunctionService.class);

    private static final long VERIFIER_TIMEOUT_SECONDS = 30L;

    private static final String DEFAULT_HANDLER_NAME = "handler.py";

    // ── Configuration injected from application.properties ───────────────────

    @Value("${oblak.storage.base-path}")
    private String basePath;

    @Value("${oblak.storage.temp-path}")
    private String tempPath;

    @Value("${oblak.verifier.script-path}")
    private String verifierScriptPath;

    @Value("${oblak.verifier.bandit.min-severity:LOW}")
    private String minSeverity;

    @Value("${oblak.verifier.bandit.min-confidence:MEDIUM}")
    private String minConfidence;

    // ── Dependencies ──────────────────────────────────────────────────────────

    private final FunctionRecordRepository repository;

    public FunctionService(FunctionRecordRepository repository) {
        this.repository = repository;
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Entry point for the upload controller.
     *
     * @param file             the uploaded Python source file (multipart)
     * @param requirementsFile optional {@code requirements.txt} (may be {@code null})
     * @return the unique URL hash that the caller can use to invoke the function
     * @throws CodeVerificationException if bandit finds security issues
     * @throws IOException               if file I/O fails
     */
    public String uploadAndRegister(MultipartFile file, MultipartFile requirementsFile)
            throws IOException {

        String originalName = sanitizeFilename(file.getOriginalFilename());

        // ── Step 1: Write to a secure temp directory ──────────────────────────
        Path tempDir = createTempDirectory();
        Path tempScript = tempDir.resolve(DEFAULT_HANDLER_NAME);

        try {
            Files.write(tempScript, file.getBytes(), StandardOpenOption.CREATE_NEW);

            // ── Step 2: Run the Code Verifier ─────────────────────────────────
            runVerifier(tempScript);

            // ── Step 3: Compute content hash (becomes the public URL token) ───
            String urlHash = computeSha256(tempScript);

            // ── Step 4: Move files to permanent storage ────────────────────────
            Path functionDir = Path.of(basePath, urlHash);
            Files.createDirectories(functionDir);
            Files.move(tempScript, functionDir.resolve(DEFAULT_HANDLER_NAME),
                    StandardCopyOption.REPLACE_EXISTING);

            if (requirementsFile != null && !requirementsFile.isEmpty()) {
                Path reqDest = functionDir.resolve("requirements.txt");
                Files.write(reqDest, requirementsFile.getBytes());
            }

            String requirementsPath = null;

            if (requirementsFile != null && !requirementsFile.isEmpty()) {
                Path reqDest = functionDir.resolve("requirements.txt");
                Files.write(reqDest, requirementsFile.getBytes());
                requirementsPath = reqDest.toAbsolutePath().toString();
            }

            FunctionRecord functionRecord = new FunctionRecord(
                    urlHash,
                    functionDir.toAbsolutePath().toString(),
                    requirementsPath,
                    originalName
            );
            functionRecord.setStatus(FunctionRecord.Status.VERIFIED);
            repository.save(functionRecord);

            log.info("Function '{}' registered with hash {}", originalName, urlHash);
            return urlHash;

        } finally {
            // Always clean up the temp directory, even if verification passed
            // (in which case the file was already moved out of it).
            deleteSilently(tempDir);
        }
    }

    public FunctionRecord resolveFunction(String urlHash) {
        return repository.findByUrlHash(urlHash)
                .filter(r -> r.getStatus() == FunctionRecord.Status.VERIFIED)
                .orElseThrow(() -> new ftn.siit.rbs.oblak.server.exception.FunctionNotFoundException(urlHash));
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private Path createTempDirectory() throws IOException {
        Path root = Path.of(tempPath);
        Files.createDirectories(root);
        return Files.createTempDirectory(root, "upload-");
    }

    /**
     * Invokes {@code verifier.py} via {@link ProcessBuilder} (no shell involved).
     *
     * <p>The verifier script exits with:
     * <ul>
     *   <li>{@code 0} – no issues above the configured threshold → accepted</li>
     *   <li>{@code 1} – bandit flagged issues above the threshold → rejected</li>
     *   <li>{@code 2} – verifier internal error → treated as a rejection</li>
     * </ul>
     *
     * @param scriptPath absolute path to the temp Python file being analysed
     * @throws CodeVerificationException if bandit finds security issues or times out
     * @throws IOException               if the subprocess cannot be started
     */
    private void runVerifier(Path scriptPath) throws IOException {
        // Security: pass arguments as a list – never concatenate into a shell string.
        List<String> command = List.of(
                "python3",
                verifierScriptPath,
                scriptPath.toAbsolutePath().toString()
        );

        ProcessBuilder pb = new ProcessBuilder(command);
        pb.environment().put("OBLAK_MIN_SEVERITY", minSeverity);
        pb.environment().put("OBLAK_MIN_CONFIDENCE", minConfidence);

        // Redirect stderr into stdout so we capture bandit's output in one stream.
        pb.redirectErrorStream(true);

        Process process;
        try {
            process = pb.start();
        } catch (IOException ex) {
            throw new IOException("Failed to launch the code verifier process: " + ex.getMessage(), ex);
        }

        // Capture verifier output (used only for logging – never returned to the client).
        String output;
        try (InputStream is = process.getInputStream()) {
            output = new String(is.readAllBytes());
        }

        boolean finished;
        try {
            finished = process.waitFor(VERIFIER_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            process.destroyForcibly();
            throw new CodeVerificationException("Verifier was interrupted.");
        }

        if (!finished) {
            process.destroyForcibly();
            throw new CodeVerificationException(
                    "Code verification timed out after " + VERIFIER_TIMEOUT_SECONDS + " seconds.");
        }

        int exitCode = process.exitValue();
        if (exitCode != 0) {
            // Log the raw bandit output server-side for audit; return only a safe summary.
            log.warn("Verifier rejected file (exit {}). Bandit output:\n{}", exitCode, output);
            throw new CodeVerificationException(
                    "Static analysis found security issues in the uploaded code. "
                    + "Upload rejected. Review your code with 'bandit' locally before retrying.");
        }

        log.debug("Verifier approved file (exit 0).");
    }

    private String computeSha256(Path path) throws IOException {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException ex) {
            // SHA-256 is mandated by the JVM spec; this branch is unreachable.
            throw new IllegalStateException("SHA-256 not available", ex);
        }

        try (InputStream in = Files.newInputStream(path)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                digest.update(buffer, 0, read);
            }
        }

        return HexFormat.of().formatHex(digest.digest());
    }

    private String sanitizeFilename(String original) {
        if (original == null || original.isBlank()) {
            return DEFAULT_HANDLER_NAME;
        }
        // Keep only the last path component.
        String name = Path.of(original).getFileName().toString();
        // Strip any remaining null bytes.
        name = name.replace("\0", "");
        return name.isBlank() ? DEFAULT_HANDLER_NAME : name;
    }

    private void deleteSilently(Path dir) {
        try (var stream = Files.walk(dir)) {
            stream.sorted(java.util.Comparator.reverseOrder())
                  .forEach(p -> {
                      try { Files.deleteIfExists(p); }
                      catch (IOException ex) {
                          log.warn("Could not delete temp path", ex);
                      }
                  });
        } catch (IOException ex) {
            log.warn("Could not walk temp directory {}: {}", dir, ex.getMessage());
        }
    }
}
