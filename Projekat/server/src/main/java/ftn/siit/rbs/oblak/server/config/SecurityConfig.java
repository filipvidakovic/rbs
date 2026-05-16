package ftn.siit.rbs.oblak.server.config;

import ftn.siit.rbs.oblak.server.service.JwtUserDetailsService;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/**
 * Spring Security konfiguracija.
 *
 * - Stateless sesija (JWT, nema HTTP sesija).
 * - CSRF isključen (REST API, ne koristimo cookie-based auth).
 * - Whitelist: /api/auth/** je javno dostupan.
 * - Sve ostalo zahteva validan JWT.
 * - BCrypt za hashovanje lozinki (strength=12).
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtRequestFilter     jwtRequestFilter;
    private final JwtUserDetailsService userDetailsService;

    public SecurityConfig(JwtRequestFilter jwtRequestFilter,
                          JwtUserDetailsService userDetailsService) {
        this.jwtRequestFilter  = jwtRequestFilter;
        this.userDetailsService = userDetailsService;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                // REST API – ne trebaju nam CSRF tokeni
                .csrf(AbstractHttpConfigurer::disable)

                // Stateless – ne čuvamo sesiju na serveru
                .sessionManagement(session ->
                        session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

                // Pravila pristupa
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/api/auth/login", "/api/auth/register").permitAll()
                        .anyRequest().authenticated()
                )

                // Ubaci JWT filter pre standardnog auth filtera
                .addFilterBefore(jwtRequestFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    /**
     * BCrypt sa strength=12 (oko 300ms po hashu – dobar balans sigurnost/brzina).
     * Strength 10 je default; 12 je preporučeno za produkciju.
     */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }

    /**
     * DaoAuthenticationProvider – koristi naš UserDetailsService i BCrypt.
     * Potreban da bi AuthenticationManager znao kako da verifikuje kredencijale.
     */
    @Bean
    public DaoAuthenticationProvider authenticationProvider() {
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider(userDetailsService);
        provider.setPasswordEncoder(passwordEncoder());
        return provider;
    }

    /**
     * AuthenticationManager koji koristimo u AuthService.login() za
     * verifikaciju username + password kredencijala.
     */
    @Bean
    public AuthenticationManager authenticationManager(
            AuthenticationConfiguration config) throws Exception {
        return config.getAuthenticationManager();
    }
}