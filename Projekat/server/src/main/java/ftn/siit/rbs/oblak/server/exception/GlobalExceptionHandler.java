package ftn.siit.rbs.oblak.server.exception;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import java.net.URI;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    // ── 422 Unprocessable Entity – bandit rejected the code ──────────────────

    @ExceptionHandler(CodeVerificationException.class)
    public ProblemDetail handleVerification(CodeVerificationException ex) {
        log.warn("Code verification failed: {}", ex.getMessage());
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(
                HttpStatus.UNPROCESSABLE_ENTITY, ex.getMessage());
        pd.setTitle("Code Verification Failed");
        pd.setType(URI.create("https://oblak.edu.rs/errors/verification-failed"));
        return pd;
    }

    // ── 404 Not Found ─────────────────────────────────────────────────────────

    @ExceptionHandler(FunctionNotFoundException.class)
    public ProblemDetail handleNotFound(FunctionNotFoundException ex) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(
                HttpStatus.NOT_FOUND, ex.getMessage());
        pd.setTitle("Function Not Found");
        pd.setType(URI.create("https://oblak.edu.rs/errors/function-not-found"));
        return pd;
    }

    // ── 413 Payload Too Large ─────────────────────────────────────────────────

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ProblemDetail handleFileTooLarge(MaxUploadSizeExceededException ex) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(
                HttpStatus.PAYLOAD_TOO_LARGE,
                "Uploaded file exceeds the maximum allowed size.");
        pd.setTitle("File Too Large");
        pd.setType(URI.create("https://oblak.edu.rs/errors/file-too-large"));
        return pd;
    }

    // ── 500 Internal Server Error – catch-all ─────────────────────────────────

    @ExceptionHandler(Exception.class)
    public ProblemDetail handleGeneric(Exception ex) {
        // Log the full exception server-side but return nothing sensitive to the client.
        log.error("Unhandled exception", ex);
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(
                HttpStatus.INTERNAL_SERVER_ERROR,
                "An unexpected error occurred. Please try again later.");
        pd.setTitle("Internal Server Error");
        pd.setType(URI.create("https://oblak.edu.rs/errors/internal-error"));
        return pd;
    }
}
