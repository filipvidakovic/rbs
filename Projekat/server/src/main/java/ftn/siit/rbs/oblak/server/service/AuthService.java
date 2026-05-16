package ftn.siit.rbs.oblak.server.service;

import ftn.siit.rbs.oblak.server.config.JwtTokenUtil;
import ftn.siit.rbs.oblak.server.dto.AuthDtos.AuthResponse;
import ftn.siit.rbs.oblak.server.dto.AuthDtos.LoginRequest;
import ftn.siit.rbs.oblak.server.dto.AuthDtos.RegisterRequest;
import ftn.siit.rbs.oblak.server.entity.User;
import ftn.siit.rbs.oblak.server.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authentication.*;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

/**
 * Servis za autentikaciju i registraciju korisnika.
 *
 * Bezbednosne napomene:
 * - Lozinke se NIKAD ne loguju ni pamte u plain text obliku.
 * - BCrypt hash se čuva u bazi (via PasswordEncoder).
 * - Greška pri loginu uvek vraća isti tekst ("Pogrešno korisničko ime ili lozinka.")
 *   kako bi se sprečilo nabrajanje korisnika (user enumeration).
 * - Username se validira regex-om pre upisa u bazu.
 */
@Service
public class AuthService {

    private static final Logger log = LoggerFactory.getLogger(AuthService.class);

    /**
     * Dozvoljeni karakteri za username: slova, brojevi, tačka, crtica, underscore.
     * Dužina: 3–32 karaktera.
     */
    private static final String USERNAME_PATTERN = "^[a-zA-Z0-9._-]{3,32}$";

    /**
     * Minimalna dužina lozinke.
     */
    private static final int MIN_PASSWORD_LENGTH = 8;

    private final AuthenticationManager authenticationManager;
    private final JwtTokenUtil          jwtTokenUtil;
    private final UserRepository        userRepository;
    private final PasswordEncoder       passwordEncoder;

    public AuthService(
            AuthenticationManager authenticationManager,
            JwtTokenUtil jwtTokenUtil,
            UserRepository userRepository,
            PasswordEncoder passwordEncoder
    ) {
        this.authenticationManager = authenticationManager;
        this.jwtTokenUtil          = jwtTokenUtil;
        this.userRepository        = userRepository;
        this.passwordEncoder       = passwordEncoder;
    }

    // ── Login ─────────────────────────────────────────────────────────────────

    /**
     * Autentikuje korisnika i vraća JWT token.
     *
     * @throws BadCredentialsException ako su kredencijali pogrešni
     * @throws DisabledException       ako je nalog deaktiviran
     */
    public AuthResponse login(LoginRequest request) {
        validateNotBlank(request.username(), "Username");
        validateNotBlank(request.password(), "Password");

        try {
            // Spring Security proverava username + bcrypt hash
            authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(
                            request.username(),
                            request.password()
                    )
            );
        } catch (AuthenticationException ex) {
            // Namerno: ne razlikujemo "nema korisnika" od "pogrešna lozinka"
            log.warn("Neuspešan login pokušaj za username='{}'", request.username());
            throw new BadCredentialsException("Pogrešno korisničko ime ili lozinka.");
        }

        User user = userRepository.findByUsername(request.username())
                .orElseThrow(() -> new BadCredentialsException("Pogrešno korisničko ime ili lozinka."));

        String token = jwtTokenUtil.generateToken(user.getUsername());
        log.info("Uspešan login: username='{}'", user.getUsername());

        return new AuthResponse(token, null, user.getUsername(), user.getRole().name());
    }

    // ── Register ──────────────────────────────────────────────────────────────

    /**
     * Registruje novog korisnika.
     *
     * @throws IllegalArgumentException ako username/password ne zadovoljavaju uslove
     * @throws IllegalStateException    ako username već postoji
     */
    public AuthResponse register(RegisterRequest request) {
        // ── Validacija username-a ─────────────────────────────────────────────
        validateNotBlank(request.username(), "Username");
        if (!request.username().matches(USERNAME_PATTERN)) {
            throw new IllegalArgumentException(
                    "Username sme sadržati samo slova, brojeve, '.', '-' i '_' (3–32 karaktera).");
        }

        // ── Validacija lozinke ────────────────────────────────────────────────
        validateNotBlank(request.password(), "Lozinka");
        if (request.password().length() < MIN_PASSWORD_LENGTH) {
            throw new IllegalArgumentException(
                    "Lozinka mora imati najmanje " + MIN_PASSWORD_LENGTH + " karaktera.");
        }

        // ── Provera jedinstvenosti ────────────────────────────────────────────
        if (userRepository.existsByUsername(request.username())) {
            // Namerno: ne otkrivamo da li je username zauzet drug. korisniku.
            // Ali za registraciju je OK reći jer korisnik sam pokušava da registruje.
            throw new IllegalStateException("Korisnik sa tim username-om već postoji.");
        }

        // ── Kreiranje korisnika ───────────────────────────────────────────────
        String hash = passwordEncoder.encode(request.password());
        User user = new User(request.username(), hash);
        userRepository.save(user);

        log.info("Novi korisnik registrovan: username='{}'", user.getUsername());

        // Odmah vraćamo token – korisnik je odmah ulogovan
        String token = jwtTokenUtil.generateToken(user.getUsername());
        return new AuthResponse(token, null, user.getUsername(), user.getRole().name());
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private void validateNotBlank(String value, String fieldName) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(fieldName + " ne sme biti prazan.");
        }
    }
}