package ftn.siit.rbs.oblak.server.controller;

import ftn.siit.rbs.oblak.server.dto.AuthDtos.*;
import ftn.siit.rbs.oblak.server.service.AuthService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.DisabledException;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * REST kontroler za autentikaciju.
 *
 * Endpoint-i:
 *   POST /api/auth/login    – prijava, vraća JWT
 *   POST /api/auth/register – registracija novog korisnika, vraća JWT
 *
 * Oba endpoint-a su whitelisted u JwtRequestFilter (ne zahtevaju token).
 *
 * Bezbednosne napomene:
 * - Greške autentikacije uvek vraćaju isti tekst (sprečava user enumeration).
 * - Lozinka se nikad ne loguje.
 * - Svi exception-i se hvataju ovde i pretvaraju u čiste HTTP odgovore
 *   kako stack trace ne bi procurio klijentu.
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private static final Logger log = LoggerFactory.getLogger(AuthController.class);

    private static final String ERROR_KEY = "error";

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    // ── POST /api/auth/login ──────────────────────────────────────────────────

    /**
     * Prijava korisnika.
     *
     * <pre>
     * Zahtev:  { "username": "pera", "password": "tajnaLozinka123" }
     * Odgovor: { "token": "eyJ...", "refreshToken": null,
     *            "username": "pera", "role": "USER" }
     * </pre>
     *
     * HTTP statusi:
     *   200 – uspešna prijava
     *   400 – nedostaje username ili password u telu
     *   401 – pogrešni kredencijali ili nalog deaktiviran
     */
    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        if (request == null) {
            return ResponseEntity.badRequest()
                    .body(Map.of(ERROR_KEY, "Telo zahteva ne sme biti prazno."));
        }

        try {
            AuthResponse response = authService.login(request);
            return ResponseEntity.ok(response);

        } catch (BadCredentialsException | DisabledException ex) {
            // Isti tekst za oba slučaja – ne otkrivamo zašto je login odbijen
            return ResponseEntity.status(401)
                    .body(Map.of(ERROR_KEY, "Pogrešno korisničko ime ili lozinka."));

        } catch (IllegalArgumentException ex) {
            return ResponseEntity.badRequest()
                    .body(Map.of(ERROR_KEY, ex.getMessage()));
        }
    }

    // ── POST /api/auth/register ───────────────────────────────────────────────

    /**
     * Registracija novog korisnika.
     *
     * <pre>
     * Zahtev:  { "username": "pera", "password": "tajnaLozinka123" }
     * Odgovor: { "token": "eyJ...", "refreshToken": null,
     *            "username": "pera", "role": "USER" }
     * </pre>
     *
     * HTTP statusi:
     *   201 – uspešna registracija (korisnik je odmah ulogovan)
     *   400 – validacijska greška (kratak password, loš username format...)
     *   409 – username već postoji
     */
    @PostMapping("/register")
    public ResponseEntity<?> register(@RequestBody RegisterRequest request) {
        if (request == null) {
            return ResponseEntity.badRequest()
                    .body(Map.of(ERROR_KEY, "Telo zahteva ne sme biti prazno."));
        }

        try {
            AuthResponse response = authService.register(request);
            return ResponseEntity.status(201).body(response);

        } catch (IllegalArgumentException ex) {
            return ResponseEntity.badRequest()
                    .body(Map.of(ERROR_KEY, ex.getMessage()));

        } catch (IllegalStateException ex) {
            // Username već postoji → 409 Conflict
            return ResponseEntity.status(409)
                    .body(Map.of(ERROR_KEY, ex.getMessage()));
        }
    }
}