package ftn.siit.rbs.oblak.server.exception;

/**
 * Thrown when the Code Verifier (bandit) rejects an uploaded script.
 * The message contains a human-readable summary from bandit's output.
 */
public class CodeVerificationException extends RuntimeException {

    public CodeVerificationException(String message) {
        super(message);
    }
}
