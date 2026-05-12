package ftn.siit.rbs.oblak.server.exception;

/**
 * Thrown when a caller references a URL hash that does not exist
 * or has not yet reached VERIFIED status.
 */
public class FunctionNotFoundException extends RuntimeException {

    public FunctionNotFoundException(String urlHash) {
        super("No verified function found for hash: " + urlHash);
    }
}
