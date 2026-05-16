package ftn.siit.rbs.oblak.server.entity;

import jakarta.persistence.*;
import java.time.OffsetDateTime;

@Entity
@Table(name = "function_registry")
public class FunctionRecord {

    // ── Lifecycle states ──────────────────────────────────────────────────────

    public enum Status {
        PENDING_VERIFICATION,
        VERIFIED,
        REJECTED
    }

    // ── Fields ────────────────────────────────────────────────────────────────

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "url_hash", nullable = false, unique = true, length = 64)
    private String urlHash;

    @Column(name = "storage_path", nullable = false)
    private String storagePath;

    @Column(name = "original_filename", nullable = false)
    private String originalFilename;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private Status status = Status.PENDING_VERIFICATION;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    // ── JPA lifecycle callbacks ───────────────────────────────────────────────

    @PrePersist
    private void onInsert() {
        this.createdAt = OffsetDateTime.now();
    }

    @PreUpdate
    private void onUpdate() {
        this.updatedAt = OffsetDateTime.now();
    }

    // ── Constructors ──────────────────────────────────────────────────────────

    /** Required by JPA. */
    protected FunctionRecord() {}

    public FunctionRecord(String urlHash, String storagePath, String originalFilename) {
        this.urlHash          = urlHash;
        this.storagePath      = storagePath;
        this.originalFilename = originalFilename;
        this.status           = Status.PENDING_VERIFICATION;
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    public Long              getId()               { return id; }
    public String            getUrlHash()          { return urlHash; }
    public String            getStoragePath()      { return storagePath; }
    public String            getOriginalFilename() { return originalFilename; }
    public Status            getStatus()           { return status; }
    public OffsetDateTime    getCreatedAt()        { return createdAt; }
    public OffsetDateTime    getUpdatedAt()        { return updatedAt; }

    public void setStatus(Status status)           { this.status = status; }
    public void setStoragePath(String storagePath) { this.storagePath = storagePath; }
}
