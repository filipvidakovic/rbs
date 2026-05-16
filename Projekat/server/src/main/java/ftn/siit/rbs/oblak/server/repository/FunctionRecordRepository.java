package ftn.siit.rbs.oblak.server.repository;

import ftn.siit.rbs.oblak.server.entity.FunctionRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface FunctionRecordRepository extends JpaRepository<FunctionRecord, Long> {

    Optional<FunctionRecord> findByUrlHash(String urlHash);
}
