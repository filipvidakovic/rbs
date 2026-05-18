package ftn.siit.rbs.oblak.server.config;


import com.auth0.jwt.exceptions.TokenExpiredException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
public class JwtRequestFilter extends OncePerRequestFilter {
    private final UserDetailsService jwtUserDetailsService;

    public JwtRequestFilter(@Lazy UserDetailsService jwtUserDetailsService, JwtTokenUtil jwtTokenUtil) {
        this.jwtUserDetailsService = jwtUserDetailsService;
        this.jwtTokenUtil = jwtTokenUtil;
    }
    @Autowired
    private final JwtTokenUtil jwtTokenUtil;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (request.getRequestURI().equals("/api/auth/login")) {
            chain.doFilter(request, response);
            return;
        }
        else if (request.getRequestURL().toString().contains("/api/")) {
            System.out.println("#### " + request.getMethod() + ":" + request.getRequestURL());
            System.out.println("#### Authorization: " + request.getHeader("Authorization"));
            String requestTokenHeader = request.getHeader("Authorization");
            String username = null;
            String jwtToken = null;
            if (requestTokenHeader != null && requestTokenHeader.contains("Bearer")) {
                jwtToken = requestTokenHeader.substring(requestTokenHeader.indexOf("Bearer ") + 7);
                System.out.println(">>>>>JWT TOKEN: " + jwtToken);
                try {
                    username = jwtTokenUtil.extractUsername(jwtToken);
                    UserDetails userDetails = this.jwtUserDetailsService.loadUserByUsername(username);
                    if (jwtTokenUtil.validateToken(jwtToken, userDetails)) {
                        UsernamePasswordAuthenticationToken authToken =
                                new UsernamePasswordAuthenticationToken(userDetails, null, userDetails.getAuthorities());
                        authToken.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                        SecurityContextHolder.getContext().setAuthentication(authToken);
                    }

                } catch (IllegalArgumentException e) {
                    logger.warn("Unable to get JWT Token.");
                } catch(TokenExpiredException ex) {
                    logger.error("JWT Token expired!");
                }
            } else {
                logger.warn("JWT Token does not exist.");
            }
        }
        chain.doFilter(request, response);
    }
}
