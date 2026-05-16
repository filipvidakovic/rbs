package ftn.siit.rbs.oblak.server.entity;


import jakarta.persistence.*;
import java.time.OffsetDateTime;

@Entity
@Table(name = "users")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 64)
    private String username;

    /**
     * BCrypt hashed password – nikad plain text.
     */
    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private Role role = Role.USER;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "enabled", nullable = false)
    private boolean enabled = true;

    public enum Role {
        USER, ADMIN
    }

    @PrePersist
    private void onInsert() {
        this.createdAt = OffsetDateTime.now();
    }

    // ── Constructors ──────────────────────────────────────────────────────────

    protected User() {}

    public User(String username, String passwordHash) {
        this.username     = username;
        this.passwordHash = passwordHash;
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    public Long            getId()           { return id; }
    public String          getUsername()     { return username; }
    public String          getPasswordHash() { return passwordHash; }
    public Role            getRole()         { return role; }
    public OffsetDateTime  getCreatedAt()    { return createdAt; }
    public boolean         isEnabled()       { return enabled; }

    public void setRole(Role role)           { this.role = role; }
    public void setEnabled(boolean enabled)  { this.enabled = enabled; }
}