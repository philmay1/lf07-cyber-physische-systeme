-- SENTINEL Projekt 06: Datenbank und Tabelle (Tag 6, AB1 und AB3)
-- Wird von einrichten.sh als Datenbank-Administrator (sudo mysql) ausgeführt.
-- Keine PIN-Spalte: gespeichert wird nur der vollständige Argon2-Prüfwert.

CREATE DATABASE IF NOT EXISTS sentinel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;  -- eigene Datenbank, UTF-8 für alle Zeichen
USE sentinel;                                                                             -- alle folgenden Befehle betreffen sie

CREATE TABLE IF NOT EXISTS access_doors (     -- eine Zeile pro Tür
    door_id        VARCHAR(32)  PRIMARY KEY,  -- technische Türkennung, z. B. door01; eindeutig und nie leer
    door_code_hash VARCHAR(255) NOT NULL      -- vollständiger $argon2id$-String; eine Tür ohne Prüfwert ist unzulässig
);
