package ftn.siit.rbs.oblak.server.dto;

/**
 * DTOs za auth endpoint-e.
 *
 * Koristimo Java record-e – immutable, bez boilerplate-a.
 * Validacija je na nivou kontrolera (@Valid + anotacije).
 */
public final class AuthDtos {

    private AuthDtos() {}

    // ── Zahtevi ───────────────────────────────────────────────────────────────

    /**
     * Telo POST /api/auth/login
     */
    public record LoginRequest(
            String username,
            String password
    ) {}

    /**
     * Telo POST /api/auth/register
     */
    public record RegisterRequest(
            String username,
            String password
    ) {}

    // ── Odgovori ──────────────────────────────────────────────────────────────

    /**
     * Odgovor na uspešan login ili register.
     * Polje "token" je JWT; refreshToken je opcionalan (null ako nije podržan).
     */
    public record AuthResponse(
            String token,
            String refreshToken,
            String username,
            String role
    ) {}

    /**
     * Generički odgovor sa porukom (grešake, potvrde...).
     */
    public record MessageResponse(String message) {}
}